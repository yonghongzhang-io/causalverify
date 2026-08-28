#!/usr/bin/env python3
"""ES-aware re-scoring of L2b+ that accepts any valid event-window choice.

Why
---
Event-study canonicals in audit/dgp_verification.json are the
single-day per-event-day abnormal-return coefficient (the OLS coef on
the `event_day >= 0` dummy). LLMs in practice report cumulative
abnormal returns (CAR) over a chosen post-event window, e.g.
CAR[0,+1] (2 days), CAR[-1,+1] (3 days), CAR[0,+5] (6 days).
Each is a valid event-study output; the canonical is just one of them
(window length 1).

So an LLM producing CAR[0,+5] with effect ≈ 6 × per_day_AR is
econometrically correct but fails L2b+ because canonical reports the
1-day value. Stage-6 spot-check confirmed this with ratios 1.5-3x
across nearly every ES failure.

Fix
---
For ES cells only: accept L2b+ pass if the judge-extracted effect
matches per_day_AR × k within `tol` for any integer k in
[1, .., max_window_post_days]. Keep non-ES cells identical to the
canonical-judge scoring.

Output
------
experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv
experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json

Cost: $0 (no LLM calls).
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORES = ROOT / "experiments/exp_b/l2b_plus_scores_canonical_judge.csv"
JUDGE = ROOT / "audit/l2b_judge_cache.json"
DGP_VERIF = ROOT / "audit/dgp_verification.json"
NEW_SCORES = ROOT / "experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv"
NEW_SUMMARY = ROOT / "experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json"

TOLERANCE = 0.5
ES_MAX_WINDOW_DAYS = 11   # [0, +10] is the longest plausible post-event window
                           # in our DGP (matches make_event_study's window=(-10,10))


def load_canonical_per_day():
    payload = json.loads(DGP_VERIF.read_text())
    return {r["scenario_id"]: float(r["estimated"])
            for r in payload["results"]
            if r.get("estimated") is not None}


def es_pass(judge_eff: float | None, per_day: float | None,
            tol: float = TOLERANCE,
            max_k: int = ES_MAX_WINDOW_DAYS) -> tuple[bool, int | None, float | None]:
    """Returns (pass, best_k, min_rel_error)."""
    if judge_eff is None or per_day is None or abs(per_day) < 1e-9:
        return False, None, None
    best_k = None
    best_err = float("inf")
    for k in range(1, max_k + 1):
        target = per_day * k
        if abs(target) < 1e-9:
            continue
        err = abs(judge_eff - target) / abs(target)
        if err < best_err:
            best_err = err
            best_k = k
    return (best_err < tol), best_k, best_err


def main():
    canonical = load_canonical_per_day()
    judge = json.loads(JUDGE.read_text())
    rows = list(csv.DictReader(open(SCORES)))

    out_rows = []
    for r in rows:
        sid = r["scenario_id"]
        method = r["method"]
        key = f"{sid}__{r['model_slug']}"
        j = judge.get(key, {})
        if not isinstance(j, dict):
            j = {}
        judge_eff = j.get("judge_effect")
        per_day = canonical.get(sid)

        nr = dict(r)
        if method == "EVENT_STUDY":
            ok, k_match, rel_err = es_pass(judge_eff, per_day)
            nr["L2b_plus_v2"] = int(ok)
            nr["es_window_match"] = k_match if k_match is not None else ""
            nr["rel_error_v2"] = round(rel_err, 4) if rel_err is not None else ""
        else:
            # Non-ES: keep judge result unchanged
            nr["L2b_plus_v2"] = int(r.get("L2b_plus_judge", "0") or 0)
            nr["es_window_match"] = ""
            nr["rel_error_v2"] = r.get("rel_error_judge", "")
        out_rows.append(nr)

    fieldnames = list(out_rows[0].keys())
    with open(NEW_SCORES, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print(f"Wrote: {NEW_SCORES}")

    by_model = defaultdict(lambda: {"n":0, "L2b":0,
                                     "L2b_plus_regex":0,
                                     "L2b_plus_judge":0,
                                     "L2b_plus_v2":0})
    by_mm = defaultdict(lambda: {"n":0, "L2b_plus_v2":0})
    es_window_dist = defaultdict(int)
    for r in out_rows:
        m = r["model"]
        by_model[m]["n"] += 1
        by_model[m]["L2b"] += int(r["L2b"])
        by_model[m]["L2b_plus_regex"] += int(r.get("regex_l2b_plus","0") or 0)
        by_model[m]["L2b_plus_judge"] += int(r.get("L2b_plus_judge","0") or 0)
        by_model[m]["L2b_plus_v2"] += int(r["L2b_plus_v2"])
        by_mm[(m, r["method"])]["n"] += 1
        by_mm[(m, r["method"])]["L2b_plus_v2"] += int(r["L2b_plus_v2"])
        if r["method"] == "EVENT_STUDY" and r.get("es_window_match"):
            es_window_dist[int(r["es_window_match"])] += 1

    summary = {
        "tolerance": TOLERANCE,
        "es_max_window_days": ES_MAX_WINDOW_DAYS,
        "by_model": {m: dict(v,
            L2b_plus_regex_rate=v["L2b_plus_regex"]/v["n"],
            L2b_plus_judge_rate=v["L2b_plus_judge"]/v["n"],
            L2b_plus_v2_rate=v["L2b_plus_v2"]/v["n"]) for m, v in by_model.items()},
        "by_model_method": {f"{m}__{meth}": dict(v, rate=v["L2b_plus_v2"]/v["n"])
                              for (m, meth), v in by_mm.items()},
        "es_window_distribution": dict(es_window_dist),
    }
    NEW_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote: {NEW_SUMMARY}")
    print()

    print(f"{'Model':<8} {'L2b':>5} {'regex':>9} {'judge':>9} {'judge_v2':>9}  Δ_v2_vs_judge")
    print("-" * 70)
    for m in ["Opus","GPT-5","GPT-4o","Sonnet","o3","Gemini","Kimi","Llama"]:
        if m not in by_model: continue
        v = by_model[m]
        print(f"{m:<8} {v['L2b']:>3}/{v['n']:<3}  "
              f"{v['L2b_plus_regex']:>3}/{v['n']:<3}={v['L2b_plus_regex']/v['n']*100:>3.0f}%  "
              f"{v['L2b_plus_judge']:>3}/{v['n']:<3}={v['L2b_plus_judge']/v['n']*100:>3.0f}%  "
              f"{v['L2b_plus_v2']:>3}/{v['n']:<3}={v['L2b_plus_v2']/v['n']*100:>3.0f}%  "
              f"{v['L2b_plus_v2']-v['L2b_plus_judge']:+d}")
    print()
    print("Per-model × method (L2b+ v2 with ES window-aware):")
    print(f"{'Model':<8}    DID         ES         IV         RDD")
    print("-" * 70)
    method_n = {'DID':30,'EVENT_STUDY':24,'IV':24,'RDD':22}
    for m in ["Opus","GPT-5","GPT-4o","Sonnet","o3","Gemini","Kimi","Llama"]:
        cells = []
        for meth in ['DID','EVENT_STUDY','IV','RDD']:
            v = by_mm.get((m, meth), {"n":method_n[meth], "L2b_plus_v2":0})
            cells.append(f"{v['L2b_plus_v2']:>2}/{v['n']:<2}={v['L2b_plus_v2']/v['n']*100:>3.0f}%")
        print(f"{m:<8}  {cells[0]:<10} {cells[1]:<10} {cells[2]:<10} {cells[3]:<10}")
    print()
    print(f"ES window-length distribution among ES passes:")
    for k in sorted(es_window_dist):
        print(f"  k={k} day(s) post-event: {es_window_dist[k]} cells")


if __name__ == "__main__":
    main()
