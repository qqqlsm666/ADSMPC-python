# ADSMPC-python · 加密 RAG 系统

> 基于 [NssMPClib](https://github.com/XidianNSS/NssMPClib)（西电 NSS 实验室）2PC 半诚实多方安全计算框架，实现的"双路检索 + 密态 Top-K + 联合 BERT 推理"加密 RAG 原型，并配套**密态 vs 明文**实验对比。

---

## 系统架构

```
                ┌──────────────────────── 加密 RAG 系统 ────────────────────────┐
                │                                                              │
   Client ─────►│  ┌──────────┐    ┌────────────────┐    ┌──────────────────┐   │
   (持有 query) │  │ tokenize │───►│ 密态 query     │───►│ 密态 BERT 编码   │   │
                │  └──────────┘    │ + 多热向量切分 │    └──────────────────┘   │
                │                  └────────────────┘             │            │
                │                                                  ▼            │
                │  Server (持有文档库)         ┌────────────────────────────┐    │
                │  ┌──────────────────────┐    │ 双路打分                  │   │
                │  │ db_embeddings [N,h]  │───►│ ├ 语义路: query·doc 内积 │   │
                │  │ bm25_matrix [V,N]    │───►│ └ 词汇路: BM25 简化打分  │   │
                │  │ db_tokens_oh [N,L,V] │    └────────────┬───────────────┘   │
                │  └──────────────────────┘                 ▼                  │
                │                            ┌────────────────────────────┐    │
                │                            │ 密态 Top-K 指示器排序     │    │
                │                            │ (冒泡 + indicator swap)    │    │
                │                            └────────────┬───────────────┘    │
                │                                          ▼                  │
                │                            ┌────────────────────────────┐    │
                │                            │ 通过指示器抽取真实 token  │    │
                │                            │ (sum(ind ⊗ db_tokens))     │    │
                │                            └────────────┬───────────────┘    │
                │                                          ▼                  │
                │                          [Q | doc_sem | doc_lex] (Seq=56)  │
                │                                          │                  │
                │                                          ▼                  │
                │                            ┌────────────────────────────┐    │
                │                            │ 联合密态 BERT 推理         │    │
                │                            └────────────┬───────────────┘    │
                │                                          ▼                  │
                │                                  pool [1, 128]               │
                │                                                              │
                └──────────────────────────────────────────────────────────────┘
```

详细架构与威胁模型见：
- [docs/architecture.md](docs/architecture.md)
- [docs/threat_model.md](docs/threat_model.md)
- [docs/experiments.md](docs/experiments.md)

---

## 目录结构

```
ADSMPC-python/
├── README.md                           ← 本文件
├── requirements.txt                    ← Python 依赖
├── .gitignore
│
├── secure_rag/                         ← 加密 RAG 应用层（本项目核心）
│   ├── __init__.py
│   ├── config.py                       ← BERT 与 RAG 超参
│   ├── retrieval.py                    ← 双路打分 + 密态 Top-K
│   ├── server.py                       ← Server 角色（party_id=0）
│   ├── client.py                       ← Client 角色（party_id=1）
│   ├── plaintext.py                    ← 明文 RAG（实验对照）
│   └── params.py                       ← 一次性生成全部辅助参数
│
├── experiments/                        ← 实验脚本与数据
│   ├── data/
│   │   └── mini_corpus.json            ← 50 query × 50 doc + ground truth
│   ├── data_loader.py                  ← 接入 HF tokenizer
│   ├── metrics.py                      ← Recall / Precision / NDCG / MRR
│   ├── _rag_runner.py                  ← 单进程双线程跑加密 RAG 的 helper
│   ├── run_numerical_compare.py        ← 任务 A：数值一致性
│   ├── run_retrieval_eval.py           ← 任务 B：检索质量
│   ├── run_main.py                     ← 整合入口
│   └── results/                        ← 实验输出（自动写）
│
├── docs/                               ← 项目文档
│   ├── architecture.md
│   ├── threat_model.md
│   └── experiments.md
│
├── models/                             ← 预训练权重
│   └── bert_tiny_weights.pth
│
├── scripts/                            ← 编译脚本（torchcsprng 等）
│   ├── build_csprng_cpu.bat
│   └── dump_deps.bat
│
├── NssMPClib/                          ← 底层 MPC 库（不动，照搬）
│   ├── NssMPC/                         ← 库源码
│   ├── csprng/                         ← AES PRG 编译扩展
│   ├── tutorials/                      ← 库教程 notebook
│   ├── data/                           ← CNN/AlexNet 等模型骨架
│   └── test/                           ← 旧入口 rag.py / test_mha.py（兼容保留）
│
└── test/                               ← 顶层 demo（CNN MNIST 推理）
    └── inference_test.ipynb
```

---

## 安装

需要 Python 3.10、PyTorch 2.3.0+cu121（或 CPU 版）、Visual Studio 2022 C++ Build Tools（编译 torchcsprng 用）。

```bash
# 1. 创建 conda 环境
conda create -n ADSMPC-python python=3.10 -y
conda activate ADSMPC-python

# 2. 装 PyTorch（GPU 版，driver 13.x 兼容 cu121）
pip install torch==2.3.0 torchvision==0.18.0 torchaudio==2.3.0 \
    --index-url https://download.pytorch.org/whl/cu121

# 3. 装其他依赖
pip install -r requirements.txt

# 4. 装 NssMPC 库本体
cd NssMPClib && pip install -e . && cd ..

# 5. （强烈推荐）编译 torchcsprng 加速 PRG（CPU AES，Linux/Win 都可）
#    Windows 需要 VS C++ Build Tools + cuda-cudart-dev/cuda-nvcc(headers)
#    详见 scripts/build_csprng_cpu.bat
conda install -c nvidia cuda-cudart-dev=12.1.105 cuda-nvcc=12.1.105 -y
cd NssMPClib/csprng && pip install -e . && cd ../..
```

不装 torchcsprng 也能跑，会自动 fallback 到 `torch.Generator` 慢路径——但单条 query 从 1-2 分钟变成 25-30 分钟。

---

## 快速启动

### 一键跑实验（推荐毕设答辩）

```bash
# 任务 A 数值一致性 + 任务 B 检索质量（前 5 条 query）
python -m experiments.run_main
```

跑完后产物：
- `experiments/results/numerical_compare.md` – 单条 query 的 max_diff / cosine_sim
- `experiments/results/retrieval_eval.md` – 多条 query 的 Recall@K / MRR / NDCG@K

### 分开跑（更可控）

```bash
# 只跑数值一致性
python -m experiments.run_numerical_compare --query_idx 0

# 只跑检索质量（先 10 条预览）
python -m experiments.run_retrieval_eval --num_queries 10

# 全 50 条（约 1-2 小时）
python -m experiments.run_retrieval_eval --num_queries 50

# 只跑明文 baseline（不调用密态侧）
python -m experiments.run_retrieval_eval --num_queries 50 --skip_cipher
```

### 旧入口（兼容保留）

```bash
DEVICE=cpu NSSMPC_GEN_NUM=10 python NssMPClib/test/rag.py
```

仍然可用，跑的就是原 `torch.randn` 占位的那个 demo。

---

## 实验结果（会随实际运行更新）

### 任务 A：密态 vs 明文 数值一致性
（详见 `experiments/results/numerical_compare.md`）

### 任务 B：检索质量对比
（详见 `experiments/results/retrieval_eval.md`）

---

## 已知限制

1. **没有生成式 LLM**：最终输出是 [1, 128] pooler 向量，不能直接产出文本回答。
2. **Top-K 是 O(N·K) 冒泡排序**：N=10 OK，N=1000+ 不实用。
3. **BM25 是简化版**：`secure_rag/plaintext.py` 用真 BM25 公式构造矩阵，但密态侧在矩阵已构造好的前提下只算简化打分。
4. **半诚实假设**：当前协议不防止主动作弊；NssMPClib 内有 VDPF/VSigma 但本项目未启用。

---

## License & 致谢

- 底层 MPC 库 [NssMPClib](https://github.com/XidianNSS/NssMPClib) (MIT, XDU NSS lab)
- bert-tiny 预训练权重 [prajjwal1/bert-tiny](https://huggingface.co/prajjwal1/bert-tiny)
