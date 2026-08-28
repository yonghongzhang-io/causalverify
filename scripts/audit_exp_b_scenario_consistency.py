#!/usr/bin/env python3
"""Audit Exp B synthetic scenarios for benchmark consistency.

This is a local, deterministic gate. It does not use an LLM and does not
claim that every natural-language scenario is externally realistic. It checks
the properties needed for execution-grounded scoring:

1. Every scenario JSON has the required schema.
2. Every referenced CSV exists and is readable.
3. Method labels and DGP types are aligned.
4. DGP effect signs match declared directions.
5. Canonical regression baselines are available for every scenario.
6. Canonical baseline directions are recorded, including cases where finite
   sample noise makes beta* and beta-hat differ beyond the old 10% verifier.
7. Scenario text contains enough variable/data-file anchors for the evaluated
   model to write executable code.

Outputs:
  audit/exp_b_scenario_consistency_audit.csv
  audit/exp_b_scenario_consistency_summary.md
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT / "experiments/exp_b/scenarios"
AUDIT_CSV = ROOT / "audit/exp_b_scenario_consistency_audit.csv"
SUMMARY_MD = ROOT / "audit/exp_b_scenario_consistency_summary.md"
DGP_VERIFICATION = ROOT / "audit/dgp_verification.json"

METHODS = {"DID", "EVENT_STUDY", "IV", "RDD"}
DGP_TYPE_TO_METHOD = {
    "did": "DID",
    "event": "EVENT_STUDY",
    "event_study": "EVENT_STUDY",
    "iv": "IV",
    "rdd": "RDD",
}
DIRECTIONS = {"positive", "negative", "zero", "mixed", "unclear"}
REQUIRED_FIELDS = {
    "scenario_id",
    "method_family",
    "difficulty",
    "title",
    "research_question",
    "data_description",
    "ground_truth",
    "data_file",
    "dgp_truth",
}


def effect_direction(x: float) -> str:
    if x > 0:
        return "positive"
    if x < 0:
        return "negative"
    return "zero"


def read_csv_header(path: Path) -> tuple[list[str], int, str]:
    with path.open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        n = sum(1 for _ in reader)
    return header, n, ""


def main() -> None:
    dgp = json.loads(DGP_VERIFICATION.read_text())
    baselines = {r["scenario_id"]: r for r in dgp["results"]}

    records = []
    for path in sorted(SCENARIO_DIR.glob("s*.json")):
        issues: list[str] = []
        warnings: list[str] = []
        s = json.loads(path.read_text())
        sid = s.get("scenario_id", path.stem)

        missing = sorted(REQUIRED_FIELDS - set(s))
        if missing:
            issues.append(f"missing_fields:{'|'.join(missing)}")

        method = s.get("method_family")
        if method not in METHODS:
            issues.append(f"bad_method:{method}")

        dgp_truth = s.get("dgp_truth") or {}
        dgp_type = dgp_truth.get("type")
        expected_method = DGP_TYPE_TO_METHOD.get(dgp_type)
        if expected_method != method:
            issues.append(f"method_dgp_mismatch:{method}!={expected_method}")

        effect = dgp_truth.get("effect")
        dgp_dir = dgp_truth.get("direction")
        effect_dir = ""
        if isinstance(effect, (int, float)):
            effect_dir = effect_direction(float(effect))
            if dgp_dir != effect_dir:
                issues.append(f"dgp_effect_direction_mismatch:{effect}->{dgp_dir}")
        else:
            issues.append("missing_or_non_numeric_effect")

        gt = s.get("ground_truth") or {}
        gt_dir = gt.get("conclusion_direction")
        if gt_dir not in DIRECTIONS:
            issues.append(f"bad_gt_direction:{gt_dir}")
        elif dgp_dir in {"positive", "negative", "zero"} and gt_dir != dgp_dir:
            issues.append(f"gt_dgp_direction_mismatch:{gt_dir}!={dgp_dir}")

        data_file = ROOT / str(s.get("data_file", ""))
        csv_header: list[str] = []
        n_rows = 0
        if not data_file.exists():
            issues.append(f"missing_data_file:{s.get('data_file')}")
        else:
            try:
                csv_header, n_rows, _ = read_csv_header(data_file)
                if n_rows <= 0:
                    issues.append("empty_data_file")
            except Exception as exc:  # noqa: BLE001 - audit should retain reason
                issues.append(f"csv_read_error:{type(exc).__name__}")

        baseline = baselines.get(sid)
        if baseline is None:
            issues.append("missing_canonical_baseline")
        else:
            if baseline.get("error_msg"):
                issues.append("canonical_baseline_error")
            if not baseline.get("sign_correct", False):
                warnings.append("canonical_sign_differs_from_dgp")
            if baseline.get("status") == "FLAGGED":
                warnings.append("canonical_beta_hat_differs_from_beta_star_gt_10pct")

        text = (s.get("research_question", "") + " " + s.get("data_description", "")).lower()
        anchor_cols = {"y", "unit_id", "period"} & {c.lower() for c in csv_header}
        if "y" in {c.lower() for c in csv_header} and " y " not in f" {text} " and "outcome" not in text:
            warnings.append("text_may_not_name_outcome_column")
        if method == "DID":
            for col in ("treated", "post"):
                if col in {c.lower() for c in csv_header} and col not in text:
                    warnings.append(f"text_may_not_name_{col}")
        if method == "IV":
            if "instrument" not in text and "z" not in text:
                warnings.append("text_may_not_name_instrument")
        if method == "RDD":
            if "cutoff" not in text and "running" not in text:
                warnings.append("text_may_not_name_cutoff_or_running_variable")
        if method == "EVENT_STUDY":
            if "event" not in text and "date" not in text and "announcement" not in text:
                warnings.append("text_may_not_name_event_timing")

        records.append({
            "scenario_id": sid,
            "method_family": method or "",
            "difficulty": s.get("difficulty", ""),
            "origin": "human_written" if int(sid[1:]) <= 30 else "llm_templated",
            "data_file_exists": int(data_file.exists()),
            "n_rows": n_rows,
            "n_columns": len(csv_header),
            "dgp_effect": effect if effect is not None else "",
            "dgp_direction": dgp_dir or "",
            "gt_direction": gt_dir or "",
            "canonical_status": baseline.get("status", "") if baseline else "",
            "canonical_estimated": baseline.get("estimated", "") if baseline else "",
            "canonical_sign_correct": int(bool(baseline and baseline.get("sign_correct", False))),
            "hard_pass": int(not issues),
            "issues": ";".join(issues),
            "warnings": ";".join(warnings),
        })

    AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    hard_pass = sum(r["hard_pass"] for r in records)
    issue_counter = Counter()
    warning_counter = Counter()
    by_method = defaultdict(lambda: Counter())
    by_origin = defaultdict(lambda: Counter())
    for r in records:
        by_method[r["method_family"]]["total"] += 1
        by_method[r["method_family"]]["hard_pass"] += r["hard_pass"]
        by_origin[r["origin"]]["total"] += 1
        by_origin[r["origin"]]["hard_pass"] += r["hard_pass"]
        for issue in filter(None, r["issues"].split(";")):
            issue_counter[issue.split(":")[0]] += 1
        for warning in filter(None, r["warnings"].split(";")):
            warning_counter[warning] += 1

    md = [
        "# Exp B scenario consistency audit",
        "",
        f"Input scenarios: `{SCENARIO_DIR.relative_to(ROOT)}`",
        f"Canonical baseline source: `{DGP_VERIFICATION.relative_to(ROOT)}`",
        "",
        "## Summary",
        "",
        f"- Scenarios audited: {len(records)}",
        f"- Hard-pass scenarios: {hard_pass}/{len(records)} ({100 * hard_pass / len(records):.1f}%)",
        "- This audit checks benchmark consistency, not external economic realism.",
        "- `FLAGGED` canonical verifier cases are warnings, not hard failures, because v11 scores against canonical beta-hat on the realized data rather than ideal beta-star.",
        "",
        "## By method",
        "",
        "| Method | hard pass | total |",
        "|---|---:|---:|",
    ]
    for method in sorted(by_method):
        c = by_method[method]
        md.append(f"| {method} | {c['hard_pass']} | {c['total']} |")

    md += ["", "## By origin", "", "| Origin | hard pass | total |", "|---|---:|---:|"]
    for origin in sorted(by_origin):
        c = by_origin[origin]
        md.append(f"| {origin} | {c['hard_pass']} | {c['total']} |")

    md += ["", "## Hard issues", ""]
    if issue_counter:
        for k, v in issue_counter.most_common():
            md.append(f"- {k}: {v}")
    else:
        md.append("- None")

    md += ["", "## Warnings", ""]
    if warning_counter:
        for k, v in warning_counter.most_common():
            md.append(f"- {k}: {v}")
    else:
        md.append("- None")

    sign_diff = [
        r for r in records
        if "canonical_sign_differs_from_dgp" in r["warnings"].split(";")
    ]
    if sign_diff:
        md += ["", "### Canonical sign differs from beta-star", ""]
        md.append(
            "These are retained for execution scoring because L2b+ compares "
            "student estimates to the canonical estimate on the realized data, "
            "not to the ideal DGP parameter. They should be described as "
            "finite-sample/prior-data conflict cases if discussed in text."
        )
        md += ["", "| Scenario | Method | beta-star | beta-hat canonical | verifier status |",
               "|---|---|---:|---:|---|"]
        for r in sign_diff:
            md.append(
                f"| {r['scenario_id']} | {r['method_family']} | "
                f"{r['dgp_effect']} ({r['dgp_direction']}) | "
                f"{r['canonical_estimated']} | {r['canonical_status']} |"
            )

    failing = [r for r in records if not r["hard_pass"]]
    if failing:
        md += ["", "## Scenarios with hard issues", ""]
        for r in failing:
            md.append(f"- {r['scenario_id']} ({r['method_family']}): {r['issues']}")

    md += ["", "## Interpretation for paper", ""]
    md.append(
        "Exp B scenarios are treated as reliable for execution-grounded scoring "
        "when they have valid schema, readable CSV data, aligned DGP labels, and "
        "available canonical baselines. Natural-language descriptions are not "
        "treated as self-validating ground truth; they are prompt surfaces for "
        "models whose numerical outputs are judged against canonical estimators."
    )

    SUMMARY_MD.write_text("\n".join(md) + "\n")

    print(f"Wrote {AUDIT_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"Hard pass: {hard_pass}/{len(records)}")
    if issue_counter:
        print("Issues:", dict(issue_counter))
    if warning_counter:
        print("Warnings:", dict(warning_counter))


if __name__ == "__main__":
    main()
