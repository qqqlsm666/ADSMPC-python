"""
secure_rag/retrieval.py

密态 RAG 三个核心检索函数（保持原 rag.py 实现不变，仅搬位置 + 重命名去掉 _placeholder 后缀）：
- secure_inner_product_score: 语义路打分（query_emb · doc_embs）
- secure_lexical_score:       词汇路简化 TF-IDF 打分（query_multihot · bm25_matrix）
- secure_top_k_indicator:     密态 Top-K 排序（指示器版冒泡）
"""
import torch
from NssMPC import RingTensor, ArithmeticSecretSharing
from NssMPC.config import DEVICE


def secure_inner_product_score(query_emb_share, doc_embs_share):
    """
    [语义路] 密态内积打分。
    query_emb_share: ASS, shape [1, hidden]
    doc_embs_share:  ASS, shape [NUM_DOCS, hidden]
    返回:            ASS, shape [NUM_DOCS]
    """
    element_wise_prod = query_emb_share * doc_embs_share
    scores_share = element_wise_prod.sum(dim=-1)
    return scores_share


def secure_lexical_score(query_multihot_share, bm25_matrix_share):
    """
    [词汇路] 密态简化 TF-IDF 打分。
    query_multihot_share: ASS, shape [VOCAB, 1]
    bm25_matrix_share:    ASS, shape [VOCAB, NUM_DOCS]
    返回:                  ASS, shape [NUM_DOCS]
    """
    element_wise_prod = query_multihot_share * bm25_matrix_share
    return element_wise_prod.sum(dim=0)


def secure_top_k_indicator(scores_share, k):
    """
    [Top-K] 密态冒泡排序，返回 [k, NUM_DOCS] 的 one-hot 指示器（密态）。
    交换的不是文档本体，而是事先生成的"身份证向量"（明文 eye(NUM_DOCS) 包成 ASS）。
    """
    num_docs = scores_share.shape[-1]
    scores_share_1d = scores_share.view(-1)
    scores_list = [scores_share_1d[i] for i in range(num_docs)]

    indicators_plain = torch.eye(num_docs).to(DEVICE)
    doc_indicators_list = [
        ArithmeticSecretSharing(RingTensor.convert_to_ring(indicators_plain[i]))
        for i in range(num_docs)
    ]

    for i in range(k):
        for j in range(num_docs - 1, i, -1):
            cond = scores_list[j] > scores_list[j - 1]

            score_diff = scores_list[j] - scores_list[j - 1]
            score_swap_term = cond * score_diff
            scores_list[j - 1] = scores_list[j - 1] + score_swap_term
            scores_list[j] = scores_list[j] - score_swap_term

            ind_diff = doc_indicators_list[j] - doc_indicators_list[j - 1]
            ind_swap_term = cond * ind_diff
            doc_indicators_list[j - 1] = doc_indicators_list[j - 1] + ind_swap_term
            doc_indicators_list[j] = doc_indicators_list[j] - ind_swap_term

    top_k_indicators_list = doc_indicators_list[:k]
    top_k_indicators_expanded = [ind.unsqueeze(0) for ind in top_k_indicators_list]
    return ArithmeticSecretSharing.cat(top_k_indicators_expanded, dim=0)


def secure_rerank(pool_share, db_embs_share):
    """
    [Reranker] 密态 cross-encoder reranker。

    把联合推理产出的 pool [1, hidden] 跟原始文档库 db_embs [N_DOCS, hidden]
    做密态 matmul，得到每篇 doc 的"重排序分数"。这是真正用上联合推理 BERT
    输出的环节——pool 已经融合了 query + 双路 doc 的语义信息，再跟纯 doc 语义
    库比对，相当于一个在双路初次检索之上做精排的密态 cross-encoder。

    Args:
        pool_share:    ASS [1, hidden]      联合推理 pooler 输出（密态）
        db_embs_share: ASS [N_DOCS, hidden] 离线编码的文档语义库（密态）

    Returns:
        ASS [1, N_DOCS] —— 每篇 doc 的密态 rerank 分数。
        Server 端 restore 后 argsort 取最终 top-K。

    实现细节：
        - 走 ASS @ ASS 的密态 matmul（NssMPClib 的 secure_matmul）
        - DEBUG_LEVEL=2 下 MatrixBeaverProvider 会按需自动生成
          [1, hidden] @ [hidden, N_DOCS] 形状的 fake MatmulTriples
        - 通信开销：一次 matmul = 一次 send/recv restore (e/f 各一份)
        - 计算开销：~1-2s（远小于 BERT 联合推理）
    """
    db_embs_T = db_embs_share.T                       # ASS [hidden, N_DOCS]
    rerank_logits = pool_share @ db_embs_T            # ASS [1, N_DOCS]
    return rerank_logits
