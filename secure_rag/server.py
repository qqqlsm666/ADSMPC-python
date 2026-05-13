"""
secure_rag/server.py

加密 RAG 的 Server 角色（party_id=0）。
负责：
- 持有并秘密分享 BERT 模型
- 持有并秘密分享文档库（embedding / BM25 矩阵 / token 库）
- 在密文上完成"双路打分 → 密态 Top-K → 取真实文档 → 联合 BERT 推理"
- 把最终 pooler 输出收回还原（明文）

为了既能在原 rag.py 的"假数据 demo"模式下跑，也能在 experiments/ 下注入真实数据，
本文件提供了 `run_server(party, db, model_state_dict)` 风格的函数式 API。
"""
from typing import Optional, Dict
import torch
import torch.nn.functional as F

from NssMPC import RingTensor, ArithmeticSecretSharing
from NssMPC.config import DEVICE
from NssMPC.config.runtime import PartyRuntime
from NssMPC.application.neural_network.utils.converter import share_model, load_model, share_data
from NssMPC.application.neural_network.layers.mha import SecBertModel

from .config import (
    BERT_CONFIG, NUM_DOCS, TOP_K, SEQ, SEM_DOC_LEN, VOCAB_SIZE_BM25, TOTAL_SEQ,
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
    plaintext_simhash_bits,
    secure_simhash_coarse_to_fine,
    load_qa_head,
    secure_reader_span,
    secure_bm25_online_score,
    secure_fusion_rerank_pregen,
    secure_sem_prf_expand_query,
    secure_rerank_on_candidates,
    secure_rerank_hybrid,
)


def load_bert_weights(model: SecBertModel, weight_path: str, log_prefix: str = "[Server]") -> int:
    """把 bert-tiny 权重 load 到 SecBertModel 的明文 parameters 里。返回成功 load 的参数个数。"""
    import os as _os
    if not _os.path.exists(weight_path):
        print(f"{log_prefix} 警告: 未找到权重文件 {weight_path}, 使用零初始化（pooler 会输出 0）")
        return 0
    print(f"{log_prefix} 加载 bert-tiny 权重: {weight_path}")
    state_dict = torch.load(weight_path, map_location=DEVICE)
    state_dict.pop('embeddings.position_ids', None)
    new_state_dict = {(k[5:] if k.startswith('bert.') else k): v for k, v in state_dict.items()}
    loaded, missing = 0, []
    for name, p in model.named_parameters():
        if name in new_state_dict:
            p.data = new_state_dict[name].to(DEVICE).to(torch.float32)
            loaded += 1
        else:
            missing.append(name)
    print(f"{log_prefix} 权重加载完成: loaded={loaded}, missing={len(missing)}")
    if missing:
        print(f"{log_prefix} 缺失权重示例: {missing[:5]}")
    return loaded


def run_server(
    server_party,
    db_embeddings: Optional[torch.Tensor] = None,
    bm25_matrix: Optional[torch.Tensor] = None,
    db_tokens_onehot: Optional[torch.Tensor] = None,
    bm25_vocab: Optional[list] = None,
    weight_path: Optional[str] = None,
    bert_config: Optional[Dict] = None,
    return_holder: Optional[list] = None,
    bm25_components: Optional[Dict] = None,
):
    """
    Args:
        ...
        bm25_components: 仅当 LEX_BM25_ONLINE=True 使用，dict 含 'tf' [V,N], 'idf' [V], 'doc_norm' [N]
                         （其中 doc_norm = k1*(1-b+b*|d|/avgdl)）。如果 None 且 LEX_BM25_ONLINE=True
                         会回退到 plaintext.build_bm25_components 现场计算（要求 server 有 docs_token_ids 信息）。
    """
    """
    Args:
        server_party: NeuralNetworkCS(type='server') 已 set_*_provider，未 online
        db_embeddings:    [NUM_DOCS, hidden]，文档语义向量库（明文）。None 则用 torch.randn 占位
        bm25_matrix:      [VOCAB_SIZE_BM25, NUM_DOCS]，词汇路打分矩阵（明文，正数）
        db_tokens_onehot: [NUM_DOCS, SEM_DOC_LEN, vocab_size]，文档 token 的 one-hot 表示
        weight_path:      bert-tiny 权重路径
        bert_config:      BERT 模型配置 dict
        return_holder:    若提供 list，会把 final_pool 这个 [1, hidden] 的 torch.Tensor append 进去

    最终 pooler 输出会打印，并（如指定 return_holder）写入 return_holder[0]
    """
    cfg = bert_config or BERT_CONFIG

    server_party.online()
    with PartyRuntime(server_party):
        # ---------- 1. 准备模型 ----------
        model = SecBertModel(cfg)
        for p in model.parameters():
            p.requires_grad = False
        if weight_path is not None:
            load_bert_weights(model, weight_path, log_prefix="[Server]")

        model_for_dummy = SecBertModel(cfg)
        print("[Server] 执行 Dummy Model 1 (Seq=8)...")
        server_party.dummy_model(model_for_dummy)

        s_local, s_remote = share_model(model)
        server_party.send(s_remote)
        model = load_model(model, s_local)

        # ---------- 2. 准备并分享文档库 ----------
        if db_embeddings is None:
            db_embeddings = torch.randn(NUM_DOCS, cfg['hidden_size']).to(DEVICE)
        else:
            db_embeddings = db_embeddings.to(DEVICE)
        if bm25_matrix is None:
            bm25_matrix = torch.abs(torch.randn(VOCAB_SIZE_BM25, NUM_DOCS)).to(DEVICE)
        else:
            bm25_matrix = bm25_matrix.to(DEVICE)
        if db_tokens_onehot is None:
            db_tokens_ids = torch.randint(0, cfg['vocab_size'], (NUM_DOCS, SEM_DOC_LEN)).to(DEVICE)
            db_tokens_onehot = F.one_hot(db_tokens_ids, cfg['vocab_size']).float()
        else:
            db_tokens_onehot = db_tokens_onehot.to(DEVICE)

        print("[Server] 构建并分享密态知识库...")
        s_db_local, s_db_remote = share_data(db_embeddings)
        server_party.send(s_db_remote)
        my_db_share = s_db_local[0]

        # SimHash 粗筛预处理：离线明文计算 doc_hashes，再 share 给 client
        # （doc_hashes 是 [N, L] 的 0/1 矩阵；W 是双方共享的公开投影矩阵）
        my_doc_hashes_share = None
        simhash_proj_ring = None
        if SIMHASH_ENABLED:
            print(f"[Server] 构建 SimHash 投影 W (L={SIMHASH_BITS}, seed={SIMHASH_SEED}) ...")
            simhash_W = get_simhash_projection(cfg['hidden_size'], SIMHASH_BITS, seed=SIMHASH_SEED)
            simhash_proj_ring = RingTensor.convert_to_ring(simhash_W)
            print("[Server] 离线计算 doc SimHash 比特 (plaintext) 并分享 ...")
            doc_hashes_plain = plaintext_simhash_bits(db_embeddings, simhash_W)        # [N, L] in {0, 1}
            s_dh_local, s_dh_remote = share_data(doc_hashes_plain)
            server_party.send(s_dh_remote)
            my_doc_hashes_share = s_dh_local[0]

        # 词汇路：根据 LEX_BM25_ONLINE 选择两种 share 方式之一
        my_bm25_matrix_share = None
        my_tf_share = None
        my_idf_share = None
        my_doc_norm_share = None
        if LEX_BM25_ONLINE:
            print("[Server] [LEX_BM25_ONLINE] 分别 share tf/idf/doc_norm 三个分量 ...")
            if bm25_components is None:
                # 没传 components 但开了 ONLINE 模式：报错
                raise RuntimeError(
                    "LEX_BM25_ONLINE=True 但未传 bm25_components；"
                    "请用 secure_rag.plaintext.build_bm25_components 算好后传入"
                )
            tf_plain = bm25_components['tf'].to(DEVICE)              # [V, N]
            idf_plain = bm25_components['idf'].to(DEVICE)            # [V]
            doc_norm_plain = bm25_components['doc_norm'].to(DEVICE)  # [N]

            s_tf_local, s_tf_remote = share_data(tf_plain)
            server_party.send(s_tf_remote)
            my_tf_share = s_tf_local[0]

            s_idf_local, s_idf_remote = share_data(idf_plain)
            server_party.send(s_idf_remote)
            my_idf_share = s_idf_local[0]

            s_dn_local, s_dn_remote = share_data(doc_norm_plain)
            server_party.send(s_dn_remote)
            my_doc_norm_share = s_dn_local[0]
        else:
            print("[Server] 构建并分享 BM25 倒排矩阵 (词汇路)...")
            s_bm25_local, s_bm25_remote = share_data(bm25_matrix)
            server_party.send(s_bm25_remote)
            my_bm25_matrix_share = s_bm25_local[0]

        print("[Server] 构建并分享文档 Token 数据库...")
        s_db_tokens_local, s_db_tokens_remote = share_data(db_tokens_onehot)
        server_party.send(s_db_tokens_remote)
        my_db_tokens_share = s_db_tokens_local[0]

        # ---------- 3. 接收 Client Query 并编码 ----------
        print("[Server] 等待 Client 输入 Query...")
        sh_in = server_party.receive()
        sh_pos = server_party.receive()
        sh_type = server_party.receive()
        mask = server_party.receive()

        print("[Server] 提取 Query 密态 Embedding...")
        _, query_emb_share = model(sh_in[0], sh_pos[0], sh_type[0], mask)

        # ---------- 4. 双路打分 ----------
        # 当 RERANK_PRE_GEN_ENABLED=True 时双路各取 K1=RERANK_K1 个候选 (比默认 TOP_K=1 多)
        sem_top_k1 = RERANK_K1 if RERANK_PRE_GEN_ENABLED else TOP_K
        print(f"[Server] RAG: 开始双路密态打分与召回 (K1={sem_top_k1}{', RERANK_PRE_GEN ON' if RERANK_PRE_GEN_ENABLED else ''})...")
        if SIMHASH_ENABLED:
            # Pisces-aligned 语义路: SimHash 粗筛 → 密态 cosine 精排 → top-K1 indicator
            print(f"[Server] [Sem round1] SimHash 粗筛 (M={SIMHASH_CANDIDATES_M}) → 密态 cosine 精排 ...")
            top_k_ind_sem_share_pre = secure_simhash_coarse_to_fine(
                query_emb_share, my_db_share, my_doc_hashes_share,
                simhash_proj_ring, SIMHASH_CANDIDATES_M, top_k=sem_top_k1,
            )
            scores_sem_share = None
            # ⭐ Sem 路 PRF round 2 (ReAct-style 多轮检索简化版)
            if SEM_PRF_ENABLED and not RERANK_PRE_GEN_ENABLED:
                # round 1 sem top-1 indicator [1, N]，提取 doc embedding [1, hidden]
                feedback_doc_emb_share = top_k_ind_sem_share_pre[0:1] @ my_db_share
                print(f"[Server] [Sem round2] PRF 扩展 query embedding (alpha={SEM_PRF_ALPHA}, beta={SEM_PRF_BETA}) ...")
                q_expanded_emb_share = secure_sem_prf_expand_query(
                    query_emb_share, feedback_doc_emb_share, SEM_PRF_ALPHA, SEM_PRF_BETA,
                )
                print(f"[Server] [Sem round2] 重新走 SimHash 粗筛 + 密态 cosine 精排 ...")
                top_k_ind_sem_share_pre = secure_simhash_coarse_to_fine(
                    q_expanded_emb_share, my_db_share, my_doc_hashes_share,
                    simhash_proj_ring, SIMHASH_CANDIDATES_M, top_k=sem_top_k1,
                )
        else:
            scores_sem_share = secure_inner_product_score(query_emb_share, my_db_share)
            top_k_ind_sem_share_pre = None

        print("[Server] RAG: 执行词汇路(BM25) 打分与排序...")
        my_query_multihot_share = server_party.receive()[0]
        if LEX_BM25_ONLINE:
            print(f"[Server] [LEX_BM25_ONLINE] 在线密态 BM25 公式 (k1={LEX_BM25_K1}) ...")
            scores_lex_share = secure_bm25_online_score(
                my_query_multihot_share, my_tf_share, my_idf_share, my_doc_norm_share,
                k1=LEX_BM25_K1,
            )
        else:
            scores_lex_share = secure_lexical_score(my_query_multihot_share, my_bm25_matrix_share)

        # ---------- 5. 第二次 Dummy Model（为 Seq=56 联合推理生成参数）+ 密态 Top-K + 取文档 + 拼接 ----------
        print("[Server] 执行 Dummy Model 2 (Seq=56)...")
        server_party.dummy_model(model_for_dummy)

        print("[融合] sem 路 Top-K + 取文档 ...")
        if SIMHASH_ENABLED:
            top_k_ind_sem_share = top_k_ind_sem_share_pre                              # [K1, N]
        else:
            top_k_ind_sem_share = secure_top_k_indicator(scores_sem_share, k=sem_top_k1)  # [K1, N]

        print("[融合] lex 路 Top-K（第一轮）+ 取反馈 doc ...")
        top_k_ind_lex_round1_share = secure_top_k_indicator(scores_lex_share, k=sem_top_k1)
        # 注意：在 RERANK_PRE_GEN_ENABLED=True 模式下，sem_top_k1 == RERANK_K1（双路对齐）

        if RERANK_PRE_GEN_ENABLED:
            # ⭐ Pre-generation Reranker 模式：双路 K1 候选 → fusion rerank → top-K2 → joint inference
            # 强制忽略 PRF（多阶段策略互斥）
            print(f"[Server] [Pre-gen Rerank] 双路融合重排 (alpha={RERANK_ALPHA}, beta={RERANK_BETA}, K1={RERANK_K1}, K2={RERANK_K2}) ...")
            top_k2_ind_share = secure_fusion_rerank_pregen(
                query_emb_share, top_k_ind_sem_share, top_k_ind_lex_round1_share,
                my_db_share, scores_lex_share,
                alpha=RERANK_ALPHA, beta=RERANK_BETA, top_k2=RERANK_K2,
            )                                                                            # ASS [K2, N]
            doc_a_ind = top_k2_ind_share[0:1]
            doc_b_ind = top_k2_ind_share[1:2] if RERANK_K2 >= 2 else top_k2_ind_share[0:1]
            my_doc_sem_share = (doc_a_ind.unsqueeze(-1).unsqueeze(-1) * my_db_tokens_share).sum(dim=1)
            my_doc_lex_share = (doc_b_ind.unsqueeze(-1).unsqueeze(-1) * my_db_tokens_share).sum(dim=1)
            # Pre-gen Rerank 模式不需要 candidate pool（已经在 fusion rerank 里筛过了）
            rerank_candidate_pool_ind = None
        else:
            # 默认模式：sem top-1 + lex top-1 → joint inference
            # ⭐ PRF v2 修复: joint inference 用 lex_round1 (跟 baseline 一致，不被 PRF 覆盖)
            # PRF round 2 的 doc 仅作为 reranker candidate pool 的额外候选
            expanded_ind_sem = top_k_ind_sem_share.unsqueeze(-1).unsqueeze(-1)
            my_doc_sem_share = (expanded_ind_sem * my_db_tokens_share).sum(dim=1)

            expanded_ind_lex_round1 = top_k_ind_lex_round1_share.unsqueeze(-1).unsqueeze(-1)
            my_doc_lex_round1_share = (expanded_ind_lex_round1 * my_db_tokens_share).sum(dim=1)
            # joint inference 用 lex_round1，**始终不被 PRF 替代**
            my_doc_lex_share = my_doc_lex_round1_share

            top_k_ind_lex_round2_share = None  # 仅 PRF on 时填充

            # 密态 PRF 扩展：用反馈源 doc 的 token 频率反过来扩展 query
            # PRF round 2 的 doc 不再替换 my_doc_lex_share，仅进 candidate pool
            if PRF_ENABLED and bm25_vocab is not None:
                if PRF_FEEDBACK_SOURCE == 'sem':
                    feedback_doc_share = my_doc_sem_share
                elif PRF_FEEDBACK_SOURCE == 'both':
                    feedback_doc_share = my_doc_sem_share + my_doc_lex_round1_share
                else:  # 'lex'
                    feedback_doc_share = my_doc_lex_round1_share
                print(f"[PRF] 反馈源={PRF_FEEDBACK_SOURCE}, 扩展 query (alpha={PRF_ALPHA}, beta={PRF_BETA}) ...")
                q_expanded_share = secure_prf_expand_query(
                    my_query_multihot_share, feedback_doc_share, bm25_vocab,
                    alpha=PRF_ALPHA, beta=PRF_BETA,
                )
                print("[Server] RAG: 词汇路第二轮打分（PRF 扩展 query, 仅供 candidate pool）...")
                scores_lex_share_round2 = secure_lexical_score(q_expanded_share, my_bm25_matrix_share) if not LEX_BM25_ONLINE else \
                    secure_bm25_online_score(q_expanded_share, my_tf_share, my_idf_share, my_doc_norm_share, k1=LEX_BM25_K1)

                print("[融合] lex 路 Top-K（第二轮）→ 仅供 candidate pool ...")
                top_k_ind_lex_round2_share = secure_top_k_indicator(scores_lex_share_round2, k=TOP_K)
                # 注意：不再替换 my_doc_lex_share；joint inference 输入仍是 lex_round1

            # ⭐ 构建 PRF 候选池 indicator (用于 PRF_CANDIDATE_POOL_RERANK)
            if PRF_CANDIDATE_POOL_RERANK in ('strict', 'hybrid'):
                pool_parts = [top_k_ind_sem_share, top_k_ind_lex_round1_share]
                if top_k_ind_lex_round2_share is not None:
                    pool_parts.append(top_k_ind_lex_round2_share)
                rerank_candidate_pool_ind = ArithmeticSecretSharing.cat(pool_parts, dim=0)  # [K_cand, N]
                print(f"[Server] PRF candidate pool 构建: {len(pool_parts)} 个候选 doc indicator (mode={PRF_CANDIDATE_POOL_RERANK})")
            else:
                rerank_candidate_pool_ind = None

        my_query_share = sh_in[0]
        my_joint_ids_share = ArithmeticSecretSharing.cat(
            [my_query_share, my_doc_sem_share, my_doc_lex_share], dim=1
        )

        # 接收 Client 发来的 56 长度辅助张量
        my_pos_share = server_party.receive()[0]
        my_typ_share = server_party.receive()[0]
        joint_mask = server_party.receive()

        # ---------- 6. 联合推理 ----------
        print("[Server] 执行联合推理...")
        seq_out, pool = model(my_joint_ids_share, my_pos_share, my_typ_share, joint_mask)

        # ---------- 7. 密态 Reranker ----------
        # PRF_CANDIDATE_POOL_RERANK='hybrid': 全 N + 候选 boost（推荐 default）
        # PRF_CANDIDATE_POOL_RERANK='strict': 只在候选池内重排（ablation 用）
        # PRF_CANDIDATE_POOL_RERANK='none':   重排全 N 库
        print("[Server] 密态 reranker 计算 ...")
        from .retrieval import secure_rerank, secure_reader
        if rerank_candidate_pool_ind is not None and PRF_CANDIDATE_POOL_RERANK == 'hybrid':
            print(f"[Server] [Rerank-Hybrid] 全 N + 候选 boost={PRF_RERANK_BOOST} (候选 {rerank_candidate_pool_ind.shape[0]} 个) ...")
            rerank_logits_share = secure_rerank_hybrid(pool, my_db_share, rerank_candidate_pool_ind, boost=PRF_RERANK_BOOST)
        elif rerank_candidate_pool_ind is not None and PRF_CANDIDATE_POOL_RERANK == 'strict':
            print(f"[Server] [Rerank-Strict] 只在候选池内重排 (候选 {rerank_candidate_pool_ind.shape[0]} 个) ...")
            rerank_logits_share = secure_rerank_on_candidates(pool, my_db_share, rerank_candidate_pool_ind)
        else:
            rerank_logits_share = secure_rerank(pool, my_db_share)

        # ---------- 8. 密态 Reader（抽取式生成）----------
        # SPAN_READER_ENABLED:  SQuAD-style start/end head（来自 mrm8488/bert-tiny-finetuned-squadv2）
        # 否则走旧的启发式 head: pool · seq_out → 密态 argmax → 密态 gather 单 token
        # 整条流程双方都看不到答案位置或答案 token，最后只在 client 端 restore。
        print("[Server] 密态 reader 抽取答案 ...")
        span_token_oh_share = None
        if SPAN_READER_ENABLED:
            print("[Server] [Reader] 使用 SQuAD-style span head ...")
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

        # ---------- 9. 输出方向反转：三个 share 全部 send 给 client，client 端 restore ----------
        # 这样 server 全程不学习到 query 相关的信息：reranker 分数、pool 数值、答案 token 都
        # 在 client 端还原。Server 只持有自己的文档库（本来就有），不学习客户端的查询、检索结果或答案。
        print("[Server] 把 rerank / pool / answer 三个 share 发给 client ...")
        server_party.send(rerank_logits_share)   # client 端 restore 拿到精排分数
        server_party.send(pool)                  # client 端 restore 拿到 pool（实验数值一致性用）
        server_party.send(answer_token_oh_share) # client 端 restore 拿到答案 token one-hot

        # 实验诊断：把 server 端持有的 share（不是明文）写出去，便于 client 端做数值一致性对比时
        # 拿到 server 端的 reader_logits / position_indicator share 也能在 client 端 restore。
        # 不过这两个用于诊断而非最终输出，所以也走 send。
        server_party.send(reader_logits_share)
        server_party.send(position_indicator_share)

        # span reader 额外发送：[1, L, V] span 内每个位置的 token one-hot，client 端按位置 argmax 解出 token id
        if SPAN_READER_ENABLED:
            server_party.send(span_token_oh_share)

        if return_holder is not None:
            # Server 端不再持有最终结果（已经全部送给 client）；这里只填空 dict 占位，
            # 真正的结果由 client 端的 run_client 写出。
            return_holder.append({})

    server_party.close()
