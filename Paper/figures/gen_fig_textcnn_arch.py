#!/usr/bin/env python3
"""Generate TextCNN architecture diagram (Figure 2.1)."""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 11, "axes.titleweight": "bold",
    "figure.dpi": 200, "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Colors
COLOR_EMBED  = "#5B9BD5"   # blue - embedding
COLOR_CONV   = "#ED7D31"   # orange - convolution
COLOR_BN     = "#FFC000"   # gold - BN
COLOR_POOL   = "#A5A5A5"   # gray - pooling
COLOR_DROP   = "#4472C4"   # dark blue - dropout
COLOR_FC     = "#70AD47"   # green - FC
COLOR_OUTPUT = "#264478"   # dark navy - output
COLOR_BG     = "#F7F7F5"
COLOR_ARROW  = "#555555"
COLOR_BORDER = "#CCCCCC"

def draw_box(ax, x, y, w, h, text, color, text_color="white", fontsize=8, bold=True):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                         facecolor=color, edgecolor=COLOR_BORDER, linewidth=0.8)
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontsize=fontsize, color=text_color, weight=weight)

def draw_arrow(ax, x1, y1, x2, y2, color=COLOR_ARROW):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.3,
                                connectionstyle="arc3,rad=0"))

def main():
    fig, ax = plt.subplots(1, 1, figsize=(12, 6.5))
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 13)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor(COLOR_BG)

    # ---- Row centers ----
    top_y    = 11.0
    row2_y   = 8.2
    row3a_y  = 6.2
    row3b_y  = 4.2
    row4_y   = 2.2
    row5_y   = 0.5

    box_w = 2.6
    box_h = 0.9

    # ---- Row 1: Input ----
    inp_x = 10.7
    draw_box(ax, inp_x, top_y, box_w, box_h, "输入文本\n(\u201c进程调度是什么\u201d)", "#E2EFDA", "#333", 7, bold=False)

    # ---- Row 2: Embedding ----
    emb_x = 10.7
    draw_box(ax, emb_x, row2_y, box_w, box_h, "Embedding\n词向量映射 (d=128)", COLOR_EMBED)

    draw_arrow(ax, inp_x + box_w/2, top_y, emb_x + box_w/2, row2_y + box_h)

    # ---- Row 3: Multi-scale Convolution Branches ----
    conv_y = row3a_y
    branch_positions = [5.5, 10.7, 15.9]

    for i, (k, cx) in enumerate(zip([2, 3, 4], branch_positions)):
        # Conv layer
        draw_box(ax, cx, conv_y, box_w, box_h,
                 f"卷积层 (h={k})\n100个卷积核", COLOR_CONV)
        draw_arrow(ax, emb_x + box_w/2, row2_y,
                   cx + box_w/2, conv_y + box_h)

        # BN layer
        bn_y = row3b_y
        bn_x = cx
        draw_box(ax, bn_x, bn_y, box_w, box_h,
                 f"BatchNorm1d(100)", COLOR_BN, "#333")
        draw_arrow(ax, cx + box_w/2, conv_y, bn_x + box_w/2, bn_y + box_h)

        # ReLU + Pool
        pool_y = row4_y
        draw_box(ax, cx, pool_y, box_w, box_h,
                 f"ReLU + 全局MaxPool\n\u2192 100\u00d71 特征向量", COLOR_POOL, "#333", 7)
        draw_arrow(ax, bn_x + box_w/2, bn_y, cx + box_w/2, pool_y + box_h)

        # Feature label
        feat_label_y = pool_y - 0.7
        ax.text(cx + box_w/2, feat_label_y, f"100维", ha="center", va="top",
                fontsize=7, color=COLOR_ARROW, style="italic")

    # ---- Row 4: Concatenation ----
    concat_x = 10.7
    concat_y = 0.0
    draw_box(ax, concat_x, concat_y, box_w, box_h,
             "特征拼接\n\u2192 300\u00d71 融合向量", "#A5A5A5", "white", 7)

    for cx in branch_positions:
        draw_arrow(ax, cx + box_w/2, pool_y, concat_x + box_w/2, concat_y + box_h)

    # ---- Row 5: Dropout + FC ----
    fc_x = 4.0
    fc_y = -1.5
    fc_w = 1.8
    fc_h = 0.8
    drop_x = 8.0
    drop_y = -1.5
    drop_w = 1.8
    drop_h = 0.8
    out_x = 13.0
    out_y = -1.5
    out_w = 2.4
    out_h = 0.8

    draw_box(ax, drop_x + 0.3, drop_y, drop_w, drop_h, "Dropout\n(p=0.5)", COLOR_DROP)
    draw_box(ax, fc_x, fc_y, fc_w, fc_h, "全连接层\n(300\u2192|C|)", COLOR_FC)
    draw_box(ax, out_x, out_y, out_w, out_h, "Softmax\n分类概率输出", COLOR_OUTPUT)

    draw_arrow(ax, concat_x + box_w/2, concat_y, fc_x + fc_w/2, fc_y + fc_h)
    draw_arrow(ax, fc_x + fc_w, fc_y + fc_h/2, drop_x + 0.3, drop_y + drop_h/2)
    draw_arrow(ax, drop_x + 0.3 + drop_w, drop_y + drop_h/2, out_x, out_y + out_h/2)

    # ---- Title ----
    ax.text(12, 13.2, "图2.1  TextCNN\u6a21\u578b\u7f51\u7edc\u6574\u4f53\u67b6\u6784\u56fe",
            ha="center", va="center", fontsize=12, weight="bold")

    # ---- Stage labels ----
    stages = [
        (emb_x + box_w/2, top_y + 0.5, "\u2460 \u8f93\u5165\u5c42"),
        (emb_x + box_w/2, row2_y + 0.7, "\u2461 \u5d4c\u5165\u5c42"),
        (15.9 + box_w/2, conv_y + 0.6, "\u2462 \u591a\u5c3a\u5ea6\u5377\u79ef\u5c42"),
        (15.9 + box_w/2, row3b_y + 0.6, "\u2463 BN\u5f52\u4e00\u5316\u5c42"),
        (15.9 + box_w/2, row4_y + 0.6, "\u2464 \u5168\u5c40\u6c60\u5316\u5c42"),
        (concat_x + box_w/2, concat_y + 0.6, "\u2465 \u7279\u5f81\u878d\u5408\u5c42"),
        (out_x + out_w/2, out_y + 0.6, "\u2466 \u5206\u7c7b\u8f93\u51fa\u5c42"),
    ]
    for sx, sy, stext in stages:
        ax.text(sx, sy, stext, ha="center", va="bottom", fontsize=6.5, color="#666")

    # ---- Legend / Annotations ----
    legend_y = 11.8
    ax.text(0.5, legend_y, "\u53c2\u6570\u8bf4\u660e\uff1a", fontsize=7, color="#444", weight="bold")
    param_items = [
        "MAX_LEN=30 (序列长度)",
        "EMBED_DIM=128 (词向量维度)",
        "卷积核窗口 h\u2208{2,3,4}",
        "每窗口100个卷积核",
        "DROPOUT=0.5",
        "\u2211 总参数量 \u2248 v\u00d7128 + 3\u00d7100\u00d7h\u00d7128 + 300\u00d7|C|",
    ]
    for i, item in enumerate(param_items):
        ax.text(0.5, legend_y - 0.5 - i * 0.45, f"  {item}", fontsize=6.5, color="#666")

    fig.savefig(os.path.join(OUTPUT_DIR, "fig_textcnn_architecture.png"), dpi=200,
                facecolor="white", edgecolor="none")
    fig.savefig(os.path.join(OUTPUT_DIR, "fig_textcnn_architecture.pdf"),
                facecolor="white", edgecolor="none")
    print("Saved: fig_textcnn_architecture.png / .pdf")

if __name__ == "__main__":
    main()
