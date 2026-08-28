"""
Replace Table 14 (RID ablation pilot) with a dot-plot visualization.

Shows each model's L3 (Strategy) and L4 (Direction) rates under RID-OFF vs.
RID-ON, with arrows indicating the direction of change. Pilot N=10,
so differences are descriptive only.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

sys.path.insert(0, str(Path(__file__).parent))
from palette import PAL, MODEL_MARKERS, MODEL_ORDER, RC_PARAMS

plt.rcParams.update(RC_PARAMS)

# RID pilot data (from Table 14 in v8/v9)
rid_data = {
    "Kimi":   {"s_off": 70, "s_on": 60, "d_off": 80, "d_on": 50},
    "Sonnet": {"s_off": 80, "s_on": 70, "d_off": 70, "d_on": 60},
    "GPT-4o": {"s_off": 90, "s_on": 80, "d_off": 70, "d_on": 80},
    "o3":     {"s_off": 60, "s_on": 70, "d_off": 90, "d_on": 90},
    "Opus":   {"s_off": 90, "s_on": 70, "d_off": 40, "d_on": 60},
    "Gemini": {"s_off": 90, "s_on": 80, "d_off": 90, "d_on": 10},
}
MODELS = [model for model in MODEL_ORDER if model in rid_data]

COLOR_OFF = PAL["input"]        # beige
COLOR_ON = PAL["code"]          # blue
COLOR_IMPROVE = PAL["deter"]    # seafoam green
COLOR_DECLINE = PAL["novel"]    # coral
COLOR_FLAT = "#A8A8A8"          # grey

fig, (ax_s, ax_d) = plt.subplots(
    1, 2, figsize=(10.5, 4.4),
    gridspec_kw={"wspace": 0.24},
    sharey=True,
)

y_pos = list(range(len(MODELS)))


def plot_dots(ax, off_key, on_key, title):
    for i, model in enumerate(MODELS):
        off = rid_data[model][off_key]
        on = rid_data[model][on_key]
        delta = on - off

        # Color of the "on" dot based on direction of change
        if delta > 2:
            arrow_color = COLOR_IMPROVE
            delta_label = f"+{delta}"
        elif delta < -2:
            arrow_color = COLOR_DECLINE
            delta_label = f"{delta}"
        else:
            arrow_color = COLOR_FLAT
            delta_label = "≈0"

        # Arrow from off to on
        ax.annotate(
            "",
            xy=(on, i), xytext=(off, i),
            arrowprops=dict(arrowstyle="->", color=arrow_color,
                             lw=2.2, shrinkA=8, shrinkB=8),
            zorder=2)

        # Off dot (beige) — model marker shape
        ax.scatter(off, i, s=140, color=COLOR_OFF,
                   marker=MODEL_MARKERS[model],
                   edgecolor="#8a7a68", linewidth=0.9,
                   zorder=3, label="RID OFF" if i == 0 else None)
        # On dot (colored by direction of change) — same model marker shape
        ax.scatter(on, i, s=140, color=arrow_color,
                   marker=MODEL_MARKERS[model],
                   edgecolor="#444", linewidth=0.9,
                   zorder=4, label="RID ON" if i == 0 else None)

        # Delta label to the right
        right_x = max(off, on) + 3
        ax.text(right_x, i, delta_label,
                ha="left", va="center", fontweight="bold", color=arrow_color)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(MODELS)
    ax.set_xlabel("Pass rate (%)")
    ax.set_xlim(0, 110)
    ax.set_ylim(-0.6, len(MODELS) - 0.4)
    ax.invert_yaxis()
    ax.set_title(title, fontweight="bold", pad=8)


plot_dots(ax_s, "s_off", "s_on", "(a) L3 Strategy (RID OFF $\\to$ ON)")
plot_dots(ax_d, "d_off", "d_on", "(b) L4 Direction (RID OFF $\\to$ ON)")

# Legend. Keep it below the x-axis labels with explicit bottom margin; the
# paper caption carries the descriptive N=10 / not-significant note, so the
# figure does not need a second caption-like line inside the image.
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_OFF,
           markeredgecolor="#8a7a68", markersize=11, label="RID OFF"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_IMPROVE,
           markersize=11, label="RID ON (improved)"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_DECLINE,
           markersize=11, label="RID ON (declined)"),
]
fig.legend(
    handles=legend_elements,
    loc="lower center",
    ncol=3,
    framealpha=0.94,
    edgecolor="#cccccc",
    bbox_to_anchor=(0.5, 0.01),
)

fig.suptitle(
    "RID pre-commitment ablation (pilot, N=10 papers)",
    fontweight="bold",
    y=0.99,
)

fig.subplots_adjust(left=0.09, right=0.985, bottom=0.28, top=0.82)

for out_dir in [Path("paper/figures"), Path("paper/latex/figures")]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "fig_rid_pilot.pdf"
    png = out.with_suffix(".png")
    plt.savefig(out, dpi=220, bbox_inches="tight")
    plt.savefig(png, dpi=220, bbox_inches="tight")
    print(f"  ✓ {out}")
    print(f"  ✓ {png}")
plt.close()
