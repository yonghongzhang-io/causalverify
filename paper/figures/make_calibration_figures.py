"""
Generate calibration diagnostic figure(s) from the calibration full experiment:

  1. calibration_reliability.pdf  — reliability diagrams (one subplot per model)

Optional auxiliary diagnostic (not referenced by the paper; disabled by
default in main()):

  2. correctness_vs_self_assessment.pdf — scatter of L2b+ pass rate vs.
     1−ECE of numerical confidence

Both rely on:
  - experiments/exp_b/calibration_scores.csv  (per-scenario confidence)
  - experiments/exp_b/calibration_summary.json (per-model aggregates)
  - experiments/exp_b/l2b_plus_summary.json   (per-model L2b+ rates)

Usage:
  python3 paper/figures/make_calibration_figures.py
"""

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent.parent
CAL_CSV = PROJECT_ROOT / "experiments/exp_b/calibration_scores.csv"
CAL_SUM = PROJECT_ROOT / "experiments/exp_b/calibration_summary_v2.json"
L2B_SUM = PROJECT_ROOT / "experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json"
OUT_DIR = PROJECT_ROOT / "paper/figures"

MODEL_ORDER = ["Opus", "Sonnet", "GPT-4o", "o3", "Kimi", "Gemini", "GPT-5"]
MODEL_COLORS = {
    "Opus":   "#1F4E79",
    "Sonnet": "#5B9BD5",
    "GPT-4o": "#ED7D31",
    "o3":     "#FFC000",
    "Kimi":   "#70AD47",
    "Gemini": "#A5A5A5",
    "GPT-5":  "#3D5A80",
}


def load_scores():
    with open(CAL_CSV) as f:
        rows = list(csv.DictReader(f))
    # Convert to native types
    for r in rows:
        for k in ("method_confidence", "specification_confidence",
                   "numerical_confidence"):
            r[k] = float(r[k])
        r["L2b_plus"] = int(r["L2b_plus"])
    return rows


def reliability_bins(conf, correct, n_bins=10):
    """Return (bin_mids, bin_confs, bin_accs, bin_weights)."""
    bin_confs, bin_accs, bin_weights = [], [], []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        mask = [(lo <= c < hi) or (hi == 1 and c == 1) for c in conf]
        n_in = sum(mask)
        if n_in == 0:
            bin_confs.append(None)
            bin_accs.append(None)
            bin_weights.append(0)
            continue
        bin_confs.append(sum(c for c, m in zip(conf, mask) if m) / n_in)
        bin_accs.append(sum(ac for ac, m in zip(correct, mask) if m) / n_in)
        bin_weights.append(n_in)
    return bin_confs, bin_accs, bin_weights


def fig1_reliability_diagrams(rows, summary):
    # Two-row grid sized to fit MODEL_ORDER (now 7 → 2x4)
    n_models = len(MODEL_ORDER)
    n_cols = 4 if n_models > 6 else 3
    n_rows = (n_models + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(3.25 * n_cols, 4.0 * n_rows),
                             sharex=True, sharey=True)
    axes = axes.flatten()

    for ax_idx, model in enumerate(MODEL_ORDER):
        ax = axes[ax_idx]
        model_rows = [r for r in rows if r["model_short"] == model]
        if not model_rows:
            ax.set_title(f"{model} (no data)")
            continue

        nc = [r["numerical_confidence"] for r in model_rows]
        correct = [r["L2b_plus"] for r in model_rows]
        bin_confs, bin_accs, bin_weights = reliability_bins(nc, correct)

        # Diagonal (perfect calibration)
        ax.plot([0, 1], [0, 1], "k:", lw=1, alpha=0.5, label="Perfect")

        # Bars (actual accuracy per bin) as connected line
        xs = [c for c in bin_confs if c is not None]
        ys = [a for a, c in zip(bin_accs, bin_confs) if c is not None]
        sizes = [max(w * 1.5, 10) for w, c in zip(bin_weights, bin_confs) if c is not None]
        ax.scatter(xs, ys, s=sizes, color=MODEL_COLORS[model], alpha=0.75,
                    edgecolors="white", linewidths=0.7, zorder=3)
        if xs and ys:
            ax.plot(xs, ys, color=MODEL_COLORS[model], lw=1.5, alpha=0.6)

        # Summary text
        s = summary.get(model, {})
        ece = s.get("ECE_numerical", float("nan"))
        l2b = s.get("L2b_plus_v2_pass_rate", s.get("L2b_plus_pass_rate", float("nan")))
        ax.text(0.05, 0.92, f"ECE = {ece:.3f}\nL2b+ = {l2b:.0%}",
                transform=ax.transAxes, fontsize=10, va="top", family="monospace",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.85))

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title(model, fontsize=12, fontweight="bold", color=MODEL_COLORS[model])
        ax.grid(True, alpha=0.2)
        if ax_idx % n_cols == 0:
            ax.set_ylabel("Empirical accuracy\n(L2b+ pass rate)")
        if ax_idx >= (n_rows - 1) * n_cols:
            ax.set_xlabel("Self-reported confidence")

    # Hide unused axes (e.g. the 8th tile when 7 models fit in 2x4)
    for k in range(n_models, len(axes)):
        axes[k].axis("off")

    fig.suptitle("Calibration of self-reported numerical confidence",
                  fontsize=14, fontweight="bold")
    fig.text(0.5, 0.01, "Dotted diagonal = perfect calibration. "
              "Bubble size ∝ samples in bin. "
              "Curves well below the diagonal indicate over-confidence.",
              ha="center", fontsize=9, style="italic", color="#555")
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    out_pdf = OUT_DIR / "calibration_reliability.pdf"
    plt.savefig(out_pdf, format="pdf", bbox_inches="tight", dpi=300)
    plt.savefig(str(out_pdf).replace(".pdf", ".png"), format="png",
                bbox_inches="tight", dpi=200)
    plt.close()
    print(f"Saved: {out_pdf}")


def fig2_correctness_vs_self_assessment(summary_cal, l2b_rates):
    """Auxiliary diagnostic: scatter of L2b+ pass rate (execution-grounded
    correctness) vs. 1 - ECE (self-assessment signal). Not referenced by the
    paper; disabled by default in main()."""
    fig, ax = plt.subplots(figsize=(8, 7))

    ax.plot([0, 1], [0, 1], "k:", lw=1, alpha=0.4,
            label="Diagonal (signals agree)")

    xs, ys = [], []
    for m in MODEL_ORDER:
        s = summary_cal.get(m)
        if not s:
            continue
        x = s.get("L2b_plus_v2_pass_rate", s.get("L2b_plus_pass_rate", float("nan")))
        y = 1.0 - s["ECE_numerical"]
        xs.append(x)
        ys.append(y)
        ax.scatter(x, y, s=300, color=MODEL_COLORS[m], alpha=0.85,
                    edgecolors="white", linewidths=1.5, zorder=3)
        ax.annotate(m, (x, y), xytext=(10, 6), textcoords="offset points",
                     fontsize=11, fontweight="bold", color=MODEL_COLORS[m])

    # Shading: region where self-assessment < execution-grounded correctness
    ax.fill_between([0, 1], [0, 1], 0, color="red", alpha=0.05,
                     zorder=1,
                     label="Self-assessment weaker than execution-grounded correctness")

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Execution-grounded correctness — L2b+ pass rate",
                   fontsize=11)
    ax.set_ylabel("Self-assessment signal — 1 − ECE of numerical confidence",
                   fontsize=11)
    ax.set_title("Execution-grounded correctness vs. self-assessment signal",
                  fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

    plt.tight_layout()
    out_pdf = OUT_DIR / "correctness_vs_self_assessment.pdf"
    plt.savefig(out_pdf, format="pdf", bbox_inches="tight", dpi=300)
    plt.savefig(str(out_pdf).replace(".pdf", ".png"), format="png",
                bbox_inches="tight", dpi=200)
    plt.close()
    print(f"Saved: {out_pdf}")


def main():
    if not CAL_CSV.exists():
        print(f"ERROR: {CAL_CSV} not found. Run run_calibration_full.py first.")
        return

    rows = load_scores()
    print(f"Loaded {len(rows)} calibration records")

    summary = json.load(open(CAL_SUM)) if CAL_SUM.exists() else {}

    l2b_rates = {}
    if L2B_SUM.exists():
        l2b_data = json.load(open(L2B_SUM)).get("by_model", {})
        l2b_rates = {
            m: d.get("L2b_plus_v2_rate", d.get("L2b_plus_rate"))
            for m, d in l2b_data.items()
        }

    fig1_reliability_diagrams(rows, summary)
    # fig2_correctness_vs_self_assessment is an auxiliary diagnostic not
    # referenced by the paper. Re-enable manually if needed.
    # fig2_correctness_vs_self_assessment(summary, l2b_rates)


if __name__ == "__main__":
    main()
