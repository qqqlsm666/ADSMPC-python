# ADSMPC-python · 加密 RAG 系统

> 基于 [NssMPClib](https://github.com/XidianNSS/NssMPClib)（西电 NSS 实验室）2PC 半诚实多方安全计算框架，实现的端到端加密 RAG 原型：**双路检索 → 密态 Top-K → 联合 BERT 推理 → 密态 Cross-Encoder Reranker → 密态抽取式 Reader**，并配套**密态 vs 明文**数值一致性 + 检索质量 + 答案抽取实验对比。

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
                │  ┌──────────────────────┐    │ 双路打分                   │   │
                │  │ db_embeddings [N,h]  │───►│ ├ 语义路: query·doc 内积  │   │
                │  │ bm25_matrix [V,N]    │───►│ └ 词汇路: BM25 简化打分   │   │
                │  │ db_tokens_oh [N,L,V] │    └────────────┬───────────────┘   │
                │  └──────────────────────┘                 ▼                  │
                │                            ┌────────────────────────────┐    │
                │                            │ [可选] 密态 PRF 扩展 query │    │
                │                            │ feedback_source ∈          │    │
                │                            │   {sem, lex, both}         │    │
                │                            │ 全程 ASS 域，无新 send/recv│    │
                │                            └────────────┬───────────────┘    │
                │                                          ▼                  │
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
                │                            └────────┬───────────────────┘    │
                │                                seq_out, pool                 │
                │                                     │                        │
                │              ┌──────────────────────┼──────────────────────┐ │
                │              ▼                      ▼                      ▼ │
                │  ┌──────────────────┐  ┌────────────────────┐  ┌──────────┐  │
                │  │ 密态 Reranker    │  │ 密态抽取式 Reader  │  │ pool     │  │
                │  │ pool @ db_embs.T │  │ pool · seq_out →   │  │ 诊断输出 │  │
                │  │ → rerank_scores  │  │ argmax → gather    │  └──────────┘  │
                │  └────────┬─────────┘  │ → answer_token_oh  │                │
                │           │            └─────────┬──────────┘                │
                │           │                      │                            │
                │           ▼                      ▼                            │
                │  ┌──────────────────────────────────────────┐                 │
                │  │ ⭐ 严格输出方向：三个 share 全部 send 给  │                 │
                │  │ Client，仅在 Client 端 restore           │                 │
                │  │ Server 不学习任何 query 相关信息          │                 │
                │  └──────────────────────────────────────────┘                 │
                │                                                              │
                └──────────────────────────────────────────────────────────────┘
```

详细架构、威胁模型、实验设计见：
- [docs/architecture.md](docs/architecture.md)
- [docs/threat_model.md](docs/threat_model.md)
- [docs/experiments.md](docs/experiments.md)

---

## 关键设计 / 创新点

| # | 阶段 | 内容 |
|---|---|---|
| 1 | 双路初次检索 | 语义路（密态内积）+ 词汇路（密态 BM25 简化打分），两路并行 |
| 2 | 密态 Top-K | O(N·K) 冒泡 + indicator swap，交换的是身份证向量而非 doc 本体 |
| 3 | 联合密态 BERT | [query, sem_doc, lex_doc] 串接成 56-token 序列做联合推理 |
| 4 | **密态 Cross-Encoder Reranker** | `pool @ db_embs.T` 密态 ASS@ASS matmul，把"装饰性"联合推理变成可解释精排 |
| 5 | **密态抽取式 Reader** | 启发式 head `(pool · seq_out).argmax`，密态 gather token 出来；query 段 + special token (PAD/CLS/SEP) mask 让答案落在文档实词上 |
| 6 | **严格输出方向（B3）** | rerank / pool / answer **三个 share 全部 send 给 client**，仅 client 端 restore；server 全程不学习客户端 query / 检索结果 / 答案 |
| 7 | **密态 PRF 实验**（实验中）| 第一轮 lex 检索 → 反馈源 doc 投影到 BM25 词表 → 加权扩展 query → 第二轮 lex 检索；全程 ASS 域无新 send/recv 同步点 |

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
│   ├── config.py                       ← BERT/RAG/PRF 超参与开关
│   ├── retrieval.py                    ← 双路打分 + Top-K + Reranker + Reader + PRF
│   ├── server.py                       ← Server 角色（party_id=0）
│   ├── client.py                       ← Client 角色（party_id=1）
│   ├── plaintext.py                    ← 明文 RAG（实验对照）
│   └── params.py                       ← 一次性生成全部辅助参数
│
├── experiments/                        ← 实验脚本与数据
│   ├── data/
│   │   └── mini_corpus.json            ← 50 query × 50 doc + ground truth + 候选答案
│   ├── data_loader.py                  ← 接入 HF tokenizer
│   ├── metrics.py                      ← Recall / Precision / NDCG / MRR + EM / PM / F1
│   ├── _rag_runner.py                  ← 子进程隔离启动器
│   ├── _cipher_worker.py               ← 子进程入口
│   ├── run_numerical_compare.py        ← 任务 A：单 query 数值一致性 + 答案对比
│   ├── run_retrieval_eval.py           ← 任务 B：N 条 query 检索质量 + EM/PM/F1
│   ├── run_main.py                     ← 整合入口
│   └── results/                        ← 实验输出（自动写）
│
├── docs/                               ← 项目文档
│   ├── architecture.md
│   ├── threat_model.md
│   └── experiments.md
│
├── 毕业论文/                           ← 论文相关
│   ├── 支持隐私保护的电子图书系统-论文.docx
│   ├── generate_thesis_full.py         ← 重新生成 docx 的脚本
│   └── thesis_full.md / thesis_part*.md
│
├── models/                             ← 预训练权重
│   └── bert_tiny_weights.pth           ← prajjwal1/bert-tiny (17 MB)
│
├── scripts/                            ← 编译脚本（torchcsprng 等）
│   ├── build_csprng_cpu.bat
│   └── dump_deps.bat
│
├── NssMPClib/                          ← 底层 MPC 库（本项目修过几个 bug，详见 SESSION_HANDOFF.md）
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

不装 torchcsprng 也能跑，会自动 fallback 到 `torch.Generator` 慢路径——但单条 query 从 ~80 秒变成 25-30 分钟。

---

## 快速启动

### 标准实验（毕设答辩）

```bash
# 必设 env
export DEVICE=cpu
export NSSMPC_GEN_NUM=10

# 任务 A 单条 query 数值一致性 + Reader 答案对比（约 80 秒）
python -m experiments.run_numerical_compare --query_idx 0

# 任务 B 多条 query 检索 + EM/PM/F1 评估（10 条约 13 分钟）
python -m experiments.run_retrieval_eval --num_queries 10 --num_docs 10

# 跳过参数生成（已生成过）
python -m experiments.run_retrieval_eval --num_queries 10 --skip_gen_params

# 全 50 条（约 60 分钟）
python -m experiments.run_retrieval_eval --num_queries 50

# 只跑明文 baseline（秒级）
python -m experiments.run_retrieval_eval --num_queries 50 --skip_cipher
```

### PRF 开关（在 `secure_rag/config.py`）

```python
PRF_ENABLED = True                     # False = 退化为单轮检索（B3 行为）
PRF_ALPHA = 0.7                        # 原始 query 权重
PRF_BETA = 0.3                         # 反馈 doc 权重
PRF_FEEDBACK_SOURCE = 'sem'            # 'sem' (跨路) / 'lex' (同路) / 'both' (聚合)
```

### 旧入口（兼容保留）

```bash
DEVICE=cpu NSSMPC_GEN_NUM=10 python NssMPClib/test/rag.py
```

---

## 实验结果

### 数值一致性（Query #0：`What is the capital of France?`）

| 指标 | 数值 | 含义 |
|---|---|---|
| Pool cosine_sim | **0.949** | 联合推理 [CLS] pooler 输出，定点数误差累积 |
| **Rerank cosine_sim** | **0.9998** ⭐ | 128 维内积求和把误差平均掉 — 论文亮点 |
| 单 query 端到端耗时 | **80-84 秒** | CPU + torchcsprng |
| 加密延迟代价 | ×1830-2040 | vs 明文 ~0.04 秒 |

### 检索质量（10 query × 10 doc，无 PRF / B3 baseline）

| 指标 | 明文 RAG | 密态 RAG |
|---|---|---|
| Recall@1 | 0.60 | **0.70** |
| Recall@5 | 0.70 | **1.00** |
| Precision@5 | 0.14 | **0.20** |
| NDCG@5 | 0.6631 | **0.8248** |
| MRR | 0.6500 | **0.7700** |

⭐ **密态指标普遍略优于明文**：定点数 LayerNorm/Softmax 查表近似的"小幅平滑"等价于隐式正则化。

### Reader 答案抽取

| 指标 | 明文 | 密态 |
|---|---|---|
| EM (严格) | 0.00 | 0.00 |
| Partial Match | 0.10 | 0.00 |
| Token F1 | 0.00 | 0.00 |

启发式 head（`pool · seq_out`）倾向于选通用词（is/city/asia/chambers），匹配不到专有名词答案（paris/beijing/tokyo）。Special token mask 起作用 — 不再选 [CLS]/[SEP]/[PAD]。提升空间在换 SQuAD 微调 head（未来工作）。

### PRF 消融实验（10 query）

| 配置 | 密态 R@1 | 密态 NDCG@5 | 密态 MRR |
|---|---|---|---|
| **B3 baseline (PRF off)** | **0.70** | **0.8248** | **0.7700** |
| PRF lex→lex (同路) | 0.60 | 0.7879 | 0.7200 |
| PRF sem→lex (跨路) | 0.50 | 0.7135 | 0.6233 |

**发现**：在含密态 cross-encoder reranker 的 RAG 架构中，PRF 失效。Reranker 主导最终排名（基于联合 BERT 的 pool），第一阶段 lex 路改变（包括 PRF 扩展）对最终 top-K 影响被平滑掉；密态侧反而引入 first-pass 近似误差污染。这是**有研究价值的 negative result**，论文可专章讨论。

### 性能拆解（单条 query ~80 秒）

| 阶段 | 耗时 | 占比 |
|---|---|---|
| 联合编码（Stage 7） | ~45 秒 | ~56% |
| 查询编码（Stage 3） | ~7 秒 | ~9% |
| 子进程启动 + 模型分享 | ~5 秒 | ~6% |
| 文档库分享 | ~1.5 秒 | ~2% |
| 双路打分 + Top-K + 取文档 | ~2.5 秒 | ~3% |
| Reranker matmul | ~0.5 秒 | ~0.6% |
| Reader (含 mask + argmax + gather) | ~1 秒 | ~1.2% |
| PRF 第二轮 lex（如启用） | +5 秒 | +6% |

通信：服务端 ~624 rounds / ~524 MB；客户端 ~389 rounds / ~319 MB。

### 关键瓶颈

联合编码的 Softmax + LayerNorm + GeLU 三个非线性算子占据联合编码 ~75%。Softmax 的 exp 查表 + LayerNorm 的 rsqrt（SigmaDICF 64 轮 prefix-parity）是协议级瓶颈，与 SIGMA / BumbleBee 论文结论一致。

---

## 已知限制

1. **Reader 是启发式 head，不是 SQuAD 微调**：bert-tiny 上效果有限，专有名词答案命中率低；论文里建议未来工作换微调 head。
2. **Top-K 是 O(N·K) 冒泡排序**：N=10 OK，N=1000+ 不实用，需要新的 MPC 友好近似 Top-K 算法。
3. **BM25 是预算化简化版**：所有非线性（idf 对数 + tf 比值）都被算到离线明文矩阵，密态侧只算稀疏点积；V=100 词表偏小。
4. **密态 PRF 在 reranker-dominated 架构下失效**：有 insight 但无正向 IR 提升；详见 `experiments/results/retrieval_eval_n10_b3_prf*.md`。
5. **半诚实假设**：当前协议不防止主动作弊；NssMPClib 内有 VDPF/VSigma 但本项目未启用。
6. **生成阶段是抽取式**：最终输出是 [V] one-hot 的 token id，不能产出多 token 自然语言段；扩展到 generative LLM 需要密态 sampling。

---

## License & 致谢

- 底层 MPC 库 [NssMPClib](https://github.com/XidianNSS/NssMPClib) (MIT, XDU NSS lab)
- bert-tiny 预训练权重 [prajjwal1/bert-tiny](https://huggingface.co/prajjwal1/bert-tiny)
- 协议参考：SIGMA (Secure GPT Inference, 2023)、BumbleBee、Iron、MPCFormer
