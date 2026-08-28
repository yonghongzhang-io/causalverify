#!/usr/bin/env python3
"""Semantic leakage audit for Phase 1 institutional_context fields.

This is a paid audit when executed because it calls an LLM. It is intentionally
separate from the hard grep in rebuild_metadata_v2primeprime.py:

- hard grep catches literal method-name leakage;
- this audit checks whether IC alone makes the method too easy to infer.

Original pre-reframe thresholds, retained for reporting:
- pilot sample of 5: <= 2/5 method guesses are correct;
- full sample of 50: accuracy <= 35%.

After the 2026-04-27 Stage-3 pilot, this check is reported as an
IC concept-inferability audit rather than a launch gate. See
experiments_log/decisions/2026-04-27__ic_inferability_audit_reframing.md.

GT timing
---------
The default --gt path (audit/gt_aggregate_decisions.json) was voted on V2
fields. This is fine for a Stage-3 pilot audit on V2'' (Phase 2 has not been
re-voted yet, and method labels are stable across Phase 1 versions per the
A2 LOO finding of 5.7% method flip). For the Stage-5 full audit run AFTER
the V2'' Phase 2 re-vote completes, pass an explicit
--gt audit/gt_aggregate_decisions_v2primeprime.json so the audit aligns
with the new GT.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT = ROOT / "audit/regen_from_pdf_v2primeprime.json"
DEFAULT_GT = ROOT / "audit/gt_aggregate_decisions.json"
DEFAULT_OUT = ROOT / "audit/ic_leakage_audit_results.json"
DEFAULT_CACHE = ROOT / "audit/ic_leakage_audit_cache.json"
DEFAULT_SEED = 20260424

METHODS = ["DID", "EVENT_STUDY", "IV", "RDD", "OTHER"]

SYSTEM_PROMPT = """You are auditing a benchmark for leakage.

You will see ONLY an institutional-context field from a finance paper. Your
task is to infer which causal method family the context most likely implies.

Return ONLY a JSON object with these keys:
{
  "method": "DID|EVENT_STUDY|IV|RDD|OTHER",
  "confidence": 0.0,
  "rationale": "one short sentence"
}

Use OTHER if the context is not enough to infer a method family."""

USER_TEMPLATE = """Institutional context:
{institutional_context}

Which method family does this most likely imply?"""


def load_gt(path: Path) -> dict[str, str]:
    rows = json.loads(path.read_text())
    out = {}
    for row in rows:
        method = row.get("new_method") or row.get("method") or row.get("orig_method")
        if method:
            out[row["paper_id"]] = normalize_method(method)
    return out


def normalize_method(value: str) -> str:
    s = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "EVENT": "EVENT_STUDY",
        "EVENTSTUDY": "EVENT_STUDY",
        "EVENT_STUDIES": "EVENT_STUDY",
        "DIFFERENCE_IN_DIFFERENCES": "DID",
        "DIFFERENCE_IN_DIFFERENCE": "DID",
        "DIFF_IN_DIFF": "DID",
        "INSTRUMENTAL_VARIABLE": "IV",
        "INSTRUMENTAL_VARIABLES": "IV",
        "REGRESSION_DISCONTINUITY": "RDD",
        "RD": "RDD",
    }
    return aliases.get(s, s if s in METHODS else "OTHER")


def parse_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\b(DID|EVENT_STUDY|EVENT STUDY|IV|RDD|OTHER)\b", text, re.I)
        parsed = {"method": m.group(1) if m else "OTHER", "confidence": None, "rationale": text[:120]}
    parsed["method"] = normalize_method(str(parsed.get("method", "OTHER")))
    try:
        parsed["confidence"] = float(parsed.get("confidence"))
    except (TypeError, ValueError):
        parsed["confidence"] = None
    return parsed


def load_phase1_rows(input_path: Path, gt_by_pid: dict[str, str]) -> list[dict]:
    rows = []
    for row in json.loads(input_path.read_text()):
        fields = row.get("new_fields") or {}
        ic = str(fields.get("institutional_context", "")).strip()
        pid = row.get("paper_id")
        gt = gt_by_pid.get(pid)
        if not pid or not ic or not gt:
            continue
        rows.append({
            "paper_id": pid,
            "ground_truth": gt,
            "institutional_context": ic,
            "source_type": row.get("source_type", ""),
            "source_chars": row.get("source_chars", 0),
        })
    return rows


def choose_sample(rows: list[dict], sample: str, seed: int,
                   stratified: bool = False) -> list[dict]:
    """Pick `sample` rows from `rows`.

    With stratified=True, distribute the budget equally across method
    families (DID, EVENT_STUDY, IV, RDD), drawing per-family without
    replacement. This is the recommended mode for the Stage-5 n=50 audit
    to avoid DID over-sampling: random sampling on a corpus where DID is
    the most common label biases the headline accuracy number.
    OTHER and any low-frequency family fall back to whatever rows remain.
    """
    rows = sorted(rows, key=lambda r: int(r["paper_id"].split("_")[1]))
    if sample == "all":
        return rows
    n = int(sample)
    if n >= len(rows):
        return rows
    rng = random.Random(seed)
    if not stratified:
        return sorted(rng.sample(rows, n),
                      key=lambda r: int(r["paper_id"].split("_")[1]))

    # Stratified by ground_truth method family.
    by_method: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_method[r["ground_truth"]].append(r)
    families = ["DID", "EVENT_STUDY", "IV", "RDD"]
    quota_each = n // len(families)
    picked: list[dict] = []
    for fam in families:
        pool = by_method.get(fam, [])
        if not pool:
            print(f"  [stratified] family {fam}: 0 rows available")
            continue
        k = min(quota_each, len(pool))
        picked.extend(rng.sample(pool, k))
        print(f"  [stratified] family {fam}: requested {quota_each}, got {k}")
    # Fill any deficit (e.g., a family had < quota_each available) from
    # remaining rows so the total approaches the requested n.
    if len(picked) < n:
        used = {r["paper_id"] for r in picked}
        leftovers = [r for r in rows if r["paper_id"] not in used]
        deficit = n - len(picked)
        picked.extend(rng.sample(leftovers, min(deficit, len(leftovers))))
    return sorted(picked, key=lambda r: int(r["paper_id"].split("_")[1]))


def call_model(model: str, ic: str) -> tuple[dict, dict]:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(institutional_context=ic)},
        ],
        max_tokens=180,
        temperature=0,
    )
    raw = resp.choices[0].message.content or ""
    usage = {
        "input_tokens": getattr(resp.usage, "prompt_tokens", None),
        "output_tokens": getattr(resp.usage, "completion_tokens", None),
    }
    return parse_response(raw), {"raw": raw, "usage": usage}


def summarize(results: list[dict]) -> dict:
    n = len(results)
    correct = sum(1 for r in results if r["correct"])
    by_method = defaultdict(lambda: {"n": 0, "correct": 0})
    confusion = Counter()
    for row in results:
        gt = row["ground_truth"]
        guess = row["guess"]
        by_method[gt]["n"] += 1
        by_method[gt]["correct"] += int(row["correct"])
        confusion[(gt, guess)] += 1
    return {
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else None,
        "pass_pilot_gate_le_2_of_5": correct <= 2 if n == 5 else None,
        "pass_full_gate_le_35pct": (correct / n <= 0.35) if n else None,
        "by_method": {
            method: {
                "n": stats["n"],
                "correct": stats["correct"],
                "accuracy": round(stats["correct"] / stats["n"], 4) if stats["n"] else None,
            }
            for method, stats in sorted(by_method.items())
        },
        "confusion": [
            {"ground_truth": gt, "guess": guess, "n": count}
            for (gt, guess), count in sorted(confusion.items())
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--gt", type=Path, default=DEFAULT_GT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--sample", default="50",
                        help="Number of rows to audit, or 'all'. Use 5 for pilot.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--rate-limit", type=float, default=0.2)
    parser.add_argument("--stratified", action="store_true",
                        help="Distribute sample across DID/EVENT_STUDY/IV/RDD "
                             "rather than uniform random. Use for Stage-5 "
                             "headline number to avoid DID over-sampling.")
    args = parser.parse_args()

    gt_by_pid = load_gt(args.gt)
    rows = choose_sample(load_phase1_rows(args.input, gt_by_pid), args.sample,
                          args.seed, stratified=args.stratified)
    if not rows:
        raise SystemExit("No auditable rows found. Check --input and --gt.")

    cache = {}
    if args.cache.exists() and not args.force:
        cache = {r["paper_id"]: r for r in json.loads(args.cache.read_text())}

    results = []
    print(f"Auditing {len(rows)} IC rows with {args.model}")
    print("Pre-reframe thresholds, reported not launch gates: "
          "pilot 5 <=2 correct; full 50 <=35% accuracy")
    for i, row in enumerate(rows, 1):
        pid = row["paper_id"]
        if pid in cache and not args.force:
            result = cache[pid]
        else:
            parsed, meta = call_model(args.model, row["institutional_context"])
            guess = parsed["method"]
            result = {
                "paper_id": pid,
                "ground_truth": row["ground_truth"],
                "guess": guess,
                "correct": guess == row["ground_truth"],
                "confidence": parsed.get("confidence"),
                "rationale": parsed.get("rationale", ""),
                "source_type": row["source_type"],
                "source_chars": row["source_chars"],
                "ic_excerpt": row["institutional_context"][:350],
                "model": args.model,
                "raw": meta["raw"],
                "usage": meta["usage"],
            }
            cache[pid] = result
            args.cache.write_text(json.dumps(list(cache.values()), indent=2, ensure_ascii=False) + "\n")
            time.sleep(args.rate_limit)
        results.append(result)
        print(f"  [{i:>2}/{len(rows)}] {pid}: gt={result['ground_truth']:<12} "
              f"guess={result['guess']:<12} correct={result['correct']}")

    summary = summarize(results)
    payload = {
        "input": str(args.input.relative_to(ROOT) if args.input.is_relative_to(ROOT) else args.input),
        "gt": str(args.gt.relative_to(ROOT) if args.gt.is_relative_to(ROOT) else args.gt),
        "model": args.model,
        "sample": args.sample,
        "seed": args.seed,
        "summary": summary,
        "results": results,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
