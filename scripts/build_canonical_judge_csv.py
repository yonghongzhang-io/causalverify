#!/usr/bin/env python3
"""Build canonical_judge.csv by joining canonical.csv with the judge cache.

The original judge.csv was produced by an earlier version of
l2b_llm_judge_extract.py whose CSV-writing block has since been removed.
This script reproduces that merge so the downstream ES-aware step works
when a new model (Llama) is added to canonical.csv.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "experiments/exp_b/l2b_plus_scores_canonical.csv"
CACHE = ROOT / "audit/l2b_judge_cache.json"
OUT = ROOT / "experiments/exp_b/l2b_plus_scores_canonical_judge.csv"

EXTRA_COLS = ["regex_estimated", "regex_l2b_plus",
              "judge_effect", "judge_rationale",
              "rel_error_judge", "L2b_plus_judge"]


def main():
    cache = json.load(open(CACHE))
    rows = list(csv.DictReader(open(CANON)))
    print(f"canonical rows: {len(rows)}")
    print(f"cache entries: {len(cache)}")

    fieldnames = list(rows[0].keys()) + [c for c in EXTRA_COLS if c not in rows[0]]
    out_rows = []
    for r in rows:
        key = f"{r['scenario_id']}__{r['model_slug']}"
        c = cache.get(key, {})
        rr = dict(r)
        # regex columns
        rr["regex_estimated"] = r.get("estimated", "") or ""
        rr["regex_l2b_plus"] = r.get("L2b_plus", "0") or "0"
        # judge columns
        je = c.get("judge_effect") if isinstance(c, dict) else None
        rr["judge_effect"] = "" if je is None else f"{je:.4f}"
        rr["judge_rationale"] = c.get("judge_rationale", "") if isinstance(c, dict) else ""
        rel = c.get("rel_error_judge") if isinstance(c, dict) else None
        rr["rel_error_judge"] = "" if rel is None else rel
        l2bj = c.get("l2b_plus_new", 0) if isinstance(c, dict) else 0
        rr["L2b_plus_judge"] = int(l2bj or 0)
        out_rows.append(rr)

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {len(out_rows)} rows -> {OUT}")

    # Per-model judge L2b+ summary
    from collections import defaultdict
    by = defaultdict(lambda: {"n":0, "L2b":0, "L2b_plus_regex":0, "L2b_plus_judge":0})
    for r in out_rows:
        m = r["model"]
        by[m]["n"] += 1
        by[m]["L2b"] += int(r.get("L2b","0") or 0)
        by[m]["L2b_plus_regex"] += int(r.get("regex_l2b_plus","0") or 0)
        by[m]["L2b_plus_judge"] += int(r.get("L2b_plus_judge","0") or 0)
    print()
    print(f"{'Model':<10} {'L2b':>7} {'regex L2b+':>11} {'judge L2b+':>11}")
    print("-" * 50)
    for m in ["Opus","GPT-5","GPT-4o","Sonnet","o3","Gemini","Kimi","Llama"]:
        if m in by:
            v = by[m]
            print(f"{m:<10} {v['L2b']:>3}/{v['n']:<3} {v['L2b_plus_regex']:>5}/{v['n']:<3}    {v['L2b_plus_judge']:>5}/{v['n']:<3}")


if __name__ == "__main__":
    main()
