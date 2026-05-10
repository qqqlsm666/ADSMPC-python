"""
experiments/_cipher_worker.py

子进程 entry：从 argv 收 input/output 文件路径，跑一次密态 RAG，把 pool 张量 pickle
写到 output 文件。不直接被脚本调用；由 _rag_runner.run_secure_rag_once 启动。

为什么用文件而不是 stdin/stdout：
- 子进程在跑加密 RAG 时会大量 print 日志到 stdout（progress 之类），如果 pickle 数据
  也走 stdout 就被混一起了，父进程 unpickle 一定会失败。
- 用独立文件做 IPC 最简单稳定。
"""
import os
import pickle
import sys
import threading

# 确保 secure_rag / experiments 包能被 import
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ_ROOT = os.path.dirname(_HERE)
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

import torch  # noqa


def main():
    if len(sys.argv) < 3:
        print("Usage: _cipher_worker.py <input.pkl> <output.pkl>", file=sys.stderr)
        sys.exit(2)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, 'rb') as f:
        payload = pickle.load(f)

    # 关键：在 import NssMPC 之前就把 NSSMPC_PORT_OFFSET 写好
    if 'port_offset' in payload:
        os.environ['NSSMPC_PORT_OFFSET'] = str(payload['port_offset'])
    if 'device' in payload:
        os.environ['DEVICE'] = payload['device']

    # 延迟 import
    from NssMPC.application.neural_network.party.neural_network_party import NeuralNetworkCS
    from secure_rag.server import run_server
    from secure_rag.client import run_client

    # 在子进程里加载 tokenizer（用于 client 端 decode 答案 token）
    tokenizer = None
    tokenizer_name = payload.get('tokenizer_name')
    if tokenizer_name:
        try:
            from transformers import BertTokenizer
            tokenizer = BertTokenizer.from_pretrained(tokenizer_name)
        except Exception as e:
            # mirror fallback
            try:
                os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
                from transformers import BertTokenizer
                tokenizer = BertTokenizer.from_pretrained(tokenizer_name)
            except Exception as e2:
                print(f"[worker] tokenizer load failed: {e2}", file=sys.stderr)

    server_party = NeuralNetworkCS(type='server')
    client_party = NeuralNetworkCS(type='client')

    for p in [server_party, client_party]:
        p.set_multiplication_provider()
        p.set_comparison_provider()
        p.set_nonlinear_operation_provider()

    # 改造：result holder 由 client 端持有（client 才是最终拿到结果的一方）
    result_holder = []        # client 端会 append 一个 result dict
    server_done_holder = []   # server 端跑完会 append [{}] 占位（用来判断 server 已完成）
    server_err: list = []
    client_err: list = []

    def _server_thread():
        try:
            run_server(
                server_party,
                db_embeddings=payload['db_embeddings'],
                bm25_matrix=payload['bm25_matrix'],
                db_tokens_onehot=payload['db_tokens_onehot'],
                bm25_vocab=payload.get('bm25_vocab'),
                weight_path=payload.get('weight_path'),
                bert_config=payload.get('bert_config'),
                return_holder=server_done_holder,
                bm25_components=payload.get('bm25_components'),
            )
        except Exception as e:
            server_err.append(e)

    def _client_thread():
        try:
            run_client(
                client_party,
                query_token_ids=payload['query_token_ids'],
                query_multihot=payload['query_multihot'],
                bm25_vocab=payload.get('bm25_vocab'),
                bert_config=payload.get('bert_config'),
                tokenizer=tokenizer,
                return_holder=result_holder,
            )
        except Exception as e:
            client_err.append(e)

    t_s = threading.Thread(target=_server_thread, daemon=True)
    t_c = threading.Thread(target=_client_thread, daemon=True)
    t_s.start(); t_c.start()

    # 主线程轮询：等 client 端 result 写入；不 join 子线程
    import time
    deadline = time.time() + 300
    while time.time() < deadline:
        if result_holder:
            break
        if not (t_s.is_alive() or t_c.is_alive()):
            break
        time.sleep(0.5)

    if not result_holder:
        msg = "Client result 没拿到。"
        if server_err:
            msg += f" server 线程异常: {server_err[0]!r}"
        if client_err:
            msg += f" client 线程异常: {client_err[0]!r}"
        if t_s.is_alive() or t_c.is_alive():
            msg += " 超时（轮询 deadline 到了，子线程仍在跑）"
        with open(output_path, 'wb') as f:
            pickle.dump({'ok': False, 'error': msg}, f)
        os._exit(1)

    # result_holder[0] 是 client 端写出的 dict: {pool, rerank_scores, answer_token_id, answer_text, ...}
    output = {'ok': True}
    output.update(result_holder[0])
    with open(output_path, 'wb') as f:
        pickle.dump(output, f)
    # 不 join 子线程，直接强退
    os._exit(0)


if __name__ == "__main__":
    main()
