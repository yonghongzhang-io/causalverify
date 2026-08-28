#!/usr/bin/env python3
"""Retry Exp A outputs whose provider response has empty content.

This is intentionally small and conservative: it only force-reruns files
that already exist but contain no usable `llm_response.content`. It is
useful for transient provider failures such as Gemini returning
`output_tokens=0, content=null, stop_reason=stop`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT / "experiments/exp_a/outputs"
RUNNER = ROOT / "src/pipeline/run_exp_a.py"


def has_usable_content(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return False
    content = payload.get("llm_response", {}).get("content")
    return isinstance(content, str) and bool(content.strip())


def find_bad_outputs(model: str, papers: list[str] | None = None) -> list[str]:
    suffix = f"_{model}.json"
    bad = []
    for path in sorted(OUTPUTS_DIR.glob(f"paper_*{suffix}"),
                       key=lambda p: int(p.name.split("_")[1])):
        paper_id = "_".join(path.name.split("_")[:2])
        if papers and paper_id not in papers:
            continue
        if not has_usable_content(path):
            bad.append(paper_id)
    return bad


def run_one(paper_id: str, model: str) -> int:
    cmd = [
        sys.executable,
        str(RUNNER),
        "--paper",
        paper_id,
        "--model",
        model,
        "--force",
    ]
    print(f"\n[retry] {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=ROOT)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--papers", default="",
                        help="Comma-separated paper ids. Omit to scan all outputs for model.")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--sleep", type=int, default=300,
                        help="Initial sleep seconds between attempts.")
    parser.add_argument("--backoff", type=float, default=2.0)
    args = parser.parse_args()

    papers = [p.strip() for p in args.papers.split(",") if p.strip()] or None
    wait = args.sleep

    for attempt in range(1, args.attempts + 1):
        bad = find_bad_outputs(args.model, papers)
        print(f"\nAttempt {attempt}/{args.attempts}: bad_count={len(bad)}", flush=True)
        for paper_id in bad:
            print(f"  bad: {paper_id}", flush=True)

        if not bad:
            print("All targeted outputs have usable content.", flush=True)
            return 0

        for paper_id in bad:
            run_one(paper_id, args.model)

        remaining = find_bad_outputs(args.model, papers)
        print(f"\nAfter attempt {attempt}: remaining_bad={len(remaining)}", flush=True)
        for paper_id in remaining:
            print(f"  remaining: {paper_id}", flush=True)

        if not remaining:
            print("All targeted outputs have usable content.", flush=True)
            return 0

        if attempt < args.attempts:
            print(f"Sleeping {wait}s before next attempt...", flush=True)
            time.sleep(wait)
            wait = int(wait * args.backoff)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
