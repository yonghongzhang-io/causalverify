#!/usr/bin/env python3
"""Merge V2'' regenerated fields into experiments/exp_a/papers/*.json.

Default is dry-run. Use --apply only after V2'' passes the pre-registered
quality gates. Existing ground_truth is preserved as _legacy_v1_ground_truth
so downstream code cannot silently confuse old GPT-4o ingestion labels with
the later 4-LLM GT vote.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
PAPERS_DIR = ROOT / "experiments/exp_a/papers"
V2PRIMEPRIME = ROOT / "audit/regen_from_pdf_v2primeprime.json"


def find_paper_file(pid: str) -> Path | None:
    hits = list(PAPERS_DIR.glob(f"{pid}_*.json")) + list(PAPERS_DIR.glob(f"{pid}.json"))
    return hits[0] if hits else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=V2PRIMEPRIME)
    parser.add_argument("--apply", action="store_true",
                        help="Write changes. Omit for dry-run.")
    args = parser.parse_args()

    input_path = args.input
    if not input_path.exists():
        raise SystemExit(f"Error: {input_path} not found")

    v2pp = {r["paper_id"]: r for r in json.loads(input_path.read_text())}
    stats = {"updated": 0, "missing_paper": 0, "missing_fields": 0}

    for pid in sorted(v2pp, key=lambda s: int(s.split("_")[1])):
        paper_file = find_paper_file(pid)
        if paper_file is None:
            stats["missing_paper"] += 1
            print(f"Skip {pid}: paper JSON not found")
            continue

        v2pp_row = v2pp[pid]
        if "new_fields" not in v2pp_row:
            stats["missing_fields"] += 1
            print(f"Skip {pid}: no new_fields")
            continue

        paper = json.loads(paper_file.read_text())
        before = {
            "research_question": paper.get("research_question", ""),
            "data_description": paper.get("data_description", ""),
            "institutional_context": paper.get("institutional_context", ""),
        }

        new_fields = v2pp_row["new_fields"]
        changed = [k for k in before if before.get(k, "") != new_fields.get(k, "")]
        if not changed:
            print(f"No-op {pid}: fields already match")
            continue

        if "ground_truth" in paper and "_legacy_v1_ground_truth" not in paper:
            paper["_legacy_v1_ground_truth"] = paper.pop("ground_truth")
        elif "ground_truth" in paper:
            paper.pop("ground_truth")

        paper.update(new_fields)

        paper["v2primeprime_source_type"] = v2pp_row.get("source_type", "")
        paper["v2primeprime_source_chars"] = v2pp_row.get("source_chars", 0)
        paper["phase1_source_version"] = "v2primeprime_full_text"

        stats["updated"] += 1
        action = "Updated" if args.apply else "Would update"
        print(f"{action} {paper_file.name}: {', '.join(changed)}")

        if args.apply:
            paper_file.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n")

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"\n{mode}: {stats}")

if __name__ == "__main__":
    main()
