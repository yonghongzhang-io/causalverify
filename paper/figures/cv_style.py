"""Shared CausalVerify figure style.

This module is intentionally small and dependency-free beyond matplotlib.
It standardizes semantic colors, model order, axis treatment, and export
settings for reviewer-facing figures.
"""

from __future__ import annotations

import matplotlib.pyplot as plt


COLORS = {
    "ink": "#1F2937",
    "muted": "#6B7280",
    "grid": "#E5E7EB",
    "axis": "#94A3B8",
    "correct": "#59A14F",
    "exec": "#4E79A7",
    "wrong": "#F28E2B",
    "missing": "#BAB0AC",
    "gap": "#DADDE1",
    "text": "#B07AA1",
    "calibration": "#E15759",
    "light_blue": "#EEF5FB",
    "light_green": "#EEF7F0",
    "light_red": "#FBEFEF",
    "panel_edge": "#CBD5E1",
}

MODEL_ORDER = [
    "Opus",
    "GPT-5",
    "GPT-4o",
    "Sonnet",
    "o3",
    "Gemini",
    "Kimi",
]

MODEL_MARKERS = {
    "Opus": "o",
    "GPT-5": "*",
    "GPT-4o": "s",
    "Sonnet": "^",
    "o3": "D",
    "Gemini": "X",
    "Kimi": "P",
}

MODEL_COLORS = {
    "Opus": "#D77A61",
    "GPT-5": "#3F5F86",
    "GPT-4o": "#5C8DB8",
    "Sonnet": "#8E6BBE",
    "o3": "#7F9AA8",
    "Gemini": "#69A88F",
    "Kimi": "#D9A441",
}

OUTCOME_ORDER = [
    "L2b+ correct",
    "Executed, wrong coefficient",
    "Code present, execution fails",
    "No code / unparseable",
]

OUTCOME_COLORS = {
    "L2b+ correct": COLORS["correct"],
    "Executed, wrong coefficient": COLORS["wrong"],
    "Code present, execution fails": COLORS["exec"],
    "No code / unparseable": COLORS["missing"],
}


def set_cv_style() -> None:
    """Apply CausalVerify rcParams."""

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "axes.titlesize": 8.6,
        "axes.titleweight": "bold",
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 6.4,
        "axes.linewidth": 0.6,
        "axes.edgecolor": COLORS["muted"],
        "axes.labelcolor": COLORS["ink"],
        "xtick.color": COLORS["ink"],
        "ytick.color": COLORS["ink"],
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.36,
        "grid.alpha": 0.62,
        "lines.linewidth": 1.2,
        "lines.markersize": 4,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def clean_axis(ax, grid_axis: str | None = "x") -> None:
    """Use a low-clutter benchmark-paper axis."""

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["axis"])
    ax.spines["bottom"].set_color(COLORS["axis"])
    if grid_axis:
        ax.grid(True, axis=grid_axis, zorder=0)
    ax.set_axisbelow(True)


def percent_axis(ax, axis: str = "x") -> None:
    """Set a 0/25/50/75/100 percentage axis."""

    if axis == "x":
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100])
    else:
        ax.set_ylim(0, 100)
        ax.set_yticks([0, 25, 50, 75, 100])


def panel_label(ax, label: str) -> None:
    """Place a compact panel label at the top-left of an axis."""

    ax.text(
        -0.08,
        1.06,
        label,
        transform=ax.transAxes,
        fontsize=8.0,
        fontweight="bold",
        va="bottom",
        ha="left",
        color=COLORS["ink"],
    )
