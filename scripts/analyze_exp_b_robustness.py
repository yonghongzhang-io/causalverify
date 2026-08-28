#!/usr/bin/env python3
"""Exp B robustness audit for L2b and L2b+ interpretation.

This script is read-only with respect to frozen Experiment B result artifacts.
It consumes the canonical-judge-v2 score CSV and writes derived audit tables
that separate:

- execution success (L2b),
- executed-but-wrong estimands, and
- scorer evolution from regex -> judge -> ES-aware v2.

It never calls an LLM API and never modifies frozen model outputs or primary
ranking files.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCORES_CSV = ROOT / "experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv"
SUMMARY_JSON = ROOT / "experiments/exp_b/l2b_plus_summary_canonical_judge_v2.json"
RANKING_JSON = ROOT / "experiments/exp_b/head_to_head_ranking.json"

TABLE_DIR = ROOT / "paper/tables"
AUDIT_DIR = ROOT / "audit/exp_b_robustness"

PRIMARY_MODELS = ["Kimi", "Sonnet", "GPT-4o", "o3", "Opus", "Gemini", "GPT-5"]
LLAMA_MODEL = "Llama"
TOLERANCES = [0.10, 0.25, 0.50, 0.75, 1.00]
SCORER_FIELDS = {
    "regex": ["regex_l2b_plus", "L2b_plus_regex"],
    "judge": ["L2b_plus_judge"],
    "v2": ["L2b_plus_v2"],
}
REL_ERROR_FIELDS = ["rel_error_v2", "rel_error_judge", "rel_error"]


def read_rows() -> list[dict[str, str]]:
    with SCORES_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


def as_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def rate(count: int, n: int) -> float | None:
    if n <= 0:
        return None
    return count / n


def round_rate(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def selected_field(fieldnames: set[str], candidates: list[str]) -> str | None:
    for name in candidates:
        if name in fieldnames:
            return name
    return None


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def conditional_table(rows: list[dict[str, str]], models: list[str]) -> list[dict[str, Any]]:
    out = []
    by_model = defaultdict(list)
    for row in rows:
        by_model[row["model"]].append(row)

    for model in models:
        model_rows = by_model.get(model, [])
        n = len(model_rows)
        l2b = sum(as_int(r.get("L2b")) for r in model_rows)
        v2 = sum(as_int(r.get("L2b_plus_v2")) for r in model_rows)
        out.append({
            "model": model,
            "n": n,
            "L2b_count": l2b,
            "L2b_rate": round_rate(rate(l2b, n)),
            "L2b_plus_v2_count": v2,
            "L2b_plus_v2_rate": round_rate(rate(v2, n)),
            "executed_but_not_correct_count": l2b - v2,
            "P_L2b_plus_v2_given_L2b": round_rate(rate(v2, l2b)),
            "gap_L2b_minus_L2b_plus_v2": round_rate((l2b / n - v2 / n) if n else None),
        })
    return out


def scorer_evolution(rows: list[dict[str, str]], fieldnames: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fields = {name: selected_field(fieldnames, candidates) for name, candidates in SCORER_FIELDS.items()}
    missing = {name: candidates for name, candidates in SCORER_FIELDS.items() if fields[name] is None}
    by_model = defaultdict(list)
    for row in rows:
        if row["model"] in PRIMARY_MODELS:
            by_model[row["model"]].append(row)

    out = []
    for model in PRIMARY_MODELS:
        model_rows = by_model.get(model, [])
        n = len(model_rows)
        record: dict[str, Any] = {"model": model, "n": n}
        for label in ("regex", "judge", "v2"):
            field = fields[label]
            if field is None:
                record[f"{label}_pass_count"] = ""
                record[f"{label}_pass_rate"] = ""
            else:
                count = sum(as_int(r.get(field)) for r in model_rows)
                record[f"{label}_pass_count"] = count
                record[f"{label}_pass_rate"] = round_rate(rate(count, n))
        judge_rate = record["judge_pass_rate"] if record["judge_pass_rate"] != "" else None
        regex_rate = record["regex_pass_rate"] if record["regex_pass_rate"] != "" else None
        v2_rate = record["v2_pass_rate"] if record["v2_pass_rate"] != "" else None
        record["delta_judge_v2_minus_judge"] = (
            round_rate(v2_rate - judge_rate) if v2_rate is not None and judge_rate is not None else ""
        )
        record["delta_judge_minus_regex"] = (
            round_rate(judge_rate - regex_rate) if judge_rate is not None and regex_rate is not None else ""
        )
        out.append(record)
    metadata = {
        "selected_fields": fields,
        "missing_fields": missing,
        "interpretation": "Deltas are rate differences. v2 is ES-aware canonical-judge-v2 scoring.",
    }
    return out, metadata


def method_breakdown(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["model"] in PRIMARY_MODELS:
            groups[(row["model"], row["method"])].append(row)

    out = []
    methods = sorted({method for _, method in groups})
    for model in PRIMARY_MODELS:
        for method in methods:
            group_rows = groups.get((model, method), [])
            n = len(group_rows)
            l2b = sum(as_int(r.get("L2b")) for r in group_rows)
            v2 = sum(as_int(r.get("L2b_plus_v2")) for r in group_rows)
            out.append({
                "model": model,
                "method": method,
                "n": n,
                "L2b_count": l2b,
                "L2b_plus_v2_count": v2,
                "L2b_plus_v2_rate": round_rate(rate(v2, n)),
                "P_L2b_plus_v2_given_L2b": round_rate(rate(v2, l2b)),
            })
    return out


def tolerance_sweep(rows: list[dict[str, str]], fieldnames: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    rel_error_field = selected_field(fieldnames, REL_ERROR_FIELDS)
    if rel_error_field is None:
        return [], None

    sweep_rows: list[dict[str, Any]] = []
    rankings: dict[str, list[str]] = {}

    for tol in TOLERANCES:
        tol_key = f"{tol:.2f}"
        rates_for_rank: dict[str, float] = {}
        for model in PRIMARY_MODELS:
            model_rows = [r for r in rows if r["model"] == model and as_int(r.get("L2b")) == 1]
            eligible = []
            for row in model_rows:
                err = as_float(row.get(rel_error_field))
                if err is not None:
                    eligible.append(err)
            passed = sum(1 for err in eligible if err <= tol)
            n = len(eligible)
            pass_rate = rate(passed, n)
            rates_for_rank[model] = pass_rate if pass_rate is not None else -1.0
            sweep_rows.append({
                "tolerance": tol,
                "model": model,
                "n_executed_with_relative_error": n,
                "pass_count": passed,
                "pass_rate": round_rate(pass_rate),
            })
        rankings[tol_key] = sorted(PRIMARY_MODELS, key=lambda m: (-rates_for_rank[m], PRIMARY_MODELS.index(m)))

    metadata = {
        "tolerances": TOLERANCES,
        "relative_error_field_used": rel_error_field,
        "denominator": "Rows with L2b=1 and a defined relative-error field.",
        "rankings": rankings,
    }
    return sweep_rows, metadata


def write_audit_readme(primary_rows: list[dict[str, Any]], llama_rows: list[dict[str, Any]]) -> None:
    def line_for(row: dict[str, Any]) -> str:
        return (
            f"| {row['model']} | {row['n']} | {row['L2b_count']} "
            f"({row['L2b_rate']:.2f}) | {row['L2b_plus_v2_count']} "
            f"({row['L2b_plus_v2_rate']:.2f}) | {row['executed_but_not_correct_count']} | "
            f"{row['P_L2b_plus_v2_given_L2b']:.2f} |"
        )

    lines = [
        "# Exp B Robustness Audit",
        "",
        "This audit strengthens the interpretation of Exp B without replacing the",
        "frozen headline L2b+ artifacts. It is derived from",
        "`experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv` and does not",
        "make LLM API calls or regenerate model outputs.",
        "",
        "## Interpretation",
        "",
        "- L2b+ requires L2b, so a raw association between L2b and L2b+ is partly",
        "  structural: code must execute before a coefficient can be checked.",
        "- The conditional metric `P(L2b+ v2 | L2b)` asks a sharper question:",
        "  among outputs whose code executed, how often did the workflow compute",
        "  the canonical treatment-effect estimate on the realised dataset?",
        "- Primary-7 results are kept separate from Llama. Llama-3.3-70B-Instruct",
        "  is retained only as an open-weights robustness check and is not part of",
        "  the primary 7-model Kendall/Spearman ranking.",
        "- L2b+ means coefficient agreement with the canonical estimator on the",
        "  realised dataset, not recovery of the ideal DGP beta parameter.",
        "",
        "## Primary-7 Conditional L2b Table",
        "",
        "| Model | n | L2b | L2b+ v2 | Executed but not correct | P(L2b+ v2 given L2b) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(line_for(row) for row in primary_rows)
    lines.extend([
        "",
        "## Llama Robustness-Only Result",
        "",
    ])
    lines.extend([
        "| Model | n | L2b | L2b+ v2 | Executed but not correct | P(L2b+ v2 given L2b) |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    lines.extend(line_for(row) for row in llama_rows)
    lines.extend([
        "",
        "## Generated Files",
        "",
        "- `paper/tables/exp_b_l2b_conditional_primary7.csv`",
        "- `paper/tables/exp_b_scorer_evolution_primary7.csv`",
        "- `paper/tables/exp_b_l2bplus_by_model_method_primary7.csv`",
        "- `paper/tables/exp_b_tolerance_sweep_primary7.csv`",
        "- `audit/exp_b_robustness/l2b_conditional_primary7.json`",
        "- `audit/exp_b_robustness/l2b_conditional_llama_robustness.json`",
        "- `audit/exp_b_robustness/scorer_evolution_primary7.json`",
        "- `audit/exp_b_robustness/l2bplus_by_model_method_primary7.json`",
        "- `audit/exp_b_robustness/tolerance_sweep_primary7.json`",
        "",
    ])
    (AUDIT_DIR / "README.md").write_text("\n".join(lines))


def main() -> int:
    rows = read_rows()
    if not rows:
        raise SystemExit("No rows found in Exp B score CSV.")
    fieldnames = set(rows[0].keys())
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    primary_conditional = conditional_table(rows, PRIMARY_MODELS)
    llama_conditional = conditional_table(rows, [LLAMA_MODEL])

    conditional_fields = [
        "model",
        "n",
        "L2b_count",
        "L2b_rate",
        "L2b_plus_v2_count",
        "L2b_plus_v2_rate",
        "executed_but_not_correct_count",
        "P_L2b_plus_v2_given_L2b",
        "gap_L2b_minus_L2b_plus_v2",
    ]
    write_csv(TABLE_DIR / "exp_b_l2b_conditional_primary7.csv", primary_conditional, conditional_fields)
    write_json(AUDIT_DIR / "l2b_conditional_primary7.json", {
        "source": str(SCORES_CSV.relative_to(ROOT)),
        "primary_models": PRIMARY_MODELS,
        "rows": primary_conditional,
    })
    write_json(AUDIT_DIR / "l2b_conditional_llama_robustness.json", {
        "source": str(SCORES_CSV.relative_to(ROOT)),
        "robustness_only_model": LLAMA_MODEL,
        "rows": llama_conditional,
    })

    scorer_rows, scorer_meta = scorer_evolution(rows, fieldnames)
    scorer_fields = [
        "model",
        "n",
        "regex_pass_count",
        "regex_pass_rate",
        "judge_pass_count",
        "judge_pass_rate",
        "v2_pass_count",
        "v2_pass_rate",
        "delta_judge_v2_minus_judge",
        "delta_judge_minus_regex",
    ]
    write_csv(TABLE_DIR / "exp_b_scorer_evolution_primary7.csv", scorer_rows, scorer_fields)
    write_json(AUDIT_DIR / "scorer_evolution_primary7.json", {
        "source": str(SCORES_CSV.relative_to(ROOT)),
        "primary_models": PRIMARY_MODELS,
        "metadata": scorer_meta,
        "rows": scorer_rows,
    })

    method_rows = method_breakdown(rows)
    method_fields = [
        "model",
        "method",
        "n",
        "L2b_count",
        "L2b_plus_v2_count",
        "L2b_plus_v2_rate",
        "P_L2b_plus_v2_given_L2b",
    ]
    write_csv(TABLE_DIR / "exp_b_l2bplus_by_model_method_primary7.csv", method_rows, method_fields)
    write_json(AUDIT_DIR / "l2bplus_by_model_method_primary7.json", {
        "source": str(SCORES_CSV.relative_to(ROOT)),
        "primary_models": PRIMARY_MODELS,
        "rows": method_rows,
    })

    sweep_rows, sweep_meta = tolerance_sweep(rows, fieldnames)
    if sweep_meta is None:
        (AUDIT_DIR / "tolerance_sweep_unavailable.md").write_text(
            "# Tolerance sweep unavailable\n\n"
            "No usable relative-error fields were found in "
            "`experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv`.\n"
        )
    else:
        sweep_fields = ["tolerance", "model", "n_executed_with_relative_error", "pass_count", "pass_rate"]
        write_csv(TABLE_DIR / "exp_b_tolerance_sweep_primary7.csv", sweep_rows, sweep_fields)
        write_json(AUDIT_DIR / "tolerance_sweep_primary7.json", {
            "source": str(SCORES_CSV.relative_to(ROOT)),
            "primary_models": PRIMARY_MODELS,
            "metadata": sweep_meta,
            "rows": sweep_rows,
        })

    write_audit_readme(primary_conditional, llama_conditional)

    # Lightweight sanity check that primary ranking remains 7-model and Llama-free.
    if RANKING_JSON.exists():
        ranking = json.loads(RANKING_JSON.read_text())
        if ranking.get("n_models") != 7:
            raise SystemExit(f"Expected head_to_head_ranking.json n_models=7, got {ranking.get('n_models')}")
        if "Llama" in json.dumps(ranking.get("rankings", {})):
            raise SystemExit("Llama appears in primary head_to_head_ranking.json rankings.")

    print("Wrote Exp B robustness audit:")
    print(f"- {TABLE_DIR / 'exp_b_l2b_conditional_primary7.csv'}")
    print(f"- {TABLE_DIR / 'exp_b_scorer_evolution_primary7.csv'}")
    print(f"- {TABLE_DIR / 'exp_b_l2bplus_by_model_method_primary7.csv'}")
    if sweep_meta is None:
        print(f"- {AUDIT_DIR / 'tolerance_sweep_unavailable.md'}")
    else:
        print(f"- {TABLE_DIR / 'exp_b_tolerance_sweep_primary7.csv'}")
    print(f"- {AUDIT_DIR / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
