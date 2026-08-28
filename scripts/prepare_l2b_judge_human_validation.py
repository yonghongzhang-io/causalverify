#!/usr/bin/env python3
"""Prepare a blinded human-validation form for the L2b coefficient judge.

This script samples frozen Exp B cells whose model-written R code executed
(L2b=1), replays the existing R code locally to capture stdout excerpts, and
writes two files:

- annotation_form.csv: blinded form for human coefficient extraction.
- annotation_key_private.csv: hidden metadata for later judge-vs-human audit.

It never calls an LLM API and does not modify frozen score artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCORES_CSV = ROOT / "experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv"
OUTPUTS_DIR = ROOT / "experiments/exp_b/outputs"
SCENARIOS_DIR = ROOT / "experiments/exp_b/scenarios"
JUDGE_CACHE = ROOT / "audit/l2b_judge_cache.json"
OUT_DIR = ROOT / "audit/l2b_judge_human_validation"

PRIMARY_MODELS = ["Kimi", "Sonnet", "GPT-4o", "o3", "Opus", "Gemini", "GPT-5"]
METHODS = ["DID", "EVENT_STUDY", "IV", "RDD"]
ANNOTATOR_INSTRUCTIONS = (
    "Read the R code and stdout excerpt. Identify the scalar treatment-effect "
    "coefficient that the executed code reports for the design indicated by the "
    "method family. Do not infer from correctness or expected sign. If no "
    "treatment-effect coefficient is present, set effect_present=0 and leave "
    "human_effect blank. If ambiguous, set ambiguity_flag=1 and explain why."
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def as_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def extract_r_code(text: str) -> str | None:
    """Extract the first R code block from a markdown response."""
    m = re.search(r"```(?:r|R)\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
    if m and re.search(r"\b(library|lm|read\.csv|read_csv|ivreg|rdrobust)\s*\(", m.group(1)):
        return m.group(1).strip()
    return None


def output_path_for(row: dict[str, str]) -> Path:
    return OUTPUTS_DIR / f"{row['scenario_id']}_{row['model_slug']}.json"


def load_output_content(row: dict[str, str]) -> str:
    path = output_path_for(row)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("llm_response", {}).get("content", "")


def load_title(row: dict[str, str]) -> str:
    path = SCENARIOS_DIR / f"{row['scenario_id']}.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("title", "")


def excerpt(text: str, limit: int = 5000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    half = max(1, (limit - 80) // 2)
    return text[:half].rstrip() + "\n\n[... middle truncated ...]\n\n" + text[-half:].lstrip()


def execute_r_code(code: str, timeout: int) -> tuple[bool, str, str]:
    """Replay existing R code locally and return (ok, stdout, stderr_excerpt)."""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".R", mode="w", delete=False, dir="/tmp", encoding="utf-8") as f:
            f.write("options(warn = -1)\n")
            f.write("suppressPackageStartupMessages({\n")
            f.write(code)
            f.write("\n})\n")
            tmp = f.name
        result = subprocess.run(
            ["Rscript", "--vanilla", tmp],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout, result.stderr.strip()[-2000:]
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as exc:  # pragma: no cover - environment dependent
        return False, "", str(exc)
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def scorer_priority(row: dict[str, str]) -> int:
    """Prioritize rows where scorer evolution changed the pass/fail label."""
    regex = row.get("regex_l2b_plus")
    judge = row.get("L2b_plus_judge")
    v2 = row.get("L2b_plus_v2")
    if regex == "0" and judge == "1":
        return 3
    if judge != "" and v2 != "" and judge != v2:
        return 2
    if regex != "" and judge != "" and regex != judge:
        return 1
    return 0


def candidate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        if row.get("model") not in PRIMARY_MODELS:
            continue
        if row.get("method") not in METHODS:
            continue
        if as_int(row.get("L2b")) != 1:
            continue
        if not output_path_for(row).exists():
            continue
        row = dict(row)
        row["_priority"] = str(scorer_priority(row))
        out.append(row)
    return out


def choose_sample(rows: list[dict[str, str]], n: int, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["method"], row["model"], row["L2b_plus_v2"])].append(row)

    # Method quotas keep the final sample balanced across DGP families.
    base = n // len(METHODS)
    quotas = {method: base for method in METHODS}
    for method in METHODS[: n % len(METHODS)]:
        quotas[method] += 1

    selected: list[dict[str, str]] = []
    selected_keys: set[tuple[str, str]] = set()

    for method in METHODS:
        method_groups = [(key, vals) for key, vals in groups.items() if key[0] == method]
        rng.shuffle(method_groups)
        method_groups.sort(key=lambda kv: -max(int(v["_priority"]) for v in kv[1]))
        for key, vals in method_groups:
            if sum(1 for row in selected if row["method"] == method) >= quotas[method]:
                break
            vals = list(vals)
            rng.shuffle(vals)
            vals.sort(key=lambda row: -int(row["_priority"]))
            row = vals[0]
            selected.append(row)
            selected_keys.add((row["scenario_id"], row["model_slug"]))

    # Fill any shortfall from the remaining highest-priority rows.
    remaining = [
        row for row in rows
        if (row["scenario_id"], row["model_slug"]) not in selected_keys
    ]
    rng.shuffle(remaining)
    remaining.sort(key=lambda row: -int(row["_priority"]))
    for row in remaining:
        if len(selected) >= n:
            break
        selected.append(row)
        selected_keys.add((row["scenario_id"], row["model_slug"]))

    # If possible, repair missing model coverage by replacing duplicate-model
    # low-priority rows from overrepresented models.
    by_model = Counter(row["model"] for row in selected)
    missing_models = [m for m in PRIMARY_MODELS if by_model[m] == 0]
    for model in missing_models:
        pool = [row for row in remaining if row["model"] == model and (row["scenario_id"], row["model_slug"]) not in selected_keys]
        if not pool:
            continue
        rng.shuffle(pool)
        pool.sort(key=lambda row: -int(row["_priority"]))
        replacement = pool[0]
        replace_idx = None
        for idx, row in sorted(enumerate(selected), key=lambda item: int(item[1]["_priority"])):
            if by_model[row["model"]] > 1:
                replace_idx = idx
                break
        if replace_idx is None:
            continue
        removed = selected[replace_idx]
        selected_keys.discard((removed["scenario_id"], removed["model_slug"]))
        by_model[removed["model"]] -= 1
        selected[replace_idx] = replacement
        selected_keys.add((replacement["scenario_id"], replacement["model_slug"]))
        by_model[replacement["model"]] += 1

    selected.sort(key=lambda row: (METHODS.index(row["method"]), row["scenario_id"], PRIMARY_MODELS.index(row["model"])))
    return selected[:n]


def load_judge_cache() -> dict[str, dict[str, Any]]:
    if not JUDGE_CACHE.exists():
        return {}
    data = json.loads(JUDGE_CACHE.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_forms(sample: list[dict[str, str]], timeout: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    judge_cache = load_judge_cache()
    form_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(sample, start=1):
        sample_id = f"l2bjhv_{idx:03d}"
        content = load_output_content(row)
        code = extract_r_code(content) or ""
        ok, stdout, stderr = execute_r_code(code, timeout=timeout) if code else (False, "", "no R code block found")
        cache_key = f"{row['scenario_id']}__{row['model_slug']}"
        cache_row = judge_cache.get(cache_key, {})

        form_rows.append({
            "sample_id": sample_id,
            "method": row["method"],
            "scenario_id": row["scenario_id"],
            "scenario_title": load_title(row),
            "annotator_instructions": ANNOTATOR_INSTRUCTIONS,
            "r_code_excerpt": excerpt(code, 6000),
            "r_stdout_excerpt": excerpt(stdout if stdout.strip() else "[stdout empty]", 6000),
            "human_effect": "",
            "effect_present": "",
            "ambiguity_flag": "",
            "target_term": "",
            "human_rationale": "",
        })
        key_rows.append({
            "sample_id": sample_id,
            "scenario_id": row["scenario_id"],
            "model": row["model"],
            "model_slug": row["model_slug"],
            "method": row["method"],
            "L2b": row.get("L2b", ""),
            "L2b_plus_v2": row.get("L2b_plus_v2", ""),
            "judge_effect": row.get("judge_effect", ""),
            "canonical_estimate": row.get("baseline_effect", ""),
            "rel_error_v2": row.get("rel_error_v2", ""),
            "regex_estimated": row.get("regex_estimated", ""),
            "regex_l2b_plus": row.get("regex_l2b_plus", ""),
            "L2b_plus_judge": row.get("L2b_plus_judge", ""),
            "rel_error_judge": row.get("rel_error_judge", ""),
            "scorer_priority": row.get("_priority", ""),
            "judge_cache_effect": cache_row.get("judge_effect", ""),
            "judge_cache_rationale": cache_row.get("judge_rationale", ""),
            "output_path": str(output_path_for(row).relative_to(ROOT)),
            "replayed_ok": int(ok),
            "r_stderr_excerpt": stderr,
        })
        replay_rows.append({
            "sample_id": sample_id,
            "scenario_id": row["scenario_id"],
            "method": row["method"],
            "model": row["model"],
            "replayed_ok": int(ok),
            "stdout_chars": len(stdout),
            "stderr_chars": len(stderr),
        })
    return form_rows, key_rows, replay_rows


def write_protocol_readme(n: int, seed: int, distribution: dict[str, Any]) -> None:
    lines = [
        "# L2b Judge Human-Validation Scaffold",
        "",
        "This directory contains a blinded human-validation scaffold for the",
        "coefficient-extraction judge used in Exp B L2b+ scoring.",
        "",
        "## Purpose",
        "",
        "The purpose is to validate coefficient extraction, not causal correctness.",
        "The human annotator sees executed R code/stdout and identifies the scalar",
        "treatment-effect coefficient reported by that code. The target is the",
        "coefficient the code reports, not whether the code used the right method.",
        "",
        "## Blinding Protocol",
        "",
        "- The annotator form omits model identity, L2b+ labels, canonical estimates,",
        "  judge effects, regex effects, and primary-ranking information.",
        "- `annotation_key_private.csv` stores hidden metadata for the later audit.",
        "- Human annotators should not open the private key while filling",
        "  `annotation_form.csv`.",
        "",
        "## Files",
        "",
        "- `annotation_form.csv`: blinded form to fill.",
        "- `annotation_key_private.csv`: hidden key for reproducibility and scoring.",
        "- `sample_distribution.json`: realised sample distribution and replay status.",
        "- `summary.md` / `summary.json`: produced by the summary script.",
        "",
        "## Annotation Columns",
        "",
        "- `human_effect`: scalar coefficient value reported in stdout.",
        "- `effect_present`: `1` if a treatment-effect coefficient is present, else `0`.",
        "- `ambiguity_flag`: `1` if multiple plausible target coefficients exist.",
        "- `target_term`: variable/term name used for the coefficient.",
        "- `human_rationale`: short explanation for the extraction decision.",
        "",
        "## Status",
        "",
        "This scaffold is incomplete until `annotation_form.csv` has human-filled",
        "`human_effect` / `effect_present` values. Do not report final human-validation",
        "metrics until `scripts/summarize_l2b_judge_human_validation.py` reports a",
        "completed summary.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"python3 scripts/prepare_l2b_judge_human_validation.py --n {n} --seed {seed}",
        "python3 scripts/summarize_l2b_judge_human_validation.py",
        "```",
        "",
        "## Realised Sample Distribution",
        "",
        f"- Requested N: {n}",
        f"- Seed: {seed}",
        f"- Sampled rows: {distribution['n_sampled']}",
        f"- Replay OK rows: {distribution['replay_ok']}",
        f"- By method: `{distribution['by_method']}`",
        f"- By hidden model: `{distribution['by_model']}`",
        f"- By L2b+ v2 label in hidden key: `{distribution['by_l2b_plus_v2']}`",
        f"- Scorer-disagreement rows: {distribution['scorer_disagreement_rows']}",
        "",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50, help="Target sample size.")
    parser.add_argument("--seed", type=int, default=20260502, help="Deterministic sampling seed.")
    parser.add_argument("--timeout", type=int, default=60, help="R execution timeout per sampled cell.")
    args = parser.parse_args()

    rows = candidate_rows(read_csv(SCORES_CSV))
    if not rows:
        raise SystemExit("No primary-model L2b=1 rows available for sampling.")

    sample = choose_sample(rows, min(args.n, len(rows)), args.seed)
    form_rows, key_rows, replay_rows = build_forms(sample, timeout=args.timeout)

    form_fields = [
        "sample_id",
        "method",
        "scenario_id",
        "scenario_title",
        "annotator_instructions",
        "r_code_excerpt",
        "r_stdout_excerpt",
        "human_effect",
        "effect_present",
        "ambiguity_flag",
        "target_term",
        "human_rationale",
    ]
    key_fields = [
        "sample_id",
        "scenario_id",
        "model",
        "model_slug",
        "method",
        "L2b",
        "L2b_plus_v2",
        "judge_effect",
        "canonical_estimate",
        "rel_error_v2",
        "regex_estimated",
        "regex_l2b_plus",
        "L2b_plus_judge",
        "rel_error_judge",
        "scorer_priority",
        "judge_cache_effect",
        "judge_cache_rationale",
        "output_path",
        "replayed_ok",
        "r_stderr_excerpt",
    ]
    write_csv(OUT_DIR / "annotation_form.csv", form_rows, form_fields)
    write_csv(OUT_DIR / "annotation_key_private.csv", key_rows, key_fields)

    distribution = {
        "n_requested": args.n,
        "n_sampled": len(sample),
        "seed": args.seed,
        "by_method": dict(Counter(row["method"] for row in key_rows)),
        "by_model": dict(Counter(row["model"] for row in key_rows)),
        "by_l2b_plus_v2": dict(Counter(str(row["L2b_plus_v2"]) for row in key_rows)),
        "scorer_disagreement_rows": sum(
            1 for row in key_rows
            if row["regex_l2b_plus"] != row["L2b_plus_judge"]
            or row["L2b_plus_judge"] != row["L2b_plus_v2"]
        ),
        "replay_ok": sum(int(row["replayed_ok"]) for row in replay_rows),
        "replay": replay_rows,
    }
    write_json(OUT_DIR / "sample_distribution.json", distribution)
    write_protocol_readme(args.n, args.seed, distribution)

    print("Prepared L2b judge human-validation scaffold:")
    print(f"- {OUT_DIR / 'annotation_form.csv'}")
    print(f"- {OUT_DIR / 'annotation_key_private.csv'}")
    print(f"- {OUT_DIR / 'README.md'}")
    print(f"Sampled {len(sample)} rows; replay OK: {distribution['replay_ok']}/{len(sample)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
