#!/usr/bin/env python3
"""Recompute calibration summary against the v11 frozen L2b+v2 labels.

Why
---
calibration_scores.csv was produced when L2b+ used the DGP-baseline +
regex-extraction scoring. It still carries the per-row L2b_plus column
under that legacy definition. After Stage 8 we use canonical-judge-v2
as the headline correctness label (judge extraction + ES window-aware
matching against the canonical estimator on the realised dataset).

Therefore confidence-vs-correctness metrics (ECE, confidence gap,
high-conf-vs-low-conf splits) need to be recomputed using the v2 label.

Inputs
------
experiments/exp_b/calibration_scores.csv   per (scenario, model) confidence
experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv  v2 correctness

Outputs
-------
experiments/exp_b/calibration_summary_v2.json  per-model recomputed metrics
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAL_CSV = ROOT / "experiments/exp_b/calibration_scores.csv"
V2_CSV = ROOT / "experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv"
OUT = ROOT / "experiments/exp_b/calibration_summary_v2.json"


def compute_ece(confidences: list[float], correct: list[int],
                n_bins: int = 10) -> float:
    """Expected calibration error across `n_bins` equal-width bins."""
    n = len(confidences)
    if n == 0:
        return 0.0
    bins = [[] for _ in range(n_bins)]
    for c, y in zip(confidences, correct):
        idx = min(n_bins - 1, int(c * n_bins))
        bins[idx].append((c, y))
    ece = 0.0
    for b in bins:
        if not b:
            continue
        b_conf = sum(c for c, _ in b) / len(b)
        b_acc = sum(y for _, y in b) / len(b)
        ece += (len(b) / n) * abs(b_conf - b_acc)
    return ece


def main():
    # Load v2 correctness map: (sid, model_slug) -> L2b+v2
    v2_map = {}
    with V2_CSV.open() as f:
        for r in csv.DictReader(f):
            v2_map[(r["scenario_id"], r["model_slug"])] = int(r["L2b_plus_v2"])

    # Load calibration scores
    cal_rows = []
    with CAL_CSV.open() as f:
        for r in csv.DictReader(f):
            try:
                nc = float(r["numerical_confidence"])
                mc = float(r["method_confidence"])
                sc = float(r["specification_confidence"])
            except (KeyError, ValueError):
                continue
            v2 = v2_map.get((r["scenario_id"], r["model_slug"]))
            if v2 is None:
                # Calibration row exists but no v2 score → skip
                continue
            cal_rows.append({
                "scenario_id": r["scenario_id"],
                "model_slug": r["model_slug"],
                "model_short": r["model_short"],
                "method_family": r["method_family"],
                "numerical_confidence": nc,
                "method_confidence": mc,
                "specification_confidence": sc,
                "L2b_plus_legacy": int(r.get("L2b_plus", "0") or "0"),
                "L2b_plus_v2": v2,
            })

    print(f"Calibration rows joined to v2 label: {len(cal_rows)}")

    # Per-model recompute against v2 label
    summary = {}
    by_model_short = {}
    for r in cal_rows:
        by_model_short.setdefault(r["model_short"], []).append(r)

    for model_short, rows in by_model_short.items():
        nc = [r["numerical_confidence"] for r in rows]
        mc = [r["method_confidence"] for r in rows]
        sc = [r["specification_confidence"] for r in rows]
        correct = [r["L2b_plus_v2"] for r in rows]

        ece_num = compute_ece(nc, correct, n_bins=10)
        ece_meth = compute_ece(mc, correct, n_bins=10)
        ece_spec = compute_ece(sc, correct, n_bins=10)

        n_wrong = sum(1 for c in correct if c == 0)
        n_right = sum(1 for c in correct if c == 1)
        high_conf_wrong = sum(1 for i, c in enumerate(nc) if c > 0.8 and correct[i] == 0)
        high_conf_right = sum(1 for i, c in enumerate(nc) if c > 0.8 and correct[i] == 1)
        p_hi_given_wrong = high_conf_wrong / max(n_wrong, 1)
        p_hi_given_right = high_conf_right / max(n_right, 1)

        mean_nc_wrong = (sum(nc[i] for i in range(len(nc)) if correct[i] == 0)
                         / max(n_wrong, 1))
        mean_nc_right = (sum(nc[i] for i in range(len(nc)) if correct[i] == 1)
                         / max(n_right, 1))

        summary[model_short] = {
            "n": len(rows),
            "L2b_plus_v2_pass_rate": round(sum(correct) / len(correct), 4),
            "ECE_numerical": round(ece_num, 4),
            "ECE_method": round(ece_meth, 4),
            "ECE_specification": round(ece_spec, 4),
            "mean_numerical_conf_all": round(sum(nc) / len(nc), 4),
            "mean_numerical_conf_wrong": round(mean_nc_wrong, 4),
            "mean_numerical_conf_right": round(mean_nc_right, 4),
            "confidence_gap_right_minus_wrong":
                round(mean_nc_right - mean_nc_wrong, 4),
            "P_high_conf_given_wrong": round(p_hi_given_wrong, 4),
            "P_high_conf_given_right": round(p_hi_given_right, 4),
        }

    OUT.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {OUT}")
    print()
    print(f"{'Model':<8} {'n':>4} {'L2b+v2 rate':>11} {'ECE_num':>9} "
          f"{'gap':>7} {'P(hi|0)':>9} {'P(hi|1)':>9}")
    print("-" * 72)
    for m, d in summary.items():
        print(f"{m:<8} {d['n']:>4} "
              f"{d['L2b_plus_v2_pass_rate']*100:>9.1f}%  "
              f"{d['ECE_numerical']:>8.3f} "
              f"{d['confidence_gap_right_minus_wrong']:>+7.3f} "
              f"{d['P_high_conf_given_wrong']:>9.3f} "
              f"{d['P_high_conf_given_right']:>9.3f}")


if __name__ == "__main__":
    main()
