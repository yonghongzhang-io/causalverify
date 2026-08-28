"""Generate Figure 3: Exp A L3 method-family agreement.

Main-paper version only. The figure uses horizontal cross-model mean bars with
individual model points, matching the visual language of Figure 2.

Inputs are frozen result artifacts; this script makes no model/API calls and
does not modify scored data.
"""

from __future__ import annotations

import csv
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
FONT_LEGEND = 7

INK = "#1F2937"
AXIS = "#94A3B8"
GRID = "#E6E6E6"
MEAN_BAR_COLOR = "#D9D9D9"
MEAN_LABEL = "#374151"

MODELS_SLUG = [
    ("Claude-Opus", "Opus"),
    ("GPT-5", "GPT-5"),
    ("GPT-4o", "GPT-4o"),
    ("Claude-Sonnet", "Sonnet"),
    ("o3", "o3"),
    ("Gemini-2.5", "Gemini"),
    ("Kimi-128k", "Kimi"),
]
MODELS = ["Opus", "GPT-5", "GPT-4o", "Sonnet", "o3", "Gemini", "Kimi"]
MODEL_COLORS = {
    "Opus": "#D77A61",
    "GPT-5": "#3F5F86",
    "GPT-4o": "#5C8DB8",
    "Sonnet": "#8E6BBE",
    "o3": "#7F9AA8",
    "Gemini": "#69A88F",
    "Kimi": "#D9A441",
}
MODEL_MARKERS = {model: "o" for model in MODELS}

METHODS = ["Event Study", "IV", "DID", "RDD"]
METHOD_KEY = {
    "Event Study": "EVENT_STUDY",
    "IV": "IV",
    "DID": "DID",
    "RDD": "RDD",
}
DISPLAY_N = {
    "Event Study": 13,
    "IV": 32,
    "DID": 101,
    "RDD": 41,
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


def load_l3_by_method() -> dict[str, dict[str, int]]:
    with (ROOT / "experiments/exp_a/auto_scores.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))

    data = {method: {model: [] for _, model in MODELS_SLUG} for method in METHODS}
    key_to_method = {v: k for k, v in METHOD_KEY.items()}
    for row in rows:
        method = key_to_method.get(row.get("method", ""))
        if method is None:
            continue
        for slug, model in MODELS_SLUG:
            data[method][model].append(int(row.get(f"{slug}_L3a", 0)))

    return {
        method: {
            model: round(sum(values) / len(values) * 100)
            for model, values in model_values.items()
        }
        for method, model_values in data.items()
    }


def make_figure() -> plt.Figure:
    set_style()
    data = load_l3_by_method()
    y_pos = np.arange(len(METHODS))
    jitter = np.linspace(-0.14, 0.14, len(MODELS))
    mean_label_x = {
        "Event Study": 58.5,
        "IV": 78.0,
        "DID": 69.5,
        "RDD": 70.0,
    }

    fig, ax = plt.subplots(figsize=(7.05, 2.52))
    fig.subplots_adjust(left=0.17, right=0.985, top=0.92, bottom=0.36)

    for i, method in enumerate(METHODS):
        vals = data[method]
        row_vals = np.array([vals[model] for model in MODELS], dtype=float)
        mean_val = float(np.mean(row_vals))

        ax.barh(
            i,
            mean_val,
            height=0.48,
            color=MEAN_BAR_COLOR,
            edgecolor="none",
            alpha=0.62,
            zorder=2,
        )
        for val, model, dy in zip(row_vals, MODELS, jitter):
            ax.scatter(
                val,
                i + dy,
                marker=MODEL_MARKERS[model],
                s=31,
                facecolors=MODEL_COLORS[model],
                edgecolors="white",
                linewidths=0.55,
                alpha=0.95,
                zorder=4,
            )

        ax.text(
            mean_label_x[method],
            i,
            f"{mean_val:.0f}%",
            va="center",
            ha="right",
            fontweight="bold",
            color=MEAN_LABEL,
            fontsize=FONT_TEXT,
            zorder=5,
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels([f"{method}\n$n$={DISPLAY_N[method]}" for method in METHODS])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.55, len(METHODS) - 0.45)
    ax.invert_yaxis()
    ax.set_xlabel("L3 method-family agreement rate (%)", fontsize=FONT_AXIS, labelpad=5)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(axis="y", length=0, labelsize=FONT_TICK)
    ax.tick_params(axis="x", length=3, color=AXIS, labelsize=FONT_TICK)

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker=MODEL_MARKERS[model],
            color="white",
            markerfacecolor=MODEL_COLORS[model],
            markeredgecolor="white",
            markeredgewidth=0.55,
            markersize=5.2,
            label=model,
        )
        for model in MODELS
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.50, -0.31),
        ncol=7,
        frameon=False,
        fontsize=FONT_LEGEND,
        columnspacing=0.86,
        handletextpad=0.25,
        borderaxespad=0.0,
    )
    return fig


def main() -> None:
    fig = make_figure()
    output_specs = [
        (ROOT / "paper/figures", ("svg", "pdf", "png")),
        (ROOT / "paper/latex/figures", ("svg", "pdf", "png")),
    ]
    for out_dir, exts in output_specs:
        out_dir.mkdir(parents=True, exist_ok=True)
        for ext in exts:
            path = out_dir / f"fig3_method_dotplot.{ext}"
            fig.savefig(path)
            print(f"  ✓ {path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
