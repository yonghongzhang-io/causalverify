"""
Quarantine 2 books misclassified as papers: paper_147, paper_179.

Moves their paper JSON + resolver cache entry + any outputs to
experiments/exp_a/quarantine_books/ (reversible, preserves history).

Does NOT delete — just moves out of the "active" set so downstream
scoring scripts skip them.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT       = Path(__file__).parent.parent
PAPERS     = ROOT / "experiments/exp_a/papers"
RESOLVER   = ROOT / "audit/resolver_cache"
OUTPUTS    = ROOT / "experiments/exp_a/outputs"
QUARANTINE = ROOT / "experiments/exp_a/quarantine_books"

BOOKS = {
    "paper_147": "Scarcity: Why Having Too Little Means So Much (Mullainathan & Shafir 2013)",
    "paper_179": "The Venture Capital Cycle (Gompers & Lerner 1999)",
}


def main():
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    log = []

    for pid, title in BOOKS.items():
        print(f"\nQuarantining {pid}: {title}")
        entry = {"paper_id": pid, "title": title, "moved": []}

        # 1. paper JSON (might have suffix like _did_easy)
        for pf in PAPERS.glob(f"{pid}_*.json"):
            dst = QUARANTINE / pf.name
            shutil.move(str(pf), str(dst))
            entry["moved"].append(str(pf.relative_to(ROOT)))
            print(f"  moved paper JSON → {dst.relative_to(ROOT)}")
        for pf in PAPERS.glob(f"{pid}.json"):
            dst = QUARANTINE / pf.name
            shutil.move(str(pf), str(dst))
            entry["moved"].append(str(pf.relative_to(ROOT)))
            print(f"  moved paper JSON → {dst.relative_to(ROOT)}")

        # 2. resolver cache
        rc = RESOLVER / f"{pid}.json"
        if rc.exists():
            dst = QUARANTINE / f"resolver_{pid}.json"
            shutil.move(str(rc), str(dst))
            entry["moved"].append(str(rc.relative_to(ROOT)))
            print(f"  moved resolver cache → {dst.relative_to(ROOT)}")

        # 3. Any LLM outputs — 7 models × this paper
        outputs_moved = 0
        for of in OUTPUTS.glob(f"{pid}_*.json"):
            dst = QUARANTINE / of.name
            shutil.move(str(of), str(dst))
            outputs_moved += 1
            entry["moved"].append(str(of.relative_to(ROOT)))
        if outputs_moved:
            print(f"  moved {outputs_moved} LLM output files")

        log.append(entry)

    # Write quarantine manifest
    (QUARANTINE / "MANIFEST.md").write_text(
        "# Quarantined Books\n\n"
        "These items were misclassified as research articles during the\n"
        "original Exp A ingestion. They are monographs / popular-press books\n"
        "and do not fit the benchmark's single-paper, single-method, single-RQ\n"
        "schema. Quarantined 2026-04-23.\n\n"
        + "\n".join(f"- **{e['paper_id']}**: {e['title']}\n"
                    + "  \n".join(f"    - moved: `{m}`" for m in e['moved'])
                    for e in log)
    )
    print(f"\n✅ Quarantined {len(BOOKS)} books.")
    print(f"   Active benchmark size: {262 - len(BOOKS)} papers (260)")


if __name__ == "__main__":
    main()
