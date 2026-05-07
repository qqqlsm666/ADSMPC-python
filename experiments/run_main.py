"""
experiments/run_main.py

整合入口：依次跑 run_numerical_compare 和 run_retrieval_eval。

毕设答辩用法（默认参数即可）：
    python -m experiments.run_main

如果想精简：
    python -m experiments.run_main --skip_retrieval         # 只跑数值一致性
    python -m experiments.run_main --num_queries 5          # 检索质量只跑 5 条
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments import run_numerical_compare, run_retrieval_eval


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", default="experiments/data/mini_corpus.json")
    p.add_argument("--query_idx", type=int, default=0)
    p.add_argument("--num_queries", type=int, default=5)
    p.add_argument("--num_docs", type=int, default=10)
    p.add_argument("--weight_path", default=None)
    p.add_argument("--gen_num", type=int, default=10)
    p.add_argument("--skip_numerical", action="store_true")
    p.add_argument("--skip_retrieval", action="store_true")
    p.add_argument("--skip_cipher_retrieval", action="store_true",
                   help="检索质量阶段跳过密态（只跑明文 baseline）")
    return p.parse_args()


def main():
    args = parse_args()

    # 任务 A：数值一致性
    if not args.skip_numerical:
        sys.argv = [
            "run_numerical_compare",
            "--corpus", args.corpus,
            "--query_idx", str(args.query_idx),
            "--gen_num", str(args.gen_num),
            "--num_docs", str(args.num_docs),
            "--output", "experiments/results/numerical_compare.md",
        ]
        if args.weight_path:
            sys.argv += ["--weight_path", args.weight_path]
        print("\n" + "=" * 60)
        print("任务 A：数值一致性对比")
        print("=" * 60)
        run_numerical_compare.main()
    else:
        print("[skip] 任务 A（数值一致性）")

    # 任务 B：检索质量
    if not args.skip_retrieval:
        sys.argv = [
            "run_retrieval_eval",
            "--corpus", args.corpus,
            "--num_queries", str(args.num_queries),
            "--num_docs", str(args.num_docs),
            "--gen_num", str(args.gen_num),
            "--output", "experiments/results/retrieval_eval.md",
            # 任务 A 已经 gen_params 过了，这里不必再生
            "--skip_gen_params",
        ]
        if args.weight_path:
            sys.argv += ["--weight_path", args.weight_path]
        if args.skip_cipher_retrieval:
            sys.argv += ["--skip_cipher"]
        print("\n" + "=" * 60)
        print("任务 B：检索质量对比")
        print("=" * 60)
        run_retrieval_eval.main()
    else:
        print("[skip] 任务 B（检索质量）")


if __name__ == "__main__":
    main()
