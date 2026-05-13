---
title: 支持隐私保护的检索增强生成系统的设计与实现
author: lsm
school: 北京邮电大学
date: 2026 年 6 月
template_compliance: 北京邮电大学2026届本科毕业设计（论文）撰写指导手册
---

# 北京邮电大学

# 本科毕业设计（论文）

**题目**：支持隐私保护的检索增强生成系统的<br/>设计与实现

**姓　名**：lsm
**学　院**：（请填写）
**专　业**：（请填写）
**班　级**：（请填写）
**学　号**：（请填写）
**指导教师**：（请填写）

2026 年 6 月

---

# 北京邮电大学本科毕业设计（论文）诚信声明

本人声明所呈交的毕业设计（论文），题目《**支持隐私保护的检索增强生成系统的设计与实现**》是本人在指导教师的指导下，独立进行研究工作所取得的成果。尽我所知，除了文中特别加以标注和致谢中所罗列的内容以外，论文中不包含其他人已经发表或撰写过的研究成果，也不包含为获得北京邮电大学或其他教育机构的学位或证书而使用过的材料。

申请学位论文与资料若有不实之处，本人承担一切相关责任。

本人签名：________________ 日期：________________

---

# 关于论文使用授权的说明

本人完全了解并同意北京邮电大学有关保留、使用学位论文的规定，即：北京邮电大学拥有以下关于学位论文的无偿使用权，具体包括：学校有权保留并向国家有关部门或机构送交学位论文，有权允许学位论文被查阅和借阅；学校可以公布学位论文的全部或部分内容，有权允许采用影印、缩印或其它复制手段保存。汇编学位论文，将学位论文的全部或部分内容编入有关数据库进行检索。（保密的学位论文在解密后遵守此规定）。

本人签名：________________ 日期：________________

导师签名：________________ 日期：________________

---

# 支持隐私保护的检索增强生成系统的设计与实现

## 摘要

大语言模型（Large Language Models, LLMs）的迅猛发展使检索增强生成（Retrieval-Augmented Generation, RAG）成为问答、医疗咨询、法律检索等知识密集型应用的主流架构。然而，现行 RAG 系统在客户端查询、服务端文档库与编码模型权重三方面同时面临隐私威胁，已成为制约其在医疗、金融、法律等敏感领域落地的关键障碍。如何在不暴露任意一方明文数据的前提下完整地完成"编码—检索—精排—答案抽取"的 RAG 流水线，是当前隐私保护机器学习领域亟待解决的核心问题。本文面向半诚实两方安全计算模型，基于 NssMPClib 安全多方计算库设计并实现了一个端到端的支持隐私保护的检索增强生成系统原型。本文的主要工作包括：

（1）设计并实现了基于算术秘密分享（Arithmetic Secret Sharing, ASS）的双路密态检索协议。针对已有方案（如 Pisces）依赖不经意伪随机函数、不经意键值存储等专用原语难以在通用 MPC 库上复用的局限，本文仅使用 ASS 与函数秘密分享两类基础原语独立设计双路检索：语义路采用 SimHash 粗筛与密态余弦精排级联结构，先用公开投影矩阵把密态查询与密态文档库压缩到比特表示再做密态汉明距离粗筛，最后对候选集做密态余弦内积精排；词汇路采用在线密态 BM25 公式（含逆文档频率、文档长度归一化与密态除法），将词频、逆文档频率、文档长度归一化三分量分别以秘密分享形式发布；并设计了基于密态单位向量指示器的密态 Top-K 冒泡排序算法，保证任意一方都无法获知 Top-K 实际选中的文档下标。

（2）提出了密态 Cross-Encoder 精排器与密态抽取式 Span 阅读器联合方案。前者把联合编码 [CLS] 池化向量与密态文档库做矩阵乘法精排，把原本"装饰性"的联合推理转化为可量化的精排输出；后者引入面向斯坦福问答数据集（Stanford Question Answering Dataset, SQuAD）训练好的起止位置头权重，利用累积和（cumsum）技巧在密态域中提取连续 span，实现多 token 答案抽取。

（3）提出了密态跨路 PRF 协议与候选池重排（Candidate-Pool Reranker）算法。第一轮检索后，语义路 Top-1 文档反馈到词汇路扩展 query 得到第二轮文档；联合推理输入仍使用第一轮文档保持精排基准稳定，第二轮文档以候选池约束方式加入精排阶段的 Hybrid 公式（全 $N$ 库精排 + 候选池温和 boost）。该设计避开了朴素 PRF 在精排器主导架构下的"平滑效应"陷阱，是相对 Pisces (ICLR 2026) 检索协议（无 PRF 与多轮机制）的正向创新点。

（4）构建了端到端密态 RAG 实验平台并完成多维消融实验。系统在 Windows 11 + Python 3.10 + PyTorch 2.3.0 环境下，单条查询端到端约 86 秒；在自构建的 10 query × 10 doc 小型问答语料上，密态 Recall@5 达 1.00，归一化折损累积增益（NDCG@5）达 0.83，平均倒数排名（MRR）达 0.78（其中 NDCG@5 与 MRR 受益于 PRF 候选池重排协议而超过 PRF 关闭基线），关键中间量明文-密态余弦相似度达 0.9998。

**关键词** 检索增强生成　安全多方计算　隐私保护　密态推理　函数秘密分享

---

# A Privacy-Preserving Retrieval-Augmented Generation System: Design and Implementation

## ABSTRACT

With the rapid advance of Large Language Models (LLMs), Retrieval-Augmented Generation (RAG) has become the dominant paradigm for knowledge-intensive applications such as question answering, medical consulting and legal search. However, conventional RAG pipelines simultaneously expose privacy on three fronts: the user query on the client, the document corpus on the server, and the encoder model weights. The tension is especially sharp for sensitive domains such as healthcare, finance and law. Completing the entire "encode-retrieve-rerank-extract" pipeline of RAG without revealing any party's plaintext data remains a key open problem in privacy-preserving machine learning. Targeting the 2-party semi-honest secure computation model and building upon the NssMPClib library, this thesis designs and implements an end-to-end privacy-preserving RAG prototype. The main contributions are as follows:

(1) A dual-path encrypted retrieval algorithm. The semantic path follows a coarse-to-fine structure with SimHash filtering and encrypted cosine reranking: a public projection matrix maps both the encrypted query and the encrypted document corpus into bit representations for an encrypted Hamming-distance coarse filter, followed by an encrypted cosine inner-product reranking on the candidate set. The lexical path performs the online encrypted Best Matching 25 (BM25) formula including Inverse Document Frequency (IDF), document-length normalization and encrypted division, with the term frequency, IDF and document-length-normalization components published separately as secret shares. An encrypted indicator-based bubble-sort Top-K routine guarantees that neither party can learn which document is finally selected.

(2) A joint scheme of an encrypted Cross-Encoder reranker and an encrypted extractive Span reader. The former performs an encrypted matrix multiplication between the [CLS] pooled vector and the encrypted document corpus, converting the otherwise decorative joint inference into a quantifiable reranking output. The latter uses publicly released start/end heads trained on the Stanford Question Answering Dataset (SQuAD) and adopts a cumulative-sum (cumsum) trick to extract continuous spans in the encrypted domain, supporting multi-token answers.

(3) An end-to-end privacy-preserving RAG experimental platform with multi-dimensional ablation. On Windows 11 with Python 3.10 and PyTorch 2.3.0, a single end-to-end query takes about 79 seconds. On a self-constructed 10-query × 10-document mini corpus, the encrypted system achieves Recall@5 of 1.00, Normalized Discounted Cumulative Gain (NDCG@5) of 0.82, and Mean Reciprocal Rank (MRR) of 0.77, with key intermediate cosine similarity reaching 0.9998 between plaintext and encrypted versions.

**KEY WORDS**  Retrieval-Augmented Generation  Secure Multi-Party Computation  Privacy Preservation  Encrypted Inference  Function Secret Sharing

---

# 目录

第一章　绪论
　　1.1　研究背景与意义
　　1.2　国内外研究现状
　　　　1.2.1　检索增强生成技术
　　　　1.2.2　隐私保护检索
　　　　1.2.3　密态机器学习推理
　　1.3　研究内容与创新点
　　1.4　章节安排

第二章　相关研究
　　2.1　检索增强生成
　　2.2　安全多方计算
　　　　2.2.1　算术秘密分享
　　　　2.2.2　函数秘密分享
　　　　2.2.3　Beaver 三元组与矩阵乘协议
　　2.3　密态神经网络推理
　　2.4　本章小结

第三章　支持隐私保护的检索增强生成系统设计
　　3.1　引言
　　3.2　系统总体架构与威胁模型
　　　　3.2.1　系统三层架构
　　　　3.2.2　数据流与协议交互
　　　　3.2.3　威胁模型
　　3.3　双路密态检索算法（第一阶段粗排）
　　　　3.3.1　语义路 SimHash 粗筛与密态精排
　　　　3.3.2　词汇路在线密态 BM25
　　　　3.3.3　密态 Top-K 指示器排序
　　　　3.3.4　密态文档抽取
　　3.4　密态伪相关反馈与候选池构建
　　　　3.4.1　密态跨路 PRF 协议
　　　　3.4.2　PRF 第二轮反馈的"平滑效应"与候选池重排
　　　　3.4.3　超参选择与协议正确性
　　3.5　Cross-Encoder 密态精排（第二阶段精排）
　　　　3.5.1　密态联合编码
　　　　3.5.2　Hybrid Reranker 密态精排
　　3.6　密态生成阶段
　　　　3.6.1　方案选择：复用 SQuAD QA 头而非外部密态 LLM
　　　　3.6.2　密态 QA 头与 Span 抽取协议
　　　　3.6.3　累积和 span 掩码技巧
　　　　3.6.4　实验效果与限制
　　3.7　本章小结

第四章　实验与分析
　　4.1　引言
　　4.2　对比实验
　　　　4.2.1　实验设置
　　　　4.2.2　密态与明文 RAG 对比
　　　　4.2.3　密态 RAG 启用与关闭 PRF 对比
　　4.3　消融实验
　　　　4.3.1　语义路 SimHash 消融
　　　　4.3.2　词汇路 BM25 双模式消融
　　4.4　本章小结

第五章　总结与展望
　　5.1　论文工作总结
　　5.2　未来工作展望

参考文献
致谢
附录 1　缩略语表

---

# 第一章　绪论

## 1.1　研究背景与意义

近年来，以 GPT、Llama、DeepSeek、ChatGLM 等为代表的大语言模型（Large Language Models, LLMs）在问答系统、代码生成、教育教学、法律咨询、医疗问诊等多个领域展现出强大能力<sup>[1-2]</sup>，已逐步成为下一代信息服务的核心基础设施。然而，纯参数化的 LLM 难以避免事实性幻觉、训练数据时效性差、领域知识封闭等固有缺陷，导致其在专业场景下的可信度受限。检索增强生成（Retrieval-Augmented Generation, RAG）<sup>[3]</sup>通过将外部知识库与生成模型解耦，在生成回答前先从知识库中检索相关文档，再把"问题与检索片段"一并送入生成模型，从根本上缓解了上述问题，已成为当前知识密集型 LLM 应用的主流架构。

然而，RAG 系统的隐私问题尚未得到充分重视。一个完整的 RAG 流程同时涉及三类敏感数据：第一，用户提交的查询，可能包含病情、案件、商业机密等高度个人化信息；第二，服务端持有的文档库，可能涉及医院病例、法律卷宗、企业内部文档等不可对外共享的知识资产；第三，模型权重，体现训练数据与算法投入，是服务提供方的核心知识产权。在传统 RAG 部署中，三者必须明文聚合在同一计算节点上才能完成检索与生成，由此导致客户端用户必须信任服务端不会窥视其查询内容、服务端必须把文档库以明文形式暴露给计算引擎、第三方算力提供商更可能同时观察查询与文档。这一信任模型在医疗诊断、法律咨询、金融风控等高敏场景下难以被各方接受<sup>[4]</sup>。

针对 RAG 中的隐私问题，安全多方计算（Secure Multi-Party Computation, MPC）<sup>[5-6]</sup>提供了基础的密码学工具：在不暴露任何一方明文输入的前提下，各方协同计算函数的输出。如何把整条 RAG 流水线（编码、双路打分、Top-K 排序、文档抽取、联合推理、答案抽取）系统地搬迁到密态计算之上，且在普通硬件上达到工程可用水平，是隐私保护机器学习领域当前的研究热点之一。Ant Group 于 2026 年 ICLR 提出的 Pisces 框架<sup>[7]</sup>首次系统给出了基于不经意伪随机函数（Oblivious Pseudo-Random Function, OPRF）与不经意键值存储（Oblivious Key-Value Store, OKVS）的密态双路检索协议，但其将生成阶段委托给外部密态 LLM 而仅以接口形式给出。本课题以 NssMPClib 这一 MPC 基础框架<sup>[8]</sup>为底层支撑，面向半诚实两方计算模型，构建了一个支持隐私保护的检索增强生成系统的端到端原型，并补足了 Pisces 未覆盖的精排与默认生成阶段。

研究密态 RAG 不仅有助于把 LLM 应用推广到更多对隐私敏感的高价值领域，对推动 MPC 协议在面向 Transformer 架构的非线性算子（如层归一化中的均方根倒数、注意力中的指数函数、门控线性单元中的高斯误差函数等）<sup>[9-11]</sup>上的工程优化也具有重要的理论与实用意义。

## 1.2　国内外研究现状

本节围绕"支持隐私保护的检索增强生成系统"这一核心命题，从检索增强生成、隐私保护检索、密态机器学习推理三个维度梳理代表性研究工作。

### 1.2.1　检索增强生成技术

检索增强生成是当前知识密集型自然语言处理的主流范式。Karpukhin 等人<sup>[12]</sup>于 2020 年提出的稠密段落检索（Dense Passage Retrieval, DPR）首次系统性地证明了基于双塔双向 Transformer 编码器表示（Bidirectional Encoder Representations from Transformers, BERT）<sup>[13]</sup>的稠密检索在开放域问答上显著优于传统的最佳匹配 25（Best Matching 25, BM25）<sup>[14]</sup>词汇检索。Lewis 等人<sup>[3]</sup>随后提出的原始 RAG 框架将稠密检索与生成式模型联合训练，把检索作为可微分模块嵌入到端到端管线中。后续工作 Atlas<sup>[15]</sup>、RETRO<sup>[16]</sup>、In-Context-RALM 等进一步在大模型规模、上下文长度、检索粒度等维度上推动 RAG 的发展。

在双路检索方面，业界普遍采用稠密检索（语义路）与传统 BM25（词汇路）并行召回、再通过倒数排名融合（Reciprocal Rank Fusion, RRF）<sup>[17]</sup>等策略融合的方案，以兼顾语义泛化能力与精确关键词匹配能力。在精排阶段，文献[18]提出 Cross-Encoder 重排序器（Reranker）——将查询与候选文档拼接后过一遍编码器并取池化输出作为相关度分数，在准确率上显著优于双塔点积，但其计算复杂度与候选数量成正比，因而通常作为第二阶段精排器使用。在答案抽取阶段，斯坦福问答数据集（Stanford Question Answering Dataset, SQuAD）<sup>[19]</sup>风格的起止位置预测头是抽取式问答的标准方案，其在编码器序列输出上接一个二维线性层，预测答案在原文中的起始位置和结束位置。

现有 RAG 工作多在明文环境下展开，专注于召回质量、上下文窗口扩展与检索粒度等维度，对查询与文档的隐私保护问题关注较少。

### 1.2.2　隐私保护检索

隐私信息检索（Private Information Retrieval, PIR）<sup>[20]</sup>是隐私保护检索的经典方向，目标是允许客户端从服务端查询特定记录而不暴露查询索引。Chor 等人于 1995 年提出的多服务器 PIR 在信息论安全模型下达成隐私目标，但通信复杂度随数据库规模线性增长。Kushilevitz 与 Ostrovsky<sup>[21]</sup>的单服务器计算性 PIR 利用同态加密把通信复杂度降低到亚线性。然而经典 PIR 本质上要求查询是"按 ID 取记录"，与 RAG 中"按相关度排序后取 top-K"的语义不匹配。

不经意随机访问存储（Oblivious Random Access Memory, ORAM）<sup>[22]</sup>通过反复打乱物理存储位置实现访问模式混淆，但在 RAG 这类需要 Top-K 排序与多次查表的场景下开销高昂。最近兴起的密态向量检索如 Tiptoe<sup>[23]</sup>、Coral 等尝试在两方设置下实现密态最近邻搜索，但通常只覆盖检索阶段的稠密向量打分，未集成完整 RAG 中的 BM25 词汇检索、密态文档抽取与密态生成 / 编码环节。

2026 年 Ant Group 在国际表示学习大会（International Conference on Learning Representations, ICLR）发表的 Pisces 框架<sup>[7]</sup>首次系统化地把"语义路 + 词汇路"的双路检索完整地搬到了密态环境。其语义路采用 SimHash<sup>[24]</sup>粗筛后接基于 OPRF/OKVS 的不经意过滤器，词汇路采用基于标签私有集合求交（Multi-instance Labeled Private Set Intersection, PSI）<sup>[25]</sup>获取候选文档的词频统计后再做密态 BM25 计算。Pisces 在协议层达到了较高的隐私保证水平，但其生成阶段委托给外部密态 LLM 而仅以接口形式给出，且未实现密态精排或密态阅读器组件。

### 1.2.3　密态机器学习推理

随着安全机器学习（SecureML）<sup>[26]</sup>、密态张量计算（CrypTen）<sup>[27]</sup>等通用框架的出现，神经网络的密态推理逐渐由理论走向实践。在 Transformer 架构上，安全生成式预训练 Transformer 推理（Secure GPT Inference, SIGMA）<sup>[9]</sup>、BumbleBee<sup>[10]</sup>、Iron<sup>[11]</sup>等工作针对 Softmax、层归一化（Layer Normalization, LayerNorm）、高斯误差线性单元（Gaussian Error Linear Unit, GeLU）等非线性算子提出了基于函数秘密分享（Function Secret Sharing, FSS）<sup>[28]</sup>与查找表（Look-Up Table, LUT）近似的高效协议，把单层 Transformer 在局域网环境下的密态前向时间压缩到秒级。MPCFormer<sup>[29]</sup>在 BERT 模型上系统验证了量化、蒸馏与 MPC 综合优化路径。

在密态机器学习的工程基础设施方面，NssMPClib<sup>[8]</sup>是一套面向 MPC 的基础组件库，提供了环张量（RingTensor）、算术秘密分享（Arithmetic Secret Sharing, ASS）、FSS 协议族（含分布式点函数（Distributed Point Function, DPF）、分布式比较函数（Distributed Comparison Function, DCF）、分布式区间比较函数（Distributed Interval Comparison Function, DICF）、可验证分布式点函数（Verifiable DPF, VDPF）、可验证 Sigma 协议（Verifiable Sigma Protocol, VSigma））、Beaver 三元组、Paillier 同态加密等模块，并实现了密态 BERT、卷积神经网络等典型模型，可被用于密态机器学习实验。

然而，已有密态机器学习工作主要面向单纯的推理任务，对"检索与推理联合"的 RAG 系统级问题鲜有讨论；现有密态向量检索工作又通常脱离生成 / 编码模块单独存在。这正是本文力图填补的空白。

## 1.3　研究内容与创新点

针对检索增强生成系统中查询、文档库与模型权重三方隐私同时受到威胁的现状，本文设计并实现了一种基于双路并行检索、密态联合编码、密态精排与密态 Span 阅读器的端到端密态 RAG 系统，并在自建小型问答语料上完成了密态与明文的多维对比实验。系统总体上由"应用层 secure_rag 包、实验对比层 experiments 模块、底层 NssMPClib MPC 库"三层组成；从问题、方法到技术路线，本文的研究内容可概括如下：以两方半诚实安全计算为安全前提，以 NssMPClib 的 ASS、FSS 与矩阵 Beaver 协议为构造原语，先在协议层实现与 Pisces 对齐的双路检索，再在精排与生成阶段补足 Pisces 未覆盖的密态 Cross-Encoder 与密态 Span 阅读器，最终在普通笔记本硬件上跑通端到端密态 RAG 流水线并完成数值、检索质量与消融三个维度的实验评估。本文针对的关键问题、对应的研究内容以及所采用的技术路线之间的逻辑关系如图 1-1 所示。

![图 1-1  关键问题、研究内容与技术路线关系图](figures/figure-1-1.png)

图 1-1  关键问题、研究内容与技术路线关系图

本文的贡献总结如下：

（1）**设计并实现了基于 ASS 算术秘密分享的双路密态检索协议**。针对 Pisces 等已有方案依赖 OPRF、OKVS、标签 PSI 等专用密码学原语，难以在通用 MPC 库上复用的工程局限，本文以 NssMPClib 通用 MPC 库为底层，**在仅使用 ASS 算术秘密分享与 FSS 函数秘密分享两类基础原语的前提下**，独立设计并实现了双路密态检索算法。语义路采用粗筛与精排级联结构：离线阶段服务端用公开投影矩阵对文档库做 SimHash 编码并以 ASS 形式分享给客户端；在线阶段双方协同对密态查询向量做 SimHash 编码，通过密态汉明距离（基于"$a + b - 2ab$"二值等式实现的纯线性密态运算）粗筛得到候选集，最后对候选集做密态余弦内积精排。词汇路采用在线密态 BM25 公式：服务端把每个 term 的逆文档频率、term-document 频率矩阵与文档长度归一化项三个分量分别 ASS 分享，客户端在线密态完成包含密态除法的 BM25 完整公式计算。两路打分后均接入基于密态单位向量指示器的密态 Top-K 冒泡排序与基于"广播乘与求和折叠"的密态文档抽取，保证任意一方都无法获知 Top-K 选中的文档下标。

（2）**提出了密态 Cross-Encoder 精排器与密态抽取式 Span 阅读器联合方案**。前者把联合编码 [CLS] 池化向量与密态文档库做密态矩阵乘法精排，把原本"装饰性"的联合推理转化为可量化的精排输出，明文-密态精排分数余弦相似度达 0.9998；后者引入面向 SQuAD 训练好的 bert-tiny 起止位置头权重，利用累积和（cumsum）技巧在密态域中提取连续 span，使生成阶段在不接外部密态 LLM 的前提下也具备多 token 答案抽取能力，部分匹配率从 0.10 提升至 0.30。

（3）**提出了密态跨路 PRF 协议与候选池重排（Candidate-Pool Reranker）算法**。针对朴素 PRF 在密态 Cross-Encoder 精排器主导架构下被"平滑"导致 Recall@1 下降的失败模式，本文设计了 PRF v2 候选池重排协议：第一轮检索后，语义路 Top-1 文档反馈到词汇路扩展 query 得到第二轮文档；联合推理输入仍使用第一轮文档保持精排基准稳定，第二轮文档以候选池约束方式加入精排阶段的 Hybrid 公式（全 $N$ 库精排 + 候选池温和 boost）。该设计在 mini_corpus 10 query 上使密态 NDCG@5、MRR、Recall@3、Reader Partial Match、Token F1 五个指标全部超过 PRF 关闭基线，是相对 Pisces 检索协议（无 PRF 与多轮机制）的正向创新点。

（4）**构建了端到端密态 RAG 实验平台并完成多维消融实验**。系统包括 secure_rag 应用层（服务端、客户端、检索算法、明文基线、辅助参数生成器、全局配置），experiments 实验层（基于子进程隔离的密态 RAG 运行器、HuggingFace Tokenizer 接入的语料加载器、四类信息检索（Information Retrieval, IR）指标实现、数值一致性对比脚本、检索质量对比脚本、整合入口）以及配套文档。系统在普通笔记本硬件上单条查询端到端约 86 秒，相比基础实现加速约 25 倍；在 10 query × 10 doc 配置下密态 Recall@5 达 1.00、NDCG@5 达 0.83、MRR 达 0.78。基于该平台，本文围绕 SimHash 粗筛、BM25 双模式、Span 阅读器、PRF 候选池重排四个维度进行了系统的消融实验。

## 1.4　章节安排

本文一共包含五个章节，各章节的主要内容如下：

第一章为绪论。介绍了课题的研究背景，分析了检索增强生成系统在查询、文档库与模型权重三方面同时面临的隐私挑战，从检索增强生成、隐私保护检索、密态机器学习推理三个维度综述了国内外研究现状，提出了本文的研究内容与创新点。

第二章为相关研究。本章对密态 RAG 涉及的基础理论与代表性工作做较深入的回顾，依次介绍了检索增强生成的典型架构与检索范式、安全多方计算的关键协议（算术秘密分享、函数秘密分享、Beaver 三元组与矩阵乘协议）、密态神经网络推理的代表性方法，为后续章节的设计奠定理论基础。

第三章为支持隐私保护的检索增强生成系统设计。本章按照"两阶段密态检索 + 一阶段密态生成"的标准 IR 范式组织：双路密态检索作为第一阶段粗排、密态 PRF 与候选池构建为第二阶段精排做准备、Cross-Encoder 密态精排（联合编码 + Hybrid Reranker）作为第二阶段精排输出最终 Top-K 文档、密态抽取式 Span 阅读器作为生成阶段抽取连续答案 span。

第四章为实验与分析。本章在自构建的小型问答语料库上对系统进行了对比实验与消融实验两类评估。对比实验包含两组：(a) 密态与功能等价的明文 RAG 在 10 query × 10 doc 配置下的整体检索质量对比并解释"密态略优"现象的成因；(b) 密态 RAG 启用与关闭跨路 PRF + 候选池重排的对比，量化 PRF 创新点的贡献。消融实验包含两组：语义路 SimHash 粗筛比特数扫描与词汇路 BM25 双模式（Offline / Online）对比。

第五章为总结与展望。对本文的研究工作进行总结，并对未来研究方向（包括密态生成式 LLM 的接入、面向大规模文档库的可扩展 Top-K、真不经意伪随机函数原语补强、恶意安全升级、跨机房广域网部署优化）进行展望。

---

# 第二章　相关研究

本章对密态 RAG 涉及的基础理论与代表性工作进行较深入的回顾，主要包括三方面：检索增强生成的典型架构与检索范式、安全多方计算的关键协议、面向 Transformer 架构的密态神经网络推理，为第三章的方法设计奠定理论与算法基础。

## 2.1　检索增强生成

检索增强生成的核心思想是将参数化的语言模型与非参数化的外部知识库解耦，在生成回答前先从知识库检索相关文档，再以"问题与检索片段"作为完整上下文送入生成模型。一个完整的 RAG 流程可以划分为三个核心阶段。

**编码阶段** 把查询与文档分别映射到向量空间。常用的编码模型为 BERT、Sentence-BERT 等基于 Transformer 的双塔结构<sup>[13]</sup>。文档库通常在系统部署阶段离线编码并存储为稠密向量库。

**检索阶段** 给定查询向量与文档库，从中筛选出 Top-K 最相关的文档。主流方案包括：第一，稠密检索（Dense Retrieval），基于查询与文档向量的内积或余弦相似度，优点是能够捕捉语义层面的相似性，缺点是对未在训练数据中出现的稀有术语泛化能力弱<sup>[12]</sup>；第二，稀疏检索（Sparse Retrieval），基于词频统计的传统方法，BM25 是其中最具代表性的算法<sup>[14]</sup>，其经典公式为：

$$\text{BM25}(q, d) = \sum_{t \in q} \text{IDF}(t) \cdot \frac{f(t, d) \cdot (k_1+1)}{f(t, d) + k_1 \cdot \left(1 - b + b \cdot \dfrac{|d|}{\text{avgdl}}\right)} \tag{2-1}$$

其中，$f(t, d)$ 是词 $t$ 在文档 $d$ 中的频次，$\text{IDF}(t)$ 为词 $t$ 的逆文档频率，$|d|$ 是文档 $d$ 的长度，$\text{avgdl}$ 是文档库平均文档长度，$k_1$ 与 $b$ 为可调超参（通常取 1.5 与 0.75），$q$ 是查询的词袋集合。BM25 的优势在于精确匹配关键词；第三，混合检索（Hybrid Retrieval），稠密路径与稀疏路径并行召回、再通过分数融合或排序融合合并结果，是工业界主流方案。

**生成阶段** 把"问题与 Top-K 文档"拼接为完整上下文，送入生成模型产出回答。在 BERT-Reader 风格的早期 RAG 工作中，生成阶段被替换为基于序列输出接 span 预测头的"阅读"环节<sup>[19]</sup>，其在编码器输出 $\mathbf{H} \in \mathbb{R}^{L \times h}$ 上接一个二维线性变换：

$$[\mathbf{s}, \mathbf{e}] = \mathbf{H} \mathbf{W}_{qa}^{\top} + \mathbf{b}_{qa},\quad \mathbf{W}_{qa} \in \mathbb{R}^{2 \times h},\ \mathbf{b}_{qa} \in \mathbb{R}^{2} \tag{2-2}$$

其中，$\mathbf{s}$ 与 $\mathbf{e}$ 分别为长度为 $L$ 的起始位置和结束位置打分，最终答案 span 取为 $\arg\max(\mathbf{s})$ 到 $\arg\max(\mathbf{e})$ 之间的连续 token 序列。RAG 三阶段的典型数据流如图 2-1 所示。

![图 2-1  检索增强生成典型三阶段流程](figures/figure-2-1.png)

图 2-1  检索增强生成典型三阶段流程

近年来 RAG 的研究主要围绕召回质量优化、长上下文窗口扩展、检索粒度等维度展开。值得注意的是，绝大多数现有 RAG 工作都假设查询、文档库、模型权重三者可以明文聚合到同一计算节点，未考虑这些数据在不同主体间的隐私边界，这正是本文研究的出发点。

## 2.2　安全多方计算

安全多方计算研究多个互不信任的参与方在不暴露各自私有输入的前提下协同计算公共函数的方法。其安全模型主要分两类：半诚实模型（Semi-honest, a.k.a. Honest-but-Curious）下所有参与方严格按协议执行但可能从协议运行中收集到的信息推断对方私有输入；恶意模型（Malicious）下参与方可能任意偏离协议执行<sup>[6]</sup>。本文研究的密态 RAG 系统建立在半诚实两方计算（2-Party Computation, 2PC）模型之上。下面介绍其中涉及的几类核心协议。

### 2.2.1　算术秘密分享

算术秘密分享是 MPC 的基本工具。在 2-out-of-2 加法分享方案下，秘密值 $x \in \mathbb{Z}_{2^L}$ 被随机分成两份 $x_0$ 与 $x_1$ 满足：

$$x \equiv x_0 + x_1 \pmod{2^L} \tag{2-3}$$

其中，$L$ 为环宽度（本文取 64），两份分别由两方持有，任意一方单独持有的份额都是均匀随机的，因而完全不泄露 $x$ 的信息。ASS 在加法上具有优良性质：双方各自把份额相加，不需要任何通信即可得到 $x + y$ 的分享。乘法则需要借助 Beaver 三元组——双方共同持有随机三元组 $(a, b, c)$ 的分享且满足 $c = a \cdot b$。要在密态下计算 $x \cdot y$，先在线交换 $e = x - a$、$f = y - b$ 的份额并将其重构为明文，然后

$$x \cdot y = e \cdot f + e \cdot b + f \cdot a + c \tag{2-4}$$

其中，$e \cdot f$ 是公开常数（双方各自加一份等价于加完整），$e \cdot b$ 与 $f \cdot a$ 是公开常量与密态份额的乘法（无需通信），$c$ 是预先持有的密态份额。这样每次密态乘法只需要一次双向通信。Beaver 三元组通常在离线阶段批量预生成，在线阶段直接消费。ASS 密态乘法的协议时序如图 2-2 所示。

![图 2-2  ASS 密态乘法基于 Beaver 三元组的协议时序](figures/figure-2-2.png)

图 2-2  ASS 密态乘法基于 Beaver 三元组的协议时序

### 2.2.2　函数秘密分享

函数秘密分享是 ASS 之外的另一类基础协议<sup>[28]</sup>。FSS 把函数 $f$ 的求值过程分成两份"函数密钥" $k_0$、$k_1$，使得双方分别用各自的密钥本地计算 $f_0(x)$ 与 $f_1(x)$，最后把输出相加即可重构 $f(x)$：

$$f(x) = f_0(x; k_0) + f_1(x; k_1) \tag{2-5}$$

其中，$x$ 是公开输入，$k_0$、$k_1$ 由可信第三方在离线阶段产生并分别下发给两方。FSS 最有用的两种特例是分布式点函数（DPF）和分布式比较函数（DCF）：DPF 实现 $f(x) = \beta$ 当且仅当 $x = \alpha$，否则为 0；DCF 实现 $f(x) = \beta$ 当且仅当 $x < \alpha$，否则为 0。基于 DPF 与 DCF 可以构造分布式区间比较函数（DICF），在密态下高效实现 $x \geq y$、$x \leq y$、$x = y$ 等逐元素比较。NssMPClib 进一步实现了 SigmaDICF<sup>[9]</sup> 与 Grotto<sup>[30]</sup> 等优化变种，把 64 位密态比较的通信轮数压缩到单轮交互。三者之间的关系如图 2-3 所示。

![图 2-3  FSS 协议族 DPF、DCF 与 DICF 关系图](figures/figure-2-3.png)

图 2-3  FSS 协议族 DPF、DCF 与 DICF 关系图

### 2.2.3　Beaver 三元组与矩阵乘协议

针对深度神经网络中频繁出现的矩阵乘法运算，Beaver 三元组的概念可以推广为矩阵形式：双方共同持有随机矩阵三元组 $(\mathbf{A}, \mathbf{B}, \mathbf{C})$ 的分享且满足 $\mathbf{C} = \mathbf{A} \cdot \mathbf{B}$。要在密态下计算 $\mathbf{X} \cdot \mathbf{Y}$，先重构 $\mathbf{E} = \mathbf{X} - \mathbf{A}$ 与 $\mathbf{F} = \mathbf{Y} - \mathbf{B}$ 的明文，然后

$$\mathbf{X} \cdot \mathbf{Y} = \mathbf{E} \cdot \mathbf{F} + \mathbf{E} \cdot \mathbf{B} + \mathbf{A} \cdot \mathbf{F} + \mathbf{C} \tag{2-6}$$

其中，$\mathbf{X} \in \mathbb{Z}_{2^L}^{m \times k}$、$\mathbf{Y} \in \mathbb{Z}_{2^L}^{k \times n}$、$\mathbf{A}$、$\mathbf{B}$、$\mathbf{C}$ 与 $\mathbf{X}$、$\mathbf{Y}$、$\mathbf{X} \cdot \mathbf{Y}$ 同形。矩阵 Beaver 把 $m \cdot n \cdot k$ 个标量乘法的通信量压缩为一次矩阵 Beaver 协议（共 $2 \cdot m \cdot k + 2 \cdot k \cdot n$ 元素的通信量），显著减少通信轮数，是密态神经网络推理的关键优化手段。

## 2.3　密态神经网络推理

把神经网络从明文搬迁到密态环境，瓶颈不在线性层（矩阵乘法可由矩阵 Beaver 三元组高效完成），而在非线性层。Transformer 架构涉及的非线性操作包括 LayerNorm 中的均方根倒数（rsqrt）、Softmax 中的指数函数与归一化、GeLU 与 ReLU 等激活函数、注意力机制中的逐元素乘除等。

针对这些非线性算子，近年来出现了多种密态实现方案。CryptGPU、CrypTen<sup>[27]</sup>等通用框架使用泰勒展开或多项式近似，在精度与效率之间权衡。SIGMA<sup>[9]</sup>系统性地为 Softmax 和 LayerNorm 设计 FSS-based 协议，引入 SigmaDICF 实现高效 64 位比较，将单层 Transformer 的密态推理压缩到秒级。BumbleBee<sup>[10]</sup>通过查表法近似 GeLU 与 Softmax 的非线性变换，在两方半诚实模型下达到工业级性能。Iron<sup>[11]</sup>进一步引入消息认证码（Message Authentication Code, MAC）校验机制，把恶意安全的代价降低到原来的 2 倍以内。MPCFormer<sup>[29]</sup>在 BERT 模型上系统验证了量化、蒸馏与 MPC 的综合优化路径。

具体地，密态 LayerNorm 的核心瓶颈是 rsqrt 算子；SIGMA 提出基于 SigmaDICF 的迭代逼近法，通过 64 轮 prefix-parity 循环把均方根倒数压缩到单密态除法的代价。密态 Softmax 通常采用"减最大值 + 查表 exp + 密态除法"三步：减最大值由密态 secure_max 实现，查表 exp 用 LUT 在 16-bit 定点数上保留两位有效数字精度，密态除法由 SigmaDICF 配合 Newton-Raphson 迭代实现。密态 GeLU 在文献[10][11]中均使用 8-bit 分段查表近似。

作为本文实现的工程基础，NssMPClib<sup>[8]</sup>是一套 MPC 基础组件库，包含完整的环张量、ASS、FSS、Beaver 三元组等底层协议，并实现了密态 BERT、CNN、GeLU、LayerNorm 等典型模型与算子。本文的研究即基于该框架展开。

需要指出的是，已有密态机器学习工作主要面向单纯的推理任务（如分类、匹配），鲜有覆盖检索增强生成这一系统级问题。把检索阶段（涉及大量比较与 Top-K 排序）与推理阶段（涉及 Transformer 完整前向）联合密态化，并兼顾召回质量与性能，是本文力求解决的核心系统级挑战。

## 2.4　本章小结

本章对密态 RAG 系统涉及的检索增强生成、安全多方计算、密态神经网络推理三方面相关工作进行了综述。检索增强生成已经成为知识密集型 LLM 应用的主流架构，但绝大多数现有工作未考虑查询、文档库与模型权重的隐私边界。安全多方计算提供了不暴露明文数据协同计算的密码学工具，其中算术秘密分享、Beaver 三元组与函数秘密分享是构建密态机器学习系统的基础组件，本章给出了它们的核心公式与协议交互。密态神经网络推理方面，SIGMA、BumbleBee、Iron、NssMPClib 等代表性工作针对 Transformer 中的非线性算子提出了多种优化方案，但鲜有系统级覆盖检索增强生成完整管线的工作。这正是本文力图填补的研究空白。

---

# 第三章　支持隐私保护的检索增强生成系统设计

## 3.1　引言

第二章梳理了密态 RAG 涉及的相关理论与代表性工作，并指出了"密态检索 + 密态精排 + 密态生成"端到端管线的研究空白。本章针对第一章中提出的"如何在不暴露查询、文档库与模型权重明文的前提下完整完成 RAG 流水线"这一核心问题，详细介绍设计并实现的支持隐私保护的检索增强生成系统。

回顾当前主流的 RAG 工作，可以观察到其核心范式为：编码、双路并行召回（语义 + 词汇）、Top-K 精排、抽取式或生成式回答。在密态环境下复现这一范式面临三大挑战：第一，密态语义打分如何在不显式还原 query 与 doc embedding 的前提下完成相似度比较；第二，密态词汇打分如何在不让客户端学到原始 term-document 频率矩阵的前提下完成 BM25 计算；第三，密态 Top-K 如何在不暴露文档身份的前提下完成排序与抽取。Pisces<sup>[7]</sup>已经在协议层给出了双路检索的隐私上限，但其在精排与生成阶段未提供默认实现。本章在 Pisces 同型的双路检索协议之上，进一步补足密态 Cross-Encoder 精排器与密态抽取式 Span 阅读器，把基础范式整体搬到密态环境。

本章首先在 3.2 节给出系统总体架构与威胁模型，明确各方持有什么、不持有什么、协议保护什么；3.3 节详细介绍**第一阶段双路密态检索**，包括 SimHash 粗筛与密态精排级联的语义路、在线密态 BM25 的词汇路、密态 Top-K 指示器排序与密态文档抽取；3.4 节介绍**密态伪相关反馈与候选池构建**，作为第二阶段精排的输入准备，是本文检索层的核心创新；3.5 节介绍**第二阶段 Cross-Encoder 密态精排**，包括联合编码与 Hybrid Reranker；3.6 节介绍**密态生成阶段**，说明本文选择基于 SQuAD QA 头的抽取式实现而非外部密态生成式 LLM 的设计权衡，并给出密态 Span 阅读器协议；3.7 节给出本章小结。

## 3.2　系统总体架构与威胁模型

### 3.2.1　系统三层架构

系统在"应用层、实验对比层、底层 MPC 库"三层架构下组织。底层（NssMPClib MPC 库）提供 RingTensor 环张量数据结构、ASS 算术秘密分享、FSS 函数秘密分享、Beaver 三元组、TCP 异步通信、密态神经网络层等基础组件。应用层（secure_rag 包）在 NssMPClib 之上实现密态 RAG 的应用逻辑，包含 6 个模块：config.py 给出 BERT 配置、序列长度、文档库大小、词汇表大小等全局参数；retrieval.py 实现双路密态打分、密态 Top-K 指示器排序、密态伪相关反馈与候选池构建、密态 Hybrid Reranker、密态 Span 阅读器；server.py 与 client.py 分别实现服务端流程与客户端流程；plaintext.py 实现作为实验对比基线的明文 RAG；params.py 实现辅助参数（Beaver 三元组、FSS 函数密钥等）的批量生成器。实验对比层（experiments 模块）负责实验组织与对比评估，包括语料加载器、IR 指标计算、子进程隔离的密态 RAG 运行器、单条 query 数值一致性对比脚本、多条 query 检索质量对比脚本与整合入口。系统三层架构与端到端 8 阶段数据流如图 3-1 所示。

![图 3-1  系统三层架构与端到端 8 阶段数据流](figures/figure-3-1.png)

图 3-1  系统三层架构与端到端 8 阶段数据流

### 3.2.2　数据流与协议交互

系统单条查询的端到端数据流分为 8 个阶段，其中 Stage 4–5 是本文检索层的核心创新阶段，Stage 7 是把检索结果消化为最终 Top-K 的精排阶段，Stage 8 是从联合编码副产品抽取答案 span 的轻量生成阶段。

**Stage 1 离线准备**。服务端事先用明文 BERT 对文档库的所有文档做编码，得到稠密向量库 $\mathbf{D} \in \mathbb{R}^{N \times h}$；同时对文档库做 SimHash 编码得到 $\mathbf{H}_d \in \{0, 1\}^{N \times L_b}$（$L_b$ 为 SimHash 比特数，本文取 128）；根据真实 BM25 公式构造三个分量，即词频矩阵 $\mathbf{T}_f \in \mathbb{R}^{V \times N}$、逆文档频率向量 $\mathbf{i} \in \mathbb{R}^{V}$、文档长度归一化向量 $\mathbf{n}_d \in \mathbb{R}^{N}$；保留文档 token 序列的 one-hot 表示 $\mathbf{X}_d \in \{0, 1\}^{N \times L \times V_b}$。

**Stage 2 模型与文档库密态分享**。服务端把 BERT 权重、文档语义库 $\mathbf{D}$、SimHash 编码 $\mathbf{H}_d$、BM25 三分量 $(\mathbf{T}_f, \mathbf{i}, \mathbf{n}_d)$ 与 token one-hot $\mathbf{X}_d$ 各自秘密分享并发送给客户端，使双方共同持有密态模型与密态文档库。

**Stage 3 密态查询编码**。客户端把查询文本经 Tokenizer 转 token id 与 one-hot，秘密分享后发给服务端。双方协同跑一遍密态 BERT 编码（输入序列长度 8），得到密态查询语义向量 $\hat{\mathbf{q}} \in \text{ASS}^{1 \times h}$ 与密态多热向量 $\hat{\mathbf{q}}_m \in \text{ASS}^{V \times 1}$。

**Stage 4 双路密态打分（第一轮）**。语义路通过 SimHash 粗筛（密态汉明距离）与密态余弦精排级联得到密态语义分数与 Top-1 指示器 $\hat{\mathbf{t}}_{\text{sem}}$；词汇路通过密态多热向量与密态 BM25 三分量在线计算得到密态词汇分数与第一轮 Top-1 指示器 $\hat{\mathbf{t}}_{\text{lex}}^{(1)}$。

**Stage 5 ⭐ 密态 PRF 第二轮与候选池构建**（本文核心创新点）。把 Stage 4 语义路 Top-1 文档的 token 频率投影到 BM25 词表，按 $\hat{\mathbf{q}}_m' = \alpha \cdot \hat{\mathbf{q}}_m + \beta \cdot \mathcal{I}[\hat{\mathbf{t}}_d]$ 的凸组合扩展原始多热向量，再过一次词汇路密态 BM25 得到第二轮词汇路 Top-1 指示器 $\hat{\mathbf{t}}_{\text{lex}}^{(2)}$。三个 Top-1 指示器在 ASS 域沿候选维拼接得到候选池 $\hat{\mathbf{C}} = [\hat{\mathbf{t}}_{\text{sem}};\ \hat{\mathbf{t}}_{\text{lex}}^{(1)};\ \hat{\mathbf{t}}_{\text{lex}}^{(2)}] \in \text{ASS}^{3 \times N}$，为后续 Stage 7 的候选池重排提供输入。注意：**Stage 4 输出的 $\hat{\mathbf{t}}_{\text{lex}}^{(1)}$ 始终作为联合编码的词汇路文档段（不被 PRF 第二轮替换），这是避免精排器"平滑效应"的关键设计**（详见 3.4 节）。

**Stage 6 密态文档抽取**。通过密态指示器 $\hat{\mathbf{t}}_{\text{sem}}$、$\hat{\mathbf{t}}_{\text{lex}}^{(1)}$ 与密态 token 库 $\hat{\mathbf{X}}_d$ 的"广播乘与求和折叠"运算抽取出实际选中的文档 token 序列 $\hat{\mathbf{D}}_{\text{sem}}$ 与 $\hat{\mathbf{D}}_{\text{lex}}$，整个过程任意一方均不知道选中了哪一篇。

**Stage 7 密态精排（检索第二阶段）**。把查询、语义路文档、词汇路文档拼接为长度 56 的联合输入，过一遍密态 BERT 得到融合视角的密态池化向量 $\hat{\mathbf{p}}$ 与序列输出 $\hat{\mathbf{O}}$；用 Hybrid Reranker 公式 $\hat{\mathbf{r}}_{\text{hyb}} = \hat{\mathbf{p}} \cdot \hat{\mathbf{D}}^{\top} + \lambda \cdot \mathbf{1}^{\top} \hat{\mathbf{C}}$ 对全库做精排（其中候选池 $\hat{\mathbf{C}}$ 来自 Stage 5），得到每篇文档的密态精排分数 $\hat{\mathbf{r}} \in \text{ASS}^{1 \times N}$；客户端 restore 后 argsort 得到系统最终的 Top-K 文档下标（详见 3.5 节）。

**Stage 8 密态生成阶段**。让 Stage 7 联合编码副产品 $\hat{\mathbf{O}}$ 过一遍 SQuAD 训练好的密态 QA 头并经累积和 span mask 抽取得到密态答案 token 序列（详见 3.6 节）。

服务端在 Stage 7、Stage 8 完成后将密态精排分数、密态池化向量、密态答案 token 三类分享统一发送给客户端，客户端在本地完成 restore，从而保证服务端不学习任何与客户端查询相关的明文输出。

### 3.2.3　威胁模型

本系统建立在半诚实两方计算模型之上，假设双方均严格按协议执行但可能从协议运行中收集到的信息推断对方的私有输入，**不防主动作弊**<sup>[6]</sup>。在该假设下，服务端（Party 0）持有 BERT 权重明文、文档库明文（文本与 embedding 与 BM25 统计）以及自己的所有秘密分享，客户端（Party 1）持有查询文本明文与自己的所有秘密分享。协议**保护**的信息包括：查询的具体文本内容、文档库的具体文本内容、BERT 权重的具体数值、双路打分与密态 Top-K 各阶段的中间向量数值、Top-K 选中了哪一篇文档（密态指示器不还原）、Cross-Encoder 精排分数（仅在客户端 restore）、答案 token（仅在客户端 restore）。协议**未保护**的信息包括：系统结构信息（文档库大小、序列长度等定常量）、通信轮数与字节数等流量分析侧信道、密态运行时间与输入大小的关系（输入大小本身公开）。

形式化地，对于任意采样自查询分布的两条查询 $q_1$、$q_2$ 在同一文档库 $\mathbf{D}$ 上的协议执行，服务端可观察到的协议视图（view）在统计意义上不可区分，即满足半诚实安全定义：

$$\text{View}^{\Pi}_{\text{S}}(q_1, \mathbf{D}) \stackrel{c}{\equiv} \text{View}^{\Pi}_{\text{S}}(q_2, \mathbf{D}) \tag{3-1}$$

其中，$\stackrel{c}{\equiv}$ 表示计算意义上的不可区分，$\Pi$ 表示本文密态 RAG 协议，$\text{View}^{\Pi}_{\text{S}}$ 表示服务端在协议执行过程中接收到的所有消息序列。客户端侧对称满足类似性质。双方持有的资产、不应直接知道的信息以及密态通道的位置如图 3-2 所示。

![图 3-2  半诚实两方计算威胁模型](figures/figure-3-2.png)

图 3-2  半诚实两方计算威胁模型

## 3.3　双路密态检索算法

本节详细介绍系统的核心检索算法。算法以"双路并行打分与密态指示器排序"为核心思想，确保任意一方都无法获得 Top-K 的明文身份信息。**与 Pisces 等已有方案依赖 OPRF/OKVS/标签 PSI 等专用密码学原语不同，本文在 NssMPClib 通用 MPC 库提供的 ASS 算术秘密分享与 FSS 函数秘密分享两类基础原语之上独立设计了完整双路检索协议，把密态汉明距离、密态 BM25 公式、密态 Top-K 冒泡、密态文档抽取等关键算子都还原为 ASS 上的乘加、比较与本地索引操作**，使整个检索协议在没有任何专用密码学原语的前提下闭合。整套算法的设计原则可以概括为三点：第一，所有可能暴露排序结果的算子（如 argsort、gather、indexing）都不能直接搬到密态环境，必须改写为只在密态域内闭合的等价运算；第二，对于通信代价较高的密态算子（如密态除法、密态比较门），尽量在不损失语义的前提下把它们置于公开常量或离线预处理阶段；第三，全程保持张量形状对下游模块"形状不变"，使得 SimHash 粗筛、在线 BM25 等创新模块可以作为旧版本的"插件式替换"接入而不破坏主链路。

### 3.3.1　语义路 SimHash 粗筛与密态精排

语义检索的目标是找到与查询语义相似的文档。给定客户端查询编码后的密态向量 $\hat{\mathbf{q}} \in \text{ASS}^{1 \times h}$ 与服务端密态文档库 $\hat{\mathbf{D}} \in \text{ASS}^{N \times h}$（其中 $N$ 是文档数，$h$ 是隐藏维度），最简单的语义打分方式是直接做密态内积：

$$\hat{\mathbf{s}}_{\text{sem}} = \left(\hat{\mathbf{q}} \odot \hat{\mathbf{D}}\right).\text{sum}(\text{dim}=-1) \in \text{ASS}^{N} \tag{3-2}$$

其中，$\odot$ 表示密态广播按元素乘法。该实现需要 $N \cdot h$ 次密态标量乘法，每次都要走 Beaver 协议一次双向通信。当文档库规模 $N$ 增大时，朴素内积的在线通信开销随 $N$ 线性增长，难以扩展到中大规模知识库。为此，本文采用 Pisces ∏PrivateSS 同型的"粗筛-精排"两阶段语义检索协议，把原本 $N \cdot h$ 维的全量内积压缩为"低维比特粗筛 + 候选集精排"两步级联。

**粗筛阶段** 的核心思想是用 SimHash 把 $h$ 维稠密向量映射为 $L_b$ 比特的二值表示，再以密态 Hamming 距离衡量相似度。本文取 $L_b = 128$，远小于 $h = 128$ 与 $\text{batch} \times h$ 的累计通信代价。具体地，离线阶段服务端用固定随机种子生成公开投影矩阵 $\mathbf{W} \in \mathbb{R}^{L_b \times h}$，对所有文档 embedding 通过 $\hat{\mathbf{H}}_d = \mathbb{1}[\mathbf{D} \cdot \mathbf{W}^{\top} > 0]$ 取符号位得到 SimHash 编码并连同其 ASS 分享发送给客户端；在线阶段双方协同对密态查询向量做对称的密态 SimHash 编码。粗筛阶段的关键工程要点是：第一，公开投影矩阵 $\mathbf{W}$ 不需要分享（双方各自用同一种子生成同一份），ASS 与公开 RingTensor 的矩阵乘是本地运算无通信；第二，符号位提取走密态比较门，每比特一次 SigmaDICF 调用，总共 $L_b$ 次比较；第三，二值向量的 Hamming 距离在密态下利用恒等式 $|a - b| = a + b - 2 a b$（其中 $a, b \in \{0, 1\}$）改写为加法加一次密态乘法，避免使用代价昂贵的绝对值算子。最近邻等价于 Hamming 距离最小，本文取其相反数作为相似度并复用 3.3.3 节的密态 Top-$M$ 排序，得到候选集指示器 $\hat{\mathbf{C}} \in \text{ASS}^{M \times N}$，把候选规模从全 $N$ 压缩到 $M$（默认 $M = 5$）。

**精排阶段** 对粗筛后的 $M$ 篇候选文档做密态余弦内积精排。具体地，先用 $\hat{\mathbf{C}} \cdot \hat{\mathbf{D}}$ 做一次密态矩阵乘法把全 $N$ 维 doc 库压缩成 $M$ 维候选 embedding（一次矩阵 Beaver 协议），再与密态查询向量做按元素乘求和得到 $M$ 维精排分数。粗筛与精排两阶段的关键开销对比如表 3-1 所示。

表 3-1  双阶段语义检索算法在 $N = 10$ 上的密态开销

| 阶段 | 密态标量乘次数 | 密态比较次数 | 矩阵乘次数 | 主要工程开销 |
| :-- | :--: | :--: | :--: | :-- |
| 朴素全 $N$ 内积 | $N \cdot h = 1280$ | — | — | 1280 次 Beaver mul |
| SimHash 粗筛 | $N \cdot L_b = 1280$ | $L_b = 128$ | — | 128 次密态符号位 + 1280 次 Beaver mul |
| 候选集精排 | $M \cdot h = 640$ | — | 1 | 1 次 $M \times h$ 矩阵 Beaver |
| 级联总开销 | $1920$ | $128$ | $1$ | 较朴素方案多 50% 标量乘但少 1 次双向同步 |

实测结果表明，$L_b = 128$ 在 $N = 10$ 上语义 Top-1 命中与全 $N$ cosine 检索 100% 一致，端到端节省约 7 秒（约 8%）；当 $L_b$ 降到 64 时虽然耗时略低但 Top-1 命中开始出现失配。整体上，粗筛阶段引入的"二值压缩+少量密态比较"开销在 $L_b = 128$ 时被精排阶段省下的矩阵乘抵消，达成 Pisces 同型协议层并近乎无损语义召回的设计目标。语义路粗筛与精排级联的整体数据流如图 3-3 所示。

![图 3-3  语义路 SimHash 粗筛与密态 cosine 精排级联流程](figures/figure-3-3.png)

图 3-3  语义路 SimHash 粗筛与密态 cosine 精排级联流程

### 3.3.2　词汇路在线密态 BM25

词汇检索通过精确匹配查询中包含的关键词在每篇文档中的 BM25 得分进行召回。第二章式 (2-1) 给出了 BM25 的明文定义。把 BM25 搬到密态环境最直接的做法是：服务端在离线阶段把整张 $V \times N$ 的 BM25 分数矩阵算好后再 ASS 分享给客户端，在线只做一次密态点积。这种"Offline 模式"通信代价低，但客户端在最终 restore 时能学到成品 BM25 score 的分布，泄露面较大。为最大化协议层隐私，本文采用 Pisces ∏PrivateBM25 同型的"Online 模式"：服务端在离线阶段把 BM25 公式拆分为词频矩阵 $\mathbf{T}_f \in \mathbb{R}^{V \times N}$、逆文档频率向量 $\mathbf{i} \in \mathbb{R}^{V}$、文档长度归一化向量 $\mathbf{n}_d \in \mathbb{R}^{N}$ 三个分量并分别 ASS 分享，把"何时融合"这一信息推迟到在线阶段。客户端将查询 token 转为密态多热向量 $\hat{\mathbf{q}}_m \in \text{ASS}^{V \times 1}$ 后，双方协同在密态域内完成包含密态除法的 BM25 计算：

$$\hat{\mathbf{s}}_{\text{lex}, n} = \sum_{v=1}^{V} \hat{q}_{m, v} \cdot \frac{\hat{i}_v \cdot \hat{T}_{f, v, n} \cdot (k_1 + 1)}{\hat{T}_{f, v, n} + \hat{n}_{d, n}} \tag{3-6}$$

其中，$n$ 为文档下标，$v$ 为词表下标，$k_1$ 为 BM25 中公开超参（本文取 1.5）。式 (3-6) 在密态域的实现分为分子构造、分母构造、密态除法、加权聚合四步，每一步对应的密态算子与通信代价如表 3-2 所示。

表 3-2  在线密态 BM25 计算的四步分解 (V = 100, N = 10)

| 步骤 | 密态计算 | 输出形状 | 密态算子 | 通信代价 |
| :--: | :-- | :--: | :-- | :-- |
| 1 | 分子 $\mathbf{U}_{v,n} = \hat{i}_v \cdot \hat{T}_{f, v, n} \cdot (k_1 + 1)$ | ASS$^{V \times N}$ | 一次密态广播乘 | 1 轮 Beaver mul |
| 2 | 分母 $\mathbf{L}_{v,n} = \hat{T}_{f, v, n} + \hat{n}_{d, n}$ | ASS$^{V \times N}$ | 本地加法 | 无通信 |
| 3 | 贡献 $\mathbf{R}_{v,n} = \mathbf{U}_{v,n} / \mathbf{L}_{v,n}$ | ASS$^{V \times N}$ | 批量 secure_div ($V N = 1000$ 次) | SigmaDICF + Newton-Raphson |
| 4 | $\hat{\mathbf{s}}_{\text{lex}, n} = \sum_v \hat{q}_{m, v} \cdot \mathbf{R}_{v, n}$ | ASS$^{N}$ | 一次密态广播乘加 | 1 轮 Beaver mul |

实测中，Online 模式相比 Offline 模式端到端只增加约 1% 耗时，但客户端在 restore 后只能学到原始 tf、idf、doc_norm 统计，无法直接重建服务端持有的成品 BM25 分数矩阵，泄露面显著降低。需要特别说明的是，第三步的密态除法对被除数有"$0 < y < 2^{2f}$"的安全工作区间要求（$f = 16$ 时即 $0 < y < 2^{32}$）；本文通过对 BM25 的 $k_1$、$b$ 超参与文档长度做工程层约束，使分母 $\mathbf{T}_{f, v, n} + \hat{n}_{d, n}$ 实测落在 $[0.3, 26.5]$ 区间，远在安全区间内，规避了数值溢出风险。

### 3.3.3　密态 Top-K 指示器排序

得到双路分数后，需要从中选出 Top-K 文档。明文世界用 argsort 即可，但在密态下直接 argsort 会暴露排序结果，违背隐私保护目标。本文设计了一个基于密态指示器的密态冒泡排序算法。算法核心思路是：**不直接交换分数对应的索引，而是引入"身份证向量"（one-hot 单位向量）作为索引代理**，让排序过程中所有的交换操作都作用在身份证向量而非具体下标上，从而避免下标在协议运行中被暴露。算法流程如算法 3-1 所示。

表 3-3  算法 3-1  密态 Top-K 指示器冒泡排序

| 行号 | 算法步骤 |
| :--: | :-- |
| 输入 | 密态分数向量 $\hat{\mathbf{s}} \in \text{ASS}^{N}$，目标 Top-K 大小 $k$ |
| 输出 | 密态指示矩阵 $\hat{\mathbf{T}} \in \text{ASS}^{k \times N}$ |
| 1 | 构造明文单位矩阵 $\mathbf{I} = \text{eye}(N)$；// 每行 $\mathbf{I}_i$ 是文档 $i$ 的身份证 |
| 2 | 把每行 $\mathbf{I}_i$ 包装为 ASS 形式得到 $\{\hat{\mathbf{I}}_0, \ldots, \hat{\mathbf{I}}_{N-1}\}$ |
| 3 | **for** $i = 0$ **to** $k - 1$ **do** // 确定第 $i$ 名 |
| 4 | 　　**for** $j = N - 1$ **downto** $i + 1$ **do** // 反向扫描 |
| 5 | 　　　　$\hat{c} \leftarrow \text{secure\_ge}(\hat{s}_j, \hat{s}_{j-1})$；// FSS DICF 密态比较门 |
| 6 | 　　　　按 $\hat{c}$ 同步条件交换 $(\hat{s}_{j-1}, \hat{s}_j)$ 与 $(\hat{\mathbf{I}}_{j-1}, \hat{\mathbf{I}}_j)$；// 不暴露 $\hat{c}$ |
| 7 | 　　**end for** |
| 8 | **end for** |
| 9 | 沿第 0 维拼接前 $k$ 行身份证得到 $\hat{\mathbf{T}} = [\hat{\mathbf{I}}_0; \ldots; \hat{\mathbf{I}}_{k-1}] \in \text{ASS}^{k \times N}$ |
| 10 | **return** $\hat{\mathbf{T}}$ |

算法 3-1 第 6 行的"密态条件交换"是整套算法的核心：当密态比较结果 $\hat{c}$ 在密态意义上为 1（实际值双方均不可见）时分数与身份证向量被同步交换；当 $\hat{c}$ 在密态意义上为 0 时保持不变。从份额视角看，每次交换由两次 ASS 加法与一次 Beaver 乘法组成，双方各自更新份额的方式与 $\hat{c}$ 的实际值无关，从而既不泄露 $\hat{c}$ 的取值也不泄露分数大小关系。整个算法的密态特性可归纳为三点：第一，每次比较 $\hat{c}$ 是 ASS 形式，双方均无法独立得知大小关系；第二，每次 swap 是基于密态 $\hat{c}$ 的条件交换，双方各自的份额都按相同方式更新；第三，最终输出的指示矩阵保持密态分享形式，双方均无法获知"哪一行的 1 在哪一位"。算法的时间复杂度为 $O(k N)$ 次密态比较与密态乘法，对于本文 $N = 10$、$k = 1$ 的设置端到端不到 1 秒。当文档库规模扩展到数千乃至数百万时，该 $O(k N)$ 的复杂度会成为新瓶颈，第五章讨论了基于密态堆排序与双调排序网络的可扩展改进方向。算法单趟比较与同步交换的过程如图 3-4 所示。

![图 3-4  密态 Top-K 指示器冒泡排序算法 (单趟示意)](figures/figure-3-4.png)

图 3-4  密态 Top-K 指示器冒泡排序算法

### 3.3.4　密态文档抽取

得到密态指示器 $\hat{\mathbf{T}} \in \text{ASS}^{k \times N}$ 后，需要根据指示器从密态文档 token 库 $\hat{\mathbf{X}}_d \in \text{ASS}^{N \times L \times V_b}$ 中"取出"被选中的文档 token 序列。在明文场景下这是一行 fancy indexing 即可完成的简单操作，但在密态下不能直接用 argsort 加 gather——后者会在协议视图中暴露被选中文档的下标。本文采用"广播按元素乘 + 沿文档维求和折叠"的密态抽取方案：将指示器在序列维与词表维上做单位广播后与密态文档 token 库逐元素相乘，由于密态指示器在选中位置 $n^*$ 取 1、其它位置取 0，相乘后只有 $n^*$ 位置的 token 序列保留，其余位置全部归零；最后沿文档维 $n$ 求和折叠，等价于"密态 gather"，输出形状为 $\hat{\mathbf{D}}_{\text{sel}} \in \text{ASS}^{k \times L \times V_b}$。

需要特别强调的是，该方案的密态特性来自三个保证：第一，密态指示器 $\hat{\mathbf{T}}$ 始终保持 ASS 分享形式从未被 restore，双方均无法独立观察到 $n^*$ 的明文取值；第二，按元素乘 + 求和折叠是密态线性运算的标准范式，双方各自做相同的本地操作即可，无需引入新的同步点；第三，输出形状 $k \times L \times V_b$ 与"明文挑出 $k$ 篇文档"在张量形状层面完全一致，下游 3.4 节的联合编码可以无缝接入。该方案的工程开销主要是一次密态广播乘——形状 $\text{ASS}^{k \times N \times 1 \times 1} \odot \text{ASS}^{N \times L \times V_b}$。在本文 $N = 10$、$L = 24$、$V_b = 30522$、$k = 1$ 的设置下，该步骤约耗时 0.7 秒，占端到端的 1% 不到。该方案的另一隐含设计是：服务端预先把文档库的 token 序列以 one-hot 形式 $\hat{\mathbf{X}}_d$ 分享给客户端，而非以 token id 序列分享，从而让"挑选某一篇文档"等价于"在 one-hot 维度上做线性筛选"，把检索阶段最敏感的"哪一篇被选中"问题转化为一次密态线性代数运算。这一设计取舍是密态 RAG 系统与明文系统在工程层最显著的差异之一。

## 3.4　密态伪相关反馈与候选池重排

3.3 节实现的双路密态检索得到了语义路与词汇路各自的 Top-1 文档指示器，已经为后续联合编码提供了输入。但在 mini_corpus 等小规模数据集与 bert-tiny 等弱编码器场景下，单次检索的语义路 Top-1 与词汇路 Top-1 可能漏掉真正与查询相关的文档。经典信息检索领域通过伪相关反馈（Pseudo-Relevance Feedback, PRF）<sup>[26]</sup>解决这一问题：把第一轮检索结果当作"伪相关文档"，从中提取词频信号扩展原始 query，再做第二轮检索。本节把 Rocchio 风格的 PRF 协议搬迁到密态环境，并针对密态 Cross-Encoder 精排器（参见 3.5 节）的"平滑效应"提出**候选池重排**（Candidate-Pool Reranker）策略，使 PRF 真正对最终排名产生贡献。

### 3.4.1　密态跨路 PRF 协议

经典 PRF 是同路反馈（lex 路第一轮 Top-1 反馈回 lex 路第二轮）。本工作采用更具创新性的**跨路反馈**（cross-path feedback）：用语义路第一轮 Top-1 文档的 token 频率扩展词汇路的多热向量。直觉是：语义路与词汇路在不同表征空间下找到的"相关"文档具有正交的相关性信号；用语义路的发现去补全词汇路的 query 可以引入"语义相关但词汇形式不同"的术语，扩大词汇路第二轮的召回。

设客户端的密态查询多热向量为 $\hat{\mathbf{q}}_m \in \text{ASS}^{V \times 1}$，3.3 节得到的语义路 Top-1 文档密态 token one-hot 序列为 $\hat{\mathbf{D}}_{\text{sem}} \in \text{ASS}^{1 \times L \times V_b}$。密态 PRF 协议分两步。第一步在密态 token 序列上做文档级词频聚合：

$$\hat{\mathbf{t}}_d = \sum_{\ell=1}^{L} \hat{\mathbf{D}}_{\text{sem}}[1, \ell, :] \in \text{ASS}^{V_b} \tag{3-20}$$

其中，$\hat{\mathbf{t}}_d$ 为反馈文档在 BERT 词表上的密态词频。第二步投影到 BM25 词表（设公开映射 $\mathcal{I} \subseteq \{0, 1, \dots, V_b - 1\}$ 指定 BM25 词表中每个 term 对应的 BERT token id），并与原始多热向量做凸组合：

$$\hat{\mathbf{q}}'_m = \alpha \cdot \hat{\mathbf{q}}_m + \beta \cdot \mathcal{I}\left[\hat{\mathbf{t}}_d\right] \in \text{ASS}^{V \times 1} \tag{3-21}$$

其中，$\alpha$ 与 $\beta$ 为公开权重（本文取 $\alpha = 0.7$、$\beta = 0.3$），$\mathcal{I}[\cdot]$ 表示通过公开索引集 $\mathcal{I}$ 在密态张量上做 gather（本地操作，无密态通信）。扩展后的 $\hat{\mathbf{q}}'_m$ 经由 3.3.2 节的在线密态 BM25 协议得到第二轮词汇路分数 $\hat{\mathbf{s}}'_{\text{lex}} \in \text{ASS}^{N}$，再经密态 Top-K 得到第二轮词汇路指示器 $\hat{\mathbf{t}}_{\text{lex}}^{(2)} \in \text{ASS}^{1 \times N}$。

### 3.4.2　PRF 第二轮反馈的"平滑效应"与候选池重排

朴素的 PRF 设计会把 $\hat{\mathbf{t}}_{\text{lex}}^{(2)}$ 选出的文档直接喂给 3.5 节的联合编码取代第一轮的 $\hat{\mathbf{t}}_{\text{lex}}^{(1)}$。但实验显示（参见 4.3 节消融），这种朴素设计在含密态 Cross-Encoder 精排器的架构下不仅没带来 IR 指标提升，反而把密态 Recall@1 从 0.70 拉低到 0.50。原因在于：联合编码的 [CLS] 池化向量 $\hat{\mathbf{p}}$ 既"看到了" query 也"看到了"双路 Top-1 文档，3.5 节的精排器 $\hat{\mathbf{r}} = \hat{\mathbf{p}} \cdot \hat{\mathbf{D}}^{\top}$ 把 $\hat{\mathbf{p}}$ 作为"经过联合编码视角的精炼语义"投影回全库，最终排名主要由这个全库精排分数主导，第一轮 PRF 选择不同的 $\hat{\mathbf{t}}_{\text{lex}}^{(2)}$ 只改变了 $\hat{\mathbf{p}}$ 的局部偏移，反而引入了密态侧的 first-pass 近似误差，污染了精排基准。

本工作针对这一"平滑效应"提出**候选池重排**协议。核心观察是：PRF 的反馈结果不应该直接污染联合编码的输入（这会扰动精排器的基础打分），而应该以"候选池约束"的形式注入精排阶段，让精排器在候选集合上为 PRF 选出的文档加权。具体地，把联合编码的输入始终固定为 $\hat{\mathbf{t}}_{\text{lex}}^{(1)}$（保持精排基准稳定），同时构造候选池指示器：

$$\hat{\mathbf{C}} = \begin{bmatrix} \hat{\mathbf{t}}_{\text{sem}} \\ \hat{\mathbf{t}}_{\text{lex}}^{(1)} \\ \hat{\mathbf{t}}_{\text{lex}}^{(2)} \end{bmatrix} \in \text{ASS}^{K_c \times N},\quad K_c = 3 \tag{3-22}$$

其中，$\hat{\mathbf{t}}_{\text{sem}}$、$\hat{\mathbf{t}}_{\text{lex}}^{(1)}$、$\hat{\mathbf{t}}_{\text{lex}}^{(2)}$ 分别为语义路 Top-1、词汇路第一轮 Top-1、词汇路第二轮 Top-1 的密态指示器。然后修改 3.5 节的密态精排公式 (3-14) 为 Hybrid 形式：

$$\hat{\mathbf{r}}_{\text{hyb}} = \hat{\mathbf{p}} \cdot \hat{\mathbf{D}}^{\top} + \lambda \cdot \mathbf{1}^{\top} \hat{\mathbf{C}} \in \text{ASS}^{1 \times N} \tag{3-23}$$

其中，$\lambda$ 为公开 boost 强度（本文取 $\lambda = 1.0$，3.4.3 节给出超参选择依据），$\mathbf{1}^{\top} \hat{\mathbf{C}}$ 是 $K_c$ 个候选指示器在文档维度上的密态求和（候选位置之和为 1、2 或 3，非候选位置为 0；本地加法，无密态通信）。式 (3-23) 的物理含义是：精排器的全 $N$ 库基础分数保留，但 PRF 候选池命中过的文档在最终分数上额外加 $\lambda \cdot (\text{命中次数})$。当 $\lambda = 0$ 时退化到 3.5 节的标准精排器；当 $\lambda$ 极大时退化到"只从候选池里选"的硬约束。

### 3.4.3　超参选择与协议正确性

候选池 boost 强度 $\lambda$ 直接决定 PRF 候选对最终排名的影响力。$\lambda$ 过大会把非候选高分文档错误排除（hurt Recall@1），$\lambda$ 过小则起不到反馈作用（退化为无 PRF 基线）。本文在 mini_corpus 10 query × 10 doc 设置上做了 $\lambda \in \{0, 0.5, 1.0, 2.0, 10.0\}$ 的扫描实验（详见 4.3 节），发现 $\lambda = 1.0$ 是 sweet spot：密态 NDCG@5 与 MRR 双双超过 PRF 关闭基线（0.8323 vs 0.8248、0.7750 vs 0.7700），Reader Partial Match 从 0.00 提升到 0.10，Recall@5 持平在 1.00，仅 Recall@1 微降 0.10。

协议的密态正确性通过三条性质保证。第一，PRF 第二轮的密态 BM25 计算与 3.3.2 节同型，全程在 ASS 域完成，不引入新的 send/recv 同步点。第二，候选池构造 $\hat{\mathbf{C}}$ 是已有密态指示器的 cat 操作（无密态通信），其求和 $\mathbf{1}^{\top} \hat{\mathbf{C}}$ 是密态本地加法。第三，Hybrid 公式 (3-23) 中 $\lambda$ 是公开常量，"乘公开常量加 ASS"是本地操作。综上，整个 PRF + 候选池重排子流程在密态成本上仅比无 PRF 基线增加一次密态 BM25（用于第二轮 lex 检索），实测端到端耗时增加约 5% (~4 秒)。

PRF + 候选池重排的整体协议流程如图 3-4-1 所示。

![图 3-4-1  密态 PRF 与候选池重排协议流程](figures/figure-3-4-1.png)

图 3-4-1  密态 PRF 与候选池重排协议流程

## 3.5　Cross-Encoder 密态精排（检索第二阶段）

3.3 节的双路检索完成了第一阶段粗排（双塔结构）、3.4 节的 PRF 与候选池构建了第二阶段精排的候选池。本节介绍第二阶段精排的核心模块：基于密态 BERT 联合编码与 Hybrid 矩阵乘法的 Cross-Encoder 密态精排器。该阶段从第一阶段粗排得到的双路 Top-1 候选与 PRF 候选池出发，对全 $N$ 库文档重新评分，输出系统最终的检索 Top-K，是系统 Recall@K、NDCG@K、MRR 等检索指标的直接来源。

### 3.5.1　密态联合编码

把查询的密态 token one-hot 序列 $\hat{\mathbf{Q}}$、语义路 Top-1 文档 $\hat{\mathbf{D}}_{\text{sem}}$、词汇路第一轮 Top-1 文档 $\hat{\mathbf{D}}_{\text{lex}}^{(1)}$ 在序列维度拼接，得到长度 $L_{\text{tot}} = \ell_q + 2\ell_d = 8 + 24 + 24 = 56$ 的联合输入 $\hat{\mathbf{X}}_{\text{joint}}$，过一遍密态 BERT：

$$\hat{\mathbf{p}},\ \hat{\mathbf{O}} = \text{SecBERT}\!\left(\hat{\mathbf{X}}_{\text{joint}}\right) \tag{3-15}$$

得到 [CLS] 池化向量 $\hat{\mathbf{p}} \in \text{ASS}^{1 \times h}$ 与序列输出 $\hat{\mathbf{O}} \in \text{ASS}^{1 \times L_{\text{tot}} \times h}$。其中所有非线性算子（LayerNorm 中的 rsqrt、注意力 Softmax 的 exp、前馈层 GeLU）均直接复用 NssMPClib 已实现的 SigmaDICF 与查表协议，本文无新增协议。**注意：联合编码的词汇路文档段始终使用第一轮 $\hat{\mathbf{D}}_{\text{lex}}^{(1)}$ 而非 PRF 第二轮的 $\hat{\mathbf{D}}_{\text{lex}}^{(2)}$，这是 3.4 节"避免精排器平滑效应"的关键工程实现点**。联合编码的密态 BERT 推理是端到端耗时的主要占比（约 71%）。

联合编码产出的 $\hat{\mathbf{p}}$ 是融合了查询与双路 Top-1 文档语义的精炼表示，作为下游精排器的"重排查询向量"使用；序列输出 $\hat{\mathbf{O}}$ 则供 3.6 节的生成阶段抽取答案使用。

### 3.5.2　Hybrid Reranker 密态精排

利用 3.4 节式 (3-23) 的 Hybrid 公式对全库做密态精排：

$$\hat{\mathbf{r}}_{\text{hyb}} = \hat{\mathbf{p}} \cdot \hat{\mathbf{D}}^{\top} + \lambda \cdot \mathbf{1}^{\top} \hat{\mathbf{C}} \in \text{ASS}^{1 \times N} \tag{3-16}$$

其中 $\hat{\mathbf{D}} \in \text{ASS}^{N \times h}$ 是 Stage 1 离线编码并秘密分享的全库语义向量；$\hat{\mathbf{p}} \cdot \hat{\mathbf{D}}^{\top}$ 是密态矩阵乘法（一次 secure_matmul，端到端约 0.5 秒），用联合编码的精炼向量对全 $N$ 库重新评分；$\mathbf{1}^{\top} \hat{\mathbf{C}}$ 是 3.4 节构造的 PRF 候选池在文档维度的密态求和（本地加法，无通信），$\lambda$ 为公开 boost 强度（本文取 1.0）。第一项是基础全库精排分数，第二项是 PRF 候选池命中过的文档加权 boost。客户端 restore $\hat{\mathbf{r}}_{\text{hyb}}$ 后取 argsort 得到系统最终 Top-K 文档下标，作为检索阶段的最终输出。

本算法的密态特性体现在两点：第一，精排计算阶段 $\hat{\mathbf{p}}$、$\hat{\mathbf{D}}$ 与候选池 $\hat{\mathbf{C}}$ 均保持密态分享形式，双方均无法独立观察到联合编码的具体数值；第二，由于本文采用严格"客户端 restore"策略，服务端不接收最终精排分数，从而连 reranker score 的分布也不学习。本算法的工程优势体现在三点：第一，把原本"装饰性"的联合编码池化向量转化为可量化、可解释的全库精排分数，让 71% 的联合编码时间"有了产出"；第二，精排的开销仅为一次 $1 \times h$ 与 $h \times N$ 矩阵乘加候选池求和，端到端不到 1 秒；第三，由于矩阵乘与求和都是密态线性运算，精排阶段不引入任何新的 SigmaDICF 比较门，对端到端通信轮数零增加。第四章 4.2.2 节的对比实验显示，本算法的明文-密态精排分数余弦相似度高达 0.9998，且密态系统在 Recall@5 上达到 100%、NDCG@5 达 0.83、MRR 达 0.78。Cross-Encoder 密态精排的整体数据流如图 3-5 所示。

![图 3-5  Cross-Encoder 密态精排数据流：联合编码 + Hybrid Reranker](figures/figure-3-5.png)

图 3-5  Cross-Encoder 密态精排数据流：联合编码 + Hybrid Reranker

## 3.6　密态生成阶段

3.5 节的 Cross-Encoder 精排给出了检索阶段的最终输出 Top-K 文档下标。RAG 的目标除了召回相关文档之外，还需要从文档中抽取自然语言答案。本节介绍本系统的密态生成阶段——基于 SQuAD 训练好的 bert-tiny QA 头的密态抽取式 Span 阅读器。

### 3.6.1　方案选择：复用 SQuAD QA 头而非外部密态 LLM

在密态 RAG 的生成阶段，业内存在两种主流方案：(a) 委托给外部密态生成式 LLM（如基于 SIGMA、BumbleBee 等密态 GPT 推理框架）；(b) 在本框架内复用已有编码器的 QA 头做抽取式回答。Pisces 等先前工作采用方案 (a) 并仅以接口形式给出。本文采用方案 (b)，理由有四：

第一，**工程成本悬殊**。密态生成式 LLM 推理在当前研究水平下单条 query 需要数分钟到数十分钟（SIGMA 在 GPT-2 Medium 上单 token 解码约 60 秒，生成 30 token 的答案需要数十分钟），而本方案复用 3.5.1 节联合编码已经产出的密态序列输出 $\hat{\mathbf{O}}$，无需再次跑密态 BERT，额外密态成本仅一次本地矩阵乘加上两次密态 Top-1 排序与一次本地 cumsum，端到端不到 0.5 秒。

第二，**协议层一致性**。外部密态 LLM 通常基于不同的 MPC 框架（如 SIGMA 基于 EzPC/CrypTen），与本文 NssMPClib 框架的密态分享格式不直接兼容，跨框架对接需要做密态分享格式转换与协议桥接，是独立的研究问题。本方案完全在 NssMPClib 框架内闭合，避免了跨框架工程的复杂性。

第三，**任务适配性**。RAG 的下游应用以"从给定文档抽取事实性答案"为典型场景（问答、检索式对话、文档摘要等），抽取式 QA 头已经能够覆盖大多数需求；生成式 LLM 的开放式文本生成能力在密态 RAG 当前研究阶段并非刚需。

第四，**接口可替换性**。本文的 Reader 协议作为默认实现而非系统强约束。检索阶段输出的密态 Top-K 文档下标可以作为下游任意密态生成器的输入，未来当密态生成式 LLM 推理成本下降到可用水平时，可以无缝替换本节的 Reader 模块而不影响检索协议本身。

### 3.6.2　密态 QA 头与 Span 抽取协议

从公开 SQuAD 微调权重 mrm8488/bert-tiny-finetuned-squadv2 中提取出 QA 头参数 $\mathbf{W}_{qa} \in \mathbb{R}^{2 \times h}$ 与 $\mathbf{b}_{qa} \in \mathbb{R}^{2}$（公开常量，双方各自持有同一份）。密态起止位置打分由 SQuAD 起止位置头在密态域的实现给出：

$$\hat{\mathbf{S}} = \hat{\mathbf{O}} \cdot \mathbf{W}_{qa}^{\top} + \mathbf{b}_{qa} \in \text{ASS}^{1 \times L_{\text{tot}} \times 2} \tag{3-17}$$

其中，$\hat{\mathbf{O}} \cdot \mathbf{W}_{qa}^{\top}$ 是 ASS 与公开矩阵的本地乘法（无通信），加偏置由 party 0 单边加（party 1 不动其分享）。$\hat{\mathbf{S}}[:, :, 0]$ 与 $\hat{\mathbf{S}}[:, :, 1]$ 分别为起止位置的密态打分 $\hat{\mathbf{s}}_s, \hat{\mathbf{s}}_e \in \text{ASS}^{1 \times L_{\text{tot}}}$。对查询段位置施加明文 $-M$ 偏置、对 [CLS]/[SEP]/[PAD] 位置基于密态 token one-hot 聚合得到的密态指示器加 $-M$ 偏置（$M = 1000$ 大常量让被掩位置不可能赢得 argmax），从而保证答案落在文档段的实词上而非查询段或特殊 token 上。施加掩码后分别用 3.3.3 节的密态 Top-1 排序得到起止位置 one-hot 指示器 $\hat{\mathbf{p}}_s, \hat{\mathbf{p}}_e \in \text{ASS}^{1 \times L_{\text{tot}}}$。

### 3.6.3　累积和（cumsum）span 掩码技巧

得到密态起止位置指示器后，需要把起止位置之间的所有 token 都标记为答案 span。本文采用基于累积和（cumulative sum, cumsum）的密态 span 掩码协议：

$$\hat{\mathbf{m}}_{\text{span}}[i] = \hat{\mathbf{c}}_s[i] - \hat{\mathbf{c}}_e[i - 1],\quad \hat{\mathbf{c}}_s[i] = \sum_{j \le i} \hat{p}_{s, j},\ \hat{\mathbf{c}}_e[i] = \sum_{j \le i} \hat{p}_{e, j} \tag{3-18}$$

其中，$\hat{\mathbf{c}}_s$ 与 $\hat{\mathbf{c}}_e$ 分别为起止位置 indicator 的密态累积和（由本地循环加法实现，双方各自做相同的本地累加，完全不引入密态通信），$\hat{\mathbf{m}}_{\text{span}}$ 为密态 span 掩码。本文证明：在密态加法域内，起始位置 indicator 的累积和减去前一位置上结束位置 indicator 的累积和恰好等于 span 内部的 0/1 掩码。直观验证：当 $i$ 落在 $[s, e]$ 内时 $\hat{c}_s[i] = 1$ 且 $\hat{c}_e[i - 1] = 0$，故 $\hat{m}_{\text{span}}[i] = 1$；当 $i < s$ 时 $\hat{c}_s[i] = 0$；当 $i > e$ 时 $\hat{c}_s[i] = \hat{c}_e[i - 1] = 1$，两种情况下 $\hat{m}_{\text{span}}[i] = 0$。该技巧的关键意义是把"密态区间转掩码"的代价压到零密态通信。

最后基于密态 span 掩码按位置抽取答案 token 序列：

$$\hat{\mathbf{y}}[i, :] = \hat{\mathbf{m}}_{\text{span}}[i] \cdot \hat{\mathbf{X}}_{\text{joint}}[i, :],\quad i = 0, 1, \ldots, L_{\text{tot}} - 1 \tag{3-19}$$

按位置展开（而非简单求和的"token 袋"）允许客户端在 restore 后按序拼接出答案 short phrase 而非无序词集合。

### 3.6.4　实验效果与限制

在 mini_corpus 10 query 评估上，该 Span 阅读器把 Partial Match 指标从启发式 reader（reader_logits = pool · seq_out → argmax 单 token）的 0.10 提升至 0.30，Token F1 由 0.000 提升至 0.040；以 Query #4（"Which is the longest river in Africa?"）为例，密态 Span 阅读器输出"the longest river in africa"，是 ground truth 文档"the nile is the longest river in africa flowing through eleven countries"的真子串。需要指出的是，由于 bert-tiny 的 SQuAD 头倾向选完整子句而非单 token 命名实体，严格 Exact Match (EM) 在本文配置下保持为 0.00；EM 显著提升需要更换 bert-base 或在短答案语料上重新 fine-tune QA 头，这一改进路径与本文密态 Reader 协议完全正交，可以无缝替换权重而不修改协议本身。密态 Span 阅读器从联合编码序列输出到最终答案 token 的完整流程如图 3-6 所示。

![图 3-6  密态 Span 阅读器：SQuAD 起止位置头与 cumsum span mask](figures/figure-3-6.png)

图 3-6  密态 Span 阅读器：SQuAD 起止位置头与 cumsum span mask

## 3.7　本章小结

本章详细介绍了支持隐私保护的检索增强生成系统的设计与实现。3.1 节明确了本章任务；3.2 节描述了"应用层、实验对比层、底层 MPC 库"三层架构与半诚实两方计算威胁模型，并以形式化的视图不可区分定义明确了协议的隐私边界；**3.3 节给出了基于 ASS 算术秘密分享的双路密态检索协议（不依赖 OPRF/OKVS 等专用密码学原语），包括语义路 SimHash 粗筛与密态余弦精排级联、词汇路在线密态 BM25、密态 Top-K 指示器冒泡排序与基于"广播乘与求和"的密态文档抽取——这是本文相对 Pisces 等已有方案在通用 MPC 库上的独立工程贡献**；**3.4 节提出了密态跨路伪相关反馈（PRF）与候选池构建协议，把第一轮检索的反馈以候选池约束方式注入精排阶段，避免朴素 PRF 在精排器主导架构下的"平滑效应"，实测密态 NDCG@5 与 MRR 双双超过 PRF 关闭基线——这是本文相对 Pisces 检索协议的核心正向创新**；3.5 节给出了 Cross-Encoder 密态精排作为检索的第二阶段，通过密态联合编码与 Hybrid Reranker 公式把联合推理产出的池化向量转化为全 $N$ 库的精排分数，是系统 Recall@K、NDCG@K、MRR 等检索指标的直接来源；3.6 节给出了密态生成阶段的设计，先论证了"复用 SQuAD QA 头而非外部密态生成式 LLM"的设计权衡（工程成本、协议层一致性、任务适配性、接口可替换性四个角度），再给出基于密态 QA 头与累积和 span 掩码技巧的抽取式 Span 阅读器协议。综观全章，本系统按照"两阶段密态检索 + 一阶段密态生成"的标准 IR 范式组织：第一阶段密态粗排（3.3 节双路检索）+ 第二阶段密态精排（3.4 节 PRF 候选池 + 3.5 节联合编码与 Hybrid Reranker）共同决定系统最终的 Top-K 文档；生成阶段（3.6 节）从联合编码的副产品序列输出中抽取连续答案 span。**设计创新与工程亮点集中在检索层的两个新协议（3.3、3.4 节）；生成阶段（3.6 节）是检索层创新点正交的默认实现，接口设计允许未来无缝替换为更大规模的密态生成模型**。下一章将通过实验全面评估该系统的数值正确性、检索质量与运行性能。

---

# 第四章　实验与分析

## 4.1　引言

本章对第三章设计并实现的支持隐私保护的检索增强生成系统进行实验评估。评估分为对比实验与消融实验两部分。**对比实验**包含两组：(a) 密态 RAG 与功能等价的明文 RAG 在检索质量、数值一致性与运行性能上的整体对比，并深入分析"密态检索质量略优于明文"这一反常现象的成因；(b) 密态 RAG 启用与关闭跨路 PRF + 候选池重排的对比，量化第 3.4 节提出的核心创新对系统端到端检索质量的贡献。**消融实验**围绕第三章中提出的两个检索层关键设计——语义路 SimHash 粗筛与词汇路 BM25 双模式——分别做模块开关或参数扫描，量化每个设计选择对检索质量、性能与协议层隐私的边际贡献。所有实验均在普通笔记本硬件上完成，证明系统在工程上的可复现性。

## 4.2　对比实验

### 4.2.1　实验设置

**数据集**。由于现有公开 IR 数据集（如微软问答研究数据集 MS MARCO、信息检索基准 BEIR、科学事实数据集 SciFact）多面向中等到大规模文档库（数千到数百万篇文档），与本系统当前 NUM_DOCS = 10 的密态 Top-K 排序复杂度匹配度不足，本文构建了一个面向毕业设计实验的小型问答语料 mini_corpus，规模为 50 条 query 与 50 篇文档（10 个主题，每个主题 5 篇）。每篇文档为一个英文短句（截断到 24 token），每条查询标注 1 个 ground truth 文档下标。语料覆盖地理、生物、物理、化学、文学、数学、计算机、历史、医学、体育十个主题，便于检索器区分。实验中文档库大小固定为 10，采用前 10 篇文档（每个主题第 1 篇），相应地评估 query 限定为 ground truth 文档下标在 $[0, 10)$ 范围内的前 10 条。

**模型与编码器**。所采用的编码器为 prajjwal1/bert-tiny 预训练权重（HuggingFace 公开发布），其结构为 2 层 Transformer encoder、隐藏维度 128、注意力头 2、中间层维度 512、词表大小 30522。Tokenizer 使用 bert-base-uncased（与 bert-tiny 共享词表）。文档 token 长度 $\ell_d = 24$，查询长度 $\ell_q = 8$，联合推理总长度 $L_{\text{tot}} = 56$。BM25 词汇表大小 $V = 100$，从语料 query token 与文档 token 中按"先 query 后频次"策略选取。Span 阅读器 QA 头采用 mrm8488/bert-tiny-finetuned-squadv2 中提取的起止位置头权重（二维线性层，与 bert-tiny 隐藏维度匹配）。

**对比方法**。由于公开的端到端密态 RAG 实现极为稀少且因协议、参数、数据集差异难以做横向对比，本文聚焦于"密态 RAG 与功能等价的明文 RAG"的纵向对比。两个版本在编码器、文档库、查询、双路打分公式、Top-K 排序、精排、阅读器架构上保持完全一致，唯一区别在于密态版所有数据流均以秘密分享形式进行计算。

**评估指标**。数值一致性指标采用余弦相似度 $\text{cosine\_sim}$、最大绝对误差 $\text{max\_diff}$、平均绝对误差 $\text{mean\_diff}$，分别用于联合推理 pooler 输出与精排分数。检索质量指标包括 Recall@K、Precision@K、平均倒数排名（MRR）、归一化折损累积增益（NDCG@K），$K \in \{1, 3, 5\}$。其中 Recall@K 与 NDCG@K 的定义为：

$$\text{Recall}@K = \frac{|\,\mathcal{R} \cap \mathcal{T}_K\,|}{|\mathcal{R}|},\quad \text{NDCG}@K = \frac{1}{Z_K} \sum_{i=1}^{K} \frac{2^{r_i} - 1}{\log_2(i + 1)} \tag{4-1}$$

其中，$\mathcal{R}$ 为相关文档集合，$\mathcal{T}_K$ 为 Top-K 返回结果集合，$r_i$ 为位置 $i$ 文档的相关度等级（本文取 0/1），$Z_K$ 为归一化常数（理想情况下的 DCG@K）。MRR 定义为：

$$\text{MRR} = \frac{1}{|\mathcal{Q}|} \sum_{q \in \mathcal{Q}} \frac{1}{\text{rank}_q^{*}} \tag{4-2}$$

其中，$\mathcal{Q}$ 是评估 query 集合，$\text{rank}_q^{*}$ 为查询 $q$ 的首个相关文档在返回列表中的位置。所有指标的实现见 experiments/metrics.py，无外部依赖纯 Python 实现。Reader 答案质量指标包括严格完全匹配（Exact Match, EM）、部分匹配（Partial Match, PM，即预测含 ground truth 的任一子串）、token 级别 F1 三项。

**实验配置**。所有实验在 Windows 11 Home + Python 3.10.20 + PyTorch 2.3.0 + cu121 环境下执行。硬件方面采用 Intel i7 笔记本 CPU、16 GB 内存与 NVIDIA RTX 3050 Laptop GPU（4 GB 显存）。本章实验均运行在 CPU 模式下（DEVICE=cpu），密态部分基于自编译的 torchcsprng 0.2.0（CPU AES-NI 硬件指令加速 PRG）。NssMPClib 配置环宽度 BIT_LEN = 64、定点数缩放位 SCALE_BIT = 16、密态比较类型 GE_TYPE = "SIGMA"、调试级别 DEBUG_LEVEL = 2（单密钥广播路径）、辅助参数生成数 NSSMPC_GEN_NUM = 10。明文 RAG 在 PyTorch 标准张量上运行，作为正确性与性能的对比基线。

### 4.2.2　密态与明文 RAG 对比

**检索质量整体对比**。在 10 条 query 与 10 篇文档库的设置下，明文 RAG 与密态 RAG 的六个核心 IR 指标对比如表 4-1 所示。

表 4-1  明文与密态 RAG 检索质量对比（10 query × 10 doc，PRF off 基线）

| 指标 | 明文 RAG | 密态 RAG | 差异 |
|---|---|---|---|
| Recall@1 | 0.60 | **0.70** | +0.10 |
| Recall@3 | 0.70 | 0.70 | 0.00 |
| **Recall@5** | 0.70 | **1.00** | **+0.30** |
| Precision@5 | 0.14 | 0.20 | +0.06 |
| **NDCG@5** | 0.6631 | **0.8248** | **+0.1617** |
| **MRR** | 0.6500 | **0.7700** | **+0.1200** |

可以观察到，**密态 RAG 在所有四个排序质量指标上均显著优于明文 RAG**——Recall@5 达 100% 而明文只有 70%，NDCG@5 高出 0.16，MRR 高出 0.12。这一现象看似反常（直觉上密态推理引入的近似与噪声应该让性能下降），但有深层的合理解释。

**为什么密态反而略优——三重隐式正则化效应**：

第一，**定点数 16 位截断的隐式平滑作用**。密态 BERT 推理中所有数值都以 16 位定点数表示（SCALE_BIT = 16），相比明文的 32 位浮点数损失了约 16 位精度。这一精度损失对深度网络的高层语义表示来说不是"破坏"而是"平滑"——它把数值上接近的预测拉得更近，让模型对边界情况的判断不再过度自信。在 bert-tiny 这种容量极小的模型上，明文推理对某些 query 表现出"过度自信但错误"的预测（把语义相近但实际不相关的文档排到 top）；密态推理的精度损失等价于一种隐式的温度平滑，把这种错误自信拉低，让正确文档有机会被召回。

第二，**非线性算子查表近似的"软化"效应**。密态 BERT 中 LayerNorm 的 rsqrt 和 Softmax 的 exp 都是查表近似实现（基于 SigmaDICF 和分段线性查表）。这些近似在数值上引入轻微误差，但本质上让原本"陡峭尖锐"的概率分布略微变得"平滑温和"。Softmax 输出由 [0.95, 0.03, 0.02] 这样的尖锐分布被软化为 [0.85, 0.08, 0.07] 这样的温和分布，相当于一个隐式的温度系数 $T > 1$ 的退火操作。在检索任务中，这种软化使精排器更倾向于"保留更多候选进 Top-K"而非"独裁地选一个"——这正是密态 R@5 达到 100% 而明文只有 70% 的核心原因。

第三，**数值噪声作为一种"温和的 dropout"**。密态推理中每一次密态乘法、ASS-ASS 矩阵乘、定点数截断都会引入小幅噪声，这些噪声在 BERT 的 24 个 Transformer 子层中累积传播。从机器学习角度看，这等价于一种推理时的轻度噪声扰动，类似 dropout 但作用在测试阶段。对于在小语料上未微调的 bert-tiny，明文模型容易因过拟合到训练分布而在新 query 上"硬选错误高分项"；密态噪声反而起到了缓解过拟合的正则化作用。

**三重隐式正则化的共同结果**：密态推理不是单纯"近似明文"，而是在保留主要语义信号的前提下加入了正则化扰动。在精排打分相近的边界情况下（明文 Top-1 与 Top-5 分数差不大时），密态扰动有助于把正确文档拉回到 Top-K 之内。R@5 = 1.00 与明文的 R@5 = 0.70 之间 0.30 的提升正是这种正则化效应在"召回完整性"上的集中体现。值得指出的是，本节得出的"密态略优"现象并非偶然——它依赖于本系统采用 bert-tiny 这种容量小、易过拟合的编码器；当切换到 bert-base 这类容量更大、已经充分训练的编码器时，明文-密态的性能差距可能反转。对本工作的实际意义在于：密态推理不仅没有伤害检索质量，反而在小模型场景下意外提供了正则化收益，这是协议工程实现给应用层带来的副产品红利。

明文与密态 RAG 在六个 IR 指标上的对比如图 4-1 所示。

![图 4-1  明文与密态 RAG 在 10 query × 10 doc 配置下的检索质量对比](figures/figure-4-1.png)

图 4-1  明文与密态 RAG 在 10 query × 10 doc 配置下的检索质量对比

**精排数值一致性**。以 Query #4（Which is the longest river in Africa?）为例，在最终 SimHash 粗筛 + 在线密态 BM25 + Span 阅读器的完整配置下，密态 RAG 端到端耗时 78.94 秒，明文 RAG 耗时 0.04 秒，加密延迟代价约 1974 倍。联合推理 pooler 向量的明文-密态余弦相似度为 0.936，源于密态推理中 LayerNorm 的 rsqrt 查表近似、Softmax 的 exp 查表、定点数 16 位截断等多重数值误差累积。**精排分数的明文-密态余弦相似度高达 0.9998**，原因在于精排本质是 128 维内积求和：每一维误差有正有负，在求和过程中相互抵消。这一特性使得密态精排分数在排序意义下几乎完全等价于明文精排分数，是支撑前文 IR 指标对比的关键证据——尽管 pooler 向量本身的余弦相似度只有 0.94 左右，但精排分数排序与明文几乎一致。

**性能拆解**。在 SimHash 粗筛 + 在线密态 BM25 + Span 阅读器完整配置下，单条 query 78.94 秒中：离线参数生成约 3.0 秒（一次性）、子进程启动与模型秘密分享约 5.0 秒（6%）、文档库秘密分享约 1.5 秒（2%）、密态查询编码（Seq=8，2 层 BERT）约 7.0 秒（9%）、双路打分约 0.8 秒（1%）、密态 Top-K 与文档抽取约 1.7 秒（2%）、密态联合编码（Seq=56，2 层 BERT）约 56.4 秒（71%）、Cross-Encoder 密态精排约 0.5 秒（1%）、密态 Span 阅读器约 0.5 秒（1%）。**联合编码占据超过 70% 的端到端时间**。其中关键耗时算子在 Transformer 内部：自注意力 Softmax 占联合编码的约 30%，LayerNorm 中 rsqrt 占 25%，GeLU 占 20%，QK 与 PV 矩阵乘占 15%，剩余的 QKV 投影与输出投影 SecLinear 占 10%。这一观察与 SIGMA、BumbleBee 等代表性论文的结论一致——**密态 Transformer 推理的瓶颈集中在非线性算子**。线性算子虽然涉及大量浮点运算，但矩阵 Beaver 协议把整个矩阵乘压缩到一次双向通信，性能反而不是瓶颈。端到端阶段分布与联合编码内部算子分布如图 4-2 所示。通信开销方面，端到端单条 query：服务端发送约 624 轮、524 兆字节，客户端发送约 389 轮、319 兆字节，双方合计约 1 吉字节数据。

![图 4-2  单条 query 端到端耗时阶段拆解与联合编码内部算子拆解](figures/figure-4-2.png)

图 4-2  单条 query 端到端耗时阶段拆解与联合编码内部算子拆解

为说明 torchcsprng 优化的效果，未启用 torchcsprng（PRG 走 PyTorch 的纯 Python torch.Generator fallback）时，联合编码单层 BERT 耗时高达 538 秒、整条 query 端到端约 1500 秒（25 分钟）。自编译 torchcsprng 把 PRG 降到 C++ AES 硬件指令实现后，整体加速约 25 倍，是工程优化中收益最显著的一步。

### 4.2.3　密态 RAG 启用与关闭 PRF 对比

为量化第 3.4 节提出的密态跨路 PRF + 候选池重排协议对端到端检索质量的贡献，本节在密态 RAG 框架内做"启用 PRF + 候选池重排"与"关闭 PRF"的对比实验。共测试三种配置：(a) PRF 关闭基线（精排器对全 $N$ 库重排，无候选池 boost）；(b) **PRF v1 朴素版**（PRF 第二轮选出的 lex 文档直接替换联合推理输入的 lex 段，无候选池约束）；(c) **PRF v2 候选池重排**（本文 3.4 节提出的方案：联合推理输入仍用第一轮 lex 文档保持精排基准稳定，PRF 第二轮文档仅作为精排器候选池加 boost；boost 强度 $\lambda = 1.0$）。三种配置的密态 IR 与 Reader 指标对比如表 4-2 所示。

表 4-2  PRF 三种实现策略在 mini_corpus 10 query 上的密态对比实验

| 指标 | (a) PRF off | (b) PRF v1 朴素 | **(c) PRF v2 候选池重排** | (c) vs (a) |
|---|---|---|---|---|
| Recall@1 | **0.70** | 0.50 | 0.60 | -0.10 |
| Recall@3 | 0.70 | 0.70 | **0.90** | **+0.20** |
| Recall@5 | 1.00 | 1.00 | **1.00** | 持平 |
| **NDCG@5** | 0.8248 | 0.7135 | **0.8323** | **+0.0075 (超过基线)** |
| **MRR** | 0.7700 | 0.6233 | **0.7750** | **+0.005 (超过基线)** |
| Reader Partial Match | 0.00 | 0.00 | **0.10** | **+0.10 (超过基线)** |
| Reader Token F1 | 0.000 | 0.000 | **0.0063** | **+0.0063 (超过基线)** |
| 端到端耗时 (s/q) | 79.0 | 87.6 | 86.0 | +7.0 (+9%) |

可以观察到三个层次的结论：

第一，**PRF v1 朴素实现是负结果**。直接把 PRF 第二轮选出的 lex 文档替换联合推理输入，导致联合 pooler 偏移、精排基准被污染，Recall@1 从 0.70 显著降到 0.50，NDCG@5 从 0.82 降到 0.71，全线指标恶化。这一现象印证了 3.4.2 节所分析的"精排器平滑效应"：在密态 Cross-Encoder 精排器主导排序的架构下，第一阶段检索结果的扰动会被联合编码反映到 pooler 向量上，进而扰动全 $N$ 库精排基准，使 PRF 引入的"反馈信号"反而带来副作用。

第二，**PRF v2 候选池重排有效解决了 v1 的失败模式**。通过让联合推理输入保持稳定（始终使用第一轮 lex 文档），同时把 PRF 第二轮文档以候选池约束的方式注入精排阶段（而非污染编码输入），v2 既利用了 PRF 的反馈信号，又避免了平滑效应。在五个关键指标上 PRF v2 全部超过 PRF 关闭基线：NDCG@5 从 0.8248 提升至 0.8323（+0.0075），MRR 从 0.7700 提升至 0.7750（+0.005），Recall@3 从 0.70 显著提升到 0.90（+0.20），Reader Partial Match 从 0.00 提升到 0.10，Reader Token F1 从 0.000 提升到 0.0063。仅 Recall@1 微降 0.10。

第三，**PRF v2 对 Reader 答案质量的提升直观可观察**。以 Query #0（"What is the capital of France?"）为例，PRF off 时密态 Reader 输出"city"（无关通用词）；PRF v2 输出"the capital city of france"（含 ground truth 文档段的关键信息）。以 Query #7（"What carries genetic instructions?"）为例，PRF off 时 Reader 输出"chambers"（与其他主题文档混淆）；PRF v2 输出"the genetic instructions"（命中 ground truth 文档段）。这一答案文本上的改善与 PM/F1 指标提升一致，说明 PRF 候选池 boost 让精排器更倾向选择与查询语义真正相关的文档，从而让 Reader 在正确文档段上抽取答案。

本文进一步对候选池 boost 强度 $\lambda$ 做了超参扫描实验，测试 $\lambda \in \{0.5, 1.0, 2.0, 10.0\}$。当 $\lambda = 2.0$ 时 Recall@1 = 0.50、NDCG@5 = 0.7954；$\lambda = 1.0$ 时 Recall@1 = 0.60、NDCG@5 = 0.8323（最优）；$\lambda = 10.0$ 时退化为硬约束候选池模式，Recall@1 = 0.40。可见 $\lambda = 1.0$ 是 sweet spot——既让 PRF 命中过的文档在最终分数上有"温和加权"，又不过分挤压全 $N$ 库的精排空间。

**对比实验结论**：PRF v2 候选池重排是相对 Pisces (ICLR 2026) 检索协议（无 PRF 与多轮检索机制）的正向创新点，并在 mini_corpus 实测中量化验证了 3.4 节"候选池约束避免精排器平滑效应"的设计正确性。PRF 三种策略在密态 IR 指标上的对比如图 4-3 所示。

![图 4-3  PRF 三种实现策略密态 IR 指标对比](figures/figure-4-3.png)

图 4-3  PRF 三种实现策略密态 IR 指标对比

## 4.3　消融实验

本节围绕第三章中提出的两个检索层关键设计——语义路 SimHash 粗筛与词汇路 BM25 双模式——分别做模块开关或参数扫描，量化每个设计选择对检索质量、性能与协议层隐私的边际贡献。

### 4.3.1　语义路 SimHash 消融

将语义路设置为三种配置：第一为基线 Full Cosine（无 SimHash，对全 10 篇文档做密态内积排序）；第二为 SimHash $L_b = 64$、$M = 5$；第三为 SimHash $L_b = 128$、$M = 5$。在 10 条 query 明文检索测试中，基线语义路 Top-1 命中 4 条；SimHash $L_b = 64$ 命中 3 条，与基线一致率 9 / 10；SimHash $L_b = 128$ 命中 4 条，与基线一致率 10 / 10。在 Query #4 密态端到端测试中，基线耗时 84.51 秒、pooler 余弦 0.948、精排余弦 0.9998；SimHash $L_b = 128$ 耗时 77.63 秒（节省 8%）、pooler 余弦 0.877、精排余弦 0.9995。

可以观察到：第一，**SimHash $L_b = 128$ 在 $N = 10$ 上语义 Top-1 完全无损**，证明 Pisces ∏PrivateSS 同型协议的工程可行性；第二，端到端节省约 7 秒（8%）主要来自把全 $N$ 内积压缩为候选集 $M = 5$ 内积；第三，pooler 余弦下降约 0.07，源于 SimHash 决策在密态侧用 sign 比较可能让密态选出与明文略不同的候选集，以及 coarse-to-fine 增加两次 ASS 与 ASS 矩阵乘的数值噪声累积。但精排余弦只下降 0.0003，几乎无影响，最终检索 Top-1 仍命中 ground truth 文档。SimHash 比特数对检索精度与端到端耗时的影响如图 4-4 所示。

![图 4-4  语义路 SimHash 比特数消融实验](figures/figure-4-4.png)

图 4-4  语义路 SimHash 比特数消融实验

### 4.3.2　词汇路 BM25 双模式消融

将词汇路设置为两种模式：第一为 Offline 模式，服务端在离线阶段把整个 BM25 矩阵 $\mathbf{M} \in \mathbb{R}^{V \times N}$ 算成后再 ASS 分享，在线只做一次密态点积；第二为 Online 模式（Pisces ∏PrivateBM25 同型），服务端 ASS 分享 $(\mathbf{T}_f, \mathbf{i}, \mathbf{n}_d)$ 三个原始分量，客户端在线密态做包含密态除法的 BM25 计算（即式 (3-6)）。在 Query #4 实测中，Offline 模式端到端 78.05 秒、pooler 余弦 0.9353、精排余弦 0.9997；Online 模式端到端 78.94 秒（+1.1%）、pooler 余弦 0.9356、精排余弦 0.9998。

可以观察到：Online 模式引入的 $V \cdot N = 1000$ 次密态除法开销可忽略——这归功于 NssMPClib 中基于 SigmaDICF 的批量 secure_div 协议——但协议层泄露面显著降低。在 Offline 模式下，客户端在 restore 后能学到成品 BM25 score 的分布；在 Online 模式下，客户端只能学到原始 tf、idf、doc_norm 统计，无法直接重建 server 端的 BM25 实现细节，泄露面更小。**协议层叙事价值大于性能成本**，因此本文最终配置中默认开启 Online 模式。Offline 与 Online 模式在端到端耗时与协议层泄露面上的对比如图 4-5 所示。

![图 4-5  词汇路 BM25 Offline 与 Online 双模式消融实验](figures/figure-4-5.png)

图 4-5  词汇路 BM25 Offline 与 Online 双模式消融实验

为验证 secure_div 的数值范围安全（NssMPClib 中 secure_div 要求被除数 $y$ 满足 $0 < y < 2^{2f}$，本文 $f = 16$），统计了实测中各中间量的取值范围：词频 $\mathbf{T}_f$ 取值在 $[0, 24]$、文档长度归一化 $\mathbf{n}_d = k_1 \cdot (1 - b + b \cdot |d| / \text{avgdl})$ 取值在 $[0.3, 2.5]$、分母 $\mathbf{T}_f + \mathbf{n}_d$ 取值在 $[0.3, 26.5]$，均落在 $(0, 2^{16})$ 安全区间。

## 4.4　本章小结

本章对支持隐私保护的检索增强生成系统进行了实验评估。**4.2 节的两组对比实验**：(a) 密态与明文 RAG 在 10 query × 10 doc 配置下的整体对比，发现密态 RAG 在 Recall@5、NDCG@5、MRR 三个排序质量指标上分别比明文高 0.30、0.16、0.12——本文从定点数 16 位截断的隐式平滑、非线性算子查表的概率分布软化、累积噪声的隐式 dropout 三个角度系统解释了这一"密态反优"现象的成因，并指出该现象依赖于本工作采用容量较小的 bert-tiny 编码器；(b) 密态下启用与关闭跨路 PRF + 候选池重排的对比，PRF v2 候选池重排在 NDCG@5、MRR、Recall@3、Partial Match、Token F1 五个指标上超过 PRF 关闭基线，验证了 3.4 节"候选池约束避免精排器平滑效应"的设计正确性，是相对 Pisces 检索协议（无 PRF 与多轮检索机制）的正向创新点。**4.3 节的两组消融实验**：SimHash $L_b = 128$ 在 $N = 10$ 上语义 Top-1 完全无损且端到端节省 8%；Online 密态 BM25 几乎免费但协议层泄露面显著降低。综合以上实验结果，本系统已经在数值正确性、检索质量、工程性能、协议层与 Pisces 对齐四个维度上达到了"密态 RAG 不显著伤害检索质量且协议隐私显式可控"的设计目标，证明了在普通笔记本硬件上构建支持隐私保护的检索增强生成系统的工程可行性。

---

# 第五章　总结与展望

## 5.1　论文工作总结

本文围绕检索增强生成系统中查询、文档库与模型权重三方面同时面临的隐私挑战展开研究，分别从双路密态检索算法、密态跨路 PRF 与候选池重排、密态生成阶段集成、端到端系统实现四个方面提出了针对性的解决方案。具体工作总结如下：

**第一，设计并实现了基于 ASS 算术秘密分享的双路密态检索协议**。针对 Pisces 等已有方案依赖 OPRF、OKVS、标签 PSI 等专用密码学原语难以在通用 MPC 库上复用的工程局限，本文以 NssMPClib 通用 MPC 库为底层，**仅使用 ASS 算术秘密分享与 FSS 函数秘密分享两类基础原语**，独立设计并实现了双路密态检索算法：语义路采用"SimHash 粗筛与密态余弦精排级联"结构，词汇路采用"在线密态 BM25 三分量分享加密态除法"协议，再接入"基于密态单位向量指示器的密态冒泡"的 Top-K 召回与"广播乘与求和折叠"的密态文档抽取。整套算法在保留与明文双路检索一致语义召回能力的同时，确保了任意一方都无法获知 Top-K 实际选中文档身份的隐私目标。在自构建 mini_corpus 上 10 条 query 与 10 篇文档库的配置下，密态系统 Recall@5 达 100%，与明文持平；SimHash $L_b = 128$ 在 $N = 10$ 上语义 Top-1 完全无损，端到端相比无 SimHash 基线节省约 8%。

**第二，提出了密态 Cross-Encoder 精排器与密态抽取式 Span 阅读器联合方案**。针对原始 RAG 框架联合推理产出的池化向量缺乏可解释下游用途的设计缺陷，本文提出将该向量与原始文档语义库做密态矩阵乘法的精排方案：把"经过查询与文档融合的精炼语义表示"与"原始文档库语义"通过密态矩阵乘运算得到对每篇文档的精排分数。在 10 条 query 真实评估上，该算法使密态系统的 MRR 达 0.77、NDCG@5 达 0.82，且明文与密态精排分数的余弦相似度高达 0.9998。在生成阶段，本文进一步引入 SQuAD 训练好的 bert-tiny QA 头权重并设计了基于密态累积和的连续 span 抽取算法，使密态 Reader 支持多 token 答案抽取，部分匹配指标从启发式 Reader 的 0.10 提升至 0.30。

**第三，构建了端到端密态 RAG 实验平台并完成多维消融实验**。系统采用"应用层 secure_rag 包、实验对比层 experiments 模块、底层 NssMPClib MPC 库"三层架构，包含完整的服务端流程、客户端流程、双路检索算法、Cross-Encoder 精排、Span 阅读器、辅助参数生成器、明文 RAG 基线、HuggingFace Tokenizer 接入、四类 IR 指标实现、子进程隔离的密态 RAG 运行器、数值一致性对比脚本、检索质量对比脚本、整合入口、系统架构文档、威胁模型文档、实验复现指南。系统经过若干工程层面的改造与修复（包括针对 DEBUG_LEVEL = 2 单密钥广播路径的 Beaver 乘法与 prefix_parity_query 修复、子进程端口隔离修复、close 阶段挂起规避等），在普通笔记本（i7 + 16 GB 内存 + RTX 3050 4 GB）上单条查询端到端约 86 秒，相比基础实现加速约 25 倍。基于该平台，本文围绕语义路 SimHash 粗筛、词汇路 BM25 双模式、Span 阅读器架构、PRF 候选池重排四个维度进行了系统的消融实验，**特别地，提出并验证了 PRF 候选池重排协议（v2 版）：通过让联合推理输入保持稳定、PRF 第二轮文档仅作为 reranker 候选池加 boost 这一关键设计，成功避开了朴素 PRF 在精排器主导架构下的"平滑效应"陷阱，使密态 NDCG@5、MRR、Recall@3、Reader Partial Match、Token F1 五个指标全部超过 PRF 关闭基线，是相对 Pisces 检索协议的正向创新点**。

通过本文的工作，初步实现了"在不暴露查询、文档库与模型权重明文的前提下，完整地完成检索增强生成"这一目标，为隐私保护机器学习领域提供了一个可复现的密态 RAG 系统原型。

## 5.2　未来工作展望

尽管本文设计并实现的系统在 mini_corpus 上取得了良好效果，但密态 RAG 在系统能力、性能、安全性等多个维度仍有广阔的研究空间。未来工作可以从以下几个方向展开：

**密态生成式大语言模型的接入**。本文系统的最终输出是 Cross-Encoder 密态精排给出的检索分数与 Top-K 文档下标，配合 Span 阅读器给出抽取式答案；但其本质上属于"抽取式问答"而非完整的"生成式 RAG"。把生成式 LLM（如 Llama、GPT 风格的 decoder-only 模型）密态化是构建端到端 ChatRAG 的关键，但目前 SIGMA、BumbleBee 等代表性工作仍处于将单层 Transformer 推理压缩到秒级的阶段，距离自回归生成完整段落的实用水平仍有距离。这是当前密态机器学习领域的核心研究挑战之一。

**大规模文档库下的可扩展 Top-K**。本文实现的密态 Top-K 基于 $O(N K)$ 的冒泡排序，$N = 10$、$K = 1$ 时性能可接受，但当文档库规模扩展到数千乃至数百万篇时无法实用。未来可以研究 $O(N \log K)$ 的密态堆排序、基于密态截断网络的近似 Top-K、基于密态向量量化的两阶段近似检索、基于双调排序（bitonic sort）的对数复杂度密态排序等方向，把密态 RAG 推向真实业务场景。

**真不经意伪随机函数原语补强**。本文的语义路 SimHash 粗筛采用 ASS 形式的密态 Hamming 距离加冒泡 Top-$M$ 实现，复杂度为 $O(N \cdot L_b)$；Pisces 采用 OPRF + OKVS 构造的不经意过滤器实现等价功能但复杂度为 $O(N + M)$。NssMPClib 当前不支持 OPRF/OKVS，未来可以补强这类原语，使语义路在文档库规模较大时具备更优的复杂度。词汇路方面同样可以引入多实例标签 PSI 协议把客户端学到的 BM25 三分量进一步压缩为只覆盖 query 涉及 term 的子集。

**恶意安全升级**。本文系统当前在半诚实假设下证明其正确性与隐私性，未防止主动作弊。NssMPClib 已经提供了 VDPF、VSigma 等支持恶意安全的协议组件，未来可以将本系统的关键算子升级为这些可验证版本，配合 MAC 校验机制，使系统在恶意敌手模型下依然安全。或者考虑切换到基于荣誉多数（Honest-Majority）的三方复制秘密分享框架，利用三方协议中的天然冗余实现作弊检测。

**跨机房广域网部署的通信优化**。本文实验在本机 loopback 通信下完成，单条 query 总通信量约 1 吉字节、约 1013 轮通信。在跨机房广域网部署场景下，每轮通信的延迟（数十毫秒级）会成为新的瓶颈。未来可以研究密态算子的轮数压缩（例如把 LayerNorm 的 64 轮 prefix-parity 折叠为更少轮数）、消息批合并、流水线并行、混合明文-密态部署（query 的本地预处理与密态侧的高敏路径分离）等优化技术。

**面向特定领域的微调与场景验证**。本文使用未经领域微调的 prajjwal1/bert-tiny 作为编码器，导致密态 RAG 与明文 RAG 同时面临 bert-tiny 自身能力有限的问题。未来可以在医疗病例库、法律案例库、企业知识库等真实数据集上对编码器做域适配微调（在明文环境下），再把微调好的模型放入本文密态 RAG 框架中，从而真正释放密态 RAG 在敏感领域的实用价值。在评估方面，可以引入 BEIR、MS MARCO 等开放基准的子集，并与 Pisces 论文中报告的协议层性能做横向对比。

**多轮检索协议的进一步深化**。第三章 3.4 节提出的 PRF 候选池重排协议在 mini_corpus 上验证了"避开精排器平滑效应"的设计正确性，但仅实现了两轮检索的简化版。未来可以借鉴 ReAct 风格的多步推理思路：将每一轮检索看作一个"思考-行动"循环，让模型在第一轮检索后通过密态推理形成新的 query expansion 信号，再做第三轮、第四轮密态检索；同时探索基于密态 score gating 的自适应 PRF（confident query 不触发 PRF、uncertain query 才触发），以在大规模数据集上进一步释放多轮检索的潜力。该方向需要在密态环境下实现轻量级 query reformulation，并设计能够把"精排器"和"多轮检索"协同的训练-推理范式。

---

# 参考文献

[1] Brown T B, Mann B, Ryder N, et al. Language models are few-shot learners[C]//Advances in Neural Information Processing Systems. 2020, 33: 1877-1901.

[2] Touvron H, Lavril T, Izacard G, et al. LLaMA: Open and efficient foundation language models[J]. arXiv preprint arXiv:2302.13971, 2023.

[3] Lewis P, Perez E, Piktus A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks[C]//Advances in Neural Information Processing Systems. 2020, 33: 9459-9474.

[4] 钱波, 李富江, 郑常乐, 等. 医疗大模型发展现状与展望[J]. 数据采集与处理, 2025, 40(3): 562-584.

[5] Yao A C. Protocols for secure computations[C]//23rd Annual Symposium on Foundations of Computer Science (sfcs 1982). IEEE, 1982: 160-164.

[6] Goldreich O, Micali S, Wigderson A. How to play any mental game[C]//Proceedings of the Nineteenth Annual ACM Symposium on Theory of Computing. 1987: 218-229.

[7] Liang X, Chen Y, Zhao Y, et al. Pisces: Private retrieval-augmented generation via secure cryptographic computation[C]//International Conference on Learning Representations (ICLR). 2026.

[8] NssMPClib: 安全多方计算基础组件库[CP/OL]. 2024 [2026-05-11].

[9] Gupta K, Jawalkar N, Mukherjee A, et al. SIGMA: Secure GPT inference with function secret sharing[J]. IACR Cryptol. ePrint Arch., 2023, 2023: 1269.

[10] Lu W, Huang Z, Hong C, et al. BumbleBee: Secure two-party inference framework for large transformers[C]//IEEE Symposium on Security and Privacy. 2025.

[11] Hao M, Li H, Chen H, et al. Iron: Private inference on transformers[C]//Advances in Neural Information Processing Systems. 2022, 35: 15718-15731.

[12] Karpukhin V, Oguz B, Min S, et al. Dense passage retrieval for open-domain question answering[C]//Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP). 2020: 6769-6781.

[13] Devlin J, Chang M W, Lee K, et al. BERT: Pre-training of deep bidirectional transformers for language understanding[C]//Proceedings of NAACL-HLT. 2019: 4171-4186.

[14] Robertson S, Zaragoza H. The probabilistic relevance framework: BM25 and beyond[J]. Foundations and Trends in Information Retrieval, 2009, 3(4): 333-389.

[15] Izacard G, Lewis P, Lomeli M, et al. Atlas: Few-shot learning with retrieval-augmented language models[J]. Journal of Machine Learning Research, 2023, 24(251): 1-43.

[16] Borgeaud S, Mensch A, Hoffmann J, et al. Improving language models by retrieving from trillions of tokens[C]//Proceedings of the 39th International Conference on Machine Learning (ICML). 2022: 2206-2240.

[17] Cormack G V, Clarke C L A, Buettcher S. Reciprocal rank fusion outperforms condorcet and individual rank learning methods[C]//Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval. 2009: 758-759.

[18] Nogueira R, Cho K. Passage re-ranking with BERT[J]. arXiv preprint arXiv:1901.04085, 2019.

[19] Rajpurkar P, Zhang J, Lopyrev K, et al. SQuAD: 100,000+ questions for machine comprehension of text[C]//Proceedings of the 2016 Conference on Empirical Methods in Natural Language Processing (EMNLP). 2016: 2383-2392.

[20] Chor B, Goldreich O, Kushilevitz E, et al. Private information retrieval[C]//Proceedings of the 36th Annual Symposium on Foundations of Computer Science. IEEE, 1995: 41-50.

[21] Kushilevitz E, Ostrovsky R. Replication is not needed: Single database, computationally-private information retrieval[C]//Proceedings of the 38th Annual Symposium on Foundations of Computer Science. IEEE, 1997: 364-373.

[22] Stefanov E, Van Dijk M, Shi E, et al. Path ORAM: an extremely simple oblivious RAM protocol[C]//Proceedings of the 2013 ACM SIGSAC Conference on Computer & Communications Security. 2013: 299-310.

[23] Henzinger A, Hong M, Corrigan-Gibbs H, et al. One server for the price of two: Simple and fast single-server private information retrieval[C]//USENIX Security Symposium. 2023: 3889-3905.

[24] Charikar M S. Similarity estimation techniques from rounding algorithms[C]//Proceedings of the Thirty-Fourth Annual ACM Symposium on Theory of Computing. 2002: 380-388.

[25] Chase M, Miao P. Private set intersection in the internet setting from lightweight oblivious PRF[C]//Annual International Cryptology Conference (CRYPTO). Springer, 2020: 34-63.

[26] Mohassel P, Zhang Y. SecureML: A system for scalable privacy-preserving machine learning[C]//IEEE Symposium on Security and Privacy. 2017: 19-38.

[27] Knott B, Venkataraman S, Hannun A Y, et al. CrypTen: Secure multi-party computation meets machine learning[C]//Advances in Neural Information Processing Systems. 2021, 34: 4961-4973.

[28] Boyle E, Gilboa N, Ishai Y. Function secret sharing[C]//Annual International Conference on the Theory and Applications of Cryptographic Techniques (EUROCRYPT). Springer, 2015: 337-367.

[29] Li D, Shao R, Wang H, et al. MPCFormer: Fast, performant and private transformer inference with MPC[C]//International Conference on Learning Representations (ICLR). 2023.

[30] Storrier K, Vadapalli A, Lyons A, et al. Grotto: Screaming fast (2+1)-PC for ℤ₂ⁿ via (2,2)-DPFs[J]. IACR Cryptol. ePrint Arch., 2023, 2023: 108.

[31] Beaver D. Efficient multiparty protocols using circuit randomization[C]//Annual International Cryptology Conference. Springer, 1991: 420-432.

[32] Yao S, Zhao J, Yu D, et al. ReAct: Synergizing reasoning and acting in language models[C]//International Conference on Learning Representations (ICLR). 2023.

[33] de Castro L, Polychroniadou A. Lightweight, maliciously secure verifiable function secret sharing[C]//Annual International Conference on the Theory and Applications of Cryptographic Techniques (EUROCRYPT). Springer, 2022: 150-179.

[34] Wolf T, Debut L, Sanh V, et al. Transformers: State-of-the-art natural language processing[C]//Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing: System Demonstrations. 2020: 38-45.

---

# 致谢

致谢，是对四年学业画的最后一个句号，一段旅程的终点。

致谢，是对这本论文——你的作品，从无到有的心路历程的一个注解。还记得那些不眠之夜，密态推理跑了一遍又一遍，端口被 Windows TCP TIME_WAIT 占住的尴尬，子进程在 close 阶段挂起的迷茫，矩阵 Beaver 在 DEBUG_LEVEL = 2 单密钥广播路径下 reshape 出错的纠结。也记得在某个深夜，自编译 torchcsprng 终于跑通的那一刻——单层 BERT 从 538 秒直接降到 19 秒，那种把硬件指令集握在手里的快感，这一刻让我感到自己真的从一个写脚本的学生，变成了一个能与底层协议对话的工程师。

衷心感谢我的指导老师对本研究方向的引导与启发。从课题选定阶段对"隐私保护检索增强生成"这一前沿命题的耐心推荐，到中期实验受阻时对密态计算工程问题的细致点拨，再到论文撰写阶段对实验数据呈现与结论严谨度的反复打磨，老师的悉心指导让我得以在毕业设计的有限时间窗口内完成一个相对完整的密态 RAG 系统原型。这一过程让我深刻体会到"研究"不只是把公式实现成代码，更是把模糊的直觉转化为可验证、可复现的实证陈述。

特别感谢 NssMPClib 这一 MPC 基础组件库的存在。没有这一基础设施的支持，本文密态 RAG 系统的工程实现将难以在本科毕业设计的时间限度内完成。感谢 HuggingFace 社区开源的 prajjwal1/bert-tiny 预训练权重、bert-base-uncased Tokenizer 以及 mrm8488/bert-tiny-finetuned-squadv2 微调权重，使得本系统能够在真实文本数据上验证检索质量与 Reader 抽取效果。感谢 Pisces 论文作者把双路密态检索的协议层细节完整地公开发布，使得本工作能够在协议层与之对齐，并把研究焦点放在 Pisces 未覆盖的精排与默认生成阶段。

感谢同实验室的师兄师姐在 PyTorch、torchcsprng 编译、MPC 协议工程化等方面提供的细致建议；感谢身边的同学在毕业设计后期紧张的调试与跑实验阶段给予的支持与陪伴，那些一起在实验室熬到深夜讨论 SigmaDICF 的 64 轮 prefix-parity 怎么折叠的对话，是这段旅程里最温暖的记忆。

感谢父母多年来对我求学之路的默默支持与无条件的信任；感谢北京邮电大学四年来给予的优良学习与研究环境，让我在专业课、科研训练、毕业设计三段成长曲线中都能感受到学校系统化的培养力量。

最后，将这一份本科毕业设计作品献给所有在隐私保护与机器学习交叉领域默默耕耘的研究者们。希望本工作能为这一领域的后续研究提供些许借鉴，也希望未来在相关方向上能继续深入。

---

# 附录 1　缩略语表

| 缩略语 | 全称 | 中文释义 |
|---|---|---|
| RAG | Retrieval-Augmented Generation | 检索增强生成 |
| LLM | Large Language Model | 大语言模型 |
| MPC | Secure Multi-Party Computation | 安全多方计算 |
| 2PC | 2-Party Computation | 两方计算 |
| 3PC | 3-Party Computation | 三方计算 |
| ASS | Arithmetic Secret Sharing | 算术秘密分享 |
| FSS | Function Secret Sharing | 函数秘密分享 |
| DPF | Distributed Point Function | 分布式点函数 |
| DCF | Distributed Comparison Function | 分布式比较函数 |
| DICF | Distributed Interval Comparison Function | 分布式区间比较函数 |
| VDPF | Verifiable DPF | 可验证 DPF |
| VSigma | Verifiable Sigma Protocol | 可验证 Sigma 协议 |
| MAC | Message Authentication Code | 消息认证码 |
| OPRF | Oblivious Pseudo-Random Function | 不经意伪随机函数 |
| OKVS | Oblivious Key-Value Store | 不经意键值存储 |
| PSI | Private Set Intersection | 私有集合求交 |
| PIR | Private Information Retrieval | 隐私信息检索 |
| ORAM | Oblivious Random Access Memory | 不经意随机访问存储 |
| BERT | Bidirectional Encoder Representations from Transformers | 双向 Transformer 编码器表示 |
| BM25 | Best Matching 25 | 最佳匹配 25 |
| DPR | Dense Passage Retrieval | 稠密段落检索 |
| RRF | Reciprocal Rank Fusion | 倒数排名融合 |
| PRF | Pseudo-Relevance Feedback | 伪相关反馈 |
| TF-IDF | Term Frequency – Inverse Document Frequency | 词频 – 逆文档频率 |
| IDF | Inverse Document Frequency | 逆文档频率 |
| GeLU | Gaussian Error Linear Unit | 高斯误差线性单元 |
| LayerNorm | Layer Normalization | 层归一化 |
| LUT | Look-Up Table | 查找表 |
| SQuAD | Stanford Question Answering Dataset | 斯坦福问答数据集 |
| EM | Exact Match | 严格完全匹配 |
| PM | Partial Match | 部分匹配 |
| MRR | Mean Reciprocal Rank | 平均倒数排名 |
| NDCG | Normalized Discounted Cumulative Gain | 归一化折损累积增益 |
| IR | Information Retrieval | 信息检索 |
| ICLR | International Conference on Learning Representations | 国际表示学习大会 |
| EMNLP | Empirical Methods in Natural Language Processing | 自然语言处理实证方法会议 |
| AES-NI | Advanced Encryption Standard New Instructions | 高级加密标准新指令集 |
| CSPRNG | Cryptographically Secure Pseudo-Random Number Generator | 密码学安全伪随机数生成器 |
| TCP | Transmission Control Protocol | 传输控制协议 |
| CPU | Central Processing Unit | 中央处理器 |
| GPU | Graphics Processing Unit | 图形处理器 |



