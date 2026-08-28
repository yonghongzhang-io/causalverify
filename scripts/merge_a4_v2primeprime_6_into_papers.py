#!/usr/bin/env python3
"""Gate 3: merge the 6 A4-cleaned V2'' papers into experiments/exp_a/papers/.

Pre-condition: audit/regen_strong_deleak_v2primeprime_6.json must already
have passed gate 2 (scripts/gate_check_a4_v2primeprime_6.py prints
'GATE 2 PASSED'). Re-run that here as a defensive guard.

Sets phase1_source_version=v2primeprime_full_text_a4_deleak so the
merged-paper provenance is distinguishable from the 254 papers that
took the direct V2'' path (which carry phase1_source_version=
v2primeprime_full_text). Preserves any existing _legacy_v1_ground_truth
key.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "agents"))
from rebuild_metadata_v2primeprime import check_leakage  # type: ignore

A4_OUT = ROOT / "audit/regen_strong_deleak_v2primeprime_6.json"
PAPERS_DIR = ROOT / "experiments/exp_a/papers"
EXPECTED_PIDS = {"paper_05", "paper_09", "paper_17", "paper_51", "paper_63", "paper_206"}


def find_paper_file(pid: str) -> Path | None:
    hits = list(PAPERS_DIR.glob(f"{pid}_*.json")) + list(PAPERS_DIR.glob(f"{pid}.json"))
    return hits[0] if hits else None


def fields_of(row: dict) -> dict:
    nf = row.get("new_fields") or row.get("new_fields_original") or {}
    return {
        "research_question":     nf.get("research_question", ""),
        "data_description":      nf.get("data_description", ""),
        "institutional_context": nf.get("institutional_context", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Write changes. Omit for dry-run.")
    args = ap.parse_args()

    a4 = {r["paper_id"]: r for r in json.loads(A4_OUT.read_text())}
    if set(a4) != EXPECTED_PIDS:
        print(f"ERR: A4 output paper_ids={sorted(a4)}, expected={sorted(EXPECTED_PIDS)}")
        return 1

    # Re-run gate 2 defensively
    fail = []
    for pid in EXPECTED_PIDS:
        leak = check_leakage(fields_of(a4[pid]))
        if leak is not None:
            fail.append((pid, leak))
    if fail:
        print(f"GATE 2 FAILED inside merge script: {fail}")
        print("Refusing to merge.")
        return 1
    print(f"Gate 2 re-check: 0/6 leakage. Proceeding.")
    print()

    stats = {"updated": 0, "missing_paper": 0, "missing_fields": 0}
    for pid in sorted(EXPECTED_PIDS, key=lambda s: int(s.split("_")[1])):
        paper_file = find_paper_file(pid)
        if paper_file is None:
            stats["missing_paper"] += 1
            print(f"Skip {pid}: paper JSON not found")
            continue

        a4_row = a4[pid]
        new_fields = fields_of(a4_row)
        if not all(new_fields.values()):
            stats["missing_fields"] += 1
            print(f"Skip {pid}: missing fields after A4")
            continue

        paper = json.loads(paper_file.read_text())
        before = {k: paper.get(k, "") for k in new_fields.keys()}
        changed = [k for k in new_fields if before.get(k, "") != new_fields[k]]
        if not changed:
            print(f"No-op {pid}: paper JSON already matches A4 cleaned fields")
            continue

        # Provenance preservation: keep V1 GT under _legacy_v1_ground_truth if not done yet
        if "ground_truth" in paper and "_legacy_v1_ground_truth" not in paper:
            paper["_legacy_v1_ground_truth"] = paper.pop("ground_truth")

        paper.update(new_fields)
        paper["phase1_source_version"] = "v2primeprime_full_text_a4_deleak"
        paper["v2primeprime_a4_action"] = a4_row.get("rewrite_action", "?")
        paper["v2primeprime_a4_hard_cues_before"] = a4_row.get("hard_cues_original", 0)
        paper["v2primeprime_a4_hard_cues_after"] = a4_row.get("hard_cues_after", 0)

        verb = "Would update" if not args.apply else "Updated"
        print(f"{verb} {paper_file.name}: {', '.join(changed)} "
              f"(action={a4_row.get('rewrite_action','?')})")
        if args.apply:
            paper_file.write_text(json.dumps(paper, indent=2, ensure_ascii=False))
        stats["updated"] += 1

    print()
    print(f"{'APPLIED' if args.apply else 'DRY-RUN'}: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
