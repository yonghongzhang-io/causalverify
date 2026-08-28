"""
Agent 6 — DGP Verifier
=======================

Purpose
-------
For every Exp B scenario, run the *canonical* regression for that method
family on the synthetic CSV data and verify that the recovered coefficient
β̂ is within 10% of the stated true effect β* (from dgp_truth.effect).

Why this matters
----------------
The paper's core claim — "LLMs fail to recover β*" — depends on β* being
the actual identifiable treatment effect in the synthetic data. If the DGP
implementation has bugs such that the true identifiable β is not the stated
β*, the entire L2b+ argument is undermined.

This agent closes that gap: it empirically validates that the synthetic
DGPs behave as advertised.

Canonical specifications
------------------------
  DID         : y ~ treat_x_post | unit FE + period FE   (TWFE)
  EVENT_STUDY : ret = α + β·mkt_ret + θ·(event_day ≥ 0)  (market model + event dummy)
  IV          : y ~ x + controls, instrumented by z       (2SLS)
  RDD         : y ~ treated + running_var + running_var·treated near cutoff  (local linear)

Quality gate
------------
  rel_error < 10%  → status "VERIFIED"
  rel_error ≥ 10%  → status "FLAGGED" (DGP may have a bug)

Output
------
v11/audit/dgp_verification.json  — per-scenario results
v11/audit/dgp_verification_summary.md — human-readable summary

Usage
-----
  python3 src/agents/dgp_verifier.py
  python3 src/agents/dgp_verifier.py --tolerance 0.05   # stricter
"""

import argparse
import json
import warnings
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCEN_DIR = PROJECT_ROOT / "experiments/exp_b/scenarios"
OUT_JSON = PROJECT_ROOT / "audit/dgp_verification.json"
OUT_MD = PROJECT_ROOT / "audit/dgp_verification_summary.md"


# ── Canonical regressions per method ───────────────────────────────────

def verify_did(df: pd.DataFrame) -> tuple[Optional[float], Optional[float], str]:
    """TWFE via within transformation (demean by unit and period, then OLS).

    Returns (estimated_beta, se, notes).
    """
    import statsmodels.api as sm

    # Expect columns: unit_id, period, treated, post, treat_x_post, y
    required = {"unit_id", "period", "treat_x_post", "y"}
    if not required.issubset(df.columns):
        return None, None, f"missing columns: {required - set(df.columns)}"

    # Demean y and treat_x_post by unit and period
    df = df.copy()
    df["y_demean_unit"] = df["y"] - df.groupby("unit_id")["y"].transform("mean")
    df["y_demean"] = (df["y_demean_unit"]
                      - df.groupby("period")["y_demean_unit"].transform("mean"))
    df["t_demean_unit"] = (df["treat_x_post"]
                           - df.groupby("unit_id")["treat_x_post"].transform("mean"))
    df["t_demean"] = (df["t_demean_unit"]
                      - df.groupby("period")["t_demean_unit"].transform("mean"))

    # OLS on demeaned variables
    X = sm.add_constant(df[["t_demean"]])
    model = sm.OLS(df["y_demean"], X).fit()

    beta = float(model.params["t_demean"])
    se = float(model.bse["t_demean"])
    return beta, se, "TWFE via within transformation"


def verify_event_study(df: pd.DataFrame) -> tuple[Optional[float], Optional[float], str]:
    """Market-model cumulative abnormal return on event window (day >= 0).

    Model: ret = α + β·mkt_ret + θ·I(event_day >= 0) + ε
    """
    import statsmodels.api as sm

    required = {"stock_id", "event_day", "ret", "mkt_ret"}
    if not required.issubset(df.columns):
        return None, None, f"missing columns: {required - set(df.columns)}"

    df = df.copy()
    df["post_event"] = (df["event_day"] >= 0).astype(int)

    # Pool across stocks (paper-level AR is what DGP targets)
    X = sm.add_constant(df[["mkt_ret", "post_event"]])
    model = sm.OLS(df["ret"], X).fit(cov_type="cluster",
                                      cov_kwds={"groups": df["stock_id"]})
    beta = float(model.params["post_event"])
    se = float(model.bse["post_event"])
    return beta, se, "Market model + post-event dummy (stock-clustered SE)"


def verify_iv(df: pd.DataFrame) -> tuple[Optional[float], Optional[float], str]:
    """2SLS: y ~ x + controls, endog = x, instrument = z."""
    from linearmodels.iv import IV2SLS

    required = {"y", "x", "z"}
    if not required.issubset(df.columns):
        return None, None, f"missing columns: {required - set(df.columns)}"

    has_controls = "controls" in df.columns
    exog_cols = ["controls"] if has_controls else []

    # linearmodels syntax
    dependent = df["y"]
    endog = df[["x"]]
    instruments = df[["z"]]
    if exog_cols:
        exog = df[exog_cols]
        import statsmodels.api as sm
        exog = sm.add_constant(exog)
    else:
        exog = pd.DataFrame({"const": np.ones(len(df))})

    model = IV2SLS(dependent, exog, endog, instruments).fit(cov_type="robust")
    beta = float(model.params["x"])
    se = float(model.std_errors["x"])
    return beta, se, "2SLS with z as instrument for x"


def verify_rdd(df: pd.DataFrame) -> tuple[Optional[float], Optional[float], str]:
    """Sharp RDD: local linear regression near cutoff.

    DGP uses cutoff=0.5 by default. Fit:
      y ~ treated + (running_var - 0.5) + treated · (running_var - 0.5)
    on observations within bandwidth.
    """
    import statsmodels.api as sm

    required = {"y", "running_var", "treated"}
    if not required.issubset(df.columns):
        return None, None, f"missing columns: {required - set(df.columns)}"

    cutoff = 0.5  # DGP default
    df = df.copy()
    df["rv_c"] = df["running_var"] - cutoff
    df["rv_c_x_treated"] = df["rv_c"] * df["treated"]

    # Restrict to near-cutoff sample (use near_cutoff flag if present)
    if "near_cutoff" in df.columns:
        mask = df["near_cutoff"] == 1
    else:
        mask = (df["running_var"].sub(cutoff).abs() <= 0.3)  # same as DGP default

    df_near = df[mask].copy()
    if len(df_near) < 30:
        return None, None, f"too few near-cutoff observations: {len(df_near)}"

    X = sm.add_constant(df_near[["treated", "rv_c", "rv_c_x_treated"]])
    model = sm.OLS(df_near["y"], X).fit(cov_type="HC3")
    beta = float(model.params["treated"])
    se = float(model.bse["treated"])
    return beta, se, f"Local linear RDD (n={len(df_near)}, bw≤0.3)"


METHOD_VERIFIERS = {
    "DID": verify_did,
    "EVENT_STUDY": verify_event_study,
    "IV": verify_iv,
    "RDD": verify_rdd,
}


# ── Data structures ─────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    scenario_id: str
    method_family: str
    true_effect: float
    estimated: Optional[float]
    standard_error: Optional[float]
    rel_error: Optional[float]
    status: str            # "VERIFIED" / "FLAGGED" / "ERROR"
    regression_notes: str
    n_observations: int
    sign_correct: Optional[bool]
    error_msg: str = ""


# ── Main verification loop ─────────────────────────────────────────────

def verify_scenario(scen_path: Path, tolerance: float) -> VerificationResult:
    with open(scen_path) as f:
        scen = json.load(f)

    sid = scen["scenario_id"]
    method = scen["method_family"]
    true_effect = scen["dgp_truth"]["effect"]
    data_path = PROJECT_ROOT / scen["data_file"]

    try:
        df = pd.read_csv(data_path)
        n_obs = len(df)
    except Exception as e:
        return VerificationResult(
            scenario_id=sid, method_family=method, true_effect=true_effect,
            estimated=None, standard_error=None, rel_error=None,
            status="ERROR", regression_notes="",
            n_observations=0, sign_correct=None,
            error_msg=f"data load failed: {e}",
        )

    verifier = METHOD_VERIFIERS.get(method)
    if verifier is None:
        return VerificationResult(
            scenario_id=sid, method_family=method, true_effect=true_effect,
            estimated=None, standard_error=None, rel_error=None,
            status="ERROR", regression_notes="",
            n_observations=n_obs, sign_correct=None,
            error_msg=f"no verifier for method {method}",
        )

    try:
        beta, se, notes = verifier(df)
    except Exception as e:
        return VerificationResult(
            scenario_id=sid, method_family=method, true_effect=true_effect,
            estimated=None, standard_error=None, rel_error=None,
            status="ERROR", regression_notes="",
            n_observations=n_obs, sign_correct=None,
            error_msg=f"{type(e).__name__}: {str(e)[:200]}",
        )

    if beta is None:
        return VerificationResult(
            scenario_id=sid, method_family=method, true_effect=true_effect,
            estimated=None, standard_error=None, rel_error=None,
            status="ERROR", regression_notes=notes,
            n_observations=n_obs, sign_correct=None,
            error_msg="verifier returned None (see notes)",
        )

    rel_error = abs(beta - true_effect) / max(abs(true_effect), 1e-6)
    status = "VERIFIED" if rel_error < tolerance else "FLAGGED"
    sign_correct = (beta * true_effect > 0) if abs(true_effect) > 1e-6 else None

    return VerificationResult(
        scenario_id=sid, method_family=method, true_effect=true_effect,
        estimated=round(beta, 6), standard_error=round(se, 6) if se else None,
        rel_error=round(rel_error, 4),
        status=status, regression_notes=notes,
        n_observations=n_obs, sign_correct=sign_correct,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tolerance", type=float, default=0.10,
                        help="Relative error threshold for VERIFIED (default 0.10 = 10%)")
    args = parser.parse_args()

    scenarios = sorted(SCEN_DIR.glob("s*.json"),
                        key=lambda p: int(p.stem[1:]))
    print(f"Running canonical regressions on {len(scenarios)} scenarios "
          f"(tolerance = ±{args.tolerance*100:.0f}%)\n")

    results = []
    for scen_path in scenarios:
        r = verify_scenario(scen_path, args.tolerance)
        results.append(r)

        symbol = {"VERIFIED": "✓", "FLAGGED": "⚠", "ERROR": "✗"}[r.status]
        if r.estimated is not None:
            print(f"  [{symbol}] {r.scenario_id:<5} {r.method_family:<12} "
                  f"true={r.true_effect:+.3f} est={r.estimated:+.3f} "
                  f"rel_err={r.rel_error:.3f} [{r.status}]")
        else:
            print(f"  [{symbol}] {r.scenario_id:<5} {r.method_family:<12} "
                  f"true={r.true_effect:+.3f} [{r.status}] {r.error_msg[:60]}")

    # Aggregates
    n_total = len(results)
    n_verified = sum(1 for r in results if r.status == "VERIFIED")
    n_flagged = sum(1 for r in results if r.status == "FLAGGED")
    n_error = sum(1 for r in results if r.status == "ERROR")

    from collections import defaultdict
    by_method = defaultdict(lambda: {"verified": 0, "flagged": 0, "error": 0, "total": 0})
    for r in results:
        by_method[r.method_family]["total"] += 1
        if r.status == "VERIFIED":
            by_method[r.method_family]["verified"] += 1
        elif r.status == "FLAGGED":
            by_method[r.method_family]["flagged"] += 1
        elif r.status == "ERROR":
            by_method[r.method_family]["error"] += 1

    # Mean rel error
    rel_errors = [r.rel_error for r in results if r.rel_error is not None]
    mean_rel_err = np.mean(rel_errors) if rel_errors else None
    median_rel_err = np.median(rel_errors) if rel_errors else None

    # Save JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump({
            "tolerance": args.tolerance,
            "summary": {
                "total": n_total,
                "verified": n_verified,
                "flagged": n_flagged,
                "error": n_error,
                "verified_pct": round(n_verified / n_total, 4),
                "mean_rel_error": round(mean_rel_err, 4) if mean_rel_err is not None else None,
                "median_rel_error": round(median_rel_err, 4) if median_rel_err is not None else None,
                "by_method": dict(by_method),
            },
            "results": [asdict(r) for r in results],
        }, f, indent=2)

    # Markdown
    lines = [
        "# DGP Ground Truth Verification\n",
        f"Ran canonical regressions on {n_total} Exp B scenarios.",
        f"Tolerance: relative error < **{args.tolerance*100:.0f}%**\n",
        "## Aggregate\n",
        f"- VERIFIED:  {n_verified}/{n_total} ({n_verified/n_total:.1%})",
        f"- FLAGGED:   {n_flagged}/{n_total} ({n_flagged/n_total:.1%})",
        f"- ERROR:     {n_error}/{n_total} ({n_error/n_total:.1%})",
    ]
    if mean_rel_err is not None:
        lines.append(f"- Mean relative error:   {mean_rel_err:.3f}")
        lines.append(f"- Median relative error: {median_rel_err:.3f}")

    lines.append("\n## Per-method breakdown\n")
    lines.append("| Method | VERIFIED | FLAGGED | ERROR | Total |")
    lines.append("|---|---:|---:|---:|---:|")
    for method in sorted(by_method):
        m = by_method[method]
        lines.append(f"| {method} | {m['verified']} | {m['flagged']} | {m['error']} | {m['total']} |")

    if n_flagged + n_error > 0:
        lines.append("\n## Flagged / errored scenarios\n")
        for r in results:
            if r.status in ("FLAGGED", "ERROR"):
                details = (f"est={r.estimated:+.3f}, rel_err={r.rel_error:.3f}"
                           if r.estimated is not None
                           else f"ERROR: {r.error_msg}")
                lines.append(f"- **{r.scenario_id}** ({r.method_family}): "
                             f"true={r.true_effect:+.3f}; {details}")

    lines.append("\n## Interpretation\n")
    if n_verified / n_total >= 0.95:
        lines.append("✅ **DGP ground truth is empirically verified** "
                     "(≥95% verified within 10% tolerance). The paper's L2b+ "
                     "argument rests on a sound ground-truth foundation.")
    elif n_verified / n_total >= 0.80:
        lines.append("⚠️  **Most scenarios verified, but some flagged.** "
                     "Review the flagged scenarios for potential DGP bugs. "
                     "Consider excluding flagged scenarios from the main analysis "
                     "or reporting results with and without them.")
    else:
        lines.append("🚨 **DGP verification largely failed.** "
                     "Canonical regressions cannot recover the stated β* in "
                     "most scenarios. The ground truth layer needs substantial "
                     "repair before L2b+ claims can be defended.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote: {OUT_JSON}")
    print(f"Wrote: {OUT_MD}")
    print(f"\n=== SUMMARY ===")
    print(f"VERIFIED: {n_verified}/{n_total} ({n_verified/n_total:.1%})")
    print(f"FLAGGED:  {n_flagged}/{n_total} ({n_flagged/n_total:.1%})")
    print(f"ERROR:    {n_error}/{n_total} ({n_error/n_total:.1%})")


if __name__ == "__main__":
    main()
