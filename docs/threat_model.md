# 威胁模型

## 系统假设

本项目实现的是**半诚实（semi-honest, a.k.a. honest-but-curious）2PC 模型**：

- 双方（Server 与 Client）会**严格按协议执行**
- 但每一方都会**尝试从协议运行时收集到的所有信息**反推对方的输入
- **不防主动作弊**（Malicious Adversary）—— 即使一方故意发送错误的 share / 错误的 Beaver triple，协议没有 MAC 校验、没有 commit-and-prove，可能产生错误结果

## 双方持有什么、不持有什么

|  | Server (party_id=0) | Client (party_id=1) |
|---|---|---|
| **持有（明文）** | 文档库的 token、embedding、BM25 矩阵；BERT 权重；自己手里的所有 secret share | query 文本；自己手里的所有 secret share |
| **不直接知道** | client 的 query 内容（只看到 share） | server 的文档内容；BERT 权重明文（只看到 share） |
| **可推理出来的元信息** | query 长度（=8 token，固定）、query 多热向量的非零位数 | 文档库大小（NUM_DOCS=10）、文档长度（24 token）、BM25 vocab 大小 |

## 信息泄露分析

✅ **被保护的信息**：
- query 文本内容
- 每篇 doc 文本内容
- BERT 权重数值
- 中间 embedding 数值（query_emb、双路 score 都是 share 形式）
- 检索 Top-K 选了哪一篇文档（指示器是密态的，没有 restore）

⚠️ **未被保护 / 已知泄露**：
- **结构信息**：双方都知道 NUM_DOCS、SEQ、SEM_DOC_LEN、LEX_DOC_LEN、TOP_K 是定值
- **通信模式**：协议 send/recv 顺序固定，不防 traffic analysis
- **运行时间**：每一步耗时与输入数值无关（基本是 oblivious 的），但与输入大小相关
- **最终 pooler 输出**：server 一侧能看到（因为是 server 收 share 还原的），如果是反向场景（让 client 拿结果）需要交换 send/recv 角色

## 不在本项目防护范围内的攻击

❌ **主动篡改攻击**：发错 share、发错 triple → 协议结果会错，但不会被察觉
❌ **侧信道**：电源、电磁、缓存 timing 等
❌ **网络层**：通信用明文 TCP，没用 TLS（实际部署需要 mutual-TLS）
❌ **协议外信道**：query 转 token id 用 BertTokenizer 时，是 client 自己本地做（不在 MPC 里），但如果 tokenizer 离线就没问题

## 与 Pisces (ICLR 2026) 协议层威胁模型对比

Pisces 是基于 cryptography 的 RAG 检索协议（ICLR 2026, Ant Group），采用 OPRF + OKVS + multi-instance labeled PSI 等高级原语。本工作架构同型但协议层简化（保留 NssMPClib 兼容）。

### Server-side 隐私（client 可观察到什么）

| 信息项 | Pisces | 本工作 (默认 LEX_BM25_ONLINE=False) | 本工作 (LEX_BM25_ONLINE=True) |
|---|---|---|---|
| Server 知道 client query 包含哪些 token | ❌（PSI 保证） | ❌（query 是 share 形式，server 看不到明文）但 indicator share 的非零位数可推 | 同左 |
| Server 知道哪些 doc 被检索 | ❌ | ❌（top-K indicator 是 share，未 restore） | 同左 |
| Server 看到联合推理 pool / answer | ❌（在 client 端 restore） | ❌（B3 模式：rerank/pool/answer/span 都 send 给 client） | 同左 |

### Client-side 隐私（server 可观察到什么）

| 信息项 | Pisces | 本工作 (默认) | 本工作 (Online) |
|---|---|---|---|
| Client 持有的 doc-side 中间统计 | tf (per-query token, via PSI 输出) | **bm25_matrix [V,N]** (成品 BM25 score) | **tf [V,N], idf [V], doc_norm [N]** (原始统计) |
| Client 能否逆推 BM25 公式 | ✅（已知 tf 和 query token） | ❌（已知 score 但无 tf/idf 拆解） | ✅（有 tf/idf/doc_norm，可重建 BM25 公式） |
| Client 知道 doc embedding | 通过 ASS share 看不到明文 | 同左 | 同左 |
| Client 知道 BERT 权重 | N/A | 通过 ASS share 看不到明文 | 同左 |

### 协议级原语对比

| 原语 | Pisces 是否使用 | NssMPClib 是否支持 | 本工作是否使用 |
|---|---|---|---|
| ASS (Arithmetic Secret Sharing) | ✅ | ✅ | ✅ |
| OPRF (Oblivious PRF) | ✅ | ❌ | ❌ |
| OKVS (Oblivious Key-Value Store) | ✅ | ❌ | ❌ |
| Multi-instance labeled PSI | ✅ | ❌ | ❌ |
| Batch PIR-to-share | ✅ | ❌ | ❌ |
| FHE (Optional 用于 Step 6) | ✅ | ❌ | ❌ |
| Function Secret Sharing (FSS) | ❌ | ✅ | ✅（用于 SimHash 比较门） |
| SigmaDICF (FSS-based comparison) | ❌ | ✅ | ✅（用于 secure_ge / secure_div） |

### 本工作未实现的 Pisces 隐私升级路径

1. **真 PSI**：要实现 "server 完全不知 client query 包含哪些 token"，需要 OPRF + OKVS。NssMPClib 当前不支持，作为 future work。
2. **Coarse filter 的 oblivious filter**：Pisces 的 ∏Oblivious Filter (Protocol 3) 用 OPRF + OKVS 把 N 大幅压缩到候选集；本工作用 ASS Hamming + bubble top-M 实现等价功能，但协议复杂度 O(N·M) vs Pisces 的 O(N + M)。
3. **Secure sorting**：本工作用 bubble + indicator swap (O(N·K))，Pisces 用 bitonic sort 类 secure sorting 协议 (O(N log² N))。

### 当前 LEX_BM25_ONLINE 模式威胁模型升级

LEX_BM25_ONLINE=False（默认）→ True（Online 模式）的威胁模型变化：

✅ **改进**：
- Server 不再算/共享"成品 BM25 matrix"，只共享原始 tf/idf/doc_norm 统计
- 协议流程跟 Pisces ∏PrivateBM25 / Protocol 2 Step 4 一致

⚠️ **未改进**：
- Server 仍能从 query indicator share 模式推断 query 词表分布
- Client restore 三个分量后能重建 BM25 公式（信息量比 offline mode 还大）

⭐ **协议层叙事价值**：让论文 ch3.3 节的协议描述跟 Pisces 一致，便于 ablation 比较。

## 总结

**本项目是 research prototype，能给毕设/论文用，不是 production-ready 系统**。读者应当清楚：

> 在半诚实假设下，密态 RAG 双方既学不到对方的 query 也学不到对方的文档库内容；但在恶意作弊或侧信道场景下没有任何保证。
