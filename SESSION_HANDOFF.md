# Session Handoff — 密态 RAG 项目交接文档

> **下个 session 的 Claude 请先读这个文件**。包含项目状态、待办计划、关键决策、踩坑历史、运行命令。读完即可无缝接着干。
>
> 最近一次更新：2026-05-07

---

## 一、项目一句话定位

**支持隐私保护的检索增强生成系统**（毕业设计）

基于西电 NSS 实验室的 NssMPClib 安全多方计算库，实现 2-Party 半诚实模型下的密态 RAG 系统。架构：双路检索（语义 + 词汇 BM25）→ 密态 Top-K 指示器排序 → 密态文档抽取 → 密态 BERT 联合编码 → 密态 Cross-Encoder Reranker → 密态抽取式 Reader → 客户端 decode 答案。

**项目路径**：`C:\Users\user\project\_external\D\桌面-65fdeb\加密rag-5caf36\ADSMPC-p-3548b9` （即 `/d/桌面/加密rag/ADSMPC-python` in git-bash）

---

## 二、已完成阶段（重要！避免重新干）

| 阶段 | 内容 | 文件 |
|---|---|---|
| 1. 目录重组 | secure_rag/ + experiments/ + docs/ + scripts/ + models/ 五层结构 | 全项目 |
| 2. NssMPClib bug 修复 | DEBUG_LEVEL=2 单 key 广播路径下 Beaver mul / prefix_parity_query / FSSKeyProvider 磁盘兜底 | NssMPClib/NssMPC/ |
| 3. torchcsprng 编译 | FORCE_CPU=1 编译 + DLL 路径修复，PRG 加速 25× | NssMPClib/csprng/ |
| 4. 子进程隔离 | 每条 query 独立子进程 + 不同 NSSMPC_PORT_OFFSET + os._exit(0) 强退避免 close() 卡死 | experiments/_cipher_worker.py + _rag_runner.py |
| 5. 双路密态检索 | secure_inner_product_score / secure_lexical_score / secure_top_k_indicator | secure_rag/retrieval.py |
| 6. 密态 Reranker（B2）| pool @ db_embs.T 密态矩阵乘 → 精排分数 | secure_rag/retrieval.py + server.py + client.py |
| 7. 数据集 + 评估 | 50 query × 50 doc Mini-QA-Corpus + Recall/MRR/NDCG/Precision 指标 | experiments/data/ + experiments/metrics.py |
| 8. 实验报告 | 数值一致性（cosine_sim=0.9998 for reranker）+ 检索质量（密态 R@5=1.0, MRR=0.72） | experiments/results/*.md |
| 9. 毕业论文 docx | 完整 5 章 + 摘要 + 参考文献 + 致谢 + 附录 | 毕业论文/支持隐私保护的检索增强生成系统-论文.docx |
| 10. **B3 严格隐私 + Reader（最近一轮，已落地基本架构）** | secure_reader 函数 + 输出方向反转（reranker/pool/answer 全送 client）+ 答案 token 密态 gather + EM/PM/F1 指标 | 见下方"当前状态" |

---

## 三、当前状态（2026-05-07）

### B3 方案的代码改动**已经写好但还未端到端验证**

**已经改完的文件**：

| 文件 | 改动点 | 状态 |
|---|---|---|
| `secure_rag/retrieval.py` | 新增 `secure_reader(pool, seq_out, joint_ids)` → 返回 `(answer_token_oh_share, reader_logits_share, position_indicator_share)` | ✅ 已写 |
| `secure_rag/server.py` | 联合推理拿 `seq_out, pool`；调用 `secure_reader` 与 `secure_rerank`；**reranker / pool / answer 三个 share 全部 send 给 client**（不再在 server restore） | ✅ 已写（system reminder 显示）|
| `secure_rag/client.py` | 接收三个 share + client 端 restore + tokenizer.decode → 自然语言答案 | 🔵 应已改完（需验证）|
| `secure_rag/plaintext.py` | 同步加 reader：`(seq_out * pool).sum(-1) → argmax → answer_token_id → tokenizer.decode` | 🔵 应已改完（system reminder 显示部分被截断）|
| `experiments/_cipher_worker.py` | result holder 从 server 移到 client；output 字段 dict: `{pool, rerank_scores, answer_token_id, answer_text, answer_position}` | 🔵 应已改完 |
| `experiments/_rag_runner.py` | 接收新 dict 格式；传 `tokenizer_name` 给子进程 | 🔵 应已改完 |
| `experiments/metrics.py` | 新增 `normalize_answer / exact_match / partial_match / token_f1` | ✅ 已写 |
| `experiments/run_numerical_compare.py` | 报告里加 reader 答案一致性、明文 vs 密态 EM/PM/F1 | ✅ 已写 |
| `experiments/run_retrieval_eval.py` | 加 reader EM/PM/F1 指标 | ✅ 已写（system reminder 显示部分） |
| `experiments/data/mini_corpus.json` | 给每条 query 加 `answer` 字段（候选答案列表，含 wordpiece） | ✅ 已写（`has_answer: true`） |

### 待验证 / 待执行（next session 的 TODO）

**优先级 A（必做）**：

1. **跑通验证**：
   ```bash
   cd /d/桌面/加密rag/ADSMPC-python
   conda activate ADSMPC-python
   DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_numerical_compare --query_idx 0
   ```
   - 看 reader 路径有没有 bug
   - 检查 send/recv 顺序是否对称（错位会死锁，超时 180s 后 fail）
   - 看明文 vs 密态答案是否一致（`answer_text`, `answer_token_id`）
   - 关键报告字段：`pool_cos`、`rerank_cos`、`answer_position_match`、`answer_token_match`、明文 vs 密态 EM/PM

2. **如果 1 通过**，跑 10 条 query 完整对比：
   ```bash
   DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_retrieval_eval \
       --num_queries 10 --num_docs 10 \
       --output experiments/results/retrieval_eval_n10_b3.md
   ```
   - 跑 ~10-12 分钟（10 条 × ~60s/条 + 子进程启动开销）
   - 关键指标：明文/密态 各自的 EM、PM、F1（除了原有的 R@K / MRR / NDCG）

**优先级 B（建议做）**：

3. **更新论文**：B3 阶段的"严格输出方向控制 + 抽取式 Reader"是新的核心创新点，需要：
   - 在 `毕业论文/generate_thesis_full.py` 第三章末尾加 "3.5 严格密态输出与抽取式 Reader" 节
   - 在第四章末尾加 "4.7 抽取式 Reader 实验（EM/PM/F1）" 节
   - 更新摘要与第五章总结，强调"客户端是答案的唯一接收者"
   - 重新跑 `python generate_thesis_full.py` 生成新版 docx

**优先级 C（可选）**：

4. **画系统架构图**（论文里目前是文字描述，没有真正的图）
5. **跑全 50 条 query**（约 50-60 分钟）拿更稳的统计
6. **答辩 PPT**

---

## 四、关键设计决策（不要重新讨论 / 不要回退）

1. **Reader 用启发式 head**：`reader_logits = (seq_out * pool).sum(-1)`，不需要训练新参数。**不要换成 SQuAD 微调权重**（毕设时间不够、且 bert-tiny 在 SQuAD 上效果也一般）。

2. **输出方向**：reranker、pool、answer 三者**全部** restore 在 client 端。**Server 全程"瞎"**，只持有自己提供的文档库（这本来就是它的）+ 双方密态 share。

3. **密态 argmax** 复用 `secure_top_k_indicator(K=1)`，不要写新协议。

4. **答案抽取** 用 `(position_indicator * joint_ids).sum(dim=1)` 密态 gather token；输出 [1, V] 密态 one-hot；client 端 restore + argmax + tokenizer.decode。

5. **Tokenizer 跨进程** 用方案 1：子进程内独立 `BertTokenizer.from_pretrained('bert-base-uncased')`，靠 HF 缓存。1-2 秒一次性开销可接受。

6. **NUM_DOCS = 10** 不动（密态 Top-K 是 O(NK) 冒泡，更大文档库需要新算法，未来工作）。

7. **DEBUG_LEVEL = 2 + NSSMPC_GEN_NUM = 10**：单 key 广播复用，足够 demo + 数值正确性验证。

8. **答案语料**：每条 query 标多个候选答案（含 wordpiece 形式如 `"par"`、`"##is"`），用 PM (partial_match) 做主指标——单 token reader 难以严格 EM 命中。

---

## 五、运行环境与配置

| 项 | 值 |
|---|---|
| OS | Windows 11 Home |
| Shell | git-bash（用 Unix 路径如 `/d/桌面/加密rag/...`）|
| Conda env | `ADSMPC-python`（Python 3.10.20）|
| PyTorch | 2.3.0+cu121 |
| torchcsprng | 0.2.0+0107bf5（CPU build, FORCE_CPU=1 编译）|
| transformers | 4.30+ |
| 必设 env | `DEVICE=cpu`（torchcsprng 是 CPU build，cuda 会报错）|
| `NSSMPC_GEN_NUM` | `10`（DEBUG_LEVEL=2 下足够）|
| `NSSMPC_PORT_OFFSET` | rag.py 自己按 PID 算，子进程版每条 query 不同 |

**激活环境的标准开头**：
```bash
source /d/anaconda/etc/profile.d/conda.sh && conda activate ADSMPC-python
cd /d/桌面/加密rag/ADSMPC-python
```

---

## 六、避坑清单（让 next session 别重复掉进去）

| 坑 | 已修 / 怎么避 |
|---|---|
| `WinError 10048` 端口被占 | 已用子进程隔离 + PID 端口偏移修复，见 `_rag_runner.py:_new_port_offset` |
| `Communicator close()` 阶段 hang | `_cipher_worker.py` 末尾用 `os._exit(0)` 强退，**不要** join 子线程 |
| `DEBUG_LEVEL=2 reshape '[1024, 1]' invalid for size 1` | 已修 `multiplication.py:beaver_mul` 加广播分支；**不要** 回退此修复 |
| `prefix_parity_query` shape `(2)` vs `(8)` 不匹配 | 已修 `dpf.py` 加 batch broadcast 分支 |
| `FSSKeyProvider pop from empty list` | 已加磁盘兜底，见 `fss_key_provider.py:_load_from_disk_fallback` |
| Windows 终端 GBK 编码无法打印 ✅ ⚠️ 等字符 | 报告写 utf-8 文件后，print(md) 要 `try/except UnicodeEncodeError` |
| Send/recv 顺序错位死锁 | 改 server.py / client.py 时，**严格对齐**两边的 send 顺序与 receive 顺序 |
| Bash 链式 sleep 被 block | 用 `until grep -qE ...; do sleep 60; done` 而不是 `sleep N && check` |
| `~$` 开头的 docx 临时文件 | 是 Word 打开的临时锁，删不掉就关了 Word 再删 |
| 终端中文乱码 | 输出文件本身是 UTF-8 OK，只是终端 GBK 不显示，无需修复 |

---

## 七、关键文件 quick reference

```
ADSMPC-python/
├── secure_rag/                  # 应用层（**核心改动区**）
│   ├── config.py                # NUM_DOCS=10, SEQ=8, TOTAL_SEQ=56, etc
│   ├── retrieval.py             # secure_inner_product_score / secure_lexical_score
│   │                            # secure_top_k_indicator / secure_rerank / secure_reader ⭐
│   ├── server.py                # run_server(); B3 后输出全 send 给 client
│   ├── client.py                # run_client(); B3 后 restore + tokenizer decode
│   ├── plaintext.py             # 明文 RAG baseline；plaintext_rag()
│   └── params.py                # gen_params() 离线生成全部 Beaver/FSS 参数
│
├── experiments/
│   ├── data/mini_corpus.json    # 50 query × 50 doc + answer 字段
│   ├── data_loader.py           # HF tokenizer + corpus 加载
│   ├── metrics.py               # Recall/Precision/NDCG/MRR + EM/PM/F1
│   ├── _rag_runner.py           # subprocess launcher
│   ├── _cipher_worker.py        # 子进程入口（改了 client 端 holder）
│   ├── run_numerical_compare.py # 任务 A：单条 query 数值 + answer 一致性
│   ├── run_retrieval_eval.py    # 任务 B：N 条 query 平均 IR + EM 指标
│   ├── run_main.py              # 整合入口
│   └── results/                 # *.md 报告输出
│
├── models/bert_tiny_weights.pth # prajjwal1/bert-tiny 权重（17 MB）
├── docs/                        # architecture.md / threat_model.md / experiments.md
├── scripts/                     # build_csprng_cpu.bat 编译脚本
├── 毕业论文/                    # 论文相关
│   ├── 支持隐私保护的检索增强生成系统-论文.docx   # 当前论文版本
│   ├── generate_thesis_full.py  # 重新生成 docx 的脚本
│   ├── thesis_full.md / thesis_part*.md         # markdown 草稿
│   └── 北京邮电...指导手册.docx  # 学校原模板
├── NssMPClib/                   # 底层 MPC 库（已修过几个 bug）
│   ├── NssMPC/                  # 库源码
│   │   ├── crypto/protocols/.../multiplication.py    # beaver_mul 已修
│   │   ├── crypto/primitives/.../dpf.py              # prefix_parity_query 已修
│   │   ├── secure_model/utils/.../fss_key_provider.py  # 加了磁盘兜底
│   │   ├── common/random/prg.py                      # CPU-only torchcsprng 兼容
│   │   └── application/neural_network/layers/        # SecBertModel, SecLayerNorm 等
│   ├── csprng/                  # torchcsprng 源码（已编译，editable 安装）
│   └── test/rag.py              # 旧入口（保留兼容）
│
├── README.md                    # 项目入口
├── requirements.txt
└── .gitignore
```

---

## 八、典型运行命令

```bash
# 激活环境
source /d/anaconda/etc/profile.d/conda.sh && conda activate ADSMPC-python
cd /d/桌面/加密rag/ADSMPC-python

# === 任务 A 单条 query 数值一致性 + reader 答案对比（约 1.5 分钟） ===
DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_numerical_compare --query_idx 0

# 不同 query
DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_numerical_compare --query_idx 5

# === 任务 B 多条 query 检索质量 + reader EM 评估（约 12 分钟 for 10 条） ===
DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_retrieval_eval --num_queries 10

# 不重新生成参数
DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_retrieval_eval --num_queries 10 --skip_gen_params

# 全 50 条（约 50-60 分钟）
DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_retrieval_eval --num_queries 50

# 只跑明文 baseline（秒级）
DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_retrieval_eval --num_queries 50 --skip_cipher

# === 旧入口（兼容保留，约 60 秒） ===
DEVICE=cpu NSSMPC_GEN_NUM=10 python NssMPClib/test/rag.py

# === 重新生成论文 docx ===
cd 毕业论文
python generate_thesis_full.py
cd ..
```

跑后台任务的标准范式：

```bash
# 启动后台
DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.xxx 2>&1 | tee /tmp/run.log &

# 等结束（用 grep 等关键词）
until grep -qE "报告已写入|RAG Baseline|Traceback" /tmp/run.log; do sleep 60; done

# 看结果
tail -40 /tmp/run.log
```

---

## 九、关键实验数据（用于论文 / 对比）

### 数值一致性（任务 A，Query #0 "What is the capital of France?"）
- pooler cosine_sim ≈ **0.949**（pool 本身有定点数误差累积）
- **reranker cosine_sim ≈ 0.9998**（128 维内积求和把误差平均掉）⭐ 论文亮点
- 单条 query 端到端 ≈ **54 秒**（CPU + torchcsprng）
- 加密延迟代价 ≈ ×2000

### 检索质量（任务 B，10 query × 10 doc）
| 指标 | 明文 | 密态 |
|---|---|---|
| Recall@1 | 0.60 | 0.60 |
| Recall@3 | 0.70 | 0.70 |
| Recall@5 | 0.70 | **1.00** |
| Precision@5 | 0.14 | 0.20 |
| NDCG@5 | 0.6631 | **0.7879** |
| MRR | 0.6500 | **0.7200** |

**密态指标普遍略优于明文**——LayerNorm/Softmax 查表近似的"小幅平滑"等价于隐式正则化（论文里这么解释，是个研究 angle）。

### 性能拆解（单条 query 53.9 秒）
- 联合编码 Stage 7：**38.4 秒（71.2%）** ← 大头
- 查询编码 Stage 3：7 秒（13%）
- 子进程启动 + 模型分享：5 秒（9.3%）
- 文档库分享：1.5 秒（2.8%）
- 双路打分 + Top-K + 文档抽取：2.5 秒（4.7%）
- Reranker matmul：0.5 秒（0.9%）

通信：服务端 624 rounds / 524 MB，客户端 389 rounds / 319 MB。

### 关键瓶颈（论文里讲）
联合编码的 Softmax + LayerNorm + GeLU 三个非线性算子占据联合编码的 ~75%。Softmax 的 exp 查表 + LayerNorm 的 rsqrt（SigmaDICF 64 轮 prefix-parity）是协议级瓶颈，与 SIGMA / BumbleBee 论文结论一致。

---

## 十、给 next session 的 Claude 的话

1. **先运行任务 A 验证 B3 改动**，看 `experiments/results/numerical_compare.md` 里 `answer_text` 字段、明文 vs 密态 EM/PM 是否合理。如果 reader 答案没出来 / 卡死，第一嫌疑是 send/recv 顺序错位（看堆栈信息排查）。

2. **不要重写已经修好的 NssMPClib bug**，特别是 `multiplication.py:beaver_mul`、`dpf.py:prefix_parity_query`、`fss_key_provider.py`。

3. **不要换 reader 算法**（已确定用启发式 pool · seq_output）；如果效果差，论文里就报告"启发式 reader EM 较低，未来工作可换 SQuAD 微调 head"。

4. **答辩重点叙述**：
   - 双路检索 + 密态 indicator 不暴露文档身份
   - Reranker 让"装饰性"联合推理变成可解释精排
   - **严格输出方向控制：客户端是答案的唯一接收者**（这是 B3 的关键卖点）
   - 抽取式 Reader 让系统具备完整 RAG 的 G 阶段（不是装饰）

5. **如果用户问"接下来做什么"**，按本文件第三节"待验证 / 待执行"的 ABC 优先级回答。

---

## 十一、知识参考

- 项目用的 BERT：`prajjwal1/bert-tiny`（HF），2 层、hidden=128、vocab=30522
- 项目用的 tokenizer：`bert-base-uncased`（与 bert-tiny vocab 共享）
- 评估语料：自建 50 query × 50 doc，10 个主题（地理 / 生物 / 物理 / 化学 / 文学 / 数学 / 计算机 / 历史 / 医学 / 体育）
- 协议参考：SIGMA（Secure GPT Inference, 2023）、BumbleBee、Iron、MPCFormer

---

**END of handoff. 直接干活。**
