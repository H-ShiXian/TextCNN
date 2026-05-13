#!/usr/bin/env python3
"""Generate Chapter 5: business flow diagram and API architecture figure."""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
    "font.size": 8.5,
    "figure.dpi": 200, "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

COLORS = {
    "entry":  "#4472C4",  # blue
    "infer":  "#ED7D31",  # orange
    "confirm":"#70AD47",  # green
    "save":   "#5B9BD5",  # light blue
    "board":  "#A5A5A5",  # gray
    "fb":     "#E76F51",  # coral
    "flush":  "#FFC000",  # gold
    "train":  "#264478",  # navy
}
COLOR_BG = "#FAFAFA"

def draw_rounded_box(ax, x, y, w, h, color, alpha=0.85):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                         facecolor=color, edgecolor="white", linewidth=1.0, alpha=alpha)
    ax.add_patch(box)

def draw_arrow(ax, x1, y1, x2, y2, color="#555", style="->"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=1.4,
                                connectionstyle="arc3,rad=0"))

def draw_node(ax, x, y, w, h, text, color, fontsize=8):
    draw_rounded_box(ax, x, y, w, h, color)
    lines = text.split("\n")
    line_h = h / len(lines)
    for i, line in enumerate(lines):
        ax.text(x + w/2, y + h - line_h/2 - i * line_h, line,
                ha="center", va="center", fontsize=fontsize, color="white", weight="bold")

def main():
    # ===== Figure 5.1: Business Flow =====
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 24)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor(COLOR_BG)

    nw, nh = 4.0, 1.0

    # Row centers
    nodes = [
        (8.0, 22.0, COLORS["entry"],   "用户录入错题\n(文本输入 / 图片上传+OCR)"),
        (8.0, 19.2, COLORS["infer"],   "TextCNN分类推理\n(返回预测类别+置信度)"),
        (8.0, 16.4, COLORS["confirm"], "用户确认/修正类别\n(查看结果,下拉框调整)"),
        (8.0, 13.6, COLORS["save"],    "题目入库保存\n(SQLite questions表)"),
        (8.0, 10.8, COLORS["board"],   "学习看板分析\n(学科分布/掌握度/趋势/薄弱点)"),
        (8.0, 8.0,  COLORS["fb"],      "反馈纠错\n(用户修正→feedback+corpus表)"),
        (8.0, 5.2,  COLORS["flush"],   "语料刷入训练集\n(管理员触发→追加train.txt)"),
        (8.0, 2.4,  COLORS["train"],   "模型重训练迭代\n(重新vocab_built+train)"),
    ]

    for x, y, color, text in nodes:
        draw_node(ax, x, y, nw, nh, text, color)

    # Vertical arrows
    positions = [23.0, 20.2, 17.4, 14.6, 11.8, 9.0, 6.2, 3.4]
    for i in range(len(positions) - 1):
        draw_arrow(ax, 10.0, positions[i], 10.0, positions[i+1])

    # Feedback loop arrow (right side, upward)
    ax.annotate("", xy=(17.0, 18.0), xytext=(17.0, 6.0),
                arrowprops=dict(arrowstyle="->", color="#E76F51", lw=2.0,
                                connectionstyle="arc3,rad=-0.3"))
    ax.text(17.8, 12.0, "反馈回路\n(数据闭环)", fontsize=7.5, color="#E76F51",
            weight="bold", ha="left", va="center")

    # Retrain loop arrow (left side, upward)
    ax.annotate("", xy=(4.0, 20.2), xytext=(4.0, 3.4),
                arrowprops=dict(arrowstyle="->", color="#264478", lw=2.0,
                                connectionstyle="arc3,rad=0.3"))
    ax.text(3.0, 12.0, "模型迭代环路\n(离线重训练)", fontsize=7.5, color="#264478",
            weight="bold", ha="right", va="center")

    ax.text(10.0, 24.4, "图5.1  系统核心业务闭环流程图", ha="center", va="center",
            fontsize=12, weight="bold")

    fig.savefig(os.path.join(OUTPUT_DIR, "fig_business_flow.png"), dpi=200,
                facecolor="white", edgecolor="none")
    fig.savefig(os.path.join(OUTPUT_DIR, "fig_business_flow.pdf"),
                facecolor="white", edgecolor="none")
    print("Saved: fig_business_flow.png / .pdf")
    plt.close(fig)

    # ===== Figure 5.2: API Layer Architecture =====
    fig2, ax2 = plt.subplots(figsize=(13, 7))
    ax2.set_xlim(0, 26)
    ax2.set_ylim(0, 14)
    ax2.set_aspect("equal")
    ax2.axis("off")
    ax2.set_facecolor(COLOR_BG)

    layer_colors = {
        "frontend": "#4472C4",
        "api":      "#ED7D31",
        "infer":    "#70AD47",
        "data":     "#A5A5A5",
    }

    layers = [
        (0, 11.0, 26, 3.0, "前端表现层 (Presentation)", layer_colors["frontend"]),
        (0,  7.5, 26, 3.5, "接口路由层 (API Gateway)", layer_colors["api"]),
        (0,  4.0, 26, 3.5, "推理服务层 (Inference Service)", layer_colors["infer"]),
        (0,  0.5, 26, 3.5, "数据持久化层 (Data Persistence)", layer_colors["data"]),
    ]
    for lx, ly, lw, lh, llab, lc in layers:
        box = FancyBboxPatch((lx, ly), lw, lh, boxstyle="round,pad=0.1",
                             facecolor=lc, edgecolor=lc, linewidth=0, alpha=0.08)
        ax2.add_patch(box)
        ax2.text(lx + 0.3, ly + lh - 0.3, llab, fontsize=8, color=lc,
                 weight="bold", va="top")

    # Frontend modules
    fy = 12.0
    mods_f = [("index.html\n主界面骨架", 1.0), ("app.js\n核心交互逻辑(870行)", 6.5),
              ("login.html+js\n登录/注册/鉴权", 12.0), ("style.css\n全局视觉样式", 17.5),
              ("数据可视化\n看板渲染(Canvas/纯CSS)", 22.0)]
    for text, mx in mods_f:
        draw_node(ax2, mx, fy, 2.8, 0.85, text, layer_colors["frontend"], fontsize=7)

    # API modules
    ay = 8.5
    mods_a = [("用户认证\n登录/注册/Token", 1.0), ("分类推理\n/predict /classify", 6.5),
              ("题目CRUD\n/questions", 12.0), ("OCR/AI解析\n/ocr /parse-*", 17.5),
              ("看板统计\n/dashboard/*", 23.0)]
    for text, mx in mods_a:
        draw_node(ax2, mx, ay, 2.8, 0.85, text, layer_colors["api"], fontsize=7)

    # Inference modules
    iy = 5.0
    mods_i = [("TextCNN模型\nTextCNN(nn.Module)", 1.2), ("TextClassifier\npredict/proba", 6.5),
              ("OCR引擎\nRapidOCR(懒加载)", 12.0), ("外部AI客户端\nQwen2.5-VL API", 17.5),
              ("语料刷入任务\n异步后台线程", 23.0)]
    for text, mx in mods_i:
        draw_node(ax2, mx, iy, 2.8, 0.85, text, layer_colors["infer"], fontsize=7)

    # Data modules
    dy = 1.5
    mods_d = [("SQLite DB\n7表+索引+外键", 1.2), ("训练数据文件\ntrain/val/test.txt", 6.5),
              ("词表/标签映射\nvocab/label.json", 12.0), ("模型权重\n.pth文件", 17.5),
              ("环境变量配置\nTEXTCNN_*系列", 23.0)]
    for text, mx in mods_d:
        draw_node(ax2, mx, dy, 2.8, 0.85, text, layer_colors["data"], fontsize=7)

    # Inter-layer arrows
    for xc in [2.6, 7.9, 13.4, 18.9, 24.4]:
        draw_arrow(ax2, xc, 12.85, xc, 11.95, "#4472C4")
        draw_arrow(ax2, xc, 10.85, xc, 10.05, "#ED7D31")
        draw_arrow(ax2, xc, 6.85, xc, 6.05, "#70AD47")

    ax2.text(13, 14.4, "图5.2  系统分层架构与模块组成", ha="center", va="center",
             fontsize=12, weight="bold")

    fig2.savefig(os.path.join(OUTPUT_DIR, "fig_api_architecture.png"), dpi=200,
                 facecolor="white", edgecolor="none")
    fig2.savefig(os.path.join(OUTPUT_DIR, "fig_api_architecture.pdf"),
                 facecolor="white", edgecolor="none")
    print("Saved: fig_api_architecture.png / .pdf")
    plt.close(fig2)


if __name__ == "__main__":
    main()
