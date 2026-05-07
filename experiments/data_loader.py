"""
experiments/data_loader.py

加载 mini_corpus.json + 用 HuggingFace BertTokenizer (bert-tiny / bert-base-uncased) 把
text 转成 token id 张量；并构造 BM25 vocab 和 query 的多热向量。

为什么不直接用 prajjwal1/bert-tiny tokenizer：
- prajjwal1/bert-tiny 复用的是 bert-base-uncased 的 30522 vocab tokenizer
- 这两者的 vocab 完全一样，所以这里直接用 bert-base-uncased 即可（更稳定，离线缓存大概率有）

如果你的网络不通 HuggingFace，可以：
    pip install transformers
    huggingface-cli download bert-base-uncased --local-dir ./hf_models/bert-base-uncased
然后传 model_name='./hf_models/bert-base-uncased'
"""
import json
from collections import Counter
from typing import List, Tuple, Dict
import torch


# 默认 tokenizer 名称：bert-base-uncased 与 prajjwal1/bert-tiny 的 vocab 完全一致
DEFAULT_TOKENIZER_NAME = "bert-base-uncased"


def _try_load_tokenizer(model_name: str):
    """尝试加载 tokenizer，附带 mirror 兜底。"""
    try:
        from transformers import BertTokenizer
    except ImportError as e:
        raise RuntimeError(
            "需要安装 transformers: pip install transformers"
        ) from e
    try:
        return BertTokenizer.from_pretrained(model_name)
    except Exception as e1:
        # 中国大陆常见的连不通 HF，尝试镜像
        import os
        if not os.environ.get('HF_ENDPOINT'):
            try:
                os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
                return BertTokenizer.from_pretrained(model_name)
            except Exception as e2:
                raise RuntimeError(
                    f"加载 tokenizer '{model_name}' 失败：{e1}\n"
                    f"已尝试 mirror https://hf-mirror.com 仍失败：{e2}\n"
                    f"请手动下载并传 model_name=本地路径"
                ) from e2
        raise


def load_corpus(path: str) -> Dict:
    """加载 mini_corpus.json，返回 {meta, documents, queries}。"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def tokenize_texts(
    texts: List[str],
    max_len: int,
    tokenizer=None,
    model_name: str = DEFAULT_TOKENIZER_NAME,
) -> torch.Tensor:
    """
    把多条 text 转成 [N, max_len] 的 long tensor。
    超长截断、不够补 0。返回的 token id 包含 [CLS]/[SEP]，与 bert-tiny 期望一致。
    """
    tok = tokenizer or _try_load_tokenizer(model_name)
    out = tok(
        texts,
        max_length=max_len,
        padding='max_length',
        truncation=True,
        return_tensors='pt',
    )
    return out['input_ids']                          # [N, max_len] long


def build_bm25_vocab(
    docs_token_ids: torch.Tensor,
    queries_token_ids: torch.Tensor,
    vocab_size: int,
    pad_id: int = 0,
    cls_id: int = 101,
    sep_id: int = 102,
) -> List[int]:
    """
    构造 BM25 用的小词表。
    优先策略：按 query 出现顺序收集 query token（保证早期 query 优先有覆盖），
    再用 doc 词频补齐。
    """
    special = {pad_id, cls_id, sep_id}

    # 1) 按 query 顺序、保留出现顺序地收集 query token
    candidate: List[int] = []
    seen = set()
    for q_row in queries_token_ids.tolist():
        for tok in q_row:
            if tok in special:
                continue
            if tok not in seen:
                candidate.append(tok); seen.add(tok)
            if len(candidate) >= vocab_size:
                break
        if len(candidate) >= vocab_size:
            break

    # 2) 不够再用 doc 词频补齐
    if len(candidate) < vocab_size:
        counter = Counter(docs_token_ids.flatten().tolist())
        for sp in special:
            counter.pop(sp, None)
        for tok, _ in counter.most_common():
            if tok not in seen:
                candidate.append(tok); seen.add(tok)
            if len(candidate) >= vocab_size:
                break

    # 3) 还不够就用 0 填（不会被 query / doc 命中）
    while len(candidate) < vocab_size:
        candidate.append(0)
    return candidate[:vocab_size]


def query_to_multihot(
    query_token_ids: torch.Tensor,
    bm25_vocab: List[int],
    pad_id: int = 0,
    cls_id: int = 101,
    sep_id: int = 102,
) -> torch.Tensor:
    """
    把单条 query 转成 [V, 1] 的多热向量；query 包含的 token id 在 BM25 vocab 中的位置标 1。
    """
    special = {pad_id, cls_id, sep_id}
    V = len(bm25_vocab)
    multihot = torch.zeros(V, 1, dtype=torch.float32)
    vocab_set = set(bm25_vocab)
    pos_map = {t: i for i, t in enumerate(bm25_vocab)}
    for tok in query_token_ids.flatten().tolist():
        if tok in special:
            continue
        if tok in vocab_set:
            multihot[pos_map[tok], 0] = 1.0
    return multihot


def prepare_corpus_for_rag(
    corpus_path: str,
    bert_config: Dict,
    doc_max_len: int,
    query_max_len: int,
    bm25_vocab_size: int,
    tokenizer_name: str = DEFAULT_TOKENIZER_NAME,
) -> Dict:
    """
    一站式：加载 corpus、tokenize、构造 BM25 vocab、转 doc 的 one-hot 表示。

    Returns dict:
        - corpus:           原始 json
        - tokenizer:        BertTokenizer
        - docs_token_ids:   [N_DOCS, doc_max_len] long
        - docs_onehot:      [N_DOCS, doc_max_len, vocab_size] float
        - queries_token_ids:[N_QUERIES, query_max_len] long
        - queries_text:     List[str]
        - gt_doc_ids:       List[int]，每条 query 的 ground truth doc id
        - bm25_vocab:       List[int]，长度 bm25_vocab_size
        - query_multihots:  [N_QUERIES, bm25_vocab_size, 1] float
    """
    import torch.nn.functional as F

    corpus = load_corpus(corpus_path)
    tokenizer = _try_load_tokenizer(tokenizer_name)

    docs = corpus['documents']
    queries = corpus['queries']

    docs_text = [d['text'] for d in docs]
    queries_text = [q['text'] for q in queries]
    gt_doc_ids = [q['gt_doc_id'] for q in queries]

    docs_token_ids = tokenize_texts(docs_text, max_len=doc_max_len, tokenizer=tokenizer)
    queries_token_ids = tokenize_texts(queries_text, max_len=query_max_len, tokenizer=tokenizer)

    docs_onehot = F.one_hot(docs_token_ids, num_classes=bert_config['vocab_size']).float()

    bm25_vocab = build_bm25_vocab(docs_token_ids, queries_token_ids, bm25_vocab_size)

    query_multihots = torch.stack([
        query_to_multihot(queries_token_ids[i], bm25_vocab) for i in range(len(queries))
    ], dim=0)

    return {
        'corpus':            corpus,
        'tokenizer':         tokenizer,
        'docs_token_ids':    docs_token_ids,
        'docs_onehot':       docs_onehot,
        'queries_token_ids': queries_token_ids,
        'queries_text':      queries_text,
        'gt_doc_ids':        gt_doc_ids,
        'bm25_vocab':        bm25_vocab,
        'query_multihots':   query_multihots,
    }
