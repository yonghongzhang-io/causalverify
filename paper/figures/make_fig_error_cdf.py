"""
Generate Figure 5: small-multiple L2b+ relative-error profiles.

Instead of reducing L2b+ to the binary ±50% threshold, show the sorted
distribution of relative errors per model. The small-multiple layout makes
the threshold-robustness claim easier to inspect: strong models should have
most of their mass near zero, not merely a few points just below 0.5.
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from palette import PAL, MODEL_COLORS, MODEL_MARKERS, MODEL_ORDER, RC_PARAMS

plt.rcParams.update(RC_PARAMS)

MODELS = MODEL_ORDER
COLORS = MODEL_COLORS
SUMMARY = Path("experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json")

# Load per-scenario errors from canonical_judge_v2 (7-model frozen).
# Use rel_error_v2 (judge-extracted, ES-window-aware), not the legacy
# regex-based rel_error. Clean rows where the judge could not extract.
rows = []
with open("experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv") as f:
    for r in csv.DictReader(f):
        rel = r.get("rel_error_v2") or r.get("rel_error_judge") or r.get("rel_error")
        if rel in ("", "None", None):
            continue
        try:
            rows.append({
                "sid": r["scenario_id"],
                "model": r["model"],
                "rel_error": float(rel),
                "L2b": int(r["L2b"]),
            })
        except (ValueError, TypeError):
            continue

print(f"Loaded {len(rows)} rows with relative error")

# Organize by model
errors_by_model = {m: [] for m in MODELS}
for r in rows:
    if r["model"] in errors_by_model:
        errors_by_model[r["model"]].append(r["rel_error"])

summary = json.loads(SUMMARY.read_text())
rates = {
    model: vals.get("L2b_plus_v2_rate", np.nan)
    for model, vals in summary.get("by_model", {}).items()
}

# Figure: 7 model panels + one legend/annotation panel.
fig, axes = plt.subplots(2, 4, figsize=(13.2, 6.6), sharey=True)
axes = axes.ravel()
fig.subplots_adjust(left=0.075, right=0.985, top=0.88, bottom=0.13,
                    wspace=0.22, hspace=0.42)

for i, model in enumerate(MODELS):
    ax = axes[i]
    errs = sorted(errors_by_model.get(model, []))
    if not errs:
        ax.set_axis_off()
        continue

    x = np.arange(1, len(errs) + 1)
    y = np.array([min(e, 2.5) for e in errs])
    clipped = sum(e > 2.5 for e in errs)
    p50_valid = sum(e <= 0.5 for e in errs) / len(errs)
    rate = rates.get(model, p50_valid)

    ax.scatter(x, y, s=22, color=COLORS[model], alpha=0.72,
               marker=MODEL_MARKERS[model], edgecolor="white",
               linewidth=0.35, zorder=3)
    ax.plot(x, y, color=COLORS[model], linewidth=1.5, alpha=0.9, zorder=2)
    ax.axhline(0.5, color="#555555", linestyle="--", linewidth=1.0, zorder=1)
    ax.axhline(1.0, color="#999999", linestyle=":", linewidth=0.8, zorder=1)
    ax.set_xlim(0, max(42, len(errs) + 3))
    ax.set_ylim(-0.05, 2.55)
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.7)
    ax.grid(axis="x", color="#f0f0f0", linewidth=0.5)
    ax.set_title(f"{model}: {rate*100:.0f}% L2b+", fontsize=11,
                 fontweight="bold", color=COLORS[model], pad=5)
    ax.text(0.03, 0.88, f"valid n={len(errs)}", transform=ax.transAxes,
            fontsize=8.5, color="#555555")
    if clipped:
        ax.text(0.03, 0.76, f"{clipped} clipped", transform=ax.transAxes,
                fontsize=8.5, color="#555555")

    if i % 4 != 0:
        ax.set_ylabel("")
    if i < 4:
        ax.set_xlabel("")

# Legend / reading guide in the empty eighth panel.
guide = axes[-1]
guide.axis("off")
guide.set_title("Reading guide", fontsize=11, fontweight="bold", pad=5)
guide.plot([0.08, 0.42], [0.78, 0.78], transform=guide.transAxes,
           color="#555555", linestyle="--", linewidth=1.2)
guide.text(0.48, 0.76, "50% L2b+ tolerance", transform=guide.transAxes,
           fontsize=9.5, va="center")
guide.plot([0.08, 0.42], [0.62, 0.62], transform=guide.transAxes,
           color="#999999", linestyle=":", linewidth=1.0)
guide.text(0.48, 0.60, "100% reference", transform=guide.transAxes,
           fontsize=9.5, va="center")
guide.scatter([0.12], [0.44], transform=guide.transAxes, s=40,
              color="#555555", edgecolor="white", linewidth=0.5)
guide.plot([0.08, 0.42], [0.44, 0.44], transform=guide.transAxes,
           color="#555555", linewidth=1.3)
guide.text(0.48, 0.42, "scenarios sorted within model", transform=guide.transAxes,
           fontsize=9.5, va="center")
guide.text(0.08, 0.20,
           "Lower, flatter profiles mean\nsmaller numerical errors across\nmore executed scenarios.",
           transform=guide.transAxes, fontsize=9.5, va="top",
           color="#333333")

fig.suptitle("L2b+ relative-error profiles by model", fontsize=14,
             fontweight="bold", y=0.965)
fig.supxlabel("Scenario rank within model (sorted by relative error)", y=0.045)
fig.supylabel("Relative error against canonical estimator (clipped at 2.5)",
              x=0.018)

out = Path("paper/figures/fig_error_cdf.pdf")
plt.savefig(out, dpi=180, bbox_inches="tight")
png = out.with_suffix(".png")
plt.savefig(png, dpi=180, bbox_inches="tight")
print(f"  ✓ {out}")
print(f"  ✓ {png}")
plt.close()
