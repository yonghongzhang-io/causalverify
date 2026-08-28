#!/usr/bin/env python3
"""Compare paper-native human labels against the 4-LLM consensus GT.

This is a post-labeling audit script. It should be run only after human
labels are saved; it does not assist classification and does not expose labels
during annotation.

Outputs:
  audit/human_gold/human_vs_llm_consensus.csv
  audit/human_gold/human_vs_llm_consensus.md
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

DEFAULT_LABELS = HERE / "paper_native_labels.csv"
DEFAULT_GT = ROOT / "audit/gt_aggregate_decisions.json"
DEFAULT_TARGET = HERE / "target30_manifest_blinded.csv"
DEFAULT_OUT_CSV = HERE / "human_vs_llm_consensus.csv"
DEFAULT_OUT_MD = HERE / "human_vs_llm_consensus.md"

METHODS = ["DID", "EVENT_STUDY", "IV", "RDD", "OTHER"]
DIRECTIONS = ["positive", "negative", "mixed", "unclear"]


def read_csv(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def cohen_kappa(pairs: list[tuple[str, str]], classes: list[str]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in classes)
    if pe == 1:
        return 1.0 if po == 1.0 else None
    return (po - pe) / (1 - pe)


def pct(num: int, den: int) -> str:
    return "NA" if den == 0 else f"{100 * num / den:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    ap.add_argument("--gt", type=Path, default=DEFAULT_GT)
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    ap.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = ap.parse_args()

    labels = [
        r for r in read_csv(args.labels)
        if not truthy(r.get("is_blind_relabel", ""))
    ]
    gt = {r["paper_id"]: r for r in json.loads(args.gt.read_text())}
    target = {r["paper_id"]: r for r in read_csv(args.target)} if args.target.exists() else {}

    rows: list[dict] = []
    for r in labels:
        pid = r["paper_id"]
        g = gt.get(pid)
        if not g:
            continue
        h_method = r["method_family"]
        h_dir = r["direction"]
        llm_method = g.get("new_method", "")
        llm_dir = g.get("new_direction", "")
        row = {
            "paper_id": pid,
            "in_target30": "1" if pid in target else "0",
            "human_method": h_method,
            "llm_consensus_method": llm_method,
            "method_match": "1" if h_method == llm_method else "0",
            "human_direction": h_dir,
            "llm_consensus_direction": llm_dir,
            "direction_match": "1" if h_dir == llm_dir else "0",
            "m_level": g.get("m_level", ""),
            "d_level": g.get("d_level", ""),
            "needs_human": str(g.get("needs_human", "")),
            "human_conf_method": r.get("confidence_method", ""),
            "human_conf_direction": r.get("confidence_direction", ""),
            "time_spent_minutes": r.get("time_spent_minutes", ""),
            "notes": r.get("notes", ""),
        }
        rows.append(row)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "paper_id", "in_target30",
        "human_method", "llm_consensus_method", "method_match",
        "human_direction", "llm_consensus_direction", "direction_match",
        "m_level", "d_level", "needs_human",
        "human_conf_method", "human_conf_direction", "time_spent_minutes",
        "notes",
    ]
    with args.out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    method_matches = sum(r["method_match"] == "1" for r in rows)
    dir_scoreable = [r for r in rows if r["llm_consensus_direction"] in DIRECTIONS]
    dir_matches = sum(r["direction_match"] == "1" for r in dir_scoreable)

    method_pairs = [
        (r["human_method"], r["llm_consensus_method"])
        for r in rows
        if r["human_method"] in METHODS and r["llm_consensus_method"] in METHODS
    ]
    dir_pairs = [
        (r["human_direction"], r["llm_consensus_direction"])
        for r in rows
        if r["human_direction"] in DIRECTIONS and r["llm_consensus_direction"] in DIRECTIONS
    ]
    k_method = cohen_kappa(method_pairs, METHODS)
    k_dir = cohen_kappa(dir_pairs, DIRECTIONS)

    by_level: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_level[r["m_level"]]["n"] += 1
        by_level[r["m_level"]]["method_match"] += int(r["method_match"])

    target_n = sum(r["in_target30"] == "1" for r in rows)
    target_pending = max(0, 30 - target_n)

    md = [
        "# Human vs 4-LLM consensus audit",
        "",
        f"Labels file: `{args.labels.relative_to(ROOT)}`",
        f"GT file: `{args.gt.relative_to(ROOT)}`",
        f"Output CSV: `{args.out_csv.relative_to(ROOT)}`",
        "",
        "## Progress",
        "",
        f"- First-pass human labels compared: {n}",
        f"- Target30 completed: {target_n}/30",
        f"- Target30 pending: {target_pending}",
        "",
        "## Agreement",
        "",
        f"- Method-family simple agreement: {method_matches}/{n} = {pct(method_matches, n)}",
        f"- Method-family Cohen kappa: {'NA' if k_method is None else f'{k_method:.3f}'}",
        f"- Direction simple agreement: {dir_matches}/{len(dir_scoreable)} = {pct(dir_matches, len(dir_scoreable))}",
        f"- Direction Cohen kappa: {'NA' if k_dir is None else f'{k_dir:.3f}'}",
        "",
        "## Method agreement by 4-LLM consensus level",
        "",
        "| m_level | n | method match |",
        "|---|---:|---:|",
    ]
    for level, c in sorted(by_level.items()):
        md.append(f"| {level or 'NA'} | {c['n']} | {pct(c['method_match'], c['n'])} |")
    md.extend([
        "",
        "## Interpretation guardrail",
        "",
        "This audit validates the 4-LLM consensus labels against a paper-native",
        "human slice. It does not make the full 259-paper Exp A corpus",
        "human-gold labeled. If Target30 is incomplete, report these numbers as",
        "progress-only and do not use them as final paper evidence.",
        "",
    ])
    args.out_md.write_text("\n".join(md))

    print(f"Wrote {args.out_csv}")
    print(f"Wrote {args.out_md}")
    print(f"Target30 progress: {target_n}/30")
    print(f"Method agreement: {method_matches}/{n} = {pct(method_matches, n)}")
    print(f"Direction agreement: {dir_matches}/{len(dir_scoreable)} = {pct(dir_matches, len(dir_scoreable))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
