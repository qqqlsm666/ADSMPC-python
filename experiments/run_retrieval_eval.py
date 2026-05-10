"""
experiments/run_retrieval_eval.py

任务 B：在 N 条 query 上跑明文 RAG（cheap）和密态 RAG（expensive），算 Recall@K /
MRR / NDCG@K，输出对比表格到 experiments/results/retrieval_eval.md。

由于密态 RAG 一条 query 在 CPU + torchcsprng 下大概 1-2 分钟，**默认只跑前 N 条**
（--num_queries），先快速看明文 vs 密态趋势。

用法：
    python -m experiments.run_retrieval_eval \\
        --corpus experiments/data/mini_corpus.json \\
        --num_queries 10 \\
        --output experiments/results/retrieval_eval.md

    # 想跑全部 50 条（约 1 小时）：
    python -m experiments.run_retrieval_eval --num_queries 50 \\
        --skip_cipher  # 也可以先只跑明文看 baseline
"""
import argparse
import os
import sys
import time
from typing import List, Dict

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from secure_rag.config import (
    BERT_CONFIG, SEM_DOC_LEN, QUERY_LEN, VOCAB_SIZE_BM25, default_weight_path,
)
from secure_rag.plaintext import (
    build_plaintext_bert, encode_docs_to_embeddings, build_bm25_matrix, plaintext_rag,
)
from secure_rag.params import gen_params

from experiments.data_loader import prepare_corpus_for_rag
from experiments.metrics import recall_at_k, mrr, ndcg_at_k, precision_at_k, aggregate
from experiments._rag_runner import run_secure_rag_once


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", default="experiments/data/mini_corpus.json")
    p.add_argument("--num_queries", type=int, default=10,
                   help="跑前 N 条 query（密态 RAG 一条 ~1-2 分钟）")
    p.add_argument("--num_docs", type=int, default=10)
    p.add_argument("--weight_path", default=None)
    p.add_argument("--output", default="experiments/results/retrieval_eval.md")
    p.add_argument("--skip_gen_params", action="store_true")
    p.add_argument("--skip_cipher", action="store_true",
                   help="只跑明文，省时间；密态那一栏会留空")
    p.add_argument("--gen_num", type=int, default=10)
    p.add_argument("--ks", default="1,3,5",
                   help="逗号分隔的 K 列表，例如 1,3,5")
    return p.parse_args()


def fuse_topk(sem_idx: torch.Tensor, lex_idx: torch.Tensor, k_max: int) -> List[int]:
    """
    简单 fusion：把语义路和词汇路的 top-1（top-k_max）结果按交错顺序合并去重。
    [sem_top1, lex_top1, sem_top2, lex_top2, ...]
    """
    out = []
    seen = set()
    for i in range(k_max):
        for src in (sem_idx, lex_idx):
            if i < len(src):
                idx = int(src[i].item())
                if idx not in seen:
                    out.append(idx); seen.add(idx)
    return out


def per_query_metrics(retrieved: List[int], relevant: List[int], ks: List[int]) -> Dict[str, float]:
    """对单条 query 算 Recall@K / Precision@K / NDCG@K / MRR。"""
    out = {}
    for k in ks:
        out[f"P@{k}"] = precision_at_k(retrieved, relevant, k)
        out[f"R@{k}"] = recall_at_k(retrieved, relevant, k)
        out[f"NDCG@{k}"] = ndcg_at_k(retrieved, relevant, k)
    out["MRR"] = mrr(retrieved, relevant)
    return out


def run_plaintext_pass(data, plain_bert, db_embeddings, bm25_matrix, n_docs, ks, tokenizer=None):
    """对所有 gt_doc_id < n_docs 的 query 跑明文 RAG。

    使用 reranker 的 top-K 作为最终 retrieved（与密态侧对齐）。
    同时返回每条 query 的 reader 答案（用于 EM/PM 评估）。
    """
    from secure_rag.plaintext import plaintext_rag
    from experiments.metrics import exact_match, partial_match, token_f1
    queries_token_ids = data['queries_token_ids']
    query_multihots   = data['query_multihots']
    docs_onehot       = data['docs_onehot'][:n_docs]
    gt_doc_ids        = data['gt_doc_ids']
    queries_meta      = data['corpus']['queries']

    n_queries = queries_token_ids.shape[0]
    per_q_metrics = []
    retrieved_list = []
    eval_indices = []
    answers_info = []  # 每条 query 的 (gt_answers, plain_answer_text, em, pm)
    for q_idx in range(n_queries):
        if gt_doc_ids[q_idx] >= n_docs:
            continue
        out = plaintext_rag(
            query_token_ids=queries_token_ids[q_idx:q_idx + 1],
            db_embeddings=db_embeddings,
            bm25_matrix=bm25_matrix,
            db_tokens_onehot=docs_onehot,
            query_multihot=query_multihots[q_idx],
            bert_model=plain_bert,
            bm25_vocab=data['bm25_vocab'],
            device='cpu',
            top_k=max(ks),
        )
        retrieved = out['rerank_scores'].argsort(descending=True).tolist()[:max(ks)]
        retrieved_list.append(retrieved)
        m = per_query_metrics(retrieved, [gt_doc_ids[q_idx]], ks)

        # Reader EM
        gt_answers = queries_meta[q_idx].get('answer', [])
        ans_id = out.get('answer_token_id')
        ans_text = None
        if tokenizer is not None and ans_id is not None:
            try:
                ans_text = tokenizer.decode([ans_id]).strip()
            except Exception:
                ans_text = None
        em = exact_match(ans_text or '', gt_answers)
        pm = partial_match(ans_text or '', gt_answers)
        f1 = token_f1(ans_text or '', gt_answers)
        m['EM']  = em
        m['PM']  = pm
        m['F1']  = f1
        answers_info.append({
            'q_idx': q_idx,
            'gt': gt_answers,
            'predicted_text': ans_text,
            'predicted_id': ans_id,
            'em': em, 'pm': pm,
        })
        per_q_metrics.append(m)
        eval_indices.append(q_idx)
    return retrieved_list, per_q_metrics, eval_indices, answers_info


def run_cipher_pass(data, weight_path, db_embeddings, bm25_matrix, n_docs, ks, num_queries, eval_indices=None):
    """对前 num_queries 条 gt_doc_id < n_docs 的 query 跑密态 RAG。

    密态侧的 retrieved 直接用 secure_rag 的 reranker 输出（rerank_scores 取 argsort）。
    单条 query 失败（子进程超时 / 报错）会被跳过，不阻塞整体评估。
    """
    from experiments.metrics import exact_match, partial_match, token_f1
    queries_token_ids = data['queries_token_ids']
    query_multihots   = data['query_multihots']
    docs_onehot       = data['docs_onehot'][:n_docs]
    gt_doc_ids        = data['gt_doc_ids']
    queries_meta      = data['corpus']['queries']

    if eval_indices is None:
        eval_indices = [i for i in range(queries_token_ids.shape[0]) if gt_doc_ids[i] < n_docs]
    eval_indices = eval_indices[:num_queries]

    per_q_metrics = []
    retrieved_list = []
    answers_info = []
    failed = []
    for n, q_idx in enumerate(eval_indices):
        print(f"\n--- 密态 RAG 第 {n + 1}/{len(eval_indices)} 条 query (idx={q_idx}) ---")
        t0 = time.time()
        try:
            cipher_out = run_secure_rag_once(
                query_token_ids=queries_token_ids[q_idx:q_idx + 1],
                query_multihot=query_multihots[q_idx],
                db_embeddings=db_embeddings,
                bm25_matrix=bm25_matrix,
                db_tokens_onehot=docs_onehot,
                weight_path=weight_path,
                timeout_sec=240,
                tokenizer_name='bert-base-uncased',
                bm25_vocab=data['bm25_vocab'],
            )
            elapsed = time.time() - t0
            print(f"     一条耗时 {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"     一条失败 ({elapsed:.1f}s): {e}")
            failed.append((q_idx, str(e)))
            continue

        rerank_scores = cipher_out['rerank_scores'].view(-1)
        retrieved = rerank_scores.argsort(descending=True).tolist()[:max(ks)]
        retrieved_list.append(retrieved)
        m = per_query_metrics(retrieved, [gt_doc_ids[q_idx]], ks)

        # Reader EM
        gt_answers = queries_meta[q_idx].get('answer', [])
        ans_text = cipher_out.get('answer_text')
        ans_id = cipher_out.get('answer_token_id')
        em = exact_match(ans_text or '', gt_answers)
        pm = partial_match(ans_text or '', gt_answers)
        f1 = token_f1(ans_text or '', gt_answers)
        m['EM']  = em
        m['PM']  = pm
        m['F1']  = f1
        answers_info.append({
            'q_idx': q_idx,
            'gt': gt_answers,
            'predicted_text': ans_text,
            'predicted_id': ans_id,
            'em': em, 'pm': pm,
        })
        per_q_metrics.append(m)

    if failed:
        print(f"\n[密态 RAG] 共 {len(failed)} 条 query 失败：{[idx for idx, _ in failed]}")
    return retrieved_list, per_q_metrics, answers_info


def main():
    args = parse_args()
    ks = [int(x) for x in args.ks.split(",")]

    # ---------- 1. 加载语料 ----------
    print(f"[1/5] 加载语料 {args.corpus}")
    data = prepare_corpus_for_rag(
        corpus_path=args.corpus,
        bert_config=BERT_CONFIG,
        doc_max_len=SEM_DOC_LEN,
        query_max_len=QUERY_LEN,
        bm25_vocab_size=VOCAB_SIZE_BM25,
    )
    n_docs = args.num_docs

    # ---------- 2. 生成辅助参数 ----------
    if not args.skip_gen_params and not args.skip_cipher:
        print(f"[2/5] 生成辅助参数 (gen_num={args.gen_num})")
        os.environ.setdefault('NSSMPC_GEN_NUM', str(args.gen_num))
        gen_params(num=args.gen_num)
    else:
        print("[2/5] 跳过 gen_params")

    # ---------- 3. 离线编码 + BM25 ----------
    weight_path = args.weight_path or default_weight_path()
    print(f"[3/5] 用明文 BERT 离线编码 {n_docs} 篇文档")
    plain_bert = build_plaintext_bert(weight_path=weight_path, device='cpu')
    db_embeddings = encode_docs_to_embeddings(data['docs_token_ids'][:n_docs], plain_bert)
    bm25_matrix = build_bm25_matrix(data['docs_token_ids'][:n_docs], data['bm25_vocab'])

    # ---------- 4. 明文 + 密态 ----------
    # 加载 tokenizer 给 plaintext reader decode
    from experiments.data_loader import _try_load_tokenizer
    tokenizer = None
    try:
        tokenizer = _try_load_tokenizer('bert-base-uncased')
    except Exception as e:
        print(f"[Warn] tokenizer 加载失败，明文侧 reader 答案不会 decode: {e}")

    print(f"[4/5] 跑明文 RAG（gt_doc_id < {n_docs} 的全部 query）")
    t0 = time.time()
    plain_retrieved, plain_per_q, eval_indices, plain_answers = run_plaintext_pass(
        data, plain_bert, db_embeddings, bm25_matrix, n_docs, ks, tokenizer=tokenizer,
    )
    plain_total_time = time.time() - t0
    plain_avg = aggregate(plain_per_q)
    print(f"     评估了 {len(plain_per_q)} 条 query "
          f"(原始 50 条中过滤 gt_doc_id < {n_docs} 的)")
    print(f"     明文阶段总耗时 {plain_total_time:.2f}s, "
          f"平均: {{ {', '.join(f'{k}={v:.3f}' for k, v in plain_avg.items())} }}")

    cipher_avg, cipher_total_time, cipher_per_q, cipher_answers = None, 0.0, [], []
    if not args.skip_cipher:
        n_cipher = min(args.num_queries, len(eval_indices))
        print(f"[5/5] 跑密态 RAG（前 {n_cipher} 条 query，预计 {n_cipher * 1.5:.0f} 分钟）")
        t0 = time.time()
        _, cipher_per_q, cipher_answers = run_cipher_pass(
            data, weight_path, db_embeddings, bm25_matrix, n_docs, ks, n_cipher,
            eval_indices=eval_indices,
        )
        cipher_total_time = time.time() - t0
        cipher_avg = aggregate(cipher_per_q)
        print(f"     密态阶段总耗时 {cipher_total_time:.2f}s")
    else:
        print("[5/5] 跳过密态 RAG")

    # ---------- 写报告 ----------
    md = build_report(
        n_docs=n_docs,
        n_q_plain=len(plain_per_q),
        n_q_cipher=len(cipher_per_q),
        plain_total_time=plain_total_time,
        cipher_total_time=cipher_total_time,
        ks=ks,
        plain_avg=plain_avg,
        cipher_avg=cipher_avg,
        plain_answers=plain_answers,
        cipher_answers=cipher_answers,
    )
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding='utf-8') as f:
        f.write(md)
    print(f"\n报告已写入: {args.output}")
    print("\n" + "=" * 60)
    try:
        print(md)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'utf-8'
        print(md.encode(encoding, errors='replace').decode(encoding))


def build_report(*, n_docs, n_q_plain, n_q_cipher, plain_total_time, cipher_total_time,
                 ks, plain_avg, cipher_avg, plain_answers=None, cipher_answers=None):
    plain_row = lambda k, name: f"{plain_avg[name]:.4f}" if plain_avg.get(name) is not None else "-"
    cipher_row = lambda k, name: (f"{cipher_avg[name]:.4f}" if (cipher_avg and cipher_avg.get(name) is not None) else "-")

    rows = []
    for k in ks:
        rows.append((f"Recall@{k}", f"R@{k}"))
        rows.append((f"Precision@{k}", f"P@{k}"))
        rows.append((f"NDCG@{k}", f"NDCG@{k}"))
    rows.append(("MRR", "MRR"))
    rows.append(("Reader EM (严格)", "EM"))
    rows.append(("Reader Partial Match (子串放宽)", "PM"))
    rows.append(("Reader Token F1", "F1"))

    table_md = "| 指标 | 明文 RAG | 密态 RAG |\n|---|---|---|\n"
    for label, name in rows:
        table_md += f"| {label} | {plain_row(0, name)} | {cipher_row(0, name)} |\n"

    # Reader 答案明细表
    answers_md = ""
    if plain_answers and cipher_answers:
        answers_md = "\n## Reader 答案明细（每条 query 的答案对照）\n\n"
        answers_md += "| q_idx | gt | 明文预测 | 密态预测 | 明文 EM | 密态 EM |\n|---|---|---|---|---|---|\n"
        for pa, ca in zip(plain_answers, cipher_answers):
            gt_str = '/'.join(pa.get('gt', []))[:30]
            answers_md += (f"| {pa['q_idx']} | {gt_str} | "
                           f"`{pa.get('predicted_text', '-')}` | "
                           f"`{ca.get('predicted_text', '-')}` | "
                           f"{pa.get('em', 0):.0f} | {ca.get('em', 0):.0f} |\n")

    return f"""# 检索质量对比 (Retrieval Eval) — B2 + Reader 方案

## 实验设置
- 文档库大小: {n_docs}
- 评估 query 数: 明文 {n_q_plain} 条；密态 {n_q_cipher} 条
- BERT: bert-tiny (2 层、hidden=128、vocab=30522)
- 检索路径: 双路初次检索 → 联合 BERT 推理 → 密态 reranker (pool @ db_embs.T) → 取 top-K
- 生成路径: 密态 reader (pool · seq_out → 密态 argmax → 密态 gather token)
- 输出方向: rerank/pool/answer 均仅在 client 端 restore；server 不学习任何客户端结果
- K 值: {ks}

## 性能
| 阶段 | 总耗时 |
|---|---|
| 明文 RAG ({n_q_plain} q) | {plain_total_time:.2f} s ({plain_total_time / max(n_q_plain, 1):.2f} s/q) |
| 密态 RAG ({n_q_cipher} q) | {cipher_total_time:.2f} s ({(cipher_total_time / max(n_q_cipher, 1)) if n_q_cipher else 0:.2f} s/q) |

## 检索质量 + Reader 答案质量
{table_md}
{answers_md}
## 结论
- 加密前后 Recall@5 差距: {('+' if cipher_avg and cipher_avg.get('R@5', 0) >= plain_avg.get('R@5', 0) else '')}{(cipher_avg.get('R@5', 0) - plain_avg.get('R@5', 0)) if cipher_avg else 0:.4f}
- 加密前后 Reader EM 差距: {(cipher_avg.get('EM', 0) - plain_avg.get('EM', 0)) if cipher_avg else 0:+.4f}
- 加密延迟代价: ×{(cipher_total_time / max(n_q_cipher, 1)) / max(plain_total_time / max(n_q_plain, 1), 1e-6) if cipher_avg else 0:.1f}
- 隐私保证: server 全程不还原任何与 query 相关的明文（rerank/pool/answer 都在 client 端 restore）
"""


if __name__ == "__main__":
    main()
