"""
secure_rag/params.py

一次性生成加密 RAG 所需的全部辅助参数（Beaver / FSS / 查表 keys）。
从 NssMPClib/test/rag.py 的 gen_params() 函数提炼出来。
"""
import os

from NssMPC.crypto.aux_parameter import (
    AssMulTriples, DivKey, GeLUKey, Wrap, SigmaDICFKey, GrottoDICFKey,
    ReciprocalSqrtKey, TanhKey, B2AKey,
)

from .config import GEN_NUM


def gen_params(num: int = None, *, also_make_data_dir: bool = True):
    """
    一次性生成全部加密 RAG 所需的辅助参数并保存到 ~/.NssMPClib/data/64/aux_parameters/。

    Args:
        num: 要生成多少份（DEBUG_LEVEL=2 下只用 1 份；这里给个默认 GEN_NUM=10 即可）
        also_make_data_dir: 是否在 cwd 下建一个 'data' 目录（兼容旧 rag.py 行为）
    """
    n = num or GEN_NUM
    print(f"=== [Init] 生成辅助参数 (N={n}) ===")
    if also_make_data_dir and not os.path.exists('data'):
        os.makedirs('data')
    AssMulTriples.gen_and_save(n, saved_name='2PCBeaver')
    DivKey.gen_and_save(n)
    GeLUKey.gen_and_save(n)
    TanhKey.gen_and_save(n)
    Wrap.gen_and_save(n)
    ReciprocalSqrtKey.gen_and_save(n)
    GrottoDICFKey.gen_and_save(n)
    SigmaDICFKey.gen_and_save(n)
    B2AKey.gen_and_save(n)
    print("=== [Init] 参数生成完成 ===\n")
