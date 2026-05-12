"""
Generate all thesis figures (paper-quality PNG + SVG).

Figures:
  2-1  RAG 三阶段流程图
  2-2  ASS + Beaver 三元组在线计算时序
  2-3  FSS DPF/DCF/DICF 关系
  3-1  系统三层架构 + 端到端 8 阶段数据流
  3-2  半诚实两方计算威胁模型
  3-3  语义路 SimHash 粗筛 + 密态 cosine 精排级联
  3-4  密态 Top-K 指示器冒泡排序
  3-5  密态联合编码 56-token 序列结构
  3-6  Cross-Encoder 密态精排
  3-7  密态 Span 阅读器 (起止 + cumsum span mask)
  4-1  明文 vs 密态检索质量对比
  4-2  单条 query 端到端耗时阶段拆解
  4-3  SimHash 比特数消融
  4-4  BM25 Offline / Online 模式对比
  4-5  Reader 架构对比 (启发式 vs SQuAD Span)
"""
from __future__ import annotations

import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle, ConnectionPatch
import numpy as np

matplotlib.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

OUT_DIR = r'D:/桌面/加密rag/ADSMPC-python/paper-output/figures'
os.makedirs(OUT_DIR, exist_ok=True)


def save(fig, name):
    png = os.path.join(OUT_DIR, name + '.png')
    svg = os.path.join(OUT_DIR, name + '.svg')
    fig.savefig(png, dpi=300, bbox_inches='tight', facecolor='white')
    fig.savefig(svg, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  -> {png}')


def _box(ax, xy, w, h, text, fc='#EAF6FB', ec='#555', fs=11, zorder=2, fontweight='normal'):
    x, y = xy
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                 boxstyle='round,pad=0.02,rounding_size=0.08',
                                 linewidth=1.0, edgecolor=ec, facecolor=fc, zorder=zorder))
    ax.text(x, y, text, ha='center', va='center', fontsize=fs,
            color='#222', linespacing=1.4, zorder=zorder + 1, fontweight=fontweight)


def _arrow(ax, p1, p2, text=None, color='#444', lw=1.3, style='-|>', mut=18, ts=9.5):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=mut,
                                  linewidth=lw, color=color, zorder=1))
    if text:
        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.12, text, ha='center', va='bottom', fontsize=ts, color=color)


# ============================================================================
# 图 2-1 RAG 三阶段流程
# ============================================================================
def fig_2_1():
    fig, ax = plt.subplots(figsize=(12, 4.5), dpi=200)
    ax.set_xlim(0, 12); ax.set_ylim(0, 4.5); ax.axis('off')
    # User -> Encoder -> Retriever -> Generator -> Answer
    nodes = [
        (0.9, 2.25, 1.4, 0.9, '查询 q', '#F0E0E0'),
        (3.0, 3.2, 1.6, 0.9, '查询编码器\n(BERT/Sent-BERT)', '#EAF6FB'),
        (3.0, 1.3, 1.6, 0.9, '文档库\n(离线编码)', '#EAF6FB'),
        (5.6, 2.25, 1.8, 1.1, '双路检索\n(Dense + BM25)\nTop-K 召回', '#FFE3B0'),
        (8.1, 2.25, 1.8, 1.1, '生成模型 / 阅读器\n(LLM 或 QA 头)', '#D7E9C8'),
        (10.6, 2.25, 1.4, 0.9, '答案 a', '#F0E0E0'),
    ]
    for x, y, w, h, t, c in nodes:
        _box(ax, (x, y), w, h, t, fc=c)
    arrows = [
        ((1.6, 2.25), (2.2, 3.2)),  # q -> encoder
        ((3.8, 3.2), (4.7, 2.55)),  # encoder -> retrieval
        ((3.8, 1.3), (4.7, 1.95)),  # doc lib -> retrieval
        ((6.5, 2.25), (7.2, 2.25), 'Top-K\n文档'),  # retrieval -> generator
        ((9.0, 2.25), (9.9, 2.25)),  # generator -> answer
    ]
    for a in arrows:
        if len(a) == 3:
            _arrow(ax, a[0], a[1], a[2])
        else:
            _arrow(ax, a[0], a[1])
    # Phase labels at top
    for x, label in [(3.0, '编码阶段'), (5.6, '检索阶段'), (8.1, '生成阶段')]:
        ax.text(x, 4.15, label, ha='center', va='center', fontsize=12, fontweight='bold', color='#444')
    save(fig, 'figure-2-1')


# ============================================================================
# 图 2-2 ASS + Beaver 三元组在线计算时序
# ============================================================================
def fig_2_2():
    fig, ax = plt.subplots(figsize=(11, 6), dpi=200)
    ax.set_xlim(0, 11); ax.set_ylim(0, 6); ax.axis('off')
    # Two vertical lifelines: Party 0, Party 1
    p0_x, p1_x = 2.5, 8.5
    ax.plot([p0_x, p0_x], [0.4, 5.4], color='#888', linestyle='--', linewidth=1, zorder=1)
    ax.plot([p1_x, p1_x], [0.4, 5.4], color='#888', linestyle='--', linewidth=1, zorder=1)
    _box(ax, (p0_x, 5.6), 2.0, 0.6, 'Party 0 (Server)', fc='#E8DCF0', fs=12, fontweight='bold')
    _box(ax, (p1_x, 5.6), 2.0, 0.6, 'Party 1 (Client)', fc='#E8DCF0', fs=12, fontweight='bold')
    # Step boxes
    rows = [
        (4.8, '离线: 持有 (a_0, b_0, c_0)', '离线: 持有 (a_1, b_1, c_1)', 'c = a · b'),
        (4.0, '本地 e_0 = x_0 − a_0\nf_0 = y_0 − b_0', '本地 e_1 = x_1 − a_1\nf_1 = y_1 − b_1', None),
        (3.2, None, None, '交换 e_0, f_0  ↔  e_1, f_1 (一次双向通信)'),
        (2.4, '重构 e = e_0 + e_1,  f = f_0 + f_1 (双方各自完成)', None, None),
        (1.5, '(xy)_0 = e·f + e·b_0 + f·a_0 + c_0', '(xy)_1 =       e·b_1 + f·a_1 + c_1', None),
        (0.7, None, None, '满足 (xy)_0 + (xy)_1 = x·y'),
    ]
    for y, l0, l1, mid in rows:
        if l0:
            _box(ax, (p0_x, y), 3.6, 0.55, l0, fc='#EAF6FB', fs=10)
        if l1:
            _box(ax, (p1_x, y), 3.6, 0.55, l1, fc='#FFE3B0', fs=10)
        if mid:
            ax.text(5.5, y, mid, ha='center', va='center', fontsize=10,
                    color='#555', style='italic')
    # Communication arrow
    _arrow(ax, (3.5, 3.2), (7.5, 3.2), color='#B33', lw=1.5)
    _arrow(ax, (7.5, 3.1), (3.5, 3.1), color='#B33', lw=1.5)
    save(fig, 'figure-2-2')


# ============================================================================
# 图 2-3 FSS DPF/DCF/DICF 关系
# ============================================================================
def fig_2_3():
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=200)
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.5); ax.axis('off')
    # FSS at top, then DPF/DCF, then DICF
    _box(ax, (5.5, 4.7), 4.5, 0.8, 'FSS  (Function Secret Sharing)\nf(x) = f_0(x; k_0) + f_1(x; k_1)',
         fc='#E8DCF0', fs=12, fontweight='bold')
    # DPF and DCF
    _box(ax, (2.5, 3.0), 3.5, 1.0,
         'DPF  Distributed Point Function\nf(x) = β  if x = α  else 0',
         fc='#EAF6FB', fs=11)
    _box(ax, (8.5, 3.0), 3.5, 1.0,
         'DCF  Distributed Comparison Function\nf(x) = β  if x < α  else 0',
         fc='#FFE3B0', fs=11)
    # DICF
    _box(ax, (5.5, 1.2), 6.5, 1.0,
         'DICF  Distributed Interval Comparison Function\n密态比较门  x ≥ y / x ≤ y / x = y',
         fc='#D7E9C8', fs=11.5, fontweight='bold')
    # Arrows
    _arrow(ax, (4.0, 4.3), (3.0, 3.6))
    _arrow(ax, (7.0, 4.3), (8.0, 3.6))
    _arrow(ax, (2.5, 2.4), (4.5, 1.7))
    _arrow(ax, (8.5, 2.4), (6.5, 1.7))
    # Side note
    ax.text(5.5, 0.4, '本文使用的 secure_ge / secure_div / secure_max 均基于 SigmaDICF 与查表优化',
            ha='center', va='center', fontsize=10, color='#666', style='italic')
    save(fig, 'figure-2-3')


# ============================================================================
# 图 3-1 系统三层架构 + 端到端 8 阶段数据流
# ============================================================================
def fig_3_1():
    fig, ax = plt.subplots(figsize=(15, 9), dpi=200)
    ax.set_xlim(-0.5, 15); ax.set_ylim(0, 9); ax.axis('off')
    # Three layers labels
    layer_y = [8.0, 5.2, 1.3]
    layer_h = [1.3, 3.5, 1.4]
    layer_names = ['实验对比层 (experiments)',
                   '应用层 (secure_rag)',
                   '底层 (NssMPClib MPC 框架)']
    layer_colors = ['#FFE3B0', '#EAF6FB', '#D7E9C8']
    for y, h, name, c in zip(layer_y, layer_h, layer_names, layer_colors):
        ax.add_patch(Rectangle((-0.2, y - h / 2), 15.0, h, linewidth=1.2,
                                edgecolor='#555', facecolor=c, alpha=0.25, zorder=0))
        # Label as a small tag on the upper-left of each layer band
        ax.add_patch(Rectangle((-0.2, y + h / 2 - 0.45), 3.6, 0.45,
                                facecolor=c, edgecolor='#555', linewidth=1.0, zorder=1.5))
        ax.text(-0.05, y + h / 2 - 0.22, name, ha='left', va='center',
                fontsize=11, fontweight='bold', color='#333', zorder=2)
    # Experiment layer modules
    exp_items = [(4.6, 7.85, 'data_loader\n(HF Tokenizer)'),
                 (6.7, 7.85, 'metrics\n(IR / Reader)'),
                 (8.8, 7.85, 'run_numerical\n_compare'),
                 (10.9, 7.85, 'run_retrieval\n_eval'),
                 (13.0, 7.85, '子进程隔离\nrunner')]
    for x, y, t in exp_items:
        _box(ax, (x, y), 1.7, 0.85, t, fc='#FFF4DC', fs=9.5)
    # Application layer: 8 stages
    stage_y = 6.0
    stages = [
        (1.7, 'Stage 1\n离线准备\n(db_embs, BM25 三分量,\nSimHash hashes)'),
        (3.6, 'Stage 2\n密态分享\n(模型权重 +\n文档库)'),
        (5.5, 'Stage 3\n密态查询编码\n(SecBERT Seq=8)'),
        (7.4, 'Stage 4\n双路打分\n(SimHash → cosine /\nOnline BM25)'),
        (9.3, 'Stage 5\nTop-K 排序\n+ 密态文档抽取'),
        (11.2, 'Stage 6\n密态联合编码\n(SecBERT Seq=56)'),
        (13.1, 'Stage 7-8\n精排 + Span\nReader'),
    ]
    for x, t in stages:
        _box(ax, (x, stage_y), 1.7, 1.4, t, fc='#EAF6FB', fs=8.5)
    sx = [s[0] for s in stages]
    for i in range(len(sx) - 1):
        _arrow(ax, (sx[i] + 0.85, stage_y), (sx[i + 1] - 0.85, stage_y))
    # App layer secondary row (modules)
    app_modules_y = 4.2
    app_modules = [(2.3, 'server.py\n服务端主流程'),
                   (5.5, 'client.py\n客户端主流程'),
                   (8.7, 'retrieval.py\n双路 + Top-K + Reranker + Reader'),
                   (12.2, 'plaintext.py\n明文 RAG 基线')]
    for x, t in app_modules:
        _box(ax, (x, app_modules_y), 2.5, 0.85, t, fc='#DCE9F4', fs=9.5)
    # Underlying layer modules
    base_items = [(2.0, 1.3, 'RingTensor\n环张量'),
                  (4.3, 1.3, 'ASS\n算术秘密分享'),
                  (6.6, 1.3, 'FSS  DPF/DCF/\nDICF/SigmaDICF'),
                  (8.9, 1.3, 'Beaver 三元组\n(标量+矩阵)'),
                  (11.4, 1.3, 'SecBert / SecLinear /\nSecLayerNorm 等密态层'),
                  (13.6, 1.3, 'TCP 异步通信')]
    for x, y, t in base_items:
        _box(ax, (x, y), 2.0, 0.85, t, fc='#E6F0DA', fs=9)
    # Layer-to-layer dashed arrows
    for x in [4.9, 9.5]:
        ax.add_patch(FancyArrowPatch((x, 7.6), (x, 6.7),
                                      arrowstyle='-|>', mutation_scale=14,
                                      linewidth=1.0, color='#888',
                                      linestyle='dashed', zorder=0))
        ax.add_patch(FancyArrowPatch((x, 4.65), (x, 3.6),
                                      arrowstyle='-|>', mutation_scale=14,
                                      linewidth=1.0, color='#888',
                                      linestyle='dashed', zorder=0))
        ax.add_patch(FancyArrowPatch((x, 3.6), (x, 1.8),
                                      arrowstyle='-|>', mutation_scale=14,
                                      linewidth=1.0, color='#888',
                                      linestyle='dashed', zorder=0))
    save(fig, 'figure-3-1')


# ============================================================================
# 图 3-2 半诚实两方计算威胁模型
# ============================================================================
def fig_3_2():
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=200)
    ax.set_xlim(0, 12); ax.set_ylim(0, 6.5); ax.axis('off')
    # Server box (left)
    _box(ax, (3.0, 5.5), 5.0, 0.8, 'Server (Party 0)', fc='#E8DCF0', fs=13, fontweight='bold')
    _box(ax, (3.0, 4.1), 5.0, 1.5,
         '明文持有:\n· BERT 权重 W\n· 文档库 D (text / embedding / BM25 三分量)\n· 文档 token one-hot\n· 自己的所有秘密分享',
         fc='#F4E8F8', fs=10)
    _box(ax, (3.0, 2.2), 5.0, 1.5,
         '不应直接知道:\n· 客户端 query 内容\n· Top-K 选了哪一篇文档\n· 联合编码 pooler 与精排分数\n· 答案 token id',
         fc='#FFF0F0', fs=10)
    # Client box (right)
    _box(ax, (9.0, 5.5), 5.0, 0.8, 'Client (Party 1)', fc='#E8DCF0', fs=13, fontweight='bold')
    _box(ax, (9.0, 4.1), 5.0, 1.5,
         '明文持有:\n· 查询文本 q\n· 自己的所有秘密分享',
         fc='#F4E8F8', fs=10)
    _box(ax, (9.0, 2.2), 5.0, 1.5,
         '不应直接知道:\n· 文档库具体内容\n· BERT 权重数值\n· 离线 SimHash / BM25 中间量\n· 其它客户端无关的明文',
         fc='#FFF0F0', fs=10)
    # Channel
    _arrow(ax, (5.7, 4.1), (6.3, 4.1), color='#B33', lw=1.6)
    _arrow(ax, (6.3, 3.9), (5.7, 3.9), color='#B33', lw=1.6)
    ax.text(6.0, 3.0, '密态通道\n(ASS / FSS share)',
            ha='center', va='center', fontsize=10, color='#B33', style='italic')
    # Bottom note
    _box(ax, (6.0, 0.8), 11.5, 0.95,
         '安全前提: 半诚实 (Semi-honest, 2PC) ·  双方严格执行协议但试图反推对方明文\n不防护: 主动篡改 · 流量分析侧信道 · 系统结构常量 (N, L, V)',
         fc='#FFF4DC', fs=10.5, fontweight='bold')
    save(fig, 'figure-3-2')


# ============================================================================
# 图 3-3 语义路 SimHash 粗筛 + 密态精排级联
# ============================================================================
def fig_3_3():
    fig, ax = plt.subplots(figsize=(13, 6.2), dpi=200)
    ax.set_xlim(0, 13); ax.set_ylim(0, 6.2); ax.axis('off')
    # Inputs
    _box(ax, (1.4, 5.0), 2.2, 1.0,
         '密态查询\nq̂ ∈ ASS¹ˣʰ',
         fc='#FFE3B0', fs=11)
    _box(ax, (1.4, 3.0), 2.2, 1.0,
         '密态文档库\nD̂ ∈ ASSᴺˣʰ',
         fc='#FFE3B0', fs=11)
    _box(ax, (1.4, 1.0), 2.2, 1.0,
         '离线 SimHash\nĤ_d ∈ {0,1}ᴺˣᴸᵇ',
         fc='#EAF6FB', fs=10.5)
    # Step 1 SimHash query
    _box(ax, (4.4, 5.0), 2.6, 1.0,
         '密态 SimHash 编码\nĥ_q = 𝟙[q̂ · Wᵀ > 0]',
         fc='#D7E9C8', fs=10.5)
    _arrow(ax, (2.5, 5.0), (3.1, 5.0))
    # Hamming
    _box(ax, (7.4, 3.0), 2.6, 1.2,
         '密态 Hamming\nd_H(ĥ_q, Ĥ_d) =\nΣ_l (ĥ_q,l + Ĥ_d,l − 2ĥ_q,l·Ĥ_d,l)',
         fc='#EAF6FB', fs=10)
    _arrow(ax, (5.7, 4.5), (6.6, 3.6))
    _arrow(ax, (2.5, 1.0), (6.1, 2.5))
    # Top-M candidates
    _box(ax, (10.5, 3.0), 2.2, 1.0,
         '候选集指示器\nĈ ∈ ASSᴹˣᴺ\n(密态 Top-M)',
         fc='#FFE3B0', fs=10.5)
    _arrow(ax, (8.7, 3.0), (9.4, 3.0))
    # Refinement
    _box(ax, (7.4, 1.0), 2.6, 1.0,
         '候选 embedding\nê_cand = Ĉ · D̂',
         fc='#EAF6FB', fs=10.5)
    _box(ax, (10.5, 1.0), 2.2, 1.0,
         '密态 cosine 精排\nŝ_cand = (q̂ ⊙ ê_cand).sum',
         fc='#D7E9C8', fs=10)
    _arrow(ax, (2.5, 3.0), (6.1, 1.4))
    _arrow(ax, (10.5, 2.4), (8.7, 1.5))
    _arrow(ax, (8.7, 1.0), (9.4, 1.0))
    # Final output
    _box(ax, (12.0, 5.0), 1.8, 0.9, 'Top-K\n indicator', fc='#FFF4DC', fs=10.5, fontweight='bold')
    _arrow(ax, (11.4, 1.4), (12.0, 4.4))
    save(fig, 'figure-3-3')


# ============================================================================
# 图 3-4 密态 Top-K 指示器冒泡排序
# ============================================================================
def fig_3_4():
    fig, ax = plt.subplots(figsize=(13, 6), dpi=200)
    ax.set_xlim(0, 13); ax.set_ylim(0, 6); ax.axis('off')
    # Header
    ax.text(6.5, 5.6, '密态 Top-K 指示器冒泡排序  (单趟示意, N=5)',
            ha='center', va='center', fontsize=13, fontweight='bold', color='#444')
    # Before / After lines
    scores_before = ['ŝ₀', 'ŝ₁', 'ŝ₂', 'ŝ₃', 'ŝ₄']
    ids_before = ['Î₀', 'Î₁', 'Î₂', 'Î₃', 'Î₄']
    # Row 1 scores
    for i, (s, idv) in enumerate(zip(scores_before, ids_before)):
        x = 1.5 + i * 2.0
        _box(ax, (x, 4.3), 1.2, 0.7, s, fc='#FFE3B0', fs=11)
        _box(ax, (x, 3.4), 1.2, 0.7, idv, fc='#EAF6FB', fs=11)
    # Comparison brackets
    for i in range(4):
        x1 = 1.5 + i * 2.0
        x2 = x1 + 2.0
        ax.add_patch(FancyArrowPatch((x1 + 0.6, 4.3), (x2 - 0.6, 4.3),
                                      arrowstyle='<->', mutation_scale=12, lw=1.0,
                                      color='#888', zorder=0))
        ax.text((x1 + x2) / 2, 4.7, f'ĉ_{i}', ha='center', fontsize=9.5, color='#888')
    # Below: condition formulas
    ax.text(6.5, 2.5, 'ĉ = secure_ge(ŝ_j, ŝ_{j−1})    (FSS DICF 密态比较门)',
            ha='center', va='center', fontsize=11, color='#222', style='italic')
    ax.text(6.5, 1.9,
            'ŝ_{j−1} += ĉ · (ŝ_j − ŝ_{j−1}),   ŝ_j  −= ĉ · (ŝ_j − ŝ_{j−1})',
            ha='center', va='center', fontsize=10.5, color='#222')
    ax.text(6.5, 1.4,
            'Î_{j−1} += ĉ · (Î_j − Î_{j−1}),   Î_j  −= ĉ · (Î_j − Î_{j−1})  (身份证向量同步交换)',
            ha='center', va='center', fontsize=10.5, color='#222')
    _box(ax, (6.5, 0.5), 9.5, 0.55,
         '交换的是身份证向量 (one-hot), 非真实下标; 双方无法独立得知比较结果',
         fc='#FFF4DC', fs=10.5, fontweight='bold')
    save(fig, 'figure-3-4')


# ============================================================================
# 图 3-5 密态联合编码序列结构
# ============================================================================
def fig_3_5():
    fig, ax = plt.subplots(figsize=(13, 5.5), dpi=200)
    ax.set_xlim(0, 13); ax.set_ylim(0, 5.5); ax.axis('off')
    # Three segments
    seg_y = 3.2
    segments = [(2.5, 8, '查询  Q̂\n(ℓ_q = 8)', '#FFE3B0'),
                (6.5, 24, '语义路 Top-1  D̂_sem\n(ℓ_d = 24)', '#EAF6FB'),
                (11.0, 24, '词汇路 Top-1  D̂_lex\n(ℓ_d = 24)', '#D7E9C8')]
    seg_widths = [1.6, 4.8, 4.8]
    for (x, n, t, c), w in zip(segments, seg_widths):
        _box(ax, (x, seg_y), w, 1.2, t, fc=c, fs=11)
    # Concat label
    ax.text(6.5, 4.5, 'Concat → X̂_joint ∈ ASS¹ˣ⁵⁶ˣⱽᵇ', ha='center', va='center',
            fontsize=12, fontweight='bold', color='#444')
    # SecBERT
    _box(ax, (6.5, 1.7), 9.5, 1.0,
         'SecBERT  (2 层 Transformer, SecLinear / SecLayerNorm / SecSoftmax / SecGeLU)',
         fc='#FFF4DC', fs=11, fontweight='bold')
    _arrow(ax, (6.5, 2.5), (6.5, 2.25))
    # Outputs
    _box(ax, (3.5, 0.5), 4.0, 0.6, 'pooler  p̂ ∈ ASS¹ˣʰ', fc='#E8DCF0', fs=10.5)
    _box(ax, (9.5, 0.5), 4.0, 0.6, 'seq_out  Ô ∈ ASS¹ˣ⁵⁶ˣʰ', fc='#E8DCF0', fs=10.5)
    _arrow(ax, (5.5, 1.2), (4.4, 0.85))
    _arrow(ax, (7.5, 1.2), (8.6, 0.85))
    save(fig, 'figure-3-5')


# ============================================================================
# 图 3-6 Cross-Encoder 密态精排
# ============================================================================
def fig_3_6():
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=200)
    ax.set_xlim(0, 12); ax.set_ylim(0, 5.5); ax.axis('off')
    _box(ax, (2.0, 4.0), 2.6, 1.0, '联合编码 pooler\np̂ ∈ ASS¹ˣʰ',
         fc='#FFE3B0', fs=11)
    _box(ax, (2.0, 1.5), 2.6, 1.0, '密态文档库\nD̂ ∈ ASSᴺˣʰ',
         fc='#FFE3B0', fs=11)
    _box(ax, (6.0, 2.75), 3.0, 1.4,
         '密态矩阵乘\nr̂ = p̂ · D̂ᵀ\n(矩阵 Beaver 三元组,\n一次双向通信)',
         fc='#D7E9C8', fs=11)
    _arrow(ax, (3.4, 4.0), (4.7, 3.1))
    _arrow(ax, (3.4, 1.5), (4.7, 2.4))
    _box(ax, (10.2, 2.75), 2.6, 1.0,
         '精排分数\nr̂ ∈ ASS¹ˣᴺ', fc='#EAF6FB', fs=11)
    _arrow(ax, (7.6, 2.75), (8.9, 2.75))
    # Bottom note
    _box(ax, (6.0, 0.5), 11.0, 0.55,
         '客户端 restore r̂ → argsort → 最终 Top-K (服务端不接收精排分数)',
         fc='#FFF4DC', fs=10.5, fontweight='bold')
    save(fig, 'figure-3-6')


# ============================================================================
# 图 3-7 密态 Span 阅读器
# ============================================================================
def fig_3_7():
    fig, ax = plt.subplots(figsize=(14, 7), dpi=200)
    ax.set_xlim(0, 14); ax.set_ylim(0, 7); ax.axis('off')
    # Top: seq_out -> QA head
    _box(ax, (1.6, 6.0), 2.6, 0.9, '联合编码 seq_out\nÔ ∈ ASS¹ˣ⁵⁶ˣʰ',
         fc='#FFE3B0', fs=10.5)
    _box(ax, (5.0, 6.0), 2.6, 0.9,
         '公开 QA 头\nW_qa ∈ R²ˣʰ,  b_qa ∈ R²',
         fc='#EAF6FB', fs=10.5)
    _box(ax, (8.5, 6.0), 3.2, 0.9,
         'Ŝ = Ô · W_qaᵀ + b_qa\n(ASS @ 公开矩阵, 本地无通信)',
         fc='#D7E9C8', fs=10.5)
    _arrow(ax, (2.9, 6.0), (3.7, 6.0))
    _arrow(ax, (6.3, 6.0), (6.9, 6.0))
    # Start/End logits
    _box(ax, (3.0, 4.3), 2.6, 0.8, '起始位置 logits\nŝ_s ∈ ASS¹ˣ⁵⁶',
         fc='#FFE3B0', fs=10.5)
    _box(ax, (8.0, 4.3), 2.6, 0.8, '结束位置 logits\nŝ_e ∈ ASS¹ˣ⁵⁶',
         fc='#FFE3B0', fs=10.5)
    _arrow(ax, (9.5, 5.5), (4.3, 4.7))
    _arrow(ax, (10.3, 5.5), (9.3, 4.7))
    # Argmax
    _box(ax, (3.0, 3.0), 2.6, 0.7, '密态 argmax → p̂_s',
         fc='#EAF6FB', fs=10.5)
    _box(ax, (8.0, 3.0), 2.6, 0.7, '密态 argmax → p̂_e',
         fc='#EAF6FB', fs=10.5)
    _arrow(ax, (3.0, 3.9), (3.0, 3.35))
    _arrow(ax, (8.0, 3.9), (8.0, 3.35))
    # cumsum trick
    _box(ax, (5.5, 1.6), 8.0, 1.0,
         'span_mask cumsum 技巧:\nĉ_s[i] = Σ_{j≤i} p̂_s,j,    ĉ_e[i] = Σ_{j≤i} p̂_e,j\nm̂_span[i] = ĉ_s[i] − ĉ_e[i−1]   (本地累加, 无密态通信)',
         fc='#D7E9C8', fs=10.5)
    _arrow(ax, (3.0, 2.65), (3.5, 2.15))
    _arrow(ax, (8.0, 2.65), (7.5, 2.15))
    # Final output
    _box(ax, (5.5, 0.4), 8.0, 0.55,
         'ŷ = Σ_i m̂_span[i] · X̂_joint[i, :]  →  客户端 restore → 答案 token 序列',
         fc='#FFF4DC', fs=10.5, fontweight='bold')
    save(fig, 'figure-3-7')


# ============================================================================
# 图 4-1 明文 vs 密态检索质量对比
# ============================================================================
def fig_4_1():
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=200)
    metrics = ['Recall@1', 'Recall@3', 'Recall@5', 'Precision@5', 'MRR', 'NDCG@5']
    plaintext = [0.60, 0.70, 0.70, 0.14, 0.65, 0.6631]
    cipher = [0.70, 0.70, 1.00, 0.20, 0.77, 0.8248]
    x = np.arange(len(metrics))
    w = 0.36
    bars1 = ax.bar(x - w / 2, plaintext, w, color='#7AAEC6', edgecolor='#333', label='明文 RAG')
    bars2 = ax.bar(x + w / 2, cipher, w, color='#E0A030', edgecolor='#333', label='密态 RAG')
    for bars in [bars1, bars2]:
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015,
                    f'{b.get_height():.2f}', ha='center', va='bottom', fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel('指标值', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10.5)
    ax.legend(fontsize=11, loc='upper left')
    ax.set_axisbelow(True)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)
    plt.tight_layout()
    save(fig, 'figure-4-1')


# ============================================================================
# 图 4-2 单条 query 端到端耗时阶段拆解
# ============================================================================
def fig_4_2():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=200,
                                   gridspec_kw={'width_ratios': [1.1, 1]})
    # Pie chart
    stages = ['Stage 6 联合编码', 'Stage 3 查询编码', 'Stage 2 模型/文档库分享',
              'Stage 5 Top-K+抽取', 'Stage 4 双路打分', 'Stage 7-8 精排+Reader', '其他']
    times = [56.4, 7.0, 6.5, 1.7, 0.8, 1.0, 5.5]
    colors = ['#7AAEC6', '#E0A030', '#9CC56D', '#C68F89', '#A088C0', '#C0C088', '#BBB']
    wedges, texts, autotexts = ax1.pie(times, labels=stages, colors=colors,
                                        autopct='%1.1f%%', startangle=90,
                                        textprops={'fontsize': 9.5},
                                        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5})
    for at in autotexts:
        at.set_color('white')
        at.set_fontweight('bold')
    ax1.set_title('(a) 单条 query 78.9 s 阶段拆解', fontsize=12, pad=10)

    # Bar: Softmax/LN/GeLU breakdown inside joint encoding
    bars = ['Softmax', 'LayerNorm rsqrt', 'GeLU', '矩阵乘 (Q@K/PV)', 'QKV+O 投影']
    pct = [30, 25, 20, 15, 10]
    bar_colors = ['#C68F89', '#7AAEC6', '#9CC56D', '#E0A030', '#A088C0']
    bars_h = ax2.barh(bars, pct, color=bar_colors, edgecolor='#333')
    for b in bars_h:
        ax2.text(b.get_width() + 0.5, b.get_y() + b.get_height() / 2,
                 f'{int(b.get_width())}%', va='center', fontsize=11)
    ax2.set_xlim(0, 38)
    ax2.set_xlabel('占联合编码比例 (%)', fontsize=11)
    ax2.set_title('(b) Stage 6 联合编码内部算子拆解', fontsize=12, pad=10)
    ax2.invert_yaxis()
    ax2.set_axisbelow(True)
    ax2.grid(axis='x', linestyle='--', alpha=0.5)
    for s in ['top', 'right']:
        ax2.spines[s].set_visible(False)
    plt.tight_layout()
    save(fig, 'figure-4-2')


# ============================================================================
# 图 4-3 SimHash 比特数消融
# ============================================================================
def fig_4_3():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=200)
    # (a) Top-1 hit and consistency
    configs = ['Full cosine\n(无 SimHash)', 'SimHash L=64\nM=5', 'SimHash L=128\nM=5']
    hits = [0.40, 0.30, 0.40]
    consistency = [1.00, 0.90, 1.00]
    x = np.arange(len(configs))
    w = 0.35
    axes[0].bar(x - w / 2, hits, w, color='#7AAEC6', edgecolor='#333', label='sem Top-1 命中率')
    axes[0].bar(x + w / 2, consistency, w, color='#E0A030', edgecolor='#333', label='与 Full cosine 一致率')
    for i, (h, c) in enumerate(zip(hits, consistency)):
        axes[0].text(i - w / 2, h + 0.02, f'{h:.2f}', ha='center', fontsize=10)
        axes[0].text(i + w / 2, c + 0.02, f'{c:.2f}', ha='center', fontsize=10)
    axes[0].set_xticks(x); axes[0].set_xticklabels(configs, fontsize=9.5)
    axes[0].set_ylim(0, 1.15); axes[0].set_ylabel('指标值', fontsize=11)
    axes[0].set_title('(a) 检索精度对比', fontsize=12)
    axes[0].legend(fontsize=10, loc='lower right')
    axes[0].grid(axis='y', linestyle='--', alpha=0.5)
    for s in ['top', 'right']: axes[0].spines[s].set_visible(False)

    # (b) End-to-end time + pool cosine
    configs2 = ['Full cosine\n(baseline)', 'SimHash L=128']
    times = [84.51, 77.63]
    pool_cos = [0.948, 0.877]
    ax = axes[1]
    ax2t = ax.twinx()
    xb = np.arange(len(configs2))
    bars = ax.bar(xb, times, 0.4, color='#9CC56D', edgecolor='#333', label='端到端耗时')
    line = ax2t.plot(xb, pool_cos, 'o-', color='#C68F89', linewidth=2, markersize=10,
                     label='pool cosine sim')
    for b, t in zip(bars, times):
        ax.text(b.get_x() + 0.2, b.get_height() + 1.5, f'{t:.1f}s',
                ha='center', fontsize=10)
    for xi, pc in zip(xb, pool_cos):
        ax2t.text(xi + 0.15, pc, f'{pc:.3f}', ha='left', fontsize=10, color='#C68F89')
    ax.set_xticks(xb); ax.set_xticklabels(configs2, fontsize=10)
    ax.set_ylabel('端到端耗时 (s)', fontsize=11, color='#5A9F30')
    ax2t.set_ylabel('pool cosine sim', fontsize=11, color='#A56361')
    ax.set_ylim(0, 95); ax2t.set_ylim(0.82, 0.96)
    ax.set_title('(b) 性能 / 数值代价', fontsize=12)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    for s in ['top']: ax.spines[s].set_visible(False); ax2t.spines[s].set_visible(False)
    plt.tight_layout()
    save(fig, 'figure-4-3')


# ============================================================================
# 图 4-4 BM25 Offline / Online 模式对比
# ============================================================================
def fig_4_4():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=200)
    modes = ['Offline 模式', 'Online 模式']
    times = [78.05, 78.94]
    pool_cos = [0.9353, 0.9356]
    rerank_cos = [0.9997, 0.9998]
    x = np.arange(len(modes))
    w = 0.35
    axes[0].bar(x, times, 0.45, color=['#7AAEC6', '#E0A030'], edgecolor='#333')
    for i, t in enumerate(times):
        axes[0].text(i, t + 1.0, f'{t:.2f} s', ha='center', fontsize=11, fontweight='bold')
    axes[0].set_xticks(x); axes[0].set_xticklabels(modes, fontsize=11)
    axes[0].set_ylabel('端到端耗时 (s)', fontsize=11)
    axes[0].set_ylim(0, 92)
    axes[0].set_title('(a) 端到端耗时 (+1.1%)', fontsize=12)
    axes[0].grid(axis='y', linestyle='--', alpha=0.5)
    for s in ['top', 'right']: axes[0].spines[s].set_visible(False)

    # (b) Privacy leakage comparison
    axes[1].axis('off')
    axes[1].set_xlim(0, 10); axes[1].set_ylim(0, 5)
    axes[1].text(5, 4.6, '(b) 协议层泄露面对比', ha='center', va='center',
                 fontsize=12, color='#222')
    headers = ['共享内容', 'Offline', 'Online (Pisces 同型)']
    cells = [
        ['服务端预算项', '成品 BM25 矩阵\n[V, N]', 'tf [V,N] / idf [V] /\ndoc_norm [N]'],
        ['客户端能学到', '成品 BM25 分数分布', '原始 tf/idf/doc_norm 统计'],
        ['在线密态运算', '一次点积 (无除法)', '密态 secure_div × V·N'],
    ]
    # Draw a tiny table
    col_x = [1.5, 4.7, 7.8]
    col_w = [3.0, 3.0, 3.0]
    for ci, (cx, h) in enumerate(zip(col_x, headers)):
        axes[1].add_patch(Rectangle((cx - col_w[ci] / 2, 3.6), col_w[ci], 0.55,
                                     facecolor='#E8DCF0', edgecolor='#555', linewidth=0.8))
        axes[1].text(cx, 3.87, h, ha='center', va='center', fontsize=10, fontweight='bold')
    for ri, row in enumerate(cells):
        for ci, (cx, cell) in enumerate(zip(col_x, row)):
            y = 3.0 - ri * 0.9
            fc = '#FFF4DC' if ci == 0 else ('#EAF6FB' if ci == 1 else '#D7E9C8')
            axes[1].add_patch(Rectangle((cx - col_w[ci] / 2, y - 0.35), col_w[ci], 0.85,
                                         facecolor=fc, edgecolor='#888', linewidth=0.5))
            axes[1].text(cx, y, cell, ha='center', va='center', fontsize=9.5, linespacing=1.3)
    plt.tight_layout()
    save(fig, 'figure-4-4')


# ============================================================================
# 图 4-5 Reader 架构对比
# ============================================================================
def fig_4_5():
    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    metrics = ['EM (严格)', 'PM (部分匹配)', 'Token F1']
    heur = [0.00, 0.10, 0.000]
    span = [0.00, 0.30, 0.040]
    x = np.arange(len(metrics))
    w = 0.36
    bars1 = ax.bar(x - w / 2, heur, w, color='#7AAEC6', edgecolor='#333',
                   label='启发式 Reader (pool · seq_out)')
    bars2 = ax.bar(x + w / 2, span, w, color='#E0A030', edgecolor='#333',
                   label='SQuAD Span Reader (start/end 头)')
    for bars in [bars1, bars2]:
        for b in bars:
            v = b.get_height()
            label = f'{v:.3f}' if 'F1' in metrics[int(b.get_x() + w / 2)] else f'{v:.2f}'
            ax.text(b.get_x() + b.get_width() / 2, v + 0.008,
                    label, ha='center', fontsize=10)
    ax.set_xticks(x); ax.set_xticklabels(metrics, fontsize=11)
    ax.set_ylabel('指标值', fontsize=11)
    ax.set_ylim(0, 0.42)
    ax.set_title('Reader 架构消融 (10 条 query, mini_corpus)', fontsize=12, pad=10)
    ax.legend(fontsize=10.5, loc='upper left')
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    for s in ['top', 'right']: ax.spines[s].set_visible(False)
    # Annotation: PM +200%
    ax.annotate('PM ×3', xy=(1 + w / 2, 0.30), xytext=(1.5, 0.36),
                arrowprops=dict(arrowstyle='->', color='#C00', lw=1.5),
                fontsize=12, color='#C00', fontweight='bold')
    plt.tight_layout()
    save(fig, 'figure-4-5')


if __name__ == '__main__':
    for f in [fig_2_1, fig_2_2, fig_2_3, fig_3_1, fig_3_2,
              fig_3_3, fig_3_4, fig_3_5, fig_3_6, fig_3_7,
              fig_4_1, fig_4_2, fig_4_3, fig_4_4, fig_4_5]:
        print(f.__name__)
        f()
    print('Done.')
