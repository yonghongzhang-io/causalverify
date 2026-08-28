#!/usr/bin/env python3
"""
label_helper.py — Interactive labeling wrapper for the A1 gold subset.

This is NOT an LLM agent. It is a deterministic interactive CLI that
handles CSV mechanics, input validation, a wall-clock timer, and session
bookkeeping so the annotator only has to read the PDF and answer
structured questions. Protocol §4.2 forbids LLM-assisted classification
during labeling; this wrapper explicitly contains zero LLM calls.

What it does NOT do:
  - It never reads the PDF content. You read the PDF; it just records.
  - It never calls an LLM to classify. Protocol §4.2 bans LLM-assisted
    classification; this script enforces that by not having an LLM API
    key or model call anywhere.
  - It never opens `sample_manifest_SEALED.csv` or any paper JSON
    containing Phase 2 labels. Blinding is preserved.

What it does:
  - Picks the next un-labeled paper from `sample_manifest.csv`.
  - Opens the PDF in your default viewer.
  - Runs a wall clock (start on PDF open, stop when you save).
  - Asks the structured questions, one at a time, with input validation.
  - Writes the row to `paper_native_labels.csv` + `session_log.csv`.
  - Warns on 90-min per-paper hard stop (protocol §4.3).
  - Warns at 6 papers in a session (fatigue), hard stop at 8.
  - Runs `audit_labels.py --validate` after each save so you know
    immediately if the row is malformed.

Usage:
  python3 label_helper.py                     # label next un-labeled paper
  python3 label_helper.py --resume row_id=1   # fix a specific row post-hoc
  python3 label_helper.py --paper paper_08    # label a specific paper (override order)

Author convention: `annotator_id = YH` is hard-coded. Change at the top
if you need a different ID.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------------ config
HERE = Path(__file__).parent.resolve()
MANIFEST = HERE / "sample_manifest.csv"
LABELS = HERE / "paper_native_labels.csv"
SESSION_LOG = HERE / "session_log.csv"
NEEDS_REVIEW = HERE / "needs_review.csv"
AUDIT_SCRIPT = HERE / "audit_labels.py"

ANNOTATOR_ID = "YH"

METHOD_FAMILIES = ["DID", "EVENT_STUDY", "IV", "RDD", "OTHER"]
DIRECTIONS = ["positive", "negative", "mixed", "unclear"]
CONFIDENCES = ["high", "medium", "low"]

SUPP_MIN_CHARS = 30
SUPP_MAX_CHARS = 200
TIME_MIN = 5
TIME_SOFT_WARN = 45       # warn at 45 min
TIME_HARD_STOP = 90       # protocol §4.3

SESSION_SOFT_WARN = 6     # slow-down warn
SESSION_HARD_STOP = 8

LABEL_HEADER = [
    "label_row_id", "paper_id", "annotator_id", "session_date",
    "method_family", "direction",
    "supporting_sentence_method", "supporting_sentence_direction",
    "confidence_method", "confidence_direction",
    "time_spent_minutes", "is_blind_relabel", "original_label_row_id",
    "notes",
]

SESSION_HEADER = [
    "session_date", "annotator_id", "start_time", "end_time",
    "papers_labeled_this_session", "blinding_confirmed",
    "interruptions", "fatigue_level", "notes",
]


# ------------------------------------------------------------------ IO

def _read(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def _write(path: Path, rows: list[dict], header: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def _append(path: Path, row: dict, header: list[str]) -> None:
    existing = _read(path)
    existing.append(row)
    _write(path, existing, header)


# ------------------------------------------------------------------ UI

def ask(prompt: str, valid: list[str] | None = None,
        allow_empty: bool = False) -> str:
    """Ask with input validation."""
    while True:
        try:
            ans = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(130)
        if not ans and allow_empty:
            return ""
        if not ans:
            print("  (required)")
            continue
        if valid and ans not in valid:
            print(f"  must be one of: {valid}")
            continue
        return ans


def ask_sentence(kind: str) -> str:
    while True:
        print(f"\n  Paste the {kind} supporting sentence (verbatim from PDF):")
        print(f"  (Must be {SUPP_MIN_CHARS}-{SUPP_MAX_CHARS} chars. Press Enter "
              "on blank line to finish multi-line paste.)")
        lines = []
        while True:
            try:
                line = input("  > ")
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(130)
            if not line.strip():
                break
            lines.append(line)
        s = " ".join(lines).strip().strip('"').strip("'")
        if not s:
            print("  (required; re-enter)")
            continue
        if len(s) < SUPP_MIN_CHARS:
            print(f"  too short ({len(s)} < {SUPP_MIN_CHARS}); re-enter")
            continue
        if len(s) > SUPP_MAX_CHARS:
            print(f"  too long ({len(s)} > {SUPP_MAX_CHARS}); trim to a "
                  "sub-sentence or use [...] to join two key fragments")
            continue
        return s


def ask_int(prompt: str, lo: int = None, hi: int = None) -> int:
    while True:
        ans = ask(prompt)
        try:
            v = int(ans)
        except ValueError:
            print("  must be integer")
            continue
        if lo is not None and v < lo:
            print(f"  must be >= {lo}")
            continue
        if hi is not None and v > hi:
            print(f"  must be <= {hi}")
            continue
        return v


# ------------------------------------------------------------------ manifest

def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        print(f"ERROR: manifest not found at {MANIFEST}")
        print("Run `python sample_selection.py --audit-root .. "
              "--out-dir . --seed 20260423` first.")
        sys.exit(2)
    return _read(MANIFEST)


def already_labeled() -> set[str]:
    return {r["paper_id"] for r in _read(LABELS)
            if r.get("is_blind_relabel", "").strip().lower() not in
            {"true", "1", "yes", "y"}}


def pick_next(preferred: str | None = None) -> dict | None:
    manifest = load_manifest()
    done = already_labeled()
    if preferred:
        for r in manifest:
            if r["paper_id"] == preferred:
                return r
        print(f"ERROR: {preferred} is not in the manifest")
        sys.exit(2)
    for r in manifest:
        if r["paper_id"] not in done:
            return r
    return None


# ------------------------------------------------------------------ session

def session_has_open_entry() -> dict | None:
    """Is today's session entry still open (no end_time)?"""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = _read(SESSION_LOG)
    for r in reversed(rows):
        if r["session_date"] == today and not r.get("end_time"):
            return r
    return None


def start_or_continue_session() -> tuple[str, dict, int]:
    """Return (start_time_iso, session_row, papers_already_in_session)."""
    existing = session_has_open_entry()
    if existing:
        # Count papers already labeled since start_time
        start_iso = existing["start_time"]
        done_in_session = sum(
            1 for r in _read(LABELS)
            if r.get("session_date") == existing["session_date"]
            and r.get("is_blind_relabel", "").strip().lower() not in
                {"true", "1", "yes", "y"}
            # Approx: session spans today; good enough for count
        )
        print(f"\n▶ Resuming open session (started {start_iso}; "
              f"{done_in_session} paper(s) labeled so far)")
        return start_iso, existing, done_in_session

    print("\n▶ Starting a new session.")
    print("  Blinding self-check: before you start, confirm you have NOT")
    print("  opened any of the following during this session:")
    print("    • sample_manifest_SEALED.csv")
    print("    • experiments/exp_a/papers/paper_*.json (Phase 2 labels)")
    print("    • Any LLM chat window that knows the paper's method")
    blind = ask("  Confirm blinding? (YES / NO): ", valid=["YES", "NO"])
    fatigue = ask_int("  Current fatigue 1-5 (1=fresh, 5=exhausted): ", 1, 5)

    now = datetime.now()
    row = {
        "session_date":   now.strftime("%Y-%m-%d"),
        "annotator_id":   ANNOTATOR_ID,
        "start_time":     now.isoformat(timespec="seconds"),
        "end_time":       "",
        "papers_labeled_this_session": "",
        "blinding_confirmed": blind,
        "interruptions":  "",
        "fatigue_level":  fatigue,
        "notes":          "",
    }
    _append(SESSION_LOG, row, SESSION_HEADER)
    return row["start_time"], row, 0


def close_session(start_iso: str, n_this_session: int) -> None:
    rows = _read(SESSION_LOG)
    for r in reversed(rows):
        if r["start_time"] == start_iso and not r["end_time"]:
            r["end_time"] = datetime.now().isoformat(timespec="seconds")
            r["papers_labeled_this_session"] = n_this_session
            if not r.get("interruptions"):
                ans = ask("\n  Approx interruptions this session (int; 0 if none): ")
                try: r["interruptions"] = str(int(ans))
                except ValueError: r["interruptions"] = "0"
            fat_end = ask_int("  End-of-session fatigue 1-5: ", 1, 5)
            r["fatigue_level"] = fat_end
            end_notes = ask("  Session notes (free text; blank to skip): ",
                            allow_empty=True)
            if end_notes:
                r["notes"] = (r["notes"] + " | " + end_notes).strip(" |")
            _write(SESSION_LOG, rows, SESSION_HEADER)
            return
    print("WARN: no matching open session row; not closing.")


# ------------------------------------------------------------------ per-paper

def open_pdf(paper_id: str, pdf_path: str) -> None:
    p = Path(pdf_path)
    if not p.is_absolute():
        p = (HERE / pdf_path).resolve()
    if not p.exists():
        p = HERE.parent / "pdfs" / f"{paper_id}.pdf"
    if not p.exists():
        print(f"  WARN: PDF not found at {p}. Open manually.")
        return
    subprocess.run(["open", str(p)], check=False)


def label_one_paper(paper_id: str, pdf_path: str,
                    next_row_id: int) -> dict:
    print(f"\n{'='*60}")
    print(f"  Paper: {paper_id}")
    print(f"  PDF:   {pdf_path}")
    print(f"{'='*60}")

    open_pdf(paper_id, pdf_path)
    input("\n  Press Enter when you've opened the PDF and are ready to "
          "start reading. Timer starts now.")
    t_start = datetime.now()

    print("\n  — Read the abstract in full, then note your preliminary")
    print("    guess on your scratchpad (NOT here).")
    input("  Press Enter after reading abstract + writing scratchpad guess.")

    print("\n  — Now read the method section and main results table.")
    print("    Use SIGNATURE_CHEATSHEET.md as reference.")
    input("  Press Enter when you're ready to commit labels.")

    # Method
    print(f"\n  Method family ({'/'.join(METHOD_FAMILIES)})?")
    method = ask("  > ", valid=METHOD_FAMILIES)
    supp_m = ask_sentence("method")
    conf_m = ask("  Method confidence (high/medium/low)? ", valid=CONFIDENCES)

    # Direction
    print(f"\n  Direction ({'/'.join(DIRECTIONS)})?")
    direction = ask("  > ", valid=DIRECTIONS)
    supp_d = ask_sentence("direction")
    conf_d = ask("  Direction confidence (high/medium/low)? ", valid=CONFIDENCES)

    # Notes
    print("\n  Notes (edge cases, alternative labels considered, flips "
          "between prelim and final; blank to skip):")
    notes = ask("  > ", allow_empty=True)

    t_end = datetime.now()
    elapsed_min = round((t_end - t_start).total_seconds() / 60)

    if elapsed_min > TIME_HARD_STOP:
        print(f"\n  WARN: {elapsed_min} min exceeds 90-min hard stop.")
        print("  Protocol §4.3: consider logging `needs_discussion` and "
              "revisiting later.")
    elif elapsed_min < TIME_MIN:
        print(f"\n  WARN: {elapsed_min} min is implausibly fast. "
              "Are you sure you read the paper?")

    row = {
        "label_row_id":                next_row_id,
        "paper_id":                    paper_id,
        "annotator_id":                ANNOTATOR_ID,
        "session_date":                t_start.strftime("%Y-%m-%d"),
        "method_family":               method,
        "direction":                   direction,
        "supporting_sentence_method":  supp_m,
        "supporting_sentence_direction": supp_d,
        "confidence_method":           conf_m,
        "confidence_direction":        conf_d,
        "time_spent_minutes":          elapsed_min,
        "is_blind_relabel":            "False",
        "original_label_row_id":       -1,
        "notes":                       notes,
    }
    return row


# ------------------------------------------------------------------ validation

def run_audit() -> int:
    """Run audit_labels.py --validate and return exit code."""
    if not AUDIT_SCRIPT.exists():
        return 0
    r = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--labels", str(LABELS),
         "--validate"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print("\n  ✓ audit_labels.py --validate: all checks clean")
    elif r.returncode == 1:
        print("\n  WARN: audit had non-fatal warnings (normal for small n):")
        for line in r.stdout.splitlines():
            if line.strip().startswith("-"):
                print("   ", line.strip())
    else:
        print("\n  ERROR: audit flagged a hard failure:")
        print(r.stdout)
        print(r.stderr)
    return r.returncode


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", type=str, default=None,
                    help="Label a specific paper_id instead of next unlabeled")
    ap.add_argument("--once", action="store_true",
                    help="Label one paper and exit (skip end-of-session prompt)")
    args = ap.parse_args()

    start_iso, session_row, n_this_session = start_or_continue_session()

    while True:
        paper = pick_next(args.paper)
        if not paper:
            print("\n✓ All 80 manifest papers are labeled. Nothing to do.")
            break

        # Compute next row_id
        next_row_id = len(_read(LABELS)) + 1
        row = label_one_paper(paper["paper_id"], paper["pdf_path"],
                               next_row_id)
        _append(LABELS, row, LABEL_HEADER)
        run_audit()

        n_this_session += 1
        print(f"\n  ✓ Saved row #{next_row_id} for {paper['paper_id']} "
              f"({row['time_spent_minutes']} min).")
        print(f"  Session progress: {n_this_session} paper(s) this session.")

        if args.paper or args.once:
            break

        if n_this_session >= SESSION_HARD_STOP:
            print(f"\n  Hard stop: {SESSION_HARD_STOP} papers this session. "
                  "Protocol §5.2 — do not exceed.")
            break
        if n_this_session >= SESSION_SOFT_WARN:
            print(f"\n  WARN: {n_this_session} papers this session; "
                  "fatigue drops label quality after ~6.")
            cont = ask("  Continue with next paper? (y/n): ",
                       valid=["y", "n", "Y", "N"])
            if cont.lower() == "n":
                break
        else:
            cont = ask("\n  Label next paper? (y/n; n = end session): ",
                       valid=["y", "n", "Y", "N"])
            if cont.lower() == "n":
                break

    close_session(start_iso, n_this_session)
    print("\n  Session closed. Run again tomorrow with "
          "`python3 label_helper.py` to continue.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
