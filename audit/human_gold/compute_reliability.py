#!/usr/bin/env python3
"""
compute_reliability.py — Intra-rater κ for the A1 gold subset.

Two modes:
  --sample   : pick a random subset of already-labeled papers for blind re-labeling
  --evaluate : compute Cohen's κ between first-pass and re-label rows

Gate 1 thresholds (from labeling_protocol.md §5.3):
  method_family  : intra-rater κ ≥ 0.80
  direction      : intra-rater κ ≥ 0.70

Usage:
    # After labeling first 20 papers, wait ≥ 7 days, then:
    python compute_reliability.py --sample \
        --labels paper_native_labels.csv \
        --n-initial 20 --n-relabel 4 --seed 20260501

    # After re-labeling the 4 papers:
    python compute_reliability.py --evaluate \
        --labels paper_native_labels.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

METHOD_FAMILIES = ["DID", "EVENT_STUDY", "IV", "RDD", "OTHER"]
DIRECTIONS = ["positive", "negative", "mixed", "unclear"]

GATE_METHOD_KAPPA = 0.80
GATE_DIRECTION_KAPPA = 0.70


# -------------------------------------------------------------------- #
# CSV helpers
# -------------------------------------------------------------------- #

def _read_labels(path: Path) -> list[dict]:
    with path.open() as f:
        reader = csv.DictReader(f)
        return list(reader)


def _is_truthy(v: str) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


# -------------------------------------------------------------------- #
# --sample mode
# -------------------------------------------------------------------- #

def sample_for_relabel(
    labels_path: Path, n_initial: int, n_relabel: int, seed: int,
) -> list[str]:
    rows = _read_labels(labels_path)
    first_pass = [r for r in rows if not _is_truthy(r.get("is_blind_relabel", ""))]
    first_pass.sort(key=lambda r: int(r["label_row_id"]))
    if len(first_pass) < n_initial:
        print(f"ERROR: only {len(first_pass)} first-pass rows available, "
              f"need at least {n_initial}", file=sys.stderr)
        sys.exit(2)
    pool = first_pass[:n_initial]

    rng = random.Random(seed)
    picked = rng.sample(pool, n_relabel)
    paper_ids = sorted(r["paper_id"] for r in picked)

    print("\n=== Blind re-label subset ===")
    print(f"Drawn from first {n_initial} first-pass rows using seed {seed}")
    print(f"Selected {n_relabel} papers for re-labeling:\n")
    for pid in paper_ids:
        print(f"  {pid}")
    print("\nNEXT STEPS:")
    print("  1. Do NOT look at the original labels for these papers.")
    print("  2. Wait until at least 7 days have passed since first labeling.")
    print("  3. Re-label each paper from scratch, using the PDF only.")
    print("  4. Set `is_blind_relabel = True` on the new rows, and set")
    print("     `original_label_row_id` to the first-pass row's id.")
    print("  5. Run: python compute_reliability.py --evaluate --labels <path>")
    return paper_ids


# -------------------------------------------------------------------- #
# --evaluate mode
# -------------------------------------------------------------------- #

def _cohen_kappa(pairs: list[tuple[str, str]], classes: list[str]) -> float:
    """Unweighted Cohen's κ. pairs = list of (label_A, label_B) tuples."""
    if not pairs:
        return float("nan")
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    count_a: dict[str, int] = defaultdict(int)
    count_b: dict[str, int] = defaultdict(int)
    for a, b in pairs:
        count_a[a] += 1
        count_b[b] += 1
    pe = sum(
        (count_a[c] / n) * (count_b[c] / n) for c in classes
    )
    if pe == 1.0:
        return 1.0 if po == 1.0 else float("nan")
    return (po - pe) / (1 - pe)


def _pair_up(rows: list[dict]) -> list[tuple[dict, dict]]:
    """Match blind-relabel rows to their first-pass originals."""
    by_id = {int(r["label_row_id"]): r for r in rows}
    pairs: list[tuple[dict, dict]] = []
    for r in rows:
        if _is_truthy(r.get("is_blind_relabel", "")):
            orig_id_str = str(r.get("original_label_row_id", "")).strip()
            if not orig_id_str or orig_id_str == "-1":
                print(f"WARN: relabel row {r.get('label_row_id')} has no "
                      f"original_label_row_id", file=sys.stderr)
                continue
            try:
                orig_id = int(orig_id_str)
            except ValueError:
                print(f"WARN: bad original_label_row_id={orig_id_str}",
                      file=sys.stderr)
                continue
            orig = by_id.get(orig_id)
            if orig is None:
                print(f"WARN: original row {orig_id} not found", file=sys.stderr)
                continue
            pairs.append((orig, r))
    return pairs


def evaluate(labels_path: Path) -> int:
    rows = _read_labels(labels_path)
    pairs = _pair_up(rows)

    if not pairs:
        print("ERROR: no blind-relabel pairs found. Did you set "
              "is_blind_relabel and original_label_row_id?", file=sys.stderr)
        return 2

    method_pairs = [
        (p[0]["method_family"], p[1]["method_family"]) for p in pairs
    ]
    direction_pairs = [
        (p[0]["direction"], p[1]["direction"]) for p in pairs
    ]

    kappa_method = _cohen_kappa(method_pairs, METHOD_FAMILIES)
    kappa_direction = _cohen_kappa(direction_pairs, DIRECTIONS)

    print("\n=== Re-label pairs ===")
    print(f"{'paper_id':<15}{'method (orig)':<18}{'method (rel)':<18}"
          f"{'direction (orig)':<20}{'direction (rel)':<20}{'match':<10}")
    for orig, rel in pairs:
        m_match = orig["method_family"] == rel["method_family"]
        d_match = orig["direction"] == rel["direction"]
        marker = "OK" if (m_match and d_match) else (
            "method diff" if not m_match and d_match else
            "direction diff" if m_match and not d_match else
            "both diff"
        )
        print(f"{orig['paper_id']:<15}"
              f"{orig['method_family']:<18}{rel['method_family']:<18}"
              f"{orig['direction']:<20}{rel['direction']:<20}{marker:<10}")

    print(f"\n=== Intra-rater Cohen's kappa (n = {len(pairs)}) ===")
    print(f"  method_family  : kappa = {kappa_method:.3f}  "
          f"(Gate 1 requires >= {GATE_METHOD_KAPPA})")
    print(f"  direction      : kappa = {kappa_direction:.3f}  "
          f"(Gate 1 requires >= {GATE_DIRECTION_KAPPA})")

    method_pass = kappa_method >= GATE_METHOD_KAPPA
    direction_pass = kappa_direction >= GATE_DIRECTION_KAPPA

    print("\n=== Gate 1 verdict ===")
    print(f"  method_family  : {'PASS' if method_pass else 'FAIL'}")
    print(f"  direction      : {'PASS' if direction_pass else 'FAIL'}")

    if method_pass and direction_pass:
        print("\nGate 1 PASSED. Proceed to label papers 21-80.")
        return 0

    print("\nGate 1 FAILED on at least one axis.")
    print("  Required remediation (per protocol Section 5.3):")
    print("    1. Re-read rubric sections 3.1 and 3.2.")
    print("    2. Discuss the disagreed-on papers; log decisions in rubric/.")
    print("    3. Revise labels ONLY via a protocol amendment (see section 10).")
    print("    4. Re-sample another 4 papers from the first 20 and re-test.")
    print("  Also note: n = 4 gives wide kappa confidence intervals; if kappa is")
    print("  close to the threshold, consider expanding the re-label subset to 8.")
    return 1


# -------------------------------------------------------------------- #
# Main
# -------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description="Intra-rater kappa for A1 gold subset")
    parser.add_argument("--labels", type=Path, required=True,
                        help="Path to paper_native_labels.csv")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample", action="store_true",
                      help="Draw random subset for blind re-labeling")
    mode.add_argument("--evaluate", action="store_true",
                      help="Compute kappa from existing blind-relabel rows")
    parser.add_argument("--n-initial", type=int, default=20,
                        help="How many first-pass rows to sample from (default 20)")
    parser.add_argument("--n-relabel", type=int, default=4,
                        help="How many papers to re-label (default 4)")
    parser.add_argument("--seed", type=int, default=20260501,
                        help="Random seed for --sample mode")
    args = parser.parse_args()

    if args.sample:
        sample_for_relabel(args.labels, args.n_initial, args.n_relabel, args.seed)
        return 0
    if args.evaluate:
        return evaluate(args.labels)
    return 2


if __name__ == "__main__":
    sys.exit(main())
