"""
D1 — Prompt Sensitivity Experiment
====================================
Tests whether the ES detection boundary is prompt-induced or method-inherent.

Design:
  V0 (baseline): Current prompt with method names in system + Section 1
  V1 (method-blind): All method family names removed from prompts

Papers: All 29 ES + 10 each of DID/IV/RDD (stratified sample) = 59 papers
Models: GPT-4o, o3, Gemini Flash (representing L3-high, ES-low, ES-high)

If ES remains lowest under V1 → boundary is method-inherent, not prompt-induced.
If ES improves significantly → prompt framing contributes to ES under-detection.

Usage:
  python src/pipeline/run_prompt_sensitivity.py --all --model gpt-4o
  python src/pipeline/run_prompt_sensitivity.py --score
"""

import argparse
import json
import os
import re
import random
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

PAPERS_DIR  = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/prompt_sensitivity/outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ── V1: Method-blind prompt (no method names anywhere) ──────────

V1_SYSTEM_PROMPT = """\
You are a financial economist with expertise in empirical causal inference
methods. You are helping conduct original empirical research.

Your task: Given a research question, available data, and institutional context,
propose a rigorous identification strategy and outline the empirical methodology.

IMPORTANT: Do NOT read ahead or guess the actual paper's methodology. Work only
from the information provided. Propose what YOU would do given this setup.
"""

V1_USER_TEMPLATE = """\
# Research Setup

## Research Question
{research_question}

## Available Data
{data_description}

## Institutional Context
{institutional_context}

---

Please provide a complete empirical research plan with the following sections:

## 1. Identification Strategy
State clearly which causal identification strategy you would use and why.
Justify why this strategy is appropriate for this research question and data.

## 2. Treatment and Control
Define precisely:
- Treatment variable (what constitutes "treated")
- Control group (what serves as counterfactual)
- Treatment timing or key variation (if applicable)

## 3. Key Identifying Assumptions
List the main assumptions required for your strategy to yield causal estimates.
For each assumption, discuss whether it is plausible given the institutional context.

## 4. Threats to Identification
Identify the 2-3 most important threats to your identification strategy.
How would you address each threat?

## 5. R Code Outline
Write executable R code for the main specification. Include:
- Data loading steps (assume data is in CSV format)
- Variable construction
- Main regression using appropriate package
- At least one robustness check

## 6. Expected Results
State your prior expectation for the direction of the main effect and its
approximate magnitude (if you can form a prior from economic theory).

## 7. Validity Checklist Self-Assessment
Rate yourself on 5 key validity criteria for your chosen method
(1 = clearly satisfied, 0 = questionable or absent).
"""

# ── LLM callers (reuse from run_exp_a.py) ───────────────────────

def call_llm(paper: dict, model: str, system_prompt: str, user_template: str) -> dict:
    user_msg = user_template.format(
        research_question=paper["research_question"],
        data_description=paper["data_description"],
        institutional_context=paper["institutional_context"],
    )

    m = model.lower()
    if "claude" in m:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=model, max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        return {"model": model, "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
                "content": msg.content[0].text, "stop_reason": msg.stop_reason}

    elif "gpt" in m or m.startswith("o3") or m.startswith("o1"):
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        token_kwarg = "max_completion_tokens" if m.startswith("o3") or m.startswith("o1") else "max_tokens"
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_msg}],
            **{token_kwarg: 4096},
        )
        return {"model": model, "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
                "content": resp.choices[0].message.content,
                "stop_reason": resp.choices[0].finish_reason}

    elif "gemini" in m:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("GOOGLE_API_KEY"),
                        base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        resp = client.chat.completions.create(
            model=model, max_tokens=16384,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_msg}],
        )
        return {"model": model, "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
                "content": resp.choices[0].message.content,
                "stop_reason": resp.choices[0].finish_reason}

    elif "moonshot" in m:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("KIMI_API_KEY"),
                        base_url="https://api.moonshot.cn/v1")
        resp = client.chat.completions.create(
            model=model, max_tokens=4096,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_msg}],
        )
        return {"model": model, "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
                "content": resp.choices[0].message.content,
                "stop_reason": resp.choices[0].finish_reason}

    raise ValueError(f"Unknown model: {model}")


# ── Scoring (same as evaluate.py) ───────────────────────────────

METHOD_KEYWORDS = {
    "DID":         [r"difference.in.difference", r"\bDID\b", r"DiD", r"diff.in.diff", r"parallel trend"],
    "EVENT_STUDY": [r"event study", r"event.window", r"abnormal return", r"\bCAR\b", r"\bAAR\b",
                    r"cumulative abnormal", r"announcement"],
    "IV":          [r"instrumental variable", r"\bIV\b(?!\w)", r"\b2SLS\b", r"first.stage",
                    r"\binstrument\b", r"two.stage"],
    "RDD":         [r"regression discontinuity", r"\bRDD\b", r"running variable", r"cutoff",
                    r"bandwidth", r"forcing variable", r"discontinuity"],
}

DIRECTION_KEYWORDS = {
    "positive": [r"\bpositive\b", r"increase[sd]?", r"higher", r"greater", r"upward"],
    "negative": [r"\bnegative\b", r"decrease[sd]?", r"lower", r"decline[sd]?", r"reduc"],
}


def detect_method(text):
    # Section-aware: Section 1 gets 3x weight
    s1_match = re.search(r"(?i)(?:##?\s*1[\.\s]|section\s*1|identification strategy)(.*?)(?=##?\s*2[\.\s]|section\s*2|treatment|$)", text[:3000], re.DOTALL)
    s1_text = s1_match.group(1) if s1_match else text[:500]

    counts = {}
    for m, pats in METHOD_KEYWORDS.items():
        full_hits = sum(len(re.findall(p, text, re.I)) for p in pats)
        s1_hits = sum(len(re.findall(p, s1_text, re.I)) for p in pats)
        score = full_hits + 2 * s1_hits  # Section 1 gets 3x total
        if score:
            counts[m] = score

    # DID/ES disambiguation
    if "DID" in counts and "EVENT_STUDY" in counts:
        did_s1 = sum(len(re.findall(p, s1_text, re.I)) for p in METHOD_KEYWORDS["DID"])
        if did_s1 > 0:
            counts["EVENT_STUDY"] = int(counts["EVENT_STUDY"] * 0.5)

    return max(counts, key=counts.get) if counts else None


def detect_direction(text):
    tail = text[len(text)//2:]
    pos = sum(len(re.findall(p, tail, re.I)) for p in DIRECTION_KEYWORDS["positive"])
    neg = sum(len(re.findall(p, tail, re.I)) for p in DIRECTION_KEYWORDS["negative"])
    if pos == 0 and neg == 0:
        return None
    return "positive" if pos > neg else "negative"


# ── Paper selection ─────────────────────────────────────────────

def select_papers() -> list[dict]:
    """All 29 ES + 10 random each of DID/IV/RDD = ~59 papers."""
    all_papers = []
    by_method = {}
    for f in sorted(PAPERS_DIR.glob("paper_*.json")):
        p = json.loads(f.read_text())
        by_method.setdefault(p["method_family"], []).append(p)

    # All ES
    selected = list(by_method.get("EVENT_STUDY", []))

    # 10 random from each other method
    random.seed(42)
    for method in ["DID", "IV", "RDD"]:
        pool = by_method.get(method, [])
        selected.extend(random.sample(pool, min(10, len(pool))))

    print(f"Selected {len(selected)} papers: "
          f"ES={sum(1 for p in selected if p['method_family']=='EVENT_STUDY')}, "
          f"DID={sum(1 for p in selected if p['method_family']=='DID')}, "
          f"IV={sum(1 for p in selected if p['method_family']=='IV')}, "
          f"RDD={sum(1 for p in selected if p['method_family']=='RDD')}")
    return selected


# ── Runner ──────────────────────────────────────────────────────

def run_all(model: str, force: bool = False):
    papers = select_papers()
    slug = model.replace("/", "-").replace(":", "-")
    print(f"\nPrompt Sensitivity V1 (method-blind): {len(papers)} papers × {model}")
    print("=" * 60)

    ok = 0
    for paper in papers:
        pid = paper["paper_id"]
        out_file = OUTPUTS_DIR / f"{pid}_{slug}_v1.json"
        if out_file.exists() and not force:
            print(f"  [SKIP] {pid}")
            ok += 1
            continue

        try:
            resp = call_llm(paper, model, V1_SYSTEM_PROMPT, V1_USER_TEMPLATE)
            det_m = detect_method(resp["content"])
            det_d = detect_direction(resp["content"])
            true_m = paper["method_family"]
            gt = paper["ground_truth"]
            true_d = (gt.get("conclusion_direction", "") if isinstance(gt, dict) else "").lower()

            l3 = (det_m == true_m) if det_m else False
            l4 = (det_d == true_d) if det_d and true_d else False

            result = {
                "paper_id": pid,
                "method_family": true_m,
                "difficulty": paper.get("difficulty", ""),
                "model": model,
                "prompt_variant": "V1_method_blind",
                "run_at": datetime.now().isoformat(),
                "llm_response": resp,
                "scores": {
                    "L3_strategy": l3,
                    "L4_direction": l4,
                    "detected_method": det_m,
                    "detected_direction": det_d,
                    "true_method": true_m,
                    "true_direction": true_d,
                },
            }
            out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            print(f"  [DONE] {pid} | {true_m} | L3={'P' if l3 else 'F'} L4={'P' if l4 else 'F'} | det={det_m}")
            ok += 1
        except Exception as e:
            print(f"  [ERR ] {pid}: {e}")
        time.sleep(0.5)

    print(f"\nDone: {ok}/{len(papers)}")


# ── Score & Compare ─────────────────────────────────────────────

def score_and_compare(models: list[str]):
    """Compare V0 (baseline from Exp A) vs V1 (method-blind)."""
    papers = select_papers()
    paper_ids = {p["paper_id"] for p in papers}
    paper_map = {p["paper_id"]: p for p in papers}

    exp_a_dir = Path("experiments/exp_a/outputs")

    print("\n" + "=" * 70)
    print("Prompt Sensitivity: V0 (baseline) vs V1 (method-blind)")
    print("=" * 70)

    for model in models:
        slug = model.replace("/", "-").replace(":", "-")
        short = {"gpt-4o": "GPT-4o", "o3": "o3", "gemini-2.5-flash": "Gemini",
                 "moonshot-v1-128k": "Kimi", "claude-sonnet-4-20250514": "Sonnet",
                 "claude-opus-4-6": "Opus"}.get(model, model)

        v0_l3 = {}  # method -> [0/1]
        v1_l3 = {}

        for pid in sorted(paper_ids):
            paper = paper_map[pid]
            method = paper["method_family"]
            true_m = method

            # V0: baseline from Exp A
            v0_file = exp_a_dir / f"{pid}_{slug}.json"
            if v0_file.exists():
                o = json.loads(v0_file.read_text())
                content = o.get("llm_response", {}).get("content", "") or o.get("content", "")
                det = detect_method(content)
                v0_l3.setdefault(method, []).append(int(det == true_m) if det else 0)

            # V1: method-blind
            v1_file = OUTPUTS_DIR / f"{pid}_{slug}_v1.json"
            if v1_file.exists():
                o = json.loads(v1_file.read_text())
                det = o["scores"]["detected_method"]
                v1_l3.setdefault(method, []).append(int(o["scores"]["L3_strategy"]))

        print(f"\n── {short} ──")
        print(f"  {'Method':<14} {'N':>4} {'V0 L3':>8} {'V1 L3':>8} {'Δ':>8}")
        print(f"  {'-'*44}")

        for method in ["RDD", "DID", "IV", "EVENT_STUDY"]:
            v0 = v0_l3.get(method, [])
            v1 = v1_l3.get(method, [])
            n = min(len(v0), len(v1))
            if n == 0:
                continue
            v0_rate = sum(v0[:n]) / n * 100
            v1_rate = sum(v1[:n]) / n * 100
            delta = v1_rate - v0_rate
            label = "ES" if method == "EVENT_STUDY" else method
            print(f"  {label:<14} {n:>4} {v0_rate:>7.0f}% {v1_rate:>7.0f}% {delta:>+7.0f}pp")

        # Overall
        all_v0 = sum(sum(v) for v in v0_l3.values())
        all_v0_n = sum(len(v) for v in v0_l3.values())
        all_v1 = sum(sum(v) for v in v1_l3.values())
        all_v1_n = sum(len(v) for v in v1_l3.values())
        if all_v0_n and all_v1_n:
            print(f"  {'TOTAL':<14} {min(all_v0_n,all_v1_n):>4} "
                  f"{all_v0/all_v0_n*100:>7.0f}% {all_v1/all_v1_n*100:>7.0f}% "
                  f"{all_v1/all_v1_n*100 - all_v0/all_v0_n*100:>+7.0f}pp")


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="D1: Prompt sensitivity experiment")
    parser.add_argument("--all", action="store_true", help="Run V1 on selected papers")
    parser.add_argument("--score", action="store_true", help="Compare V0 vs V1")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--models", nargs="+", default=["gpt-4o", "o3", "gemini-2.5-flash"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.all:
        run_all(args.model, force=args.force)
    elif args.score:
        score_and_compare(args.models)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
