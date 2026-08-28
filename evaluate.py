#!/usr/bin/env python3
"""evaluate.py — reviewer-facing dispatcher for CausalVerify entry points.

This is a SAFE wrapper. It does not call any LLM API. It does not
modify frozen artifacts. It does not pretend to be the official
benchmark scorer; it just routes to the current scoring scripts so that
reviewers reproducing the paper do not have to memorise paths.

The legacy CAUSAL-BENCH-era evaluator that previously lived at this
path was moved to ``legacy/evaluate_v1_causalbench.py``; see
``legacy/README.md``.

Usage
-----
    python evaluate.py --check          # cross-doc claim consistency
    python evaluate.py --exp-a-score    # rerun L1/L2a/L2b/L3/L4 scoring
    python evaluate.py --exp-b-ranking  # rerun L2b vs L2b+ ranking
    python evaluate.py --robustness     # rerun Exp B robustness aggregation
    python evaluate.py --all            # all of the above

None of these subcommands make LLM API calls. The L2b+ judge re-scoring
needs a separate command (``python scripts/l2b_llm_judge_extract.py``)
because it reads the cached judge JSON; it is intentionally NOT exposed
here so this dispatcher cannot accidentally trigger network traffic.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ENTRY_POINTS = [
    ("--check", "Cross-document claim consistency",
     [sys.executable, "scripts/check_claim_consistency.py"]),
    ("--exp-a-score", "Score Exp A L1/L2a/L2b/L3/L4 from frozen outputs",
     [sys.executable, "src/pipeline/auto_score_exp_a.py"]),
    ("--exp-b-ranking", "L2b/L2b+/L4 head-to-head Kendall and Spearman",
     [sys.executable, "src/pipeline/head_to_head_ranking.py"]),
    ("--robustness", "Aggregate Exp B robustness panels",
     [sys.executable, "scripts/analyze_exp_b_robustness.py"]),
]


def _run(label: str, cmd: list[str]) -> int:
    print(f"\n--- {label} ---", flush=True)
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="CausalVerify reviewer-facing dispatcher (no LLM API calls)."
    )
    for flag, help_text, _cmd in ENTRY_POINTS:
        ap.add_argument(flag, action="store_true", help=help_text)
    ap.add_argument("--all", action="store_true",
                    help="Run every safe entry point in order.")
    args = ap.parse_args()

    selected = [(flag, label, cmd) for flag, label, cmd in ENTRY_POINTS
                if args.all or getattr(args, flag.lstrip("-").replace("-", "_"))]
    if not selected:
        ap.print_help()
        print("\nNote: this dispatcher never calls an LLM API.")
        print("To re-judge L2b+ from scratch, run "
              "`python scripts/l2b_llm_judge_extract.py` directly; that script "
              "reads the cached judge JSON and only spends API calls on cells "
              "that are not already in the cache.")
        return 0

    rc = 0
    for flag, label, cmd in selected:
        rc |= _run(label, cmd)
    return rc


if __name__ == "__main__":
    sys.exit(main())
