#!/usr/bin/env python3
"""Compare Menu-B panel results vs the pre-MenuB state.

Reads:
  audit/gt_reextract_multi.json.preMenuB   (pre: GPT-4o cached + others fresh)
  audit/gt_reextract_multi.json            (post: all 4 fresh disjoint panel)

Reports:
  - per-slot vote-change rate (how many papers each LLM changed its vote)
  - aggregate-level transitions (papers moving between all4/3of4/plurality/tie/split)
  - method-flip and direction-flip count
  - paper_114 specifically (the Dale-Krueger reference case)
  - papers escaping out of the human-adjudication queue
  - papers entering the human-adjudication queue

Also reproduces a summary block suitable for pasting into the paper §3.2
or §6 audit paragraph.

Usage:
  python3 scripts/diff_panel_b_vs_pre.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "audit/gt_reextract_multi.json.preMenuB"
POST = ROOT / "audit/gt_reextract_multi.json"

# Slot mapping pre -> post (the slot keys differ)
SLOT_MAP = {
    "opus_4_7":     "opus_4_7",
    "gpt4o":        "gpt_4o_mini",
    "gemini":       "gemini_2_5_pro",
    "kimi":         "deepseek_v3_2",
}


def index_by_pid(rows):
    return {r["paper_id"]: r for r in rows}


def vote_method(entry: dict) -> str | None:
    if not isinstance(entry, dict):
        return None
    return entry.get("method")


def vote_dir(entry: dict) -> str | None:
    if not isinstance(entry, dict):
        return None
    return entry.get("direction")


def aggregate_method(votes: list[str]) -> tuple[str, str]:
    """Return (top_method, level)."""
    valid = [v for v in votes if v]
    if not valid:
        return ("UNKNOWN", "no_votes")
    c = Counter(valid)
    top, top_n = c.most_common(1)[0]
    n = len(valid)
    if top_n == n == 4:
        return (top, "all4_agree")
    if top_n == 3:
        return (top, "3of4_agree")
    if top_n == 2 and len(c) == 2:
        # 2-2 tie
        return (top, "2of4_tie")
    if top_n == 2 and len(c) >= 3:
        return (top, "2of4_plurality")
    return (top, "split")


def main() -> int:
    pre_rows = json.loads(PRE.read_text())
    post_rows = json.loads(POST.read_text())
    pre = index_by_pid(pre_rows)
    post = index_by_pid(post_rows)

    common = sorted(set(pre) & set(post),
                    key=lambda p: int(p.split("_")[1]))
    print(f"Comparing {len(common)} papers")
    print()

    # 1. Per-slot vote-change rate
    flip_count = {pre_k: 0 for pre_k in SLOT_MAP}
    valid_count = {pre_k: 0 for pre_k in SLOT_MAP}
    for pid in common:
        for pre_k, post_k in SLOT_MAP.items():
            v_pre = vote_method(pre[pid].get(pre_k, {}))
            v_post = vote_method(post[pid].get(post_k, {}))
            if v_pre and v_post:
                valid_count[pre_k] += 1
                if v_pre != v_post:
                    flip_count[pre_k] += 1

    print("Per-slot vote change (pre -> post):")
    print(f"  {'Slot':<22} {'Flips':>6} {'Valid':>6} {'%Flip':>7}")
    for pre_k, post_k in SLOT_MAP.items():
        f, v = flip_count[pre_k], valid_count[pre_k]
        pct = 100*f/max(1, v)
        print(f"  {pre_k} -> {post_k:<10} {f:>6} {v:>6} {pct:>6.1f}%")
    print()

    # 2. Aggregate transitions
    pre_levels = []
    post_levels = []
    transitions = Counter()
    method_flips = 0
    dir_flips = 0
    enter_human = []   # papers that move INTO needs_human (tie/split)
    exit_human = []    # papers that move OUT of needs_human

    HUMAN_LEVELS = {"2of4_tie", "split", "no_votes"}

    for pid in common:
        pre_methods = [vote_method(pre[pid].get(k)) for k in SLOT_MAP]
        post_methods = [vote_method(post[pid].get(SLOT_MAP[k])) for k in SLOT_MAP]
        pre_top, pre_level = aggregate_method(pre_methods)
        post_top, post_level = aggregate_method(post_methods)
        pre_levels.append(pre_level)
        post_levels.append(post_level)
        transitions[(pre_level, post_level)] += 1
        if pre_top != post_top:
            method_flips += 1

        pre_dirs = [vote_dir(pre[pid].get(k)) for k in SLOT_MAP]
        post_dirs = [vote_dir(post[pid].get(SLOT_MAP[k])) for k in SLOT_MAP]
        pre_d_top, _ = aggregate_method(pre_dirs)
        post_d_top, _ = aggregate_method(post_dirs)
        if pre_d_top != post_d_top:
            dir_flips += 1

        in_pre = pre_level in HUMAN_LEVELS
        in_post = post_level in HUMAN_LEVELS
        if not in_pre and in_post:
            enter_human.append(pid)
        if in_pre and not in_post:
            exit_human.append(pid)

    pre_dist = Counter(pre_levels)
    post_dist = Counter(post_levels)
    print("Aggregation level distribution (method):")
    print(f"  {'Level':<18} {'Pre':>6} {'Post':>6} {'Δ':>6}")
    for lvl in ["all4_agree", "3of4_agree", "2of4_plurality",
                "2of4_tie", "split", "no_votes"]:
        a, b = pre_dist[lvl], post_dist[lvl]
        print(f"  {lvl:<18} {a:>6} {b:>6} {b-a:>+6}")
    print()
    print(f"Method top-vote flips:     {method_flips}/{len(common)}")
    print(f"Direction top-vote flips:  {dir_flips}/{len(common)}")
    print()
    print(f"Papers entering human-adjudication queue: {len(enter_human)}")
    if enter_human[:10]:
        print(f"  e.g.: {', '.join(enter_human[:10])}")
    print(f"Papers exiting human-adjudication queue: {len(exit_human)}")
    if exit_human[:10]:
        print(f"  e.g.: {', '.join(exit_human[:10])}")
    print()

    # 3. paper_114 specifically
    if "paper_114" in pre and "paper_114" in post:
        print("paper_114 (Dale and Krueger 2002, matching + group FE):")
        for label, src, key_map in [("PRE-MenuB", pre, SLOT_MAP), ("POST-MenuB", post, SLOT_MAP)]:
            r = src["paper_114"]
            line = []
            for pre_k, post_k in SLOT_MAP.items():
                k = pre_k if label == "PRE-MenuB" else post_k
                m = vote_method(r.get(k))
                line.append(f"{pre_k}={m}")
            print(f"  {label:<11} {' / '.join(line)}")
            methods = [vote_method(r.get(SLOT_MAP[k] if label=='POST-MenuB' else k))
                       for k in SLOT_MAP]
            top, lvl = aggregate_method(methods)
            print(f"  {' '*11}  -> top={top} level={lvl}")
    print()


if __name__ == "__main__":
    main()
