"""
extract_squad_qa_head.py

从 mrm8488/bert-tiny-finetuned-squadv2 提取 qa_outputs head 权重，
保存到 models/qa_head_squadv2.pth，供密态 span reader 使用。

qa_outputs: Linear(128, 2)  →  weight [2, 128]、bias [2]
其中:  start_logits = seq_out @ W[0]  + b[0]
       end_logits   = seq_out @ W[1]  + b[1]
"""
import os
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

import torch
from transformers import AutoModelForQuestionAnswering

MODEL_NAME = 'mrm8488/bert-tiny-finetuned-squadv2'
OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'models', 'qa_head_squadv2.pth',
)

m = AutoModelForQuestionAnswering.from_pretrained(MODEL_NAME)
W = m.qa_outputs.weight.detach().cpu()    # [2, 128]
b = m.qa_outputs.bias.detach().cpu()      # [2]

# 也保存 bert backbone 的权重以便后续可选 fine-tune 使用 (与 prajjwal1/bert-tiny 兼容)
backbone_state = m.bert.state_dict()

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
torch.save({
    'qa_W': W,
    'qa_b': b,
    'backbone': backbone_state,
    'source': MODEL_NAME,
    'note': 'qa_outputs is a Linear(hidden=128, 2). W[0]=start, W[1]=end.',
}, OUT_PATH)

print(f'saved: {OUT_PATH}')
print(f'W shape: {tuple(W.shape)}')
print(f'b shape: {tuple(b.shape)}')
print(f'backbone keys (first 3): {list(backbone_state.keys())[:3]}')
