"""
Full Calibration Experiment — All 100 Scenarios × 6 Models
===========================================================

Scales the pilot (15 samples, Opus only) to the full Exp B:
  100 scenarios × 6 models = 600 retrospective self-assessment queries.

Each LLM is shown its own earlier Exp B analysis and asked to rate
confidence along three dimensions: method / specification / numerical.
Ground truth is NOT revealed.

Outputs
-------
  experiments/exp_b/calibration_scores.csv    — per (scenario, model)
  experiments/exp_b/calibration_summary.json  — per-model ECE + over-confidence

Analysis pipeline
-----------------
  1. ECE (Expected Calibration Error) across 10 confidence bins
  2. Over-confidence asymmetry:
        P(numerical_conf > 0.8 | L2b+ = 0)
        vs
        P(numerical_conf > 0.8 | L2b+ = 1)
  3. Three-dimensional calibration comparison (method/spec/numerical)

Cost estimate
-------------
  Opus:      100 × $0.03 ≈ $3
  Sonnet:    100 × $0.005 ≈ $0.5
  GPT-4o:    100 × $0.005 ≈ $0.5
  o3:        100 × $0.02 ≈ $2
  Kimi:      100 × $0.005 ≈ $0.5
  Gemini:    100 × $0.001 ≈ $0.1
  Total: ~$7-15 (lower than earlier estimate)

Usage
-----
  python3 src/pipeline/run_calibration_full.py
  python3 src/pipeline/run_calibration_full.py --models claude-opus-4-6
  python3 src/pipeline/run_calibration_full.py --skip-cached
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.llm_client import call_llm

SCORES_CSV = PROJECT_ROOT / "experiments/exp_b/l2b_plus_scores_canonical.csv"
SCEN_DIR = PROJECT_ROOT / "experiments/exp_b/scenarios"
OUT_DIR = PROJECT_ROOT / "experiments/exp_b/outputs"
CACHE_DIR = PROJECT_ROOT / "experiments/exp_b/calibration_cache"
RESULTS_CSV = PROJECT_ROOT / "experiments/exp_b/calibration_scores.csv"
RESULTS_JSON = PROJECT_ROOT / "experiments/exp_b/calibration_summary.json"

ALL_MODELS = [
    ("claude-opus-4-6", "Opus"),
    ("claude-sonnet-4-20250514", "Sonnet"),
    ("gpt-4o", "GPT-4o"),
    ("o3", "o3"),
    ("moonshot-v1-128k", "Kimi"),
    ("gemini-2.5-flash", "Gemini"),
    ("gpt-5", "GPT-5"),
]

SYSTEM_PROMPT = """You are reviewing your own earlier empirical analysis. \
Your task is to rate your own confidence in different aspects of that \
analysis, based only on what you can see from the analysis itself.

You will NOT be shown the ground truth. Your confidence ratings should \
reflect your honest belief about how likely each aspect is correct."""


USER_PROMPT_TEMPLATE = """Here is a research scenario and the analysis you produced earlier:

## Research Scenario
{research_question}

## Data Description
{data_description}

## Your Previous Analysis
{llm_output}

---

Please rate your confidence on the following three dimensions, using a \
0-1 scale where 0 = "definitely wrong" and 1 = "definitely correct":

1. **method_confidence**: How confident are you that the identification \
method you chose (DID / Event Study / IV / RDD) is the appropriate one \
for this scenario?

2. **specification_confidence**: How confident are you that the \
specification details (fixed effects, clustering, event windows, \
bandwidth choice, interaction terms, etc.) are correctly implemented?

3. **numerical_confidence**: How confident are you that your estimated \
treatment effect coefficient is within 20% of the true effect? \
(i.e., |β̂ - β_true| / |β_true| < 0.2)

Output STRICTLY a JSON object with EXACTLY these three keys, nothing else:

{{"method_confidence": 0.XX, "specification_confidence": 0.XX, "numerical_confidence": 0.XX}}"""


def load_scored(model_short):
    with open(SCORES_CSV) as f:
        return [r for r in csv.DictReader(f) if r["model"] == model_short]


def load_scenario(sid):
    with open(SCEN_DIR / f"{sid}.json") as f:
        return json.load(f)


def load_llm_output(sid, model_slug):
    path = OUT_DIR / f"{sid}_{model_slug}.json"
    if not path.exists():
        return ""
    return json.load(open(path)).get("llm_response", {}).get("content", "")


def elicit_confidence(scenario, content, model, cache_path, skip_cached):
    if skip_cached and cache_path.exists():
        return json.load(open(cache_path))

    user_prompt = USER_PROMPT_TEMPLATE.format(
        research_question=scenario["research_question"],
        data_description=scenario["data_description"],
        llm_output=content[:6000],
    )

    # Token budget depends on model family:
    # - Reasoning models (o1/o3/o4/gpt-5) burn tokens on internal
    #   chain-of-thought.
    # - Gemini 2.5-flash also has a "thinking" phase + verbose formatting.
    # - Other models (Claude, GPT-4o, Kimi) need only the JSON.
    is_reasoning = any(model.startswith(p) for p in ("o1", "o3", "o4", "gpt-5"))
    is_gemini = "gemini" in model.lower()
    if is_reasoning:
        mt = 4000
    elif is_gemini:
        mt = 2000
    else:
        mt = 500

    try:
        resp = call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_prompt,
            max_tokens=mt,
        )
        raw = resp["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        parsed = json.loads(raw)
        result = {
            "method_confidence": float(parsed.get("method_confidence", -1)),
            "specification_confidence": float(parsed.get("specification_confidence", -1)),
            "numerical_confidence": float(parsed.get("numerical_confidence", -1)),
            "raw": raw,
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(result, f)
        return result
    except Exception as e:
        return {"error": str(e)[:200]}


def compute_ece(conf_values, correct_values, n_bins=10):
    """Expected Calibration Error with equal-width bins."""
    if not conf_values:
        return 0.0
    bins = [(i / n_bins, (i + 1) / n_bins) for i in range(n_bins)]
    total = len(conf_values)
    ece = 0.0
    for lo, hi in bins:
        in_bin = [i for i, c in enumerate(conf_values) if lo <= c < hi or (hi == 1.0 and c == 1.0)]
        if not in_bin:
            continue
        bin_conf = sum(conf_values[i] for i in in_bin) / len(in_bin)
        bin_acc = sum(correct_values[i] for i in in_bin) / len(in_bin)
        weight = len(in_bin) / total
        ece += weight * abs(bin_conf - bin_acc)
    return ece


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=None,
                        help="Restrict to specific model slugs")
    parser.add_argument("--skip-cached", action="store_true", default=True,
                        help="Use cached responses (default)")
    parser.add_argument("--force", action="store_true",
                        help="Ignore cache, re-query")
    parser.add_argument("--rate-limit", type=float, default=0.3)
    parser.add_argument("--shard", type=str, default=None,
                        help="Shard k/N (1-indexed) — every Nth scenario")
    args = parser.parse_args()

    if args.force:
        args.skip_cached = False

    models_to_run = ALL_MODELS
    if args.models:
        models_to_run = [(s, sh) for s, sh in ALL_MODELS if s in args.models]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Running calibration on {len(models_to_run)} models × ~100 scenarios each\n")

    all_results = []
    for model_slug, model_short in models_to_run:
        print(f"=== {model_short} ({model_slug}) ===")
        rows = load_scored(model_short)
        if args.shard:
            k, n = (int(x) for x in args.shard.split("/"))
            rows = [r for i, r in enumerate(rows) if i % n == (k - 1)]
            print(f"  [shard {k}/{n}] taking {len(rows)} scenarios")
        n_cached = 0
        n_fetched = 0
        n_error = 0

        for i, row in enumerate(rows, 1):
            sid = row["scenario_id"]
            l2b_plus = int(row["L2b_plus"])

            # Load scenario + content
            try:
                scen = load_scenario(sid)
                content = load_llm_output(sid, model_slug)
            except Exception as e:
                continue
            if not content:
                continue

            cache_path = CACHE_DIR / f"{sid}_{model_slug}.json"
            if args.skip_cached and cache_path.exists():
                n_cached += 1
                result = json.load(open(cache_path))
            else:
                result = elicit_confidence(scen, content, model_slug,
                                            cache_path, args.skip_cached)
                if "error" not in result:
                    n_fetched += 1
                else:
                    n_error += 1
                time.sleep(args.rate_limit)

            if "error" in result:
                continue

            all_results.append({
                "scenario_id": sid,
                "method_family": row.get("method", ""),
                "model_slug": model_slug,
                "model_short": model_short,
                "true_effect": row.get("true_effect", ""),
                "estimated": row.get("estimated", ""),
                "rel_error": row.get("rel_error", ""),
                "L2b": int(row["L2b"]),
                "L2b_plus": l2b_plus,
                "method_confidence": result["method_confidence"],
                "specification_confidence": result["specification_confidence"],
                "numerical_confidence": result["numerical_confidence"],
            })

            if i % 20 == 0:
                print(f"  [{i}/{len(rows)}]  cached={n_cached}  fetched={n_fetched}  err={n_error}")

        print(f"  Done: {model_short}  cached={n_cached}  fetched={n_fetched}  err={n_error}")

    # Save CSV
    if all_results:
        with open(RESULTS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\nWrote {len(all_results)} rows → {RESULTS_CSV}")

    # Aggregate: per-model ECE + over-confidence ratios
    summary = {}
    for _, model_short in models_to_run:
        model_rows = [r for r in all_results if r["model_short"] == model_short]
        if not model_rows:
            continue

        nc = [r["numerical_confidence"] for r in model_rows]
        mc = [r["method_confidence"] for r in model_rows]
        sc = [r["specification_confidence"] for r in model_rows]
        correct = [r["L2b_plus"] for r in model_rows]

        # ECE
        ece_num = compute_ece(nc, correct, n_bins=10)
        ece_meth = compute_ece(mc, correct, n_bins=10)
        ece_spec = compute_ece(sc, correct, n_bins=10)

        # Over-confidence ratios
        high_conf_wrong = sum(1 for i, c in enumerate(nc) if c > 0.8 and correct[i] == 0)
        high_conf_right = sum(1 for i, c in enumerate(nc) if c > 0.8 and correct[i] == 1)
        n_wrong = sum(1 for c in correct if c == 0)
        n_right = sum(1 for c in correct if c == 1)

        p_hi_given_wrong = high_conf_wrong / max(n_wrong, 1)
        p_hi_given_right = high_conf_right / max(n_right, 1)

        # Mean confidence conditional on outcome
        mean_nc_wrong = sum(nc[i] for i in range(len(nc)) if correct[i] == 0) / max(n_wrong, 1)
        mean_nc_right = sum(nc[i] for i in range(len(nc)) if correct[i] == 1) / max(n_right, 1)

        summary[model_short] = {
            "n": len(model_rows),
            "L2b_plus_pass_rate": round(sum(correct) / len(correct), 4),
            "ECE_numerical": round(ece_num, 4),
            "ECE_method": round(ece_meth, 4),
            "ECE_specification": round(ece_spec, 4),
            "mean_numerical_conf_all": round(sum(nc) / len(nc), 4),
            "mean_numerical_conf_wrong": round(mean_nc_wrong, 4),
            "mean_numerical_conf_right": round(mean_nc_right, 4),
            "confidence_gap_right_minus_wrong": round(mean_nc_right - mean_nc_wrong, 4),
            "P_high_conf_given_wrong": round(p_hi_given_wrong, 4),
            "P_high_conf_given_right": round(p_hi_given_right, 4),
        }

    with open(RESULTS_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote: {RESULTS_JSON}")

    # Print summary
    print("\n" + "=" * 90)
    print("CALIBRATION SUMMARY")
    print("=" * 90)
    print(f"{'Model':<10} {'n':>4} {'L2b+':>6} {'ECE_num':>8} {'ECE_meth':>9} "
          f"{'gap':>6} {'P(hi|W)':>8} {'P(hi|R)':>8}")
    print("-" * 90)
    for _, m in [(s, sh) for s, sh in ALL_MODELS]:
        s = summary.get(m)
        if not s:
            continue
        print(f"{m:<10} {s['n']:>4} {s['L2b_plus_pass_rate']:>6.2f} "
              f"{s['ECE_numerical']:>8.3f} {s['ECE_method']:>9.3f} "
              f"{s['confidence_gap_right_minus_wrong']:>+6.3f} "
              f"{s['P_high_conf_given_wrong']:>8.3f} "
              f"{s['P_high_conf_given_right']:>8.3f}")
    print()
    print("  gap       = mean_conf(right) − mean_conf(wrong). Small gap → poor calibration.")
    print("  P(hi|W)   = P(conf>0.8 | L2b+ = 0).  High → 'confident when wrong'.")
    print("  P(hi|R)   = P(conf>0.8 | L2b+ = 1).  Similar values → model can't distinguish.")


if __name__ == "__main__":
    main()
