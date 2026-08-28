"""
Figure 4: The execution-grounded cascade (Exp B, N=100).

The final paper version uses a single horizontal decomposition instead of
two small panels. Each model's 100 Exp B scenarios are partitioned into:
  - coefficient-correct executed workflows (L2b+)
  - executed workflows with the wrong coefficient
  - code-present execution failures
  - missing/unparseable code

This keeps the figure readable at NeurIPS column/page scale while preserving
the same frozen metrics.
"""

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
FONT_LEGEND = 7
FONT_PERCENT = 9

INK = "#1F2937"
AXIS = "#94A3B8"
GRID = "#E5E7EB"

SEGMENT_COLORS = {
    "L2b+ correct": "#5FAE8B",
    "Executed, wrong coefficient": "#E08A61",
    "Code present, execution fails": "#8FA8C6",
    "No code / unparseable": "#D8D5CC",
}


def set_style() -> None:
    """Match the Figure 3 typography/export settings exactly."""

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


set_style()

# Load Exp B layer rates from V11 frozen sources (7 models).
# L2a / L2b: l2b_plus_summary_canonical.json (raw layered scores).
# L2b+: l2b_plus_summary_canonical_judge_v2.json (judge + ES-aware).
canonical = json.loads(
    (ROOT / "experiments/exp_b/l2b_plus_summary_canonical.json").read_text())
v2 = json.loads(
    (ROOT / "experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json").read_text())
bm_c = canonical["by_model"]
bm_v2 = v2["by_model"]
by_model = {
    m: {
        "L2a_rate":     bm_c[m]["L2a_rate"],
        "L2b_rate":     bm_c[m]["L2b_rate"],
        "L2b_plus_rate": bm_v2[m]["L2b_plus_v2_rate"],
    }
    for m in bm_c if m in bm_v2
}

# Primary seven-model panel only. Llama is robustness-only and is not included
# in the paper's primary leaderboard/cascade figure.
PRIMARY_MODELS = ["Opus", "GPT-5", "GPT-4o", "Sonnet", "o3", "Gemini", "Kimi"]
MODELS = [m for m in PRIMARY_MODELS if m in by_model]

layer_rate = lambda m, k: by_model[m][k] * 100

# ────────────────────── Single-panel cascade decomposition ───────────
correct = np.array([layer_rate(m, "L2b_plus_rate") for m in MODELS])
executed_wrong = np.array([
    max(0, layer_rate(m, "L2b_rate") - layer_rate(m, "L2b_plus_rate"))
    for m in MODELS
])
execution_fail = np.array([
    max(0, layer_rate(m, "L2a_rate") - layer_rate(m, "L2b_rate"))
    for m in MODELS
])
no_code = np.array([max(0, 100 - layer_rate(m, "L2a_rate")) for m in MODELS])

segments = [
    ("L2b+ correct", correct, SEGMENT_COLORS["L2b+ correct"]),
    ("Executed, wrong coefficient", executed_wrong, SEGMENT_COLORS["Executed, wrong coefficient"]),
    ("Code present, execution fails", execution_fail, SEGMENT_COLORS["Code present, execution fails"]),
    ("No code / unparseable", no_code, SEGMENT_COLORS["No code / unparseable"]),
]

fig, ax = plt.subplots(figsize=(6.70, 2.52))
fig.subplots_adjust(left=0.17, right=0.985, top=0.92, bottom=0.36)

y_pos = np.arange(len(MODELS))
left = np.zeros(len(MODELS))
bar_h = 0.52

for label, vals, color in segments:
    ax.barh(
        y_pos, vals, left=left, height=bar_h,
        color=color, edgecolor="white", linewidth=0.75,
        label=label, zorder=3)
    left += vals

# Label the final correctness rate directly on the L2b+ segment.
for y, m, rate in zip(y_pos, MODELS, correct):
    if rate >= 15:
        ax.text(rate / 2, y, f"{rate:.0f}%", ha="center", va="center",
                color="white", fontweight="bold", fontsize=FONT_PERCENT)
    else:
        ax.text(rate + 1.3, y, f"{rate:.0f}%", ha="left", va="center",
                color=INK, fontweight="bold", fontsize=FONT_PERCENT)

ax.set_xlim(0, 100)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xticklabels(["0", "25", "50", "75", "100"])
ax.set_xlabel("Share of 100 Exp B scenarios (%)", labelpad=5)
ax.set_yticks(y_pos)
ax.set_yticklabels(MODELS)
ax.invert_yaxis()
ax.grid(axis="x", color=GRID, linestyle="-", linewidth=0.6, zorder=0)
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0)
ax.tick_params(axis="x", length=3, color=AXIS)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_color(AXIS)
ax.spines["left"].set_color(AXIS)
ax.set_axisbelow(True)

legend_handles = [
    Line2D([0], [0],
           marker="s", color="w",
           markerfacecolor=color,
           markeredgecolor="white",
           markeredgewidth=0.55,
           markersize=5.2,
           label=label)
    for label, _, color in segments
]
leg = ax.legend(
    handles=legend_handles,
    loc="upper center",
    bbox_to_anchor=(0.50, -0.31),
    ncol=4,
    frameon=False,
    fontsize=FONT_LEGEND,
    columnspacing=0.86,
    handletextpad=0.25,
    borderaxespad=0.0,
    handlelength=1.0,
    handleheight=0.7,
    labelspacing=0.5)
leg._legend_box.align = "left"

for out_dir in [ROOT / "paper/figures", ROOT / "paper/latex/figures"]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "pdf", "png"):
        out = out_dir / f"fig4_cascade.{ext}"
        plt.savefig(out, dpi=600, bbox_inches="tight")
        print(f"  ✓ {out}")
plt.close()

# Numeric summary
print("\nNumeric summary:")
for m in MODELS:
    l2a = layer_rate(m, "L2a_rate")
    l2b = layer_rate(m, "L2b_rate")
    l2bp = layer_rate(m, "L2b_plus_rate")
    print(f"  {m:<8}: L2a={l2a:>5.1f}% L2b={l2b:>5.1f}% L2b+={l2bp:>5.1f}% "
          f"| exec_gap={l2a-l2b:>5.1f}pp corr_gap={l2b-l2bp:>5.1f}pp")
