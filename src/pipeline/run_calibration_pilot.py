"""
Calibration Pilot — Self-Assessment on Existing Exp B Outputs
==============================================================

Purpose:
  Test whether LLM self-reported confidence tracks actual correctness
  (L2b+). This is the P0 experiment that decides whether Pillar B
  (Self-Awareness) has a defensible narrative.

Method:
  For Opus's existing Exp B outputs, sample 10 L2b+ failures and
  5 L2b+ passes. For each, retrospectively ask Opus to rate its
  confidence in 3 dimensions:
    - method_confidence: Is the identification method right?
    - specification_confidence: Are the spec details correct?
    - numerical_confidence: Is β̂ within 20% of β*?

  The prompt DOES NOT reveal the ground truth β*. We measure whether
  the model can identify its own failures without external signal.

Output:
  experiments/exp_b/calibration_pilot_results.csv

Success criteria ("confidently wrong" hypothesis holds):
  - Mean numerical_confidence on failures > 0.6
  - Gap between P(high_conf | correct) and P(high_conf | wrong) < 0.2
  - Otherwise reconsider Pillar B framing.

Usage:
  python src/pipeline/run_calibration_pilot.py
  python src/pipeline/run_calibration_pilot.py --n-fail 15 --n-pass 5
  python src/pipeline/run_calibration_pilot.py --model claude-opus-4-7
"""

import argparse
import csv
import json
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.llm_client import call_llm

SCORES_CSV = PROJECT_ROOT / "experiments/exp_b/l2b_plus_scores.csv"
SCEN_DIR = PROJECT_ROOT / "experiments/exp_b/scenarios"
OUT_DIR = PROJECT_ROOT / "experiments/exp_b/outputs"
RESULTS_CSV = PROJECT_ROOT / "experiments/exp_b/calibration_pilot_results.csv"

DEFAULT_MODEL = "claude-opus-4-6"  # Match Paper 1 / Exp B version
SEED = 42


# ── Prompt ────────────────────────────────────────────────────────────

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


# ── Data loading ──────────────────────────────────────────────────────

def load_scored_outputs(model_filter: str = "Opus"):
    """Load per-output L2b+ scores; return list of dicts."""
    with open(SCORES_CSV) as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r["model"] == model_filter]
    return rows


def load_scenario(scenario_id: str) -> dict:
    with open(SCEN_DIR / f"{scenario_id}.json") as f:
        return json.load(f)


def load_llm_output(scenario_id: str, model_slug: str) -> str:
    """Load the original LLM output content."""
    path = OUT_DIR / f"{scenario_id}_{model_slug}.json"
    if not path.exists():
        return ""
    with open(path) as f:
        data = json.load(f)
    return data.get("llm_response", {}).get("content", "")


# ── Pilot sampling ────────────────────────────────────────────────────

def sample_cases(rows: list, n_fail: int, n_pass: int):
    """Sample failures and passes stratified by L2b+ outcome."""
    fails = [r for r in rows if int(r["L2b_plus"]) == 0]
    passes = [r for r in rows if int(r["L2b_plus"]) == 1]

    rng = random.Random(SEED)
    sampled_fails = rng.sample(fails, min(n_fail, len(fails)))
    sampled_passes = rng.sample(passes, min(n_pass, len(passes)))

    return sampled_fails + sampled_passes


# ── Confidence elicitation ────────────────────────────────────────────

def elicit_confidence(row: dict, model: str, model_slug: str) -> dict:
    sid = row["scenario_id"]
    scenario = load_scenario(sid)
    content = load_llm_output(sid, model_slug)
    if not content:
        return {"error": "no llm output"}

    user_prompt = USER_PROMPT_TEMPLATE.format(
        research_question=scenario["research_question"],
        data_description=scenario["data_description"],
        llm_output=content[:6000],  # trim for token budget
    )

    try:
        resp = call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_prompt,
            max_tokens=150,
        )
        raw = resp["content"].strip()
        # Handle markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        parsed = json.loads(raw)
        return {
            "method_confidence": float(parsed.get("method_confidence", -1)),
            "specification_confidence": float(parsed.get("specification_confidence", -1)),
            "numerical_confidence": float(parsed.get("numerical_confidence", -1)),
            "raw": raw,
        }
    except Exception as e:
        return {"error": str(e), "raw": raw if 'raw' in dir() else ""}


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="Model to elicit confidence from")
    parser.add_argument("--n-fail", type=int, default=10,
                        help="Number of L2b+ failure samples")
    parser.add_argument("--n-pass", type=int, default=5,
                        help="Number of L2b+ pass samples")
    args = parser.parse_args()

    # Model slug must match Exp B output filenames
    model_slug = args.model.replace("/", "-").replace(":", "-")
    # Opus short label in l2b_plus_scores.csv is "Opus"
    short_label = "Opus"  # assumes claude-opus-*

    print(f"Loading scored outputs for {short_label}...")
    rows = load_scored_outputs(short_label)
    print(f"  Found {len(rows)} scored outputs.")
    fails = [r for r in rows if int(r["L2b_plus"]) == 0]
    passes = [r for r in rows if int(r["L2b_plus"]) == 1]
    print(f"  {len(fails)} failures, {len(passes)} passes.")

    print(f"\nSampling: {args.n_fail} failures + {args.n_pass} passes...")
    samples = sample_cases(rows, args.n_fail, args.n_pass)

    print(f"\nEliciting self-confidence from {args.model} on {len(samples)} cases:\n")
    results = []
    for i, row in enumerate(samples, 1):
        sid = row["scenario_id"]
        l2b_plus = int(row["L2b_plus"])
        true_effect = row.get("true_effect", "?")
        estimated = row.get("estimated", "?")

        label = "✗ WRONG" if l2b_plus == 0 else "✓ RIGHT"
        print(f"  [{i:>2}/{len(samples)}] {sid:<5} "
              f"{label} true={true_effect} est={estimated}", end=" ")

        conf = elicit_confidence(row, args.model, model_slug)
        if "error" in conf:
            print(f"→ ERROR: {conf['error'][:60]}")
            results.append({**row, "elicit_error": conf["error"]})
            continue

        mc = conf["method_confidence"]
        sc = conf["specification_confidence"]
        nc = conf["numerical_confidence"]
        print(f"→ conf(m,s,n) = ({mc:.2f}, {sc:.2f}, {nc:.2f})")

        results.append({
            "scenario_id": sid,
            "method_family": row.get("method", ""),
            "true_effect": true_effect,
            "estimated": estimated,
            "rel_error": row.get("rel_error", ""),
            "L2b": int(row["L2b"]),
            "L2b_plus": l2b_plus,
            "method_confidence": mc,
            "specification_confidence": sc,
            "numerical_confidence": nc,
        })

    # Save CSV
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    if results:
        fieldnames = list(results[0].keys())
        with open(RESULTS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames,
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSaved → {RESULTS_CSV}")

    # ── Pilot analysis ────────────────────────────────────────────────
    valid = [r for r in results if "elicit_error" not in r]
    failures = [r for r in valid if r["L2b_plus"] == 0]
    passes = [r for r in valid if r["L2b_plus"] == 1]

    def mean(xs):
        xs = [x for x in xs if isinstance(x, (int, float)) and x >= 0]
        return sum(xs) / len(xs) if xs else float("nan")

    print("\n" + "=" * 70)
    print("PILOT DIAGNOSIS — 'Confidently Wrong' Hypothesis Check")
    print("=" * 70)

    if failures:
        print(f"\nOn {len(failures)} L2b+ FAILURES (model got coefficient wrong):")
        print(f"  method_conf        mean = {mean([r['method_confidence'] for r in failures]):.3f}")
        print(f"  specification_conf mean = {mean([r['specification_confidence'] for r in failures]):.3f}")
        print(f"  numerical_conf     mean = {mean([r['numerical_confidence'] for r in failures]):.3f}  ← KEY")

    if passes:
        print(f"\nOn {len(passes)} L2b+ PASSES (model got coefficient right):")
        print(f"  method_conf        mean = {mean([r['method_confidence'] for r in passes]):.3f}")
        print(f"  specification_conf mean = {mean([r['specification_confidence'] for r in passes]):.3f}")
        print(f"  numerical_conf     mean = {mean([r['numerical_confidence'] for r in passes]):.3f}")

    # Gap analysis
    if failures and passes:
        nc_fail = mean([r["numerical_confidence"] for r in failures])
        nc_pass = mean([r["numerical_confidence"] for r in passes])
        gap = nc_pass - nc_fail
        print(f"\nNumerical confidence gap (pass − fail): {gap:+.3f}")

        if gap < 0.15:
            print("  ⚠️  SMALL GAP — model barely distinguishes right from wrong.")
            print("  ✓ Supports 'confidently wrong' hypothesis for Pillar B narrative.")
        elif gap < 0.30:
            print("  → MODEST GAP — model has some self-awareness but limited.")
            print("  → Pillar B narrative holds but less dramatic.")
        else:
            print("  ✗ LARGE GAP — model actually can distinguish right from wrong.")
            print("  ⚠️  'Confidently wrong' hypothesis WEAKENED; reconsider Pillar B.")

    print("\n" + "=" * 70)
    print("If gap < 0.15 → proceed with full calibration experiment (Day 2-4).")
    print("If gap > 0.30 → pause; discuss reframing of Pillar B.")
    print("=" * 70)


if __name__ == "__main__":
    main()
