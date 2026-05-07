# 系统架构

## 概览

加密 RAG 由三层组成（自底向上）：

| 层 | 路径 | 职责 |
|---|---|---|
| **底层 MPC 库** | `NssMPClib/NssMPC/` | RingTensor、ASS、FSS、Beaver triples、密态层（SecBertModel 等）|
| **应用层** | `secure_rag/` | 双路检索 + 密态 Top-K + 联合推理；明文 baseline |
| **实验层** | `experiments/` | tokenizer、IR 指标、对比脚本 |

## 双路 RAG 数据流

```mermaid
flowchart LR
    Q[Client: query 文本] --> T[BertTokenizer]
    T --> QID[query token id 1×8]
    QID --> ENC[密态 BERT 编码<br/>SecBertModel Seq=8]
    ENC --> QEMB[query_emb 1×128]

    DB[Server: 文档库<br/>50 篇短文本] --> DT[文档 token id]
    DT --> DOH[文档 one-hot 50×24×30522]
    DT --> DEMB[文档语义向量 50×128<br/>明文 BERT 离线编码]
    DT --> BM[BM25 矩阵 V×50<br/>真 BM25 公式]

    QEMB -->|内积| SEM[语义路打分 50]
    QID -.->|多热向量| QM[query_multihot V×1]
    QM -->|内积| LEX[词汇路打分 50]
    BM ---> LEX

    SEM --> TKS[密态 Top-K<br/>指示器冒泡]
    LEX --> TKL[密态 Top-K<br/>指示器冒泡]
    TKS --> EX1[抽语义路 doc 1×24]
    TKL --> EX2[抽词汇路 doc 1×24]
    DOH --> EX1
    DOH --> EX2

    QID --> CAT[拼接 1×56]
    EX1 --> CAT
    EX2 --> CAT
    CAT --> JOINT[联合密态 BERT 推理<br/>SecBertModel Seq=56]
    JOINT --> POOL[pool 1×128<br/>最终输出]
```

## 密态 vs 明文 流程对照

| 步骤 | 密态版 | 明文版 |
|---|---|---|
| query 编码 | `client.py` 走 SecBertModel 密文路径 | `plaintext.py` 走 SecBertModel 明文路径 |
| 双路打分 | `retrieval.py` 三个 secure_* 函数（基于 ASS Beaver mul） | 同一份 PyTorch 张量直接乘加 |
| Top-K 排序 | 冒泡 + indicator swap，每次比较走 secure_ge → SIGMA DICF | `torch.topk` 一行 |
| 取真实文档 | `(indicator ⊗ db_tokens).sum(dim=1)` 全 ASS 操作 | 同一公式但用 PyTorch 张量 |
| 联合推理 | SecBertModel 全密态 forward | SecBertModel 明文 forward |
| 输出 | server 收 client 的 pool share，restore 还原 | 直接 return |

## 关键文件代码路径

- 双路打分函数：`secure_rag/retrieval.py:secure_inner_product_score / secure_lexical_score / secure_top_k_indicator`
- Server 流程：`secure_rag/server.py:run_server`
- Client 流程：`secure_rag/client.py:run_client`
- 明文等价物：`secure_rag/plaintext.py:plaintext_rag`
- 离线 doc 编码：`secure_rag/plaintext.py:encode_docs_to_embeddings`
- 真 BM25 公式：`secure_rag/plaintext.py:build_bm25_matrix`

## 通信开销（典型一条 query）

- send rounds: ~624
- send bytes: ~524 MB
- recv rounds: ~389
- recv bytes: ~319 MB

主要开销在 LayerNorm 的 rsqrt（SigmaDICF 64 轮 prefix-parity）和 SoftMax 的 exp。
