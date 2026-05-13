"""
secure_rag/client.py

加密 RAG 的 Client 角色（party_id=1）。
负责：
- 接收并加载来自 Server 的密态 BERT 权重
- 接收来自 Server 的密态文档库
- 持有自己的明文 query（token id），转 one-hot 后秘密分享出去
- 在密文上完成"双路打分（自己半边）→ 密态 Top-K（自己半边）→ 联合推理"
- 把最终 pool share 发回 Server 帮助还原
"""
from typing import Optional, Dict
import torch
import torch.nn.functional as F

from NssMPC import RingTensor, ArithmeticSecretSharing
from NssMPC.config import DEVICE
from NssMPC.config.runtime import PartyRuntime
from NssMPC.application.neural_network.utils.converter import load_model, share_data
from NssMPC.application.neural_network.layers.mha import SecBertModel

from .config import (
    BERT_CONFIG, NUM_DOCS, TOP_K, SEQ, QUERY_LEN, SEM_DOC_LEN, LEX_DOC_LEN,
    VOCAB_SIZE_BM25, TOTAL_SEQ,
    PRF_ENABLED, PRF_ALPHA, PRF_BETA, PRF_FEEDBACK_SOURCE, PRF_CANDIDATE_POOL_RERANK,
    PRF_RERANK_BOOST,
    SIMHASH_ENABLED, SIMHASH_BITS, SIMHASH_CANDIDATES_M, SIMHASH_SEED,
    SPAN_READER_ENABLED, default_qa_head_path,
    LEX_BM25_ONLINE, LEX_BM25_K1, LEX_BM25_B,
    RERANK_PRE_GEN_ENABLED, RERANK_K1, RERANK_K2, RERANK_ALPHA, RERANK_BETA,
    SEM_PRF_ENABLED, SEM_PRF_ALPHA, SEM_PRF_BETA,
)
from .retrieval import (
    secure_inner_product_score,
    secure_lexical_score,
    secure_top_k_indicator,
    secure_prf_expand_query,
    get_simhash_projection,
    secure_simhash_coarse_to_fine,
    load_qa_head,
    secure_reader_span,
    secure_bm25_online_score,
    secure_fusion_rerank_pregen,
    secure_sem_prf_expand_query,
    secure_rerank_on_candidates,
    secure_rerank_hybrid,
)


def _default_query_token_ids(seq_len: int) -> torch.Tensor:
    """默认 query：[CLS] hello world [SEP] + padding"""
    ids = [101, 7592, 2088, 102] + [0] * max(0, seq_len - 4)
    return torch.tensor([ids[:seq_len]]).to(DEVICE)


def _default_query_multihot(vocab_size_bm25: int) -> torch.Tensor:
    qm = torch.zeros(vocab_size_bm25, 1).to(DEVICE)
    qm[5, 0] = 1.0
    qm[8, 0] = 1.0
    return qm


def run_client(
    client_party,
    query_token_ids: Optional[torch.Tensor] = None,
    query_multihot: Optional[torch.Tensor] = None,
    bm25_vocab: Optional[list] = None,
    bert_config: Optional[Dict] = None,
    tokenizer=None,
    return_holder: Optional[list] = None,
):
    """
    Args:
        client_party: NeuralNetworkCS(type='client') 已 set_*_provider，未 online
        query_token_ids: [1, SEQ] long，query 的 token id（含 [CLS] 等特殊 token）
        query_multihot:  [VOCAB_SIZE_BM25, 1] float，BM25 路用的多热向量
        bert_config:     BERT 模型配置 dict
        tokenizer:       HuggingFace tokenizer 实例（可选；不传就只输出 token id 不 decode 文本）
        return_holder:   若提供 list，会把最终结果 dict append 进去，含
                         'pool', 'rerank_scores', 'answer_token_id', 'answer_text'
    """
    cfg = bert_config or BERT_CONFIG

    client_party.online()
    with PartyRuntime(client_party):
        # ---------- 1. 接收模型 ----------
        model = SecBertModel(cfg)
        for p in model.parameters():
            p.requires_grad = False

        # 准备 query 输入
        ids = query_token_ids.to(DEVICE) if query_token_ids is not None else _default_query_token_ids(SEQ)
        pos = torch.arange(SEQ).unsqueeze(0).to(DEVICE)
        typ = torch.zeros_like(ids).to(DEVICE)
        mask = torch.ones_like(ids, dtype=torch.float32).to(DEVICE)

        oh_ids = F.one_hot(ids, cfg['vocab_size']).float()
        oh_pos = F.one_hot(pos, cfg['max_position_embeddings']).float()
        oh_typ = F.one_hot(typ, cfg['type_vocab_size']).float()

        print("[Client] 执行 Dummy Model 1 (Seq=8)...")
        dummy_ids_8 = torch.zeros(1, SEQ, cfg['vocab_size']).to(DEVICE)
        dummy_pos_8 = torch.zeros(1, SEQ, cfg['max_position_embeddings']).to(DEVICE)
        dummy_typ_8 = torch.zeros(1, SEQ, cfg['type_vocab_size']).to(DEVICE)
        dummy_mask_8 = torch.ones(1, SEQ).to(DEVICE)
        client_party.dummy_model(dummy_ids_8, dummy_pos_8, dummy_typ_8, dummy_mask_8)

        s_local = client_party.receive()
        model = load_model(model, s_local)

        # ---------- 2. 接收文档库 ----------
        print("[Client] 接收密态知识库...")
        my_db_share = client_party.receive()[0]

        # SimHash 粗筛预处理（与 server 端对称）
        my_doc_hashes_share = None
        simhash_proj_ring = None
        if SIMHASH_ENABLED:
            print(f"[Client] 构建 SimHash 投影 W (L={SIMHASH_BITS}, seed={SIMHASH_SEED}) ...")
            simhash_W = get_simhash_projection(cfg['hidden_size'], SIMHASH_BITS, seed=SIMHASH_SEED)
            simhash_proj_ring = RingTensor.convert_to_ring(simhash_W)
            print("[Client] 接收 doc SimHash 比特库 ...")
            my_doc_hashes_share = client_party.receive()[0]

        # 词汇路：根据 LEX_BM25_ONLINE 选择两种 share 接收方式之一
        my_bm25_matrix_share = None
        my_tf_share = None
        my_idf_share = None
        my_doc_norm_share = None
        if LEX_BM25_ONLINE:
            print("[Client] [LEX_BM25_ONLINE] 接收 tf/idf/doc_norm 三个分量 ...")
            my_tf_share = client_party.receive()[0]
            my_idf_share = client_party.receive()[0]
            my_doc_norm_share = client_party.receive()[0]
        else:
            print("[Client] 接收 BM25 密态索引矩阵...")
            my_bm25_matrix_share = client_party.receive()[0]

        print("[Client] 接收文档 Token 数据库...")
        my_db_tokens_share = client_party.receive()[0]

        # ---------- 3. 发送 Query 并编码 ----------
        print("[Client] 发送并编码 Query...")
        s_ids = share_data(oh_ids); client_party.send(s_ids[1])
        s_pos = share_data(oh_pos); client_party.send(s_pos[1])
        s_typ = share_data(oh_typ); client_party.send(s_typ[1])
        client_party.send(RingTensor.convert_to_ring(mask))

        _, query_emb_share = model(
            s_ids[0][0], s_pos[0][0], s_typ[0][0], RingTensor.convert_to_ring(mask)
        )

        # ---------- 4. 双路打分 ----------
        # 当 RERANK_PRE_GEN_ENABLED=True 时双路各取 K1=RERANK_K1 候选 (比默认 TOP_K=1 多)
        sem_top_k1 = RERANK_K1 if RERANK_PRE_GEN_ENABLED else TOP_K
        print(f"[Client] RAG: 参与双路密态打分与召回 (K1={sem_top_k1}{', RERANK_PRE_GEN ON' if RERANK_PRE_GEN_ENABLED else ''})...")
        if SIMHASH_ENABLED:
            print(f"[Client] [Sem round1] SimHash 粗筛 (M={SIMHASH_CANDIDATES_M}) → 密态 cosine 精排 ...")
            top_k_ind_sem_share_pre = secure_simhash_coarse_to_fine(
                query_emb_share, my_db_share, my_doc_hashes_share,
                simhash_proj_ring, SIMHASH_CANDIDATES_M, top_k=sem_top_k1,
            )
            scores_sem_share = None
            # ⭐ Sem 路 PRF round 2 (ReAct-style 多轮检索简化版)
            if SEM_PRF_ENABLED and not RERANK_PRE_GEN_ENABLED:
                feedback_doc_emb_share = top_k_ind_sem_share_pre[0:1] @ my_db_share
                print(f"[Client] [Sem round2] PRF 扩展 query embedding (alpha={SEM_PRF_ALPHA}, beta={SEM_PRF_BETA}) ...")
                q_expanded_emb_share = secure_sem_prf_expand_query(
                    query_emb_share, feedback_doc_emb_share, SEM_PRF_ALPHA, SEM_PRF_BETA,
                )
                print(f"[Client] [Sem round2] 重新走 SimHash 粗筛 + 密态 cosine 精排 ...")
                top_k_ind_sem_share_pre = secure_simhash_coarse_to_fine(
                    q_expanded_emb_share, my_db_share, my_doc_hashes_share,
                    simhash_proj_ring, SIMHASH_CANDIDATES_M, top_k=sem_top_k1,
                )
        else:
            scores_sem_share = secure_inner_product_score(query_emb_share, my_db_share)
            top_k_ind_sem_share_pre = None

        print("[Client] RAG: 执行词汇路(BM25) 打分与排序...")
        qm = query_multihot.to(DEVICE) if query_multihot is not None else _default_query_multihot(VOCAB_SIZE_BM25)
        s_qhot_local, s_qhot_remote = share_data(qm)
        my_query_multihot_share = s_qhot_local[0]
        client_party.send(s_qhot_remote)

        scores_lex_share = secure_lexical_score(my_query_multihot_share, my_bm25_matrix_share) if not LEX_BM25_ONLINE else \
            secure_bm25_online_score(my_query_multihot_share, my_tf_share, my_idf_share, my_doc_norm_share, k1=LEX_BM25_K1)

        # ---------- 5. 第二次 Dummy Model + 密态 Top-K + 取文档 + 拼接 ----------
        print("[Client] 执行 Dummy Model 2 (Seq=56)...")
        dummy_ids_32 = torch.zeros(1, TOTAL_SEQ, cfg['vocab_size']).to(DEVICE)
        dummy_pos_32 = torch.zeros(1, TOTAL_SEQ, cfg['max_position_embeddings']).to(DEVICE)
        dummy_typ_32 = torch.zeros(1, TOTAL_SEQ, cfg['type_vocab_size']).to(DEVICE)
        dummy_mask_32 = torch.ones(1, TOTAL_SEQ).to(DEVICE)
        client_party.dummy_model(dummy_ids_32, dummy_pos_32, dummy_typ_32, dummy_mask_32)

        if SIMHASH_ENABLED:
            top_k_ind_sem_share = top_k_ind_sem_share_pre                              # [K1, N]
        else:
            top_k_ind_sem_share = secure_top_k_indicator(scores_sem_share, k=sem_top_k1)

        print("[Client] RAG: 执行词汇路 Top-K（第一轮）...")
        top_k_ind_lex_round1_share = secure_top_k_indicator(scores_lex_share, k=sem_top_k1)

        if RERANK_PRE_GEN_ENABLED:
            print(f"[Client] [Pre-gen Rerank] 双路融合重排 (alpha={RERANK_ALPHA}, beta={RERANK_BETA}, K1={RERANK_K1}, K2={RERANK_K2}) ...")
            top_k2_ind_share = secure_fusion_rerank_pregen(
                query_emb_share, top_k_ind_sem_share, top_k_ind_lex_round1_share,
                my_db_share, scores_lex_share,
                alpha=RERANK_ALPHA, beta=RERANK_BETA, top_k2=RERANK_K2,
            )
            doc_a_ind = top_k2_ind_share[0:1]
            doc_b_ind = top_k2_ind_share[1:2] if RERANK_K2 >= 2 else top_k2_ind_share[0:1]
            my_doc_sem_share = (doc_a_ind.unsqueeze(-1).unsqueeze(-1) * my_db_tokens_share).sum(dim=1)
            my_doc_lex_share = (doc_b_ind.unsqueeze(-1).unsqueeze(-1) * my_db_tokens_share).sum(dim=1)
            rerank_candidate_pool_ind = None
        else:
            print("[融合] sem 路 Top-K + 取文档 ...")
            expanded_ind_sem = top_k_ind_sem_share.unsqueeze(-1).unsqueeze(-1)
            my_doc_sem_share = (expanded_ind_sem * my_db_tokens_share).sum(dim=1)

            print("[融合] lex 路 Top-K（第一轮）+ 取反馈 doc ...")
            expanded_ind_lex_round1 = top_k_ind_lex_round1_share.unsqueeze(-1).unsqueeze(-1)
            my_doc_lex_round1_share = (expanded_ind_lex_round1 * my_db_tokens_share).sum(dim=1)
            # ⭐ PRF v2: joint inference 始终用 lex_round1（不被 PRF round 2 替换）
            my_doc_lex_share = my_doc_lex_round1_share

            top_k_ind_lex_round2_share = None

            # 密态 PRF 扩展（与 server.py 完全对称）
            # PRF round 2 仅供 candidate pool；不替换 my_doc_lex_share
            if PRF_ENABLED and bm25_vocab is not None:
                if PRF_FEEDBACK_SOURCE == 'sem':
                    feedback_doc_share = my_doc_sem_share
                elif PRF_FEEDBACK_SOURCE == 'both':
                    feedback_doc_share = my_doc_sem_share + my_doc_lex_round1_share
                else:
                    feedback_doc_share = my_doc_lex_round1_share
                print(f"[PRF] 反馈源={PRF_FEEDBACK_SOURCE}, 扩展 query (alpha={PRF_ALPHA}, beta={PRF_BETA}) ...")
                q_expanded_share = secure_prf_expand_query(
                    my_query_multihot_share, feedback_doc_share, bm25_vocab,
                    alpha=PRF_ALPHA, beta=PRF_BETA,
                )
                print("[Client] RAG: 词汇路第二轮打分（PRF 扩展 query, 仅供 candidate pool）...")
                scores_lex_share_round2 = secure_lexical_score(q_expanded_share, my_bm25_matrix_share) if not LEX_BM25_ONLINE else \
                    secure_bm25_online_score(q_expanded_share, my_tf_share, my_idf_share, my_doc_norm_share, k1=LEX_BM25_K1)

                print("[融合] lex 路 Top-K（第二轮）→ 仅供 candidate pool ...")
                top_k_ind_lex_round2_share = secure_top_k_indicator(scores_lex_share_round2, k=TOP_K)

            # ⭐ 构建 PRF 候选池 indicator（与 server.py 完全对称）
            if PRF_CANDIDATE_POOL_RERANK in ('strict', 'hybrid'):
                pool_parts = [top_k_ind_sem_share, top_k_ind_lex_round1_share]
                if top_k_ind_lex_round2_share is not None:
                    pool_parts.append(top_k_ind_lex_round2_share)
                rerank_candidate_pool_ind = ArithmeticSecretSharing.cat(pool_parts, dim=0)
                print(f"[Client] PRF candidate pool 构建: {len(pool_parts)} 个候选 doc indicator (mode={PRF_CANDIDATE_POOL_RERANK})")
            else:
                rerank_candidate_pool_ind = None

        my_query_share = s_ids[0][0]
        my_joint_ids_share = ArithmeticSecretSharing.cat(
            [my_query_share, my_doc_sem_share, my_doc_lex_share], dim=1
        )

        # 构造 56 长度的 pos / typ / mask
        joint_pos = torch.arange(TOTAL_SEQ).unsqueeze(0).to(DEVICE)
        joint_typ = torch.cat([
            torch.zeros(1, QUERY_LEN),
            torch.ones(1, SEM_DOC_LEN),
            torch.ones(1, LEX_DOC_LEN),
        ], dim=1).long().to(DEVICE)
        joint_mask = torch.ones(1, TOTAL_SEQ, dtype=torch.float32).to(DEVICE)

        oh_joint_pos = F.one_hot(joint_pos, cfg['max_position_embeddings']).float()
        oh_joint_typ = F.one_hot(joint_typ, cfg['type_vocab_size']).float()

        s_pos_local, s_pos_remote = share_data(oh_joint_pos); client_party.send(s_pos_remote)
        s_typ_local, s_typ_remote = share_data(oh_joint_typ); client_party.send(s_typ_remote)
        client_party.send(RingTensor.convert_to_ring(joint_mask))

        my_pos_share = s_pos_local[0]
        my_typ_share = s_typ_local[0]

        # ---------- 6. 联合推理（拿 seq_out 用于 reader）----------
        print("[Client] 执行联合推理...")
        seq_out, pool = model(
            my_joint_ids_share, my_pos_share, my_typ_share,
            RingTensor.convert_to_ring(joint_mask),
        )

        print("[Client] 密态 reranker 计算 ...")
        from .retrieval import secure_rerank, secure_reader
        if rerank_candidate_pool_ind is not None and PRF_CANDIDATE_POOL_RERANK == 'hybrid':
            print(f"[Client] [Rerank-Hybrid] 全 N + 候选 boost={PRF_RERANK_BOOST} (候选 {rerank_candidate_pool_ind.shape[0]} 个) ...")
            rerank_logits_share = secure_rerank_hybrid(pool, my_db_share, rerank_candidate_pool_ind, boost=PRF_RERANK_BOOST)
        elif rerank_candidate_pool_ind is not None and PRF_CANDIDATE_POOL_RERANK == 'strict':
            print(f"[Client] [Rerank-Strict] 只在候选池内重排 (候选 {rerank_candidate_pool_ind.shape[0]} 个) ...")
            rerank_logits_share = secure_rerank_on_candidates(pool, my_db_share, rerank_candidate_pool_ind)
        else:
            rerank_logits_share = secure_rerank(pool, my_db_share)

        # ---------- 8. 密态 Reader（双方对称调用，内部含 top_k_indicator + gather）----------
        print("[Client] 密态 reader 抽取答案 ...")
        span_token_oh_share = None
        if SPAN_READER_ENABLED:
            print("[Client] [Reader] 使用 SQuAD-style span head ...")
            qa_W_ring, qa_b_ring = load_qa_head(default_qa_head_path())
            (
                answer_token_oh_share,
                reader_logits_share,
                end_logits_share,
                position_indicator_share,
                span_token_oh_share,
            ) = secure_reader_span(
                seq_out, my_joint_ids_share,
                qa_W_ring, qa_b_ring,
            )
        else:
            answer_token_oh_share, reader_logits_share, position_indicator_share = secure_reader(
                pool, seq_out, my_joint_ids_share,
            )

        # ---------- 9. 接收 server 的三个 share，在 client 端 restore ----------
        # 顺序与 server 端 send 严格对齐：rerank → pool → answer → reader_logits → position_indicator
        print("[Client] 接收 server 端 share 并 restore ...")
        s_rerank = client_party.receive()
        final_rerank = ArithmeticSecretSharing.restore_from_shares(rerank_logits_share, s_rerank)
        rerank_scores_real = final_rerank.convert_to_real_field().view(-1)         # [NUM_DOCS]

        s_pool = client_party.receive()
        final_pool = ArithmeticSecretSharing.restore_from_shares(pool, s_pool)
        pool_real = final_pool.convert_to_real_field()                             # [1, hidden]

        s_answer = client_party.receive()
        final_answer = ArithmeticSecretSharing.restore_from_shares(answer_token_oh_share, s_answer)
        answer_oh = final_answer.convert_to_real_field()                           # [1, V]
        # SPAN reader 输出的是 span 内 token one-hot 之和（多个非零位置）
        # 启发式 reader 输出的是单个 token 的 one-hot
        if SPAN_READER_ENABLED:
            # nonzero 位置 = span 包含的所有 token id
            answer_oh_flat = answer_oh.view(-1)                                    # [V]
            nz_mask = answer_oh_flat > 0.5                                          # 容忍数值噪声
            span_token_ids = nz_mask.nonzero(as_tuple=True)[0].tolist()            # 多个 token id
            if not span_token_ids:
                # 退化保护：取 argmax
                span_token_ids = [int(answer_oh_flat.argmax().item())]
            answer_token_id = span_token_ids[0]
        else:
            span_token_ids = [int(answer_oh.argmax(dim=-1).item())]
            answer_token_id = span_token_ids[0]

        # 诊断信息（reader logits 与 position indicator）
        s_reader_logits = client_party.receive()
        final_reader_logits = ArithmeticSecretSharing.restore_from_shares(reader_logits_share, s_reader_logits)
        reader_logits_real = final_reader_logits.convert_to_real_field().view(-1)  # [seq_len]

        s_position = client_party.receive()
        final_position = ArithmeticSecretSharing.restore_from_shares(position_indicator_share, s_position)
        position_real = final_position.convert_to_real_field().view(-1)            # [seq_len]
        if SPAN_READER_ENABLED:
            # span_mask is the position vector; first nonzero = start_pos
            nz = (position_real > 0.5).nonzero(as_tuple=True)[0]
            answer_position = int(nz[0].item()) if nz.numel() > 0 else 0
        else:
            answer_position = int(position_real.argmax().item())

        # SPAN_READER_ENABLED 多收一个 share：[1, L, V] span 内每个位置的 token one-hot
        ordered_span_token_ids = None
        if SPAN_READER_ENABLED:
            s_span_oh = client_party.receive()
            final_span_oh = ArithmeticSecretSharing.restore_from_shares(span_token_oh_share, s_span_oh)
            span_oh_real = final_span_oh.convert_to_real_field().view(span_token_oh_share.shape[1], -1)  # [L, V]
            # 在 span 位置（position_real > 0.5）做明文 argmax 取 token id
            nz_pos = (position_real > 0.5).nonzero(as_tuple=True)[0]
            ordered_span_token_ids = []
            for pos_i in nz_pos.tolist():
                tok_id = int(span_oh_real[pos_i].argmax().item())
                ordered_span_token_ids.append(tok_id)
            if not ordered_span_token_ids:
                ordered_span_token_ids = span_token_ids
            span_token_ids = ordered_span_token_ids
            answer_token_id = span_token_ids[0] if span_token_ids else 0

        # ---------- 10. 用 tokenizer decode 答案 token ----------
        answer_text = None
        if tokenizer is not None:
            try:
                answer_text = tokenizer.decode(span_token_ids).strip()
            except Exception as e:
                answer_text = f"<decode_error: {e}>"

        # ---------- 11. 打印 + 写出结果 ----------
        print(f"\n=== [Client] Rerank 分数 (在 client 端 restore) ===")
        print(f"shape={tuple(rerank_scores_real.shape)}, scores={rerank_scores_real.tolist()}")
        rerank_top_k = torch.topk(rerank_scores_real, k=min(5, rerank_scores_real.shape[0])).indices
        print(f"Rerank top-{rerank_top_k.shape[0]} doc id: {rerank_top_k.tolist()}")

        print(f"\n=== [Client] 联合推理 Pooler 输出 (在 client 端 restore) ===")
        print(f"shape={tuple(pool_real.shape)} first5: {pool_real[:, :5]}")
        print(f"abs_max: {pool_real.abs().max().item()} mean: {pool_real.mean().item()}")

        print(f"\n=== [Client] Reader 抽取答案 ===")
        print(f"answer_position (在联合序列中的位置): {answer_position} / {position_real.shape[0]}")
        print(f"answer_token_id: {answer_token_id}")
        if answer_text is not None:
            print(f"answer_text: {answer_text!r}")

        if return_holder is not None:
            return_holder.append({
                'pool':              pool_real.detach().cpu(),
                'rerank_scores':     rerank_scores_real.detach().cpu(),
                'answer_token_id':   answer_token_id,
                'answer_text':       answer_text,
                'answer_position':   answer_position,
                'reader_logits':     reader_logits_real.detach().cpu(),
                'span_token_ids':    span_token_ids,
            })

    client_party.close()
