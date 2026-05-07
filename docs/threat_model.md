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

## 升级路径（不在本项目实现）

| 想要的 | 需要做的 |
|---|---|
| 防主动作弊 | 启用 NssMPClib 已有的 VDPF / VSigma；加 MAC check；改用 honest-majority 3PC |
| 防 traffic analysis | 在每一步加 padding 或 dummy ops |
| 防 server 看到 pooler | 把 restore 接收端从 server 换到 client |
| 端到端密态 LLM | 把 SecBertModel 换成 SecLlamaModel（参考 SIGMA / BumbleBee 论文）|

## 总结

**本项目是 research prototype，能给毕设/论文用，不是 production-ready 系统**。读者应当清楚：

> 在半诚实假设下，密态 RAG 双方既学不到对方的 query 也学不到对方的文档库内容；但在恶意作弊或侧信道场景下没有任何保证。
