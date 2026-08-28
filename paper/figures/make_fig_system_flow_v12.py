"""
Presentation-style CausalVerify v12 framework diagram.

This intentionally mirrors the older "CausalVerify Benchmarks" slide style:
large dashed containers, grey section badges, side-by-side Exp A / Exp B
blocks, a shared model row, matched task interfaces, and an evaluation/output
row. The content is updated to the frozen v12 state.

Outputs:
  paper/figures/fig_system_flow_v12.pdf
  paper/figures/fig_system_flow_v12.png
  paper/figures/fig_system_flow_v12.svg
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle, Rectangle, Polygon


INK = "#111111"
DASH = "#1F2A7C"
GREY = "#9CA0AA"
GREEN = "#2F8A4A"
GREEN_BG = "#F3FBF4"
BLUE = "#2D7FC1"
BLUE_BG = "#F3FAFF"
PURPLE = "#7C4D99"
PURPLE_BG = "#FBF5FF"
GOLD = "#D59A22"
GOLD_BG = "#FFF9E8"
PANEL_GREY = "#F4F5F7"
PANEL_GREY_EDGE = "#9CA0AA"
RED = "#D62728"


def rounded(ax, x, y, w, h, *, fc="white", ec=INK, lw=1.4, radius=0.02,
            linestyle="solid", alpha=1.0, z=1):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.008,rounding_size={radius}",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
        linestyle=linestyle,
        alpha=alpha,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def label_box(ax, x, y, text, w=0.24, h=0.035, fs=13):
    rounded(ax, x - w / 2, y - h / 2, w, h, fc=GREY, ec="#858995", lw=0.8, radius=0.008, z=20)
    ax.text(x, y, text, ha="center", va="center", color="white", fontsize=fs,
            fontweight="bold", zorder=21)


def text(ax, x, y, s, *, fs=11, weight="normal", color=INK, ha="center", va="center", z=10):
    ax.text(x, y, s, fontsize=fs, fontweight=weight, color=color, ha=ha, va=va,
            linespacing=1.12, zorder=z)


def arrow(ax, x1, y1, x2, y2, *, color=INK, lw=1.5, dashed=False, z=5):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=lw,
        color=color,
        linestyle=(0, (3, 3)) if dashed else "solid",
        shrinkA=4,
        shrinkB=4,
        zorder=z,
    )
    ax.add_patch(arr)
    return arr


def doc_icon(ax, x, y, s=0.045):
    for dx in [-0.010, 0.000, 0.010]:
        ax.add_patch(Rectangle((x - s / 2 + dx, y - s / 2 - dx * 0.2), s * 0.72, s,
                               facecolor="white", edgecolor=INK, linewidth=1.5, zorder=8))
    ax.add_patch(Polygon([[x + s * 0.12, y + s * 0.50],
                          [x + s * 0.28, y + s * 0.34],
                          [x + s * 0.12, y + s * 0.34]],
                         closed=True, facecolor="#EFEFEF", edgecolor=INK, linewidth=1.0, zorder=9))
    for k in range(4):
        ax.plot([x - s * 0.25, x + s * 0.16], [y + s * (0.22 - k * 0.16)] * 2,
                color=INK, linewidth=1.0, zorder=10)


def dgp_icon(ax, x, y, s=0.045):
    pts = [(x - s * 0.35, y + s * 0.18), (x, y + s * 0.05),
           (x + s * 0.34, y + s * 0.20), (x - s * 0.12, y - s * 0.28),
           (x + s * 0.30, y - s * 0.25)]
    edges = [(0, 1), (1, 2), (1, 3), (3, 4)]
    for a, b in edges:
        ax.plot([pts[a][0], pts[b][0]], [pts[a][1], pts[b][1]], color=INK, linewidth=1.3, zorder=8)
    cols = ["#CFE6F3", "#D8D8D8", "#CFE6F3", "#CFE6F3", "#D8D8D8"]
    for (px, py), c in zip(pts, cols):
        ax.add_patch(Circle((px, py), s * 0.13, facecolor=c, edgecolor=INK, linewidth=1.2, zorder=9))


def prompt_icon(ax, x, y, s=0.045):
    rounded(ax, x - s * 0.45, y - s * 0.26, s * 0.9, s * 0.52,
            fc="white", ec=INK, lw=1.4, radius=0.006, z=8)
    ax.add_patch(Polygon([[x - s * 0.10, y - s * 0.26],
                          [x - s * 0.02, y - s * 0.40],
                          [x + s * 0.04, y - s * 0.26]],
                         facecolor="white", edgecolor=INK, linewidth=1.0, zorder=9))
    ax.plot([x - s * 0.25, x + s * 0.25], [y + s * 0.08, y + s * 0.08], color=INK, lw=1.0, zorder=10)
    ax.plot([x - s * 0.25, x + s * 0.12], [y - s * 0.06, y - s * 0.06], color=INK, lw=1.0, zorder=10)


def llm_icon(ax, x, y, s=0.044):
    ax.add_patch(Circle((x, y), s * 0.48, facecolor="#F9F9F9", edgecolor=INK, linewidth=1.2, zorder=8))
    text(ax, x, y, "LLM", fs=8.5, weight="bold", z=10)


def code_icon(ax, x, y, s=0.045):
    rounded(ax, x - s * 0.45, y - s * 0.32, s * 0.9, s * 0.64,
            fc="white", ec=INK, lw=1.4, radius=0.006, z=8)
    ax.plot([x - s * 0.25, x + s * 0.25], [y + s * 0.20, y + s * 0.20], color=INK, lw=1.0, zorder=9)
    text(ax, x, y - s * 0.08, "</>", fs=10, weight="bold", z=10)


def terminal_icon(ax, x, y, s=0.045):
    rounded(ax, x - s * 0.45, y - s * 0.32, s * 0.9, s * 0.64,
            fc="white", ec=INK, lw=1.4, radius=0.006, z=8)
    ax.plot([x - s * 0.25, x + s * 0.25], [y + s * 0.20, y + s * 0.20], color=INK, lw=1.0, zorder=9)
    text(ax, x - s * 0.05, y - s * 0.05, ">", fs=12, weight="bold", z=10)


def bars_icon(ax, x, y, s=0.045):
    rounded(ax, x - s * 0.45, y - s * 0.32, s * 0.9, s * 0.64,
            fc="white", ec=INK, lw=1.4, radius=0.006, z=8)
    for i, h in enumerate([0.18, 0.32, 0.48]):
        ax.add_patch(Rectangle((x - s * 0.25 + i * s * 0.18, y - s * 0.22),
                               s * 0.11, s * h, facecolor=INK, edgecolor=INK, zorder=9))


def check_icon(ax, x, y, s=0.045):
    ax.add_patch(Circle((x, y + s * 0.10), s * 0.18, facecolor=INK, edgecolor=INK, zorder=8))
    rounded(ax, x - s * 0.35, y - s * 0.33, s * 0.7, s * 0.34,
            fc=INK, ec=INK, lw=1.0, radius=0.02, z=8)
    ax.add_patch(Circle((x + s * 0.28, y - s * 0.05), s * 0.16, facecolor="white", edgecolor=INK, linewidth=1.1, zorder=9))
    text(ax, x + s * 0.28, y - s * 0.05, "✓", fs=9, weight="bold", z=10)


def metric_row(ax, x, y, tag, desc):
    rounded(ax, x, y, 0.20, 0.035, fc="white", ec=PURPLE, lw=0.9, radius=0.006)
    rounded(ax, x + 0.01, y + 0.007, 0.038, 0.021, fc="#F9F9F9", ec=PURPLE, lw=0.8, radius=0.004)
    text(ax, x + 0.029, y + 0.0175, tag, fs=8.7, weight="bold")
    text(ax, x + 0.058, y + 0.0175, desc, fs=8.9, ha="left")


def model_badge(ax, x, y, label, color, marker):
    ax.scatter([x], [y + 0.018], s=260, marker=marker, color=color, edgecolor="white", linewidth=1.0, zorder=10)
    text(ax, x, y - 0.020, label, fs=9.3)


def pipeline_step(ax, x, y, icon_fn, caption):
    icon_fn(ax, x, y + 0.045)
    text(ax, x, y - 0.010, caption, fs=9.0)


def main():
    fig, ax = plt.subplots(figsize=(14.0, 8.0))
    fig.subplots_adjust(left=0.015, right=0.985, top=0.960, bottom=0.040)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Overall top group.
    rounded(ax, 0.065, 0.745, 0.870, 0.205, fc="white", ec=DASH, lw=1.2,
            radius=0.018, linestyle=(0, (4, 4)))
    label_box(ax, 0.50, 0.975, "CausalVerify v12 Benchmarks", w=0.24, h=0.040, fs=13)

    # Exp A / Exp B top blocks.
    rounded(ax, 0.085, 0.785, 0.330, 0.125, fc=GREEN_BG, ec=GREEN, lw=1.0, radius=0.008)
    rounded(ax, 0.585, 0.785, 0.330, 0.125, fc=BLUE_BG, ec=BLUE, lw=1.0, radius=0.008)
    text(ax, 0.250, 0.892, "Exp A : Real Papers — Recognition", fs=10.6, weight="bold")
    text(ax, 0.750, 0.892, "Exp B: Synthetic DGPs — Execution", fs=10.6, weight="bold")
    doc_icon(ax, 0.250, 0.835, 0.072)
    dgp_icon(ax, 0.750, 0.835, 0.082)

    # Shared model row.
    rounded(ax, 0.015, 0.630, 0.97, 0.085, fc="white", ec=DASH, lw=1.2,
            radius=0.014, linestyle=(0, (4, 4)))
    label_box(ax, 0.50, 0.715, "LLMs", w=0.12, h=0.036, fs=11.5)
    arrow(ax, 0.250, 0.785, 0.250, 0.715, dashed=True)
    arrow(ax, 0.750, 0.785, 0.750, 0.715, dashed=True)
    model_specs = [
        ("Opus", "#D4785A", "o"),
        ("Sonnet", "#9B82BB", "^"),
        ("GPT-4o", "#5B8DB8", "s"),
        ("o3", "#7D9CAD", "D"),
        ("Gemini 2.5", "#6BA898", "*"),
        ("Kimi-128k", "#D4A85A", "P"),
        ("GPT-5", "#3D5A80", "X"),
    ]
    for x, spec in zip([0.13, 0.255, 0.38, 0.505, 0.63, 0.755, 0.88], model_specs):
        model_badge(ax, x, 0.670, *spec)

    # Matched task interfaces.
    rounded(ax, 0.015, 0.350, 0.97, 0.245, fc="white", ec=DASH, lw=1.2,
            radius=0.014, linestyle=(0, (4, 4)))
    label_box(ax, 0.50, 0.600, "Two Matched Task Interfaces", w=0.27, h=0.036, fs=11.5)
    rounded(ax, 0.025, 0.375, 0.43, 0.180, fc=GREEN_BG, ec=GREEN, lw=1.0, radius=0.010)
    rounded(ax, 0.545, 0.375, 0.43, 0.180, fc=BLUE_BG, ec=BLUE, lw=1.0, radius=0.010)
    text(ax, 0.240, 0.535, "A. Text Pipeline (Exp A)", fs=10.5, weight="bold", color=GREEN)
    text(ax, 0.760, 0.535, "B. Execution Pipeline (Exp B)", fs=10.5, weight="bold", color=BLUE)

    def layer_card(cx, tag, desc, *, fc, ec):
        rounded(ax, cx - 0.045, 0.430, 0.090, 0.060,
                fc=fc, ec=ec, lw=1.1, radius=0.008)
        text(ax, cx, 0.466, tag, fs=12.0, weight="bold")
        text(ax, cx, 0.443, desc, fs=7.9)

    # Middle row intentionally shows only the scoring layers. Detailed input /
    # prompt / execution mechanics are described in the text and tables.
    xs_a = [0.125, 0.240, 0.355]
    a_layers = [
        ("L1", "output"),
        ("L3", "method"),
        ("L4", "direction"),
    ]
    for x, (tag, desc) in zip(xs_a, a_layers):
        layer_card(x, tag, desc, fc="white", ec=GREEN)
    for x1, x2 in zip(xs_a[:-1], xs_a[1:]):
        arrow(ax, x1 + 0.045, 0.460, x2 - 0.045, 0.460)

    xs_b = [0.605, 0.715, 0.825, 0.925]
    b_layers = [
        ("L1", "output"),
        ("L2a", "R code"),
        ("L2b", "runs"),
        ("L2b+", "β match"),
    ]
    for x, (tag, desc) in zip(xs_b, b_layers):
        layer_card(x, tag, desc, fc="white", ec=BLUE)
    for x1, x2 in zip(xs_b[:-1], xs_b[1:]):
        arrow(ax, x1 + 0.045, 0.460, x2 - 0.045, 0.460)

    # Evaluation / outputs row.
    rounded(ax, 0.015, 0.040, 0.97, 0.265, fc="white", ec=DASH, lw=1.2,
            radius=0.014, linestyle=(0, (4, 4)))
    label_box(ax, 0.50, 0.310, "Evaluation, Comparison & Outputs", w=0.31, h=0.036, fs=11.5)

    rounded(ax, 0.035, 0.062, 0.225, 0.208, fc=PURPLE_BG, ec=PURPLE, lw=1.0, radius=0.010)
    text(ax, 0.147, 0.256, "Evaluation Dimensions", fs=10.2, weight="bold", color=PURPLE)
    metric_row(ax, 0.055, 0.205, "L1", "Output exists")
    metric_row(ax, 0.055, 0.169, "L2a", "R code present (Exp B)")
    metric_row(ax, 0.055, 0.133, "L2b", "Code executes (Exp B)")
    metric_row(ax, 0.055, 0.097, "L2b+", "Coefficient match (Exp B)")
    metric_row(ax, 0.055, 0.061, "L3/L4", "Text agreement (Exp A)")

    rounded(ax, 0.335, 0.080, 0.330, 0.190, fc=PANEL_GREY, ec=PANEL_GREY_EDGE, lw=1.0, radius=0.010)
    text(ax, 0.500, 0.245, "Core Finding", fs=10.2, weight="bold", color="#666A73")
    text(ax, 0.500, 0.224, "Text agreement is higher than executable correctness",
         fs=8.4, color=RED, weight="bold")
    # Frozen v12 aggregate rates, shown as separate evidence cards rather than
    # grouped bars to avoid implying that Exp B has L3/L4 or Exp A has L2b+.
    cards = [
        (0.355, "Exp A", "L3", "79%", "Method text", GREEN_BG, GREEN),
        (0.462, "Exp A", "L4", "81%", "Direction text", GREEN_BG, GREEN),
        (0.569, "Exp B", "L2b+", "51%", "Execution", BLUE_BG, BLUE),
    ]
    for x, exp, metric, value, desc, fc, ec in cards:
        rounded(ax, x, 0.118, 0.080, 0.078, fc=fc, ec=ec, lw=1.0, radius=0.008)
        text(ax, x + 0.040, 0.181, exp, fs=8.0, weight="bold", color=ec)
        text(ax, x + 0.040, 0.158, value, fs=13.0, weight="bold")
        text(ax, x + 0.040, 0.137, metric, fs=8.5, weight="bold")
        text(ax, x + 0.040, 0.119, desc, fs=7.6)
    text(ax, 0.500, 0.100, "Same seven models; different evidence layers",
         fs=7.9, color="#555555")

    rounded(ax, 0.750, 0.080, 0.210, 0.190, fc="#FDF8FF", ec=PURPLE, lw=1.0, radius=0.010)
    text(ax, 0.855, 0.245, "Outputs & Artifacts", fs=10.2, weight="bold", color=PURPLE)
    out_items = [
        ("Reports", 0.220),
        ("Result figures", 0.186),
        ("Error analysis", 0.152),
        ("Benchmarks & code", 0.118),
        ("Reproducibility package", 0.086),
    ]
    for label, yy in out_items:
        doc_icon(ax, 0.780, yy, 0.026)
        text(ax, 0.815, yy, label, fs=9.2, ha="left")

    arrow(ax, 0.260, 0.175, 0.335, 0.175, dashed=True)
    arrow(ax, 0.665, 0.175, 0.750, 0.175, dashed=True)

    out = Path("paper/figures/fig_system_flow_v12")
    fig.savefig(out.with_suffix(".pdf"), dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    print(f"  ✓ {out}.pdf")
    print(f"  ✓ {out}.png")
    print(f"  ✓ {out}.svg")


if __name__ == "__main__":
    main()
