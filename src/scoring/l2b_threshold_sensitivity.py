#!/usr/bin/env python3
"""
A6 · L2b+ threshold sensitivity and small-coefficient boundary handling.

Implements three things from the master plan (Module 4.2):

  Task 4.2.1 — Small-coefficient robust scoring.
      For scenarios where |beta_true| < DGP_SCALE_PCT of DGP scale,
      switch from relative error  (|beta_hat - beta_true| / |beta_true|)
      to absolute error           (|beta_hat - beta_true|).
      This prevents tiny-beta scenarios from dominating the pass-rate
      (where a 0.01 error on beta* = 0.001 produces rel_error = 10).

  Task 4.2.2 — Sensitivity sweep.
      Compute L2b+ pass rates at thresholds {0.1, 0.2, 0.3, 0.5, 1.0}
      for each of the 6 (or 7) evaluated models.

  Task 4.2.3 — Ranking stability.
      Compute Kendall tau for the 6-model ranking at each threshold vs
      the canonical threshold (0.5). If tau remains high across
      thresholds, the ranking is robust.

Outputs
  paper/tables/l2b_sensitivity_appendix.tex   (LaTeX booktabs table)
  audit/l2b_sensitivity_sweep.csv             (long-format data for figs)
  experiments_log/runs/YYYY-MM-DD/NNN__a6_l2b_threshold_sensitivity/

Usage
  python3 src/scoring/l2b_threshold_sensitivity.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

# ----------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
SCORES = ROOT / "experiments/exp_b/l2b_plus_scores.csv"
SCENARIOS_DIR = ROOT / "experiments/exp_b/scenarios"
OUT_CSV = ROOT / "audit/l2b_sensitivity_sweep.csv"
OUT_TEX = ROOT / "paper/tables/l2b_sensitivity_appendix.tex"

sys.path.insert(0, str(ROOT / "src"))
from labnotebook.experiment_logger import ExperimentLogger

# ----------------------------------------------------------------- config
THRESHOLDS = [0.1, 0.2, 0.3, 0.5, 1.0]      # master plan 4.2.2
CANONICAL = 0.5                             # current primary threshold

# Small-coefficient rule: if |beta*| < 1% of DGP scale, use absolute error.
# We approximate DGP scale as the 90th percentile of |true_effect| within
# each method family — this is defensible and doesn't require reading the
# DGP simulation code.
DGP_SCALE_PCT = 0.01

# -----------------------------------------------------------------

def _float(s: str) -> float:
    try: return float(s)
    except (ValueError, TypeError): return float("nan")


def _to_bool(s: str) -> bool:
    return str(s).strip() in {"1", "True", "true"}


def load_scores() -> list[dict]:
    rows = []
    with SCORES.open() as f:
        for r in csv.DictReader(f):
            rows.append({
                "scenario_id":   r["scenario_id"],
                "method":        r["method"],
                "true_effect":   _float(r["true_effect"]),
                "true_direction": r["true_direction"],
                "L2b":           _to_bool(r["L2b"]),
                "estimated":     _float(r["estimated"]),
                "rel_error":     _float(r["rel_error"]),
                "L2b_plus_orig": _to_bool(r["L2b_plus"]),
                "model":         r["model"],
            })
    return rows


# -----------------------------------------------------------------

def compute_dgp_scales(rows: list[dict]) -> dict[str, float]:
    """Per-method 90th percentile of |true_effect|, our DGP-scale proxy."""
    by_method: dict[str, list[float]] = defaultdict(list)
    seen_scenarios: set[str] = set()
    for r in rows:
        if r["scenario_id"] in seen_scenarios: continue
        seen_scenarios.add(r["scenario_id"])
        by_method[r["method"]].append(abs(r["true_effect"]))
    scales: dict[str, float] = {}
    for m, vals in by_method.items():
        vals = sorted(v for v in vals if v > 0)
        if not vals:
            scales[m] = 0.0
            continue
        # 90th percentile
        idx = int(round(0.9 * (len(vals) - 1)))
        scales[m] = vals[idx]
    return scales


def is_small_coef(row: dict, dgp_scales: dict[str, float]) -> bool:
    scale = dgp_scales.get(row["method"], 0.0)
    if scale <= 0: return False
    return abs(row["true_effect"]) < DGP_SCALE_PCT * scale


def score_at_threshold(row: dict, tau: float, dgp_scales: dict[str, float]) -> bool:
    """
    Returns True iff the scenario passes L2b+ at threshold `tau`.

    Definition:
      Pass = (code executed) AND (error below tolerance).
      Tolerance:
        small-coef scenarios → absolute error tolerance `tau` (using DGP scale)
        normal scenarios     → relative error tolerance `tau`
    """
    if not row["L2b"]: return False             # must execute
    if row["estimated"] != row["estimated"]:     # NaN
        return False
    beta_hat = row["estimated"]
    beta_true = row["true_effect"]
    err_abs = abs(beta_hat - beta_true)

    if is_small_coef(row, dgp_scales):
        # Use absolute-error tolerance, scaled by DGP scale of this method
        scale = dgp_scales.get(row["method"], 1.0) or 1.0
        return err_abs < tau * scale
    if beta_true == 0:
        return err_abs < tau   # degenerate; fall back to abs
    return err_abs / abs(beta_true) < tau


# -----------------------------------------------------------------

def kendall_tau(x: list[float], y: list[float]) -> float:
    """Unweighted Kendall's tau-b over two aligned rank vectors."""
    if len(x) != len(y) or len(x) < 2:
        return float("nan")
    n = len(x)
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            s = dx * dy
            if s > 0: concordant += 1
            elif s < 0: discordant += 1
    total = n * (n - 1) / 2
    if total == 0: return float("nan")
    return (concordant - discordant) / total


# -----------------------------------------------------------------

def main() -> int:
    exp = ExperimentLogger(
        run_name="a6_l2b_threshold_sensitivity",
        script_path=__file__,
        hypothesis=(
            "Primary threshold tau=0.5 yields rankings that are stable "
            "across tau in {0.1, 0.2, 0.3, 0.5, 1.0} with pairwise "
            "Kendall tau >= 0.8 on the 6-model ranking."
        ),
        config={
            "thresholds":     THRESHOLDS,
            "canonical":      CANONICAL,
            "dgp_scale_pct":  DGP_SCALE_PCT,
            "scores_input":   str(SCORES.relative_to(ROOT)),
        },
    )

    rows = load_scores()
    exp.log_event("loaded_scores", n_rows=len(rows))

    dgp_scales = compute_dgp_scales(rows)
    exp.log_event("computed_dgp_scales", dgp_scales=dgp_scales)

    small = sum(1 for r in rows if is_small_coef(r, dgp_scales))
    exp.log_event("small_coef_rows", n=small)

    # Sweep: per (model, threshold) → pass-rate
    models = sorted({r["model"] for r in rows})
    sweep: dict[tuple[str, float], float] = {}
    n_scenarios_per_model: dict[str, int] = {}
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        n_scenarios_per_model[m] = len(sub)
        for t in THRESHOLDS:
            passes = sum(1 for r in sub if score_at_threshold(r, t, dgp_scales))
            sweep[(m, t)] = passes / len(sub) if sub else 0.0

    # Write long-format CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "threshold", "pass_rate", "n_scenarios"])
        for m in models:
            for t in THRESHOLDS:
                w.writerow([m, t, round(sweep[(m, t)], 4),
                            n_scenarios_per_model[m]])
    exp.attach_output("sweep_csv", OUT_CSV)

    # Rankings at each threshold (higher pass-rate = better rank)
    rankings: dict[float, list[tuple[str, float]]] = {}
    for t in THRESHOLDS:
        rankings[t] = sorted(
            ((m, sweep[(m, t)]) for m in models),
            key=lambda x: -x[1],
        )

    # Kendall tau matrix (thresholds vs thresholds)
    model_order = models
    rate_vecs: dict[float, list[float]] = {
        t: [sweep[(m, t)] for m in model_order] for t in THRESHOLDS
    }
    tau_matrix: dict[tuple[float, float], float] = {}
    for ta in THRESHOLDS:
        for tb in THRESHOLDS:
            tau_matrix[(ta, tb)] = kendall_tau(rate_vecs[ta], rate_vecs[tb])

    # Generate LaTeX table
    OUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "% Auto-generated by src/scoring/l2b_threshold_sensitivity.py",
        "% A6 · L2b+ threshold sensitivity appendix table",
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\caption{L2b+ pass-rate sensitivity to the relative-error "
        "threshold $\\tau$. Each row is an evaluated model; columns are "
        "thresholds. The canonical threshold is $\\tau=0.5$. "
        "For scenarios where $|\\beta^{*}|$ is below 1\\% of the "
        "per-method DGP scale, absolute error is used instead. "
        "Kendall's $\\tau$ is computed against the canonical-threshold "
        "ranking of models.}",
        "\\label{tab:l2b-threshold-sensitivity}",
        "\\begin{tabular}{l" + "c" * len(THRESHOLDS) + "}",
        "\\toprule",
        "Model & " + " & ".join(f"$\\tau={t}$" for t in THRESHOLDS) + " \\\\",
        "\\midrule",
    ]
    # Order models by canonical-threshold pass-rate, descending
    canon_order = [m for m, _ in rankings[CANONICAL]]
    for m in canon_order:
        cells = " & ".join(f"{sweep[(m, t)]*100:.1f}\\%" for t in THRESHOLDS)
        lines.append(f"{m} & {cells} \\\\")
    lines.append("\\midrule")
    # Kendall tau row vs canonical
    kr = []
    for t in THRESHOLDS:
        tau = tau_matrix[(CANONICAL, t)]
        kr.append("$1.00$" if t == CANONICAL else f"${tau:.2f}$")
    lines.append("Kendall $\\tau$ vs $\\tau=" + str(CANONICAL) + "$ & " +
                 " & ".join(kr) + " \\\\")
    lines += [
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
    ]
    OUT_TEX.write_text("\n".join(lines) + "\n")
    exp.attach_output("tex_table", OUT_TEX)

    # Console output
    print(f"Models:       {len(models)} ({', '.join(models)})")
    print(f"Scenarios/m:  {next(iter(n_scenarios_per_model.values()))}")
    print(f"Small-coef rows (of {len(rows)}): {small}")
    print(f"DGP scales (90th pct |beta*|): {dgp_scales}")
    print()
    print(f"{'model':<10} " + " ".join(f"tau={t}" for t in THRESHOLDS))
    for m in canon_order:
        print(f"{m:<10} " + " ".join(f"{sweep[(m, t)]*100:>6.1f}%" for t in THRESHOLDS))
    print()
    print("Kendall tau vs canonical (tau = {}):".format(CANONICAL))
    for t in THRESHOLDS:
        if t == CANONICAL:
            print(f"  tau={t}: 1.00 (self)")
        else:
            print(f"  tau={t}: {tau_matrix[(CANONICAL, t)]:+.3f}")

    # Compute minimum Kendall tau across all pairwise comparisons
    min_tau = min(tau_matrix[(a, b)]
                  for a in THRESHOLDS for b in THRESHOLDS if a != b)
    exp.finish(
        status="success",
        results={
            "n_models":         len(models),
            "n_scenarios":      next(iter(n_scenarios_per_model.values())),
            "small_coef_rows":  small,
            "pass_rates_by_threshold": {
                m: {t: round(sweep[(m, t)], 4) for t in THRESHOLDS}
                for m in canon_order
            },
            "kendall_tau_vs_canonical": {
                str(t): round(tau_matrix[(CANONICAL, t)], 3) for t in THRESHOLDS
            },
            "min_pairwise_tau": round(min_tau, 3),
            "ranking_stable":   bool(min_tau >= 0.8),
        },
        interpretation=(
            f"Primary-threshold ranking is {'stable' if min_tau >= 0.8 else 'UNSTABLE'} "
            f"across the five sampled thresholds (min pairwise Kendall tau = {min_tau:.3f}). "
            f"{small} of {len(rows)} scenario-model rows have |beta*| in the "
            "small-coefficient regime and were scored via absolute error."
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
