#!/usr/bin/env python3
"""Gate 2: re-run V2'' check_leakage() on the A4 output for the 6 leaky papers.

Per the design plan (user instruction 2026-04-27): the V2'' hard
anti-leakage rule is the load-bearing definition for what counts as
'leaked'. A4 has its own broader 117-cue taxonomy, which can choose to
passthrough a paper that V2'' would block. Before merging the cleaned
6 papers back into experiments/exp_a/papers/*.json, every accepted row
MUST pass V2''-level check_leakage() with 0 hits across all three
fields.

Exits 0 if all 6 are clean. Exits 1 with a per-paper report otherwise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "agents"))
from rebuild_metadata_v2primeprime import check_leakage  # type: ignore

A4_OUT_CANDIDATES = [
    ROOT / "audit/regen_strong_deleak_v2primeprime_6.json",
    ROOT / "audit/regen_strong_deleak.json",
]
WITH_LEAK_IN = ROOT / "audit/regen_from_pdf_v2primeprime_with_leakage.json"


def fields_of(row: dict) -> dict:
    """Pull RQ/DD/IC into a flat dict that check_leakage() expects.

    A4 output schema differs slightly: rewritten rows have a 'new_fields'
    block; passthrough rows keep the original new_fields under
    'new_fields_original' (or just leave new_fields unchanged).
    """
    nf = row.get("new_fields") or row.get("new_fields_original") or {}
    return {
        "research_question":     nf.get("research_question", ""),
        "data_description":      nf.get("data_description", ""),
        "institutional_context": nf.get("institutional_context", ""),
    }


def main() -> int:
    a4_path = next((p for p in A4_OUT_CANDIDATES if p.exists()), None)
    if a4_path is None:
        print("No A4 output found. Checked:")
        for p in A4_OUT_CANDIDATES:
            print(f"  - {p}")
        return 1
    a4 = {r["paper_id"]: r for r in json.loads(a4_path.read_text())}
    cap = {r["paper_id"]: r for r in json.loads(WITH_LEAK_IN.read_text())}

    expected = ["paper_05", "paper_09", "paper_17", "paper_51", "paper_63", "paper_206"]
    print(f"Gate 2 — V2'' check_leakage() on A4 output ({a4_path.name})")
    print(f"  expected n={len(expected)}, A4 rows={len(a4)}")
    print()

    failures = []
    for pid in expected:
        if pid not in a4:
            print(f"  {pid}: ⚠️  MISSING from A4 output")
            failures.append((pid, "missing"))
            continue
        row = a4[pid]
        action = row.get("rewrite_action", "?")
        fields = fields_of(row)
        captured_leak = cap.get(pid, {}).get("leakage_at_capture")

        leak = check_leakage(fields)
        ok = leak is None
        marker = "✓" if ok else "✗"
        print(f"  {pid}: {marker} action={action:<12} captured_leak={captured_leak!r:<35}  "
              f"v2pp_check_leakage={leak!r}")
        if not ok:
            failures.append((pid, leak))
            for fname, fval in fields.items():
                if fval:
                    print(f"      {fname}: {fval[:140]}...")

    print()
    if failures:
        print(f"GATE 2 FAILED: {len(failures)} / {len(expected)} papers still have V2''-level leakage.")
        for pid, reason in failures:
            print(f"  - {pid}: {reason}")
        return 1
    print(f"GATE 2 PASSED: 0 / {len(expected)} have V2''-level leakage. Safe to merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
