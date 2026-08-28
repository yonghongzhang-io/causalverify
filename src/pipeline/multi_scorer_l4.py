"""
A1: Multi-Scorer L4 Fragility Analysis
=======================================

Implements 5 independent L4 (direction prediction) scorers and runs them
all on the 137-paper × 6-model output corpus to demonstrate that text-based
direction scoring is fundamentally fragile.

Scorers:
  S1: latter_half_keyword     — original (looks at second half)
  S2: section6_keyword        — section-aware (extracts Section 6)
  S3: llm_judge              — Claude Opus reads the output
  S4: structured_extraction  — second-pass prompt asking for JSON {direction}
  S5: token_logprob          — fallback: use S3 since logprob not available

Output:
  experiments/exp_a/multi_scorer_l4.csv     (per-paper × per-model × per-scorer)
  experiments/exp_a/multi_scorer_summary.json (per-model L4 rate under each scorer)

Usage:
  # Run S1 + S2 (deterministic, no API)
  python src/pipeline/multi_scorer_l4.py --scorers s1 s2

  # Run all 5 (S3 + S4 use API, costs ~$10)
  python src/pipeline/multi_scorer_l4.py --scorers s1 s2 s3 s4 s5

  # Run on a small sample first (cheap)
  python src/pipeline/multi_scorer_l4.py --scorers s1 s2 s3 s4 s5 --limit 20
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

PAPERS_DIR = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/exp_a/outputs")
RESULTS_DIR = Path("experiments/exp_a")
CACHE_DIR = Path("experiments/exp_a/multi_scorer_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MODELS = [
    ("moonshot-v1-128k", "Kimi"),
    ("claude-sonnet-4-20250514", "Sonnet"),
    ("gpt-4o", "GPT-4o"),
    ("o3", "o3"),
    ("claude-opus-4-6", "Opus"),
    ("gemini-2.5-flash", "Gemini"),
]

# ── S1: Latter-half keyword (original, broken) ────────────────────────────

DIRECTION_POS = ["positive", "increase", "higher", "gain", "improve",
                 "larger", "upward", "beneficial", "raises"]
DIRECTION_NEG = ["negative", "decrease", "lower", "decline", "worse",
                 "reduces", "destroy", "underperform", "fall", "drop"]


def s1_latter_half(text: str, gt_direction: str) -> str | None:
    """Original scorer: count direction words in the second half of text."""
    tail = text[len(text)//2:].lower()
    pos = sum(tail.count(kw) for kw in DIRECTION_POS)
    neg = sum(tail.count(kw) for kw in DIRECTION_NEG)
    if pos == 0 and neg == 0:
        return None
    return "positive" if pos > neg else "negative"


# ── S2: Section-6 aware (already in evaluate.py / auto_score) ─────────────

def s2_section6_keyword(text: str, gt_direction: str) -> str | None:
    """Find Section 6 'Expected Results', search within that window only."""
    tl = text.lower()
    seg = ""
    for marker in ["6. expected", "## 6", "expected results",
                   "6. prior", "prior expectation"]:
        pos = tl.find(marker)
        if pos >= 0:
            end = pos + 1200
            for stop in ["## 7", "7. validity", "validity checklist",
                         "self-assessment", "c1:", "c1 "]:
                spos = tl.find(stop, pos + 20)
                if spos > 0:
                    end = min(end, spos)
            seg = tl[pos:end]
            break
    if not seg:
        # Fallback: substantive paragraph before checklist
        checklist_start = len(tl)
        for ck in ["validity checklist", "self-assessment",
                   "c1:", "## 7", "7. validity"]:
            cp = tl.rfind(ck)
            if cp > len(tl) // 2:
                checklist_start = min(checklist_start, cp)
        seg = tl[max(0, checklist_start - 800):checklist_start]
    if not seg:
        seg = tl[-800:]

    pos_count = sum(seg.count(kw) for kw in DIRECTION_POS)
    neg_count = sum(seg.count(kw) for kw in DIRECTION_NEG)
    if pos_count == 0 and neg_count == 0:
        return None
    return "positive" if pos_count > neg_count else "negative"


# ── S3: LLM-as-judge (Claude Opus reads output) ────────────────────────────

S3_PROMPT = """You are reading an LLM's response to an empirical economics research question. Your task: extract the model's predicted direction of the main causal effect.

Output ONLY one of: positive, negative, mixed, unstated

- "positive" if the model clearly predicts the main effect is positive
- "negative" if the model clearly predicts the main effect is negative
- "mixed" if the model gives competing predictions or hedges
- "unstated" if no clear direction is given

Output ONLY the single word. No explanation."""


def s3_llm_judge(text: str, gt_direction: str, paper_id: str, model_slug: str) -> str | None:
    """Use Claude Opus as a rater to extract the model's direction."""
    cache_file = CACHE_DIR / f"s3_{paper_id}_{model_slug}.json"
    if cache_file.exists():
        return json.load(open(cache_file)).get("direction")

    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=10,
        system=S3_PROMPT,
        messages=[{"role": "user", "content": text[:6000]}],
    )
    raw = msg.content[0].text.strip().lower()
    if "positive" in raw:
        d = "positive"
    elif "negative" in raw:
        d = "negative"
    elif "mixed" in raw:
        d = "mixed"
    else:
        d = None
    cache_file.write_text(json.dumps({"direction": d, "raw": raw}))
    return d


# ── S4: Structured extraction (second-pass prompt) ────────────────────────

S4_SYSTEM = """Extract the predicted main effect direction from the following empirical research plan. Output STRICTLY a JSON object with this exact schema and nothing else:

{"direction": "positive" | "negative" | "mixed" | "unstated"}

Definitions:
- "positive": the plan clearly anticipates the main effect to be positive
- "negative": the plan clearly anticipates the main effect to be negative
- "mixed": competing or hedged predictions
- "unstated": no clear directional claim"""


def s4_structured(text: str, gt_direction: str, paper_id: str, model_slug: str) -> str | None:
    cache_file = CACHE_DIR / f"s4_{paper_id}_{model_slug}.json"
    if cache_file.exists():
        return json.load(open(cache_file)).get("direction")

    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=50,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": S4_SYSTEM},
            {"role": "user", "content": text[:6000]},
        ],
    )
    raw = resp.choices[0].message.content
    try:
        d = json.loads(raw).get("direction")
        if d not in ("positive", "negative", "mixed", "unstated"):
            d = None
    except json.JSONDecodeError:
        d = None
    cache_file.write_text(json.dumps({"direction": d, "raw": raw}))
    return d


# ── S5: Token-logprob fallback (uses LLM-judge with logprobs) ─────────────

def s5_logprob(text: str, gt_direction: str, paper_id: str, model_slug: str) -> str | None:
    """Use OpenAI logprobs to get P(positive) vs P(negative) at the next token."""
    cache_file = CACHE_DIR / f"s5_{paper_id}_{model_slug}.json"
    if cache_file.exists():
        return json.load(open(cache_file)).get("direction")

    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = f"""The following is an empirical research plan. The plan's predicted direction of the main effect is:

{text[:5500]}

The predicted main effect direction is: """
    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2,
        logprobs=True,
        top_logprobs=10,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    # Look for "positive" vs "negative" in top tokens
    top = resp.choices[0].logprobs.content[0].top_logprobs
    pos_lp = neg_lp = -100.0
    for tlp in top:
        tok = tlp.token.lower().strip()
        if tok.startswith("positive") or tok in ("pos", "+"):
            pos_lp = max(pos_lp, tlp.logprob)
        if tok.startswith("negative") or tok in ("neg", "-"):
            neg_lp = max(neg_lp, tlp.logprob)
    if pos_lp == -100.0 and neg_lp == -100.0:
        d = None
    elif pos_lp > neg_lp:
        d = "positive"
    else:
        d = "negative"
    cache_file.write_text(json.dumps({
        "direction": d, "pos_lp": pos_lp, "neg_lp": neg_lp
    }))
    return d


# ── Main pipeline ─────────────────────────────────────────────────────────

SCORERS = {
    "s1": ("S1_latter_half", s1_latter_half, False),    # no API
    "s2": ("S2_section6", s2_section6_keyword, False),  # no API
    "s3": ("S3_llm_judge", s3_llm_judge, True),         # API: Anthropic
    "s4": ("S4_structured", s4_structured, True),       # API: OpenAI
    "s5": ("S5_logprob", s5_logprob, True),             # API: OpenAI
}


def run_scoring(scorer_keys: list[str], limit: int | None = None):
    papers = sorted(PAPERS_DIR.glob("paper_*.json"),
                    key=lambda p: int(p.stem.split("_")[1]))
    if limit:
        papers = papers[:limit]

    rows = []
    n_papers = len(papers)
    n_total = n_papers * len(MODELS) * len(scorer_keys)
    print(f"Scoring {n_papers} papers × {len(MODELS)} models × {len(scorer_keys)} scorers "
          f"= {n_total} scoring calls", flush=True)

    done = 0
    for p_file in papers:
        paper = json.load(open(p_file))
        pid = paper["paper_id"]
        gt_direction = paper["ground_truth"].get("conclusion_direction", "").lower()
        method = paper.get("method_family", "")
        difficulty = paper.get("difficulty", "")

        for model_slug, model_short in MODELS:
            out_file = OUTPUTS_DIR / f"{pid}_{model_slug}.json"
            if not out_file.exists():
                continue
            llm_out = json.load(open(out_file))
            content = llm_out.get("llm_response", {}).get("content", "")
            if not content:
                continue

            row = {
                "paper_id": pid,
                "method": method,
                "difficulty": difficulty,
                "model": model_short,
                "gt_direction": gt_direction,
            }
            for sk in scorer_keys:
                name, fn, _ = SCORERS[sk]
                try:
                    if sk in ("s3", "s4", "s5"):
                        pred = fn(content, gt_direction, pid, model_slug)
                    else:
                        pred = fn(content, gt_direction)
                except Exception as e:
                    print(f"    [{sk} ERR] {pid}/{model_short}: {e}", flush=True)
                    pred = None
                row[f"{name}_pred"] = pred or ""
                # Match: 1 if pred matches GT, 0 otherwise (mixed/unstated → 0)
                row[f"{name}_match"] = int(pred == gt_direction) if pred in ("positive", "negative") else 0
                done += 1

            rows.append(row)

        if (papers.index(p_file) + 1) % 10 == 0:
            print(f"  Processed {papers.index(p_file)+1}/{n_papers} papers "
                  f"({done}/{n_total} scoring calls)", flush=True)

    # Save CSV
    out_csv = RESULTS_DIR / "multi_scorer_l4.csv"
    if rows:
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSaved per-paper scores: {out_csv}", flush=True)

    # Aggregate per-model L4 rate per scorer
    summary = {}
    scorer_names = [SCORERS[sk][0] for sk in scorer_keys]
    for _, model_short in MODELS:
        model_rows = [r for r in rows if r["model"] == model_short]
        if not model_rows:
            continue
        summary[model_short] = {
            "n_papers": len(model_rows),
        }
        for sname in scorer_names:
            matches = sum(r[f"{sname}_match"] for r in model_rows)
            summary[model_short][f"{sname}_l4"] = round(matches / len(model_rows), 4)

    out_json = RESULTS_DIR / "multi_scorer_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print(f"Saved summary: {out_json}", flush=True)

    # Print summary table
    print("\n" + "="*80, flush=True)
    print("L4 Pass Rate by Scorer", flush=True)
    print("="*80, flush=True)
    header = f"{'Model':<10}"
    for sname in scorer_names:
        header += f" {sname:<18}"
    print(header)
    print("-" * len(header))
    for model_short in [m for _, m in MODELS]:
        if model_short not in summary:
            continue
        line = f"{model_short:<10}"
        for sname in scorer_names:
            rate = summary[model_short].get(f"{sname}_l4", 0)
            line += f" {rate*100:>5.0f}%             "
        print(line)

    # Compute pairwise scorer correlation
    if len(scorer_names) >= 2 and rows:
        print("\n" + "="*80, flush=True)
        print("Pairwise Scorer Agreement (Pearson r on per-paper match)", flush=True)
        print("="*80, flush=True)
        try:
            import numpy as np
            mats = {sname: np.array([r[f"{sname}_match"] for r in rows]) for sname in scorer_names}
            print(f"\n{'':>20}" + "".join(f"{s:>15}" for s in scorer_names))
            for s1 in scorer_names:
                print(f"{s1:>20}", end="")
                for s2 in scorer_names:
                    if s1 == s2:
                        print(f"{1.0:>15.3f}", end="")
                    else:
                        v1, v2 = mats[s1], mats[s2]
                        if v1.std() == 0 or v2.std() == 0:
                            r = float("nan")
                        else:
                            r = float(np.corrcoef(v1, v2)[0, 1])
                        print(f"{r:>15.3f}", end="")
                print()
        except ImportError:
            print("(numpy not available, skipping correlation)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scorers", nargs="+", default=["s1", "s2"],
                        choices=["s1", "s2", "s3", "s4", "s5"])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_scoring(args.scorers, limit=args.limit)


if __name__ == "__main__":
    main()
