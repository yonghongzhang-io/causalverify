#!/usr/bin/env python3
"""Score Llama-only Exp B outputs and append to frozen canonical CSV.

Avoids a full 8-model rerun that would risk byte-shifting the frozen
7-model rows (R execution is deterministic in principle but small package
diffs could perturb stdout).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "pipeline"))
from score_l2b_plus import (  # type: ignore
    load_canonical_baselines, score_output, DEFAULT_TOL,
)

SCEN_DIR = ROOT / "experiments/exp_b/scenarios"
OUT_DIR = ROOT / "experiments/exp_b/outputs"
CSV_PATH = ROOT / "experiments/exp_b/l2b_plus_scores_canonical.csv"

LLAMA_SLUG = "meta-llama-Llama-3.3-70B-Instruct"
LLAMA_SHORT = "Llama"


def main():
    canonical = load_canonical_baselines()
    print(f"Canonical baselines: {len(canonical)}")

    rows = []
    scenarios = sorted(SCEN_DIR.glob("s*.json"), key=lambda p: int(p.stem[1:]))
    for s_file in scenarios:
        scenario = json.load(open(s_file))
        sid = scenario["scenario_id"]
        out_file = OUT_DIR / f"{sid}_{LLAMA_SLUG}.json"
        if not out_file.exists():
            print(f"  MISSING: {sid}")
            continue
        llm_output = json.load(open(out_file))
        result = score_output(scenario, llm_output, DEFAULT_TOL, "canonical", canonical)
        result["model"] = LLAMA_SHORT
        result["model_slug"] = LLAMA_SLUG
        rows.append(result)
        tag = "+" if result["L2b_plus"] else ("V" if result["L2b"] else ("c" if result["L2a"] else "."))
        est = f"{result['estimated']:.3f}" if result["estimated"] is not None else "?"
        print(f"  {sid} L2a={result['L2a']} L2b={result['L2b']} L2b+={result['L2b_plus']} [{tag}] est={est}")

    print(f"\nScored {len(rows)} Llama rows")
    n_l2b = sum(r["L2b"] for r in rows)
    n_l2bp = sum(r["L2b_plus"] for r in rows)
    print(f"L2b: {n_l2b}/{len(rows)}  L2b+: {n_l2bp}/{len(rows)}")

    # Read existing CSV
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing = list(reader)

    # Drop any prior Llama rows just in case
    existing = [r for r in existing if r.get("model") != LLAMA_SHORT]
    print(f"Existing rows (non-Llama): {len(existing)}")

    # Append new Llama rows, normalising fields to match existing schema
    for r in rows:
        out = {k: "" for k in fieldnames}
        for k, v in r.items():
            if k in out:
                out[k] = "" if v is None else v
        existing.append(out)

    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(existing)
    print(f"Wrote {len(existing)} rows -> {CSV_PATH}")


if __name__ == "__main__":
    main()
