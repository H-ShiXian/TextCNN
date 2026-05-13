#!/usr/bin/env python3
"""Generate ER diagram for the TextCNN application database."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial"],
    "font.size": 9,
    "axes.titlesize": 11,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

COLORS = {
    "blue": "#4A90D9",
    "teal": "#5BA58B",
    "amber": "#D4A252",
    "slate": "#7B8794",
    "dark": "#2C3E50",
    "light": "#F7F7F5",
    "white": "#FFFFFF",
    "gray": "#BDC3C7",
}

ENTITIES = [
    {
        "name": "users",
        "fields": ["id (PK)", "username", "password_hash", "role", "created_at", "updated_at"],
        "pos": (1.0, 7.0),
        "color": COLORS["blue"],
    },
    {
        "name": "questions",
        "fields": ["id (PK)", "user_id (FK)", "stem", "options_json", "final_label",
                   "mastery_status", "source_type", "is_deleted", "created_at", "..."],
        "pos": (5.0, 7.0),
        "color": COLORS["teal"],
    },
    {
        "name": "question_feedback",
        "fields": ["id (PK)", "question_id (FK)", "user_id (FK)", "question_text",
                   "predicted_label", "corrected_label", "is_corrected", "created_at"],
        "pos": (9.0, 7.0),
        "color": COLORS["amber"],
    },
    {
        "name": "incremental_corpus",
        "fields": ["id (PK)", "question_text", "label", "source_feedback_id (FK)",
                   "write_status", "write_error", "created_at"],
        "pos": (9.0, 3.5),
        "color": COLORS["amber"],
    },
    {
        "name": "model_versions",
        "fields": ["id (PK)", "version_name", "model_path", "notes",
                   "is_active", "is_deleted", "created_at"],
        "pos": (1.0, 1.5),
        "color": COLORS["slate"],
    },
    {
        "name": "user_sessions",
        "fields": ["token (PK)", "user_id (FK)", "created_at",
                   "expired_at", "is_revoked"],
        "pos": (5.0, 3.5),
        "color": COLORS["dark"],
    },
    {
        "name": "question_review_logs",
        "fields": ["id (PK)", "question_id (FK)", "user_id (FK)",
                   "from_status", "to_status", "created_at"],
        "pos": (5.0, 1.5),
        "color": COLORS["slate"],
    },
]

RELATIONSHIPS = [
    ("users", "questions", "1", "N", "user_id"),
    ("users", "question_feedback", "1", "N", "user_id"),
    ("users", "user_sessions", "1", "N", "user_id"),
    ("users", "question_review_logs", "1", "N", "user_id"),
    ("questions", "question_feedback", "1", "N", "question_id"),
    ("questions", "question_review_logs", "1", "N", "question_id"),
    ("question_feedback", "incremental_corpus", "1", "1", "source_feedback_id"),
]

FIG_W, FIG_H = 13.5, 10.0


def draw_entity(ax, entity):
    x, y = entity["pos"]
    color = entity["color"]
    header_height = 0.45
    field_height = 0.30
    n_fields = len(entity["fields"])
    total_h = header_height + n_fields * field_height
    box_w = 3.2
    box_x = x - box_w / 2
    box_y = y - total_h

    outer = FancyBboxPatch(
        (box_x, box_y), box_w, total_h,
        boxstyle="round,pad=0.02", edgecolor=color, facecolor=COLORS["white"],
        linewidth=1.5, zorder=3,
    )
    ax.add_patch(outer)

    header = FancyBboxPatch(
        (box_x, box_y + total_h - header_height), box_w, header_height,
        boxstyle="round,pad=0", edgecolor="none", facecolor=color,
        linewidth=0, zorder=4,
    )
    ax.add_patch(header)

    ax.text(x, box_y + total_h - header_height / 2, entity["name"],
            ha="center", va="center", fontsize=8.5, fontweight="bold",
            color="white", zorder=5)

    sep_y = box_y + total_h - header_height
    ax.plot([box_x + 0.05, box_x + box_w - 0.05], [sep_y, sep_y],
            color=color, linewidth=0.6, zorder=4)

    pk_count = 0
    for i, field in enumerate(entity["fields"]):
        fy = box_y + total_h - header_height - (i + 1) * field_height + field_height / 2
        is_pk = "(PK)" in field
        prefix = "◆ " if is_pk else "  "
        color_f = "#2C3E50" if is_pk else "#555555"
        weight = "bold" if is_pk else "normal"
        ax.text(box_x + 0.15, fy, f"{prefix}{field}",
                ha="left", va="center", fontsize=6.5, color=color_f,
                fontweight=weight, zorder=5, fontfamily="monospace")
        if is_pk:
            pk_count += 1

    if pk_count > 0:
        for i, field in enumerate(entity["fields"]):
            if "(PK)" in field:
                fy_pk = box_y + total_h - header_height - (i + 1) * field_height + field_height / 2
                ax.plot([box_x + 0.08, box_x + box_w - 0.08], [fy_pk - field_height / 2, fy_pk - field_height / 2],
                        color="#EEEEEE", linewidth=0.3, zorder=2)
        if pk_count > 1:
            for i in range(pk_count - 1):
                idx = next(j for j, f in enumerate(entity["fields"]) if "(PK)" in f and j >= i)
                fy_pk = box_y + total_h - header_height - (idx + 1) * field_height
                ax.plot([box_x + 0.08, box_x + box_w - 0.08], [fy_pk, fy_pk],
                        color="#EEEEEE", linewidth=0.3, zorder=2)


def draw_relationship(ax, entities, rel):
    src_name, tgt_name, card1, card2, label = rel
    src = next(e for e in entities if e["name"] == src_name)
    tgt = next(e for e in entities if e["name"] == tgt_name)

    sx, sy = src["pos"]
    tx, ty = tgt["pos"]

    dx = tx - sx
    dy = ty - sy

    if abs(dx) > abs(dy):
        if dx > 0:
            xs, ys = sx + 1.6, sy
            xt, yt = tx - 1.6, ty
        else:
            xs, ys = sx - 1.6, sy
            xt, yt = tx + 1.6, ty
        conn = "arc3,rad=-0.15" if dy < 0 else "arc3,rad=0.15"
    else:
        if dy > 0:
            xs, ys = sx, sy + 1.2
            xt, yt = tx, ty - 1.2
        else:
            xs, ys = sx, sy - 1.2
            xt, yt = tx, ty + 1.2
        conn = "arc3,rad=0.15"

    ax.annotate("", xy=(xt, yt), xytext=(xs, ys),
                arrowprops=dict(arrowstyle="->", color="#7F8C8D", lw=1.0,
                                connectionstyle=conn),
                zorder=1)

    mx, my = (xs + xt) / 2, (ys + yt) / 2
    offset = 0.35
    if abs(dx) > abs(dy):
        my += offset if dy < 0 else -offset
    else:
        mx += offset if dx < 0 else -offset

    card_str = f"{card1}:{card2}"
    ax.text(mx + 0.05, my + 0.05, card_str,
            ha="center", va="center", fontsize=6.5, color="#E74C3C",
            fontweight="bold", zorder=5,
            bbox=dict(boxstyle="round,pad=0.1", facecolor="#FDEDEC",
                      edgecolor="none", alpha=0.9))

    lx, ly = mx, my + 0.30 if dy < 0 else my - 0.30
    ax.text(lx, ly, label,
            ha="center", va="center", fontsize=6, color="#7F8C8D",
            fontstyle="italic", zorder=5)


def main():
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(-0.5, 13.0)
    ax.set_ylim(-0.5, 9.5)
    ax.set_aspect("equal")
    ax.axis("off")

    bg = plt.Rectangle((-0.5, -0.5), 13.5, 10.0, facecolor="#FAFAF8", zorder=0)
    ax.add_patch(bg)

    ax.text(6.25, 9.2, "TextCNN \u7cfb\u7edf\u6570\u636e\u5e93 ER \u56fe",
            ha="center", va="center", fontsize=14, fontweight="bold", color=COLORS["dark"])

    for entity in ENTITIES:
        draw_entity(ax, entity)

    for rel in RELATIONSHIPS:
        draw_relationship(ax, ENTITIES, rel)

    legend_elements = [
        mpatches.Patch(facecolor=COLORS["blue"], label="\u7528\u6237\u4e0e\u8ba4\u8bc1"),
        mpatches.Patch(facecolor=COLORS["teal"], label="\u9898\u76ee\u4e1a\u52a1"),
        mpatches.Patch(facecolor=COLORS["amber"], label="\u53cd\u9988\u4e0e\u8bed\u6599"),
        mpatches.Patch(facecolor=COLORS["slate"], label="\u6a21\u578b\u4e0e\u65e5\u5fd7"),
        mpatches.Patch(facecolor=COLORS["dark"], label="\u4f1a\u8bdd\u7ba1\u7406"),
    ]
    legend = ax.legend(handles=legend_elements, loc="lower right", fontsize=7.5,
                       framealpha=0.8, edgecolor=COLORS["gray"], ncol=2,
                       bbox_to_anchor=(0.98, 0.02))
    legend.set_zorder(10)

    out_path = "figures/fig_er_diagram.png"
    fig.savefig(out_path, dpi=300)
    fig.savefig("figures/fig_er_diagram.pdf", dpi=300)
    print(f"ER diagram saved to {out_path}")


if __name__ == "__main__":
    main()
