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

# 离线辅助参数生成数量（DEBUG_LEVEL=2 下单 key 复用，所以 10 也能跑）
GEN_NUM = int(os.getenv("NSSMPC_GEN_NUM", "10"))

# 调试开关
DEBUG = False

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
