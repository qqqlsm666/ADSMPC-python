"""
secure_rag/server.py

加密 RAG 的 Server 角色（party_id=0）。
负责：
- 持有并秘密分享 BERT 模型
- 持有并秘密分享文档库（embedding / BM25 矩阵 / token 库）
- 在密文上完成"双路打分 → 密态 Top-K → 取真实文档 → 联合 BERT 推理"
- 把最终 pooler 输出收回还原（明文）

为了既能在原 rag.py 的"假数据 demo"模式下跑，也能在 experiments/ 下注入真实数据，
本文件提供了 `run_server(party, db, model_state_dict)` 风格的函数式 API。
"""
from typing import Optional, Dict
import torch
import torch.nn.functional as F

from NssMPC import RingTensor, ArithmeticSecretSharing
from NssMPC.config import DEVICE
from NssMPC.config.runtime import PartyRuntime
from NssMPC.application.neural_network.utils.converter import share_model, load_model, share_data
from NssMPC.application.neural_network.layers.mha import SecBertModel

from .config import BERT_CONFIG, NUM_DOCS, TOP_K, SEQ, SEM_DOC_LEN, VOCAB_SIZE_BM25, TOTAL_SEQ
from .retrieval import (
    secure_inner_product_score,
    secure_lexical_score,
    secure_top_k_indicator,
)


def load_bert_weights(model: SecBertModel, weight_path: str, log_prefix: str = "[Server]") -> int:
    """把 bert-tiny 权重 load 到 SecBertModel 的明文 parameters 里。返回成功 load 的参数个数。"""
    import os as _os
    if not _os.path.exists(weight_path):
        print(f"{log_prefix} 警告: 未找到权重文件 {weight_path}, 使用零初始化（pooler 会输出 0）")
        return 0
    print(f"{log_prefix} 加载 bert-tiny 权重: {weight_path}")
    state_dict = torch.load(weight_path, map_location=DEVICE)
    state_dict.pop('embeddings.position_ids', None)
    new_state_dict = {(k[5:] if k.startswith('bert.') else k): v for k, v in state_dict.items()}
    loaded, missing = 0, []
    for name, p in model.named_parameters():
        if name in new_state_dict:
            p.data = new_state_dict[name].to(DEVICE).to(torch.float32)
            loaded += 1
        else:
            missing.append(name)
    print(f"{log_prefix} 权重加载完成: loaded={loaded}, missing={len(missing)}")
    if missing:
        print(f"{log_prefix} 缺失权重示例: {missing[:5]}")
    return loaded


def run_server(
    server_party,
    db_embeddings: Optional[torch.Tensor] = None,
    bm25_matrix: Optional[torch.Tensor] = None,
    db_tokens_onehot: Optional[torch.Tensor] = None,
    weight_path: Optional[str] = None,
    bert_config: Optional[Dict] = None,
    return_holder: Optional[list] = None,
):
    """
    Args:
        server_party: NeuralNetworkCS(type='server') 已 set_*_provider，未 online
        db_embeddings:    [NUM_DOCS, hidden]，文档语义向量库（明文）。None 则用 torch.randn 占位
        bm25_matrix:      [VOCAB_SIZE_BM25, NUM_DOCS]，词汇路打分矩阵（明文，正数）
        db_tokens_onehot: [NUM_DOCS, SEM_DOC_LEN, vocab_size]，文档 token 的 one-hot 表示
        weight_path:      bert-tiny 权重路径
        bert_config:      BERT 模型配置 dict
        return_holder:    若提供 list，会把 final_pool 这个 [1, hidden] 的 torch.Tensor append 进去

    最终 pooler 输出会打印，并（如指定 return_holder）写入 return_holder[0]
    """
    cfg = bert_config or BERT_CONFIG

    server_party.online()
    with PartyRuntime(server_party):
        # ---------- 1. 准备模型 ----------
        model = SecBertModel(cfg)
        for p in model.parameters():
            p.requires_grad = False
        if weight_path is not None:
            load_bert_weights(model, weight_path, log_prefix="[Server]")

        model_for_dummy = SecBertModel(cfg)
        print("[Server] 执行 Dummy Model 1 (Seq=8)...")
        server_party.dummy_model(model_for_dummy)

        s_local, s_remote = share_model(model)
        server_party.send(s_remote)
        model = load_model(model, s_local)

        # ---------- 2. 准备并分享文档库 ----------
        if db_embeddings is None:
            db_embeddings = torch.randn(NUM_DOCS, cfg['hidden_size']).to(DEVICE)
        else:
            db_embeddings = db_embeddings.to(DEVICE)
        if bm25_matrix is None:
            bm25_matrix = torch.abs(torch.randn(VOCAB_SIZE_BM25, NUM_DOCS)).to(DEVICE)
        else:
            bm25_matrix = bm25_matrix.to(DEVICE)
        if db_tokens_onehot is None:
            db_tokens_ids = torch.randint(0, cfg['vocab_size'], (NUM_DOCS, SEM_DOC_LEN)).to(DEVICE)
            db_tokens_onehot = F.one_hot(db_tokens_ids, cfg['vocab_size']).float()
        else:
            db_tokens_onehot = db_tokens_onehot.to(DEVICE)

        print("[Server] 构建并分享密态知识库...")
        s_db_local, s_db_remote = share_data(db_embeddings)
        server_party.send(s_db_remote)
        my_db_share = s_db_local[0]

        print("[Server] 构建并分享 BM25 倒排矩阵 (词汇路)...")
        s_bm25_local, s_bm25_remote = share_data(bm25_matrix)
        server_party.send(s_bm25_remote)
        my_bm25_matrix_share = s_bm25_local[0]

        print("[Server] 构建并分享文档 Token 数据库...")
        s_db_tokens_local, s_db_tokens_remote = share_data(db_tokens_onehot)
        server_party.send(s_db_tokens_remote)
        my_db_tokens_share = s_db_tokens_local[0]

        # ---------- 3. 接收 Client Query 并编码 ----------
        print("[Server] 等待 Client 输入 Query...")
        sh_in = server_party.receive()
        sh_pos = server_party.receive()
        sh_type = server_party.receive()
        mask = server_party.receive()

        print("[Server] 提取 Query 密态 Embedding...")
        _, query_emb_share = model(sh_in[0], sh_pos[0], sh_type[0], mask)

        # ---------- 4. 双路打分 ----------
        print("[Server] RAG: 开始双路密态打分与召回...")
        scores_sem_share = secure_inner_product_score(query_emb_share, my_db_share)

        print("[Server] RAG: 执行词汇路(BM25) 打分与排序...")
        my_query_multihot_share = server_party.receive()[0]
        scores_lex_share = secure_lexical_score(my_query_multihot_share, my_bm25_matrix_share)

        # ---------- 5. 第二次 Dummy Model（为 Seq=56 联合推理生成参数）+ 密态 Top-K + 取文档 + 拼接 ----------
        print("[Server] 执行 Dummy Model 2 (Seq=56)...")
        server_party.dummy_model(model_for_dummy)

        print("[融合] 通过密态指示器，提取真实 Token 序列...")
        top_k_ind_sem_share = secure_top_k_indicator(scores_sem_share, k=TOP_K)
        top_k_ind_lex_share = secure_top_k_indicator(scores_lex_share, k=TOP_K)

        expanded_ind_sem = top_k_ind_sem_share.unsqueeze(-1).unsqueeze(-1)
        my_doc_sem_share = (expanded_ind_sem * my_db_tokens_share).sum(dim=1)

        expanded_ind_lex = top_k_ind_lex_share.unsqueeze(-1).unsqueeze(-1)
        my_doc_lex_share = (expanded_ind_lex * my_db_tokens_share).sum(dim=1)

        my_query_share = sh_in[0]
        my_joint_ids_share = ArithmeticSecretSharing.cat(
            [my_query_share, my_doc_sem_share, my_doc_lex_share], dim=1
        )

        # 接收 Client 发来的 56 长度辅助张量
        my_pos_share = server_party.receive()[0]
        my_typ_share = server_party.receive()[0]
        joint_mask = server_party.receive()

        # ---------- 6. 联合推理 ----------
        print("[Server] 执行联合推理...")
        seq_out, pool = model(my_joint_ids_share, my_pos_share, my_typ_share, joint_mask)

        # ---------- 7. 密态 Reranker（B2 方案）----------
        # 把联合推理产出的 pool 跟原始文档语义库做密态 matmul，得到每篇 doc 的精排分数。
        print("[Server] 密态 reranker 计算 ...")
        from .retrieval import secure_rerank, secure_reader
        rerank_logits_share = secure_rerank(pool, my_db_share)

        # ---------- 8. 密态 Reader（抽取式生成）----------
        # 启发式 head: pool · seq_out → reader logits → 密态 argmax → 密态 gather token
        # 整条流程双方都看不到答案位置或答案 token，最后只在 client 端 restore。
        print("[Server] 密态 reader 抽取答案 ...")
        answer_token_oh_share, reader_logits_share, position_indicator_share = secure_reader(
            pool, seq_out, my_joint_ids_share,
        )

        # ---------- 9. 输出方向反转：三个 share 全部 send 给 client，client 端 restore ----------
        # 这样 server 全程不学习到 query 相关的信息：reranker 分数、pool 数值、答案 token 都
        # 在 client 端还原。Server 只持有自己的文档库（本来就有），不学习客户端的查询、检索结果或答案。
        print("[Server] 把 rerank / pool / answer 三个 share 发给 client ...")
        server_party.send(rerank_logits_share)   # client 端 restore 拿到精排分数
        server_party.send(pool)                  # client 端 restore 拿到 pool（实验数值一致性用）
        server_party.send(answer_token_oh_share) # client 端 restore 拿到答案 token one-hot

        # 实验诊断：把 server 端持有的 share（不是明文）写出去，便于 client 端做数值一致性对比时
        # 拿到 server 端的 reader_logits / position_indicator share 也能在 client 端 restore。
        # 不过这两个用于诊断而非最终输出，所以也走 send。
        server_party.send(reader_logits_share)
        server_party.send(position_indicator_share)

        if return_holder is not None:
            # Server 端不再持有最终结果（已经全部送给 client）；这里只填空 dict 占位，
            # 真正的结果由 client 端的 run_client 写出。
            return_holder.append({})

    server_party.close()
