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
):
    """
    Args:
        client_party: NeuralNetworkCS(type='client') 已 set_*_provider，未 online
        query_token_ids: [1, SEQ] long，query 的 token id（含 [CLS] 等特殊 token）
        query_multihot:  [VOCAB_SIZE_BM25, 1] float，BM25 路用的多热向量
        bert_config:     BERT 模型配置 dict
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

        # ---------- 6. 联合推理 ----------
        print("[Client] 执行联合推理...")
        _, pool = model(
            my_joint_ids_share, my_pos_share, my_typ_share,
            RingTensor.convert_to_ring(joint_mask),
        )

        # ---------- 7. 密态 Reranker（B2 方案）----------
        # 与 server 对称：双方各自调一次 secure_rerank（内部 secure_matmul 会双向通信），
        # 然后 client 把自己那一半 share 发给 server，server 端做 restore。
        print("[Client] 密态 reranker 计算 ...")
        from .retrieval import secure_rerank
        rerank_logits_share = secure_rerank(pool, my_db_share)
        client_party.send(rerank_logits_share)   # 先发 rerank（与 server 的 receive 顺序对齐）

        # ---------- 8. 把 pool 发给 server 还原（保留兼容）----------
        client_party.send(pool)

    client_party.close()
