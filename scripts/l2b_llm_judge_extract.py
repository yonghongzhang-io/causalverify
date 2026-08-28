#!/usr/bin/env python3
"""LLM-judge re-extractor for L2b+ treatment-effect coefficients.

Replaces the brittle regex in score_l2b_plus.py for cases where R code
ran successfully (L2b=1) but coefficient extraction either returned None
or pulled the wrong number from the regression table.

Spot-check (audit/l2b_extraction_spot_check.json) showed 73% of L2b+
failures with L2b=1 are scorer issues, not model issues. This script
fixes that by sending R stdout + the executed R code + scenario method
context to Haiku, which returns the treatment-effect estimate.

Cost: ~$0.30-0.50 for ~350 L2b=1 cells across 6 models × 100 scenarios.

Usage:
  python3 scripts/l2b_llm_judge_extract.py --validate 30   # sanity-check 30 first
  python3 scripts/l2b_llm_judge_extract.py --all           # full re-judge
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "pipeline"))
from score_l2b_plus import extract_r_code, execute_r_code  # type: ignore

SCORES_CSV = ROOT / "experiments/exp_b/l2b_plus_scores_canonical.csv"
OUTPUTS_DIR = ROOT / "experiments/exp_b/outputs"
DGP_VERIF = ROOT / "audit/dgp_verification.json"
JUDGE_CACHE = ROOT / "audit/l2b_judge_cache.json"
NEW_SCORES_CSV = ROOT / "experiments/exp_b/l2b_plus_scores_canonical_judge.csv"
NEW_SUMMARY = ROOT / "experiments/exp_b/l2b_plus_summary_canonical_judge.json"

JUDGE_MODEL = "claude-haiku-4-5-20251001"
TOLERANCE = 0.5

METHOD_GUIDANCE = {
    "DID": (
        "DID with two-way fixed effects. The treatment effect is the "
        "coefficient on the treat-by-post interaction term (often named "
        "treat_x_post, did, treated:post, or equivalent)."
    ),
    "EVENT_STUDY": (
        "Event-study using a market model on stock returns. The treatment "
        "effect is the coefficient on the post-event indicator (event_day "
        ">= 0), or the average abnormal return over the post-event window. "
        "Do NOT return individual day-by-day abnormal returns or pre-event "
        "coefficients. If the script reports a single 'effect' or 'event_dummy' "
        "coefficient, that is it."
    ),
    "IV": (
        "Instrumental variables (2SLS). The treatment effect is the "
        "coefficient on the endogenous regressor (often named x or D), "
        "instrumented by z. Do NOT return the first-stage coefficient on z."
    ),
    "RDD": (
        "Sharp regression discontinuity. The treatment effect is the "
        "coefficient on the treatment indicator (often named treated, "
        "above_cutoff, or D) in the local linear regression around the cutoff."
    ),
}

SYSTEM_PROMPT = """You are an expert econometrician reviewing R regression output.

Given:
1. The R code that was executed.
2. The R script's stdout (output).
3. The intended causal-inference method.

Return ONLY a JSON object:
{
  "effect": <number> or null,
  "rationale": "<one short sentence describing where you found it>"
}

Rules:
- Return the SCALAR treatment effect coefficient, not its standard error
  or t-statistic.
- If the output truly does not contain a treatment-effect estimate
  (e.g. the model failed silently, or the script printed only summary stats
  with no coefficient table), return effect=null.
- Do not invent numbers. Only return numbers that visibly appear in stdout.
- Round to 4 decimal places.
"""

USER_TEMPLATE = """Method: {method}

Method context: {method_guidance}

Scenario: {title}

R code that was executed:
```r
{r_code}
```

R stdout:
```
{stdout}
```

What is the treatment-effect coefficient? Return JSON only."""


def load_canonical() -> dict[str, float]:
    payload = json.loads(DGP_VERIF.read_text())
    return {r["scenario_id"]: float(r["estimated"]) for r in payload["results"]
            if r.get("estimated") is not None}


def load_cache() -> dict:
    if JUDGE_CACHE.exists():
        return json.loads(JUDGE_CACHE.read_text())
    return {}


def save_cache(cache: dict) -> None:
    JUDGE_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def call_judge(method: str, title: str, r_code: str, stdout: str) -> tuple[float | None, str, dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    user = USER_TEMPLATE.format(
        method=method,
        method_guidance=METHOD_GUIDANCE.get(method, "(no method guidance)"),
        title=title[:200],
        r_code=r_code[:4000],
        stdout=stdout[:6000],
    )
    r = client.messages.create(
        model=JUDGE_MODEL, max_tokens=200, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    raw = r.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip("` \n")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'"effect"\s*:\s*(-?\d+\.?\d*(?:[eE][-+]?\d+)?|null)', raw)
        parsed = {"effect": None, "rationale": f"parse_error: {raw[:120]}"}
        if m and m.group(1) != "null":
            try:
                parsed["effect"] = float(m.group(1))
            except ValueError:
                pass
    eff = parsed.get("effect")
    if isinstance(eff, str):
        try:
            eff = float(eff)
        except ValueError:
            eff = None
    rationale = str(parsed.get("rationale", ""))[:200]
    usage = {
        "input_tokens": r.usage.input_tokens,
        "output_tokens": r.usage.output_tokens,
        "cost_usd": r.usage.input_tokens * 1 / 1_000_000 + r.usage.output_tokens * 5 / 1_000_000,
    }
    return eff, rationale, usage


def select_cases(rows: list[dict], mode: str, n: int) -> list[dict]:
    """Pick which (scenario × model) cells to judge."""
    suspects = [r for r in rows if r["L2b"] == "1"]
    if mode == "all":
        return suspects
    if mode == "validate":
        # Stratified: equal across models
        by_model = defaultdict(list)
        for r in suspects:
            by_model[r["model"]].append(r)
        rng = random.Random(20260427)
        picked = []
        per_model = max(1, n // max(1, len(by_model)))
        for m, rs in by_model.items():
            picked.extend(rng.sample(rs, min(per_model, len(rs))))
        return picked[:n]
    raise ValueError(mode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", type=int, default=None,
                    help="Run on a stratified sample of N cases for sanity check.")
    ap.add_argument("--all", action="store_true",
                    help="Judge all L2b=1 cases.")
    ap.add_argument(
        "--cache-only", action="store_true",
        help=("Verify the cache covers every L2b=1 cell that --all/--validate "
              "would visit, without ever instantiating an Anthropic client. "
              "Exits 0 if all required keys are cached, nonzero otherwise. "
              "Does not modify the cache, scores, or any frozen artifact."),
    )
    args = ap.parse_args()
    if not args.all and args.validate is None:
        ap.error("--validate N or --all required")

    canonical = load_canonical()
    rows = list(csv.DictReader(open(SCORES_CSV)))
    cases = select_cases(rows, "all" if args.all else "validate", args.validate or 0)
    print(f"L2b=1 cells in CSV: {sum(1 for r in rows if r['L2b']=='1')}")
    print(f"Will judge: {len(cases)}")

    cache = load_cache()

    if args.cache_only:
        # Read-only audit. Never touch Anthropic, never write any file.
        needed = [
            f"{c['scenario_id']}__{c['model_slug']}"
            for c in cases
        ]
        missing = [k for k in needed if k not in cache]
        n_total = len(needed)
        n_present = n_total - len(missing)
        coverage = (n_present / n_total * 100.0) if n_total else 100.0
        print(f"[cache-only] cache entries: {len(cache)}")
        print(f"[cache-only] required cache keys: {n_total}")
        print(f"[cache-only] present in cache:   {n_present} "
              f"({coverage:.1f}%)")
        print(f"[cache-only] missing from cache: {len(missing)}")
        if missing:
            example = ", ".join(missing[:3])
            more = f" (+{len(missing)-3} more)" if len(missing) > 3 else ""
            print(f"[cache-only] example missing keys: {example}{more}")
            print("[cache-only] FAIL: no-new-LLM reproduction not possible "
                  "with the current cache. Re-run without --cache-only "
                  "(this is a paid path).")
            return 1
        print("[cache-only] OK: all required L2b judge keys are cached. "
              "No API calls would be made by --all.")
        return 0
    total_cost = 0.0
    n_done = 0
    n_eff = 0
    n_l2b_plus_new = 0
    judge_outputs: dict[str, dict] = {}

    for i, case in enumerate(cases, 1):
        sid = case["scenario_id"]
        model_slug = case["model_slug"]
        cache_key = f"{sid}__{model_slug}"
        if cache_key in cache:
            r = cache[cache_key]
            judge_outputs[cache_key] = r
            n_done += 1
            if r.get("effect") is not None:
                n_eff += 1
            if r.get("l2b_plus_new") == 1:
                n_l2b_plus_new += 1
            continue

        out_file = OUTPUTS_DIR / f"{sid}_{model_slug}.json"
        if not out_file.exists():
            continue
        d = json.loads(out_file.read_text())
        content = d.get("llm_response", {}).get("content", "")
        title = d.get("title", "")
        r_code = extract_r_code(content)
        if r_code is None:
            continue
        ok, stdout, _err = execute_r_code(r_code)
        if not ok:
            continue

        try:
            eff, rationale, usage = call_judge(case["method"], title, r_code, stdout)
        except Exception as e:
            cache[cache_key] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
            save_cache(cache)
            print(f"  [{i:>3}/{len(cases)}] {sid} {case['model']:<8} ERROR: {e}")
            continue

        canon = canonical.get(sid)
        rel_err = None
        l2b_plus_new = 0
        if eff is not None and canon is not None and abs(canon) > 1e-9:
            rel_err = abs(eff - canon) / abs(canon)
            l2b_plus_new = int(rel_err < TOLERANCE)

        record = {
            "scenario_id": sid,
            "model": case["model"],
            "model_slug": model_slug,
            "method": case["method"],
            "canonical": canon,
            "regex_estimated": float(case["estimated"]) if case["estimated"] not in ("", "None") else None,
            "regex_l2b_plus": int(case["L2b_plus"]),
            "judge_effect": eff,
            "judge_rationale": rationale,
            "rel_error_judge": rel_err,
            "l2b_plus_new": l2b_plus_new,
            "usage": usage,
        }
        cache[cache_key] = record
        judge_outputs[cache_key] = record
        save_cache(cache)
        total_cost += usage["cost_usd"]
        n_done += 1
        if eff is not None:
            n_eff += 1
        if l2b_plus_new:
            n_l2b_plus_new += 1
        flag = "+" if l2b_plus_new else "."
        eff_s = f"{eff:+.4f}" if eff is not None else "  null "
        print(f"  [{i:>3}/{len(cases)}] {sid} {case['model']:<8} "
              f"canon={canon:+.3f}  judge={eff_s}  {flag}  ${usage['cost_usd']:.5f}")
        time.sleep(0.15)

    print()
    print("=" * 70)
    print(f"Judged: {n_done}/{len(cases)}")
    print(f"Returned a number: {n_eff}/{n_done} ({n_eff/max(1,n_done)*100:.0f}%)")
    print(f"NEW L2b+ pass: {n_l2b_plus_new}/{n_done}")
    print(f"Cost: ${total_cost:.4f}")
    if args.validate:
        # Compare with regex outcome on the same cells
        regex_pass = sum(int(case["L2b_plus"]) for case in cases)
        print(f"Regex L2b+ pass (same cells): {regex_pass}")
        print(f"Δ judge − regex = {n_l2b_plus_new - regex_pass:+d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
