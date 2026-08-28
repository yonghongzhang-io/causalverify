#!/usr/bin/env python3
"""Spot-check whether L2b+ failures are model failures or regex-extraction
failures.

For each (scenario, model) where L2b=1 AND L2b+=0 (i.e. the model wrote R
that ran successfully but our regex did not yield a passing coefficient),
re-run the R code, and look at the full stdout for any number that is
within 50% of the canonical baseline beta.

  EXTRACTION_FAIL : current regex returned None (or a wrong number),
                    but stdout contains a number near canonical beta.
                    => the model probably DID get it right, our scorer
                    failed to read the result.

  MODEL_FAIL      : current regex returned None and stdout has no
                    number near canonical beta. The model truly did
                    not produce the right effect.

  EXTRACTED_WRONG : regex returned a number, but it was far from
                    canonical, AND stdout contains another number that
                    is near canonical. The regex picked the wrong
                    coefficient from the table.

This is a $0 audit (R code is local).
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "pipeline"))
from score_l2b_plus import (  # type: ignore
    extract_r_code,
    execute_r_code,
    extract_coefficient,
)

SCORES_CSV = ROOT / "experiments/exp_b/l2b_plus_scores_canonical.csv"
OUTPUTS_DIR = ROOT / "experiments/exp_b/outputs"
DGP_VERIF = ROOT / "audit/dgp_verification.json"
OUT_PATH = ROOT / "audit/l2b_extraction_spot_check.json"

NEAR_TOL = 0.5  # what counts as "close to canonical"
N_PER_MODEL = 5


def load_canonical() -> dict[str, float]:
    payload = json.loads(DGP_VERIF.read_text())
    return {r["scenario_id"]: float(r["estimated"]) for r in payload["results"]
            if r.get("estimated") is not None}


def find_near_canonical(stdout: str, canonical: float, tol: float = NEAR_TOL):
    """Return the first stdout number within `tol` relative error of canonical."""
    if not stdout or canonical is None or abs(canonical) < 1e-9:
        return None
    pattern = re.compile(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?")
    for tok in pattern.findall(stdout):
        try:
            v = float(tok)
        except ValueError:
            continue
        if abs(v) < 1e-9 or abs(v) > 50:  # implausible
            continue
        if abs(v - canonical) / abs(canonical) < tol:
            return v
    return None


def main() -> int:
    canonical = load_canonical()
    print(f"Loaded {len(canonical)} canonical baselines")

    # Load all suspect rows (L2b=1, L2b+=0)
    suspects = []
    with open(SCORES_CSV) as f:
        for r in csv.DictReader(f):
            if r["L2b"] == "1" and r["L2b_plus"] == "0":
                suspects.append(r)
    print(f"Total L2b=1 & L2b+=0 suspects: {len(suspects)}")

    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in suspects:
        by_model[r["model"]].append(r)

    rng = random.Random(20260427)
    selected: list[dict] = []
    for model, rows in by_model.items():
        k = min(N_PER_MODEL, len(rows))
        selected.extend(rng.sample(rows, k))
    print(f"Selected {len(selected)} cases ({N_PER_MODEL} per model max)")
    print()

    results = []
    for i, case in enumerate(selected, 1):
        sid = case["scenario_id"]
        model_slug = case["model_slug"]
        out_file = OUTPUTS_DIR / f"{sid}_{model_slug}.json"
        if not out_file.exists():
            continue
        d = json.loads(out_file.read_text())
        content = d.get("llm_response", {}).get("content", "")
        code = extract_r_code(content)
        if code is None:
            continue

        ok, stdout, err = execute_r_code(code)
        if not ok:
            # Was L2b=1 originally; this is a flake. Note and skip.
            continue

        beta_canon = canonical.get(sid)
        method = case["method"]
        re_extracted = extract_coefficient(stdout, method) if stdout else None
        nearby = find_near_canonical(stdout, beta_canon)

        # Diagnose
        if re_extracted is None and nearby is not None:
            diagnosis = "EXTRACTION_FAIL"
        elif re_extracted is not None and nearby is not None and \
             abs(re_extracted - beta_canon) / abs(beta_canon) > NEAR_TOL:
            diagnosis = "EXTRACTED_WRONG"
        else:
            diagnosis = "MODEL_FAIL"

        results.append({
            "scenario_id": sid,
            "model": case["model"],
            "method": method,
            "canonical_beta": beta_canon,
            "regex_extracted": re_extracted,
            "near_canonical_in_stdout": nearby,
            "diagnosis": diagnosis,
            "stdout_tail": (stdout or "")[-600:],
        })
        flag = {"EXTRACTION_FAIL": "⚠️ EXTRACTION", "EXTRACTED_WRONG": "⚠️ WRONG",
                "MODEL_FAIL": "model"}[diagnosis]
        print(f"  [{i:>2}/{len(selected)}] {sid} {case['model']:<8} "
              f"canon={beta_canon:>+.3f} "
              f"regex={'None' if re_extracted is None else f'{re_extracted:+.3f}'} "
              f"near={'None' if nearby is None else f'{nearby:+.3f}'} "
              f"{flag}")

    diag = Counter(r["diagnosis"] for r in results)
    by_model_diag = defaultdict(Counter)
    for r in results:
        by_model_diag[r["model"]][r["diagnosis"]] += 1

    summary = {
        "n_audited": len(results),
        "diagnosis_counts": dict(diag),
        "extraction_fail_rate": (diag.get("EXTRACTION_FAIL", 0) +
                                  diag.get("EXTRACTED_WRONG", 0)) / max(1, len(results)),
        "by_model": {m: dict(c) for m, c in by_model_diag.items()},
    }

    OUT_PATH.write_text(json.dumps({"summary": summary, "cases": results},
                                    indent=2, ensure_ascii=False))

    print()
    print("=" * 70)
    print(f"Audited {len(results)} L2b=1 & L2b+=0 suspects")
    print(f"Diagnosis: {dict(diag)}")
    print(f"  EXTRACTION_FAIL + EXTRACTED_WRONG = "
          f"{diag.get('EXTRACTION_FAIL',0) + diag.get('EXTRACTED_WRONG',0)} / {len(results)} "
          f"= {summary['extraction_fail_rate']*100:.0f}%")
    print()
    print("Per-model:")
    for m, c in sorted(by_model_diag.items()):
        ext = c.get("EXTRACTION_FAIL", 0) + c.get("EXTRACTED_WRONG", 0)
        tot = sum(c.values())
        print(f"  {m:<8}: ext-issue {ext}/{tot},  detail {dict(c)}")
    print()
    print(f"Saved: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
