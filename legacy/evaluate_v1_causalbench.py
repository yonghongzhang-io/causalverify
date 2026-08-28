#!/usr/bin/env python3
"""
evaluate.py — CAUSAL-BENCH one-command evaluation
==================================================
Evaluate any model's causal research competence against the
CAUSAL-BENCH ground truth. This is the official evaluation
script for the NeurIPS 2026 Evaluations & Datasets Track.

Usage:
  # Evaluate a single model output file
  python evaluate.py --output experiments/exp_a/outputs/paper_01_o3.json

  # Evaluate all outputs for a model
  python evaluate.py --model o3

  # Evaluate all outputs in a directory
  python evaluate.py --output-dir experiments/exp_a/outputs/

  # Full benchmark evaluation with bootstrap CI
  python evaluate.py --model o3 --bootstrap --n-boot 1000

Output format (JSON):
  {
    "model": "o3",
    "n_papers": 57,
    "L1": {"pass": 57, "total": 57, "rate": 1.0, "ci_95": [0.94, 1.0]},
    "L3": {"pass": 48, "total": 57, "rate": 0.84, "ci_95": [0.73, 0.93]},
    "L4": {"pass": 42, "total": 57, "rate": 0.74, "ci_95": [0.61, 0.85]},
    "by_method": {...},
    "by_difficulty": {...},
    "by_domain": {...}
  }
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# ── Paths ────────────────────────────────────────────────

PAPERS_DIR = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/exp_a/outputs")

# ── Strategy detection keywords ──────────────────────────

STRATEGY_KEYWORDS = {
    "DID": [
        "difference-in-differences", "diff-in-diff", "dif-in-dif",
        "differences-in-differences", "double difference",
        "staggered did", "staggered diff", "twfe",
        "two-way fixed effect", "canonical did",
    ],
    "EVENT_STUDY": [
        "event study", "event-study", "cumulative abnormal return",
        "announcement return", "abnormal return", "car ",
    ],
    "IV": [
        "instrumental variable", "two-stage least squares", "2sls",
        "iv approach", "iv estimat", "instrument for",
    ],
    "RDD": [
        "regression discontinuity", "rd design", "rdrobust",
        "sharp cutoff", "running variable", "fuzzy rd",
        "discontinuity design",
    ],
}

DIRECTION_POS = [
    "positive", "increase", "higher", "gain", "improve",
    "larger", "upward", "beneficial", "raises",
]
DIRECTION_NEG = [
    "negative", "decrease", "lower", "decline", "worse",
    "reduces", "destroy", "underperform", "fall", "drop",
]


# ── Scoring functions ────────────────────────────────────

def detect_primary_strategy(text: str) -> str:
    """Detect the primary identification strategy from model output.

    Uses weighted scoring: occurrences in strategy section (Section 1)
    count 3x; first-mention position is a tiebreaker, not the sole signal.
    This avoids the 'first-mention bias' where a passing reference to
    another method before the primary one causes mis-classification.
    """
    s = text.lower()

    # Try to isolate Section 1 (Identification Strategy) — highest signal
    sec1_start = -1
    for marker in ["1. identification", "## 1", "identification strategy"]:
        pos = s.find(marker)
        if pos >= 0 and (sec1_start < 0 or pos < sec1_start):
            sec1_start = pos
    # Section 1 window: from marker to +1500 chars (or next ## section)
    if sec1_start >= 0:
        sec1_end = sec1_start + 1500
        for next_sec in ["## 2", "2. treatment", "## 3", "3. key"]:
            ns = s.find(next_sec, sec1_start + 20)
            if ns > 0:
                sec1_end = min(sec1_end, ns)
        sec1 = s[sec1_start:sec1_end]
    else:
        sec1 = s[:1500]  # fallback: first 1500 chars

    full_window = s[:4000]  # broader window for count-based scoring

    scores = {}
    for method, keywords in STRATEGY_KEYWORDS.items():
        # Count in strategy section (weight=3) + full window (weight=1)
        sec1_count = sum(sec1.count(kw) for kw in keywords)
        full_count = sum(full_window.count(kw) for kw in keywords)
        score = sec1_count * 3 + full_count

        # First-position tiebreaker (small bonus, max 2 points)
        first_pos = 9999
        for kw in keywords:
            idx = full_window.find(kw)
            if idx >= 0:
                first_pos = min(first_pos, idx)
        if first_pos < 9999:
            score += max(0, 2 - first_pos / 2000)  # 0-2 bonus for early mention

        if score > 0:
            scores[method] = score

    if not scores:
        return "OTHER"

    # Disambiguation: modern DiD papers routinely include event-study plots
    # as diagnostics (parallel-trends testing).  When the text explicitly
    # names "difference-in-differences" (or variants) in Section 1, the
    # event-study mentions are likely sub-components → discount EVENT_STUDY.
    # We only apply this when core DID terms appear (not just "parallel trend").
    did_core = ["difference-in-differences", "diff-in-diff", "dif-in-dif",
                "differences-in-differences", "double difference"]
    if "DID" in scores and "EVENT_STUDY" in scores:
        has_core_did = any(sec1.count(kw) > 0 for kw in did_core)
        if has_core_did:
            scores["EVENT_STUDY"] *= 0.5

    return max(scores, key=scores.get)


def detect_direction(text: str, gt_direction: str) -> float:
    """Score direction match (0, 0.5, or 1) using keyword analysis.

    Searches multiple candidate regions in priority order:
    1. Section 6 / "Expected Results" (most reliable)
    2. Section 7 / "Validity Checklist" preamble (sometimes has direction)
    3. Last substantive paragraph before any checklist
    Falls back to last 800 chars only if no section marker found.
    """
    tl = text.lower()

    # Try to find the Expected Results section specifically
    seg = ""
    for marker in ["6. expected", "## 6", "expected results",
                    "6. prior", "prior expectation"]:
        pos = tl.find(marker)
        if pos >= 0:
            # Read from marker to next section or end
            end = pos + 1200
            for stop in ["## 7", "7. validity", "validity checklist",
                         "self-assessment", "c1:", "c1 "]:
                spos = tl.find(stop, pos + 20)
                if spos > 0:
                    end = min(end, spos)
            seg = tl[pos:end]
            break

    if not seg:
        # Fallback: find last substantive paragraph (skip checklist)
        # Remove trailing checklist if present
        checklist_start = len(tl)
        for ck in ["validity checklist", "self-assessment",
                    "c1:", "## 7", "7. validity"]:
            cp = tl.rfind(ck)
            if cp > len(tl) // 2:  # only if in second half
                checklist_start = min(checklist_start, cp)
        seg = tl[max(0, checklist_start - 800):checklist_start]

    if not seg:
        seg = tl[-800:]

    pos_count = sum(seg.count(kw) for kw in DIRECTION_POS)
    neg_count = sum(seg.count(kw) for kw in DIRECTION_NEG)

    if gt_direction == "positive":
        if pos_count > neg_count + 1:
            return 1.0
        elif pos_count > neg_count:
            return 0.5
        return 0.0
    elif gt_direction == "negative":
        if neg_count > pos_count + 1:
            return 1.0
        elif neg_count > pos_count:
            return 0.5
        return 0.0
    return 0.0


def score_output(paper: dict, output: dict) -> dict:
    """Score a single model output against ground truth."""
    gt = paper.get("ground_truth", {})
    gt_method = paper.get("method_family", "")
    gt_direction = gt.get("conclusion_direction", "")

    content = output.get("llm_response", {}).get("content", "")

    # L1: Task completion (non-empty output)
    l1 = len(content.strip()) > 50

    # L2: R code present
    l2 = any(kw in content.lower() for kw in [
        "library(", "install.packages", "lm(", "felm(",
        "feols(", "rdrobust(", "ivreg(", "<-", "data.frame",
    ])

    # L3: Strategy identification
    detected = detect_primary_strategy(content)
    # Map ground truth to detection format
    gt_short = {"DID": "DID", "EVENT_STUDY": "EVENT_STUDY",
                "IV": "IV", "RDD": "RDD"}.get(gt_method, gt_method)
    # Allow hybrid papers to accept multiple methods
    accepted = paper.get("method_family_accepted", [gt_short])
    l3 = detected in accepted

    # L4: Direction match
    l4_score = detect_direction(content, gt_direction)
    l4 = l4_score >= 0.75  # pass threshold

    # Failure classification
    failures = []
    if not l3:
        failures.append("IH")
    if l1 and l2 and not l3:
        if any(kw in content.lower() for kw in STRATEGY_KEYWORDS.get(gt_short, [])):
            failures = ["ME"]  # mentioned correct strategy but didn't lead with it
    if not l4:
        failures.append("NF")

    return {
        "paper_id": paper["paper_id"],
        "method": gt_method,
        "difficulty": paper.get("difficulty", ""),
        "domain": paper.get("domain", "finance"),
        "gt_direction": gt_direction,
        "detected_strategy": detected,
        "L1": l1, "L2": l2, "L3": l3, "L4": l4,
        "l4_score": l4_score,
        "failures": failures,
    }


# ── Aggregation ──────────────────────────────────────────

def aggregate_scores(scores: list, n_boot: int = 0) -> dict:
    """Aggregate per-paper scores into summary statistics."""
    n = len(scores)
    if n == 0:
        return {"error": "no scores to aggregate"}

    result = {"n_papers": n}

    for layer in ["L1", "L2", "L3", "L4"]:
        passes = sum(1 for s in scores if s[layer])
        rate = passes / n
        entry = {"pass": passes, "total": n, "rate": round(rate, 4)}

        if n_boot > 0:
            boot_rates = []
            arr = np.array([s[layer] for s in scores], dtype=float)
            rng = np.random.default_rng(42)
            for _ in range(n_boot):
                sample = rng.choice(arr, size=n, replace=True)
                boot_rates.append(sample.mean())
            ci_lo = float(np.percentile(boot_rates, 2.5))
            ci_hi = float(np.percentile(boot_rates, 97.5))
            entry["ci_95"] = [round(ci_lo, 4), round(ci_hi, 4)]

        result[layer] = entry

    # Breakdowns
    for dim in ["method", "difficulty", "domain"]:
        grouped = defaultdict(list)
        for s in scores:
            grouped[s[dim]].append(s)
        breakdown = {}
        for key, group in sorted(grouped.items()):
            gn = len(group)
            breakdown[key] = {
                "n": gn,
                "L3_pass": sum(1 for s in group if s["L3"]),
                "L3_rate": round(sum(1 for s in group if s["L3"]) / gn, 4),
                "L4_pass": sum(1 for s in group if s["L4"]),
                "L4_rate": round(sum(1 for s in group if s["L4"]) / gn, 4),
            }
        result[f"by_{dim}"] = breakdown

    # Failure type distribution
    failure_counts = defaultdict(int)
    for s in scores:
        for f in s["failures"]:
            failure_counts[f] += 1
    result["failure_types"] = dict(failure_counts)

    return result


# ── Main evaluation ──────────────────────────────────────

def evaluate_model(model_slug: str, n_boot: int = 0,
                   core_only: bool = False) -> dict:
    """Evaluate all outputs for a given model."""
    # Load all papers
    papers = {}
    for pf in sorted(PAPERS_DIR.glob("paper_*.json")):
        d = json.load(open(pf))
        if core_only:
            pid_num = int(d["paper_id"].replace("paper_", ""))
            if pid_num > 57:
                continue
        papers[d["paper_id"]] = d

    # Find outputs for this model
    scores = []
    for pid, paper in sorted(papers.items()):
        out_file = OUTPUTS_DIR / f"{pid}_{model_slug}.json"
        if not out_file.exists():
            continue
        output = json.load(open(out_file))
        score = score_output(paper, output)
        scores.append(score)

    if not scores:
        return {"error": f"No outputs found for model '{model_slug}'"}

    result = aggregate_scores(scores, n_boot=n_boot)
    result["model"] = model_slug
    return result


def evaluate_single(output_path: str) -> dict:
    """Evaluate a single output file."""
    out = json.load(open(output_path))
    pid = out.get("paper_id", "")

    # Find the corresponding paper
    matches = list(PAPERS_DIR.glob(f"{pid}*.json"))
    if not matches:
        return {"error": f"Paper not found for {pid}"}

    paper = json.load(open(matches[0]))
    return score_output(paper, out)


def evaluate_directory(output_dir: str, n_boot: int = 0) -> dict:
    """Evaluate all outputs in a directory, grouped by model."""
    papers = {}
    for pf in sorted(PAPERS_DIR.glob("paper_*.json")):
        d = json.load(open(pf))
        papers[d["paper_id"]] = d

    # Group outputs by model
    model_scores = defaultdict(list)
    for out_file in sorted(Path(output_dir).glob("paper_*.json")):
        out = json.load(open(out_file))
        pid = out.get("paper_id", "")
        model = out.get("model", "unknown")
        if pid not in papers:
            continue
        score = score_output(papers[pid], out)
        model_scores[model].append(score)

    results = {}
    for model, scores in sorted(model_scores.items()):
        result = aggregate_scores(scores, n_boot=n_boot)
        result["model"] = model
        results[model] = result

    return results


# ── CLI ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CAUSAL-BENCH evaluation script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--output", type=str, help="Path to a single output JSON file")
    parser.add_argument("--model", type=str, help="Model slug to evaluate (e.g., 'o3', 'claude-opus-4-6')")
    parser.add_argument("--output-dir", type=str, help="Directory containing output JSON files")
    parser.add_argument("--bootstrap", action="store_true", help="Compute bootstrap 95%% CI")
    parser.add_argument("--n-boot", type=int, default=1000, help="Number of bootstrap resamples (default: 1000)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON (default: pretty-print)")
    parser.add_argument("--mcnemar", action="store_true", help="Run pairwise McNemar tests (L3 & L4)")
    parser.add_argument("--core-only", action="store_true",
                        help="Restrict to core set (paper_01..paper_57)")
    args = parser.parse_args()

    n_boot = args.n_boot if args.bootstrap else 0

    if args.mcnemar:
        # Load all papers and score all models
        papers = {}
        for pf in sorted(PAPERS_DIR.glob("paper_*.json")):
            d = json.load(open(pf))
            papers[d["paper_id"]] = d

        model_scores = defaultdict(list)
        for out_file in sorted(OUTPUTS_DIR.glob("paper_*.json")):
            out = json.load(open(out_file))
            pid = out.get("paper_id", "")
            model = out.get("model", "unknown")
            if pid not in papers:
                continue
            model_scores[model].append(score_output(papers[pid], out))

        for layer in ["L3", "L4"]:
            print(f"\n{'='*60}")
            print(f"  McNemar Pairwise Tests — {layer}")
            print(f"{'='*60}")
            results = mcnemar_pairwise(dict(model_scores), layer)
            print(f"  {'Model A':<28} {'Model B':<28} b    c    p-value")
            print(f"  {'-'*80}")
            for (m1, m2), d in sorted(results.items(), key=lambda x: x[1]["p_value"]):
                sig = d["sig"]
                print(f"  {m1:<28} {m2:<28} {d['b']:<4} {d['c']:<4} {d['p_value']:.4f} {sig}")
        return

    core_only = getattr(args, "core_only", False)

    if args.output:
        result = evaluate_single(args.output)
    elif args.model:
        result = evaluate_model(args.model, n_boot=n_boot, core_only=core_only)
    elif args.output_dir:
        result = evaluate_directory(args.output_dir, n_boot=n_boot)
    else:
        # Default: evaluate all models
        result = evaluate_directory(str(OUTPUTS_DIR), n_boot=n_boot)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Pretty-print
        if isinstance(result, dict) and "model" in result:
            _print_model_result(result)
        elif isinstance(result, dict):
            for model, res in result.items():
                if isinstance(res, dict) and "model" in res:
                    _print_model_result(res)
                    print()
        else:
            print(json.dumps(result, indent=2))


def mcnemar_pairwise(model_scores: dict, layer: str = "L3") -> dict:
    """Compute pairwise McNemar exact tests between all model pairs.

    Returns dict of {(modelA, modelB): {"b": int, "c": int, "p_value": float}}
    where b = A_pass & B_fail, c = A_fail & B_pass.
    """
    try:
        from scipy.stats import binomtest as _scipy_binomtest
        def _binom_p(k, n): return _scipy_binomtest(k, n, 0.5, alternative='two-sided').pvalue
    except ImportError:
        from scipy.stats import binom_test as _legacy_binom
        def _binom_p(k, n): return _legacy_binom(k, n, 0.5)
    from itertools import combinations

    models = sorted(model_scores.keys())
    results = {}

    for m1, m2 in combinations(models, 2):
        s1 = {s["paper_id"]: s[layer] for s in model_scores[m1]}
        s2 = {s["paper_id"]: s[layer] for s in model_scores[m2]}
        common = set(s1.keys()) & set(s2.keys())

        b = sum(1 for pid in common if s1[pid] and not s2[pid])  # m1 pass, m2 fail
        c = sum(1 for pid in common if not s1[pid] and s2[pid])  # m1 fail, m2 pass

        if b + c == 0:
            p = 1.0
        else:
            p = _binom_p(min(b, c), b + c)

        results[(m1, m2)] = {"b": b, "c": c, "n_discord": b + c,
                             "p_value": round(p, 4),
                             "sig": "*" if p < 0.05 else ""}

    return results


def _print_model_result(r: dict):
    """Pretty-print a single model's evaluation result."""
    print(f"\n{'='*55}")
    print(f"  CAUSAL-BENCH Evaluation: {r.get('model', '?')}")
    print(f"  Papers evaluated: {r.get('n_papers', '?')}")
    print(f"{'='*55}")

    for layer in ["L1", "L2", "L3", "L4"]:
        if layer not in r:
            continue
        d = r[layer]
        ci = f"  CI: [{d['ci_95'][0]:.2f}, {d['ci_95'][1]:.2f}]" if "ci_95" in d else ""
        bar = "█" * int(d["rate"] * 20) + "░" * (20 - int(d["rate"] * 20))
        print(f"  {layer}: {d['pass']:>3}/{d['total']}  "
              f"({d['rate']:.1%})  {bar}{ci}")

    if "failure_types" in r:
        ft = r["failure_types"]
        if ft:
            print(f"\n  Failures: " + ", ".join(f"{k}={v}" for k, v in ft.items()))

    if "by_method" in r:
        print(f"\n  By method:")
        for m, d in r["by_method"].items():
            print(f"    {m:<14} L3={d['L3_pass']}/{d['n']} ({d['L3_rate']:.0%})"
                  f"  L4={d['L4_pass']}/{d['n']} ({d['L4_rate']:.0%})")

    if "by_domain" in r:
        print(f"\n  By domain:")
        for m, d in r["by_domain"].items():
            print(f"    {m:<14} L3={d['L3_pass']}/{d['n']} ({d['L3_rate']:.0%})"
                  f"  L4={d['L4_pass']}/{d['n']} ({d['L4_rate']:.0%})")


if __name__ == "__main__":
    main()
