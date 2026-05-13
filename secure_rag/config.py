"""
secure_rag/config.py

加密 RAG 项目的全局配置：BERT 模型超参 + RAG 流程超参。
所有数字都来自原 NssMPClib/test/rag.py 的顶部常量，提取出来便于实验脚本统一引用。
"""
import os

# bert-tiny 配置（与 prajjwal1/bert-tiny 兼容）
BERT_CONFIG = {
    "hidden_size": 128,
    "num_hidden_layers": 2,
    "num_attention_heads": 2,
    "intermediate_size": 512,
    "vocab_size": 30522,
    "max_position_embeddings": 512,
    "type_vocab_size": 2,
}

# RAG 流程超参
BATCH = 1
SEQ = 8                                    # query token 长度
NUM_DOCS = 10                              # 知识库文档数
TOP_K = 1                                  # 每路召回数量
QUERY_LEN = 8                              # = SEQ
SEM_DOC_LEN = 24                           # 语义路文档长度
LEX_DOC_LEN = 24                           # BM25 路文档长度
TOTAL_SEQ = QUERY_LEN + SEM_DOC_LEN + LEX_DOC_LEN  # 联合推理序列长度 = 56
VOCAB_SIZE_BM25 = 100                      # 词汇路使用的小词表大小

# SimHash 粗筛配置（语义路 coarse-to-fine 检索，对应 Pisces ICLR 2026 的 ∏PrivateSS / Protocol 1）
# 流程：query/doc embedding 经公开投影 W → 取符号位得到 L-bit binary → 密态 Hamming 距离粗筛
#       → top-M 候选集 → 对 M 个候选做密态 cosine 精排 → top-K1
# 全程在 ASS 域，W 是双方共享的公开矩阵（同一 SIMHASH_SEED 即可保证一致）
SIMHASH_ENABLED = True                     # 总开关：False 则退化为对全 N 个 doc 直接做密态内积
SIMHASH_BITS = 128                         # SimHash 比特数 L（N=10 实测：L=64 损失 1/10 hit，L=128 完全无损）
SIMHASH_CANDIDATES_M = 5                   # 粗筛后保留多少候选（M < N，建议 N//2）
SIMHASH_SEED = 42                          # 投影矩阵 W 的固定随机种子，保证 server/client 双方算同一个 W

# PRF (Pseudo-Relevance Feedback / 伪相关反馈) 配置
# 流程：第一轮 lex 检索 → 用 反馈源 doc 作扩展信号 → PRF 扩展 query → 第二轮 lex 检索
# 全程在 ASS 域完成，不引入新 send/recv 同步点
PRF_ENABLED = True                         # 总开关：False 则退化为 B3 单轮 lex 检索
PRF_ALPHA = 0.7                            # 原始 query 的权重
PRF_BETA = 0.3                             # 反馈 doc 词频的权重

# ⭐ PRF 候选池约束 Reranker (实测在 mini_corpus N=10 上仍 negative result)
# 'none' (默认):  Reranker = pool @ db_embs.T 重排全 N 库
# 'strict':       Reranker 只在 PRF 候选池 (sem_top1 + lex_round1 + lex_round2) 里重排
# 'hybrid':       全 N reranker + 候选池 boost
# ⚠️ mini_corpus 10-query 实测：'strict' 和 'hybrid' 都让 R@1 从 0.70 降到 0.40
# 原因：PRF round 2 改变 lex_doc 输入到 joint BERT，让联合 pool 偏移、base scores 错位
# 这是 architecture-level 问题，reranker 端无法救。论文写成 negative finding。
PRF_CANDIDATE_POOL_RERANK = 'hybrid'
PRF_RERANK_BOOST = 1.0

# Sem 路 PRF / 多轮检索（对应 task #5 / ReAct 多轮简化版）
# 第一轮 sem 检索 → 取 sem top-1 doc 的 embedding → q_expanded_emb = α·query_emb + β·doc_emb
#                → 第二轮 sem 检索 (用 q_expanded_emb)
# 概念上对应 ReAct 中"Thought 1 → Act → Thought 2"的两步推理
SEM_PRF_ENABLED = False                    # 默认关，跟现状兼容；论文 ablation 用
SEM_PRF_ALPHA = 0.7                        # 原始 query embedding 权重
SEM_PRF_BETA = 0.3                         # 反馈 doc embedding 权重
# 反馈源选择 ⭐ 跨路反馈是这个项目的实际创新点
#   'lex': 同路反馈（用第一轮 lex top-1 doc 反馈到 lex 路） - 经典 PRF
#   'sem': 跨路反馈（用 sem top-1 doc 反馈到 lex 路） - 跨模态扩展，引入"语义相关但词汇不同"的词
#   'both': 双路反馈聚合（sem + lex 两个 doc 的词频都进 query）
PRF_FEEDBACK_SOURCE = 'sem'

# 离线辅助参数生成数量（DEBUG_LEVEL=2 下单 key 复用，所以 10 也能跑）
GEN_NUM = int(os.getenv("NSSMPC_GEN_NUM", "10"))

# 调试开关
DEBUG = False

# Pre-generation Reranker 配置（架构正确性升级：把 reranker 从 generation 之后移到之前）
# False (默认): 沿用现状 — 双路各取 top-1 直接喂 joint inference，post-encoding 重排
# True : 双路各取 top-K1=RERANK_K1 候选 → fusion rerank (bi-encoder + lex score) → top-K2 → joint inference
#        架构与标准 RAG (first-stage retrieval → cross-encoder rerank → generation) 一致
# 注意：开启时建议关闭 PRF（互斥的多阶段策略）。代码会强制忽略 PRF。
RERANK_PRE_GEN_ENABLED = False
RERANK_K1 = 2                              # 双路各取 K1 个候选 (合并后候选池 = 2*K1)
RERANK_K2 = 2                              # 融合后保留 K2 个 doc 喂 joint inference
RERANK_ALPHA = 0.5                         # 融合权重：bi-encoder score (query_emb · cand_emb)
RERANK_BETA = 0.5                          # 融合权重：cand 对应的 lex score (BM25)

# Lex 路在线密态 BM25 配置（Pisces ICLR 2026 ∏PrivateBM25 / Protocol 2 同型）
# False: 离线明文算好 bm25_matrix [V, N]，在线只做 indicator @ bm25 (当前默认)
# True : 离线 share (tf [V,N], idf [V], doc_norm [N]) 三个分量；
#        在线密态算 score = sum_v indicator[v] * idf[v] * tf[v,d] * (k1+1) / (tf[v,d] + doc_norm[d])
#        协议层跟 Pisces Protocol 2 Step 4 (在线密态 BM25 计算) 对齐
LEX_BM25_ONLINE = False
LEX_BM25_K1 = 1.5
LEX_BM25_B = 0.75

# Span Reader 配置（SQuAD-style start/end head, 来自 mrm8488/bert-tiny-finetuned-squadv2）
# 用 scripts/extract_squad_qa_head.py 提取的 qa_outputs 权重，密态 sequnce → 密态 span
SPAN_READER_ENABLED = True                 # 总开关：False 退化为旧的启发式 reader (pool · seq_out)
def default_qa_head_path():
    """返回默认 QA head 权重路径 (models/qa_head_squadv2.pth)。"""
    here = os.path.dirname(os.path.abspath(__file__))
    proj_root = os.path.dirname(here)
    return os.path.join(proj_root, "models", "qa_head_squadv2.pth")


# 权重默认路径（可被实验脚本覆盖）
def default_weight_path():
    """返回默认 bert-tiny 权重路径，按优先级尝试两个位置。"""
    # 项目根 / models / bert_tiny_weights.pth
    here = os.path.dirname(os.path.abspath(__file__))
    proj_root = os.path.dirname(here)
    candidates = [
        os.path.join(proj_root, "models", "bert_tiny_weights.pth"),
        os.path.join(proj_root, "NssMPClib", "test", "bert_tiny_weights.pth"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]
