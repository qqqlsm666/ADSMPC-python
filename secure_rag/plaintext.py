"""
secure_rag/plaintext.py

明文 RAG —— 与 secure_rag.server / secure_rag.client 严格对应的"非加密"版本。

为什么单独写一份：
- SecBertModel 已经支持明文模式（输入是 torch.Tensor 时走纯 PyTorch 路径），
  但 RAG 的"双路打分 + Top-K + 取真实文档 + 联合推理"流程没有现成入口。
- 实验需要"同一查询、同一权重、同一文档库"在两侧跑出来对比 max_diff / cosine_sim
  以及 Recall@K / MRR / NDCG@K。

输入约定（与 secure_rag/server.py、client.py 完全对齐）：
    query_token_ids:  [1, SEQ] long
    db_embeddings:    [NUM_DOCS, hidden] float
    bm25_matrix:      [VOCAB_SIZE_BM25, NUM_DOCS] float
    db_tokens_onehot: [NUM_DOCS, SEM_DOC_LEN, vocab_size] float
    query_multihot:   [VOCAB_SIZE_BM25, 1] float

返回：
    dict 包含
        - 'pool':                 [1, hidden] 联合推理 pooler 输出
        - 'sem_top_k_idx':        [TOP_K] 语义路 top-k 文档索引
        - 'lex_top_k_idx':        [TOP_K] 词汇路 top-k 文档索引
        - 'sem_scores':           [NUM_DOCS] 语义路分数
        - 'lex_scores':           [NUM_DOCS] 词汇路分数
        - 'query_emb':            [1, hidden] query 编码（query 单独跑一遍 BERT 的 pooler）
"""
from typing import Optional, Dict, List
import torch
import torch.nn.functional as F

from NssMPC.application.neural_network.layers.mha import SecBertModel

from .config import (
    BERT_CONFIG, SEQ, NUM_DOCS, TOP_K, QUERY_LEN, SEM_DOC_LEN, LEX_DOC_LEN,
    TOTAL_SEQ, VOCAB_SIZE_BM25,
    PRF_ENABLED, PRF_ALPHA, PRF_BETA, PRF_FEEDBACK_SOURCE,
    SIMHASH_ENABLED, SIMHASH_BITS, SIMHASH_CANDIDATES_M, SIMHASH_SEED,
    SPAN_READER_ENABLED, default_qa_head_path,
    LEX_BM25_ONLINE, LEX_BM25_K1, LEX_BM25_B,
)
from .retrieval import get_simhash_projection, plaintext_simhash_bits
from .retrieval import get_simhash_projection, plaintext_simhash_bits


def _load_weights_into(model: SecBertModel, weight_path: str, log_prefix: str = "[Plain]") -> int:
    """与 server.load_bert_weights 完全等价，但拆出来避免循环依赖。"""
    import os as _os
    if not _os.path.exists(weight_path):
        print(f"{log_prefix} 警告: 未找到权重文件 {weight_path}, 使用零初始化")
        return 0
    state_dict = torch.load(weight_path, map_location='cpu')
    state_dict.pop('embeddings.position_ids', None)
    new_state_dict = {(k[5:] if k.startswith('bert.') else k): v for k, v in state_dict.items()}
    loaded = 0
    for name, p in model.named_parameters():
        if name in new_state_dict:
            p.data = new_state_dict[name].to(torch.float32)
            loaded += 1
    print(f"{log_prefix} 权重加载完成: loaded={loaded}")
    return loaded


def build_plaintext_bert(weight_path: Optional[str] = None, bert_config: Optional[Dict] = None,
                         device: str = 'cpu') -> SecBertModel:
    """构造一份加载好权重的明文 SecBertModel。"""
    cfg = bert_config or BERT_CONFIG
    model = SecBertModel(cfg).to(device)
    for p in model.parameters():
        p.requires_grad = False
    if weight_path is not None:
        _load_weights_into(model, weight_path)
    model.eval()
    return model


@torch.no_grad()
def encode_docs_to_embeddings(
    docs_token_ids: torch.Tensor,
    bert_model: SecBertModel,
    bert_config: Optional[Dict] = None,
    device: str = 'cpu',
) -> torch.Tensor:
    """
    用明文 BERT 把每篇文档编码成 [hidden] 向量（取 [CLS] pooler 输出）。

    Args:
        docs_token_ids: [N_DOCS, doc_len] long
        bert_model:     已加载权重的 SecBertModel
    Returns:
        [N_DOCS, hidden] float
    """
    cfg = bert_config or BERT_CONFIG
    docs_token_ids = docs_token_ids.to(device).long()
    n_docs, doc_len = docs_token_ids.shape

    embs = []
    for i in range(n_docs):
        ids_i = docs_token_ids[i:i + 1]                                         # [1, L]
        pos_i = torch.arange(doc_len).unsqueeze(0).to(device)                   # [1, L]
        typ_i = torch.zeros_like(ids_i).to(device)
        mask_i = torch.ones_like(ids_i, dtype=torch.float32).to(device)
        oh_ids = F.one_hot(ids_i, cfg['vocab_size']).float()
        oh_pos = F.one_hot(pos_i, cfg['max_position_embeddings']).float()
        oh_typ = F.one_hot(typ_i, cfg['type_vocab_size']).float()
        _, pool = bert_model(oh_ids, oh_pos, oh_typ, mask_i)
        embs.append(pool[0])
    return torch.stack(embs, dim=0)                                              # [N_DOCS, hidden]


def build_bm25_matrix(
    docs_token_ids: torch.Tensor,
    bm25_vocab: List[int],
) -> torch.Tensor:
    """
    用真实 BM25 公式（Robertson-Spärck Jones 形式）构造 [V, N_DOCS] 矩阵。

    Args:
        docs_token_ids: [N_DOCS, doc_len] long，文档 token id
        bm25_vocab:     长度为 V 的 token id 列表（必须与 query_multihot 维度一致）

    Returns:
        bm25_matrix [V, N_DOCS] float
    """
    import math
    n_docs, doc_len = docs_token_ids.shape
    V = len(bm25_vocab)

    # 文档长度（去掉 padding token=0）
    doc_lens = (docs_token_ids != 0).sum(dim=1).float().clamp(min=1)             # [N_DOCS]
    avgdl = doc_lens.mean().item()

    k1, b = 1.5, 0.75
    bm25 = torch.zeros(V, n_docs)

    for v_idx, term_id in enumerate(bm25_vocab):
        # df: 含该 term 的文档数
        df = ((docs_token_ids == term_id).any(dim=1)).sum().item()
        if df == 0:
            continue
        idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
        for d_idx in range(n_docs):
            tf = (docs_token_ids[d_idx] == term_id).sum().item()
            if tf == 0:
                continue
            denom = tf + k1 * (1 - b + b * doc_lens[d_idx].item() / avgdl)
            bm25[v_idx, d_idx] = idf * tf * (k1 + 1) / denom
    return bm25                                                                   # [V, N_DOCS]


def build_bm25_components(
    docs_token_ids: torch.Tensor,
    bm25_vocab: List[int],
    k1: float = 1.5,
    b: float = 0.75,
):
    """
    把 BM25 拆解成三个分量：tf_matrix [V, N], idf [V], doc_norm [N]。

    BM25 公式: score = sum_v indicator[v] * idf[v] * tf[v,d] * (k1+1) / (tf[v,d] + doc_norm[d])
        其中 doc_norm[d] = k1 * (1 - b + b * doc_len[d] / avgdl)

    用于 LEX_BM25_ONLINE=True 模式：协议层 server 暴露原始 tf/idf/doc_norm 而非预算 BM25 矩阵，
    BM25 公式在线密态计算（含密态 div），与 Pisces ∏PrivateBM25 Protocol 2 Step 4 对齐。

    Args:
        docs_token_ids: [N, doc_len] long
        bm25_vocab:     [V] list of token ids
        k1, b:          BM25 公开参数

    Returns:
        (tf [V, N] float, idf [V] float, doc_norm [N] float)
    """
    import math
    n_docs, _ = docs_token_ids.shape
    V = len(bm25_vocab)

    doc_lens = (docs_token_ids != 0).sum(dim=1).float().clamp(min=1)         # [N]
    avgdl = doc_lens.mean().item()
    doc_norm = k1 * (1 - b + b * doc_lens / avgdl)                            # [N]

    tf = torch.zeros(V, n_docs)
    idf = torch.zeros(V)
    for v_idx, term_id in enumerate(bm25_vocab):
        df = ((docs_token_ids == term_id).any(dim=1)).sum().item()
        if df == 0:
            continue
        idf[v_idx] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
        for d_idx in range(n_docs):
            cnt = (docs_token_ids[d_idx] == term_id).sum().item()
            if cnt > 0:
                tf[v_idx, d_idx] = float(cnt)
    return tf, idf, doc_norm


@torch.no_grad()
def plaintext_rag(
    query_token_ids: torch.Tensor,
    db_embeddings: torch.Tensor,
    bm25_matrix: torch.Tensor,
    db_tokens_onehot: torch.Tensor,
    query_multihot: torch.Tensor,
    bert_model: SecBertModel,
    bm25_vocab: Optional[List[int]] = None,
    bert_config: Optional[Dict] = None,
    device: str = 'cpu',
    top_k: int = TOP_K,                    # 兼容旧参数；目前不影响联合推理
) -> Dict[str, torch.Tensor]:
    """
    明文版 RAG，与 secure_rag/server.py + client.py 的密态流程严格对应。

    流程：
    1) query 编码 (Seq=8 BERT) → query_emb [1, hidden]
    2) 语义路打分 sem_scores = query_emb · db_embeddings           [NUM_DOCS]
    3) 词汇路打分 lex_scores = query_multihot · bm25_matrix        [NUM_DOCS]
    4) 各取 top-1 文档的 token 序列                                 [1, doc_len, V]
       （联合推理的输入序列长度固定 = QUERY_LEN + SEM_DOC_LEN + LEX_DOC_LEN，
        只能塞下各 1 个 doc；如果实验需要 top-k，看 retrieved_top_k_idx 字段）
    5) cat(query, sem_doc_top1, lex_doc_top1) → joint_ids [1, 56, V]
    6) 联合推理 → pool [1, hidden]

    返回 dict:
        - pool:                [1, hidden] 联合推理 pooler 输出
        - sem_top_k_idx:       [top_k] 语义路 top-k 文档索引（用于 IR 评估）
        - lex_top_k_idx:       [top_k] 词汇路 top-k 文档索引
        - sem_scores:          [NUM_DOCS]
        - lex_scores:          [NUM_DOCS]
        - query_emb:           [1, hidden]
    """
    cfg = bert_config or BERT_CONFIG
    bert_model = bert_model.to(device)

    query_token_ids = query_token_ids.to(device).long()
    db_embeddings = db_embeddings.to(device)
    bm25_matrix = bm25_matrix.to(device)
    db_tokens_onehot = db_tokens_onehot.to(device)
    query_multihot = query_multihot.to(device)

    # ---------- 1. query 编码 ----------
    pos = torch.arange(SEQ).unsqueeze(0).to(device)
    typ = torch.zeros_like(query_token_ids).to(device)
    mask = torch.ones_like(query_token_ids, dtype=torch.float32).to(device)
    oh_ids = F.one_hot(query_token_ids, cfg['vocab_size']).float()
    oh_pos = F.one_hot(pos, cfg['max_position_embeddings']).float()
    oh_typ = F.one_hot(typ, cfg['type_vocab_size']).float()
    _, query_emb = bert_model(oh_ids, oh_pos, oh_typ, mask)                       # [1, hidden]

    # ---------- 2. 语义路打分 ----------
    if SIMHASH_ENABLED:
        # Pisces-aligned coarse-to-fine：明文 SimHash 粗筛 → 候选集 cosine 精排
        simhash_W = get_simhash_projection(cfg['hidden_size'], SIMHASH_BITS, seed=SIMHASH_SEED, device=device)
        q_hash = plaintext_simhash_bits(query_emb, simhash_W).view(-1)                  # [L]
        doc_hashes = plaintext_simhash_bits(db_embeddings, simhash_W)                   # [N, L]
        # Hamming 距离 |q-d| with q,d∈{0,1} → q+d-2qd
        hamming = (q_hash.unsqueeze(0) + doc_hashes - 2 * q_hash.unsqueeze(0) * doc_hashes).sum(dim=-1)  # [N]
        M = min(SIMHASH_CANDIDATES_M, db_embeddings.shape[0])
        cand_idx = torch.topk(-hamming, k=M).indices                                     # [M] doc id of M 候选
        # 在候选集上做 cosine 精排
        cand_embs = db_embeddings[cand_idx]                                              # [M, hidden]
        cand_scores = (query_emb * cand_embs).sum(dim=-1)                                # [M]
        # 把全 N 维 sem_scores 填回（候选外位置 = -inf 等价）
        sem_scores = torch.full((db_embeddings.shape[0],), float('-inf'), device=device)
        sem_scores[cand_idx] = cand_scores
    else:
        sem_scores = (query_emb * db_embeddings).sum(dim=-1)                              # [NUM_DOCS]

    # ---------- 3. 词汇路打分（第一轮）----------
    lex_scores_round1 = (query_multihot * bm25_matrix).sum(dim=0)                 # [NUM_DOCS]

    # ---------- 4. 取 top-k（评估用）+ 取 top-1（联合推理用）----------
    n_docs = db_tokens_onehot.shape[0]
    k_for_metrics = min(top_k, n_docs)
    sem_top_k_idx = torch.topk(sem_scores, k=k_for_metrics).indices               # [k]

    # 词汇路第一轮 Top-K（用于反馈源 + IR 评估对比基线）
    lex_top_k_idx_round1 = torch.topk(lex_scores_round1, k=k_for_metrics).indices

    # ---------- 3.5. PRF 扩展 query（与 secure_rag.retrieval.secure_prf_expand_query 对齐）----------
    if PRF_ENABLED and bm25_vocab is not None:
        # 反馈源：PRF_FEEDBACK_SOURCE 控制
        if PRF_FEEDBACK_SOURCE == 'sem':
            feedback_doc_oh = db_tokens_onehot[sem_top_k_idx[0]]                  # [doc_len, V_bert]
            doc_term_freq = feedback_doc_oh.sum(dim=0)                            # [V_bert]
        elif PRF_FEEDBACK_SOURCE == 'both':
            doc_term_freq = (
                db_tokens_onehot[sem_top_k_idx[0]].sum(dim=0) +
                db_tokens_onehot[lex_top_k_idx_round1[0]].sum(dim=0)
            )
        else:  # 'lex'
            feedback_doc_oh = db_tokens_onehot[lex_top_k_idx_round1[0]]
            doc_term_freq = feedback_doc_oh.sum(dim=0)
        bm25_indices = torch.tensor(bm25_vocab, dtype=torch.long, device=device)
        doc_bm25_feedback = doc_term_freq[bm25_indices].unsqueeze(-1)             # [V_bm25, 1]
        q_expanded = PRF_ALPHA * query_multihot + PRF_BETA * doc_bm25_feedback
        # 第二轮 lex 检索
        lex_scores = (q_expanded * bm25_matrix).sum(dim=0)                        # [NUM_DOCS]
        lex_top_k_idx = torch.topk(lex_scores, k=k_for_metrics).indices
    else:
        lex_scores = lex_scores_round1
        lex_top_k_idx = lex_top_k_idx_round1

    # 联合推理只用 top-1（输入序列长度固定 56，只塞得下 1 个 sem + 1 个 lex）
    sem_top1_idx = sem_top_k_idx[:1]                                              # [1]
    lex_top1_idx = lex_top_k_idx[:1]                                              # [1]

    sem_indicator_top1 = F.one_hot(sem_top1_idx, num_classes=n_docs).float()      # [1, N]
    lex_indicator_top1 = F.one_hot(lex_top1_idx, num_classes=n_docs).float()
    sem_doc_oh = (sem_indicator_top1.unsqueeze(-1).unsqueeze(-1) *
                  db_tokens_onehot.unsqueeze(0)).sum(dim=1)                       # [1, doc_len, V]
    lex_doc_oh = (lex_indicator_top1.unsqueeze(-1).unsqueeze(-1) *
                  db_tokens_onehot.unsqueeze(0)).sum(dim=1)

    # ---------- 5. 拼接 ----------
    joint_ids_oh = torch.cat([oh_ids, sem_doc_oh, lex_doc_oh], dim=1)              # [1, 56, V]

    joint_pos = torch.arange(TOTAL_SEQ).unsqueeze(0).to(device)
    joint_typ = torch.cat([
        torch.zeros(1, QUERY_LEN),
        torch.ones(1, SEM_DOC_LEN),
        torch.ones(1, LEX_DOC_LEN),
    ], dim=1).long().to(device)
    joint_mask = torch.ones(1, TOTAL_SEQ, dtype=torch.float32).to(device)

    oh_joint_pos = F.one_hot(joint_pos, cfg['max_position_embeddings']).float()
    oh_joint_typ = F.one_hot(joint_typ, cfg['type_vocab_size']).float()

    # ---------- 6. 联合推理（拿 sequence output 给 reader 用）----------
    seq_out, pool = bert_model(joint_ids_oh, oh_joint_pos, oh_joint_typ, joint_mask)  # seq: [1, L, h], pool: [1, h]

    # ---------- 7. Reranker（与 secure_rag.server.py 对齐）----------
    # pool [1, hidden] @ db_embeddings.T [hidden, n_docs] = [1, n_docs] reranker 分数
    rerank_scores = (pool @ db_embeddings.T).view(-1)                              # [n_docs]
    rerank_top_k = min(top_k, n_docs)
    rerank_top_k_idx = torch.topk(rerank_scores, k=rerank_top_k).indices            # [k]

    # ---------- 8. Reader（与 secure_rag.retrieval.secure_reader / secure_reader_span 对齐）----------
    mask_value = 1000.0
    joint_token_ids = joint_ids_oh[0].argmax(dim=-1)                               # [L]
    answer_text = None

    if SPAN_READER_ENABLED:
        # SQuAD-style span reader：用 mrm8488/bert-tiny-finetuned-squadv2 的 qa_outputs
        import os as _os
        _qa_path = default_qa_head_path()
        if not _os.path.exists(_qa_path):
            raise FileNotFoundError(
                f"QA head not found: {_qa_path}\n"
                f"先跑: python scripts/extract_squad_qa_head.py"
            )
        _qa_state = torch.load(_qa_path, map_location=device)
        qa_W = _qa_state['qa_W'].to(device).to(torch.float32)            # [2, hidden]
        qa_b = _qa_state['qa_b'].to(device).to(torch.float32)            # [2]
        # logits = seq_out @ qa_W.T + qa_b → [1, L, 2]
        qa_logits = seq_out @ qa_W.T + qa_b                              # [1, L, 2]
        start_logits = qa_logits[..., 0].view(-1)                        # [L]
        end_logits = qa_logits[..., 1].view(-1)                          # [L]
        # mask
        if QUERY_LEN > 0:
            start_logits[:QUERY_LEN] = start_logits[:QUERY_LEN] - mask_value
            end_logits[:QUERY_LEN] = end_logits[:QUERY_LEN] - mask_value
        for special_id in (0, 101, 102):
            sp_mask = (joint_token_ids == special_id).float() * mask_value
            start_logits = start_logits - sp_mask
            end_logits = end_logits - sp_mask
        start_pos = int(start_logits.argmax().item())
        end_pos = int(end_logits.argmax().item())
        # 强制 end >= start，超长截断
        if end_pos < start_pos:
            end_pos = start_pos
        if end_pos - start_pos > 8:                                       # 限制 span 长度 ≤ 8
            end_pos = start_pos + 8
        # gather span tokens
        span_token_ids = joint_token_ids[start_pos:end_pos + 1].tolist()
        answer_position = start_pos                                       # diagnostic：start position
        answer_token_id = span_token_ids[0] if span_token_ids else 0
        # answer_text 在 run_numerical_compare/eval 里用 tokenizer 拼起来
        reader_logits = start_logits                                      # diagnostic
        # 把整个 span 也保存出来（list of token ids）
        reader_extras = {
            'start_pos':       start_pos,
            'end_pos':         end_pos,
            'span_token_ids':  span_token_ids,
        }
    else:
        # 旧的启发式 head: reader_logits[i] = pool · seq_out[i]
        reader_logits = (seq_out * pool.unsqueeze(1)).sum(dim=-1).view(-1)             # [L]
        if QUERY_LEN > 0:
            reader_logits[:QUERY_LEN] = reader_logits[:QUERY_LEN] - mask_value
        for special_id in (0, 101, 102):
            reader_logits = reader_logits - (joint_token_ids == special_id).float() * mask_value
        answer_position = int(reader_logits.argmax().item())
        answer_token_oh = joint_ids_oh[0, answer_position]                              # [V]
        answer_token_id = int(answer_token_oh.argmax().item())
        reader_extras = {
            'start_pos':       answer_position,
            'end_pos':         answer_position,
            'span_token_ids':  [answer_token_id],
        }

    return {
        'pool':              pool.detach().cpu(),
        'sem_top_k_idx':     sem_top_k_idx.detach().cpu(),
        'lex_top_k_idx':     lex_top_k_idx.detach().cpu(),
        'sem_scores':        sem_scores.detach().cpu(),
        'lex_scores':        lex_scores.detach().cpu(),
        'query_emb':         query_emb.detach().cpu(),
        'rerank_scores':     rerank_scores.detach().cpu(),
        'rerank_top_k_idx':  rerank_top_k_idx.detach().cpu(),
        'reader_logits':     reader_logits.detach().cpu(),
        'answer_position':   answer_position,
        'answer_token_id':   answer_token_id,
        'answer_text':       answer_text,
        'span_token_ids':    reader_extras['span_token_ids'],
        'start_pos':         reader_extras['start_pos'],
        'end_pos':           reader_extras['end_pos'],
    }
