"""
experiments/_rag_runner.py

每条 query 起一个独立子进程跑密态 RAG。
- 进程间通信通过临时文件（pickle），避免 stdout 被进度日志污染
- 每条 query 用不同的 NSSMPC_PORT_OFFSET，进一步降低端口撞概率
"""
import os
import pickle
import subprocess
import sys
import tempfile
import time
from typing import Dict, Optional

import torch


_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cipher_worker.py")


def _new_port_offset(call_idx: int) -> int:
    """每次调用换一个新偏移，避开上一条 query 的 TCP TIME_WAIT。"""
    base = 20000 + (os.getpid() % 10000)
    return base + call_idx * 50 + (int(time.time()) % 50)


_call_counter = 0


def run_secure_rag_once(
    *,
    query_token_ids: torch.Tensor,
    query_multihot: torch.Tensor,
    db_embeddings: torch.Tensor,
    bm25_matrix: torch.Tensor,
    db_tokens_onehot: torch.Tensor,
    weight_path: str,
    bert_config: Optional[Dict] = None,
    device: Optional[str] = None,
    timeout_sec: int = 600,
    show_subprocess_output: bool = True,
) -> Dict[str, torch.Tensor]:
    """起子进程跑一次完整加密 RAG。

    Returns:
        dict 包含
            - 'pool':          [1, hidden] 联合推理 pooler 输出（密态还原后的明文）
            - 'rerank_scores': [NUM_DOCS]   reranker 重排序分数（密态还原后的明文）
    """
    global _call_counter
    _call_counter += 1
    port_offset = _new_port_offset(_call_counter)

    payload = {
        'port_offset':       port_offset,
        'query_token_ids':   query_token_ids,
        'query_multihot':    query_multihot,
        'db_embeddings':     db_embeddings,
        'bm25_matrix':       bm25_matrix,
        'db_tokens_onehot':  db_tokens_onehot,
        'weight_path':       weight_path,
        'bert_config':       bert_config,
    }
    if device is not None:
        payload['device'] = device
    elif os.environ.get('DEVICE'):
        payload['device'] = os.environ['DEVICE']

    print(f"     [_rag_runner] 启动子进程 (port_offset={port_offset}) ...")

    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'

    # 用临时文件做进程间数据交换，避免 stdout 被混合
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f_in:
        input_path = f_in.name
        pickle.dump(payload, f_in)
    output_path = input_path + '.out'

    try:
        # 子进程的 stdout/stderr 透传到当前进程，方便看 progress
        proc = subprocess.Popen(
            [sys.executable, _SCRIPT, input_path, output_path],
            stdout=None if show_subprocess_output else subprocess.DEVNULL,
            stderr=None if show_subprocess_output else subprocess.DEVNULL,
            env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        try:
            ret = proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise RuntimeError(f"子进程超时 ({timeout_sec}s)，已 kill")

        if ret != 0:
            raise RuntimeError(f"子进程退出码非 0 ({ret})")

        if not os.path.exists(output_path):
            raise RuntimeError(f"子进程没写出 output 文件: {output_path}")

        with open(output_path, 'rb') as f:
            result = pickle.load(f)
        if not result.get('ok'):
            raise RuntimeError(f"子进程报错: {result.get('error')}")
        # 返回完整 dict，调用方拿什么取什么
        return {
            'pool':          result['pool'],
            'rerank_scores': result['rerank_scores'],
        }

    finally:
        for p in (input_path, output_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
