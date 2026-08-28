"""
Re-compute Exp B L3 (method identification) rates on the clean
79-scenario subset (100 total minus 21 critical-leak scenarios).

Context (Issue C2 from Stage 0 Audit):
  Leakage Scanner (src/agents/leakage_scanner.py) found 21 of 100
  Exp B scenarios whose research_question / data_description literally
  mentions the method family name. L3 pass rates on these scenarios
  are artificially inflated — the LLM is not "identifying" the method,
  it is echoing a phrase given to it in the prompt.

This script:
  1. Reads audit/leakage_scan.json to get the 21 CRITICAL leak scenario IDs
  2. Reads each LLM output in experiments/exp_b/outputs/
  3. Applies the L3 (method identification) keyword scorer (same algorithm
     as auto_score_exp_a.py's detect_method)
  4. Reports per-model L3 pass rate on:
     (a) all 100 scenarios (for comparison with pre-fix)
     (b) clean 79-scenario subset (leak-free)
  5. Writes audit/l3_clean_subset_rates.json + .md

Output informs:
  - Paper §5 (method-level findings)
  - Paper §5 (L3 fragility discussion)
  - Paper Limitations disclosure
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCEN_DIR = PROJECT_ROOT / "experiments/exp_b/scenarios"
OUT_DIR = PROJECT_ROOT / "experiments/exp_b/outputs"
LEAK_JSON = PROJECT_ROOT / "audit/leakage_scan.json"
OUT_JSON = PROJECT_ROOT / "audit/l3_clean_subset_rates.json"
OUT_MD = PROJECT_ROOT / "audit/l3_clean_subset_rates.md"

MODEL_SLUGS = {
    "moonshot-v1-128k": "Kimi",
    "claude-sonnet-4-20250514": "Sonnet",
    "gpt-4o": "GPT-4o",
    "o3": "o3",
    "claude-opus-4-6": "Opus",
    "gemini-2.5-flash": "Gemini",
}

# Keywords (copy of STRATEGY_KEYWORDS from auto_score_exp_a.py)
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


def detect_method(text: str) -> str | None:
    """Same section-aware weighted scoring as auto_score_exp_a.py."""
    s = text.lower()
    # Isolate Section 1 window
    sec1_start = -1
    for marker in ["1. identification", "## 1", "identification strategy"]:
        pos = s.find(marker)
        if pos >= 0 and (sec1_start < 0 or pos < sec1_start):
            sec1_start = pos
    if sec1_start >= 0:
        sec1_end = sec1_start + 1500
        for next_sec in ["## 2", "2. treatment", "## 3", "3. key"]:
            ns = s.find(next_sec, sec1_start + 20)
            if ns > 0:
                sec1_end = min(sec1_end, ns)
        sec1 = s[sec1_start:sec1_end]
    else:
        sec1 = s[:1500]
    full_window = s[:4000]

    scores = {}
    for method, keywords in STRATEGY_KEYWORDS.items():
        sec1_count = sum(sec1.count(kw) for kw in keywords)
        full_count = sum(full_window.count(kw) for kw in keywords)
        score = sec1_count * 3 + full_count
        first_pos = 9999
        for kw in keywords:
            idx = full_window.find(kw)
            if idx >= 0:
                first_pos = min(first_pos, idx)
        if first_pos < 9999:
            score += max(0, 2 - first_pos / 2000)
        if score > 0:
            scores[method] = score

    if not scores:
        return None

    # DID/ES disambiguation
    did_core = ["difference-in-differences", "diff-in-diff", "dif-in-dif",
                "differences-in-differences", "double difference"]
    if "DID" in scores and "EVENT_STUDY" in scores:
        has_core_did = any(sec1.count(kw) > 0 for kw in did_core)
        if has_core_did:
            scores["EVENT_STUDY"] *= 0.5

    return max(scores, key=scores.get)


def main():
    # Load leakage scan to get the 21 critical-leak scenarios
    leak_data = json.load(open(LEAK_JSON))
    leaking_ids = {f["scenario_id"] for f in leak_data["findings"]
                    if f["has_critical_leak"]}
    print(f"Leaking scenarios to exclude: {len(leaking_ids)}")
    print(f"  IDs: {sorted(leaking_ids, key=lambda s: int(s[1:]))}\n")

    # Load all scenarios to get ground-truth method
    true_method = {}
    for sp in SCEN_DIR.glob("s*.json"):
        d = json.load(open(sp))
        true_method[d["scenario_id"]] = d["method_family"]

    # Score each (scenario, model) output
    records = []
    for out_file in OUT_DIR.glob("s*.json"):
        # Parse scenario_id and model from filename
        stem = out_file.stem  # e.g. "s01_claude-opus-4-6"
        # Match model slug
        model_slug = None
        for slug in MODEL_SLUGS:
            if stem.endswith(f"_{slug}"):
                model_slug = slug
                sid = stem[:-(len(slug) + 1)]
                break
        if model_slug is None:
            continue

        try:
            data = json.load(open(out_file))
            content = data.get("llm_response", {}).get("content", "")
        except Exception:
            continue

        detected = detect_method(content)
        gt = true_method.get(sid)
        records.append({
            "scenario_id": sid,
            "method_family": gt,
            "model_slug": model_slug,
            "model_short": MODEL_SLUGS[model_slug],
            "detected": detected,
            "correct": (detected == gt),
            "is_leaking": sid in leaking_ids,
        })

    # Aggregate: per-model L3 rate on ALL vs CLEAN subset
    by_model_all = defaultdict(lambda: {"total": 0, "correct": 0})
    by_model_clean = defaultdict(lambda: {"total": 0, "correct": 0})
    by_model_method_all = defaultdict(lambda: {"total": 0, "correct": 0})
    by_model_method_clean = defaultdict(lambda: {"total": 0, "correct": 0})

    for r in records:
        m = r["model_short"]
        method = r["method_family"]
        by_model_all[m]["total"] += 1
        if r["correct"]:
            by_model_all[m]["correct"] += 1
        by_model_method_all[(m, method)]["total"] += 1
        if r["correct"]:
            by_model_method_all[(m, method)]["correct"] += 1

        if not r["is_leaking"]:
            by_model_clean[m]["total"] += 1
            if r["correct"]:
                by_model_clean[m]["correct"] += 1
            by_model_method_clean[(m, method)]["total"] += 1
            if r["correct"]:
                by_model_method_clean[(m, method)]["correct"] += 1

    # Output
    summary = {
        "n_leaking_excluded": len(leaking_ids),
        "leaking_scenario_ids": sorted(leaking_ids, key=lambda s: int(s[1:])),
        "by_model_all_100": {m: {"rate": round(s["correct"] / max(s["total"], 1), 4),
                                   **s}
                              for m, s in by_model_all.items()},
        "by_model_clean_79": {m: {"rate": round(s["correct"] / max(s["total"], 1), 4),
                                    **s}
                               for m, s in by_model_clean.items()},
        "by_model_method_all": {
            f"{m}__{method}": {"rate": round(s["correct"] / max(s["total"], 1), 4), **s}
            for (m, method), s in by_model_method_all.items()
        },
        "by_model_method_clean": {
            f"{m}__{method}": {"rate": round(s["correct"] / max(s["total"], 1), 4), **s}
            for (m, method), s in by_model_method_clean.items()
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(summary, f, indent=2)

    # Markdown
    lines = [
        "# L3 Rate on Clean Subset (Leaks Excluded)\n",
        f"Recomputed Exp B L3 (method identification) rates after excluding "
        f"the {len(leaking_ids)} scenarios with critical method-name leakage.\n",
        "## Per-model comparison: all 100 vs clean 79\n",
        "| Model | L3 (all 100) | L3 (clean 79) | Δ |",
        "|---|:---:|:---:|:---:|",
    ]
    model_order = ["Opus", "Sonnet", "GPT-4o", "o3", "Kimi", "Gemini"]
    for m in model_order:
        a = by_model_all.get(m)
        c = by_model_clean.get(m)
        if not a or not c:
            continue
        r_all = a["correct"] / max(a["total"], 1)
        r_clean = c["correct"] / max(c["total"], 1)
        delta = r_clean - r_all
        lines.append(f"| {m} | {r_all:.1%} ({a['correct']}/{a['total']}) | "
                     f"{r_clean:.1%} ({c['correct']}/{c['total']}) | "
                     f"{delta:+.1%} |")

    lines.append("\n## Per-method L3 on clean 79-scenario subset\n")
    lines.append("| Model | DID | EVENT_STUDY | IV | RDD |")
    lines.append("|---|:---:|:---:|:---:|:---:|")
    for m in model_order:
        row = [f"**{m}**"]
        for method in ["DID", "EVENT_STUDY", "IV", "RDD"]:
            s = by_model_method_clean.get((m, method))
            if s and s["total"] > 0:
                row.append(f"{s['correct']/s['total']:.0%} ({s['correct']}/{s['total']})")
            else:
                row.append("–")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("\n## Interpretation\n")
    # Identify the model with biggest drop
    biggest_drop_model = None
    biggest_drop = 0
    for m in model_order:
        a = by_model_all.get(m)
        c = by_model_clean.get(m)
        if not a or not c:
            continue
        delta = (c["correct"] / max(c["total"], 1)) - (a["correct"] / max(a["total"], 1))
        if delta < biggest_drop:
            biggest_drop = delta
            biggest_drop_model = m

    if biggest_drop_model and biggest_drop < -0.05:
        lines.append(f"**{biggest_drop_model} had the largest L3 drop ({biggest_drop:+.1%})** "
                     "when leaking scenarios are excluded, confirming that method-name "
                     "leakage was materially inflating its method-identification rate. "
                     "Paper §5 should report the clean-subset rates as primary.")
    else:
        lines.append("L3 rates are largely unchanged by excluding leaking scenarios. "
                     "This suggests the leakage was not a dominant driver of L3 performance, "
                     "though the clean subset remains the more defensible comparison.")

    OUT_MD.write_text("\n".join(lines))

    print("Per-model L3 rates:\n")
    print(f"{'Model':<10} {'all_100':>15} {'clean_79':>15} {'Δ':>10}")
    print("-" * 55)
    for m in model_order:
        a = by_model_all.get(m)
        c = by_model_clean.get(m)
        if not a or not c:
            continue
        r_all = a["correct"] / max(a["total"], 1)
        r_clean = c["correct"] / max(c["total"], 1)
        print(f"{m:<10} {a['correct']:>3}/{a['total']:<3} ({r_all:.0%})   "
              f"{c['correct']:>3}/{c['total']:<3} ({r_clean:.0%})   {r_clean-r_all:+.1%}")

    print(f"\nWrote: {OUT_JSON}")
    print(f"Wrote: {OUT_MD}")


if __name__ == "__main__":
    main()
