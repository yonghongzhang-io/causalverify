"""Regenerate replication_heatmap.png — 7 models × 259 papers (post-Stage 8.4)."""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

METHOD_COLORS = {
    "DID":         "#1D9E75",
    "EVENT_STUDY": "#378ADD",
    "IV":          "#7F77DD",
    "RDD":         "#D85A30",
}

MODELS = [
    ("Kimi-128k",     "Kimi-128k"),
    ("Claude-Sonnet", "Claude-S"),
    ("GPT-4o",        "GPT-4o"),
    ("o3",            "o3"),
    ("Claude-Opus",   "Opus"),
    ("Gemini-2.5",    "Gemini"),
    ("GPT-5",         "GPT-5"),
]

with open("experiments/exp_a/auto_scores.csv") as f:
    all_rows = list(csv.DictReader(f))

# Include all papers with at least one valid output (non-empty detected field).
# Sort numerically (paper_01, paper_02, ..., paper_137).
def _pnum(r):
    try:
        return int(r["paper_id"].replace("paper_", ""))
    except ValueError:
        return 999999

models_short = ["Kimi-128k", "Claude-Sonnet", "GPT-4o", "o3", "Claude-Opus", "Gemini-2.5", "GPT-5"]
rows = [r for r in all_rows
        if any(r.get(f"{m}_detected", "") for m in models_short)]
rows.sort(key=_pnum)

papers  = [r["paper_id"] for r in rows]
methods = [r["method"]   for r in rows]
diffs   = [r["difficulty"] for r in rows]
n       = len(rows)

y_labels = [
    f"P{r['paper_id'].replace('paper_','')}: "
    f"{r['method'].replace('_',' ')} ({r['difficulty']})"
    for r in rows
]

# Build data matrix: rows=papers, cols=models × [L3a, L3b]
n_models = len(MODELS)
data = np.zeros((n, n_models * 2), dtype=float)
for i, r in enumerate(rows):
    for j, (col_prefix, _) in enumerate(MODELS):
        l3a_key = f"{col_prefix}_L3a"
        l3b_key = f"{col_prefix}_L3b"
        data[i, j*2]     = float(r.get(l3a_key, 0))
        data[i, j*2 + 1] = float(r.get(l3b_key, 0))

# ── Layout ────────────────────────────────────────────────
fig_w = 3.0 * n_models + 2
fig_h = max(n * 0.35, 10)
fig = plt.figure(figsize=(fig_w, fig_h))
gs = fig.add_gridspec(1, 2, width_ratios=[1, 0.015],
                      left=0.22, right=0.96, wspace=0.02)
ax = fig.add_subplot(gs[0])
ax_cbar = fig.add_subplot(gs[1])

# ── Heatmap ───────────────────────────────────────────────
cmap = plt.cm.RdYlGn
im = ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")

# X-axis: Strategy/Direction repeated per model
x_labels = ["Str", "Dir"] * n_models
ax.set_xticks(range(n_models * 2))
ax.set_xticklabels(x_labels, fontsize=7)
ax.xaxis.set_label_position("top")
ax.xaxis.tick_top()

# Y-axis
ax.set_yticks(range(n))
ax.set_yticklabels(y_labels, fontsize=6.5)
ax.tick_params(axis="y", length=0, pad=4)

# Color y-ticks by method
for tick, m in zip(ax.get_yticklabels(), methods):
    tick.set_color(METHOD_COLORS.get(m, "#333"))

# Model group headers
for j, (col_prefix, short_name) in enumerate(MODELS):
    x_center = (j * 2 + 0.5) / (n_models * 2)
    ax.text(x_center, 1.04, short_name, ha="center", va="bottom",
            fontsize=8.5, fontweight="bold", transform=ax.transAxes)

# White dividers between models
for j in range(1, n_models):
    ax.axvline(j * 2 - 0.5, color="white", linewidth=2, zorder=5)

# ✓/✗ cell text
for i in range(n):
    for j in range(n_models * 2):
        val = data[i, j]
        txt = "✓" if val == 1 else "✗"
        c = "white" if val == 1 else "#800"
        ax.text(j, i, txt, ha="center", va="center",
                fontsize=7, color=c, fontweight="bold")

# ── Colorbar ──────────────────────────────────────────────
plt.colorbar(im, cax=ax_cbar, label="Pass / Fail")
ax_cbar.tick_params(labelsize=6)

# ── Legend ─────────────────────────────────────────────────
legend_patches = [mpatches.Patch(color=c, label=m.replace("_", " "))
                  for m, c in METHOD_COLORS.items()]
ax.legend(handles=legend_patches, loc="lower right", fontsize=6.5,
          title="Method", title_fontsize=6.5,
          framealpha=0.9, edgecolor="#ccc")

fig.suptitle(
    "Experiment A  ·  Replication Heatmap\n"
    f"{n} papers  ×  {n_models} models  ×  L3a Strategy + L3b Direction",
    fontsize=11, fontweight="bold", y=1.02
)

out = Path("paper/figures/replication_heatmap.png")
plt.savefig(out, dpi=200, bbox_inches="tight")
plt.close()
print(f"Saved → {out}")
