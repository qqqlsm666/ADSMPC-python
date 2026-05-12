"""
Generate figure 1-1: 关键问题 - 研究内容 - 技术路线 关系图.

Produces a high-DPI PNG suitable for thesis insertion.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib

# Use a Chinese-capable font (Windows ships SimHei / Microsoft YaHei)
matplotlib.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(13, 7.5), dpi=200)
ax.set_xlim(0, 13)
ax.set_ylim(0, 7.5)
ax.axis('off')

# Column header positions
col_x = [2.0, 6.5, 11.0]
header_y = 7.0
headers = ['关键问题', '研究内容', '技术路线']
header_colors = ['#C8E6F0', '#FFE3B0', '#D7E9C8']

for x, h, c in zip(col_x, headers, header_colors):
    box = FancyBboxPatch((x - 1.5, header_y - 0.4), 3.0, 0.8,
                         boxstyle="round,pad=0.02,rounding_size=0.1",
                         linewidth=1.2, edgecolor='#333333', facecolor=c, zorder=2)
    ax.add_patch(box)
    ax.text(x, header_y, h, fontsize=15, ha='center', va='center',
            fontweight='bold', color='#222222', zorder=3)

# Three rows of content
row_y = [5.3, 3.4, 1.5]
box_w, box_h = 3.0, 1.4

problems = [
    '客户端查询隐私\n泄露给服务端',
    '服务端文档库与\n模型权重泄露',
    '密态检索-推理联合\n管线工程可行性',
]
contents = [
    '双路密态检索算法\n(语义路 SimHash 粗筛\n+ 词汇路在线 BM25\n+ Top-K 指示器排序)',
    '密态 Cross-Encoder 精排\n+ 抽取式 Span 阅读器\n(基于 SQuAD QA 头)',
    '端到端密态 RAG 系统\n+ 多维消融实验平台\n(数值/检索/性能)',
]
routes = [
    'ASS 算术秘密分享\n+ FSS DPF/DCF/DICF\n+ 密态 Hamming 距离\n+ 密态 secure_div',
    '矩阵 Beaver 三元组\n+ 密态 cumsum 技巧\n+ 公开 QA 头权重',
    'NssMPClib MPC 框架\n+ 子进程隔离运行器\n+ torchcsprng AES-NI',
]

row_colors = [['#EAF6FB', '#FFF4DC', '#EEF6E2']] * 3

for ri, y in enumerate(row_y):
    for ci, (x, text, c) in enumerate(zip(col_x, [problems[ri], contents[ri], routes[ri]], row_colors[ri])):
        box = FancyBboxPatch((x - box_w / 2, y - box_h / 2), box_w, box_h,
                             boxstyle="round,pad=0.02,rounding_size=0.08",
                             linewidth=1.0, edgecolor='#555555', facecolor=c, zorder=2)
        ax.add_patch(box)
        ax.text(x, y, text, fontsize=11, ha='center', va='center',
                color='#222222', linespacing=1.4, zorder=3)

# Arrows between columns at each row
for y in row_y:
    for ax_from, ax_to in [(col_x[0] + box_w / 2 + 0.05, col_x[1] - box_w / 2 - 0.05),
                            (col_x[1] + box_w / 2 + 0.05, col_x[2] - box_w / 2 - 0.05)]:
        arr = FancyArrowPatch((ax_from, y), (ax_to, y),
                              arrowstyle='-|>', mutation_scale=18,
                              linewidth=1.3, color='#444444', zorder=1)
        ax.add_patch(arr)

# Bottom anchor: 实验验证 with arrows from each route
anchor_x, anchor_y = 11.0, 0.35
anchor_box = FancyBboxPatch((anchor_x - 2.8, anchor_y - 0.32), 5.6, 0.64,
                            boxstyle="round,pad=0.02,rounding_size=0.1",
                            linewidth=1.2, edgecolor='#333333', facecolor='#E8DCF0', zorder=2)
# place anchor centered horizontally
anchor_x_center = (col_x[0] + col_x[2]) / 2
anchor_box.set_x(anchor_x_center - 2.8)
ax.add_patch(anchor_box)
ax.text(anchor_x_center, anchor_y, '半诚实两方计算安全模型 · 普通笔记本硬件验证',
        fontsize=11.5, ha='center', va='center', fontweight='bold', color='#222222', zorder=3)

# Title
ax.text(6.5, 7.4, '图 1-1  关键问题、研究内容与技术路线关系图',
        fontsize=12, ha='center', va='center', color='#333333', style='italic', visible=False)

plt.tight_layout(pad=0.5)
out_path = r'D:/桌面/加密rag/ADSMPC-python/paper-output/figures/figure-1-1.png'
plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
print(out_path)
