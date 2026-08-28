"""
Bootstrap the head-to-head Kendall tau at the scenario level.

The issue: Kendall tau is computed on 6 model rates. The point estimate is
+0.83, p = 0.022, but "effective N" for the rank correlation is only 6. A
reviewer will ask whether this is a small-sample artifact.

Bootstrap procedure:
  for b in 1..B:
    resample 100 scenarios with replacement
    recompute each model's L2b / L2b+ / L4-S2 rate on the resampled set
    rerank the 6 models
    recompute Kendall tau against the resampled GT (L2b+) ranking
  Report mean, SE, 95% CI of the distribution of taus.

This gives us a proper CI on the head-to-head result.
"""

import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau, spearmanr

RESULTS_DIR = Path("experiments/exp_b")
L2B_CSV = RESULTS_DIR / "l2b_plus_scores.csv"

MODELS = ["Kimi", "Sonnet", "GPT-4o", "o3", "Opus", "Gemini"]


def load_per_scenario_scores():
    """Load per-(scenario, model) scores from l2b_plus_scores.csv."""
    with open(L2B_CSV) as f:
        rows = list(csv.DictReader(f))

    # Also need L4 S1 + S2 from multi_scorer (or compute live)
    # For bootstrap we'll recompute L4-S2 on the fly using the outputs
    import sys
    sys.path.insert(0, ".")
    from src.pipeline.multi_scorer_l4 import s2_section6_keyword, s1_latter_half

    OUT_DIR = Path("experiments/exp_b/outputs")
    SCEN_DIR = Path("experiments/exp_b/scenarios")
    slug_map = {
        "Kimi": "moonshot-v1-128k", "Sonnet": "claude-sonnet-4-20250514",
        "GPT-4o": "gpt-4o", "o3": "o3", "Opus": "claude-opus-4-6",
        "Gemini": "gemini-2.5-flash",
    }

    # Build a (scenario_id, model) → dict with all layers
    scores = {}
    for r in rows:
        key = (r["scenario_id"], r["model"])
        scores[key] = {
            "L2a": int(r["L2a"]),
            "L2b": int(r["L2b"]),
            "L2b_plus": int(r["L2b_plus"]),
        }

    # Load scenarios to get GT direction and compute L4 scorers
    scenarios = {}
    for sf in SCEN_DIR.glob("s*.json"):
        d = json.load(open(sf))
        scenarios[d["scenario_id"]] = d

    # Compute L4 per (scenario, model)
    for (sid, model), entry in scores.items():
        scen = scenarios.get(sid)
        if not scen:
            continue
        gt_dir = scen.get("dgp_truth", {}).get("direction", "")
        slug = slug_map[model]
        out_f = OUT_DIR / f"{sid}_{slug}.json"
        if not out_f.exists():
            entry["L4_S1"] = 0
            entry["L4_S2"] = 0
            continue
        content = json.load(open(out_f)).get("llm_response", {}).get("content", "")
        entry["L4_S1"] = int(s1_latter_half(content, gt_dir) == gt_dir)
        entry["L4_S2"] = int(s2_section6_keyword(content, gt_dir) == gt_dir)

    return scores, list(scenarios.keys())


def compute_rates(scores, scenario_subset, layer):
    """Compute per-model rate over a given subset of scenarios."""
    rates = {}
    for m in MODELS:
        vals = [scores.get((s, m), {}).get(layer, 0) for s in scenario_subset]
        rates[m] = sum(vals) / len(vals) if vals else 0
    return rates


def kendall_tau_against_gt(pred_rates: dict, gt_rates: dict) -> float:
    common = [m for m in MODELS if m in pred_rates and m in gt_rates]
    if len(common) < 3:
        return float("nan")
    pred_vec = [pred_rates[m] for m in common]
    gt_vec = [gt_rates[m] for m in common]
    tau, _ = kendalltau(pred_vec, gt_vec)
    return float(tau)


def bootstrap_tau(scores, scenarios, layer_pred, layer_gt="L2b_plus",
                  n_boot=10000, seed=42):
    rng = np.random.default_rng(seed)
    n = len(scenarios)
    taus = []
    for _ in range(n_boot):
        sample = [scenarios[rng.integers(n)] for _ in range(n)]
        pred_rates = compute_rates(scores, sample, layer_pred)
        gt_rates = compute_rates(scores, sample, layer_gt)
        tau = kendall_tau_against_gt(pred_rates, gt_rates)
        if not np.isnan(tau):
            taus.append(tau)
    taus = np.array(taus)
    return {
        "n_boot_valid": len(taus),
        "mean": float(taus.mean()),
        "median": float(np.median(taus)),
        "se": float(taus.std()),
        "ci_low": float(np.percentile(taus, 2.5)),
        "ci_high": float(np.percentile(taus, 97.5)),
        "p_gt_zero": float((taus > 0).mean()),
        "p_gt_half": float((taus > 0.5).mean()),
    }


def main():
    scores, scenarios = load_per_scenario_scores()
    print(f"Loaded {len(scenarios)} scenarios, {len(MODELS)} models",
          flush=True)

    results = {}
    for pred_layer, label in [
        ("L2b",    "L2b (code executes)"),
        ("L2a",    "L2a (code present)"),
        ("L4_S1",  "L4 latter-half (S1)"),
        ("L4_S2",  "L4 section-aware (S2)"),
    ]:
        res = bootstrap_tau(scores, scenarios, pred_layer)
        results[pred_layer] = res
        print(f"\n{label}:")
        print(f"  Bootstrap N={res['n_boot_valid']}")
        print(f"  Kendall τ = {res['mean']:+.3f} (median {res['median']:+.3f})")
        print(f"  SE = {res['se']:.3f}")
        print(f"  95% CI = [{res['ci_low']:+.3f}, {res['ci_high']:+.3f}]")
        print(f"  P(τ > 0)   = {res['p_gt_zero']:.3f}")
        print(f"  P(τ > 0.5) = {res['p_gt_half']:.3f}")

    # Save
    out = RESULTS_DIR / "head_to_head_bootstrap.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
