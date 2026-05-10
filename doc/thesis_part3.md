# 第三章 系统设计与实现

## 3.1 引言

针对第一章中提出的"如何在不暴露查询、文档库与模型权重明文的前提下完整完成 RAG 流水线"的核心问题，本章详细介绍设计并实现的支持隐私保护的检索增强生成系统。本章首先描述系统的总体架构与威胁模型，明确各方持有什么、不持有什么、协议保护什么；然后介绍系统的核心算法——双路密态检索（含密态语义检索、密态词汇检索、密态 Top-K 指示器排序、密态文档抽取）；最后介绍把"装饰性"的联合推理转化为可解释 Cross-Encoder Reranker 的密态精排算法。

## 3.2 系统架构与威胁模型

### 3.2.1 系统总体架构

系统在"应用层 + 实验层 + 底层 MPC 库"三层架构下组织，整体架构如图 3-1 所示。

**底层（NssMPClib MPC 库）** 提供 RingTensor 环张量数据结构、ASS 算术秘密分享、FSS 函数秘密分享（DPF/DCF/DICF/SigmaDICF）、Beaver Triples 离线参数生成、TCP 异步通信、密态神经网络层（SecLinear、SecLayerNorm、SecGELU、SecSoftmax、SecBertModel 等）等基础组件。

**应用层（secure_rag 包）** 在 NssMPClib 之上实现密态 RAG 的应用逻辑，包含 6 个模块：

- `config.py`：BERT 配置、序列长度、文档库大小、词汇表大小等全局参数；
- `retrieval.py`：双路密态打分、密态 Top-K 指示器排序、密态 Cross-Encoder Reranker；
- `server.py`：服务端流程，持有文档库、接收查询、组织全流程；
- `client.py`：客户端流程，持有查询、配合协议、回传分数；
- `plaintext.py`：明文 RAG 实现，作为实验对比的 baseline；
- `params.py`：辅助参数（Beaver triples、FSS keys 等）的批量生成器。

**实验层（experiments 模块）** 负责实验组织与对比评估，包括：

- `data_loader.py`：基于 HuggingFace Tokenizer 的语料加载与预处理；
- `metrics.py`：Recall@K / Precision@K / NDCG@K / MRR 四类 IR 指标；
- `_rag_runner.py` 与 `_cipher_worker.py`：基于子进程隔离的密态 RAG 运行器，规避 Windows TCP TIME_WAIT 端口占用；
- `run_numerical_compare.py`：单条查询的明文/密态数值一致性对比；
- `run_retrieval_eval.py`：多条查询的检索质量平均指标对比；
- `run_main.py`：实验整合入口。

### 3.2.2 数据流与协议交互

系统单条查询的数据流如下：

**Stage 1 离线准备**。服务端事先用明文 BERT 对文档库的所有文档做编码，得到稠密向量库 `db_embeddings: [NUM_DOCS, hidden]`；同时根据真实 BM25 公式构造倒排矩阵 `bm25_matrix: [V, NUM_DOCS]`；保留文档 token 序列的 one-hot 表示 `db_tokens_onehot: [NUM_DOCS, doc_len, vocab_size]`。

**Stage 2 模型与文档库密态分享**。服务端把 BERT 权重秘密分享发送给客户端，使双方共同持有密态模型；同时将三类文档库数据各自秘密分享给客户端。

**Stage 3 查询编码**。客户端把查询文本经 Tokenizer 转 token id 与 one-hot，秘密分享后发给服务端。双方协同跑一遍密态 BERT 编码（Seq=8），得到查询的密态语义向量。

**Stage 4 双路密态打分**。语义路通过密态查询向量与密态文档库的内积打分；词汇路通过密态多热向量与密态 BM25 倒排矩阵的内积打分。两路并行，输出两组各自的密态分数向量。

**Stage 5 密态 Top-K 与文档抽取**。对两路分数分别执行密态 Top-K 冒泡排序，输出密态指示器；通过密态指示器与密态 token 库的元素积求和抽取出实际选中的文档 token 序列，整个过程任意一方均不知道选中了哪一篇。

**Stage 6 密态联合编码**。把"查询 + 语义路文档 + 词汇路文档"三段 token 序列在序列维度拼接为长度 56 的联合输入，再经过一遍密态 BERT 编码，得到融合视角的池化向量 [1, hidden]。

**Stage 7 密态 Cross-Encoder Reranker**。把 Stage 6 的池化向量与 Stage 1 的密态文档库做密态矩阵乘法，得到对每篇文档的精排分数向量；服务端在还原后取 argmax 即得最终 Top-K 文档下标。

### 3.2.3 威胁模型

本系统建立在半诚实两方计算（2-Party Semi-honest, 2PC）模型之上，假设双方均严格按协议执行但可能从协议运行中收集到的信息推断对方的私有输入，**不防主动作弊**。在该假设下：

| 资产 | 服务端（Party 0） | 客户端（Party 1） |
|---|---|---|
| 持有明文 | BERT 权重、文档库（文本 + embedding + BM25）、自己的所有秘密分享 | 查询文本、自己的所有秘密分享 |
| 不应直接知道 | 客户端的查询内容 | 服务端的文档内容、BERT 权重 |
| 可推理出的元信息 | 查询长度（=8 token，固定）、查询多热向量的非零位数 | 文档库大小（NUM_DOCS=10）、文档长度（24 token） |

协议**保护**的信息：（1）查询的具体文本内容；（2）文档库的具体文本内容；（3）BERT 权重的具体数值；（4）双路打分、密态 Top-K 各阶段的中间向量数值；（5）Top-K 选中了哪一篇文档（密态指示器不还原）。

协议**未保护**的信息：（1）系统结构信息（NUM_DOCS、SEQ、SEM_DOC_LEN 等定常量），（2）通信轮数与字节数等流量分析侧信道；（3）最终的精排分数（在服务端还原），通过这一点服务端能学到 reranker 给每篇文档打了多少分（但仍不知道哪篇是 ground truth 答案）。

## 3.3 双路密态检索算法

本节详细介绍系统的核心检索算法。算法以"双路并行打分 + 密态指示器排序"为核心思想，确保任意一方都无法获得 Top-K 的明文身份信息。

### 3.3.1 密态语义检索

语义检索的目标是找到与查询语义相似的文档。给定客户端查询编码后的密态向量 $\hat{\mathbf{q}} \in \text{ASS}^{1 \times d}$ 与服务端密态文档库 $\hat{\mathbf{D}} \in \text{ASS}^{N \times d}$（其中 $N$ 是文档数，$d$ 是 hidden size），密态语义打分定义为：

$$\hat{\mathbf{s}}_{\text{sem}} = \sum_{i=1}^{d} \left( \hat{\mathbf{q}} \odot \hat{\mathbf{D}} \right)_{:, i} \in \text{ASS}^{N}$$

其中 $\odot$ 表示密态广播按元素乘法。该实现利用了 PyTorch 风格的广播机制：$\hat{\mathbf{q}}$ 形状为 $[1, d]$，$\hat{\mathbf{D}}$ 形状为 $[N, d]$，按元素乘法广播为 $[N, d]$，再沿特征维度求和得到 $[N]$ 维分数。这一过程在密态下消耗 $N \cdot d$ 次密态标量乘法（走 Beaver triples），最终得到的 $\hat{\mathbf{s}}_{\text{sem}}$ 仍是 ASS 形式，双方均不知道每篇文档的具体分数。该函数对应 `secure_rag/retrieval.py` 中的 `secure_inner_product_score`。

### 3.3.2 密态词汇检索

词汇检索通过精确匹配 query 中包含的关键词在每篇文档中的 BM25 分数得分进行召回。设服务端预计算的 BM25 倒排矩阵为 $\hat{\mathbf{M}} \in \text{ASS}^{V \times N}$（$V$ 为 BM25 词表大小），客户端将查询 token 转为多热向量 $\hat{\mathbf{q}}_m \in \text{ASS}^{V \times 1}$，密态词汇打分定义为：

$$\hat{\mathbf{s}}_{\text{lex}} = \sum_{v=1}^{V} \left( \hat{\mathbf{q}}_m \odot \hat{\mathbf{M}} \right)_{v, :} \in \text{ASS}^{N}$$

直观上，多热向量在某个 term 位置为 1 时，BM25 矩阵中该 term 行所有文档的 BM25 分数被累加；多热向量为 0 时，该 term 行被屏蔽。该计算同样在密态下完成，对应 `secure_lexical_score` 函数。

### 3.3.3 密态 Top-K 指示器排序

得到双路分数后，需要从中选出 Top-K 文档。明文世界用 `argsort` 即可，但在密态下直接 `argsort` 会暴露排序结果（即"哪一位是 Top-K"），违背隐私保护目标。为此，本文设计了基于密态指示器的密态冒泡排序算法。

算法核心思路是：**不直接交换分数对应的索引，而是引入"身份证向量"作为索引代理**。具体地：

**输入**：密态分数向量 $\hat{\mathbf{s}} \in \text{ASS}^{N}$，目标 Top-K 大小 $k$

**Step 1**：构造明文单位矩阵 $\mathbf{I} = \text{eye}(N) \in \mathbb{R}^{N \times N}$，每一行 $\mathbf{I}_i$ 是文档 $i$ 的"身份证向量"（one-hot）。把每一行包装为 ASS：

$$\hat{\mathbf{I}}_i = \text{ASS}(\mathbf{I}_i), \quad i = 0, 1, \ldots, N-1$$

**Step 2**：对分数与身份证执行 K 轮冒泡。第 $i$ 轮（$i = 0, 1, \ldots, k-1$）确定第 $i$ 名文档：

```
for j = N-1 downto i+1:
    cond = secure_ge(s[j], s[j-1])         # 密态比较，返回 ASS 0 或 1
    score_diff = s[j] - s[j-1]              # ASS 减法
    score_swap_term = cond * score_diff     # Beaver 乘法
    s[j-1] = s[j-1] + score_swap_term       # 同步更新
    s[j]   = s[j]   - score_swap_term

    ind_diff = I[j] - I[j-1]
    ind_swap_term = cond * ind_diff
    I[j-1] = I[j-1] + ind_swap_term
    I[j]   = I[j]   - ind_swap_term
```

**Step 3**：返回前 $k$ 行身份证向量，沿第 0 维拼接为 $\hat{\mathbf{T}} \in \text{ASS}^{k \times N}$ 的密态指示矩阵。

整个算法的密态特性在于：（1）每次比较 `cond` 是 ASS 形式，双方无法独立得知大小关系；（2）每次 swap 是基于密态 cond 的"条件交换"，无论 cond 的实际值是多少，双方各自的份额都按相同方式更新；（3）最终输出的指示器矩阵保持密态分享形式，双方均无法获知"哪一行的 1 在哪一位"。该算法对应 `secure_top_k_indicator` 函数，时间复杂度为 $O(kN)$ 次密态比较 + 密态乘法。

### 3.3.4 密态文档抽取

得到密态指示器 $\hat{\mathbf{T}} \in \text{ASS}^{k \times N}$ 后，需要根据指示器从密态文档 token 库 $\hat{\mathbf{T}}_{\text{doc}} \in \text{ASS}^{N \times L \times V}$ 中"取出"被选中的文档 token 序列。在明文场景下这是 fancy indexing 即可，但在密态下不能用 `argsort` + `gather`（会暴露索引）。

本文采用基于"广播按元素乘 + 求和"的密态抽取算法：

$$\hat{\mathbf{D}}_{\text{selected}} = \sum_{n=1}^{N} \hat{\mathbf{T}}_{:, n, \text{None}, \text{None}} \odot \hat{\mathbf{T}}_{\text{doc},\, n, :, :} \in \text{ASS}^{k \times L \times V}$$

直观上：指示器在选中位置 $n^*$ 是 1，其它位置是 0；与文档库的 $n$ 维做按元素乘后，只有 $n^*$ 位置的 token 序列保留下来，其它全是 0；最后沿 $n$ 维求和折叠掉文档维度，等价于"密态 gather"。整个过程任意一方均无法获知 $n^*$ 的实际取值。

## 3.4 密态联合编码与 Cross-Encoder Reranker

3.3 节的双路检索已经在密态下完成了"召回 + Top-K 选择"，能够输出密态形式的 Top-K 文档 token 序列。接下来需要把这些 token 序列与查询拼接，再过一遍密态 BERT 完成"联合编码"。

### 3.4.1 密态联合编码

设查询的密态 token one-hot 序列为 $\hat{\mathbf{Q}} \in \text{ASS}^{1 \times \ell_q \times V}$，语义路 Top-1 文档的密态 token 序列为 $\hat{\mathbf{D}}_{\text{sem}} \in \text{ASS}^{1 \times \ell_d \times V}$，词汇路 Top-1 文档为 $\hat{\mathbf{D}}_{\text{lex}} \in \text{ASS}^{1 \times \ell_d \times V}$。在序列维度拼接：

$$\hat{\mathbf{X}} = \text{Cat}\left[\hat{\mathbf{Q}}, \hat{\mathbf{D}}_{\text{sem}}, \hat{\mathbf{D}}_{\text{lex}}\right] \in \text{ASS}^{1 \times (\ell_q + 2\ell_d) \times V}$$

再构造对应的位置编码、token 类型编码和 attention mask，送入密态 BERT 完成前向：

$$\hat{\mathbf{p}} = \text{SecBert}\!\left(\hat{\mathbf{X}}, \hat{\mathbf{P}}, \hat{\mathbf{T}}, \hat{\mathbf{M}}\right)_{\text{[CLS] pooler}} \in \text{ASS}^{1 \times h}$$

得到密态池化向量 $\hat{\mathbf{p}}$（维度 $h = 128$）。

### 3.4.2 Cross-Encoder Reranker

如果直接把 $\hat{\mathbf{p}}$ 还原后作为系统输出，那它只是一个 128 维向量，没有显式的下游可解释含义——这正是基础 RAG 实现的设计缺陷之一：联合推理产出的池化向量缺乏明确用途，但占据了整条流水线 75% 的计算时间。

本文针对这一缺陷提出基于密态矩阵乘法的 Cross-Encoder Reranker 算法：

$$\hat{\mathbf{r}} = \hat{\mathbf{p}} \cdot \hat{\mathbf{D}}^{\top} \in \text{ASS}^{1 \times N}$$

其中 $\hat{\mathbf{D}} \in \text{ASS}^{N \times h}$ 是 Stage 1 离线编码并秘密分享给双方的文档库。$\hat{\mathbf{p}} \cdot \hat{\mathbf{D}}^{\top}$ 是一次 ASS @ ASS 的密态矩阵乘法，由 NssMPClib 内置的 `secure_matmul` 通过 Beaver 矩阵三元组协议完成。

直观上，Cross-Encoder Reranker 的工作原理是：联合推理后的池化向量 $\hat{\mathbf{p}}$ 已经"看完了" query 和双路 Top-1 文档，是融合了三者信息的精炼语义表示；将其与原始文档语义库做内积得到的 $\hat{\mathbf{r}}$ 反映了"经过联合编码视角后"每篇文档与 query 的相关度，是更可靠的精排打分。

服务端最终对 $\hat{\mathbf{r}}$ 做 restore 得到明文分数向量，再通过 `argsort` 得到最终 Top-K 文档下标。该 Top-K 是系统的最终检索输出，可以直接交付给下游应用（接 LLM 生成、接分类头、报告给用户等）。

值得指出的是，本算法的密态特性体现在：（1）reranker 计算阶段 $\hat{\mathbf{p}}$ 与 $\hat{\mathbf{D}}$ 都保持密态分享形式，双方均无法独立观察到联合编码的具体数值；（2）只有最终的 reranker 分数 $\mathbf{r} \in \mathbb{R}^N$ 在服务端还原，这部分信息泄露与传统检索系统相同（服务端总是知道每篇文档的检索分数）。如果需要进一步保护这部分信息，可以把 restore 接收方从服务端换到客户端，这是工程上的简单变换。

## 3.5 本章小结

本章详细介绍了支持隐私保护的检索增强生成系统的设计与实现。3.1 节明确了本章任务；3.2 节描述了"应用层 + 实验层 + 底层 MPC 库"三层架构与半诚实两方计算威胁模型；3.3 节给出了双路密态检索的核心算法，包括密态语义检索的内积打分、密态词汇检索的多热向量与 BM25 矩阵打分、密态 Top-K 指示器冒泡排序、基于"广播乘 + 求和"的密态文档抽取；3.4 节针对联合推理产出的池化向量缺乏可解释下游用途的问题，提出基于密态矩阵乘法的 Cross-Encoder Reranker 算法，使联合推理转化为可解释、可量化的密态精排器。下一章将通过实验全面评估该系统的数值正确性、检索质量与运行性能。
