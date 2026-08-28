"""Generate Figure 2: headline CausalVerify result.

The figure separates three claims:
(a) L2b execution and L2b+ coefficient correctness are distinct.
(b) L2b ranking tracks L2b+ ranking better than L4 text scoring.
(c) Exp A L3/L4 are text-agreement diagnostics for the same seven models.

All inputs are frozen result artifacts; this script makes no model calls and
does not change scored data.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[2]

FONT_TITLE = 11
FONT_AXIS = 10
FONT_TICK = 9
FONT_TEXT = 9
FONT_LEGEND = 9
FONT_PERCENT = 9

INK = "#1F2937"
MUTED = "#6B7280"
AXIS = "#94A3B8"
GRID = "#E5E7EB"
GUIDE = "#DDE3EA"
GREEN = "#59A14F"
BLUE = "#4E79A7"
GAP = "#DADDE1"
L4_PURPLE = "#B07AA1"

MODEL_ORDER = ["Opus", "GPT-5", "GPT-4o", "Sonnet", "o3", "Gemini", "Kimi"]
MODEL_COLORS = {
    "Opus": "#D77A61",
    "GPT-5": "#3F5F86",
    "GPT-4o": "#5C8DB8",
    "Sonnet": "#8E6BBE",
    "o3": "#7F9AA8",
    "Gemini": "#69A88F",
    "Kimi": "#D9A441",
}


def set_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "mathtext.fontset": "dejavusans",
            "font.size": FONT_TEXT,
            "axes.titlesize": FONT_TITLE,
            "axes.titleweight": "bold",
            "axes.labelsize": FONT_AXIS,
            "xtick.labelsize": FONT_TICK,
            "ytick.labelsize": FONT_TICK,
            "legend.fontsize": FONT_LEGEND,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.65,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.labelcolor": INK,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
        }
    )


def load_json(path: str):
    return json.loads((ROOT / path).read_text())


def load_exp_a_table() -> dict[str, dict[str, float]]:
    path = ROOT / "paper/tables/exp_a_l3_l4_by_model.csv"
    name_map = {
        "Claude-Opus": "Opus",
        "Claude-Sonnet": "Sonnet",
        "Kimi-128k": "Kimi",
        "Gemini-2.5": "Gemini",
    }
    rows: dict[str, dict[str, float]] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            model = name_map.get(row["model"], row["model"])
            rows[model] = {
                "L3": float(row["L3_pct"]),
                "L4": float(row["L4_pct"]),
            }
    return rows


def clean_axis(ax, grid_axis: str | None = "x") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(axis="both", labelsize=FONT_TICK, colors=INK)
    if grid_axis:
        ax.grid(True, axis=grid_axis, color=GRID, linewidth=0.55, alpha=0.72, zorder=0)
    ax.set_axisbelow(True)


def panel_execution_gap(ax, canonical, v2) -> None:
    models = [m for m in MODEL_ORDER if m in canonical["by_model"] and m in v2["by_model"]]
    y = np.arange(len(models))
    l2b = np.array([canonical["by_model"][m]["L2b_rate"] * 100 for m in models])
    l2bp = np.array([v2["by_model"][m]["L2b_plus_v2_rate"] * 100 for m in models])

    ax.barh(y, l2bp, height=0.42, color=GREEN, edgecolor="none", zorder=2)
    for yi, model, executed, correct in zip(y, models, l2b, l2bp):
        ax.plot(
            [correct, executed],
            [yi, yi],
            color=GAP,
            linewidth=2.2,
            solid_capstyle="round",
            zorder=1,
        )
        ax.scatter(
            executed,
            yi,
            marker="o",
            s=32,
            color=BLUE,
            edgecolor="white",
            linewidth=0.50,
            zorder=4,
        )
        if correct >= 20:
            ax.text(
                correct - 1.5,
                yi,
                f"{correct:.0f}%",
                ha="right",
                va="center",
                fontsize=FONT_PERCENT,
                color="white",
                fontweight="bold",
            )
        else:
            ax.text(
                correct + 1.7,
                yi,
                f"{correct:.0f}%",
                ha="left",
                va="center",
                fontsize=FONT_PERCENT,
                color=INK,
                fontweight="bold",
            )
        gap = executed - correct
        if model == "Kimi":
            ax.text(
                executed + 1.8,
                yi,
                f"{gap:.0f}pp",
                ha="left",
                va="center",
                fontsize=FONT_TEXT,
                color=MUTED,
            )

    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=FONT_TEXT)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("")
    ax.set_title("(a) Execution vs. coefficient correctness", loc="left", pad=3)
    clean_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    handles = [
        Line2D([0], [0], color=GREEN, lw=4.2, solid_capstyle="butt", label="L2b+ correct"),
        Line2D(
            [0],
            [0],
            marker="o",
            color="white",
            markerfacecolor=BLUE,
            markeredgecolor="white",
            markersize=5.2,
            label="L2b executes",
        ),
        Line2D([0], [0], color=GAP, lw=4.2, solid_capstyle="butt", label="gap"),
    ]
    ax.legend(
        handles=handles,
        frameon=False,
        ncol=1,
        loc="lower right",
        bbox_to_anchor=(1.04, 0.02),
        handlelength=1.15,
        columnspacing=0.70,
        borderaxespad=0.2,
        fontsize=FONT_LEGEND,
    )


def panel_rank_agreement(ax, head_to_head) -> None:
    corr = head_to_head["correlations_with_GT"]
    tau_l2b = corr["L2b (code executes)"]["kendall_tau"]
    l4_vals = [
        corr["L4 section-aware (S2)"]["kendall_tau"],
        corr["L4 latter-half (S1)"]["kendall_tau"],
    ]
    l4_lo, l4_hi = min(l4_vals), max(l4_vals)

    ax.axvline(0, color=AXIS, linewidth=0.75, zorder=1)
    ax.hlines(1, 0, tau_l2b, color=BLUE, linewidth=3.5, zorder=2, capstyle="round")
    ax.scatter([tau_l2b], [1], color=BLUE, s=30, edgecolor="white", linewidth=0.55, zorder=3)
    ax.text(
        tau_l2b + 0.045,
        1,
        f"{tau_l2b:+.2f}",
        ha="left",
        va="center",
        fontsize=FONT_TEXT,
        color=BLUE,
        fontweight="bold",
    )

    ax.hlines(0, l4_lo, l4_hi, color=L4_PURPLE, linewidth=2.5, zorder=2, capstyle="round")
    ax.scatter(l4_vals, [0, 0], color=L4_PURPLE, s=28, edgecolor="white", linewidth=0.55, zorder=3)
    ax.text(
        (l4_lo + l4_hi) / 2,
        -0.235,
        f"{l4_lo:+.2f} to {l4_hi:+.2f}",
        ha="center",
        va="center",
        fontsize=FONT_TEXT,
        color=L4_PURPLE,
    )

    ax.set_yticks([1, 0])
    ax.set_yticklabels(["", ""])
    ax.set_xlim(-1.00, 1.00)
    ax.set_xticks([-1.0, -0.5, 0, 0.5, 1.0])
    ax.set_xlabel("")
    ax.set_ylim(-0.62, 1.48)
    ax.set_title("(b) Rank agreement with L2b+", loc="left", pad=3)
    clean_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.text(
        -0.95,
        1,
        "L2b\nexecution",
        ha="left",
        va="center",
        fontsize=FONT_TEXT,
        color=INK,
        linespacing=0.92,
    )
    ax.text(
        -0.95,
        0,
        "L4\ntext direction",
        ha="left",
        va="center",
        fontsize=FONT_TEXT,
        color=INK,
        linespacing=0.92,
    )


def panel_exp_a_text_agreement(ax, exp_a) -> None:
    label_offsets = {
        "Sonnet": (-8, 10),
        "Opus": (7, 3),
        "Kimi": (7, 8),
        "GPT-4o": (-10, -8),
        "Gemini": (7, -8),
        "o3": (7, -10),
        "GPT-5": (7, -8),
    }
    label_align = {
        "Sonnet": ("right", "bottom"),
        "Opus": ("left", "center"),
        "Kimi": ("left", "bottom"),
        "GPT-4o": ("right", "top"),
        "Gemini": ("left", "top"),
        "o3": ("left", "top"),
        "GPT-5": ("left", "top"),
    }

    for model in [m for m in MODEL_ORDER if m in exp_a]:
        x = exp_a[model]["L3"]
        y = exp_a[model]["L4"]
        ax.scatter(
            x,
            y,
            s=50,
            color=MODEL_COLORS[model],
            edgecolor="white",
            linewidth=0.60,
            alpha=0.95,
            zorder=3,
        )
        dx, dy = label_offsets[model]
        ha, va = label_align[model]
        ax.annotate(
            model,
            xy=(x, y),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va=va,
            fontsize=FONT_TEXT,
            color=INK,
            zorder=4,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=0.35),
        )

    ax.axvline(75, color=GUIDE, linewidth=0.80, alpha=0.80, zorder=0)
    ax.axhline(75, color=GUIDE, linewidth=0.80, alpha=0.80, zorder=0)
    ax.set_xlim(60, 91)
    ax.set_ylim(72, 88.8)
    ax.set_xticks([60, 70, 80, 90])
    ax.set_yticks([72, 76, 80, 84, 88])
    ax.set_xlabel("")
    ax.set_ylabel("Exp A L4 direction agreement (%)", fontsize=FONT_AXIS)
    ax.set_title("(c) Exp A text agreement", loc="left", pad=3)
    clean_axis(ax, None)
    ax.grid(True, axis="both", color=GRID, linewidth=0.55, alpha=0.72, zorder=0)


def add_aligned_xlabels(fig, axes, labels) -> None:
    y = 0.105
    for ax, label in zip(axes, labels):
        pos = ax.get_position()
        x = (pos.x0 + pos.x1) / 2
        fig.text(x, y, label, ha="center", va="center", fontsize=FONT_AXIS, color=INK)


def main() -> None:
    set_style()
    canonical = load_json("experiments/exp_b/l2b_plus_summary_canonical.json")
    v2 = load_json("experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json")
    head_to_head = load_json("experiments/exp_b/head_to_head_ranking.json")
    exp_a = load_exp_a_table()

    fig = plt.figure(figsize=(10.0, 3.10), facecolor="white")
    gs = fig.add_gridspec(
        1,
        3,
        width_ratios=[1.15, 1.00, 1.10],
        left=0.060,
        right=0.992,
        top=0.835,
        bottom=0.230,
        wspace=0.34,
    )
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 2])

    panel_execution_gap(ax_a, canonical, v2)
    panel_rank_agreement(ax_b, head_to_head)
    panel_exp_a_text_agreement(ax_c, exp_a)
    add_aligned_xlabels(
        fig,
        [ax_a, ax_b, ax_c],
        [
            "Share of Exp B scenarios (%)",
            "Kendall \u03c4 vs. L2b+ rank",
            "Exp A L3 method agreement (%)",
        ],
    )

    output_specs = [
        (ROOT / "paper/figures", ("svg", "pdf", "png")),
        (ROOT / "paper/latex/figures", ("svg", "pdf", "png")),
    ]
    for out_dir, exts in output_specs:
        out_dir.mkdir(parents=True, exist_ok=True)
        for ext in exts:
            out_path = out_dir / f"fig2_l2b_plus_cascade.{ext}"
            fig.savefig(out_path)
            print(f"  ✓ {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
