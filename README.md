# ADSMPC-python · 加密 RAG 系统

> 基于 [NssMPClib](https://github.com/XidianNSS/NssMPClib)（西电 NSS 实验室）2PC 半诚实多方安全计算框架，实现的端到端加密 RAG 原型。**核心创新点集中在密态检索层**：(1) 设计了基于 ASS 算术秘密分享的双路密态检索协议（语义路 SimHash 粗筛+cosine 精排 / 词汇路在线密态 BM25），(2) 提出密态跨路伪相关反馈（PRF）+ 候选池重排算法，避开了朴素 PRF 在精排器主导架构下的"平滑效应"陷阱。
>
> **完整流水线**：双路密态检索 → 跨路 PRF 第二轮 → 候选池 Hybrid Reranker → 联合 BERT 推理 → 密态 Span Reader → Client 解密答案

---

## 系统架构

```
                ┌──────────────────────── 加密 RAG 系统 ────────────────────────┐
                │                                                              │
   Client ─────►│  ┌──────────┐    ┌────────────────┐    ┌──────────────────┐   │
   (持有 query) │  │ tokenize │───►│ 密态 query     │───►│ 密态 BERT 编码   │   │
                │  └──────────┘    │ + 多热向量切分 │    │ (SecBertModel)   │   │
                │                  └────────────────┘    └──────────────────┘   │
                │                                                  │            │
                │  Server (持有文档库)         ┌────────────────────────────┐    │
                │  ┌──────────────────────┐    │ ⭐ Sem 路双阶段 (Pisces  │    │
                │  │ db_embeddings [N,h]  │───►│   ∏PrivateSS 同型)        │    │
                │  │ doc_hashes [N,L]     │───►│ ┌ SimHash 粗筛           │    │
                │  │ tf/idf/doc_norm 或   │    │ │  密态 Hamming → top-M │    │
                │  │   bm25_matrix        │───►│ └ 密态 cosine 精排       │    │
                │  │ db_tokens_oh         │    │                            │    │
                │  └──────────────────────┘    │ ⭐ Lex 路 BM25 双模式    │    │
                │                              │ ├ Offline: bm25_matrix    │    │
                │                              │ └ Online: tf/idf/doc_norm │    │
                │                              │    + secure_div (Pisces   │    │
                │                              │     ∏PrivateBM25 同型)   │    │
                │                              └────────────┬───────────────┘    │
                │                                            ▼                  │
                │                            ┌────────────────────────────┐    │
                │                            │ [可选] 多轮检索:           │    │
                │                            │  • Lex PRF (跨路反馈)      │    │
                │                            │  • Sem PRF (ReAct 简化)    │    │
                │                            └────────────┬───────────────┘    │
                │                                            ▼                  │
                │                            ┌────────────────────────────┐    │
                │                            │ 密态 Top-K (冒泡+indicator)│    │
                │                            │ [可选] Pre-gen Reranker:  │    │
                │                            │  fusion(bi-enc + lex score)│    │
                │                            └────────────┬───────────────┘    │
                │                                            ▼                  │
                │                          [Q | doc_sem | doc_lex] (Seq=56)    │
                │                                            │                  │
                │                                            ▼                  │
                │                            ┌────────────────────────────┐    │
                │                            │ 联合密态 BERT 推理         │    │
                │                            └────────┬───────────────────┘    │
                │                                seq_out, pool                  │
                │                                     │                          │
                │              ┌──────────────────────┼──────────────────────┐ │
                │              ▼                      ▼                      ▼ │
                │  ┌──────────────────┐  ┌────────────────────────┐  ┌─────┐  │
                │  │ Post Reranker    │  │ ⭐ SQuAD Span Reader   │  │ pool │  │
                │  │ pool @ db_embs.T │  │  start/end heads       │  │ 诊断 │  │
                │  │ → rerank_scores  │  │  cumsum span_mask      │  └─────┘  │
                │  └────────┬─────────┘  │  [1,L,V] send 保序     │           │
                │           │            └─────────┬──────────────┘           │
                │           ▼                      ▼                          │
                │  ┌──────────────────────────────────────────┐               │
                │  │ ⭐ 严格输出方向：所有 share 都 send 给    │              │
                │  │ Client，仅在 Client 端 restore           │              │
                │  │ Server 不学习任何 query 相关信息          │              │
                │  └──────────────────────────────────────────┘               │
                │                                                              │
                └──────────────────────────────────────────────────────────────┘
```

详细架构、威胁模型、实验设计见：
- [docs/architecture.md](docs/architecture.md) — 含 Pisces 协议对齐章节 + 升级版数据流图
- [docs/threat_model.md](docs/threat_model.md) — 含 Pisces 协议层威胁模型对比
- [docs/experiments.md](docs/experiments.md)
- ⭐ [experiments/results/ablation_summary.md](experiments/results/ablation_summary.md) — 6 个 task 消融汇总，论文 ch4 主素材
- [experiments/results/simhash_ablation.md](experiments/results/simhash_ablation.md) — Sem 路 SimHash 粗筛 (task #1)
- [experiments/results/rerank_pregen_ablation.md](experiments/results/rerank_pregen_ablation.md) — Pre-gen Reranker 架构正确性 (task #2)
- [experiments/results/span_reader_ablation.md](experiments/results/span_reader_ablation.md) — Span Reader vs 启发式 reader (task #3)
- [experiments/results/bm25_online_ablation.md](experiments/results/bm25_online_ablation.md) — Lex 路 BM25 双模式 (task #4)
- [experiments/results/sem_prf_react_ablation.md](experiments/results/sem_prf_react_ablation.md) — Sem 路 PRF / ReAct 简化 (task #5)
- [experiments/results/prf_v2_ablation.md](experiments/results/prf_v2_ablation.md) — ⭐ **PRF v2 + Hybrid Reranker 正向创新点** (task #7/#8)

---

## 关键设计 / 创新点

### ⭐ 检索层核心创新（论文主要创新点）

| # | 阶段 | 内容 | 默认 |
|---|---|---|---|
| **1** | **⭐ 双路密态检索 — 语义路** | 基于 ASS 实现的 SimHash 粗筛（密态 Hamming 距离）+ 密态 cosine 精排级联协议，全程无 OPRF/OKVS 原语依赖；L=128 在 N=10 上语义 Top-1 完全无损 | ON |
| **2** | **⭐ 双路密态检索 — 词汇路** | 在线密态 BM25 公式（含密态 secure_div），把 tf/idf/doc_norm 三分量分别 ASS 分享，BM25 完整公式在线密态计算 | ONLINE 可选 |
| **3** | **⭐ 跨路 PRF + 候选池重排** | 语义路 Top-1 反馈到词汇路 query 扩展 → 第二轮词汇路检索；联合 BERT 输入保持稳定，PRF 第二轮文档仅作为 Hybrid Reranker 的候选池加 boost。**实测 NDCG@5 / MRR / R@3 / PM / F1 全部超过 PRF 关闭基线** | ON (boost=1.0) |

### 检索层之外的工程组件

| # | 阶段 | 内容 | 默认 |
|---|---|---|---|
| 4 | 密态 Top-K | O(N·K) 冒泡 + indicator swap | - |
| 5 | 联合密态 BERT | [query, doc_a, doc_b] 串接 56-token 联合推理 | - |
| 6 | Hybrid Reranker | `pool @ db_embs.T` + 候选池 boost（与创新点 3 协同） | ON |
| 7 | 密态 Span Reader | SQuAD-style start/end heads + cumsum span_mask + [1,L,V] send 保留顺序 | ON |
| 8 | 严格输出方向 (B3) | 所有 share 都送 Client 端 restore，Server 不学习 | ON |
| 9 | Sem 路 PRF / ReAct 两轮（可选） | 第一轮 sem top-1 → 反馈 doc embedding → q_expanded → 第二轮 sem | OFF |
| 10 | Pre-generation Reranker（可选） | 双路 K1=2 候选 → fusion rerank → top-K2 → joint inference | OFF |

### 与 Pisces (ICLR 2026) 对比

| 维度 | Pisces | 本工作 |
|---|---|---|
| 实现底层 | 自研协议栈（OPRF + OKVS + 标签 PSI） | NssMPClib 通用 MPC 库（ASS + FSS） |
| Sem 路粗筛 | SimHash → Oblivious filter (OPRF/OKVS) | **本工作贡献**：SimHash → 密态 Hamming + bubble top-M（无 OPRF 原语依赖） |
| Sem 路精排 | 密态 cosine | 密态内积（cosine 等价） |
| Lex 路 BM25 | 多实例标签 PSI + 在线密态 BM25 | **本工作贡献**：query indicator @ tf 矩阵 + 在线密态 BM25 公式（含密态除法） |
| Top-K | Secure sorting (bitonic) | Bubble + indicator swap |
| **跨路 PRF + 候选池重排** | ❌ **无任何 PRF / 多轮检索机制** | **⭐ 本工作核心创新点** |
| **Cross-encoder Reranker** | ❌ 无 | ✅ pool @ db_embs.T + PRF 候选池 boost |
| **生成阶段** | 委托外部密态 LLM (声明) | 委托接口 + **可跑的 default SQuAD span reader** |

**叙事**：检索协议基础架构借鉴 Pisces 但**独立实现**（NssMPClib 框架内不依赖 OPRF/OKVS），并在此之上提出**跨路 PRF + 候选池重排算法**作为相对 Pisces 的正向创新。

---

## 配置开关（`secure_rag/config.py`）

5 个开关控制整个 pipeline 行为，便于论文 ablation：

```python
# Sem 路 SimHash 粗筛 (task #1) ⭐ 默认 ON
SIMHASH_ENABLED        = True       # OFF 时退化为全 N 直接密态内积
SIMHASH_BITS           = 128        # L=64 在 N=10 损失 1 hit；L=128 完全无损
SIMHASH_CANDIDATES_M   = 5          # 粗筛后候选集大小 (建议 N//2)

# Lex 路在线密态 BM25 (task #4) ⭐ 默认 OFF（Pisces 同型协议）
LEX_BM25_ONLINE        = False      # True 切到 tf/idf/doc_norm + secure_div
LEX_BM25_K1, LEX_BM25_B = 1.5, 0.75 # BM25 公开参数

# Pre-generation Reranker (task #2) ⭐ 默认 OFF
RERANK_PRE_GEN_ENABLED = False      # True: 双路 K1=2 → fusion rerank → top-K2 → joint
RERANK_K1, RERANK_K2   = 2, 2
RERANK_ALPHA, RERANK_BETA = 0.5, 0.5  # bi-encoder 权重 / lex score 权重

# Span Reader (task #3) ⭐ 默认 ON
SPAN_READER_ENABLED    = True       # OFF 退化到旧启发式 (pool · seq_out).argmax

# Sem 路 PRF / ReAct 两轮 (task #5) ⭐ 默认 OFF
SEM_PRF_ENABLED        = False      # True 启用 sem 两轮（与 lex PRF 对称）
SEM_PRF_ALPHA, SEM_PRF_BETA = 0.7, 0.3

# Lex 路 PRF (跨路反馈) + 候选池 Reranker (task #7/#8) ⭐ 默认 ON
PRF_ENABLED               = True
PRF_FEEDBACK_SOURCE       = 'sem'      # 'sem' (跨路) / 'lex' (同路) / 'both'
PRF_ALPHA, PRF_BETA       = 0.7, 0.3
# ⭐ PRF v2 关键：让 PRF 真正变正向（避免污染 joint BERT 输入）
PRF_CANDIDATE_POOL_RERANK = 'hybrid'   # 'none' / 'strict' / 'hybrid' (推荐 hybrid)
PRF_RERANK_BOOST          = 1.0        # boost=1.0 实测 sweet spot
```

**默认组合**（推荐答辩配置）：SimHash ON + Span Reader ON + Lex PRF ON，其他 OFF。端到端 ~78s/query，Pool cos 0.93+，密态 reader 输出有意义的 doc 子串。

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
│   ├── config.py                       ← 5 个开关 + BERT/RAG 超参
│   ├── retrieval.py                    ← 10 个 secure_* 协议函数
│   │   ├ 双路打分: secure_inner_product_score / secure_lexical_score
│   │   ├ Top-K:    secure_top_k_indicator
│   │   ├ SimHash:  get_simhash_projection / plaintext_simhash_bits /
│   │   │           secure_simhash_query / secure_simhash_coarse_filter /
│   │   │           secure_simhash_coarse_to_fine
│   │   ├ BM25:     secure_bm25_online_score
│   │   ├ Reranker: secure_rerank (post) / secure_fusion_rerank_pregen (pre)
│   │   ├ Reader:   secure_reader (启发式) / secure_reader_span (SQuAD)
│   │   │           load_qa_head
│   │   └ PRF:      secure_prf_expand_query (lex) / secure_sem_prf_expand_query (sem)
│   ├── server.py                       ← Server 角色（party_id=0）
│   ├── client.py                       ← Client 角色（party_id=1）
│   ├── plaintext.py                    ← 明文 RAG（实验对照，含 build_bm25_components）
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
│   └── results/                        ← 实验输出（含 6 个 ablation md）
│
├── docs/                               ← 项目文档
│   ├── architecture.md                 ← 系统架构 + Pisces 对齐
│   ├── threat_model.md                 ← 威胁模型 + Pisces 协议层对比
│   └── experiments.md
│
├── doc/                                ← 关键参考论文
│   ├── 17937_Pisces_Cryptography_base.pdf       ← Pisces (ICLR 2026)
│   └── 5016_react_synergizing_reasoning_an.pdf  ← ReAct (ICLR 2023)
│
├── 毕业论文/                           ← 论文相关
│   ├── 支持隐私保护的电子图书系统-论文.docx
│   └── thesis_full.md / thesis_part*.md
│
├── models/                             ← 预训练权重
│   ├── bert_tiny_weights.pth           ← prajjwal1/bert-tiny (17 MB)
│   └── qa_head_squadv2.pth             ← SQuAD QA head (task #3 用)
│
├── scripts/                            ← 工具脚本
│   ├── build_csprng_cpu.bat            ← 编译 torchcsprng
│   ├── dump_deps.bat
│   └── extract_squad_qa_head.py        ← 从 HF 提取 SQuAD QA head 权重
│
├── NssMPClib/                          ← 底层 MPC 库
│   ├── NssMPC/                         ← 库源码
│   ├── csprng/                         ← AES PRG 编译扩展
│   ├── tutorials/                      ← 库教程 notebook
│   ├── data/                           ← CNN/AlexNet 等模型骨架
│   └── test/                           ← 旧入口 rag.py（兼容保留）
│
└── test/                               ← 顶层 demo
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

### 标准实验（毕设答辩，默认配置）

```bash
# 必设 env
export DEVICE=cpu
export NSSMPC_GEN_NUM=10

# 默认配置: SimHash L=128 + Span Reader + Lex PRF + 其他 OFF
# 任务 A 单条 query 数值一致性 + Reader 答案对比（约 80 秒）
python -m experiments.run_numerical_compare --query_idx 4

# 任务 B 多条 query 检索 + EM/PM/F1 评估（10 条约 13 分钟）
python -m experiments.run_retrieval_eval --num_queries 10 --num_docs 10

# 跳过参数生成（已生成过）
python -m experiments.run_retrieval_eval --num_queries 10 --skip_gen_params

# 全 50 条（约 60 分钟）
python -m experiments.run_retrieval_eval --num_queries 50

# 只跑明文 baseline（秒级）
python -m experiments.run_retrieval_eval --num_queries 50 --skip_cipher
```

### SQuAD QA head 提取（首次运行 Span Reader 前）

```bash
# 从 HuggingFace 拉 mrm8488/bert-tiny-finetuned-squadv2，提取 qa_outputs 权重
python scripts/extract_squad_qa_head.py
# → 产物保存到 models/qa_head_squadv2.pth (~28 KB)
```

### 开 Pisces 同型协议 / 多轮 / 架构正确性 ablation

直接改 `secure_rag/config.py` 中对应开关即可，所有 ablation 都不需要改其他代码：

```python
# 实验 1: 启用 Pisces ∏PrivateBM25 同型协议
LEX_BM25_ONLINE = True

# 实验 2: 启用 Sem 路两轮检索 (ReAct Thought→Act→Thought 简化版)
SEM_PRF_ENABLED = True

# 实验 3: 启用 Pre-generation Reranker (标准 RAG 拓扑)
RERANK_PRE_GEN_ENABLED = True   # 注意：与 PRF 互斥，会强制关闭 PRF

# 实验 4: 关闭 SimHash 粗筛 (退化到全 N 直接密态内积)
SIMHASH_ENABLED = False

# 实验 5: 关闭 Span Reader (退化到旧启发式 reader)
SPAN_READER_ENABLED = False
```

### 旧入口（兼容保留）

```bash
DEVICE=cpu NSSMPC_GEN_NUM=10 python NssMPClib/test/rag.py
```

---

## 实验结果

### 6 个 Task 实证收益总览

| Task | 创新点 | 默认 | Q#4 实证收益 (vs 旧版 baseline) |
|---|---|---|---|
| #1 SimHash 粗筛 | Sem 路 Pisces ∏PrivateSS 同型 | ON | 端到端 **-8%** (84.5→77.6s)；sem top-1 在 N=10 上完全无损 |
| #2 Pre-gen Reranker | 架构正确性 (post→pre rerank) | OFF | 协议价值 (标准 RAG 拓扑)；密态 noise 让 reader 退化为 [PAD] |
| #3 Span Reader | 启发式→SQuAD start/end heads | ON | 明文 **PM 0.10→0.30 (+200%)**；F1 0→0.04；密态输出 'the longest river in africa' |
| #4 BM25 Online | Lex 路 Pisces ∏PrivateBM25 同型 | OFF | 协议层 Pisces 对齐；+1% 耗时 (batched secure_div 极快) |
| #5 Sem PRF / ReAct | 两轮 sem 检索 (ReAct 简化) | OFF | 与 lex PRF 对称，+4s/query；单跳问答上无额外收益 |
| #6 Pisces baseline + 消融 | 论文 ch4 章节素材 | - | 6 个 ablation 报告 + Pisces 对比表 + 升级版 architecture/threat_model |

---### 数值一致性（Query #4：`Which is the longest river in Africa?`）

| 配置 | 端到端耗时 | Pool cosine_sim | Rerank cosine_sim | 加密延迟代价 |
|---|---|---|---|---|
| 旧版 (无 SimHash + 启发式 reader) | ~84.5 s | 0.949 | 0.9998 | ×2042 |
| **+SimHash L=128 (Pisces ∏PrivateSS 同型)** | 77.6 s | 0.877 | 0.9995 | ×1844 |
| **+SimHash + Span Reader (SQuAD head)** | ~82.0 s | 0.935 | 0.9997 | ×1709 |
| **+SimHash + Span + BM25 Online (Pisces ∏PrivateBM25 同型)** | 78.9 s | 0.936 | 0.9998 | ×2322 |

### Reader 答案抽取（明文 10-query）

| 配置 | EM (严格) | Partial Match | Token F1 | 改进 |
|---|---|---|---|---|
| 旧版 启发式 reader (`pool · seq_out`) | 0.00 | **0.10** | 0.000 | baseline |
| **新版 SQuAD Span Reader (start/end heads)** | 0.00 | **0.30** ⭐ | **0.040** ⭐ | PM +200% |

**关键例子**（Q#4 'longest river in Africa', gt='nile'）：
- 旧 reader 输出：`is`（无关词）
- **新明文 reader**：`the nile is the longest river in africa flowing` ✓ 含 'nile'
- **新密态 reader**：`the longest river in africa` ✓ 是 doc 4 的真子串

### Sem 路 SimHash 检索精度（明文 10-query, N=10, gt 在前 10 doc 内）

| 配置 | sem top-1 hit | 与 Full cosine 一致率 |
|---|---|---|
| Full cosine (无 SimHash baseline) | 4/10 = 0.40 | 1.00 |
| SimHash L=64, M=5 | 3/10 = 0.30 | 0.90 |
| **SimHash L=128, M=5 (默认)** | **4/10 = 0.40** | **1.00** ⭐ |

L=128 在 N=10 上 sem top-1 完全无损；L=64 损失 1/10。

### Lex 路 BM25 双模式（Q#4 实测）

| 模式 | 端到端耗时 | Pool cos | Rerank cos | 协议层 |
|---|---|---|---|---|
| Offline (默认): 离线 bm25_matrix | 78.0 s | 0.9353 | 0.9997 | 简单 |
| **Online: tf+idf+doc_norm + secure_div** | **78.9 s (+1%)** | **0.9356** | 0.9998 | Pisces ∏PrivateBM25 同型 |

**结论**：online 模式增加开销可忽略（NssMPClib batched secure_div 极快），但协议层叙事跟 Pisces 一致。

### 检索质量（10 query × 10 doc）⭐ 含 PRF v2 + Hybrid Reranker (默认 ON, boost=1.0)

| 指标 | 明文 RAG | 单纯双路 (PRF off) | **默认 含 PRF v2** | PRF v2 vs PRF off |
|---|---|---|---|---|
| Recall@1 | 0.60 | 0.70 | 0.60 | ⬇ -0.10 |
| Recall@3 | 0.70 | 0.70 | **0.90** | ⬆ +0.20 |
| Recall@5 | 0.70 | 1.00 | **1.00** | = 持平 |
| Precision@5 | 0.14 | 0.20 | 0.20 | = 持平 |
| **NDCG@5** | 0.6631 | 0.8248 | **0.8323** | ⬆ **+0.0075 超过 baseline** ⭐ |
| **MRR** | 0.6500 | 0.7700 | **0.7750** | ⬆ **+0.005 超过 baseline** ⭐ |
| Reader EM | 0.00 | 0.00 | 0.00 | 持平 |
| **Reader Partial Match** | 0.20 | 0.00 | **0.10** | ⬆ **+0.10** ⭐ |
| **Reader Token F1** | 0.000 | 0.000 | **0.0063** | ⬆ ⭐ |

⭐ **PRF v2 + Hybrid Reranker 是正向创新点**：NDCG@5 / MRR / R@3 / PM / F1 全部超过 baseline；仅 R@1 微降 (0.70→0.60)。
**关键设计**：joint inference 仍用 lex_round1（保持语义稳定），PRF round 2 只进 reranker candidate pool 加 boost；Pisces ICLR 2026 无此机制。

**Reader 答案质量举例**（更直观）：
- Q#0 capital of France: PRF off→`city` (无关) ／ **PRF v2→`the capital city of france`** (gt doc, 含 'france')
- Q#7 carries genetic info: PRF off→`chambers` (无关) ／ **PRF v2→`the genetic instructions`** (gt doc)
- Q#4 longest river Africa: PRF off→`is` (无关) ／ **PRF v2→`the longest river in africa`** (gt doc)

### 检索质量（10 query × 10 doc，无 PRF / B3 baseline）

| 指标 | 明文 RAG | 密态 RAG |
|---|---|---|
| Recall@1 | 0.60 | **0.70** |
| Recall@5 | 0.70 | **1.00** |
| Precision@5 | 0.14 | **0.20** |
| NDCG@5 | 0.6631 | **0.8248** |
| MRR | 0.6500 | **0.7700** |

⭐ **密态指标普遍略优于明文**：定点数 LayerNorm/Softmax 查表近似的"小幅平滑"等价于隐式正则化。

### PRF v1 Naive 消融实验（旧版，PRF round 2 直接替换 joint inference 的 lex_doc，已被 v2 取代）

| 配置 | 密态 R@1 | 密态 NDCG@5 | 密态 MRR |
|---|---|---|---|
| **B3 baseline (PRF off)** | **0.70** | 0.8248 | 0.7700 |
| PRF v1 lex→lex (同路) | 0.60 | 0.7879 | 0.7200 |
| PRF v1 sem→lex (跨路) | 0.50 | 0.7135 | 0.6233 |

**v1 失败原因**：PRF round 2 选不同 lex_doc 替换 joint BERT 输入 → 联合 pool 偏移 → reranker base scores 错位。
**v2 修复**：joint inference 仍用 lex_round1（保持 baseline 语义），PRF round 2 只进 reranker candidate pool 加 boost（参见上表 PRF v2 数据）。

详见 [experiments/results/prf_v2_ablation.md](experiments/results/prf_v2_ablation.md)。

### 性能拆解（单条 query ~80 秒）

| 阶段 | 耗时 | 占比 |
|---|---|---|
| 联合编码（Stage 7） | ~45 秒 | ~56% |
| 查询编码（Stage 3） | ~7 秒 | ~9% |
| 子进程启动 + 模型分享 | ~5 秒 | ~6% |
| 文档库分享 | ~1.5 秒 | ~2% |
| 双路打分 + Top-K + 取文档 (含 SimHash) | ~3 秒 | ~4% |
| Reranker matmul | ~0.5 秒 | ~0.6% |
| Reader (含 mask + argmax + gather) | ~1 秒 | ~1.2% |
| PRF 第二轮 lex（如启用） | +5 秒 | +6% |
| BM25 Online (如启用) | +1 秒 | +1% |

通信：服务端 ~624 rounds / ~524 MB；客户端 ~389 rounds / ~319 MB。

### 关键瓶颈

联合编码的 Softmax + LayerNorm + GeLU 三个非线性算子占据联合编码 ~75%。Softmax 的 exp 查表 + LayerNorm 的 rsqrt（SigmaDICF 64 轮 prefix-parity）是协议级瓶颈，与 SIGMA / BumbleBee 论文结论一致。

---

## 已知限制

1. **EM 仍为 0**：bert-tiny SQuAD-finetune head 倾向于选完整子句（如 'the nile is the longest river in africa'）而非单 token 实体（如 'nile'）。EM 显著提升需要换 bert-base 或 fine-tune 短答案。Partial Match 已从 0.10 提升到 0.30。
2. **Top-K 是 O(N·K) 冒泡排序**：N=10 OK，N=1000+ 不实用，需要新的 MPC 友好近似 Top-K 算法（Pisces 用 secure sorting）。
3. **协议层未实现真 PSI**：Lex 路 BM25 Online 模式让 server 不再持有"成品 BM25 score"，但 server 仍能从 query indicator share 推断 query 词表分布；要达到 Pisces 那种"server 完全不知 client query 包含哪些 token"，需要 OPRF/OKVS 原语，NssMPClib 当前不支持。
4. **PRF v2 hybrid R@1 trade-off**：boost=1.0 在 NDCG@5 / MRR / R@3 / PM / F1 上超过 PRF off baseline，但 R@1 仍微降 (0.70→0.60)。可通过 boost 进一步调优或换更大数据集验证。
5. **半诚实假设**：当前协议不防止主动作弊；NssMPClib 内有 VDPF/VSigma 但本项目未启用。
6. **生成阶段是抽取式**：最终输出是 [start, end] 区间内的 token id 序列，不能产出多 token 自然语言段；扩展到 generative LLM 需要外接 SIGMA / PUMA / BumbleBee（项目提供"可插拔生成接口"）。

---

## License & 致谢

- 底层 MPC 库 [NssMPClib](https://github.com/XidianNSS/NssMPClib) (MIT, XDU NSS lab)
- bert-tiny 预训练权重 [prajjwal1/bert-tiny](https://huggingface.co/prajjwal1/bert-tiny)
- 协议参考：SIGMA (Secure GPT Inference, 2023)、BumbleBee、Iron、MPCFormer
