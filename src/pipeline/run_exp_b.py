"""
Experiment B — Full Pipeline Runner
=====================================
Gives each LLM a research scenario + data preview, asks for:
  1. Identification strategy
  2. Complete, runnable R code
  3. Expected findings

Usage:
  python src/pipeline/run_exp_b.py --list
  python src/pipeline/run_exp_b.py --scenario s01 --model moonshot-v1-128k
  python src/pipeline/run_exp_b.py --all --model moonshot-v1-128k
  python src/pipeline/run_exp_b.py --all --model claude-sonnet-4-20250514
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SCENARIOS_DIR = Path("experiments/exp_b/scenarios")
DATA_DIR      = Path("experiments/exp_b/data")
OUTPUTS_DIR   = Path("experiments/exp_b/outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Prompt ────────────────────────────────────────────────────────────

# The prompt text and prompt builder live in src/prompts/exp_b.py so they can
# be imported without this module's side effects (dotenv, output-dir creation).
# The names are re-exported here unchanged for existing importers of this module.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.prompts.exp_b import (  # noqa: E402
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    build_user_prompt,
)


# ── LLM callers ───────────────────────────────────────────────────────

def call_anthropic(scenario: dict, model: str) -> dict:
    try:
        import anthropic
    except ImportError:
        raise ImportError("pip install anthropic")
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(scenario)}],
    )
    return {
        "model": model,
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
        "content": msg.content[0].text,
        "stop_reason": msg.stop_reason,
    }


def call_openai_compat(scenario: dict, model: str,
                       api_key_env: str, base_url: str | None = None) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("pip install openai")
    kwargs = {"api_key": os.getenv(api_key_env)}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    # Reasoning models (o-series, GPT-5) use max_completion_tokens and
    # burn a lot of tokens on internal thinking; bump budget generously.
    is_reasoning = (model.startswith("o3") or model.startswith("o1")
                    or model.startswith("o4") or model.startswith("gpt-5"))
    token_kwarg = "max_completion_tokens" if is_reasoning else "max_tokens"
    max_out = 16384 if is_reasoning else 4096
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(scenario)},
        ],
        **{token_kwarg: max_out},
    )
    return {
        "model": model,
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "content": resp.choices[0].message.content,
        "stop_reason": resp.choices[0].finish_reason,
    }


def call_llm(scenario: dict, model: str) -> dict:
    m = model.lower()
    if "claude" in m:
        return call_anthropic(scenario, model)
    elif "moonshot" in m:
        return call_openai_compat(scenario, model,
                                  api_key_env="KIMI_API_KEY",
                                  base_url="https://api.moonshot.cn/v1")
    elif "gpt" in m or m.startswith("o3") or m.startswith("o1"):
        return call_openai_compat(scenario, model, api_key_env="OPENAI_API_KEY")
    elif "gemini" in m:
        return call_openai_compat(scenario, model, api_key_env="GOOGLE_API_KEY",
                                  base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    elif (m.startswith("meta-llama/") or m.startswith("qwen/")
          or m.startswith("mistralai/") or m.startswith("deepseek-ai/")
          or m.startswith("nousresearch/") or m.startswith("microsoft/")):
        return call_openai_compat(scenario, model, api_key_env="NEBIUS_API_KEY",
                                  base_url="https://api.studio.nebius.com/v1/")
    else:
        raise ValueError(f"Unknown model: {model}. Prefix with claude/moonshot/gpt/o3/gemini, "
                         f"or use a Nebius vendor prefix (meta-llama/qwen/mistralai/...).")


# ── Runner ────────────────────────────────────────────────────────────

def load_scenarios() -> list[dict]:
    files = sorted(SCENARIOS_DIR.glob("s*.json"))
    return [json.loads(f.read_text()) for f in files]


def run_scenario(scenario: dict, model: str, force: bool = False) -> dict | None:
    sid = scenario["scenario_id"]
    slug = model.replace("/", "-").replace(":", "-")
    out_file = OUTPUTS_DIR / f"{sid}_{slug}.json"

    if out_file.exists() and not force:
        print(f"  [SKIP] {sid} already done → {out_file.name}")
        return json.loads(out_file.read_text())

    try:
        llm_resp = call_llm(scenario, model)
        result = {
            "scenario_id": sid,
            "method_family": scenario["method_family"],
            "difficulty": scenario["difficulty"],
            "title": scenario["title"],
            "model": model,
            "run_at": datetime.utcnow().isoformat(),
            "llm_response": llm_resp,
            "_ground_truth": scenario["ground_truth"],
        }
        out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"  [DONE] {sid} | {scenario['method_family']}/{scenario['difficulty']}")
        print(f"         tokens: {llm_resp['input_tokens']} in / {llm_resp['output_tokens']} out")
        return result
    except Exception as e:
        print(f"  [ERR ] {sid}: {e}")
        return None


def run_all(model: str, force: bool = False, shard: str | None = None):
    scenarios = load_scenarios()
    if shard:
        k, n = (int(x) for x in shard.split("/"))
        scenarios = [s for i, s in enumerate(scenarios) if i % n == (k - 1)]
        print(f"  [shard {k}/{n}] taking {len(scenarios)} scenarios")
    print(f"Running Experiment B: {len(scenarios)} scenarios × model={model}")
    print("=" * 65)
    ok = 0
    for sc in scenarios:
        result = run_scenario(sc, model, force=force)
        if result:
            ok += 1
        time.sleep(0.5)   # light rate-limit buffer
    print(f"\nDone: {ok}/{len(scenarios)} succeeded")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list",     action="store_true")
    parser.add_argument("--all",      action="store_true")
    parser.add_argument("--scenario", type=str)
    parser.add_argument("--model",    type=str, default="moonshot-v1-128k")
    parser.add_argument("--force",    action="store_true")
    parser.add_argument("--shard",    type=str, default=None,
                        help="Shard k/N (1-indexed) — every Nth scenario")
    args = parser.parse_args()

    if args.list:
        for sc in load_scenarios():
            print(f"  {sc['scenario_id']:<6} {sc['method_family']:<14} "
                  f"{sc['difficulty']:<8} {sc['title'][:50]}")
        return

    if args.all:
        run_all(args.model, force=args.force, shard=args.shard)
    elif args.scenario:
        scenarios = {sc["scenario_id"]: sc for sc in load_scenarios()}
        sc = scenarios.get(args.scenario)
        if not sc:
            print(f"Scenario not found: {args.scenario}")
            sys.exit(1)
        run_scenario(sc, args.model, force=args.force)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
