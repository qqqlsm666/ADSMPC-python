# 实验复现指南

本文档说明如何复现毕设论文里的两类对比实验。

## 实验环境

- Windows 11 / Linux Ubuntu 22.04
- Python 3.10
- PyTorch 2.3.0 + CUDA 12.1（或 CPU）
- 推荐已编译 `torchcsprng`（PRG 走 C++ AES，单条 query 从 25 分钟 → 1-2 分钟）

## 一键跑全部

```bash
conda activate ADSMPC-python
cd /path/to/ADSMPC-python

DEVICE=cpu NSSMPC_GEN_NUM=10 python -m experiments.run_main
```

会按顺序跑：
1. 任务 A：单条 query 的密态 vs 明文 数值一致性
2. 任务 B：5 条 query 的检索质量对比

产物：
- `experiments/results/numerical_compare.md`
- `experiments/results/retrieval_eval.md`

总耗时 ≈ 5-15 分钟（torchcsprng 已装）；25-60 分钟（fallback PRG）。

## 任务 A：数值一致性

### 命令

```bash
python -m experiments.run_numerical_compare \
    --corpus experiments/data/mini_corpus.json \
    --query_idx 0 \
    --output experiments/results/numerical_compare.md
```

### 流程

1. 加载 `mini_corpus.json` 的 50 query / 50 doc
2. 用 HF `bert-base-uncased` tokenizer 把 query / doc 转 token id
3. 用 **明文 bert-tiny** 离线编码所有文档 → `db_embeddings [N, 128]`
4. 用真 BM25 公式构造倒排矩阵 → `bm25_matrix [V, N]`
5. **明文 RAG** 跑 query #0
6. **密态 RAG** 跑同一条 query #0（同一权重、同一 db、同一 query_multihot）
7. 对比两侧 pooler 输出：
   - `max_diff`、`mean_diff`、`cosine_sim`
   - 双路 top-1 doc id 是否一致

### 期待结果

- `cosine_sim > 0.99`（基本一致）
- `max_diff < 0.1`（pooler 是 tanh 输出值域 (-1, 1)，0.1 已经是较大误差）
- 语义路 top-1 ≈ 词汇路 top-1 ≈ ground truth doc id

如果差距大，常见原因：
- 权重没加载成功（看 `[Server] 权重加载完成: loaded=39, missing=0`）
- BERT_CONFIG 不匹配 .pth 文件

## 任务 B：检索质量

### 命令

```bash
# 只跑前 10 条（快速看趋势，约 15-30 分钟）
python -m experiments.run_retrieval_eval \
    --corpus experiments/data/mini_corpus.json \
    --num_queries 10 \
    --output experiments/results/retrieval_eval.md

# 全 50 条（论文最终结果，约 1-2 小时）
python -m experiments.run_retrieval_eval --num_queries 50

# 只跑明文 baseline（先确认 ground truth 合理，再跑密态）
python -m experiments.run_retrieval_eval --num_queries 50 --skip_cipher
```

### 评估指标

对每条 query 算：
- **Precision@K**: top-K 中相关文档比例
- **Recall@K**:    top-K 中召回的相关文档比例
- **NDCG@K**:      位置打折累积增益（位置越靠前奖励越大）
- **MRR**:         第一个相关文档位置的倒数

K 取 1, 3, 5。

`retrieved` 列表的构造：
- **明文**：双路各取 top-`max(K)` 文档 → 交错合并去重
- **密态**：用密态 pool 跟 db_embeddings 做明文 cosine 最近邻（**因为目前 secure_rag/server.py 没有还原 indicator 的接口**，这是简化处理；论文里需要明示这一点）

### 期待结果

| 指标 | 明文 | 密态 |
|---|---|---|
| Recall@5 | ≈ 0.85+ | ≈ 0.80+ |
| MRR | ≈ 0.7+ | ≈ 0.6+ |

如果加密前后差距 < 5 %，可以在论文里写 "加密不显著伤害检索质量"。

## 自定义实验

### 改语料

直接编辑 `experiments/data/mini_corpus.json`，按下面 schema 补：

```json
{
  "documents": [{"id": 0, "topic": "...", "text": "..."}, ...],
  "queries":   [{"id": 0, "text": "...", "gt_doc_id": 0}, ...]
}
```

注意：
- doc 长度截断到 `SEM_DOC_LEN = 24` token，过长信息会丢
- query 长度截断到 `QUERY_LEN = 8` token

### 改文档库大小

修改 `secure_rag/config.py:NUM_DOCS`，从 10 改到你想要的值。

但注意：
- `NUM_DOCS` 越大，密态 Top-K 越慢（O(N·K) 比较 + swap）
- 4GB 显存的笔记本 GPU 上 NUM_DOCS = 50 可能 OOM；先试 20

### 改 BERT 大小

修改 `secure_rag/config.py:BERT_CONFIG`：

```python
BERT_CONFIG = {
    "hidden_size": 64,            # 砍半
    "num_hidden_layers": 1,       # 单层
    "intermediate_size": 128,
    "vocab_size": 1000,           # 大幅缩小
    "max_position_embeddings": 64,
    ...
}
```

但注意：缩小 vocab 后**不能再加载 prajjwal1/bert-tiny 的权重**（vocab 不匹配），需要从头训练或者放弃权重加载。

### 跑 GPU

```bash
DEVICE=cuda python -m experiments.run_main
```

笔记本 GPU 4GB VRAM 跑 NUM_DOCS=10 + Seq=56 联合推理可能 OOM；先试 NUM_DOCS=5。

## 故障排查

### `RuntimeError: shape '[1024, 1]' is invalid for input of size 1`
PRG fallback 没有正确广播。检查 `NssMPClib/NssMPC/crypto/protocols/arithmetic_secret_sharing/semi_honest_functional/multiplication.py` 是否含有 `target_shape_x` 分支。

### `IndexError: pop from empty list` in `FSSKeyProvider`
GeLU key 没加载。检查 `~/.NssMPClib/data/64/aux_parameters/GeLUKey/GeLUKey_0.pth` 是否存在；不存在就跑 `python -c "from secure_rag.params import gen_params; gen_params(10)"`。

### 卡在 "Encoder layer 0 start"
PRG fallback 太慢，正常等 5-10 分钟一层。装 torchcsprng 解决。

### 端口冲突
`rag.py / experiments/_rag_runner.py` 自动按 PID 算 `NSSMPC_PORT_OFFSET`。如果还是冲突，手动 `export NSSMPC_PORT_OFFSET=12345`。

### tokenizer 下不下来
连不上 huggingface.co，`data_loader.py` 已经会自动尝试 `https://hf-mirror.com`。还不行就：
```bash
huggingface-cli download bert-base-uncased --local-dir ./hf_models/bert-base-uncased
# 然后改 experiments/data_loader.py 顶部 DEFAULT_TOKENIZER_NAME 为本地路径
```
