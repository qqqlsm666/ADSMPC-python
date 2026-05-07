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
)
from .retrieval import (
    secure_inner_product_score,
    secure_lexical_score,
    secure_top_k_indicator,
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
        print("[Client] RAG: 参与双路密态打分与召回...")
        scores_sem_share = secure_inner_product_score(query_emb_share, my_db_share)

        print("[Client] RAG: 执行词汇路(BM25) 打分与排序...")
        qm = query_multihot.to(DEVICE) if query_multihot is not None else _default_query_multihot(VOCAB_SIZE_BM25)
        s_qhot_local, s_qhot_remote = share_data(qm)
        my_query_multihot_share = s_qhot_local[0]
        client_party.send(s_qhot_remote)

        scores_lex_share = secure_lexical_score(my_query_multihot_share, my_bm25_matrix_share)

        # ---------- 5. 第二次 Dummy Model + 密态 Top-K + 取文档 + 拼接 ----------
        print("[Client] 执行 Dummy Model 2 (Seq=56)...")
        dummy_ids_32 = torch.zeros(1, TOTAL_SEQ, cfg['vocab_size']).to(DEVICE)
        dummy_pos_32 = torch.zeros(1, TOTAL_SEQ, cfg['max_position_embeddings']).to(DEVICE)
        dummy_typ_32 = torch.zeros(1, TOTAL_SEQ, cfg['type_vocab_size']).to(DEVICE)
        dummy_mask_32 = torch.ones(1, TOTAL_SEQ).to(DEVICE)
        client_party.dummy_model(dummy_ids_32, dummy_pos_32, dummy_typ_32, dummy_mask_32)

        top_k_ind_sem_share = secure_top_k_indicator(scores_sem_share, k=TOP_K)
        top_k_ind_lex_share = secure_top_k_indicator(scores_lex_share, k=TOP_K)

        print("[融合] 通过密态指示器，提取真实 Token 序列...")
        expanded_ind_sem = top_k_ind_sem_share.unsqueeze(-1).unsqueeze(-1)
        my_doc_sem_share = (expanded_ind_sem * my_db_tokens_share).sum(dim=1)

        expanded_ind_lex = top_k_ind_lex_share.unsqueeze(-1).unsqueeze(-1)
        my_doc_lex_share = (expanded_ind_lex * my_db_tokens_share).sum(dim=1)

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

        # ---------- 7. 密态 Reranker（双方对称调用一次 secure_matmul）----------
        print("[Client] 密态 reranker 计算 ...")
        from .retrieval import secure_rerank, secure_reader
        rerank_logits_share = secure_rerank(pool, my_db_share)

        # ---------- 8. 密态 Reader（双方对称调用，内部含 top_k_indicator + gather）----------
        print("[Client] 密态 reader 抽取答案 ...")
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
        answer_token_id = int(answer_oh.argmax(dim=-1).item())

        # 诊断信息（reader logits 与 position indicator）
        s_reader_logits = client_party.receive()
        final_reader_logits = ArithmeticSecretSharing.restore_from_shares(reader_logits_share, s_reader_logits)
        reader_logits_real = final_reader_logits.convert_to_real_field().view(-1)  # [seq_len]

        s_position = client_party.receive()
        final_position = ArithmeticSecretSharing.restore_from_shares(position_indicator_share, s_position)
        position_real = final_position.convert_to_real_field().view(-1)            # [seq_len]
        answer_position = int(position_real.argmax().item())

        # ---------- 10. 用 tokenizer decode 答案 token ----------
        answer_text = None
        if tokenizer is not None:
            try:
                answer_text = tokenizer.decode([answer_token_id]).strip()
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
            })

    client_party.close()
