#!/usr/bin/env python3
"""Figure 1: CausalVerify evidence layers in the supplied horizontal style.

This script follows the coordinate system and visual grammar of
`causalverify_each_experiment_horizontal_style.svg`:

  - 1700 x 1120 canvas
  - three stacked horizontal experiment panels
  - dark-navy dashed outer frames
  - grey floating header tabs
  - pale green / blue / purple modules
  - black arrows and code-like artifact boxes

The content is updated to the current CausalVerify v12 state:
Exp A = 259 papers; Exp B = 100 DGPs; calibration = confidence vs L2b+ truth.

Outputs:
  paper/figures/fig1_benchmark_construction_v12.pdf
  paper/figures/fig1_benchmark_construction_v12.png
  paper/figures/fig1_benchmark_construction_v12.svg
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


plt.rcParams["font.family"] = ["Arial", "Helvetica", "DejaVu Sans"]
FS_SCALE = 0.54

INK = "#111827"
NAVY = "#0B1B5E"
HEADER = "#8B8F96"
MUTED = "#374151"

GREEN = "#0B6B2F"
GREEN_BG = "#F1FBF4"
GREEN_EDGE = "#9ACBAA"

BLUE = "#0A55A0"
BLUE_BG = "#DFF0FB"
BLUE_EDGE = "#82B6D5"

YELLOW = "#FFF3BF"
YELLOW_EDGE = "#E5BC45"
PURPLE = "#F5EFFF"
PURPLE_EDGE = "#B792DF"
PURPLE_TEXT = "#5B2D90"

SOFT = "#F8FAFC"
SOFT_EDGE = "#CBD5E1"


def rect(ax, x, y, w, h, *, fc="white", ec=INK, lw=1.5,
         radius=0, linestyle="solid", z=1):
    if radius:
        patch = FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0,rounding_size={radius}",
            facecolor=fc,
            edgecolor=ec,
            linewidth=lw,
            linestyle=linestyle,
            zorder=z,
        )
    else:
        patch = Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                          linewidth=lw, linestyle=linestyle, zorder=z)
    ax.add_patch(patch)
    return patch


def txt(ax, x, y, s, *, fs=20, weight="normal", color=INK,
        ha="center", va="center", family=None, z=5):
    ax.text(
        x, y, s,
        fontsize=fs * FS_SCALE,
        fontweight=weight,
        color=color,
        ha=ha,
        va=va,
        family=family,
        linespacing=1.08,
        zorder=z,
    )


def arrow(ax, x1, y1, x2, y2, *, lw=3, color=INK):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>",
            mutation_scale=18,
            linewidth=lw,
            color=color,
            shrinkA=0,
            shrinkB=0,
            zorder=4,
        )
    )


def elbow_arrow(ax, points, *, lw=3, color=INK, linestyle="solid", mutation_scale=18):
    """Draw a right-angled connector with an arrowhead on the final segment."""
    for (x1, y1), (x2, y2) in zip(points[:-2], points[1:-1]):
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw,
                linestyle=linestyle, zorder=4)
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>",
            mutation_scale=mutation_scale,
            linewidth=lw,
            linestyle=linestyle,
            color=color,
            shrinkA=0,
            shrinkB=0,
            zorder=4,
        )
    )


def outer(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc="white", ec=NAVY, lw=3,
         radius=32, linestyle=(0, (10, 9)))


def header(ax, x, y, w, title, fs=28):
    rect(ax, x, y, w, 58, fc=HEADER, ec=HEADER, lw=0, radius=12, z=8)
    txt(ax, x + w / 2, y + 38, title, fs=fs, weight="bold", color="white", z=9)


def soft_box(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc=SOFT, ec=SOFT_EDGE, lw=1.5, radius=6)


def green_box(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc=GREEN_BG, ec=GREEN_EDGE, lw=3, radius=18)


def blue_box(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc=BLUE_BG, ec=BLUE_EDGE, lw=3, radius=18)


def yellow_box(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc=YELLOW, ec=YELLOW_EDGE, lw=2.2, radius=10)


def purple_box(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc=PURPLE, ec=PURPLE_EDGE, lw=2.2, radius=10)


def dashed_box(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc="white", ec=INK, lw=2.4,
         radius=24, linestyle=(0, (9, 8)))


def code_box(ax, x, y, w, h):
    rect(ax, x, y, w, h, fc="white", ec=INK, lw=1.7, radius=3)


def doc_icon(ax, x, y):
    ax.plot(
        [x, x + 70, x + 95, x + 95, x, x],
        [y, y, y + 25, y + 105, y + 105, y],
        color=INK,
        linewidth=2,
        zorder=4,
    )
    ax.plot([x + 70, x + 70, x + 95], [y, y + 25, y + 25], color=INK, linewidth=2, zorder=4)
    for yy, ww in [(35, 45), (57, 58), (79, 50)]:
        ax.plot([x + 20, x + 20 + ww], [y + yy, y + yy], color=INK, linewidth=2, zorder=4)


def mini_network(ax, x, y, scale=1.0):
    pts = [
        (x, y),
        (x + 42 * scale, y - 16 * scale),
        (x + 82 * scale, y),
        (x + 22 * scale, y + 38 * scale),
        (x + 72 * scale, y + 36 * scale),
    ]
    for a, b in [(0, 1), (1, 2), (1, 3), (3, 4)]:
        ax.plot([pts[a][0], pts[b][0]], [pts[a][1], pts[b][1]],
                color=INK, linewidth=2, zorder=4)
    for i, (px, py) in enumerate(pts):
        ax.add_patch(Circle((px, py), 11 * scale,
                            facecolor=BLUE_BG if i % 2 else "white",
                            edgecolor=INK, linewidth=2, zorder=5))


def mini_table(ax, x, y):
    rect(ax, x, y, 200, 95, fc="#E8F4C9", ec="#91BD63", lw=2)
    rect(ax, x, y, 200, 28, fc="#A6CF58", ec="#A6CF58", lw=0)
    for tx, lab in [(x + 33, "D"), (x + 100, "Y"), (x + 165, "X")]:
        txt(ax, tx, y + 20, lab, fs=16, weight="bold", color="white")
    ax.plot([x + 65, x + 65], [y, y + 95], color="#91BD63", linewidth=2)
    ax.plot([x + 130, x + 130], [y, y + 95], color="#91BD63", linewidth=2)
    ax.plot([x, x + 200], [y + 28, y + 28], color="#91BD63", linewidth=2)
    ax.plot([x, x + 200], [y + 60, y + 60], color="#91BD63", linewidth=2)
    vals = [("1", "5.6", "97"), ("0", "7.8", "87"), ("1", "3.0", "56")]
    ys = [y + 46, y + 69, y + 89]
    for row, yy in zip(vals, ys):
        for xx, val in zip([x + 33, x + 100, x + 165], row):
            txt(ax, xx, yy, val, fs=16)


def write_code(ax, x, y, lines, fs=13, dy=23):
    for i, line in enumerate(lines):
        txt(ax, x, y + i * dy, line, fs=fs, ha="left", family="monospace")


def experiment_a(ax):
    outer(ax, 55, 55, 1590, 305)
    header(ax, 520, 32, 660, "Exp A: Real Papers → Text-Agreement Tasks")

    soft_box(ax, 95, 110, 170, 76)
    txt(ax, 180, 144, "Published", fs=24)
    txt(ax, 180, 174, "papers", fs=24)
    arrow(ax, 180, 186, 180, 224)

    green_box(ax, 70, 228, 225, 78)
    txt(ax, 182, 260, "RQ / DD / IC", fs=23, color=GREEN, weight="bold")
    txt(ax, 182, 290, "prompt fields", fs=20)
    txt(ax, 330, 270, "{", fs=26, weight="bold")
    txt(ax, 325, 306, "259 active published papers", fs=13, color=MUTED)

    doc_icon(ax, 425, 135)
    txt(ax, 472, 300, "V2'' fields", fs=22)
    txt(ax, 472, 330, "database", fs=22)

    arrow(ax, 540, 210, 612, 210)

    dashed_box(ax, 640, 100, 360, 210)
    txt(ax, 820, 140, "Anti-leakage", fs=24, weight="bold")
    txt(ax, 820, 170, "+ fidelity checks", fs=24, weight="bold")
    yellow_box(ax, 690, 198, 260, 58)
    txt(ax, 820, 222, "No method names", fs=16, weight="bold")
    txt(ax, 820, 244, "in RQ / DD / IC", fs=16)
    for base_x, base_y, color1, color2 in [(700, 130, "#168AAD", "#0B1B5E"), (925, 135, "#9ACBAA", "#2F7D32")]:
        pts = [(base_x, base_y), (base_x + 40, base_y - 12), (base_x + 55, base_y + 20)]
        ax.plot([pts[0][0], pts[1][0], pts[2][0], pts[0][0]],
                [pts[0][1], pts[1][1], pts[2][1], pts[0][1]], color=INK, linewidth=2)
        for j, (px, py) in enumerate(pts):
            ax.add_patch(Circle((px, py), 8, facecolor=color1 if j != 1 else color2, edgecolor="none", zorder=5))

    arrow(ax, 1000, 210, 1072, 210)

    code_box(ax, 1100, 105, 330, 105)
    write_code(ax, 1125, 142, [
        '"paper_id": "paper_..."',
        '"prompt": RQ + DD + IC',
        '"label": method, direction',
        '"layers": L1, L3, L4',
    ], fs=11.5, dy=19)
    blue_box(ax, 1120, 222, 290, 48)
    txt(ax, 1265, 250, "Text-agreement scores", fs=19)
    purple_box(ax, 1100, 290, 330, 54)
    txt(ax, 1265, 304, "Human validation audit", fs=13.5, weight="bold", color=PURPLE_TEXT)
    txt(ax, 1265, 321, "30 blind PDF labels vs 4-LLM consensus", fs=11.2)
    txt(ax, 1265, 336, "method 60% κ=.606; direction 47.6% κ=.294", fs=10.7)

    blue_box(ax, 1485, 135, 125, 102)
    txt(ax, 1548, 175, "L1 / L3", fs=22)
    txt(ax, 1548, 205, "/ L4", fs=22)
    txt(ax, 1548, 252, "reported metrics", fs=11, color=MUTED)
    arrow(ax, 1265, 210, 1265, 222, lw=2, color="#64748B")
    arrow(ax, 1180, 210, 1180, 290, lw=2, color="#64748B")
    txt(ax, 1150, 255, "post-freeze\ncheck", fs=9.5, color="#64748B", ha="right")
    elbow_arrow(ax, [(1410, 246), (1450, 246), (1450, 184), (1485, 184)])


def experiment_b(ax):
    outer(ax, 55, 410, 1590, 305)
    header(ax, 500, 387, 700, "Exp B: Synthetic DGPs → Execution-Grounded Tasks")

    soft_box(ax, 95, 470, 170, 76)
    txt(ax, 180, 504, "Synthetic", fs=24)
    txt(ax, 180, 534, "DGPs", fs=24)
    arrow(ax, 180, 546, 180, 584)

    green_box(ax, 70, 588, 225, 78)
    txt(ax, 182, 620, "Treatment +", fs=24)
    txt(ax, 182, 650, "outcome data", fs=24)
    txt(ax, 330, 628, "{", fs=26, weight="bold")
    txt(ax, 325, 682, "100 DID / ES / IV / RDD scenarios", fs=13, color=MUTED)

    mini_table(ax, 405, 478)
    blue_box(ax, 415, 600, 180, 58)
    txt(ax, 505, 625, "Fixed-seed", fs=20)
    txt(ax, 505, 650, "realised data", fs=20)

    arrow(ax, 620, 565, 690, 565)

    dashed_box(ax, 720, 455, 340, 205)
    txt(ax, 890, 495, "Canonical", fs=24, weight="bold")
    txt(ax, 890, 525, "estimators", fs=24, weight="bold")
    code_box(ax, 765, 550, 250, 78)
    write_code(ax, 787, 578, ["lm(Y ~ D + X)", "ivreg(Y ~ D | Z)", "canonical β̂"], fs=13, dy=22)

    arrow(ax, 1060, 565, 1130, 565)

    code_box(ax, 1160, 460, 330, 145)
    write_code(ax, 1185, 492, [
        '"description": ...',
        '"data_file": "sXX.csv"',
        '"model_output": R code',
        '"score": L1 → L2a → L2b → L2b+',
    ])
    blue_box(ax, 1180, 615, 290, 58)
    txt(ax, 1325, 650, "Execution task", fs=22)

    blue_box(ax, 1515, 485, 95, 100)
    txt(ax, 1562, 525, "L2b+", fs=22)
    txt(ax, 1562, 555, "truth", fs=22)
    txt(ax, 1562, 600, "verified effect", fs=11, color=MUTED)
    arrow(ax, 1325, 605, 1325, 615, lw=2, color="#64748B")
    elbow_arrow(ax, [(1470, 644), (1500, 644), (1500, 535), (1515, 535)])


def calibration(ax):
    outer(ax, 55, 765, 1590, 305)
    header(ax, 388, 742, 924, "Calibration: Does the Model Know When Its Workflow Is Wrong?", fs=27)

    soft_box(ax, 95, 825, 170, 76)
    txt(ax, 180, 858, "Model's", fs=24)
    txt(ax, 180, 888, "Exp B answer", fs=24)
    arrow(ax, 180, 901, 180, 939)

    green_box(ax, 70, 943, 225, 78)
    txt(ax, 182, 975, "Generated code", fs=24)
    txt(ax, 182, 1005, "+ estimate", fs=24)
    txt(ax, 330, 985, "{", fs=26, weight="bold")

    code_box(ax, 405, 840, 230, 120)
    write_code(ax, 430, 872, ['"analysis": R code', '"estimate": β̂', '"hidden_truth": not shown'])
    txt(ax, 520, 1000, "Returned answer", fs=22)

    arrow(ax, 650, 900, 730, 900)

    dashed_box(ax, 760, 825, 310, 165)
    txt(ax, 915, 870, "Self-assessed", fs=24, weight="bold")
    txt(ax, 915, 900, "confidence", fs=24, weight="bold")
    purple_box(ax, 805, 925, 220, 45)
    txt(ax, 915, 953, "method / specification / number", fs=16)

    arrow(ax, 1070, 900, 1150, 900)

    code_box(ax, 1180, 835, 320, 115)
    blue_box(ax, 1200, 860, 125, 60)
    txt(ax, 1262, 885, "correct?", fs=16, weight="bold", color=BLUE)
    txt(ax, 1262, 907, "L2b+ pass/fail", fs=16, color=MUTED)
    purple_box(ax, 1350, 860, 125, 60)
    txt(ax, 1412, 885, "confidence", fs=16, weight="bold", color=PURPLE)
    txt(ax, 1412, 907, "ECE + gap", fs=16, color=MUTED)
    txt(ax, 1340, 995, "Calibration analysis", fs=22)

    arrow(ax, 1500, 890, 1540, 890)
    blue_box(ax, 1540, 835, 70, 115)
    txt(ax, 1575, 875, "Gap", fs=22)
    txt(ax, 1575, 905, "plot", fs=22)


def main():
    fig, ax = plt.subplots(figsize=(17.0, 11.2))
    fig.subplots_adjust(left=0.010, right=0.990, top=0.990, bottom=0.010)
    ax.set_xlim(0, 1700)
    ax.set_ylim(1120, 0)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    rect(ax, 0, 0, 1700, 1120, fc="white", ec="none", lw=0)

    experiment_a(ax)
    experiment_b(ax)
    calibration(ax)

    out = Path("paper/figures/fig1_benchmark_construction_v12")
    out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png", "svg"):
        path = out.with_suffix(f".{ext}")
        fig.savefig(path, dpi=300 if ext == "png" else None)
        print(f"  ✓ {path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
