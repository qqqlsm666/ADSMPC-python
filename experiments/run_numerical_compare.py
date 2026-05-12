"""
experiments/run_numerical_compare.py

任务 A：单条 query 跑明文 RAG 和密态 RAG，对比 pooler 输出的 max_diff / mean_diff /
cosine_sim，以及双路 top-1 文档是否一致。结果写到 experiments/results/numerical_compare.md。

用法：
    python -m experiments.run_numerical_compare \\
        --corpus experiments/data/mini_corpus.json \\
        --query_idx 0 \\
        --output experiments/results/numerical_compare.md
"""
import argparse
import os
import sys
import time
from typing import Dict

import torch
import torch.nn.functional as F

# 让 secure_rag 包能 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from secure_rag.config import (
    BERT_CONFIG, SEM_DOC_LEN, QUERY_LEN, VOCAB_SIZE_BM25, default_weight_path,
    LEX_BM25_ONLINE, LEX_BM25_K1, LEX_BM25_B,
)
from secure_rag.plaintext import (
    build_plaintext_bert, encode_docs_to_embeddings, build_bm25_matrix, plaintext_rag,
    build_bm25_components,
)
from secure_rag.params import gen_params

from experiments.data_loader import prepare_corpus_for_rag
from experiments._rag_runner import run_secure_rag_once


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", default="experiments/data/mini_corpus.json")
    p.add_argument("--query_idx", type=int, default=0, help="语料中第几条 query")
    p.add_argument("--weight_path", default=None)
    p.add_argument("--output", default="experiments/results/numerical_compare.md")
    p.add_argument("--skip_gen_params", action="store_true",
                   help="跳过 gen_params（如果之前已经生成过）")
    p.add_argument("--gen_num", type=int, default=10,
                   help="辅助参数生成数量（DEBUG_LEVEL=2 下 10 即可）")
    p.add_argument("--num_docs", type=int, default=10,
                   help="实验用前多少篇文档（必须等于 secure_rag.config.NUM_DOCS）")
    return p.parse_args()


def main():
    args = parse_args()

    # 配置 secure_rag.config.NUM_DOCS：这里依赖文件中的常量，不便动态改；用户自己改 config.py 即可
    if args.num_docs != 10:
        print(f"[Warn] 当前 secure_rag/config.py 的 NUM_DOCS 是 10。"
              f"如果你想改成 {args.num_docs}，需要手动改 config.py。")

    # ---------- 1. 加载语料 ----------
    print(f"[1/6] 加载语料 {args.corpus}")
    data = prepare_corpus_for_rag(
        corpus_path=args.corpus,
        bert_config=BERT_CONFIG,
        doc_max_len=SEM_DOC_LEN,
        query_max_len=QUERY_LEN,
        bm25_vocab_size=VOCAB_SIZE_BM25,
    )

    # 只取前 num_docs 篇（受 secure_rag.config.NUM_DOCS 约束）
    n_docs = args.num_docs
    docs_token_ids = data['docs_token_ids'][:n_docs]              # [N, 24]
    docs_onehot    = data['docs_onehot'][:n_docs]                 # [N, 24, V]
    bm25_vocab     = data['bm25_vocab']                           # [VOCAB_SIZE_BM25]
    queries_token_ids = data['queries_token_ids']
    query_multihots   = data['query_multihots']
    queries_text      = data['queries_text']
    gt_doc_ids        = data['gt_doc_ids']

    q_idx = args.query_idx
    query_text = queries_text[q_idx]
    gt = gt_doc_ids[q_idx]
    print(f"      Query #{q_idx}: '{query_text}'  (gt_doc_id={gt})")

    if gt >= n_docs:
        print(f"[Warn] gt_doc_id {gt} 超出 num_docs={n_docs}，本条 query 没法命中 gt。")

    weight_path = args.weight_path or default_weight_path()

    # ---------- 2. 生成辅助参数（密态用）----------
    if not args.skip_gen_params:
        print(f"[2/6] 生成辅助参数 (gen_num={args.gen_num})")
        os.environ.setdefault('NSSMPC_GEN_NUM', str(args.gen_num))
        from secure_rag.config import GEN_NUM
        gen_params(num=args.gen_num)
    else:
        print("[2/6] 跳过 gen_params")

    # ---------- 3. 构造 db_embeddings + bm25_matrix（明文）----------
    print(f"[3/6] 用明文 BERT 离线编码 {n_docs} 篇文档")
    plain_bert = build_plaintext_bert(weight_path=weight_path, device='cpu')
    db_embeddings = encode_docs_to_embeddings(docs_token_ids, plain_bert, device='cpu')
    bm25_matrix = build_bm25_matrix(docs_token_ids, bm25_vocab)

    # 仅当 LEX_BM25_ONLINE 时另外算 BM25 三分量 (tf, idf, doc_norm)
    bm25_components = None
    if LEX_BM25_ONLINE:
        print(f"      [LEX_BM25_ONLINE] 计算 BM25 三分量 (tf/idf/doc_norm) for k1={LEX_BM25_K1}, b={LEX_BM25_B}")
        tf, idf, doc_norm = build_bm25_components(docs_token_ids, bm25_vocab, k1=LEX_BM25_K1, b=LEX_BM25_B)
        bm25_components = {'tf': tf, 'idf': idf, 'doc_norm': doc_norm}

    # ---------- 4. 跑明文 RAG ----------
    print("[4/6] 跑明文 RAG ...")
    t0 = time.time()
    plain_out = plaintext_rag(
        query_token_ids=queries_token_ids[q_idx:q_idx + 1],
        db_embeddings=db_embeddings,
        bm25_matrix=bm25_matrix,
        db_tokens_onehot=docs_onehot,
        query_multihot=query_multihots[q_idx],
        bert_model=plain_bert,
        bm25_vocab=bm25_vocab,
        device='cpu',
    )
    plain_time = time.time() - t0
    print(f"      明文 RAG 耗时 {plain_time:.2f}s")

    # ---------- 5. 跑密态 RAG ----------
    print("[5/6] 跑密态 RAG ...")
    t0 = time.time()
    cipher_out = run_secure_rag_once(
        query_token_ids=queries_token_ids[q_idx:q_idx + 1],
        query_multihot=query_multihots[q_idx],
        db_embeddings=db_embeddings,
        bm25_matrix=bm25_matrix,
        db_tokens_onehot=docs_onehot,
        weight_path=weight_path,
        tokenizer_name='bert-base-uncased',
        bm25_vocab=bm25_vocab,
        bm25_components=bm25_components,
    )
    cipher_pool = cipher_out['pool']                                       # [1, hidden]
    cipher_rerank = cipher_out['rerank_scores']                            # [NUM_DOCS]
    cipher_answer_id = cipher_out.get('answer_token_id')
    cipher_answer_text = cipher_out.get('answer_text')
    cipher_answer_pos = cipher_out.get('answer_position')
    cipher_time = time.time() - t0
    print(f"      密态 RAG 耗时 {cipher_time:.2f}s")

    # ---------- 6. 对比 + 写报告 ----------
    print("[6/6] 对比并写报告")
    # Pool 一致性
    diff_pool = (plain_out['pool'].float() - cipher_pool.float()).abs()
    pool_max_diff = diff_pool.max().item()
    pool_mean_diff = diff_pool.mean().item()
    pool_cos = F.cosine_similarity(
        plain_out['pool'].float().view(1, -1),
        cipher_pool.float().view(1, -1),
        dim=-1,
    ).item()

    # Rerank 分数一致性
    plain_rerank = plain_out['rerank_scores'].float().view(-1)
    cipher_rerank_f = cipher_rerank.float().view(-1)
    diff_rerank = (plain_rerank - cipher_rerank_f).abs()
    rerank_max_diff = diff_rerank.max().item()
    rerank_mean_diff = diff_rerank.mean().item()
    rerank_cos = F.cosine_similarity(plain_rerank.view(1, -1), cipher_rerank_f.view(1, -1), dim=-1).item()

    # Top-1 一致性
    sem_top1_plain = int(plain_out['sem_top_k_idx'][0].item())
    lex_top1_plain = int(plain_out['lex_top_k_idx'][0].item())
    rerank_top1_plain = int(plain_out['rerank_top_k_idx'][0].item())
    rerank_top1_cipher = int(torch.topk(cipher_rerank_f, k=1).indices[0].item())

    # Reader 答案一致性
    plain_answer_id = plain_out.get('answer_token_id')
    plain_answer_pos = plain_out.get('answer_position')
    # 用 tokenizer 给明文也 decode 一份答案
    plain_answer_text = None
    try:
        from experiments.data_loader import _try_load_tokenizer
        _tok = _try_load_tokenizer('bert-base-uncased')
        plain_answer_text = _tok.decode([plain_answer_id]).strip() if plain_answer_id is not None else None
    except Exception:
        pass

    # Reader 一致性指标
    answer_position_match = (plain_answer_pos == cipher_answer_pos)
    answer_token_match = (plain_answer_id == cipher_answer_id)
    # 跟 ground truth 比对
    gt_answers = data['corpus']['queries'][q_idx].get('answer', [])
    from experiments.metrics import exact_match, partial_match, token_f1
    plain_em = exact_match(plain_answer_text or '', gt_answers)
    cipher_em = exact_match(cipher_answer_text or '', gt_answers)
    plain_pm = partial_match(plain_answer_text or '', gt_answers)
    cipher_pm = partial_match(cipher_answer_text or '', gt_answers)

    md = build_report(
        query_idx=q_idx,
        query_text=query_text,
        gt=gt,
        n_docs=n_docs,
        plain_time=plain_time,
        cipher_time=cipher_time,
        pool_max_diff=pool_max_diff,
        pool_mean_diff=pool_mean_diff,
        pool_cos=pool_cos,
        rerank_max_diff=rerank_max_diff,
        rerank_mean_diff=rerank_mean_diff,
        rerank_cos=rerank_cos,
        sem_top1=sem_top1_plain,
        lex_top1=lex_top1_plain,
        rerank_top1_plain=rerank_top1_plain,
        rerank_top1_cipher=rerank_top1_cipher,
        plain_pool=plain_out['pool'],
        cipher_pool=cipher_pool,
        plain_rerank=plain_rerank,
        cipher_rerank=cipher_rerank_f,
        plain_answer_pos=plain_answer_pos,
        cipher_answer_pos=cipher_answer_pos,
        plain_answer_id=plain_answer_id,
        cipher_answer_id=cipher_answer_id,
        plain_answer_text=plain_answer_text,
        cipher_answer_text=cipher_answer_text,
        answer_position_match=answer_position_match,
        answer_token_match=answer_token_match,
        gt_answers=gt_answers,
        plain_em=plain_em,
        cipher_em=cipher_em,
        plain_pm=plain_pm,
        cipher_pm=cipher_pm,
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding='utf-8') as f:
        f.write(md)
    print(f"\n报告已写入: {args.output}")
    print("\n" + "=" * 60)
    # Windows 终端默认 GBK 编码，无法打印部分 Unicode 字符（如 ✅ ⚠️）
    try:
        print(md)
    except UnicodeEncodeError:
        # 退化方案：把无法编码的字符替换成 ?
        encoding = sys.stdout.encoding or 'utf-8'
        print(md.encode(encoding, errors='replace').decode(encoding))


def build_report(*, query_idx, query_text, gt, n_docs, plain_time, cipher_time,
                 pool_max_diff, pool_mean_diff, pool_cos,
                 rerank_max_diff, rerank_mean_diff, rerank_cos,
                 sem_top1, lex_top1, rerank_top1_plain, rerank_top1_cipher,
                 plain_pool, cipher_pool, plain_rerank, cipher_rerank,
                 plain_answer_pos, cipher_answer_pos,
                 plain_answer_id, cipher_answer_id,
                 plain_answer_text, cipher_answer_text,
                 answer_position_match, answer_token_match,
                 gt_answers, plain_em, cipher_em, plain_pm, cipher_pm):
    rerank_top1_match = rerank_top1_plain == rerank_top1_cipher
    rerank_hit_plain = rerank_top1_plain == gt
    rerank_hit_cipher = rerank_top1_cipher == gt
    return f"""# 数值一致性对比 (Numerical Compare) — B2 + Reader 方案

## 实验设置
- Query #{query_idx}: `{query_text}`
- Ground truth doc id: {gt}
- Ground truth answers: {gt_answers}
- 文档库大小: {n_docs}
- BERT 配置: bert-tiny (2 层、hidden=128、vocab=30522)
- Reranker: pool [1,128] @ db_embs.T [128,N_DOCS] (密态 ASS@ASS matmul)
- Reader: 启发式 head (pool · seq_out → 密态 argmax → 密态 gather token)
- 输出方向：rerank/pool/answer 均在 client 端 restore（server 不学习任何客户端结果）

## 性能
| 指标 | 明文 RAG | 密态 RAG |
|---|---|---|
| 端到端耗时 | {plain_time:.2f} s | {cipher_time:.2f} s |

## Pool 一致性 (联合推理 [CLS] pooler)
| 指标 | 数值 | 含义 |
|---|---|---|
| `max_diff` | {pool_max_diff:.4f} | 最大绝对误差 |
| `mean_diff` | {pool_mean_diff:.4f} | 平均绝对误差 |
| `cosine_sim` | {pool_cos:.6f} | 越接近 1 越一致 |

## Rerank 分数一致性 (Cross-Encoder Reranker)
| 指标 | 数值 | 含义 |
|---|---|---|
| `max_diff` | {rerank_max_diff:.4f} | reranker 各维分数的最大误差 |
| `mean_diff` | {rerank_mean_diff:.4f} | 平均误差 |
| `cosine_sim` | {rerank_cos:.6f} | 排序相似度 |

## Top-1 检索一致性
| 路径 | 选中 doc id | gt | 命中? |
|---|---|---|---|
| 明文双路·语义 top-1 | {sem_top1} | {gt} | {'YES' if sem_top1 == gt else 'NO'} |
| 明文双路·词汇 top-1 | {lex_top1} | {gt} | {'YES' if lex_top1 == gt else 'NO'} |
| **明文 Reranker top-1** | **{rerank_top1_plain}** | {gt} | **{'YES' if rerank_hit_plain else 'NO'}** |
| **密态 Reranker top-1** | **{rerank_top1_cipher}** | {gt} | **{'YES' if rerank_hit_cipher else 'NO'}** |

明文 vs 密态 reranker top-1 是否一致：**{'YES' if rerank_top1_match else 'NO'}**

## Reader 抽取式生成结果

| 维度 | 明文 RAG | 密态 RAG |
|---|---|---|
| 答案位置 (在长 56 联合序列中) | {plain_answer_pos} | {cipher_answer_pos} |
| 答案 token id | {plain_answer_id} | {cipher_answer_id} |
| 答案文本 | `{plain_answer_text}` | `{cipher_answer_text}` |
| EM (严格)  | {plain_em:.2f} | {cipher_em:.2f} |
| Partial Match (子串放宽) | {plain_pm:.2f} | {cipher_pm:.2f} |

| 一致性维度 | 结果 |
|---|---|
| 明文 vs 密态 答案位置一致 | {'YES' if answer_position_match else 'NO'} |
| 明文 vs 密态 答案 token 一致 | {'YES' if answer_token_match else 'NO'} |

## Pool 输出预览
```
明文 first5: {plain_pool[0, :5].tolist()}
密态 first5: {cipher_pool[0, :5].tolist()}
```

## Rerank 分数预览（[NUM_DOCS] 全量）
```
明文 rerank: {[round(x, 3) for x in plain_rerank.tolist()]}
密态 rerank: {[round(x, 3) for x in cipher_rerank.tolist()]}
```

## 结论
- Pool 一致性 cosine_sim={pool_cos:.4f}
- Rerank 一致性 cosine_sim={rerank_cos:.4f}
- 明文/密态 reranker top-1 一致：{rerank_top1_match}
- 明文/密态 Reader 答案 token 一致：{answer_token_match}
- 加密延迟代价：×{cipher_time / max(plain_time, 1e-6):.1f}
- **隐私保证**：所有结果（rerank、pool、answer）均仅在 client 端 restore，server 全程不学习客户端的查询、检索结果或答案。
"""


if __name__ == "__main__":
    main()
