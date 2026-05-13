#!/usr/bin/env python3
"""Generate system overall architecture diagram (Figure 2.2)."""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
    "font.size": 8.5,
    "axes.titlesize": 11, "axes.titleweight": "bold",
    "figure.dpi": 200, "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

COLOR_LAYER = {
    "present": "#4472C4",      # blue - presentation
    "service": "#ED7D31",      # orange - service
    "algo":    "#70AD47",      # green - algorithm
    "data":    "#A5A5A5",      # gray - data
    "storage": "#FFC000",      # gold - storage
}
COLOR_BG     = "#FAFAFA"
COLOR_LAYER_BG = "#F0F0EE"
COLOR_ARROW  = "#555555"

def draw_layer_box(ax, x, y, w, h, label, color):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                         facecolor=color, edgecolor=color, linewidth=0,
                         alpha=0.12)
    ax.add_patch(box)
    ax.text(x + 0.15, y + h - 0.25, label, fontsize=8.5, color=color,
            weight="bold", va="top", ha="left")

def draw_module(ax, x, y, w, h, text, color, fontsize=6.8):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                         facecolor=color, edgecolor="white", linewidth=1.0,
                         alpha=0.85)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontsize=fontsize, color="white", weight="bold")

def draw_arrow_v(ax, x, y1, y2, color=COLOR_ARROW):
    ax.annotate("", xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.2))

def main():
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_xlim(0, 28)
    ax.set_ylim(0, 16)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor(COLOR_BG)

    # ---- Layer backgrounds ----
    layers = [
        (0,  0.0, 28, 3.5,  "\u8868\u73b0\u4e0e\u9a8c\u8bc1\u5c42 (Presentation & Validation)", COLOR_LAYER["present"]),
        (0,  3.5, 28, 4.0,  "\u63a8\u7406\u4e0e\u670d\u52a1\u5c42 (Inference & Service)",     COLOR_LAYER["service"]),
        (0,  7.5, 28, 3.5,  "\u7b97\u6cd5\u4e0e\u8bad\u7ec3\u5c42 (Algorithm & Training)",     COLOR_LAYER["algo"]),
        (0, 11.0, 28, 5.0,  "\u6570\u636e\u5904\u7406\u4e0e\u5b58\u50a8\u5c42 (Data & Storage)",     COLOR_LAYER["data"]),
    ]
    for lx, ly, lw, lh, label, lc in layers:
        draw_layer_box(ax, lx, ly, lw, lh, label, lc)

    # ---- Data & Storage Layer (bottom) ----
    mod_w, mod_h = 3.6, 1.0
    base_y = 15.2
    db_y   = 12.2

    draw_module(ax, 1.5, base_y, mod_w, mod_h,
                "train.txt / val.txt / test.txt\n\u8bad\u7ec3/\u9a8c\u8bc1/\u6d4b\u8bd5\u6570\u636e\u96c6",
                COLOR_LAYER["data"])
    draw_module(ax, 6.5, base_y, mod_w, mod_h,
                "vocab_built.py\n\u8bcd\u8868\u4e0e\u6807\u7b7e\u6620\u5c04\u6784\u5efa",
                COLOR_LAYER["data"])
    draw_module(ax, 11.5, base_y, mod_w, mod_h,
                "config.py\n\u8def\u5f84/\u8d85\u53c2\u6570/\u9884\u5904\u7406\u51fd\u6570",
                COLOR_LAYER["data"])
    draw_module(ax, 16.5, base_y, mod_w, mod_h,
                "Subject_data/\n\u539f\u59cb\u9898\u5e93\u8bed\u6599\u6e90\u5934",
                COLOR_LAYER["data"])

    draw_module(ax, 1.5, db_y, mod_w, mod_h,
                "SQLite (app.db)\n\u7528\u6237/\u9898\u76ee/\u53cd\u9988/\u8bed\u6599/\u7248\u672c\u8868",
                COLOR_LAYER["storage"])
    draw_module(ax, 6.5, db_y, mod_w, mod_h,
                "vocab.json / label.json\n\u8bcd\u8868\u4e0e\u6807\u7b7e\u6620\u5c04\u6587\u4ef6",
                COLOR_LAYER["storage"])
    draw_module(ax, 11.5, db_y, mod_w, mod_h,
                "textcnn_model.pth\n\u6a21\u578b\u6743\u91cd\u6301\u4e45\u5316\u6587\u4ef6",
                COLOR_LAYER["storage"])
    draw_module(ax, 16.5, db_y, mod_w, mod_h,
                "incremental_corpus\n\u53cd\u9988\u589e\u91cf\u8bed\u6599\u8868",
                COLOR_LAYER["storage"])

    # ---- Algorithm & Training Layer ----
    algo_y = 9.0
    draw_module(ax, 1.5, algo_y, mod_w, mod_h,
                "textcnn_model.py\nEmbedding+Conv+BN+Pool+FC",
                COLOR_LAYER["algo"])
    draw_module(ax, 6.5, algo_y, mod_w, mod_h,
                "train.py\nDataset/DataLoader/\u8bad\u7ec3\u5faa\u73af/\u9a8c\u8bc1\u9009\u4f18",
                COLOR_LAYER["algo"])
    draw_module(ax, 11.5, algo_y, mod_w, mod_h,
                "evaluate_test.py\n\u6d4b\u8bd5\u96c6\u79bb\u7ebf\u8bc4\u4f30",
                COLOR_LAYER["algo"])
    draw_module(ax, 16.5, algo_y, mod_w, mod_h,
                "Adam\u4f18\u5316\u5668 + CrossEntropy\n\u6a21\u578b\u8bad\u7ec3\u4e0e\u635f\u5931\u51fd\u6570",
                COLOR_LAYER["algo"])

    # ---- Inference & Service Layer ----
    svc_y = 5.5
    draw_module(ax, 1.5, svc_y, mod_w, mod_h,
                "inference.py\nTextClassifier\u7edf\u4e00\u63a8\u7406\u63a5\u53e3",
                COLOR_LAYER["service"])
    draw_module(ax, 6.5, svc_y, mod_w, mod_h,
                "app.py (FastAPI)\nREST API/\u9274\u6743/\u9898\u76ee\u7ba1\u7406/\u770b\u677f",
                COLOR_LAYER["service"])
    draw_module(ax, 11.5, svc_y, mod_w, mod_h,
                "OCR + \u5916\u90e8AI\u6a21\u5757\nRapidOCR/Qwen2.5-VL\u89e3\u6790",
                COLOR_LAYER["service"])
    draw_module(ax, 16.5, svc_y, mod_w, mod_h,
                "\u53cd\u9988\u56de\u6d41\u4e0e\u8bed\u6599\u589e\u91cf\n\u4e1a\u52a1\u95ed\u73af\u7ba1\u7406",
                COLOR_LAYER["service"])

    # ---- Presentation & Validation Layer ----
    pres_y = 1.8
    draw_module(ax, 1.5, pres_y, mod_w, mod_h,
                "index.html / app.js\n\u4e3b\u754c\u9762/\u5f55\u5165/\u5217\u8868/\u770b\u677f",
                COLOR_LAYER["present"])
    draw_module(ax, 6.5, pres_y, mod_w, mod_h,
                "login.html / login.js\n\u767b\u5f55/\u6ce8\u518c/\u4f1a\u8bdd\u7ba1\u7406",
                COLOR_LAYER["present"])
    draw_module(ax, 11.5, pres_y, mod_w, mod_h,
                "style.css\n\u54cd\u5e94\u5f0f\u5e03\u5c40\u4e0e\u89c6\u89c9\u6837\u5f0f",
                COLOR_LAYER["present"])
    draw_module(ax, 16.5, pres_y, mod_w, mod_h,
                "\u5b66\u4e60\u770b\u677f\u53ef\u89c6\u5316\n\u5b66\u79d1\u5206\u5e03/\u638c\u63e1\u5ea6/\u8d8b\u52bf\u56fe",
                COLOR_LAYER["present"])

    # ---- Data flow arrows (right side) ----
    arrow_x = 25.8
    arrow_positions = [
        (14.7, 11.7, "\u2460 \u6570\u636e\u51c6\u5907"),
        (11.2, 8.2,  "\u2461 \u6a21\u578b\u8bad\u7ec3"),
        (7.7,  4.7,  "\u2462 \u63a8\u7406\u670d\u52a1"),
        (4.2,  1.2,  "\u2463 \u524d\u7aef\u5c55\u793a"),
    ]
    vert_lines = [13.5, 9.5, 6.0, 2.8]
    for i, (sy, ey, label) in enumerate(arrow_positions):
        draw_arrow_v(ax, arrow_x, sy, ey)
        ax.text(arrow_x + 0.3, (sy + ey)/2, label, fontsize=6.5,
                color=COLOR_ARROW, ha="left", va="center", weight="bold")

    # ---- Feedback arrow (left side, upward) ----
    fb_x = 0.8
    ax.annotate("", xy=(fb_x, 15.0), xytext=(fb_x, 2.5),
                arrowprops=dict(arrowstyle="->", color="#E76F51", lw=1.5,
                                connectionstyle="arc3,rad=0.2"))
    ax.text(fb_x - 0.3, 8.8, "\u2190 \u53cd\u9988\u56de\u6d41\n\u8bed\u6599\u589e\u91cf",
            fontsize=6.5, color="#E76F51", ha="right", va="center", rotation=0)

    # ---- Title ----
    ax.text(14, 16.4, "\u56fe2.2  \u667a\u80fd\u9519\u9898\u5206\u7c7b\u7cfb\u7edf\u6574\u4f53\u6280\u672f\u67b6\u6784\u56fe",
            ha="center", va="center", fontsize=12, weight="bold")

    # ---- Legend ----
    legend_y_pos = -0.2
    legend_items = [
        (0.5, "\u6570\u636e\u5904\u7406\u5c42", COLOR_LAYER["data"]),
        (4.0, "\u7b97\u6cd5\u8bad\u7ec3\u5c42", COLOR_LAYER["algo"]),
        (7.5, "\u63a8\u7406\u670d\u52a1\u5c42", COLOR_LAYER["service"]),
        (11.0, "\u8868\u73b0\u9a8c\u8bc1\u5c42", COLOR_LAYER["present"]),
        (15.0, "\u6570\u636e\u5b58\u50a8", COLOR_LAYER["storage"]),
    ]
    for lx, llabel, lc in legend_items:
        ax.add_patch(FancyBboxPatch((lx, legend_y_pos), 0.35, 0.25,
                     boxstyle="round,pad=0.02", facecolor=lc))
        ax.text(lx + 0.5, legend_y_pos + 0.12, llabel, fontsize=6.5, color="#444", va="center")

    fig.savefig(os.path.join(OUTPUT_DIR, "fig_system_architecture.png"), dpi=200,
                facecolor="white", edgecolor="none")
    fig.savefig(os.path.join(OUTPUT_DIR, "fig_system_architecture.pdf"),
                facecolor="white", edgecolor="none")
    print("Saved: fig_system_architecture.png / .pdf")

if __name__ == "__main__":
    main()
