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


def secure_reader(pool_share, seq_out_share, joint_ids_share,
                  query_len: int = 8,
                  special_token_ids=(0, 101, 102),
                  mask_value: float = 1000.0):
    """
    [Reader] 密态抽取式阅读器（启发式版 + special token mask）。

    用启发式 head 实现"在联合输入序列里挑出答案 token"：
      - reader_logits[i] = pool · seq_out[i]   (pool 跟每个位置的相关度)
      - **mask 特殊位置 / 特殊 token，避免选到 [CLS]/[SEP]/[PAD] 或 query 段**
      - 密态 argmax (复用 secure_top_k_indicator with K=1)
      - 用密态 indicator 从 joint_ids 里 gather 出答案 token 的 one-hot

    整个过程任意一方都不知道答案在第几位、答案是哪个 token。
    最终输出 ASS [1, V] 的密态 token one-hot；只在 client 端 restore，
    再用 tokenizer.decode 拿到自然语言答案。

    Args:
        pool_share:        ASS [1, hidden]            联合推理 pooler
        seq_out_share:     ASS [1, seq_len, hidden]   联合推理 sequence output
        joint_ids_share:   ASS [1, seq_len, vocab]    联合输入的 token one-hot
        query_len:         前 query_len 个位置是 query（公开），不能是答案
        special_token_ids: 这些 token 不能是答案（[PAD]=0, [CLS]=101, [SEP]=102）
        mask_value:        被 mask 的位置 logits 减去这个常量，让其不可能赢得 argmax

    Returns:
        answer_token_oh_share: ASS [1, vocab] —— 密态 one-hot 答案 token
        reader_logits_share:   ASS [1, seq_len] —— 密态 reader 分数（已含 mask 偏置；供调试）
        position_indicator_share: ASS [1, seq_len] —— 密态答案位置指示器（供调试）
    """
    # 1) 计算密态 reader logits = sum_d (seq_out[i, d] * pool[d])  ↔  内积
    #    seq_out_share: [1, L, h]; pool_share.unsqueeze(1): [1, 1, h]
    #    广播按位乘后 [1, L, h] → sum(-1) → [1, L]
    reader_logits = (seq_out_share * pool_share.unsqueeze(1)).sum(dim=-1)   # ASS [1, L]

    # 1.5) Mask：让 query 段、[CLS]/[SEP]/[PAD] 位置都不可能赢
    L = reader_logits.shape[-1]

    # (a) 明文 mask：query 段位置 0..query_len-1（公开，所有方一致）
    plain_mask = torch.zeros(1, L, device=DEVICE)
    if query_len > 0:
        plain_mask[:, :query_len] = -mask_value
    plain_mask_ring = RingTensor.convert_to_ring(plain_mask)
    reader_logits = reader_logits + plain_mask_ring                          # ASS + RingTensor

    # (b) 密态 mask：joint_ids_share[..., tok_id] 是 [1, L] 的 ASS one-hot，
    #     聚合 special token 形成 indicator，乘 -mask_value 加到 logits 上
    if special_token_ids:
        special_indicator = None
        for tok_id in special_token_ids:
            ind = joint_ids_share[..., tok_id]                               # ASS [1, L]
            special_indicator = ind if special_indicator is None else (special_indicator + ind)
        reader_logits = reader_logits + special_indicator * (-mask_value)    # ASS * 明文常量

    # 2) 密态 argmax：把 reader_logits view 成 [L]，复用 secure_top_k_indicator
    position_indicator = secure_top_k_indicator(reader_logits.view(-1), k=1)  # ASS [1, L]

    # 3) 密态 gather：用 indicator 从 joint_ids 的 seq 维度上"挑"出答案 token
    #    position_indicator: [1, L] → [1, L, 1]
    #    joint_ids_share:    [1, L, V]
    #    乘 + sum(dim=1) → [1, V]   即被选中那一行的 token one-hot
    expanded_ind = position_indicator.unsqueeze(-1)                          # ASS [1, L, 1]
    answer_token_oh = (expanded_ind * joint_ids_share).sum(dim=1)            # ASS [1, V]

    return answer_token_oh, reader_logits, position_indicator
