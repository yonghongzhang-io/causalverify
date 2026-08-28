"""
Experiment C v2 — RID Ablation on Exp A Papers (Proposal-aligned)
==================================================================
Runs RID-ON on the same 10 Exp A papers (RID-OFF = Exp A baseline).
Computes proper TPR / FPR against ground truth.

TPR = proportion of correct cases correctly identified as correct (with RID)
FPR = proportion of incorrect cases incorrectly endorsed (without RID vs with RID)

Here we operationalize:
  True Positive  = model gets L3a (strategy) AND L3b (direction) correct
  False Positive = model claims valid strategy but gets it wrong

Usage:
  python src/pipeline/run_exp_c_v2.py --all --model moonshot-v1-128k
  python src/pipeline/run_exp_c_v2.py --all --model claude-sonnet-4-20250514
  python src/pipeline/run_exp_c_v2.py --report
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

PAPERS_DIR    = Path("experiments/exp_a/papers")
EXP_A_OUTPUTS = Path("experiments/exp_a/outputs")          # RID-OFF baseline
OUTPUTS_DIR   = Path("experiments/exp_c_v2/outputs")        # RID-ON results
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ── RID-augmented prompt (same as run_exp_c.py) ───────────────────────

SYSTEM_PROMPT = """You are an expert financial economist and econometrician operating under
Research Integrity by Design (RID) constraints.

RID requires a strict 5-step protocol:

STEP 1 — PRE-COMMITMENT
State your causal identification strategy and directional hypothesis NOW,
before analyzing the data description in detail. You may NOT change these after Step 1.

STEP 2 — SPECIFICATION DISCIPLINE
List EXACTLY the specifications you will run — no more than 5.
Commit to these now; no additions after seeing results.

STEP 3 — FALSIFICATION GATE
State explicitly: what empirical result would cause you to REJECT your hypothesis?
Be specific (sign reversal, p > 0.10, failed pre-trend test, weak first stage F < 10).

STEP 4 — R CODE
Write complete, self-contained R code implementing ONLY the pre-committed specifications.

STEP 5 — FINDINGS & GATE ASSESSMENT
Report expected numerical results and state whether they would trigger your falsification gate.

Follow all 5 steps in order. Do not skip or reorder."""

USER_PROMPT_TEMPLATE = """Research scenario from published financial economics paper:

Research question:
{research_question}

Data description:
{data_description}

Institutional context:
{institutional_context}

BEGIN RID PROTOCOL — follow all 5 steps in order."""


def build_prompt(paper: dict) -> str:
    return USER_PROMPT_TEMPLATE.format(
        research_question=paper["research_question"],
        data_description=paper["data_description"],
        institutional_context=paper["institutional_context"],
    )


# ── LLM callers ───────────────────────────────────────────────────────

def call_anthropic(paper: dict, model: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model=model, max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(paper)}],
    )
    return {"model": model, "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
            "content": msg.content[0].text, "stop_reason": msg.stop_reason}


def call_openai_compat(paper: dict, model: str, api_key_env: str,
                       base_url: str | None = None) -> dict:
    from openai import OpenAI
    kwargs = {"api_key": os.getenv(api_key_env)}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    token_kwarg = "max_completion_tokens" if model.startswith("o3") or model.startswith("o1") else "max_tokens"
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": build_prompt(paper)}],
        **{token_kwarg: 4096},
    )
    return {"model": model,
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
            "content": resp.choices[0].message.content,
            "stop_reason": resp.choices[0].finish_reason}


def call_llm(paper: dict, model: str) -> dict:
    m = model.lower()
    if "claude" in m:
        return call_anthropic(paper, model)
    elif "moonshot" in m:
        return call_openai_compat(paper, model, "KIMI_API_KEY",
                                  "https://api.moonshot.cn/v1")
    elif "gpt" in m or m.startswith("o3"):
        return call_openai_compat(paper, model, "OPENAI_API_KEY")
    elif "gemini" in m:
        return call_openai_compat(paper, model, "GOOGLE_API_KEY",
                                  "https://generativelanguage.googleapis.com/v1beta/openai/")
    raise ValueError(f"Unknown model: {model}")


# ── Auto scoring helpers ──────────────────────────────────────────────

METHOD_KEYWORDS = {
    "DID":         [r"difference.in.difference", r"\bDID\b", r"DiD"],
    "EVENT_STUDY": [r"event study", r"abnormal return", r"\bCAR\b", r"\bAAR\b"],
    "IV":          [r"instrumental variable", r"\bIV\b(?!\w)", r"\b2SLS\b", r"first.stage"],
    "RDD":         [r"regression discontinuity", r"\bRDD\b", r"running variable", r"cutoff"],
}
DIRECTION_KEYWORDS = {
    "positive": [r"\bpositive\b", r"increase[sd]?", r"higher", r"greater"],
    "negative": [r"\bnegative\b", r"decrease[sd]?", r"lower", r"decline[sd]?", r"reduc"],
}


def detect_method(text):
    counts = {}
    for m, pats in METHOD_KEYWORDS.items():
        h = sum(len(re.findall(p, text, re.I)) for p in pats)
        if h:
            counts[m] = h
    return max(counts, key=counts.get) if counts else None


def detect_direction(text):
    tail = text[len(text)//2:]
    pos = sum(len(re.findall(p, tail, re.I)) for p in DIRECTION_KEYWORDS["positive"])
    neg = sum(len(re.findall(p, tail, re.I)) for p in DIRECTION_KEYWORDS["negative"])
    if pos == 0 and neg == 0:
        return None
    return "positive" if pos > neg else "negative"


def score_response(paper: dict, content: str) -> dict:
    gt       = paper["ground_truth"]
    true_m   = paper["method_family"]
    true_dir = gt.get("conclusion_direction", "").lower()
    det_m    = detect_method(content)
    det_dir  = detect_direction(content)
    l3a = (det_m == true_m) if det_m else False
    l3b = (det_dir == true_dir) if det_dir else False
    return {"L3a_strategy": l3a, "L3b_direction": l3b,
            "detected_method": det_m, "detected_direction": det_dir,
            "true_method": true_m, "true_direction": true_dir}


# ── Runner ────────────────────────────────────────────────────────────

def load_papers() -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(PAPERS_DIR.glob("paper_*.json"))]


def run_all(model: str, force: bool = False):
    papers = load_papers()
    slug   = model.replace("/", "-").replace(":", "-")
    print(f"Experiment C v2 (RID-ON): {len(papers)} papers × model={model}")
    print("=" * 60)
    ok = 0
    for paper in papers:
        pid      = paper["paper_id"]
        out_file = OUTPUTS_DIR / f"{pid}_{slug}.json"
        if out_file.exists() and not force:
            print(f"  [SKIP] {pid}")
            ok += 1
            continue
        try:
            resp   = call_llm(paper, model)
            scored = score_response(paper, resp["content"])
            result = {
                "paper_id": pid, "method_family": paper["method_family"],
                "difficulty": paper["difficulty"], "model": model,
                "experiment": "C_v2_RID_ON",
                "run_at": datetime.now().isoformat(),
                "llm_response": resp, "scores": scored,
                "_ground_truth": paper["ground_truth"],
            }
            out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            print(f"  [DONE] {pid} | {paper['method_family']}/{paper['difficulty']} "
                  f"| L3a={'✓' if scored['L3a_strategy'] else '✗'} "
                  f"L3b={'✓' if scored['L3b_direction'] else '✗'}")
            ok += 1
        except Exception as e:
            print(f"  [ERR ] {pid}: {e}")
        time.sleep(0.4)
    print(f"\nDone: {ok}/{len(papers)}")


# ── TPR/FPR Report ────────────────────────────────────────────────────

def tpr_fpr_report(models: list[str]):
    """Compare RID-OFF (Exp A) vs RID-ON (Exp C v2) with proper TPR/FPR."""
    import csv, io

    print("\n" + "=" * 65)
    print("Experiment C v2 — TPR / FPR Report")
    print("RID-OFF = Exp A outputs | RID-ON = Exp C v2 outputs")
    print("=" * 65)

    # Load Exp A auto scores (RID-OFF)
    a_scores = {}
    with open("experiments/exp_a/auto_scores.csv") as f:
        for row in csv.DictReader(f):
            a_scores[row["paper_id"]] = row

    # Map model slug -> auto_scores.csv column prefix
    SLUG_TO_COL = {
        "moonshot-v1-128k":         "Kimi-128k",
        "claude-sonnet-4-20250514": "Claude-Sonnet",
        "gpt-4o":                   "GPT-4o",
        "o3":                       "o3",
        "claude-opus-4-6":          "Claude-Opus",
        "gemini-2.5-flash":         "Gemini-2.5",
    }

    for model in models:
        slug  = model.replace("/", "-").replace(":", "-")
        short = {"moonshot-v1-128k": "Kimi-128k",
                 "claude-sonnet-4-20250514": "Claude-Sonnet",
                 "gpt-4o": "GPT-4o", "o3": "o3",
                 "claude-opus-4-6": "Claude-Opus",
                 "gemini-2.5-flash": "Gemini-2.5"}.get(model, model)

        print(f"\n── {short} ──")
        print(f"  {'Paper':<10} {'Method':<14} {'Diff':<8} "
              f"{'OFF L3a':>8} {'OFF L3b':>8} {'ON L3a':>8} {'ON L3b':>8}")
        print(f"  {'-'*68}")

        off_l3a = off_l3b = on_l3a = on_l3b = 0
        n = 0
        for pid in sorted(a_scores.keys()):
            row   = a_scores[pid]
            model_key = SLUG_TO_COL.get(model, "Claude-Sonnet")
            off_a = int(row.get(f"{model_key}_L3a", 0))
            off_b = int(row.get(f"{model_key}_L3b", 0))

            on_file = OUTPUTS_DIR / f"{pid}_{slug}.json"
            if on_file.exists():
                d    = json.loads(on_file.read_text())
                on_a = int(d["scores"]["L3a_strategy"])
                on_b = int(d["scores"]["L3b_direction"])
            else:
                on_a = on_b = -1   # not run

            print(f"  {pid:<10} {row['method']:<14} {row['difficulty']:<8} "
                  f"{'✓' if off_a else '✗':>8} {'✓' if off_b else '✗':>8} "
                  f"{'✓' if on_a==1 else ('?' if on_a==-1 else '✗'):>8} "
                  f"{'✓' if on_b==1 else ('?' if on_b==-1 else '✗'):>8}")
            if on_a >= 0:
                off_l3a += off_a; off_l3b += off_b
                on_l3a  += on_a;  on_l3b  += on_b
                n += 1

        print(f"\n  Strategy (L3a): RID-OFF={off_l3a}/{n}  RID-ON={on_l3a}/{n}  "
              f"Δ={on_l3a-off_l3a:+d}")
        print(f"  Direction (L3b): RID-OFF={off_l3b}/{n}  RID-ON={on_l3b}/{n}  "
              f"Δ={on_l3b-off_l3b:+d}")

        # TPR/FPR framing
        # TPR = P(correctly identified | true strategy exists) = on_l3a/n
        # FPR = P(wrong strategy endorsed) = (n-on_l3a)/n
        print(f"\n  TPR (correct strategy rate, RID-ON):  {on_l3a/n:.0%}")
        print(f"  FPR (wrong strategy rate,  RID-ON):   {(n-on_l3a)/n:.0%}")
        print(f"  vs baseline RID-OFF TPR: {off_l3a/n:.0%} | FPR: {(n-off_l3a)/n:.0%}")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all",    action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--model",  type=str, default="moonshot-v1-128k")
    parser.add_argument("--models", nargs="+",
                        default=["moonshot-v1-128k", "claude-sonnet-4-20250514"])
    parser.add_argument("--force",  action="store_true")
    args = parser.parse_args()

    if args.all:
        run_all(args.model, force=args.force)
    elif args.report:
        tpr_fpr_report(args.models)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
