#!/usr/bin/env python3
"""GT re-extraction with the V2'' Menu-B panel — fresh votes from 4 LLMs.

Why
---
The original audit/gt_reextract_multi.json had three problems:

  1. GPT-4o vote was 100% sourced from V1-era cached labels
     (`source: "cached_from_paper_json"`), not a fresh V2'' call. The
     four-LLM panel was effectively three-LLM.
  2. Three of four panel members (Kimi v1-128k, Gemini 2.5 Flash,
     GPT-4o) shared the exact API model with three of seven evaluated
     models, partially violating the anti-fox-in-henhouse separation
     claimed in §3.2.
  3. paper_114 (Dale and Krueger 2002, matching + group fixed effects)
     was misclassified as IV by two cached/heuristic votes; only Opus
     correctly flagged it as OTHER.

This script re-runs the panel with **Menu B**, which is fully
disjoint from the seven evaluated models:

  Slot 1: claude-opus-4-7              (Opus 4.7   — ≠ Opus 4.6 in eval)
  Slot 2: gpt-4o-mini                  (mini       — ≠ gpt-4o / o3 / gpt-5)
  Slot 3: gemini-2.5-pro               (Pro        — ≠ Gemini 2.5 Flash)
  Slot 4: deepseek-ai/DeepSeek-V3.2    (open-weights frontier, via Nebius;
                                        DeepSeek vendor lineage absent
                                        from the evaluated pool)

Cost: ~$3 total for 259 papers.

Output
------
audit/gt_reextract_multi.json (overwrites the previous mixed state)

Usage
-----
  python3 scripts/gt_reextract_panel_b.py --smoke 5    # 5-paper smoke
  python3 scripts/gt_reextract_panel_b.py --all        # full 259
  python3 scripts/gt_reextract_panel_b.py --resume     # only fill in
                                                       # missing/error votes
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Manual .env load (avoids dotenv heredoc quirk)
ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

sys.path.insert(0, str(ROOT / "src" / "agents"))
from gt_reextract_multi import (  # type: ignore
    STRICT_PROMPT_SYS, build_user, _strip_fences,
)

PAPERS_DIR = ROOT / "experiments/exp_a/papers"
OUT_JSON = ROOT / "audit/gt_reextract_multi.json"
BACKUP_JSON = ROOT / "audit/gt_reextract_multi.json.preMenuB"


# ── Slot model IDs ────────────────────────────────────────────────────

SLOTS = [
    ("opus_4_7",        "claude-opus-4-7",            "anthropic"),
    ("gpt_4o_mini",     "gpt-4o-mini",                "openai"),
    ("gemini_2_5_pro",  "gemini-2.5-pro",             "google_oai_compat"),
    ("deepseek_v3_2",   "deepseek-ai/DeepSeek-V3.2",  "nebius"),
]


# ── Per-vendor callers ───────────────────────────────────────────────

def call_anthropic(model: str, paper: dict) -> dict:
    import anthropic
    c = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    r = c.messages.create(
        model=model, max_tokens=300,
        system=STRICT_PROMPT_SYS,
        messages=[{"role": "user", "content": build_user(paper)}],
    )
    return json.loads(_strip_fences(r.content[0].text))


def call_openai(model: str, paper: dict, base_url: str | None = None,
                api_key_env: str = "OPENAI_API_KEY",
                max_tokens: int = 300) -> dict:
    from openai import OpenAI
    kw = {"api_key": os.getenv(api_key_env)}
    if base_url:
        kw["base_url"] = base_url
    c = OpenAI(**kw)
    r = c.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": STRICT_PROMPT_SYS},
            {"role": "user",   "content": build_user(paper)},
        ],
    )
    return json.loads(_strip_fences(r.choices[0].message.content))


def call_slot(slot_id: str, model: str, vendor: str, paper: dict) -> dict:
    if vendor == "anthropic":
        return call_anthropic(model, paper)
    if vendor == "openai":
        return call_openai(model, paper)
    if vendor == "google_oai_compat":
        # Gemini Pro needs more output budget for "thinking" tokens
        return call_openai(
            model, paper,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key_env="GOOGLE_API_KEY",
            max_tokens=2048,
        )
    if vendor == "nebius":
        return call_openai(
            model, paper,
            base_url="https://api.studio.nebius.com/v1/",
            api_key_env="NEBIUS_API_KEY",
        )
    raise ValueError(f"Unknown vendor: {vendor}")


# ── Normalisation ────────────────────────────────────────────────────

def normalise_method(m) -> str:
    if not m:
        return "OTHER"
    m = str(m).upper().replace(" ", "_").replace("-", "_")
    if m in ("ES", "EVENT_STUDY"):
        return "EVENT_STUDY"
    if m in ("DID", "EVENT_STUDY", "IV", "RDD", "OTHER"):
        return m
    return "OTHER"


def normalise_dir(d) -> str | None:
    if d is None:
        return None
    d = str(d).lower()
    if d in ("positive", "negative", "mixed", "unclear"):
        return d
    return None


def normalised_vote(parsed: dict) -> dict:
    return {
        "method": normalise_method(parsed.get("method_family")),
        "secondary_method": (
            normalise_method(parsed.get("secondary_method"))
            if parsed.get("secondary_method") else None
        ),
        "direction": normalise_dir(parsed.get("direction")),
        "confidence": parsed.get("confidence"),
        "source": "fresh_v2pp_panel_b",
    }


# ── Main ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=None,
                    help="Smoke test on first N papers (~$0.05 for N=5)")
    ap.add_argument("--all", action="store_true", help="Run all 259 papers")
    ap.add_argument("--resume", action="store_true",
                    help="Only call slots whose vote is missing/error")
    ap.add_argument("--slot", type=str, default=None,
                    help=f"Restrict to one slot: {[s[0] for s in SLOTS]}")
    args = ap.parse_args()
    if args.smoke is None and not args.all and not args.resume:
        ap.error("--smoke N or --all or --resume required")

    # 1. Load papers
    paper_files = sorted(PAPERS_DIR.glob("paper_*.json"),
                         key=lambda p: int(p.stem.split("_")[1]))
    paper_by_id = {json.loads(f.read_text())["paper_id"]:
                   json.loads(f.read_text()) for f in paper_files}
    print(f"Loaded {len(paper_by_id)} papers from {PAPERS_DIR}")

    # 2. Backup existing OUT_JSON before overwrite (only on first call)
    if OUT_JSON.exists() and not BACKUP_JSON.exists():
        BACKUP_JSON.write_text(OUT_JSON.read_text())
        print(f"Backup: {BACKUP_JSON}")

    # 3. Load or initialise rows
    if OUT_JSON.exists():
        rows = json.loads(OUT_JSON.read_text())
        rows_by_pid = {r["paper_id"]: r for r in rows}
    else:
        rows_by_pid = {pid: {"paper_id": pid} for pid in paper_by_id}

    # 4. Determine paper subset
    pids = sorted(paper_by_id.keys(), key=lambda p: int(p.split("_")[1]))
    if args.smoke:
        pids = pids[: args.smoke]
        print(f"Smoke test: {len(pids)} papers")
    print(f"Processing {len(pids)} papers x {len(SLOTS)} slots")

    # 5. Loop
    n_done = {sid: 0 for sid, _, _ in SLOTS}
    n_skip = {sid: 0 for sid, _, _ in SLOTS}
    n_err = {sid: 0 for sid, _, _ in SLOTS}
    t0 = time.time()

    for i, pid in enumerate(pids, 1):
        paper = paper_by_id[pid]
        row = rows_by_pid.setdefault(pid, {"paper_id": pid})
        for sid, model, vendor in SLOTS:
            if args.slot and sid != args.slot:
                continue
            existing = row.get(sid, {}) or {}
            if args.resume:
                # Skip only if existing has a non-error fresh result
                if (existing.get("source") == "fresh_v2pp_panel_b"
                        and existing.get("method")
                        and "error" not in existing):
                    n_skip[sid] += 1
                    continue
            try:
                parsed = call_slot(sid, model, vendor, paper)
                row[sid] = normalised_vote(parsed)
                n_done[sid] += 1
            except Exception as e:
                row[sid] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
                n_err[sid] += 1
            time.sleep(0.1)

        # Progress
        votes = [row.get(sid, {}).get("method", "?") for sid, _, _ in SLOTS]
        print(f"  [{i:>3}/{len(pids)}] {pid:<10} -> "
              f"O={votes[0]:<11} G4om={votes[1]:<11} "
              f"Gpro={votes[2]:<11} DS={votes[3]:<11}")

        # Save every 25 papers
        if i % 25 == 0:
            rows_out = [rows_by_pid[p] for p in
                        sorted(rows_by_pid, key=lambda p: int(p.split("_")[1]))]
            OUT_JSON.write_text(json.dumps(rows_out, indent=2, ensure_ascii=False))

    # 6. Final write
    rows_out = [rows_by_pid[p] for p in
                sorted(rows_by_pid, key=lambda p: int(p.split("_")[1]))]
    OUT_JSON.write_text(json.dumps(rows_out, indent=2, ensure_ascii=False))
    print()
    print("=" * 70)
    print(f"Wrote: {OUT_JSON}")
    print(f"{'Slot':<16} {'Done':>6} {'Skip':>6} {'Error':>6}")
    print("-" * 40)
    for sid, _, _ in SLOTS:
        print(f"  {sid:<14} {n_done[sid]:>6} {n_skip[sid]:>6} {n_err[sid]:>6}")
    print(f"Wall time: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
