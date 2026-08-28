#!/usr/bin/env python3
"""4-provider API dry-run: minimal hello call to each LLM provider.

Verifies API key + connectivity + reports per-provider token + cost so we
catch quota / rate-limit / network problems before launching V2'' full or
the 7-LLM Exp A rerun.

Each call is intentionally tiny (max ~10 output tokens). Total cost
should be under $0.02 across all 4 providers.

Usage:
  python3 scripts/api_dryrun.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROMPT = "Reply with a single word: ok"


def test_anthropic_opus_47() -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    t0 = time.time()
    r = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=10,
        messages=[{"role": "user", "content": PROMPT}],
    )
    cost = r.usage.input_tokens * 15 / 1_000_000 + r.usage.output_tokens * 75 / 1_000_000
    return {
        "provider": "Anthropic",
        "model": "claude-opus-4-7",
        "ok": True,
        "input_tokens": r.usage.input_tokens,
        "output_tokens": r.usage.output_tokens,
        "cost_usd": round(cost, 6),
        "latency_s": round(time.time() - t0, 2),
        "reply": r.content[0].text[:60],
    }


def test_openai_o3() -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    t0 = time.time()
    # o3 uses max_completion_tokens, no temperature override
    r = client.chat.completions.create(
        model="o3",
        max_completion_tokens=200,  # o3 reserves reasoning_tokens internally
        messages=[{"role": "user", "content": PROMPT}],
    )
    in_t = r.usage.prompt_tokens
    out_t = r.usage.completion_tokens
    # o3 pricing (approx 2026-04): $2/M input, $8/M output
    cost = in_t * 2 / 1_000_000 + out_t * 8 / 1_000_000
    return {
        "provider": "OpenAI",
        "model": "o3",
        "ok": True,
        "input_tokens": in_t,
        "output_tokens": out_t,
        "cost_usd": round(cost, 6),
        "latency_s": round(time.time() - t0, 2),
        "reply": (r.choices[0].message.content or "")[:60],
    }


def test_openai_gpt5() -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    t0 = time.time()
    r = client.chat.completions.create(
        model="gpt-5",
        max_completion_tokens=200,
        messages=[{"role": "user", "content": PROMPT}],
    )
    in_t = r.usage.prompt_tokens
    out_t = r.usage.completion_tokens
    # GPT-5 pricing (approx): use same $2/M $8/M envelope
    cost = in_t * 2 / 1_000_000 + out_t * 8 / 1_000_000
    return {
        "provider": "OpenAI",
        "model": "gpt-5",
        "ok": True,
        "input_tokens": in_t,
        "output_tokens": out_t,
        "cost_usd": round(cost, 6),
        "latency_s": round(time.time() - t0, 2),
        "reply": (r.choices[0].message.content or "")[:60],
    }


def test_kimi() -> dict:
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("KIMI_API_KEY"),
        base_url="https://api.moonshot.cn/v1",
    )
    t0 = time.time()
    r = client.chat.completions.create(
        model="moonshot-v1-128k",
        max_tokens=10,
        messages=[{"role": "user", "content": PROMPT}],
    )
    in_t = r.usage.prompt_tokens
    out_t = r.usage.completion_tokens
    # Moonshot pricing (CNY -> USD approx): $1.7/M input, $1.7/M output
    cost = (in_t + out_t) * 1.7 / 1_000_000
    return {
        "provider": "Moonshot",
        "model": "moonshot-v1-128k",
        "ok": True,
        "input_tokens": in_t,
        "output_tokens": out_t,
        "cost_usd": round(cost, 6),
        "latency_s": round(time.time() - t0, 2),
        "reply": (r.choices[0].message.content or "")[:60],
    }


def test_gemini() -> dict:
    # Project pattern (gt_reextract_multi.py L154): OpenAI-compatible endpoint.
    # Gemini 2.5 Flash silently uses ~1.5K thinking tokens, so request a
    # generous max_tokens even for a hello-world call.
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    t0 = time.time()
    r = client.chat.completions.create(
        model="gemini-2.5-flash",
        max_tokens=2048,
        messages=[{"role": "user", "content": PROMPT}],
    )
    in_t = r.usage.prompt_tokens
    out_t = r.usage.completion_tokens
    # Gemini 2.5 Flash pricing: $0.075/M input, $0.30/M output (approx)
    cost = in_t * 0.075 / 1_000_000 + out_t * 0.30 / 1_000_000
    return {
        "provider": "Google",
        "model": "gemini-2.5-flash",
        "ok": True,
        "input_tokens": in_t,
        "output_tokens": out_t,
        "cost_usd": round(cost, 6),
        "latency_s": round(time.time() - t0, 2),
        "reply": (r.choices[0].message.content or "")[:60],
    }


TESTS = [
    ("anthropic_opus_47", test_anthropic_opus_47),
    ("openai_o3",         test_openai_o3),
    ("openai_gpt5",       test_openai_gpt5),
    ("kimi",              test_kimi),
    ("gemini",            test_gemini),
]


def main() -> int:
    results = []
    total_cost = 0.0
    print(f"{'Provider':<10} {'Model':<22} {'in':>5} {'out':>5} "
          f"{'cost($)':>9} {'lat(s)':>6}  reply")
    print("-" * 90)
    for name, fn in TESTS:
        try:
            r = fn()
            results.append({"name": name, **r})
            total_cost += r["cost_usd"]
            print(f"{r['provider']:<10} {r['model']:<22} "
                  f"{r['input_tokens']:>5} {r['output_tokens']:>5} "
                  f"{r['cost_usd']:>9.6f} {r['latency_s']:>6.2f}  "
                  f"{r['reply'][:40]!r}")
        except Exception as e:
            err = type(e).__name__ + ": " + str(e)[:120]
            results.append({"name": name, "ok": False, "error": err})
            print(f"{name:<33} FAIL  {err[:60]}")
            traceback.print_exc(file=sys.stderr)
    print("-" * 90)
    print(f"Total: {sum(1 for r in results if r.get('ok'))} / {len(results)} ok, "
          f"${total_cost:.6f} spent")
    out_path = Path("audit/api_dryrun_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_cost_usd": round(total_cost, 6),
        "results": results,
    }, indent=2, ensure_ascii=False))
    print(f"Saved: {out_path}")
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
