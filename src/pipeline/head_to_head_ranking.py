"""
Head-to-Head Ranking Comparison: L2b vs L4-text vs Ground Truth (L2b+)
======================================================================

For each (model, scoring metric), compute a model ranking. Then compare
each ranking against the GT ranking (L2b+) using:
  - Kendall tau-b
  - Spearman rho
  - Pairwise ranking accuracy
  - Top-vs-bottom discrimination

The claim 'L2b is more reliable than L4-text' becomes quantitative:
  τ(L2b, GT) > τ(L4_text, GT)

This is the publication-blocker analysis from the user's Point 5.
"""

import csv
import json
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau, spearmanr

RESULTS_DIR = Path("experiments/exp_b")
EXP_A_DIR = Path("experiments/exp_a")

MODELS = ["Kimi", "Sonnet", "GPT-4o", "o3", "Opus", "Gemini", "GPT-5"]


# ── Load per-model rates from each scorer ───────────────────────────────

def load_l2b_plus_rates() -> dict:
    """Load L2b family rates.

    L2a / L2b come from l2b_plus_summary_canonical.json (7-model, has L2a/L2b).
    L2b+ uses the v2 (judge + ES-aware) rate from
    l2b_plus_summary_canonical_judge_v2.json — the post-Stage-8 headline.
    """
    canonical = json.load(open(RESULTS_DIR / "l2b_plus_summary_canonical.json"))
    v2 = json.load(open(RESULTS_DIR / "l2b_plus_summary_canonical_judge_v2.json"))
    bm_c = canonical["by_model"]
    bm_v2 = v2["by_model"]
    return {
        "L2a": {m: bm_c[m]["L2a_rate"] for m in MODELS if m in bm_c},
        "L2b": {m: bm_c[m]["L2b_rate"] for m in MODELS if m in bm_c},
        "L2b_plus": {m: bm_v2[m]["L2b_plus_v2_rate"]
                     for m in MODELS if m in bm_v2},
    }


def load_l4_text_rates() -> dict:
    """Load L4-text rates from multi_scorer_summary.json (or auto_scores.csv)."""
    rates = {}

    # First, try the multi_scorer_summary if it exists with full data
    msf = EXP_A_DIR / "multi_scorer_summary.json"
    if msf.exists():
        ms = json.load(open(msf))
        # Note: multi-scorer was on Exp A (137 papers), but we need Exp B for direct comparison
        # We'll load whatever we can

    # For now, compute Exp B L4 rates from outputs directly using our existing scorers
    return rates


def compute_exp_b_l4_rates() -> dict:
    """Compute L4 rates on Exp B using S1 and S2 scorers."""
    import sys
    sys.path.insert(0, ".")
    from src.pipeline.multi_scorer_l4 import s1_latter_half, s2_section6_keyword

    OUT_DIR = Path("experiments/exp_b/outputs")
    SCEN_DIR = Path("experiments/exp_b/scenarios")
    MODEL_SLUGS = [
        ("moonshot-v1-128k", "Kimi"),
        ("claude-sonnet-4-20250514", "Sonnet"),
        ("gpt-4o", "GPT-4o"),
        ("o3", "o3"),
        ("claude-opus-4-6", "Opus"),
        ("gemini-2.5-flash", "Gemini"),
        ("gpt-5", "GPT-5"),
    ]

    s1_results = {ms: {"correct": 0, "total": 0} for _, ms in MODEL_SLUGS}
    s2_results = {ms: {"correct": 0, "total": 0} for _, ms in MODEL_SLUGS}

    for s_file in sorted(SCEN_DIR.glob("s*.json"), key=lambda p: int(p.stem[1:])):
        scenario = json.load(open(s_file))
        sid = scenario["scenario_id"]
        gt_dir = scenario.get("dgp_truth", {}).get("direction", "")

        for slug, short in MODEL_SLUGS:
            out_f = OUT_DIR / f"{sid}_{slug}.json"
            if not out_f.exists():
                continue
            content = json.load(open(out_f)).get("llm_response", {}).get("content", "")
            if not content:
                continue
            s1_results[short]["total"] += 1
            s2_results[short]["total"] += 1
            if s1_latter_half(content, gt_dir) == gt_dir:
                s1_results[short]["correct"] += 1
            if s2_section6_keyword(content, gt_dir) == gt_dir:
                s2_results[short]["correct"] += 1

    return {
        "L4_S1_latter_half": {
            ms: round(r["correct"] / r["total"], 4) if r["total"] else 0
            for ms, r in s1_results.items()
        },
        "L4_S2_section_aware": {
            ms: round(r["correct"] / r["total"], 4) if r["total"] else 0
            for ms, r in s2_results.items()
        },
    }


# ── Ranking comparison ──────────────────────────────────────────────────

def rates_to_ranking(rates: dict) -> list:
    """Convert {model: rate} to a ranking (descending). Returns ordered list of models."""
    return [m for m, _ in sorted(rates.items(), key=lambda kv: -kv[1])]


def kendall_pairwise_acc(ranks_a: list, ranks_b: list) -> float:
    """Pairwise ranking accuracy: fraction of pairs where the two rankings agree."""
    pos_a = {m: i for i, m in enumerate(ranks_a)}
    pos_b = {m: i for i, m in enumerate(ranks_b)}
    common = set(pos_a) & set(pos_b)
    if len(common) < 2:
        return float("nan")
    pairs = list(combinations(common, 2))
    agree = 0
    for x, y in pairs:
        # Both rankings agree on the order of (x, y)?
        if (pos_a[x] < pos_a[y]) == (pos_b[x] < pos_b[y]):
            agree += 1
    return agree / len(pairs)


def top_bottom_discrimination(rates_pred: dict, rates_gt: dict) -> dict:
    """How often does the pred ranking put the GT-top model in the top half?"""
    common = sorted(set(rates_pred) & set(rates_gt))
    if len(common) < 4:
        return {"top1_match": float("nan"), "top_half_overlap": float("nan")}

    pred_sorted = sorted(common, key=lambda m: -rates_pred[m])
    gt_sorted = sorted(common, key=lambda m: -rates_gt[m])

    top1_match = pred_sorted[0] == gt_sorted[0]

    n = len(common)
    top_half = n // 2
    pred_top = set(pred_sorted[:top_half])
    gt_top = set(gt_sorted[:top_half])
    overlap = len(pred_top & gt_top) / top_half

    return {
        "top1_match": int(top1_match),
        "top_half_overlap": round(overlap, 3),
    }


def ranking_correlation(rates_pred: dict, rates_gt: dict) -> dict:
    """Compute Kendall tau-b and Spearman rho between two model rankings."""
    common = sorted(set(rates_pred) & set(rates_gt))
    if len(common) < 3:
        return {}

    pred_vec = [rates_pred[m] for m in common]
    gt_vec = [rates_gt[m] for m in common]

    tau, tau_p = kendalltau(pred_vec, gt_vec)
    rho, rho_p = spearmanr(pred_vec, gt_vec)

    pred_ranks = rates_to_ranking(rates_pred)
    gt_ranks = rates_to_ranking(rates_gt)
    pwa = kendall_pairwise_acc(pred_ranks, gt_ranks)

    tb = top_bottom_discrimination(rates_pred, rates_gt)

    return {
        "n_common": len(common),
        "kendall_tau": round(float(tau), 4),
        "kendall_p": round(float(tau_p), 4),
        "spearman_rho": round(float(rho), 4),
        "spearman_p": round(float(rho_p), 4),
        "pairwise_accuracy": round(pwa, 4),
        **tb,
    }


def main():
    print("="*80, flush=True)
    print("Head-to-Head Ranking: L2b/L2b+ vs L4-text vs Ground Truth", flush=True)
    print("="*80, flush=True)

    # 1. Load L2b/L2b+ rates from Exp B
    l2_rates = load_l2b_plus_rates()
    print("\n--- L2b family rates (Exp B) ---")
    for layer, rates in l2_rates.items():
        ranking = rates_to_ranking(rates)
        print(f"{layer:>10}: {' > '.join(f'{m}({rates[m]:.0%})' for m in ranking)}")

    # 2. Compute L4 rates on Exp B from outputs
    print("\n--- L4-text rates (Exp B, computed live) ---")
    l4_rates = compute_exp_b_l4_rates()
    for scorer, rates in l4_rates.items():
        ranking = rates_to_ranking(rates)
        print(f"{scorer:>22}: {' > '.join(f'{m}({rates[m]:.0%})' for m in ranking)}")

    # 3. Define ground truth = L2b+ (best proxy for "correctness")
    gt_rates = l2_rates["L2b_plus"]

    # 4. Compute ranking correlations
    print("\n" + "="*80)
    print("Correlation with Ground Truth (L2b+)")
    print("="*80)
    print(f"{'Predictor':<25} {'τ':>8} {'τ_p':>8} {'ρ':>8} {'ρ_p':>8} "
          f"{'PWA':>8} {'top1':>6} {'top½':>6}")
    print("-" * 80)

    candidates = {
        "L2a (code present)": l2_rates["L2a"],
        "L2b (code executes)": l2_rates["L2b"],
        "L4 latter-half (S1)": l4_rates["L4_S1_latter_half"],
        "L4 section-aware (S2)": l4_rates["L4_S2_section_aware"],
    }

    correlations = {}
    for name, rates in candidates.items():
        c = ranking_correlation(rates, gt_rates)
        correlations[name] = c
        print(f"{name:<25} {c['kendall_tau']:>8.3f} {c['kendall_p']:>8.3f} "
              f"{c['spearman_rho']:>8.3f} {c['spearman_p']:>8.3f} "
              f"{c['pairwise_accuracy']:>8.3f} {c['top1_match']:>6} {c['top_half_overlap']:>6.2f}")

    # 5. Output as JSON
    out = {
        "ground_truth": "L2b+ v2: code runs AND coefficient matches canonical estimator on realized data within +/-50% (with ES window-aware match for event studies)",
        "n_scenarios": 100,
        "n_models": 7,
        "rates": {
            **{f"L2_{k}": v for k, v in l2_rates.items()},
            **l4_rates,
            "GT_L2b_plus": gt_rates,
        },
        "rankings": {
            **{f"L2_{k}": rates_to_ranking(v) for k, v in l2_rates.items()},
            **{k: rates_to_ranking(v) for k, v in l4_rates.items()},
            "GT_L2b_plus": rates_to_ranking(gt_rates),
        },
        "correlations_with_GT": correlations,
    }

    json_out = RESULTS_DIR / "head_to_head_ranking.json"
    json_out.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {json_out}")

    # 6. Headline conclusion
    print("\n" + "="*80)
    print("HEADLINE CONCLUSION")
    print("="*80)
    l2b_tau = correlations["L2b (code executes)"]["kendall_tau"]
    s1_tau = correlations["L4 latter-half (S1)"]["kendall_tau"]
    s2_tau = correlations["L4 section-aware (S2)"]["kendall_tau"]
    print(f"\nKendall τ with GT (L2b+):")
    print(f"  L2b (execution)     : τ = {l2b_tau:+.3f}")
    print(f"  L4 latter-half (S1) : τ = {s1_tau:+.3f}")
    print(f"  L4 section-aware(S2): τ = {s2_tau:+.3f}")
    print()
    if l2b_tau > max(s1_tau, s2_tau):
        delta = l2b_tau - max(s1_tau, s2_tau)
        print(f"  → L2b ranking is MORE consistent with GT than L4-text "
              f"by Δτ = {delta:+.3f}")
    else:
        print(f"  → L2b ranking is NOT more consistent than L4-text on this metric.")


if __name__ == "__main__":
    main()
