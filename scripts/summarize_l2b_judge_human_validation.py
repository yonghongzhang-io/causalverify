#!/usr/bin/env python3
"""Summarize human validation of the L2b coefficient-extraction judge.

The script is deliberately conservative. If the annotation form is not fully
filled, it writes an incomplete status and reports no final validation metrics.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "audit/l2b_judge_human_validation"
FORM_CSV = AUDIT_DIR / "annotation_form.csv"
KEY_CSV = AUDIT_DIR / "annotation_key_private.csv"
SUMMARY_MD = AUDIT_DIR / "summary.md"
SUMMARY_JSON = AUDIT_DIR / "summary.json"

DEFAULT_L2BPLUS_TOLERANCE = 0.50


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def relative_error(estimate: float, target: float) -> float | None:
    if abs(target) <= 1e-12:
        return None
    return abs(estimate - target) / abs(target)


def numeric_agree(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-4 or (relative_error(a, b) is not None and relative_error(a, b) <= 0.01)


def human_l2bplus_pass(human_effect: float, canonical: float) -> bool:
    rel = relative_error(human_effect, canonical)
    return rel is not None and rel <= DEFAULT_L2BPLUS_TOLERANCE


def row_complete(form_row: dict[str, str]) -> bool:
    effect_present = parse_bool(form_row.get("effect_present"))
    if effect_present is False:
        return True
    if effect_present is True:
        return parse_float(form_row.get("human_effect")) is not None
    return False


def incomplete_summary(form_rows: list[dict[str, str]], key_rows: list[dict[str, str]]) -> dict[str, Any]:
    completed = sum(1 for row in form_rows if row_complete(row))
    payload = {
        "status": "incomplete",
        "n_form_rows": len(form_rows),
        "n_key_rows": len(key_rows),
        "n_completed_annotations": completed,
        "message": "Human validation annotations are incomplete; no final metrics reported.",
    }
    SUMMARY_MD.write_text(
        "# L2b Judge Human-Validation Summary\n\n"
        "**Status:** incomplete\n\n"
        "Human validation annotations are incomplete; no final metrics reported.\n\n"
        f"- Form rows: {len(form_rows)}\n"
        f"- Completed annotations: {completed}\n"
        f"- Hidden key rows: {len(key_rows)}\n",
        encoding="utf-8",
    )
    write_json(SUMMARY_JSON, payload)
    return payload


def main() -> int:
    if not KEY_CSV.exists() and (SUMMARY_MD.exists() or SUMMARY_JSON.exists()):
        # Public release: the hidden audit metadata key
        # is intentionally withheld. The completed audit summary remains
        # available in summary.md and summary.json.
        print(
            "annotation_key_private.csv is intentionally withheld from the "
            "public release because it contains hidden audit metadata. "
            "The completed reviewer-facing audit summary is available in "
            "summary.md and summary.json."
        )
        if SUMMARY_MD.exists():
            print(f"  - {SUMMARY_MD}")
        if SUMMARY_JSON.exists():
            print(f"  - {SUMMARY_JSON}")
        return 0

    if not FORM_CSV.exists() or not KEY_CSV.exists():
        raise SystemExit("Run scripts/prepare_l2b_judge_human_validation.py first.")

    form_rows = read_csv(FORM_CSV)
    key_rows = read_csv(KEY_CSV)
    key_by_id = {row["sample_id"]: row for row in key_rows}

    if len(form_rows) != len(key_rows) or any(row["sample_id"] not in key_by_id for row in form_rows):
        raise SystemExit("annotation_form.csv and annotation_key_private.csv sample_ids do not align.")

    if not form_rows or any(not row_complete(row) for row in form_rows):
        payload = incomplete_summary(form_rows, key_rows)
        print(payload["message"])
        return 0

    annotated = []
    for row in form_rows:
        key = key_by_id[row["sample_id"]]
        effect_present = parse_bool(row.get("effect_present"))
        ambiguity = parse_bool(row.get("ambiguity_flag")) or False
        human_effect = parse_float(row.get("human_effect"))
        judge_effect = parse_float(key.get("judge_effect"))
        canonical = parse_float(key.get("canonical_estimate"))
        judge_pass = parse_bool(key.get("L2b_plus_v2"))

        record = {
            "sample_id": row["sample_id"],
            "method": key["method"],
            "effect_present": effect_present,
            "ambiguity_flag": ambiguity,
            "human_effect": human_effect,
            "judge_effect": judge_effect,
            "canonical_estimate": canonical,
            "judge_l2bplus_pass": judge_pass,
        }
        if effect_present and human_effect is not None and judge_effect is not None:
            record["judge_human_numeric_agree"] = numeric_agree(judge_effect, human_effect)
        else:
            record["judge_human_numeric_agree"] = False

        if effect_present and human_effect is not None and canonical is not None and judge_pass is not None:
            record["human_l2bplus_pass"] = human_l2bplus_pass(human_effect, canonical)
            record["judge_human_pass_agree"] = record["human_l2bplus_pass"] == judge_pass
        else:
            record["human_l2bplus_pass"] = None
            record["judge_human_pass_agree"] = False
        annotated.append(record)

    n = len(annotated)
    numeric_eligible = [r for r in annotated if r["effect_present"] and r["human_effect"] is not None and r["judge_effect"] is not None]
    pass_eligible = [r for r in annotated if r["human_l2bplus_pass"] is not None]
    numeric_agreements = sum(1 for r in numeric_eligible if r["judge_human_numeric_agree"])
    pass_agreements = sum(1 for r in pass_eligible if r["judge_human_pass_agree"])
    ambiguity_count = sum(1 for r in annotated if r["ambiguity_flag"])

    disagreements_by_method: dict[str, int] = defaultdict(int)
    disagreement_examples = []
    for r in annotated:
        if not r["judge_human_numeric_agree"] or not r["judge_human_pass_agree"]:
            disagreements_by_method[r["method"]] += 1
            if len(disagreement_examples) < 10:
                disagreement_examples.append(r["sample_id"])

    payload = {
        "status": "complete",
        "n_annotated": n,
        "n_numeric_eligible": len(numeric_eligible),
        "judge_human_numeric_agreement_count": numeric_agreements,
        "judge_human_numeric_agreement_rate": numeric_agreements / len(numeric_eligible) if numeric_eligible else None,
        "n_pass_fail_eligible": len(pass_eligible),
        "judge_human_l2bplus_pass_agreement_count": pass_agreements,
        "judge_human_l2bplus_pass_agreement_rate": pass_agreements / len(pass_eligible) if pass_eligible else None,
        "l2bplus_tolerance": DEFAULT_L2BPLUS_TOLERANCE,
        "disagreement_count_by_method": dict(disagreements_by_method),
        "disagreement_examples_sample_id_only": disagreement_examples,
        "ambiguity_count": ambiguity_count,
        "ambiguity_rate": ambiguity_count / n if n else None,
    }
    write_json(SUMMARY_JSON, payload)

    lines = [
        "# L2b Judge Human-Validation Summary",
        "",
        "**Status:** complete",
        "",
        f"- N annotated: {n}",
        f"- Numeric eligible: {len(numeric_eligible)}",
        f"- Judge-human numeric agreement: {numeric_agreements}/{len(numeric_eligible)}",
        f"- Pass/fail eligible: {len(pass_eligible)}",
        f"- Judge-human L2b+ pass/fail agreement: {pass_agreements}/{len(pass_eligible)}",
        f"- Ambiguity rate: {ambiguity_count}/{n}",
        f"- Disagreement count by method: `{dict(disagreements_by_method)}`",
        f"- Example disagreements (sample_id only): `{disagreement_examples}`",
        "",
        "L2b+ pass/fail agreement uses the frozen canonical estimate and the",
        f"current default L2b+ tolerance ({DEFAULT_L2BPLUS_TOLERANCE:.0%}).",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote complete human-validation summary for {n} annotations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
