"""
experiments/metrics.py

不依赖任何外部库的检索质量指标实现：
    - precision_at_k(retrieved, relevant, k)
    - recall_at_k(retrieved, relevant, k)
    - mrr(retrieved, relevant)
    - ndcg_at_k(retrieved, relevant, k)
    - aggregate(per_query_results) -> 平均到 corpus 级

签名约定：
    retrieved: List[int] 或 1D numpy array，按相关度从高到低排好的文档 id 序列
    relevant:  Set[int] 或 List[int]，ground truth 的相关文档 id 集合
"""
from typing import Iterable, Sequence, Dict, List
import math


def _to_set(xs: Iterable[int]) -> set:
    return set(xs) if not isinstance(xs, set) else xs


def precision_at_k(retrieved: Sequence[int], relevant: Iterable[int], k: int) -> float:
    """Precision@K = (top-k 中有几个相关) / k"""
    if k <= 0:
        return 0.0
    rel = _to_set(relevant)
    topk = list(retrieved)[:k]
    hit = sum(1 for x in topk if x in rel)
    return hit / k


def recall_at_k(retrieved: Sequence[int], relevant: Iterable[int], k: int) -> float:
    """Recall@K = (top-k 中有几个相关) / 全部相关数。"""
    if k <= 0:
        return 0.0
    rel = _to_set(relevant)
    if not rel:
        return 0.0
    topk = list(retrieved)[:k]
    hit = sum(1 for x in topk if x in rel)
    return hit / len(rel)


def mrr(retrieved: Sequence[int], relevant: Iterable[int]) -> float:
    """Mean Reciprocal Rank：第一个命中相关 doc 的位置的倒数。"""
    rel = _to_set(relevant)
    for rank, x in enumerate(retrieved, start=1):
        if x in rel:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[int], relevant: Iterable[int], k: int) -> float:
    """
    Normalized Discounted Cumulative Gain @K：
        DCG@k  = sum_{i=1..k} (2^{rel_i} - 1) / log2(i + 1),  rel_i ∈ {0, 1}
        IDCG@k = 完美排序下的 DCG@k
        NDCG@k = DCG / IDCG
    """
    if k <= 0:
        return 0.0
    rel = _to_set(relevant)
    if not rel:
        return 0.0
    topk = list(retrieved)[:k]

    dcg = 0.0
    for i, x in enumerate(topk, start=1):
        if x in rel:
            dcg += 1.0 / math.log2(i + 1)

    n_rel = min(len(rel), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_rel + 1))
    return dcg / idcg if idcg > 0 else 0.0


def aggregate(per_query_results: List[Dict[str, float]]) -> Dict[str, float]:
    """对一组 per-query 指标求平均。所有 dict 必须有相同的 key。"""
    if not per_query_results:
        return {}
    keys = per_query_results[0].keys()
    avg = {k: sum(d[k] for d in per_query_results) / len(per_query_results) for k in keys}
    return avg
