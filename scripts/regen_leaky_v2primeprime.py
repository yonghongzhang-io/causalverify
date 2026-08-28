#!/usr/bin/env python3
"""Recover V2'' new_fields for hard-leakage-blocked papers.

The Stage-4 rebuild script discards the Opus-generated JSON when
check_leakage() flags a hard cue (e.g. 'abnormal return' or the
acronym 'IV'). To run A4 strong-deleak on those 6 papers we need
the original raw text, regenerated and persisted.

Output goes to audit/regen_from_pdf_v2primeprime_with_leakage.json,
NOT to the main regen file. This is gate 1 from the design plan:
"save-leaky 只保存到临时文件，不直接进入 main new_fields".

Usage:
  python3 scripts/regen_leaky_v2primeprime.py \
      --papers paper_05,paper_09,paper_17,paper_51,paper_63,paper_206
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "agents"))

from labnotebook.experiment_logger import ExperimentLogger  # type: ignore
from rebuild_metadata_v2primeprime import (  # type: ignore
    call_opus,
    check_leakage,
    extract_pdf_text,
    find_paper_file,
    validate_fields,
    EmptyOpusResponse,
    PDF_DIR,
    REAL_ABS,
    ROOT,
    MAX_PAGES,
    MAX_CHARS,
)

LEAKY_OUT = ROOT / "audit/regen_from_pdf_v2primeprime_with_leakage.json"


def regen_one(pid: str, real_abs_by_id: dict, exp=None) -> tuple[dict, float]:
    """Regenerate V2'' new_fields, saving regardless of leakage outcome."""
    pf = find_paper_file(pid)
    if not pf:
        return {"paper_id": pid, "error": "paper_json_not_found"}, 0.0
    paper = json.loads(pf.read_text())
    title = paper.get("title", "")
    authors = paper.get("authors", "")

    pdf_path = PDF_DIR / f"{pid}.pdf"
    text = ""
    source_type = "none"
    if pdf_path.exists():
        text = extract_pdf_text(pdf_path)
        if text:
            source_type = f"pdf_full_text_up_to_{MAX_PAGES}pg_{MAX_CHARS}c"
    if not text and pid in real_abs_by_id:
        abs_row = real_abs_by_id[pid]
        if abs_row.get("real_abstract"):
            text = abs_row["real_abstract"]
            source_type = "openalex_abstract"
    if not text:
        return {"paper_id": pid, "error": "no_source_text",
                "source_type": "none"}, 0.0

    if exp:
        exp.log_event("start_paper", paper_id=pid,
                       source_type=source_type, source_chars=len(text))

    try:
        new_fields, cost = call_opus(title, authors, text, source_type,
                                      exp=exp, paper_id=pid)
    except EmptyOpusResponse as ee:
        return {"paper_id": pid,
                "error": f"opus_empty: {ee}",
                "source_type": source_type}, ee.cost
    except Exception as e:
        return {"paper_id": pid,
                "error": f"opus_error: {type(e).__name__}: {str(e)[:160]}",
                "source_type": source_type}, 0.0

    schema_error = validate_fields(new_fields)
    if schema_error:
        return {"paper_id": pid, "error": schema_error,
                "source_type": source_type}, cost

    leak = check_leakage(new_fields)
    # Whether or not leak fires, save the full new_fields. That is the
    # whole point of this script.
    row = {
        "paper_id":           pid,
        "source_type":        source_type,
        "source_chars":       len(text),
        "title":              title,
        "new_fields":         new_fields,
        "leakage_at_capture": leak,  # None if clean, else the offending cue
        "ts":                 time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if exp:
        exp.log_event("captured_with_leakage", paper_id=pid,
                       leakage=str(leak), source_chars=len(text))
    return row, cost


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True,
                    help="Comma-separated paper_ids")
    args = ap.parse_args()

    pids = [p.strip() for p in args.papers.split(",") if p.strip()]
    print(f"Regenerating leaky V2'' fields for {len(pids)} paper(s): {pids}")

    real_abs_by_id = {r["paper_id"]: r
                       for r in json.loads(REAL_ABS.read_text())}

    existing: list[dict] = []
    if LEAKY_OUT.exists():
        existing = json.loads(LEAKY_OUT.read_text())
    by_pid = {r["paper_id"]: r for r in existing}

    exp = ExperimentLogger(
        run_name="v2primeprime_save_leaky",
        script_path=__file__,
        hypothesis=(
            "Recover V2'' Opus-generated raw fields for the 6 papers "
            "Stage 4 quarantined for hard-cue leakage, so A4 strong-deleak "
            "can rewrite them into neutral language without losing the V2'' "
            "full-text richness."
        ),
        config={
            "model": "claude-opus-4-7",
            "target_papers": pids,
            "output_file": str(LEAKY_OUT.relative_to(ROOT)),
            "save_leaky": True,
        },
    )

    total_cost = 0.0
    for i, pid in enumerate(pids, 1):
        row, cost = regen_one(pid, real_abs_by_id, exp=exp)
        by_pid[pid] = row
        total_cost += cost
        leak = row.get("leakage_at_capture")
        if "new_fields" in row:
            tag = f"  leakage_at_capture={leak}" if leak else "  CLEAN"
            print(f"  [{i}/{len(pids)}] {pid}: ok ({row['source_chars']:>6}c)  "
                  f"this=${cost:.3f}  cum=${total_cost:.2f}{tag}")
        else:
            print(f"  [{i}/{len(pids)}] {pid}: ERR {row.get('error','?')[:80]}")
        # Flush after each (only 6 papers)
        out_rows = sorted(by_pid.values(), key=lambda r: int(r["paper_id"].split("_")[1]))
        LEAKY_OUT.write_text(json.dumps(out_rows, indent=2, ensure_ascii=False))

    print()
    print(f"Saved: {LEAKY_OUT.relative_to(ROOT)}  ({len(by_pid)} rows)")
    print(f"Total cost: ${total_cost:.4f}")
    exp.attach_output(LEAKY_OUT.name, LEAKY_OUT)
    exp.finish(
        status="success",
        results={
            "n_processed": len(pids),
            "n_with_new_fields": sum(1 for r in by_pid.values() if "new_fields" in r),
            "total_cost_usd": round(total_cost, 4),
        },
        interpretation=(
            "Raw V2'' fields captured for hard-leakage papers. "
            "Next: feed audit/regen_from_pdf_v2primeprime_with_leakage.json "
            "to src/agents/strong_deleak_pass.py via --input."
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
