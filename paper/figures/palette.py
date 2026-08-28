"""
Canonical CausalVerify color palette.

All figure scripts should import from this module to ensure visual
consistency across the paper. Modeled on fig1_v4 Morandi scheme.
"""

# ── Semantic / concept colors ──
PAL = {
    # Tasks
    "input":     "#E5D8C3",  # Exp A (real papers, beige)
    "input_d":   "#9E8B6E",

    # Models
    "model":     "#D1DFE9",
    "model_d":   "#5E8BA8",

    # Outputs
    "code":      "#5B8DB8",  # R code (cornflower blue)
    "code_d":    "#2D5A7C",

    # Novel layer (L2b+)
    "novel":     "#D4785A",  # coral
    "novel_bg":  "#FBE9E0",  # pale coral
    "novel_d":   "#8C3E1D",

    # Deterministic group (L1, L2a, L2b)
    "deter":     "#6BA898",  # seafoam green
    "deter_bg":  "#E8F5F0",
    "deter_d":   "#3E7864",

    # Text-fragile group (L3, L4)
    "fragile":   "#C89F72",  # warm tan
    "fragile_bg":"#F8EFE0",
    "fragile_d": "#8A5E38",

    # Utility / background
    "zone_bg":   "#F8F6F2",
    "zone_edge": "#E8E4DF",
    "ink":       "#1A1A1A",
    "muted":     "#6B6B6B",
    "shadow":    "#C8C8C8",
    "divider":   "#D8D2C8",
}

# ── Canonical per-model colors (used across all figures) ──
MODEL_COLORS = {
    "Opus":    "#D4785A",  # coral (best L2b+ performer, matches novel color)
    "GPT-4o":  "#5B8DB8",  # cornflower blue
    "Sonnet":  "#9B82BB",  # muted violet
    "o3":      "#7D9CAD",  # slate blue
    "Kimi":    "#D4A85A",  # golden amber
    "Gemini":  "#6BA898",  # seafoam green
    "GPT-5":   "#3D5A80",  # deep navy (OpenAI provider family)
}

# Ordering for consistent bar/rank positions. GPT-5 is kept last for
# visual stability with earlier v11 figures.
MODEL_ORDER = ["Opus", "GPT-4o", "Sonnet", "o3", "Kimi", "Gemini", "GPT-5"]

# Canonical per-model marker shapes (shape + color = double encoding)
MODEL_MARKERS = {
    "Opus":   "o",   # circle
    "GPT-4o": "s",   # square
    "Sonnet": "^",   # triangle up
    "o3":     "D",   # diamond
    "Kimi":   "P",   # plus (filled)
    "Gemini": "X",   # x (filled)
    "GPT-5":  "*",   # star
}

# ── Method family colors (used in sunburst, method-level heatmap) ──
METHOD_COLORS = {
    "DID":         "#DCCBB2",  # soft tan
    "ES":          "#C4B59A",  # darker tan
    "EVENT_STUDY": "#C4B59A",
    "IV":          "#A896C2",  # muted violet
    "RDD":         "#7FB59F",  # soft teal
}

# ── Domain colors (used in sunburst outer ring only) ──
DOMAIN_COLORS = {
    "finance":     "#5B8DB8",
    "labor":       "#9B82BB",
    "health":      "#6BA898",
    "education":   "#D4A85A",
    "development": "#D4785A",
    "public":      "#7D9CAD",
    "trade":       "#A8C5D5",
    "environment": "#8FB08E",
    "urban":       "#C8B8A6",
    "agriculture": "#E8C8A0",
}

# ── Layer-specific colors for grouped bar charts (L2a/L2b/L2b+) ──
LAYER_COLORS = {
    "L1":    PAL["deter_bg"],
    "L2a":   "#C8B8A6",        # pale beige (near-ceiling layer)
    "L2b":   PAL["code"],       # blue (code executes)
    "L2b+":  PAL["novel"],      # coral (DGP-verified)
    "L3":    PAL["fragile"],    # tan (strategy)
    "L4":    PAL["fragile"],    # tan (direction)
}

# ── Diverging colormap stops (heatmaps) ──
# Goes from pale coral (low) through beige (mid) to cornflower blue (high)
HEATMAP_STOPS = [
    (0.00, "#FBE9E0"),   # very pale coral
    (0.25, "#F2C0A0"),   # light coral
    (0.50, "#E8D8C0"),   # beige
    (0.75, "#B8D0DC"),   # pale blue
    (1.00, "#5B8DB8"),   # cornflower blue
]

# ── Standard matplotlib rcParams for all figures ──
RC_PARAMS = {
    # Match NeurIPS body text (Times / serif) for visual consistency
    "font.family":       "serif",
    "font.serif":        ["Times", "Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset":  "stix",
    # Unified font-size stack for all paper figures.
    "font.size":         13,
    "axes.titlesize":    14,
    "axes.labelsize":    13,
    "xtick.labelsize":   12,
    "ytick.labelsize":   12,
    "legend.fontsize":   12,
    "figure.titlesize":  15,
    "axes.facecolor":    "#FAFAFA",
    "figure.facecolor":  "white",
    "axes.grid":         True,
    "axes.axisbelow":    True,
    "grid.color":        "#E8E4DF",
    "grid.linestyle":    "--",
    "grid.linewidth":    0.5,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "pdf.fonttype":      42,
    "ps.fonttype":       42,
}
