"""
secure_rag/retrieval.py

密态 RAG 三个核心检索函数（保持原 rag.py 实现不变，仅搬位置 + 重命名去掉 _placeholder 后缀）：
- secure_inner_product_score: 语义路打分（query_emb · doc_embs）
- secure_lexical_score:       词汇路简化 TF-IDF 打分（query_multihot · bm25_matrix）
- secure_top_k_indicator:     密态 Top-K 排序（指示器版冒泡）

SimHash 粗筛 + 密态 cosine 精排（Pisces ICLR 2026 ∏PrivateSS / Protocol 1 的 NssMPClib 实现）：
- get_simhash_projection:           根据固定种子产生公开投影矩阵 W
- plaintext_simhash_bits:           离线对 plaintext embedding 做 SimHash 取符号位
- secure_simhash_query:             对密态 query embedding 做 SimHash → ASS [1, L] 0/1 比特
- secure_simhash_coarse_filter:     密态 Hamming 距离粗筛 → top-M 候选 indicator
- secure_inner_product_on_candidates: 在候选子集上做密态内积精排
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


def secure_bm25_online_score(
    query_indicator_share,
    tf_share,
    idf_share,
    doc_norm_share,
    k1: float = 1.5,
):
    """
    [词汇路·在线密态 BM25] 与 Pisces ICLR 2026 ∏PrivateBM25 Protocol 2 Step 4 同型。

    BM25 公式拆解：score[d] = sum_v indicator[v] * idf[v] * tf[v,d] * (k1+1) / (tf[v,d] + doc_norm[d])
        - tf[v, d]:    每个 (term, doc) 的原始词频
        - idf[v]:      term v 的 inverse document frequency (离线 plaintext 算 log)
        - doc_norm[d]: doc d 的长度归一化项 = k1 * (1 - b + b * |d| / avgdl)
        - k1, b:       公开参数
        - indicator:   query 多热向量

    在线密态计算流程（全程 ASS 域）：
        1. numerator   = idf[v] * tf[v,d] * (k1+1)            ASS [V, N]
        2. denominator = tf[v,d] + doc_norm[d]                ASS [V, N]
        3. contrib     = numerator / denominator              ASS [V, N]   ⭐ 这里走 secure_div
        4. score[d]    = sum_v indicator[v] * contrib[v, d]   ASS [N]

    与 secure_lexical_score 的对比：
        - secure_lexical_score 是离线把 contrib 算成 bm25_matrix [V, N] 直接 share，在线只点积
        - secure_bm25_online_score 是离线 share 原始 tf/idf/doc_norm，在线密态做除法
        协议层后者跟 Pisces 一致；性能层前者快得多 (无在线 secure_div)

    Args:
        query_indicator_share: ASS [V, 1]   query 多热向量 (或 [V])
        tf_share:              ASS [V, N]   每个 (term, doc) 的原始 tf
        idf_share:             ASS [V]      每个 term 的 idf
        doc_norm_share:        ASS [N]      每个 doc 的 length 归一化
        k1:                    float        BM25 参数（默认 1.5，公开）

    Returns:
        ASS [N] BM25 score
    """
    # 1. 分子: idf[v] * tf[v,d] * (k1+1)  → [V, N]
    numerator = idf_share.view(-1, 1) * tf_share * (k1 + 1)               # ASS [V, N]
    # 2. 分母: tf[v,d] + doc_norm[d]  → [V, N] = [V, N] + [1, N]
    denominator = tf_share + doc_norm_share.view(1, -1)                    # ASS [V, N]
    # 3. 密态 batched division: [V, N] / [V, N]
    contrib = numerator / denominator                                       # ASS [V, N]
    # 4. 与 query indicator 加权聚合：[V, 1] * [V, N] → sum over V → [N]
    indicator_2d = query_indicator_share.view(-1, 1)                        # ASS [V, 1]
    score = (indicator_2d * contrib).sum(dim=0)                             # ASS [N]
    return score


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


def secure_prf_expand_query(
    query_multihot_share,
    feedback_doc_tokens_share,
    bm25_vocab,
    alpha: float = 0.7,
    beta: float = 0.3,
):
    """
    [PRF] 密态伪相关反馈：用第一轮 lex top-1 doc 的 token 频率反过来扩展 query。

    动机：
        经典 IR 的 Pseudo-Relevance Feedback 假设第一轮检索的 top-K 文档"相关"
        （pseudo），从中提取词频信号扩展原始 query，再做第二轮检索。本函数把
        Rocchio-style PRF 搬到 ASS 域，实现"密态版" query 扩展。

    流程（全程 ASS 域，不引入任何 send/recv 同步点）：
        1. 文档词频聚合：feedback_doc_tokens_share.sum(dim=seq) → [V_bert]
        2. 投影到 BM25 词表：用明文 indices 索引 → [V_bm25]
        3. 加权融合：q' = alpha * q + beta * doc_term_freq

    隐私性：
        - 所有运算都在 share 上进行，server / client 各自做相同的对称运算
        - bm25_vocab、alpha、beta 是协议级公开常量
        - 不暴露 lex top-1 是哪篇 doc（feedback_doc_tokens_share 是 ASS）

    Args:
        query_multihot_share:      ASS [V_bm25, 1]            原始 query
        feedback_doc_tokens_share: ASS [1, doc_len, V_bert]   第一轮 lex top-1 doc one-hot
        bm25_vocab:                List[int]                  BM25 词表对应的 BERT token id
        alpha:                     float                      原始 query 权重
        beta:                      float                      反馈权重

    Returns:
        q_expanded_share:          ASS [V_bm25, 1]            扩展后的 query
    """
    # 1. 文档词频聚合：[1, doc_len, V_bert] → [1, V_bert]
    doc_term_freq = feedback_doc_tokens_share.sum(dim=1)                       # ASS [1, V_bert]

    # 2. 投影到 BM25 词表（公开 indices）：[1, V_bert] → [1, V_bm25]
    bm25_indices = torch.tensor(bm25_vocab, dtype=torch.long, device=DEVICE)
    doc_bm25_feedback = doc_term_freq[:, bm25_indices]                         # ASS [1, V_bm25]

    # 3. 转置到 [V_bm25, 1] 与 query_multihot 同形（便于 secure_lexical_score 复用）
    doc_bm25_feedback = doc_bm25_feedback.T                                    # ASS [V_bm25, 1]

    # 4. 加权融合：ASS · 明文常量 + ASS · 明文常量
    q_expanded = alpha * query_multihot_share + beta * doc_bm25_feedback
    return q_expanded


# ============================================================================
# SimHash 粗筛 + 密态 cosine 精排（Pisces ICLR 2026 ∏PrivateSS / Protocol 1 同型）
# ============================================================================

def get_simhash_projection(hidden_size: int, num_bits: int, seed: int = 42, device=None) -> torch.Tensor:
    """
    生成 SimHash 投影矩阵 W ∈ R^{num_bits × hidden_size}。
    server 和 client 以同样的 seed 各自生成同一个 W（公开常量，不需要分享）。

    Args:
        device: 默认 DEVICE；测试时可传 'cpu' 等覆盖

    Returns:
        W: torch.Tensor [num_bits, hidden_size]
    """
    g = torch.Generator(device='cpu')
    g.manual_seed(seed)
    W = torch.randn(num_bits, hidden_size, generator=g)
    return W.to(device if device is not None else DEVICE)


def plaintext_simhash_bits(embeddings: torch.Tensor, projection: torch.Tensor) -> torch.Tensor:
    """
    离线明文 SimHash：把 [N, hidden] embedding 映射到 [N, L] 的 {0, 1} 比特矩阵。
    server 在预处理阶段对 db_embeddings 做这个，得到 doc_hashes，再 share 给 client。

    Args:
        embeddings: [N, hidden] 明文 embedding（已离线 L2 归一化更好，影响 cosine 一致性）
        projection: [L, hidden] 公开投影 W（自动 follow embeddings 的 device）

    Returns:
        [N, L] float 张量，元素 ∈ {0.0, 1.0}
    """
    proj = projection.to(embeddings.device)
    return (embeddings @ proj.T > 0).float()


def secure_simhash_query(query_emb_share, projection_ring):
    """
    密态计算 query 的 SimHash 比特：q_hash = sign(query_emb · W^T)。

    W 是公开的 RingTensor（不是 ASS），所以 ASS @ RingTensor 是本地线性运算（无通信）。
    `> 0` 是密态比较门（一次密态比较 / 比特），共 num_bits 次。

    Args:
        query_emb_share: ASS [1, hidden]      query 密态 embedding
        projection_ring: RingTensor [L, hidden]  W 转成 ring 形式（双方各自持有同一个）

    Returns:
        ASS [1, L] 密态 0/1 比特向量
    """
    proj = query_emb_share @ projection_ring.T          # ASS [1, L] —— 本地 matmul
    return proj > 0                                      # ASS [1, L] —— 密态 sign


def secure_simhash_coarse_filter(query_hash_share, doc_hashes_share, candidates_M: int):
    """
    密态 Hamming 距离粗筛，输出 top-M 候选 indicator。

    Hamming(q, d) = sum_l |q_l - d_l|；当 q, d ∈ {0, 1} 时，
        |q_l - d_l| = q_l + d_l - 2·q_l·d_l    （这是 ASS 域内可线性 + 一次 mul 算出来的）

    最近邻 = Hamming 最小 = -Hamming 最大 → 复用 secure_top_k_indicator 取最大。

    Args:
        query_hash_share: ASS [1, L]      query 比特向量（0/1）
        doc_hashes_share: ASS [N, L]      每篇 doc 的比特向量
        candidates_M:     int             候选集大小 (M < N)

    Returns:
        ASS [M, N] 候选集 indicator（每行是某个候选 doc 的 one-hot 在 N 维上的位置）
    """
    # 广播：q [1, L]，d [N, L]
    elem = query_hash_share + doc_hashes_share - 2 * (query_hash_share * doc_hashes_share)  # ASS [N, L]
    hamming = elem.sum(dim=-1)                          # ASS [N]
    similarity = -hamming                                # 越大越相似
    return secure_top_k_indicator(similarity.view(-1), k=candidates_M)


def secure_inner_product_on_candidates(query_emb_share, doc_embs_share, candidate_indicator_share):
    """
    在候选子集上做密态内积（cosine 精排，假设 db_embs 已离线 L2 归一化）。

    流程：先用 indicator 把 N 个 doc embedding 投影成 M 个候选 embedding（一次 ASS@ASS matmul），
    再跟 query 做内积。

    Args:
        query_emb_share:           ASS [1, hidden]
        doc_embs_share:            ASS [N, hidden]
        candidate_indicator_share: ASS [M, N]

    Returns:
        ASS [M] —— M 个候选的 cosine（内积）分数
    """
    cand_embs = candidate_indicator_share @ doc_embs_share        # ASS [M, hidden]
    return (query_emb_share * cand_embs).sum(dim=-1)              # ASS [M]


def secure_simhash_coarse_to_fine(
    query_emb_share,
    doc_embs_share,
    doc_hashes_share,
    projection_ring,
    candidates_M: int,
    top_k: int,
):
    """
    [Pisces-aligned 语义路] SimHash 粗筛 → 密态 cosine 精排 → top-K indicator（在全 N 维上）。

    这是 secure_inner_product_score + secure_top_k_indicator 的"coarse-to-fine 增强版"，
    输出形状跟原来的 secure_top_k_indicator(scores, k=TOP_K) 完全一致 [top_k, N]，所以下游
    （indicator 取 doc tokens、PRF 反馈源等）无需改。

    Args:
        query_emb_share:  ASS [1, hidden]
        doc_embs_share:   ASS [N, hidden]
        doc_hashes_share: ASS [N, L]
        projection_ring:  RingTensor [L, hidden]
        candidates_M:     int
        top_k:            int   最终保留的 top-K 数量

    Returns:
        ASS [top_k, N] 最终候选 indicator (在全 N 维 doc 上的 one-hot)
    """
    q_hash = secure_simhash_query(query_emb_share, projection_ring)                   # ASS [1, L]
    cand_ind = secure_simhash_coarse_filter(q_hash, doc_hashes_share, candidates_M)   # ASS [M, N]
    cand_scores = secure_inner_product_on_candidates(
        query_emb_share, doc_embs_share, cand_ind
    )                                                                                  # ASS [M]
    top_k_ind_on_M = secure_top_k_indicator(cand_scores.view(-1), k=top_k)            # ASS [top_k, M]
    # 把 [top_k, M] 的候选维 indicator 投回全 N 维：[top_k, M] @ [M, N] → [top_k, N]
    top_k_ind_on_N = top_k_ind_on_M @ cand_ind                                         # ASS [top_k, N]
    return top_k_ind_on_N


# ============================================================================
# Span Reader（SQuAD-style start/end head + 密态 span 抽取，对应 Pisces 委托
# 给外部密态 LLM 之外的本地 default backend）
# ============================================================================

def _upper_tri_ones_ring(L: int) -> 'RingTensor':
    """
    构造 [L, L] 上三角 ones 矩阵（含对角线），转为公开 RingTensor 用于 cumsum。

    cumsum(x)[i] = sum_{j<=i} x[j] = (x @ M)[i] where M[j, i] = 1 if j<=i (上三角)。
    M 是公开常量（双方各自构造同一份），ASS @ M 是本地 matmul，无密态成本。
    """
    M = torch.triu(torch.ones(L, L, device=DEVICE))
    return RingTensor.convert_to_ring(M)


def secure_reader_span(
    seq_out_share,
    joint_ids_share,
    qa_W_ring,
    qa_b_ring,
    query_len: int = 8,
    special_token_ids=(0, 101, 102),
    mask_value: float = 1000.0,
):
    """
    [Span Reader] 用 SQuAD-finetuned QA head 做密态 start/end span 抽取。

    跟启发式 secure_reader 的关键区别：
      - 旧: reader_logits[i] = pool · seq_out[i]   →  单 token argmax，准确率极低
      - 新: start/end logits = seq_out @ qa_W.T + qa_b（用真训练过的 head）
            然后密态 argmax(start), argmax(end)，cumsum trick 算 span_mask
            最终输出 span 内所有 token 的 one-hot 之和（"答案 token 袋"）

    QA head 是公开常量（来自 mrm8488/bert-tiny-finetuned-squadv2 的 qa_outputs）：
      - qa_W: [2, hidden]   行 0 = start, 行 1 = end
      - qa_b: [2]
    所以 ASS @ qa_W.T 是本地 matmul（cheap），加 bias 是 party-0 only add（cheap）。

    Args:
        seq_out_share:     ASS [1, L, hidden]    联合推理 sequence output
        joint_ids_share:   ASS [1, L, vocab]     联合输入的 token one-hot
        qa_W_ring:         RingTensor [2, hidden]  QA head weight (公开常量)
        qa_b_ring:         RingTensor [2]          QA head bias   (公开常量)
        query_len:         前 query_len 位是 query（公开），不能选作答案
        special_token_ids: 特殊 token 不能选作答案 ([PAD]=0, [CLS]=101, [SEP]=102)
        mask_value:        被 mask 的位置 logits 减去这个常量

    Returns:
        answer_token_oh_share: ASS [1, vocab]   span 内所有 token 的 one-hot 之和
                                                client restore 后取 nonzero 位置 = answer token ids
        start_logits_share:    ASS [1, L]       诊断用
        end_logits_share:      ASS [1, L]       诊断用
        span_mask_share:       ASS [1, L]       诊断用（restore 后是 0/1 序列）
    """
    L = seq_out_share.shape[-2]

    # 1. logits = seq_out @ qa_W.T + qa_b
    #    qa_W.T: [hidden, 2]   →   matmul gives [1, L, 2]
    #    qa_W 是公开 RingTensor → ASS @ Ring 是本地 matmul（无通信）
    logits = seq_out_share @ qa_W_ring.T                                # ASS [1, L, 2]
    logits = logits + qa_b_ring                                          # ASS [1, L, 2] (party 0 only add)
    start_logits = logits[..., 0]                                        # ASS [1, L]
    end_logits = logits[..., 1]                                          # ASS [1, L]

    # 2. mask: query 段 + special tokens
    plain_mask = torch.zeros(1, L, device=DEVICE)
    if query_len > 0:
        plain_mask[:, :query_len] = -mask_value
    plain_mask_ring = RingTensor.convert_to_ring(plain_mask)
    start_logits = start_logits + plain_mask_ring
    end_logits = end_logits + plain_mask_ring

    if special_token_ids:
        special_indicator = None
        for tok_id in special_token_ids:
            ind = joint_ids_share[..., tok_id]                           # ASS [1, L]
            special_indicator = ind if special_indicator is None else (special_indicator + ind)
        special_mask_term = special_indicator * (-mask_value)
        start_logits = start_logits + special_mask_term
        end_logits = end_logits + special_mask_term

    # 3. 密态 argmax 拿 start / end indicator
    start_ind = secure_top_k_indicator(start_logits.view(-1), k=1)       # ASS [1, L]
    end_ind = secure_top_k_indicator(end_logits.view(-1), k=1)           # ASS [1, L]

    # 4. span_mask 通过 cumsum trick 计算：
    #    cum_start[i] = 1 once we pass start;  cum_end_shifted[i] = 1 once we passed end (next)
    #    span_mask[i] = cum_start[i] - cum_end_shifted[i]
    #      - 在 [start, end] 内：span_mask[i] = 1 - 0 = 1
    #      - 在 [start, end] 外：span_mask[i] = 0 (start 之前) 或 1 - 1 = 0 (end 之后)
    # 注意：用 ASS @ public_RingTensor matmul 实现 cumsum 会因 fixed-point 截断引入误差
    # （/ scale 操作让 0/1 indicator 累加后变成 0.99/1.01 等噪声值），改用 for-loop 本地累加避免。
    cum_start_list = []
    cum_end_list = []
    cur_s = ArithmeticSecretSharing(RingTensor.zeros_like(start_ind[..., 0:1].item))
    cur_e = ArithmeticSecretSharing(RingTensor.zeros_like(end_ind[..., 0:1].item))
    for i in range(L):
        cur_s = cur_s + start_ind[..., i:i + 1]
        cur_e = cur_e + end_ind[..., i:i + 1]
        cum_start_list.append(cur_s)
        cum_end_list.append(cur_e)
    cum_start = ArithmeticSecretSharing.cat(cum_start_list, dim=-1)         # ASS [1, L]
    cum_end = ArithmeticSecretSharing.cat(cum_end_list, dim=-1)             # ASS [1, L]
    # 右移一位：cum_end_shifted[0] = 0; cum_end_shifted[i] = cum_end[i-1] for i >= 1
    zero_first = ArithmeticSecretSharing(RingTensor.zeros_like(cum_end[..., 0:1].item))
    cum_end_shifted = ArithmeticSecretSharing.cat([zero_first, cum_end[..., :-1]], dim=-1)  # ASS [1, L]
    span_mask = cum_start - cum_end_shifted                                 # ASS [1, L]，期望精确 0/1

    # 5. span bag: 把 span 内所有位置的 token one-hot 累加
    #    expanded: [1, L, 1]  *  joint_ids: [1, L, V]  →  [1, L, V]  →  sum(dim=1)  →  [1, V]
    expanded = span_mask.unsqueeze(-1)                                    # ASS [1, L, 1]
    answer_token_oh = (expanded * joint_ids_share).sum(dim=1)             # ASS [1, V]

    # 6. ⭐ 每个 span 位置的 token one-hot：[1, L, V] = span_mask * joint_ids
    #    保留全 [L, V] 形状，不 sum，client 端按位置顺序 argmax 解出 token id
    #    通信开销 = L * V (≈ 56 × 30522 ≈ 1.7M ints)，跟已有 joint_ids 同级
    span_token_oh_share = expanded * joint_ids_share                      # ASS [1, L, V]

    return answer_token_oh, start_logits, end_logits, span_mask, span_token_oh_share


def load_qa_head(qa_head_path: str):
    """
    从 scripts/extract_squad_qa_head.py 保存的 .pth 加载 qa_outputs 权重，
    并转成 RingTensor（公开常量，server / client 各自加载即可，无需 share）。

    Returns:
        (qa_W_ring [2, hidden], qa_b_ring [2])
    """
    import os as _os
    if not _os.path.exists(qa_head_path):
        raise FileNotFoundError(
            f"QA head not found: {qa_head_path}\n"
            f"先跑: python scripts/extract_squad_qa_head.py"
        )
    state = torch.load(qa_head_path, map_location=DEVICE)
    qa_W = state['qa_W'].to(DEVICE).to(torch.float32)        # [2, hidden]
    qa_b = state['qa_b'].to(DEVICE).to(torch.float32)        # [2]
    return RingTensor.convert_to_ring(qa_W), RingTensor.convert_to_ring(qa_b)
