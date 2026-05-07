# 北京邮电大学 本科毕业设计（论文）

**题目**：支持隐私保护的检索增强生成系统

**姓名**：（请填写）
**学院**：（请填写）
**专业**：（请填写）
**班级**：（请填写）
**学号**：（请填写）
**指导教师**：（请填写）

2026 年 6 月

---

## 北京邮电大学 本科毕业设计（论文）诚信声明

本人声明所呈交的毕业设计（论文），题目《**支持隐私保护的检索增强生成系统**》是本人在指导教师的指导下，独立进行研究工作所取得的成果。尽我所知，除了文中特别加以标注和致谢中所罗列的内容以外，论文中不包含其他人已经发表或撰写过的研究成果，也不包含为获得北京邮电大学或其他教育机构的学位或证书而使用过的材料。

申请学位论文与资料若有不实之处，本人承担一切相关责任。

本人签名： ________________ 日期： ________________

---

## 关于论文使用授权的说明

本人完全了解并同意北京邮电大学有关保留、使用学位论文的规定，即：北京邮电大学拥有以下关于学位论文的无偿使用权，具体包括：学校有权保留并向国家有关部门或机构送交学位论文，有权允许学位论文被查阅和借阅；学校可以公布学位论文的全部或部分内容，有权允许采用影印、缩印或其它复制手段保存。汇编学位论文，将学位论文的全部或部分内容编入有关数据库进行检索。（保密的学位论文在解密后遵守此规定）

本人签名： ________________ 日期： ________________

导师签名： ________________ 日期： ________________

---

# 支持隐私保护的检索增强生成系统

## 摘要

随着大语言模型（Large Language Models, LLMs）能力的迅猛提升，检索增强生成（Retrieval-Augmented Generation, RAG）已成为构建知识密集型问答系统的主流方案。然而，传统 RAG 系统在客户端的查询语句、服务端的文档库以及编码模型的权重三方面同时面临隐私泄露风险，特别是在医疗、法律、金融等敏感领域，这一矛盾尤为突出。如何在不暴露任意一方明文数据的前提下，完整地完成"检索 → 召回 → 联合推理"的 RAG 流水线，是当前隐私保护机器学习领域亟待解决的关键问题。

本课题面向半诚实两方计算（2-Party Semi-honest）安全模型，针对密态 RAG 系统中"双路检索如何不泄露文档身份""联合推理后的语义向量如何形成有意义的检索输出"以及"密态计算的工程性能与数值正确性如何兼顾"三大挑战展开研究，主要工作包括：

1. **设计并实现了基于双路检索的密态 RAG 检索算法**：以 NssMPClib 安全多方计算库为底层，融合算术秘密分享（Arithmetic Secret Sharing, ASS）与函数秘密分享（Function Secret Sharing, FSS）两类基本协议，提出"密态语义检索 + 密态简化 BM25 词汇检索"双路并行打分方案，并设计基于密态指示器（One-hot Indicator）的密态 Top-K 冒泡排序与密态文档抽取算法，实现双方协同选出最相关文档但任意一方均不知道选了哪一篇的隐私目标。

2. **提出基于密态 BERT 联合编码的 Cross-Encoder Reranker 算法**：针对联合推理产出的池化向量缺乏可解释下游用途的问题，设计将联合编码的池化向量与原始文档语义库进行密态矩阵乘法的精排算法，把"装饰性"的联合推理转化为可解释、可量化的密态精排器。在自建的小型问答语料 10 条查询测试中，密态系统的 Recall@5 达到 100%、平均倒数排名 (MRR) 0.72、归一化折损累积增益 (NDCG@5) 0.79，且明文与密态精排分数的余弦相似度高达 0.9998。

3. **构建了端到端的支持隐私保护的检索增强生成系统**：包括应用层 secure_rag 包（服务端、客户端、检索算法、明文基线）、实验对比层（数值一致性测试、检索质量评估、子进程隔离运行器）以及完整的项目文档（系统架构、威胁模型、实验复现指南）。系统在 Windows 11 + Python 3.10 + PyTorch 2.3 + 自编译 torchcsprng AES PRG 环境下，单条查询端到端约 54 秒，相比基础实现加速约 25 倍，证明了在普通笔记本硬件上运行密态 RAG 的工程可行性。

**关键词** 检索增强生成 安全多方计算 隐私保护 密态推理 函数秘密分享

---

## A Privacy-Preserving Retrieval-Augmented Generation System

### ABSTRACT

With the rapid advance of Large Language Models (LLMs), Retrieval-Augmented Generation (RAG) has become the de-facto paradigm for building knowledge-intensive question-answering systems. However, traditional RAG pipelines simultaneously expose privacy on three sides: the user query on the client, the document corpus on the server, and the weights of the encoder model. The tension is particularly sharp in sensitive domains such as healthcare, legal, and financial services. Completing the entire "retrieve → recall → joint inference" pipeline of RAG without revealing any party's plaintext data remains a key open problem in privacy-preserving machine learning.

This thesis targets a 2-party semi-honest secure computation setting and tackles three challenges in encrypted RAG: (i) how to perform dual-path retrieval without leaking the identity of the selected document, (ii) how to turn the pooled vector produced by joint inference into a meaningful retrieval output, and (iii) how to balance engineering performance with numerical correctness in encrypted computation. The main contributions are:

1. **A dual-path encrypted retrieval algorithm**. Built on top of the NssMPClib secure multi-party computation library, this work combines Arithmetic Secret Sharing (ASS) with Function Secret Sharing (FSS) and proposes a parallel scoring scheme that consists of an encrypted semantic path and an encrypted BM25-like lexical path. A novel encrypted Top-K bubble-sort with a one-hot indicator vector and a subsequent encrypted document-extraction routine ensure that both parties cooperatively select the most relevant document while neither party learns which document was chosen.

2. **A secure Cross-Encoder Reranker** built upon encrypted BERT joint encoding. We address the previously unused pooler output of the joint inference stage by performing an encrypted matrix multiplication between the pooled vector and the original document embedding library, turning what was decorative into a quantifiable encrypted reranker. On a self-constructed mini QA corpus, the encrypted system achieves Recall@5 = 1.00, Mean Reciprocal Rank (MRR) = 0.72, and NDCG@5 = 0.79 across 10 queries, while the cosine similarity between the plaintext and encrypted reranker scores reaches 0.9998.

3. **An end-to-end privacy-preserving RAG system** that includes the application-layer `secure_rag` package (server, client, retrieval algorithms, plaintext baseline), an experimental comparison layer (numerical consistency tests, retrieval-quality evaluation, subprocess-isolated runners), and project-level documentation (system architecture, threat model, reproduction guide). On a Windows 11 + Python 3.10 + PyTorch 2.3 environment with self-compiled torchcsprng AES PRG, a single end-to-end query takes about 54 seconds, roughly 25× faster than the baseline implementation, demonstrating the engineering feasibility of running encrypted RAG on commodity laptop hardware.

**KEY WORDS** Retrieval-Augmented Generation, Secure Multi-Party Computation, Privacy Preservation, Encrypted Inference, Function Secret Sharing

---

# 目录

第一章 绪论
1.1 研究背景与意义
1.2 国内外研究现状
1.2.1 检索增强生成技术
1.2.2 隐私保护检索
1.2.3 密态机器学习推理
1.3 研究内容与创新点
1.4 章节安排

第二章 相关研究
2.1 检索增强生成
2.2 安全多方计算
2.3 密态神经网络推理
2.4 本章小结

第三章 系统设计与实现
3.1 引言
3.2 系统架构与威胁模型
3.3 双路密态检索算法
3.3.1 密态语义检索
3.3.2 密态词汇检索
3.3.3 密态 Top-K 指示器排序
3.3.4 密态文档抽取
3.4 密态联合编码与 Cross-Encoder Reranker
3.5 本章小结

第四章 实验与分析
4.1 引言
4.2 实验设置
4.3 数值一致性实验
4.4 检索质量实验
4.5 性能拆解
4.6 消融实验
4.7 本章小结

第五章 总结与展望
5.1 论文工作总结
5.2 未来工作展望

参考文献
致谢
附录 1 缩略语表
附录 2 系统目录结构
附录 3 伦理声明
攻读学位期间取得的创新成果

---

# 第一章 绪论

## 1.1 研究背景与意义

近年来，以 GPT、Llama、DeepSeek 等为代表的大语言模型（Large Language Models, LLMs）在问答系统、代码生成、教育教学、法律咨询、医疗问诊等众多领域展现出强大能力，已逐步成为信息服务的核心基础设施。然而，纯参数化的 LLM 难以避免事实性幻觉、训练数据时效性差、领域知识封闭等固有缺陷，导致其在专业场景下的可信度受限。检索增强生成（Retrieval-Augmented Generation, RAG）通过将外部知识库与生成模型解耦，在生成回答前先从知识库中检索相关文档，再把"问题 + 检索片段"一并送入生成模型，从根本上缓解了上述问题，已成为当前知识密集型 LLM 应用的主流架构。

然而，RAG 系统的隐私问题尚未得到充分重视。一个完整的 RAG 流程同时涉及三类敏感数据：（1）用户提交的查询，可能包含病情、案件、商业机密等高度个人化信息；（2）服务端持有的文档库，可能涉及医院病例、法律卷宗、企业内部文档等不可对外共享的知识资产；（3）模型权重，体现训练数据与算法投入，是服务提供方的核心知识产权。在传统 RAG 部署中，三者必须明文聚合在同一计算节点上才能完成检索与生成，导致客户端用户必须信任服务端不会窥视其查询内容、服务端必须把文档库以明文形式暴露给计算引擎、第三方算力提供商更可能同时观察查询与文档。这一信任模型在医疗诊断、法律咨询、金融风控等高敏场景下难以被各方接受。

针对 RAG 中的隐私问题，安全多方计算（Secure Multi-Party Computation, MPC）提供了基础的密码学工具：在不暴露任何一方明文输入的前提下，各方协同计算函数的输出。如何把整条 RAG 流水线（编码、双路打分、Top-K 排序、文档抽取、联合推理）系统地搬迁到密态计算之上，且在普通硬件上达到工程可用水平，是隐私保护机器学习领域当前的研究热点之一。本课题在西安电子科技大学网络与系统安全实验室开源的 NssMPClib 框架之上，面向半诚实两方计算模型，构建了一个支持隐私保护的检索增强生成系统的原型。研究密态 RAG 不仅有助于把 LLM 应用推广到更多对隐私敏感的高价值领域，也对推动 MPC 协议在面向 Transformer 架构的非线性计算（如 LayerNorm、Softmax、GeLU 等）上的工程优化具有重要的理论与实用意义。

## 1.2 国内外研究现状

本节围绕"支持隐私保护的检索增强生成系统"这一核心命题，从检索增强生成、隐私保护检索与密态机器学习推理三个维度梳理代表性研究工作。

### 1.2.1 检索增强生成技术

检索增强生成是当前知识密集型自然语言处理的主流范式。Karpukhin 等人于 2020 年提出的 Dense Passage Retriever（DPR）首次系统性地证明了基于双塔 BERT 的稠密检索在开放域问答上显著优于传统的 BM25 词汇检索。Lewis 等人随后提出的原始 RAG 框架将稠密检索与生成式模型联合训练，把检索作为可微分模块嵌入到端到端管线中。后续 Atlas、RETRO、In-Context-RALM 等工作进一步在大模型规模、上下文长度、检索粒度等维度上推动 RAG 的发展。在工业界，OpenAI、百度文心、阿里通义等头部 LLM 平台均已将 RAG 作为知识接入的标准接口。在双路检索（hybrid retrieval）方面，业界普遍采用稠密检索（语义路）与传统 BM25（词汇路）并行召回、再通过 Reciprocal Rank Fusion（RRF）等策略融合的方案，以兼顾语义泛化能力与精确关键词匹配能力。

现有 RAG 工作多在明文环境下展开，专注于召回质量、上下文窗口扩展与检索粒度等维度，对查询与文档的隐私保护问题关注较少。

### 1.2.2 隐私保护检索

隐私信息检索（Private Information Retrieval, PIR）是隐私保护检索的经典方向，其目标是允许客户端从服务端查询特定记录而不暴露查询索引。Chor 等人 1995 年提出的多服务器 PIR 在信息论安全模型下达成隐私目标，但通信复杂度随数据库规模线性增长。Kushilevitz 与 Ostrovsky 的单服务器计算性 PIR 利用同态加密把通信复杂度降低到亚线性。然而经典 PIR 本质上要求查询是"按 ID 取记录"，与 RAG 中"按相关度排序后取 top-K"的语义不匹配。

不经意随机访问机（Oblivious Random Access Memory, ORAM）通过反复打乱物理存储位置实现访问模式混淆，但在 RAG 这类需要 Top-K 排序与多次查表的场景下开销高昂。最近兴起的密态向量检索（如 Tiptoe、Coral 等）尝试在两方设置下实现密态最近邻搜索，但通常只覆盖检索阶段的稠密向量打分，未集成完整 RAG 中的 BM25 词汇检索、密态文档抽取与密态生成 / 编码环节。

### 1.2.3 密态机器学习推理

随着 SecureML、CrypTen 等通用框架的出现，神经网络的密态推理逐渐由理论走向实践。在 Transformer 架构上，SIGMA（Secure GPT Inference）、BumbleBee、Iron 等工作针对 Softmax、LayerNorm、GeLU 等非线性算子提出了基于函数秘密分享（FSS）与查表近似的高效协议，把单层 Transformer 在 LAN 环境下的密态前向时间压缩到数秒级。MPCFormer 在 BERT 模型上系统验证了密态推理的可行性。开源的 NssMPClib 库由西安电子科技大学网络与系统安全实验室维护，提供了 RingTensor、ASS、FSS（含 DPF/DCF/DICF/VDPF/VSigma）、Beaver Triples、Paillier 同态加密等基础组件，并实现了密态 BERT、CNN 等典型模型，已被多个研究项目用于密态机器学习实验。

然而，已有密态机器学习工作主要面向单纯的推理任务，对"检索 + 推理联合"的 RAG 系统级问题鲜有讨论；现有密态向量检索工作又通常脱离生成 / 编码模块单独存在。这正是本课题试图填补的空白。

## 1.3 研究内容与创新点

针对检索增强生成系统中查询、文档库与模型权重三方隐私同时受到威胁的现状，本文设计并实现了一种基于双路检索 + 密态联合编码 + 密态精排的端到端密态 RAG 系统，并在自建小型问答语料上完成了密态 vs 明文的多维对比实验。系统总体上由"应用层 secure_rag 包 + 实验对比层 experiments 模块 + 底层 NssMPClib MPC 库"三层组成。

本文的主要贡献总结如下：

（1）**设计并实现了基于双路并行的密态检索算法**。算法包含：（a）基于密态广播乘法的语义路打分，对密态查询向量与密态文档库做内积；（b）基于密态稀疏向量与 BM25 倒排矩阵的词汇路打分；（c）基于密态指示器（one-hot 单位向量包装为密态分享）的密态 Top-K 冒泡排序，使得在交换分数的同时同步交换"身份证向量"，最终输出 [K, NUM_DOCS] 的密态指示矩阵；（d）基于"指示器与文档 token 库逐元素相乘后求和"的密态文档抽取，使任意一方无法获知 Top-K 实际选中的文档下标。算法整体保留了与明文双路检索一致的语义召回能力，同时实现了文档身份的完全隐私保护。

（2）**提出了基于密态联合编码的 Cross-Encoder Reranker 算法**。本文观察到原 RAG 框架联合推理产出的 [CLS] 池化向量缺乏明确下游用途的设计缺陷，进一步提出将该向量与原始文档语义库做密态矩阵乘法的精排方案：以联合编码后的池化向量作为"经过 query-doc 融合的精炼表示"，通过 [1, hidden] @ [hidden, NUM_DOCS] 的密态矩阵乘运算得到对每篇文档的精排分数。在 10 条查询的真实评估上，该方案使密态系统的 Recall@5 达到 100%、MRR 达到 0.72、NDCG@5 达到 0.79，且明文与密态精排分数的余弦相似度高达 0.9998，证明了协议的数值正确性。

（3）**构建了完整的端到端密态 RAG 实验平台**。系统包括：（a）应用层 secure_rag 包（服务端流程、客户端流程、检索算法库、明文基线、辅助参数生成器、全局配置），（b）实验对比层 experiments 模块（基于子进程隔离的密态 RAG 运行器、HuggingFace Tokenizer 接入的语料加载器、Recall@K / MRR / NDCG@K / Precision@K 四类 IR 指标实现、数值一致性对比脚本、检索质量对比脚本、整合入口），（c）配套文档（系统架构图、威胁模型说明、实验复现指南）。在普通笔记本（i7 + 16GB RAM + RTX 3050 4GB）上，针对自编译 torchcsprng AES PRG 优化后单条查询端到端约 54 秒，相比基础实现加速约 25 倍。系统已经过若干工程层面的改造与修复，包括针对 DEBUG_LEVEL=2 单密钥广播路径的 Beaver mul 与 prefix_parity_query 修复、子进程端口隔离修复、close() 阶段挂起规避等。

## 1.4 章节安排

本文一共包含五个章节，各章节的主要内容如下：

第一章为绪论。介绍了课题的研究背景，分析了检索增强生成系统在查询、文档库与模型权重三方面同时面临的隐私挑战，从检索增强生成、隐私保护检索、密态机器学习推理三个维度综述了国内外研究现状，提出了本文的研究内容与创新点。

第二章为相关研究。本章对密态 RAG 涉及的基础理论与代表性工作做较深入的回顾，依次介绍了检索增强生成的典型架构与检索范式、安全多方计算的关键协议（算术秘密分享、函数秘密分享、Beaver triples、半诚实两方计算模型）、密态神经网络推理的代表性方法（SIGMA、BumbleBee、Iron、NssMPClib），为后续章节的设计奠定基础。

第三章为系统设计与实现。本章详细介绍设计并实现的密态 RAG 系统，包括系统总体架构与威胁模型、双路密态检索算法（密态语义检索、密态词汇检索、密态 Top-K 指示器排序、密态文档抽取）、密态联合编码与 Cross-Encoder Reranker 算法。

第四章为实验与分析。本章在自构建的小型问答语料库上对系统进行了多维评估：数值一致性实验验证密态计算的正确性、检索质量实验对比明文与密态在 Recall@K / MRR / NDCG@K 等 IR 指标上的差异、性能拆解实验定位密态推理的主要瓶颈、消融实验考察 Reranker 的有效性。

第五章为总结与展望。对本文的研究工作进行总结，并对未来的研究方向（包括密态生成式 LLM、可扩展 Top-K、恶意安全升级等）进行展望。
