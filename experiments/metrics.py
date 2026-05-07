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


def normalize_answer(text: str) -> str:
    """SQuAD 风格的 answer 归一化：lowercase + 去标点 + 去多余空白。"""
    import re
    if text is None:
        return ''
    text = str(text).lower()
    # 去标点
    text = re.sub(r'[\W_]+', ' ', text, flags=re.UNICODE)
    # 收缩多余空格
    text = ' '.join(text.split())
    return text.strip()


def exact_match(predicted: str, gt_answers) -> float:
    """Exact Match (EM)：预测答案与任一 ground truth 完全匹配（归一化后）→ 1.0；否则 0.0。

    Args:
        predicted: 预测答案文本
        gt_answers: 单个 str 或 List[str]，多个候选答案时只要命中任意一个就算对

    Returns:
        1.0 / 0.0
    """
    if isinstance(gt_answers, str):
        gt_answers = [gt_answers]
    pred = normalize_answer(predicted)
    if not pred:
        return 0.0
    for gt in gt_answers:
        if pred == normalize_answer(gt):
            return 1.0
    return 0.0


def partial_match(predicted: str, gt_answers) -> float:
    """单 token reader 友好版的 EM：

    严格 EM 对 wordpiece 输出几乎都失败（如 "mit" vs "mitochondria"），所以放宽：
    只要 pred 与某个 gt 满足"互为子串"或"去掉 ## 前缀后互为子串"，就算命中 1.0。

    适用场景：单 token / wordpiece 级别的 reader 输出。
    """
    if isinstance(gt_answers, str):
        gt_answers = [gt_answers]
    pred = normalize_answer(predicted)
    if not pred:
        return 0.0
    pred_clean = pred.replace('##', '')
    for gt in gt_answers:
        gt_n = normalize_answer(gt)
        if not gt_n:
            continue
        if pred == gt_n:
            return 1.0
        # 子串匹配（去掉 wordpiece 前缀符）
        if len(pred_clean) >= 2 and pred_clean in gt_n:
            return 1.0
        if len(gt_n) >= 2 and gt_n in pred_clean:
            return 1.0
    return 0.0


def token_f1(predicted: str, gt_answers) -> float:
    """Token-level F1（SQuAD 风格）：预测与 gt 在 token 级的 F1。

    一个简化版：把 normalize 后的字符串按空白切 token，求 P/R/F1。
    """
    if isinstance(gt_answers, str):
        gt_answers = [gt_answers]
    pred_tokens = normalize_answer(predicted).split()
    if not pred_tokens:
        return 0.0
    best = 0.0
    for gt in gt_answers:
        gt_tokens = normalize_answer(gt).split()
        if not gt_tokens:
            continue
        common = set(pred_tokens) & set(gt_tokens)
        if not common:
            continue
        # 注意：用 set 求 common 是简化（忽略重复 token）；标准 SQuAD F1 用 multiset。
        n_common = sum(min(pred_tokens.count(t), gt_tokens.count(t)) for t in common)
        precision = n_common / len(pred_tokens)
        recall = n_common / len(gt_tokens)
        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
            best = max(best, f1)
    return best
