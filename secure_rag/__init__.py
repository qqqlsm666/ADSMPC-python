"""
secure_rag/__init__.py

加密 RAG 应用层包：
- config:     全局配置
- retrieval:  双路密态打分 + Top-K 指示器排序
- server:     Server 端流程（持有文档库、收 query、做联合推理、还原 pooler）
- client:     Client 端流程（持有 query、收文档库 share、参与运算、回传 pool share）
- plaintext:  明文 RAG 实现，用于实验对比
- params:     一次性生成全部辅助参数（gen_params）
"""
from .config import (
    BERT_CONFIG, BATCH, SEQ, NUM_DOCS, TOP_K, QUERY_LEN, SEM_DOC_LEN, LEX_DOC_LEN,
    TOTAL_SEQ, VOCAB_SIZE_BM25, GEN_NUM, DEBUG, default_weight_path,
)
from .retrieval import (
    secure_inner_product_score,
    secure_lexical_score,
    secure_top_k_indicator,
)
from .server import run_server, load_bert_weights
from .client import run_client
from .plaintext import plaintext_rag, encode_docs_to_embeddings, build_bm25_matrix
from .params import gen_params

__all__ = [
    "BERT_CONFIG", "BATCH", "SEQ", "NUM_DOCS", "TOP_K",
    "QUERY_LEN", "SEM_DOC_LEN", "LEX_DOC_LEN", "TOTAL_SEQ", "VOCAB_SIZE_BM25",
    "GEN_NUM", "DEBUG", "default_weight_path",
    "secure_inner_product_score", "secure_lexical_score", "secure_top_k_indicator",
    "run_server", "load_bert_weights", "run_client",
    "plaintext_rag", "encode_docs_to_embeddings", "build_bm25_matrix",
    "gen_params",
]
