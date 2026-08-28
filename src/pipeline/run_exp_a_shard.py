"""
Sharded version of run_exp_a.py — runs only papers where paper_num % shards == shard_id.

Enables N-way parallelism with no race conditions: each shard processes
a disjoint subset of papers, so multiple instances can run safely.

Usage:
  # Shard 0 of 3
  python src/pipeline/run_exp_a_shard.py --model gemini-2.5-flash --shards 3 --shard 0
  # Shard 1 of 3
  python src/pipeline/run_exp_a_shard.py --model gemini-2.5-flash --shards 3 --shard 1
  # Shard 2 of 3
  python src/pipeline/run_exp_a_shard.py --model gemini-2.5-flash --shards 3 --shard 2
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Reuse the existing implementation
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.pipeline.run_exp_a import run_paper, PAPERS_DIR


def natural_paper_num(p: Path) -> int:
    try:
        return int(p.stem.split("_")[1])
    except (IndexError, ValueError):
        return 999999


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--shards", type=int, default=3)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not (0 <= args.shard < args.shards):
        print(f"ERROR: --shard must be in [0, {args.shards-1}]")
        sys.exit(1)

    papers = sorted(PAPERS_DIR.glob("paper_*.json"), key=natural_paper_num)
    my_papers = [p for p in papers if natural_paper_num(p) % args.shards == args.shard]

    print(f"[shard {args.shard}/{args.shards}] Processing {len(my_papers)} papers "
          f"with model={args.model}", flush=True)

    success = 0
    for p in my_papers:
        result = run_paper(p, args.model, force=args.force)
        if "error" not in result:
            success += 1

    print(f"[shard {args.shard}/{args.shards}] Done: {success}/{len(my_papers)}", flush=True)


if __name__ == "__main__":
    main()
