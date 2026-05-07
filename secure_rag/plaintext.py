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
)


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


@torch.no_grad()
def plaintext_rag(
    query_token_ids: torch.Tensor,
    db_embeddings: torch.Tensor,
    bm25_matrix: torch.Tensor,
    db_tokens_onehot: torch.Tensor,
    query_multihot: torch.Tensor,
    bert_model: SecBertModel,
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
    sem_scores = (query_emb * db_embeddings).sum(dim=-1)                          # [NUM_DOCS]

    # ---------- 3. 词汇路打分 ----------
    lex_scores = (query_multihot * bm25_matrix).sum(dim=0)                        # [NUM_DOCS]

    # ---------- 4. 取 top-k（评估用）+ 取 top-1（联合推理用）----------
    n_docs = db_tokens_onehot.shape[0]
    k_for_metrics = min(top_k, n_docs)
    sem_top_k_idx = torch.topk(sem_scores, k=k_for_metrics).indices               # [k]
    lex_top_k_idx = torch.topk(lex_scores, k=k_for_metrics).indices               # [k]

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

    # ---------- 6. 联合推理 ----------
    _, pool = bert_model(joint_ids_oh, oh_joint_pos, oh_joint_typ, joint_mask)     # [1, hidden]

    # ---------- 7. Reranker（与 secure_rag.server.py 对齐）----------
    # pool [1, hidden] @ db_embeddings.T [hidden, n_docs] = [1, n_docs] reranker 分数
    rerank_scores = (pool @ db_embeddings.T).view(-1)                              # [n_docs]
    rerank_top_k = min(top_k, n_docs)
    rerank_top_k_idx = torch.topk(rerank_scores, k=rerank_top_k).indices            # [k]

    return {
        'pool':              pool.detach().cpu(),
        'sem_top_k_idx':     sem_top_k_idx.detach().cpu(),
        'lex_top_k_idx':     lex_top_k_idx.detach().cpu(),
        'sem_scores':        sem_scores.detach().cpu(),
        'lex_scores':        lex_scores.detach().cpu(),
        'query_emb':         query_emb.detach().cpu(),
        'rerank_scores':     rerank_scores.detach().cpu(),
        'rerank_top_k_idx':  rerank_top_k_idx.detach().cpu(),
    }
