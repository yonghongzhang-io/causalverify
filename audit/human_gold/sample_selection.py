#!/usr/bin/env python3
"""
sample_selection.py — A1 paper-native gold subset sampler.

Selects 80 papers from the CAUSAL-BENCH corpus, stratified by:
  primary   : method_family (5) × difficulty (2) = 10 cells × 8 papers
  secondary : conclusion_direction balanced as post-hoc constraint (≥ 15 per direction)

Reads Phase 2 aggregate labels and Phase 1 source-type flags from the `audit/`
tree. Writes a manifest split into VISIBLE (annotator-safe) and SEALED (contains
Phase 2 labels, opened only after labeling) files.

Usage:
    python sample_selection.py \
        --audit-root .. \
        --out-dir . \
        --seed 20260423

This version is adapted to the CAUSAL-BENCH v11 data shape:
  - `audit/gt_aggregate_decisions.json` is a LIST of per-paper records
  - Consensus levels use `m_level` / `d_level` (not `consensus_level`)
    with values {all4_agree, 3of4_agree, 2of4_plurality, 2of4_tie, split}
  - `audit/regen_from_pdf.json` is a LIST of records with `source_type`
    values {pdf_first_8_pages, openalex_abstract}
  - Method families as written in this corpus: {DID, EVENT_STUDY, IV, RDD, OTHER}
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# -------------------------------------------------------------------- #
# Configuration
# -------------------------------------------------------------------- #

# Method families as stored in the corpus (note caps + underscore for EVENT_STUDY)
METHOD_FAMILIES = ["DID", "EVENT_STUDY", "IV", "RDD", "OTHER"]
DIRECTIONS = ["positive", "negative", "mixed", "unclear"]
DIFFICULTY_TIERS = ["easy", "hard"]

TARGET_TOTAL = 80
PAPERS_PER_CELL = 8
MIN_PER_DIRECTION = 15
MAX_DIRECTION_SWAPS_PCT = 0.10

# Phase 2 consensus-level → difficulty mapping for OUR m_level values.
# "easy" = strong agreement; "hard" = contested / required adjudication.
EASY_M_LEVELS = {"all4_agree", "3of4_agree"}
HARD_M_LEVELS = {"2of4_plurality", "2of4_tie", "split"}

# Eligibility: which Phase 1 source types count as "usable for human labeling"?
ACCEPTABLE_SOURCE_TYPES = {"pdf_first_8_pages"}   # we want a PDF, not just abstract


# -------------------------------------------------------------------- #
# Data model
# -------------------------------------------------------------------- #

@dataclass
class PaperRecord:
    paper_id: str
    method_family_phase2: str
    direction_phase2: str
    consensus_level: str            # stored as m_level for traceability
    difficulty: str                 # "easy" | "hard" | "unknown"
    source_type: str                # "pdf_first_8_pages" | "openalex_abstract" | ...
    pdf_path: Path | None
    eligible: bool
    ineligible_reason: str | None = None

    def cell(self) -> tuple[str, str]:
        return (self.method_family_phase2, self.difficulty)


@dataclass
class SelectionResult:
    selected: list[PaperRecord] = field(default_factory=list)
    per_cell_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    per_direction_counts: dict[str, int] = field(default_factory=dict)
    shortfalls: list[str] = field(default_factory=list)
    direction_swaps: list[str] = field(default_factory=list)


# -------------------------------------------------------------------- #
# Loading
# -------------------------------------------------------------------- #

def _classify_difficulty(m_level: str) -> str:
    c = str(m_level).strip().lower()
    if c in EASY_M_LEVELS:
        return "easy"
    if c in HARD_M_LEVELS:
        return "hard"
    return "unknown"


def _as_dict_by_paper_id(raw: Any) -> dict[str, dict]:
    """Accept either a list of records (with paper_id) or a dict keyed by paper_id."""
    if isinstance(raw, list):
        return {r["paper_id"]: r for r in raw if isinstance(r, dict) and "paper_id" in r}
    if isinstance(raw, dict):
        return raw
    raise TypeError(f"unsupported JSON root type: {type(raw).__name__}")


def load_corpus(audit_root: Path, log: logging.Logger) -> list[PaperRecord]:
    """Merge Phase 2 labels + Phase 1 source types + PDF presence into PaperRecords."""
    gt_path = audit_root / "gt_aggregate_decisions.json"
    regen_path = audit_root / "regen_from_pdf.json"
    pdfs_dir = audit_root / "pdfs"

    if not gt_path.exists():
        log.error("Missing %s", gt_path)
        sys.exit(2)
    if not regen_path.exists():
        log.error("Missing %s", regen_path)
        sys.exit(2)

    gt = _as_dict_by_paper_id(json.load(gt_path.open()))
    regen = _as_dict_by_paper_id(json.load(regen_path.open()))

    records: list[PaperRecord] = []
    for paper_id, gt_row in gt.items():
        # Corpus-specific field names:
        method = str(gt_row.get("new_method", gt_row.get("method_family", ""))).strip().upper()
        # Normalize "Event Study" ↔ "EVENT_STUDY"
        method = method.replace(" ", "_")
        direction = str(gt_row.get("new_direction",
                                    gt_row.get("conclusion_direction", ""))).strip().lower()
        m_level = str(gt_row.get("m_level", gt_row.get("consensus_level", ""))).strip()
        difficulty = _classify_difficulty(m_level)

        regen_row = regen.get(paper_id, {})
        source_type = str(regen_row.get("source_type", "unknown")).strip()

        pdf_candidates = list(pdfs_dir.glob(f"{paper_id}.pdf"))
        pdf_path = pdf_candidates[0] if pdf_candidates else None

        ineligible_reason = None
        if method not in METHOD_FAMILIES:
            ineligible_reason = f"method_family='{method}' not in allowed set"
        elif difficulty == "unknown":
            ineligible_reason = f"m_level='{m_level}' unclassifiable"
        elif source_type not in ACCEPTABLE_SOURCE_TYPES:
            ineligible_reason = f"source_type='{source_type}' not in {ACCEPTABLE_SOURCE_TYPES}"
        elif pdf_path is None:
            ineligible_reason = "pdf missing"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                method_family_phase2=method,
                direction_phase2=direction,
                consensus_level=m_level,
                difficulty=difficulty,
                source_type=source_type,
                pdf_path=pdf_path,
                eligible=(ineligible_reason is None),
                ineligible_reason=ineligible_reason,
            )
        )

    log.info("Loaded %d papers; %d eligible", len(records),
             sum(1 for r in records if r.eligible))
    # Report breakdown of eligibility blockers (so user can see why)
    block_reasons = Counter(r.ineligible_reason for r in records if not r.eligible)
    for reason, n in block_reasons.most_common():
        log.info("  ineligible: %s  (%d papers)", reason, n)

    # Report what's available per (method, difficulty) cell
    per_cell = Counter(r.cell() for r in records if r.eligible)
    log.info("Eligible papers per cell:")
    for mf in METHOD_FAMILIES:
        for diff in DIFFICULTY_TIERS:
            n = per_cell.get((mf, diff), 0)
            marker = " ⚠️ " if n < PAPERS_PER_CELL else "    "
            log.info("  %s%-15s × %-5s : %3d eligible (target %d)",
                     marker, mf, diff, n, PAPERS_PER_CELL)

    return records


# -------------------------------------------------------------------- #
# Sampling
# -------------------------------------------------------------------- #

def _bucketize(records: list[PaperRecord]) -> dict[tuple[str, str], list[PaperRecord]]:
    buckets: dict[tuple[str, str], list[PaperRecord]] = defaultdict(list)
    for r in records:
        if r.eligible:
            buckets[r.cell()].append(r)
    return buckets


def primary_stratified_draw(
    records: list[PaperRecord],
    rng: random.Random,
    log: logging.Logger,
) -> SelectionResult:
    buckets = _bucketize(records)
    result = SelectionResult()

    cells = [(mf, diff) for mf in METHOD_FAMILIES for diff in DIFFICULTY_TIERS]
    cells.sort(key=lambda c: len(buckets.get(c, [])))

    for cell in cells:
        pool = buckets.get(cell, [])
        take = min(PAPERS_PER_CELL, len(pool))
        if take < PAPERS_PER_CELL:
            msg = f"cell {cell}: only {len(pool)} eligible, drew {take}"
            log.warning(msg)
            result.shortfalls.append(msg)
        drawn = rng.sample(pool, take) if take > 0 else []
        result.selected.extend(drawn)
        result.per_cell_counts[cell] = take

    while len(result.selected) < TARGET_TOTAL:
        selected_ids = {r.paper_id for r in result.selected}
        surplus_candidates = sorted(
            (
                (cell, [p for p in pool if p.paper_id not in selected_ids])
                for cell, pool in buckets.items()
            ),
            key=lambda item: len(item[1]),
            reverse=True,
        )
        progress = False
        for cell, leftover in surplus_candidates:
            if len(result.selected) >= TARGET_TOTAL:
                break
            if not leftover:
                continue
            extra = rng.choice(leftover)
            result.selected.append(extra)
            result.per_cell_counts[cell] = result.per_cell_counts.get(cell, 0) + 1
            msg = f"backfill: +1 to cell {cell} for paper {extra.paper_id}"
            log.info(msg)
            result.shortfalls.append(msg)
            progress = True
        if not progress:
            log.error("Unable to reach TARGET_TOTAL=%d; selected=%d",
                      TARGET_TOTAL, len(result.selected))
            break

    return result


def direction_audit_and_rebalance(
    result: SelectionResult,
    all_records: list[PaperRecord],
    rng: random.Random,
    log: logging.Logger,
) -> SelectionResult:
    selected_ids = {r.paper_id for r in result.selected}
    dir_counts = Counter(r.direction_phase2 for r in result.selected)
    log.info("Direction distribution before rebalance: %s", dict(dir_counts))

    under = [d for d in DIRECTIONS if dir_counts.get(d, 0) < MIN_PER_DIRECTION]
    if not under:
        result.per_direction_counts = dict(dir_counts)
        return result

    max_swaps = int(MAX_DIRECTION_SWAPS_PCT * len(result.selected))
    swaps_done = 0

    for target_dir in under:
        needed = MIN_PER_DIRECTION - dir_counts.get(target_dir, 0)
        candidates = [
            r for r in all_records
            if r.eligible
            and r.paper_id not in selected_ids
            and r.direction_phase2 == target_dir
        ]
        rng.shuffle(candidates)

        for cand in candidates:
            if needed <= 0 or swaps_done >= max_swaps:
                break
            over_dirs = [d for d in DIRECTIONS
                         if dir_counts.get(d, 0) > MIN_PER_DIRECTION]
            same_cell_victims = [
                r for r in result.selected
                if r.cell() == cand.cell()
                and r.direction_phase2 in over_dirs
            ]
            if not same_cell_victims:
                same_cell_victims = [
                    r for r in result.selected
                    if r.direction_phase2 in over_dirs
                ]
            if not same_cell_victims:
                break

            victim = rng.choice(same_cell_victims)
            result.selected.remove(victim)
            result.selected.append(cand)
            selected_ids.discard(victim.paper_id)
            selected_ids.add(cand.paper_id)

            dir_counts[victim.direction_phase2] -= 1
            dir_counts[target_dir] = dir_counts.get(target_dir, 0) + 1
            swaps_done += 1
            needed -= 1

            msg = (f"direction swap #{swaps_done}: "
                   f"evicted {victim.paper_id} ({victim.direction_phase2}) "
                   f"for {cand.paper_id} ({cand.direction_phase2})")
            log.info(msg)
            result.direction_swaps.append(msg)

    log.info("Direction distribution after rebalance: %s", dict(dir_counts))
    result.per_direction_counts = dict(dir_counts)
    return result


# -------------------------------------------------------------------- #
# Output
# -------------------------------------------------------------------- #

def _write_visible_manifest(out_dir: Path, records: list[PaperRecord]) -> Path:
    path = out_dir / "sample_manifest.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["paper_id", "difficulty_tier", "pdf_path"])
        for r in sorted(records, key=lambda x: int(x.paper_id.split("_")[1])):
            w.writerow([r.paper_id, r.difficulty,
                        str(r.pdf_path) if r.pdf_path else ""])
    return path


def _write_sealed_manifest(out_dir: Path, records: list[PaperRecord]) -> Path:
    path = out_dir / "sample_manifest_SEALED.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "paper_id", "method_family_phase2", "direction_phase2",
            "consensus_level", "difficulty_tier", "source_type",
        ])
        for r in sorted(records, key=lambda x: int(x.paper_id.split("_")[1])):
            w.writerow([
                r.paper_id, r.method_family_phase2, r.direction_phase2,
                r.consensus_level, r.difficulty, r.source_type,
            ])
    return path


def _write_hash(manifest_path: Path) -> Path:
    h = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    hash_path = manifest_path.with_suffix(".sha256")
    hash_path.write_text(f"{h}  {manifest_path.name}\n")
    return hash_path


def write_outputs(out_dir: Path, result: SelectionResult,
                  log: logging.Logger) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    visible = _write_visible_manifest(out_dir, result.selected)
    sealed = _write_sealed_manifest(out_dir, result.selected)
    hash_file = _write_hash(visible)

    log.info("Wrote VISIBLE manifest:  %s (%d rows)", visible, len(result.selected))
    log.info("Wrote SEALED manifest:   %s", sealed)
    log.info("Wrote manifest hash:     %s", hash_file)

    log.info("=== Per-cell counts ===")
    for cell in sorted(result.per_cell_counts):
        log.info("  %-25s : %d", f"{cell[0]} × {cell[1]}",
                 result.per_cell_counts[cell])
    log.info("=== Per-direction counts ===")
    for d, n in sorted(result.per_direction_counts.items()):
        flag = " ⚠️" if n < MIN_PER_DIRECTION else ""
        log.info("  %-10s : %d%s", d, n, flag)
    if result.shortfalls:
        log.warning("=== Shortfalls / backfills ===")
        for s in result.shortfalls:
            log.warning("  %s", s)


# -------------------------------------------------------------------- #
# Main
# -------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description="A1 gold-subset sampler")
    parser.add_argument("--audit-root", type=Path, required=True,
                        help="Path to the audit/ directory")
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="Output directory for manifests")
    parser.add_argument("--seed", type=int, default=20260423,
                        help="Random seed (default: 20260423)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    args.out_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.out_dir / "sample_selection.log"

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("sample_selection")
    log.info("Seed = %d", args.seed)

    rng = random.Random(args.seed)

    records = load_corpus(args.audit_root, log)
    result = primary_stratified_draw(records, rng, log)
    result = direction_audit_and_rebalance(result, records, rng, log)

    if len(result.selected) != TARGET_TOTAL:
        log.error("Final sample size %d ≠ TARGET_TOTAL %d",
                  len(result.selected), TARGET_TOTAL)

    write_outputs(args.out_dir, result, log)
    log.info("Done. Review %s and %s before labeling.",
             args.out_dir / "sample_manifest.csv",
             log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
