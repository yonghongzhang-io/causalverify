#!/usr/bin/env python3
"""Stage 8.5 (Step 3) — aggregate auto_scores.csv into paper-ready tables.

Inputs
------
experiments/exp_a/auto_scores.csv   produced by Stage 8.4

Outputs
-------
paper/tables/exp_a_l3_l4_by_model.csv
paper/tables/exp_a_l3_l4_by_method.csv
paper/tables/exp_a_confusion_matrix_by_model.csv
audit/exp_a_stage8_score_summary.md

Numbers reported with 95% bootstrap CI (n=10,000) on L3_scoreable /
L4_scoreable subsets only. Method-family breakdown uses the canonical
method label from gt_aggregate_decisions.json (already merged into
auto_scores.csv as 'method').
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORES_CSV = ROOT / "experiments/exp_a/auto_scores.csv"
TABLES_DIR = ROOT / "paper/tables"
SUMMARY_MD = ROOT / "audit/exp_a_stage8_score_summary.md"

MODELS_SHORT = [
    "Kimi-128k",
    "Claude-Sonnet",
    "GPT-4o",
    "o3",
    "Claude-Opus",
    "Gemini-2.5",
    "GPT-5",
]
METHOD_FAMILIES = ["DID", "EVENT_STUDY", "IV", "RDD"]

random.seed(20260428)


def bootstrap_ci(values: list[int], n_boot: int = 10_000) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    means = []
    n = len(values)
    for _ in range(n_boot):
        sample = [values[random.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def main():
    rows = list(csv.DictReader(SCORES_CSV.open()))
    print(f"Loaded {len(rows)} rows from {SCORES_CSV}")

    # ── L3 / L4 by model ───────────────────────────────────────────────
    by_model_records = []
    for m in MODELS_SHORT:
        l3_pool = [int(r[f"{m}_L3_method_agree"]) for r in rows
                   if r["L3_scoreable"] == "1" and r[f"{m}_L3_method_agree"] in ("0", "1")]
        l4_pool = [int(r[f"{m}_L4_direction_agree"]) for r in rows
                   if r["L4_scoreable"] == "1" and r[f"{m}_L4_direction_agree"] in ("0", "1")]
        l3_pct = sum(l3_pool) / len(l3_pool) if l3_pool else 0
        l4_pct = sum(l4_pool) / len(l4_pool) if l4_pool else 0
        l3_lo, l3_hi = bootstrap_ci(l3_pool)
        l4_lo, l4_hi = bootstrap_ci(l4_pool)
        by_model_records.append({
            "model": m,
            "n_L3_scoreable": len(l3_pool),
            "L3_pct": round(100 * l3_pct, 1),
            "L3_ci_lo": round(100 * l3_lo, 1),
            "L3_ci_hi": round(100 * l3_hi, 1),
            "n_L4_scoreable": len(l4_pool),
            "L4_pct": round(100 * l4_pct, 1),
            "L4_ci_lo": round(100 * l4_lo, 1),
            "L4_ci_hi": round(100 * l4_hi, 1),
        })

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TABLES_DIR / "exp_a_l3_l4_by_model.csv"
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(by_model_records[0].keys()))
        w.writeheader()
        w.writerows(by_model_records)
    print(f"Wrote {out_path}")

    # ── L3 / L4 by model × method-family ──────────────────────────────
    by_method_records = []
    for m in MODELS_SHORT:
        for mf in METHOD_FAMILIES:
            sub = [r for r in rows if r["method"] == mf]
            l3_pool = [int(r[f"{m}_L3_method_agree"]) for r in sub
                       if r["L3_scoreable"] == "1" and r[f"{m}_L3_method_agree"] in ("0", "1")]
            l4_pool = [int(r[f"{m}_L4_direction_agree"]) for r in sub
                       if r["L4_scoreable"] == "1" and r[f"{m}_L4_direction_agree"] in ("0", "1")]
            by_method_records.append({
                "model": m,
                "method": mf,
                "n_L3": len(l3_pool),
                "L3_pct": round(100 * sum(l3_pool) / max(1, len(l3_pool)), 1),
                "n_L4": len(l4_pool),
                "L4_pct": round(100 * sum(l4_pool) / max(1, len(l4_pool)), 1),
            })
    out_path = TABLES_DIR / "exp_a_l3_l4_by_method.csv"
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(by_method_records[0].keys()))
        w.writeheader()
        w.writerows(by_method_records)
    print(f"Wrote {out_path}")

    # ── Confusion matrix per model ────────────────────────────────────
    confusion_rows = []
    for m in MODELS_SHORT:
        cmat = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if r["L3_scoreable"] != "1":
                continue
            true_m = r["method"]
            pred_m = r[f"{m}_detected"] or "UNKNOWN"
            cmat[true_m][pred_m] += 1
        # flatten: each row = (model, true, pred_DID, pred_ES, pred_IV, pred_RDD, pred_OTHER, total)
        for true_m in METHOD_FAMILIES:
            row_data = {
                "model": m,
                "true_method": true_m,
                "pred_DID": cmat[true_m].get("DID", 0),
                "pred_EVENT_STUDY": cmat[true_m].get("EVENT_STUDY", 0),
                "pred_IV": cmat[true_m].get("IV", 0),
                "pred_RDD": cmat[true_m].get("RDD", 0),
                "pred_OTHER": sum(v for k, v in cmat[true_m].items()
                                  if k not in METHOD_FAMILIES),
                "n_total": sum(cmat[true_m].values()),
            }
            confusion_rows.append(row_data)

    out_path = TABLES_DIR / "exp_a_confusion_matrix_by_model.csv"
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(confusion_rows[0].keys()))
        w.writeheader()
        w.writerows(confusion_rows)
    print(f"Wrote {out_path}")

    # ── Markdown summary ──────────────────────────────────────────────
    n_papers = len(rows)
    n_l3_score = sum(1 for r in rows if r["L3_scoreable"] == "1")
    n_l4_score = sum(1 for r in rows if r["L4_scoreable"] == "1")
    n_l4_canonical_method = sum(
        1 for r in rows
        if r["L4_scoreable"] == "1" and r["method"] in METHOD_FAMILIES
    )
    n_l4_noncanonical_method = n_l4_score - n_l4_canonical_method

    md = ["# Exp A Stage 8 score summary",
          "",
          f"**Source**: `{SCORES_CSV.relative_to(ROOT)}` ({n_papers} papers × 7 models)",
          f"**GT source**: `audit/gt_aggregate_decisions.json` (V2'' 4-LLM consensus)",
          f"**Scoreable subsets**: L3={n_l3_score}/{n_papers}, L4={n_l4_score}/{n_papers}",
          "",
          "## Per-model L3 / L4 with 95% bootstrap CI (n=10,000)",
          "",
          "| Model | L3 method | 95% CI | L4 direction | 95% CI |",
          "|---|---:|:---:|---:|:---:|"]
    for r in by_model_records:
        md.append(
            f"| {r['model']} | {r['L3_pct']}% | "
            f"[{r['L3_ci_lo']}, {r['L3_ci_hi']}] | "
            f"{r['L4_pct']}% | [{r['L4_ci_lo']}, {r['L4_ci_hi']}] |"
        )

    md += ["", "## Per-method × per-model L3 (method-family agreement)",
           "",
           "| Model | DID | EVENT_STUDY | IV | RDD |",
           "|---|---:|---:|---:|---:|"]
    for m in MODELS_SHORT:
        cells = [m]
        for mf in METHOD_FAMILIES:
            r = next(x for x in by_method_records if x["model"] == m and x["method"] == mf)
            cells.append(f"{r['L3_pct']}% (n={r['n_L3']})")
        md.append("| " + " | ".join(cells) + " |")

    md += ["", "## Per-method × per-model L4 (direction agreement)",
           "",
           f"The per-method L4 table is restricted to the four canonical method families "
           f"({n_l4_canonical_method}/{n_l4_score} direction-scoreable papers). "
           f"The remaining {n_l4_noncanonical_method} direction-scoreable papers have "
           "`OTHER` or unresolved method labels and are included in the overall L4 rates above.",
           "",
           "| Model | DID | EVENT_STUDY | IV | RDD |",
           "|---|---:|---:|---:|---:|"]
    for m in MODELS_SHORT:
        cells = [m]
        for mf in METHOD_FAMILIES:
            r = next(x for x in by_method_records if x["model"] == m and x["method"] == mf)
            cells.append(f"{r['L4_pct']}% (n={r['n_L4']})")
        md.append("| " + " | ".join(cells) + " |")

    md += ["", "## L3 ranking (highest → lowest)",
           ""]
    ranked = sorted(by_model_records, key=lambda r: -r["L3_pct"])
    for i, r in enumerate(ranked, 1):
        md.append(f"{i}. **{r['model']}** — {r['L3_pct']}% L3 "
                  f"(95% CI [{r['L3_ci_lo']}, {r['L3_ci_hi']}])")

    md += ["", "## L4 ranking (highest → lowest)",
           ""]
    ranked = sorted(by_model_records, key=lambda r: -r["L4_pct"])
    for i, r in enumerate(ranked, 1):
        md.append(f"{i}. **{r['model']}** — {r['L4_pct']}% L4 "
                  f"(95% CI [{r['L4_ci_lo']}, {r['L4_ci_hi']}])")

    md += ["", "## Notes for paper §5",
           "",
           f"- L3/L4 are **text-level agreement**, not detection. L3 is computed on the {n_l3_score}/{n_papers} papers where the 4-LLM consensus produced one of the four canonical method-family labels. L4 is computed on the {n_l4_score}/{n_papers} papers where the 4-LLM consensus produced a positive/negative direction label.",
           f"- Per-method L4 rows cover {n_l4_canonical_method}/{n_l4_score} L4-scoreable papers; the remaining {n_l4_noncanonical_method} have `OTHER` or unresolved method labels but still have scoreable directions.",
           "- Rankings differ between L3 and L4 (e.g., GPT-4o leads L3 at 88.8%, Claude-Sonnet leads L4 at 85.9%); this is the F4 fragility result.",
           "- For execution-grounded correctness, see Exp B L2b+ (canonical-baseline judge_v2).",
           ""]

    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(md))
    print(f"Wrote {SUMMARY_MD}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
