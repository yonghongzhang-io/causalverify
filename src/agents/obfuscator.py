"""
Agent 7 — Variable Name Obfuscator
===================================

Purpose
-------
Exp B synthetic CSVs use column names that literally telegraph the method
(e.g., `treated`, `post`, `treat_x_post` → DID; `running_var` → RDD).
An LLM seeing these names doesn't need to "identify" the method — it's
in the data.

This agent produces an obfuscated parallel copy of each CSV with
generic variable names, plus a mapping file that the scoring pipeline
can use to translate LLM output back to canonical names.

Obfuscation schemes
-------------------
Methods get deliberately neutral column names that do not reveal the
analytical framework. The mapping is one-to-one and reversible.

Input
-----
  experiments/exp_b/data/sXX_data.csv        (100 CSVs)
  experiments/exp_b/scenarios/sXX.json       (100 scenarios)

Output
------
  experiments/exp_b/data_obfuscated/sXX_data.csv  (100 obfuscated CSVs)
  experiments/exp_b/data_obfuscated/obfuscation_map.json  (column mappings)
  audit/obfuscation_summary.md

Usage
-----
  python3 src/agents/obfuscator.py
  python3 src/agents/obfuscator.py --scheme randomized   # every scenario unique mapping
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCEN_DIR = PROJECT_ROOT / "experiments/exp_b/scenarios"
DATA_DIR = PROJECT_ROOT / "experiments/exp_b/data"
OUT_DATA_DIR = PROJECT_ROOT / "experiments/exp_b/data_obfuscated"
OUT_MAP = OUT_DATA_DIR / "obfuscation_map.json"
OUT_MD = PROJECT_ROOT / "audit/obfuscation_summary.md"


# ── Neutral column-name schemes ────────────────────────────────────
# Key design goal: names should be descriptive enough for the LLM to
# reason about the data, but NOT reveal the causal-inference framework.

STATIC_SCHEMES = {
    "DID": {
        "unit_id":       "entity_id",
        "period":        "wave",
        "treated":       "group_indicator",
        "post":          "phase_indicator",
        "treat_x_post":  "group_phase_interaction",
        "y":             "outcome",
    },
    "EVENT_STUDY": {
        "stock_id":      "series_id",
        "event_day":     "time_offset",
        "ret":           "observation",
        "mkt_ret":       "reference_series",
        "beta":          "sensitivity_coefficient",
    },
    "IV": {
        "y":             "outcome",
        "x":             "focal_variable",
        "z":             "auxiliary_variable",
        "controls":      "covariate_a",
    },
    "RDD": {
        "running_var":   "assignment_score",
        "treated":       "status_flag",
        "y":             "outcome",
        "near_cutoff":   "proximity_flag",
    },
}


def obfuscate_scenario(scen: dict, data_path: Path, out_dir: Path) -> dict:
    """Obfuscate one scenario's CSV. Returns mapping record."""
    method = scen["method_family"]
    sid = scen["scenario_id"]

    scheme = STATIC_SCHEMES.get(method)
    if scheme is None:
        return {"scenario_id": sid, "status": "no_scheme_for_method", "method": method}

    df = pd.read_csv(data_path)

    # Only rename columns that exist in the data (avoid KeyError)
    applicable_mapping = {k: v for k, v in scheme.items() if k in df.columns}
    unexpected_cols = [c for c in df.columns if c not in scheme and not c.startswith("_")]

    df_obf = df.rename(columns=applicable_mapping)

    # Write obfuscated CSV
    out_csv = out_dir / data_path.name
    out_dir.mkdir(parents=True, exist_ok=True)
    df_obf.to_csv(out_csv, index=False)

    # Compute data hash for provenance
    csv_bytes = out_csv.read_bytes()
    sha = hashlib.sha256(csv_bytes).hexdigest()[:16]

    return {
        "scenario_id": sid,
        "method_family": method,
        "status": "obfuscated",
        "original_to_obfuscated": applicable_mapping,
        "obfuscated_to_original": {v: k for k, v in applicable_mapping.items()},
        "unexpected_columns": unexpected_cols,  # columns not in scheme (preserved as-is)
        "n_rows": len(df_obf),
        "original_csv": str(data_path.relative_to(PROJECT_ROOT)),
        "obfuscated_csv": str(out_csv.relative_to(PROJECT_ROOT)),
        "obfuscated_sha256_prefix": sha,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", choices=["static", "randomized"], default="static",
                        help="'static' = same names across scenarios; 'randomized' = per-scenario (TBD)")
    args = parser.parse_args()

    if args.scheme == "randomized":
        print("WARN: 'randomized' scheme not yet implemented; falling back to 'static'.")

    scenarios = sorted(SCEN_DIR.glob("s*.json"), key=lambda p: int(p.stem[1:]))
    print(f"Obfuscating {len(scenarios)} scenarios (scheme=static)...\n")

    records = []
    for scen_path in scenarios:
        scen = json.load(open(scen_path))
        sid = scen["scenario_id"]
        data_path = PROJECT_ROOT / scen["data_file"]

        if not data_path.exists():
            rec = {"scenario_id": sid, "status": "missing_data",
                   "expected_path": str(data_path)}
            records.append(rec)
            print(f"  [!] {sid} missing data file")
            continue

        rec = obfuscate_scenario(scen, data_path, OUT_DATA_DIR)
        records.append(rec)
        if rec["status"] == "obfuscated":
            mapping_summary = ", ".join(f"{k}→{v}" for k, v in
                                         list(rec["original_to_obfuscated"].items())[:3])
            print(f"  [✓] {sid} ({rec['method_family']}): "
                  f"{len(rec['original_to_obfuscated'])} cols renamed ({mapping_summary}...)")
        else:
            print(f"  [?] {sid}: {rec['status']}")

    # Save mapping
    with open(OUT_MAP, "w") as f:
        json.dump({
            "scheme": args.scheme,
            "static_schemes": STATIC_SCHEMES,
            "records": records,
        }, f, indent=2)

    # Aggregate
    from collections import Counter
    status_counts = Counter(r["status"] for r in records)

    # Markdown summary
    lines = [
        "# Obfuscation Summary\n",
        f"Obfuscated {len(records)} Exp B scenarios using static scheme.\n",
        "## Status\n",
    ]
    for status, count in status_counts.items():
        lines.append(f"- {status}: {count}")

    lines.append("\n## Obfuscation Schemes\n")
    for method, scheme in STATIC_SCHEMES.items():
        lines.append(f"\n### {method}\n")
        lines.append("| Original | Obfuscated |")
        lines.append("|---|---|")
        for orig, obf in scheme.items():
            lines.append(f"| `{orig}` | `{obf}` |")

    lines.append("\n## Usage\n")
    lines.append("To use the obfuscated data for a new LLM evaluation round:")
    lines.append("")
    lines.append("1. In `run_exp_b.py`, replace `data_file` with the obfuscated version:")
    lines.append("   ```python")
    lines.append("   data_file = str(data_path).replace(")
    lines.append("       'experiments/exp_b/data/',")
    lines.append("       'experiments/exp_b/data_obfuscated/')")
    lines.append("   ```")
    lines.append("2. In `score_l2b_plus.py`, when extracting coefficients, apply the reverse")
    lines.append("   mapping from `obfuscation_map.json` so that LLM-generated references to")
    lines.append("   obfuscated names are understood correctly.")
    lines.append("")
    lines.append("3. Compare L3 results on obfuscated vs. original data to quantify how much")
    lines.append("   the method-revealing variable names inflated L3 pass rates.")

    lines.append("\n## Interpretation\n")
    n_obf = status_counts.get("obfuscated", 0)
    lines.append(f"✅ **{n_obf}/{len(records)} scenarios successfully obfuscated.**")
    lines.append("")
    lines.append("**Recommended robustness test for v11 paper**: run Exp B on a subset (say 30 "
                 "scenarios) using the obfuscated CSVs. Report L3 and L2b+ rates on both "
                 "original and obfuscated data. Large differences indicate that method-revealing "
                 "names were inflating L3 results.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote: {OUT_DATA_DIR}/ (100 obfuscated CSVs)")
    print(f"Wrote: {OUT_MAP}")
    print(f"Wrote: {OUT_MD}")


if __name__ == "__main__":
    main()
