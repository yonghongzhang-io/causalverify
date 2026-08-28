#!/usr/bin/env python3
"""
audit_labels.py — Quality audit for the A1 gold subset as labeling progresses.

Runs six checks against paper_native_labels.csv (and optionally the sealed
manifest for cell-fill):
  1. Schema validity  (enums, types, required fields)
  2. Cell fill        (method × difficulty coverage vs target)
  3. Direction balance (no direction < MIN_PER_DIRECTION when n ≥ 80)
  4. Confidence distribution  (flag over/under-confidence)
  5. Time distribution  (outliers outside mean ± 2σ)
  6. Supporting-sentence quality (length, non-empty)

Usage:
    python audit_labels.py \
        --labels paper_native_labels.csv \
        --sealed-manifest sample_manifest_SEALED.csv \
        --out-dir .

    # Minimum viable (no manifest cross-check):
    python audit_labels.py --labels paper_native_labels.csv

Exit codes:
    0 — all checks passed
    1 — warnings only (progress OK, but issues to address before Gate 2)
    2 — hard failures (schema errors or missing required data)
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

METHOD_FAMILIES = ["DID", "EVENT_STUDY", "IV", "RDD", "OTHER"]
DIRECTIONS = ["positive", "negative", "mixed", "unclear"]
CONFIDENCES = ["high", "medium", "low"]
DIFFICULTY_TIERS = ["easy", "hard"]

TARGET_TOTAL = 80
PAPERS_PER_CELL = 8
CELL_FILL_THRESHOLD = 0.75           # ≥ 75% of 8 = ≥ 6 per cell
MIN_PER_DIRECTION = 15

CONFIDENCE_HIGH_MIN = 0.20           # < 20% high → under-confident
CONFIDENCE_HIGH_MAX = 0.40           # > 40% high → over-confident

TIME_MIN_MIN = 5
TIME_MAX_MIN = 90
TIME_OUTLIER_Z = 2.0

SUPPORT_MIN_CHARS = 30


# -------------------------------------------------------------------- #
# IO
# -------------------------------------------------------------------- #

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    with path.open() as f:
        return list(csv.DictReader(f))


def _is_truthy(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


# -------------------------------------------------------------------- #
# Checks
# -------------------------------------------------------------------- #

class AuditReport:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def err(self, msg: str): self.errors.append(msg)
    def warn(self, msg: str): self.warnings.append(msg)
    def inf(self, msg: str): self.info.append(msg)


def check_schema(rows: list[dict], rep: AuditReport) -> None:
    required = [
        "label_row_id", "paper_id", "annotator_id", "session_date",
        "method_family", "direction",
        "supporting_sentence_method", "supporting_sentence_direction",
        "confidence_method", "confidence_direction",
        "time_spent_minutes", "is_blind_relabel", "original_label_row_id",
    ]
    if not rows:
        rep.inf("labels file has no rows yet (labeling not started)")
        return

    for col in required:
        if col not in rows[0]:
            rep.err(f"schema: missing required column `{col}`")

    for i, r in enumerate(rows, start=1):
        row_id = r.get("label_row_id", f"<row {i}>")
        if r.get("method_family", "") not in METHOD_FAMILIES:
            rep.err(f"row {row_id}: method_family='{r.get('method_family')}' "
                    f"not in allowed set {METHOD_FAMILIES}")
        if r.get("direction", "") not in DIRECTIONS:
            rep.err(f"row {row_id}: direction='{r.get('direction')}' "
                    f"not in allowed set {DIRECTIONS}")
        if r.get("confidence_method", "") not in CONFIDENCES:
            rep.err(f"row {row_id}: confidence_method="
                    f"'{r.get('confidence_method')}' not in allowed set")
        if r.get("confidence_direction", "") not in CONFIDENCES:
            rep.err(f"row {row_id}: confidence_direction="
                    f"'{r.get('confidence_direction')}' not in allowed set")

        try:
            t = int(r.get("time_spent_minutes", ""))
            if t < TIME_MIN_MIN or t > TIME_MAX_MIN:
                rep.warn(f"row {row_id}: time_spent_minutes={t} outside "
                         f"[{TIME_MIN_MIN}, {TIME_MAX_MIN}]")
        except ValueError:
            rep.err(f"row {row_id}: time_spent_minutes="
                    f"'{r.get('time_spent_minutes')}' not an integer")

        if _is_truthy(r.get("is_blind_relabel", "")):
            orig = str(r.get("original_label_row_id", "")).strip()
            if not orig or orig == "-1":
                rep.err(f"row {row_id}: blind_relabel=True but no "
                        f"original_label_row_id set")


def check_cell_fill(rows: list[dict], sealed: dict[str, dict] | None,
                    rep: AuditReport) -> None:
    if sealed is None:
        rep.inf("cell-fill check skipped (no sealed manifest provided)")
        return
    first_pass = [r for r in rows if not _is_truthy(r.get("is_blind_relabel", ""))]
    cell_counts: dict[tuple[str, str], int] = defaultdict(int)
    for r in first_pass:
        pid = r["paper_id"]
        meta = sealed.get(pid)
        if not meta:
            rep.warn(f"paper {pid}: not in sealed manifest — "
                     f"outside A1 sampled subset?")
            continue
        mf = meta.get("method_family_phase2", "")
        diff = meta.get("difficulty_tier", "")
        cell_counts[(mf, diff)] += 1

    target_cells = [(mf, diff) for mf in METHOD_FAMILIES for diff in DIFFICULTY_TIERS]
    n_labeled = len(first_pass)
    threshold = math.ceil(PAPERS_PER_CELL * CELL_FILL_THRESHOLD)

    rep.inf(f"cell fill (labeled first-pass rows: {n_labeled} / {TARGET_TOTAL})")
    for cell in target_cells:
        count = cell_counts.get(cell, 0)
        expected_at_progress = int(PAPERS_PER_CELL * (n_labeled / TARGET_TOTAL)) if n_labeled else 0
        if n_labeled >= TARGET_TOTAL and count < threshold:
            rep.warn(f"cell {cell}: {count} / {PAPERS_PER_CELL} "
                     f"(below {threshold} threshold)")
        elif count < expected_at_progress - 1:
            rep.inf(f"cell {cell}: {count} (on-track ~{expected_at_progress})")


def check_direction_balance(rows: list[dict], rep: AuditReport) -> None:
    first_pass = [r for r in rows if not _is_truthy(r.get("is_blind_relabel", ""))]
    counts = Counter(r.get("direction", "") for r in first_pass)
    n = len(first_pass)
    rep.inf(f"direction counts (n={n}): {dict(counts)}")

    if n >= TARGET_TOTAL:
        for d in DIRECTIONS:
            if counts.get(d, 0) < MIN_PER_DIRECTION:
                rep.warn(f"direction '{d}' underrepresented: "
                         f"{counts.get(d, 0)} < {MIN_PER_DIRECTION}")


def check_confidence(rows: list[dict], rep: AuditReport) -> None:
    first_pass = [r for r in rows if not _is_truthy(r.get("is_blind_relabel", ""))]
    if not first_pass:
        return
    n = len(first_pass)
    for field in ("confidence_method", "confidence_direction"):
        high = sum(1 for r in first_pass if r.get(field) == "high")
        frac = high / n
        rep.inf(f"{field}: {high}/{n} high ({frac:.1%})")
        if frac < CONFIDENCE_HIGH_MIN:
            rep.warn(f"{field}: only {frac:.1%} high — possible "
                     f"under-confidence; review rubric clarity")
        elif frac > CONFIDENCE_HIGH_MAX:
            rep.warn(f"{field}: {frac:.1%} high — possible over-confidence "
                     f"or rubric too permissive")


def check_time(rows: list[dict], rep: AuditReport) -> None:
    first_pass = [r for r in rows if not _is_truthy(r.get("is_blind_relabel", ""))]
    times = []
    for r in first_pass:
        try:
            t = int(r.get("time_spent_minutes", ""))
            times.append((r.get("paper_id"), t))
        except ValueError:
            continue
    if len(times) < 5:
        return
    vals = [t for _, t in times]
    mean = statistics.mean(vals)
    sd = statistics.pstdev(vals)
    rep.inf(f"time per paper: mean={mean:.1f} min, sd={sd:.1f} min "
            f"(n={len(vals)})")
    if sd == 0:
        return
    for pid, t in times:
        z = (t - mean) / sd
        if abs(z) > TIME_OUTLIER_Z:
            rep.warn(f"paper {pid}: time={t} min (z={z:+.2f}) outlier")


def check_support_sentences(rows: list[dict], rep: AuditReport) -> None:
    for r in rows:
        row_id = r.get("label_row_id", "?")
        for field in ("supporting_sentence_method", "supporting_sentence_direction"):
            s = (r.get(field) or "").strip()
            if len(s) < SUPPORT_MIN_CHARS:
                rep.err(f"row {row_id}: {field} too short "
                        f"(len={len(s)} < {SUPPORT_MIN_CHARS})")


# -------------------------------------------------------------------- #
# Output
# -------------------------------------------------------------------- #

def write_report(rep: AuditReport, out_path: Path, n_rows: int) -> None:
    lines = [
        f"# A1 labeling audit report",
        f"",
        f"Generated: {date.today().isoformat()}",
        f"Rows processed: {n_rows}",
        f"",
    ]
    if rep.errors:
        lines.append(f"## Errors ({len(rep.errors)})")
        lines.extend(f"- {e}" for e in rep.errors)
        lines.append("")
    if rep.warnings:
        lines.append(f"## Warnings ({len(rep.warnings)})")
        lines.extend(f"- {w}" for w in rep.warnings)
        lines.append("")
    if rep.info:
        lines.append(f"## Info")
        lines.extend(f"- {i}" for i in rep.info)
        lines.append("")
    if not (rep.errors or rep.warnings):
        lines.append("All checks passed.")
    out_path.write_text("\n".join(lines))


def print_summary(rep: AuditReport) -> None:
    if rep.errors:
        print("\nERRORS:")
        for e in rep.errors:
            print(f"  - {e}")
    if rep.warnings:
        print("\nWARNINGS:")
        for w in rep.warnings:
            print(f"  - {w}")
    if rep.info:
        print("\nINFO:")
        for i in rep.info:
            print(f"  - {i}")
    print()
    if rep.errors:
        print(f"FAIL: {len(rep.errors)} errors, {len(rep.warnings)} warnings")
    elif rep.warnings:
        print(f"WARN: {len(rep.warnings)} warnings (no errors)")
    else:
        print("PASS: all checks clean")


# -------------------------------------------------------------------- #
# Main
# -------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description="A1 labeling quality audit")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--sealed-manifest", type=Path, default=None,
                        help="Optional sealed manifest for cell-fill check")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Where to write the audit_report_YYYYMMDD.md")
    parser.add_argument("--validate", action="store_true",
                        help="Shortcut: strict schema check only, exit 2 on errors")
    args = parser.parse_args()

    rows = _read_csv(args.labels)
    sealed = None
    if args.sealed_manifest:
        sealed_rows = _read_csv(args.sealed_manifest)
        sealed = {r["paper_id"]: r for r in sealed_rows}

    rep = AuditReport()
    check_schema(rows, rep)
    if args.validate and rep.errors:
        print_summary(rep)
        return 2

    check_cell_fill(rows, sealed, rep)
    check_direction_balance(rows, rep)
    check_confidence(rows, rep)
    check_time(rows, rep)
    check_support_sentences(rows, rep)

    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        out_path = args.out_dir / f"audit_report_{date.today().strftime('%Y%m%d')}.md"
        write_report(rep, out_path, len(rows))
        print(f"Audit report written to {out_path}")

    print_summary(rep)
    if rep.errors:
        return 2
    if rep.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
