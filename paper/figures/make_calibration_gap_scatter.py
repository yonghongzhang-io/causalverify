#!/usr/bin/env python3
"""Plot Exp B correctness vs self-assessment from frozen summaries.

This figure is intentionally different from the reliability-curve figure:

  x-axis: L2b+ v2 pass rate (execution-grounded correctness)
  y-axis: confidence gap = mean confidence(correct) - mean confidence(wrong)

The plot asks whether models that compute the target estimate more often also
know when their own workflow is wrong. It uses only frozen JSON summaries and
does not make API calls or modify result artifacts.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[2]
CAL_SUM = ROOT / "experiments/exp_b/calibration_summary_v2.json"
L2B_SUM = ROOT / "experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json"
OUT_DIR = ROOT / "paper/figures"
TABLE_PATH = ROOT / "paper/tables/exp_b_calibration_gap_scatter.csv"

MODEL_ORDER = ["Kimi", "Gemini", "o3", "Sonnet", "GPT-4o", "GPT-5", "Opus"]
MODEL_COLORS = {
    "Kimi": "#9A7B4F",
    "Gemini": "#8FA6B3",
    "o3": "#B07AA1",
    "Sonnet": "#59A14F",
    "GPT-4o": "#F28E2B",
    "GPT-5": "#4E79A7",
    "Opus": "#1F4E79",
}


def load_rows() -> list[dict[str, object]]:
    cal = json.loads(CAL_SUM.read_text())
    l2b = json.loads(L2B_SUM.read_text())["by_model"]

    rows = []
    for model in MODEL_ORDER:
        c = cal[model]
        b = l2b[model]
        rows.append(
            {
                "model": model,
                "n_calibration": int(c["n"]),
                "l2bplus_v2_rate": float(b["L2b_plus_v2_rate"]),
                "l2bplus_v2_count": int(b["L2b_plus_v2"]),
                "confidence_gap": float(c["confidence_gap_right_minus_wrong"]),
                "mean_conf_right": float(c["mean_numerical_conf_right"]),
                "mean_conf_wrong": float(c["mean_numerical_conf_wrong"]),
                "ece_numerical": float(c["ECE_numerical"]),
            }
        )
    return rows


def write_table(rows: list[dict[str, object]]) -> None:
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model",
        "n_calibration",
        "l2bplus_v2_count",
        "l2bplus_v2_rate",
        "confidence_gap",
        "mean_conf_right",
        "mean_conf_wrong",
        "ece_numerical",
    ]
    with TABLE_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fields})


def plot(rows: list[dict[str, object]]) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.5,
            "axes.titlesize": 8.8,
            "axes.labelsize": 8.2,
            "xtick.labelsize": 7.6,
            "ytick.labelsize": 7.6,
            "legend.fontsize": 7.4,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    fig, ax = plt.subplots(figsize=(5.35, 3.2))

    # Regions: a useful self-assessment signal should be comfortably above 0.
    ax.axhline(0, color="#4B5563", linestyle=(0, (5, 3)), linewidth=0.9)
    ax.text(
        0.975,
        0.006,
        "no confidence signal",
        transform=ax.get_yaxis_transform(),
        ha="right",
        va="bottom",
        color="#4B5563",
        fontsize=6.8,
    )
    ax.axhspan(-0.075, 0.075, color="#F2F4F7", zorder=0)
    ax.text(
        0.025,
        0.065,
        "weak separation band",
        transform=ax.get_yaxis_transform(),
        ha="left",
        va="top",
        color="#6B7280",
        fontsize=6.7,
    )

    # Plot points. Gemini has partial calibration coverage, so use lower alpha.
    offsets = {
        "Kimi": (5, -10),
        "Gemini": (5, 3),
        "o3": (-18, -12),
        "Sonnet": (-36, 7),
        "GPT-4o": (5, 4),
        "GPT-5": (5, -12),
        "Opus": (5, 4),
    }
    for row in rows:
        model = str(row["model"])
        x = float(row["l2bplus_v2_rate"])
        y = float(row["confidence_gap"])
        n = int(row["n_calibration"])
        partial = n < 100
        ax.scatter(
            x,
            y,
            s=78 if not partial else 70,
            color=MODEL_COLORS[model],
            edgecolor="white",
            linewidth=0.85,
            alpha=0.95 if not partial else 0.62,
            zorder=3,
        )
        dx, dy = offsets[model]
        label = model if not partial else f"{model} (n={n})"
        ax.annotate(
            label,
            (x, y),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=7.1,
            fontweight="bold",
            color=MODEL_COLORS[model],
        )

    # Main interpretive annotation, placed away from labels.
    ax.annotate(
        "high correctness,\nsmall confidence gap",
        xy=(0.80, 0.03),
        xytext=(0.55, 0.18),
        arrowprops=dict(arrowstyle="->", color="#7A1F1F", lw=0.9),
        color="#7A1F1F",
        fontsize=7.0,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#E6B8B7", alpha=0.92),
    )

    ax.set_xlim(0.0, 0.94)
    ax.set_ylim(-0.075, 0.255)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.set_xlabel("Execution-grounded correctness: L2b+ pass rate")
    ax.set_ylabel("Confidence gap: correct - wrong")
    ax.set_title("Correctness vs. Self-Assessment", pad=5)
    ax.grid(axis="both", color="#E5E7EB", linewidth=0.65)

    note = "One point per model. Labels report n when calibration coverage is incomplete."
    fig.text(0.5, 0.012, note, ha="center", va="bottom", fontsize=6.5, color="#555555")
    fig.tight_layout(rect=[0, 0.06, 1, 1])

    for ext in ("png", "pdf"):
        out = OUT_DIR / f"calibration_gap_scatter.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight")
        print(f"Wrote {out.relative_to(ROOT)}")
    plt.close(fig)


def main() -> None:
    rows = load_rows()
    write_table(rows)
    print(f"Wrote {TABLE_PATH.relative_to(ROOT)}")
    for row in rows:
        print(
            f"{row['model']:<7} "
            f"L2b+={100 * float(row['l2bplus_v2_rate']):5.1f}% "
            f"gap={100 * float(row['confidence_gap']):+5.1f}pp "
            f"n={row['n_calibration']}"
        )
    plot(rows)


if __name__ == "__main__":
    main()
