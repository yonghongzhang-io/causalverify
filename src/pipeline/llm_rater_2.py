"""
LLM Rater 2 — Independent inter-rater reliability check.

Uses Claude Opus 4.6 as a "rater_2" to independently score the same papers
that human rater_1 has scored, then computes Cohen's kappa.

This provides a defensible IRR proxy when a second human rater is unavailable.
The LLM rater is given the same rubric as the human rater, with no access to
rater_1's scores.

Usage:
  python src/pipeline/llm_rater_2.py --papers paper_01 paper_02 ... paper_10
  python src/pipeline/llm_rater_2.py --auto  # auto-detect papers from rater_1
  python src/pipeline/llm_rater_2.py --kappa # compute kappa after scoring
"""

import argparse
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
RATINGS_DIR = Path("experiments/exp_a/human_ratings")
RATER_2_ID = "llm_rater_2_opus"
RATER_2_MODEL = "claude-opus-4-6"

RUBRIC_PROMPT = """You are an expert empirical economist serving as an independent rater for a benchmark study. You will score one LLM output against the published paper's ground truth using a strict 3-dimensional rubric.

**Dimension 1: ID Strategy Match (0-3)**
- 3: Exact match — model correctly names the paper's identification method (DID / Event Study / IV / RDD / etc.)
- 2: Same broad family — correct method but missing key features, OR hybrid framing that includes the correct method
- 1: Related logic — wrong method name but conceptually similar
- 0: Wrong method or no clear identification strategy

**Dimension 2: Direction Match (0 / 0.5 / 1)**
- 1: Correct direction, clearly stated
- 0.5: Correct direction but hedged/insignificant
- 0: Wrong direction or contradicts ground truth

**Dimension 3: Failure type (one of: IH / ME / NF / none)**
- IH = Identification Hallucination (wrong/invalid strategy)
- ME = Mechanical Execution (right strategy, wrong implementation)
- NF = Narrative Fabrication (plausibly wrong context/direction)
- none = no failure

Be strict. If unsure between two scores, choose the lower one.

Output ONLY a JSON object in this exact format:
{
  "id_strategy_score": <int 0/1/2/3>,
  "direction_score": <float 0/0.5/1>,
  "failure_types": ["IH"|"ME"|"NF"|"none"...],
  "rationale": "<one sentence explanation>"
}"""


def score_with_opus(paper: dict, llm_output: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    gt = paper["ground_truth"]
    content = llm_output["llm_response"]["content"][:4500]  # truncate for cost

    user_msg = f"""**Paper**: {paper.get('title', paper['paper_id'])}
**Ground-truth identification strategy**: {gt['identification_strategy']}
**Ground-truth direction**: {gt['conclusion_direction']}
**Ground-truth detail**: {gt.get('conclusion_detail', '')}

---

**Model output to score** (first 4500 chars):

{content}

---

Score this output using the rubric. Output ONLY the JSON object."""

    msg = client.messages.create(
        model=RATER_2_MODEL,
        max_tokens=500,
        system=RUBRIC_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = msg.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object in the text
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if m:
            result = json.loads(m.group(0))
        else:
            raise ValueError(f"Could not parse JSON from: {text[:200]}")

    # Normalize failure_types
    ft = result.get("failure_types", [])
    if isinstance(ft, str):
        ft = [ft]
    ft = [f.strip().upper() for f in ft if f]
    if not ft or ft == ["NONE"]:
        ft = []
    result["failure_types"] = ft

    return result


def rate_paper(paper_id: str, model: str, force: bool = False) -> dict:
    paper_files = list(PAPERS_DIR.glob(f"{paper_id}_*.json"))
    if not paper_files:
        print(f"  [SKIP] {paper_id}: paper file not found")
        return None
    paper = json.load(open(paper_files[0]))

    out_file = OUTPUTS_DIR / f"{paper_id}_{model}.json"
    if not out_file.exists():
        print(f"  [SKIP] {paper_id}: no LLM output for {model}")
        return None
    llm_output = json.load(open(out_file))

    rating_file = RATINGS_DIR / f"{paper_id}_{RATER_2_ID}_{model}.json"
    if rating_file.exists() and not force:
        print(f"  [SKIP] {paper_id}: already rated by {RATER_2_ID}")
        return json.load(open(rating_file))

    print(f"  [RATE] {paper_id} | {model}")
    try:
        scores = score_with_opus(paper, llm_output)
    except Exception as e:
        print(f"    [ERR] {e}")
        return None

    rating = {
        "paper_id": paper_id,
        "rater_id": RATER_2_ID,
        "model": model,
        "method_family": paper["method_family"],
        "difficulty": paper["difficulty"],
        "id_strategy_score": scores["id_strategy_score"],
        "direction_score": scores["direction_score"],
        "failure_types": scores["failure_types"],
        "l3_pass": scores["id_strategy_score"] >= 2,
        "notes": scores.get("rationale", ""),
    }
    rating_file.write_text(json.dumps(rating, indent=2, ensure_ascii=False))
    print(f"    L3={scores['id_strategy_score']} L4={scores['direction_score']} "
          f"failures={scores['failure_types']}")
    return rating


def auto_detect_rater1_papers() -> list[tuple[str, str]]:
    """Find all (paper_id, model) pairs that rater_1 has scored."""
    pairs = []
    for f in sorted(RATINGS_DIR.glob("*_rater_1_*.json")):
        d = json.load(open(f))
        pairs.append((d["paper_id"], d["model"]))
    return pairs


def compute_kappa():
    """Compute Cohen's kappa between rater_1 and llm_rater_2 on shared items."""
    pairs_r1 = {(p, m): None for p, m in auto_detect_rater1_papers()}

    for f in RATINGS_DIR.glob("*_rater_1_*.json"):
        d = json.load(open(f))
        pairs_r1[(d["paper_id"], d["model"])] = d

    pairs_r2 = {}
    for f in RATINGS_DIR.glob(f"*_{RATER_2_ID}_*.json"):
        d = json.load(open(f))
        pairs_r2[(d["paper_id"], d["model"])] = d

    common = sorted(set(pairs_r1.keys()) & set(pairs_r2.keys()))
    if len(common) < 2:
        print(f"Not enough co-rated items ({len(common)}). Need at least 2.")
        return

    # L3 (binary l3_pass)
    a_l3 = [int(pairs_r1[k]["l3_pass"]) for k in common]
    b_l3 = [int(pairs_r2[k]["l3_pass"]) for k in common]

    # L4 (binary: direction_score >= 0.5)
    a_l4 = [int(pairs_r1[k]["direction_score"] >= 0.5) for k in common]
    b_l4 = [int(pairs_r2[k]["direction_score"] >= 0.5) for k in common]

    # ID strategy score (4-level: 0/1/2/3)
    a_id = [pairs_r1[k]["id_strategy_score"] for k in common]
    b_id = [pairs_r2[k]["id_strategy_score"] for k in common]

    def cohen_kappa(a, b):
        n = len(a)
        agree = sum(ai == bi for ai, bi in zip(a, b))
        p_obs = agree / n
        # Marginal probabilities
        cats = sorted(set(a) | set(b))
        p_exp = sum(
            (a.count(c) / n) * (b.count(c) / n)
            for c in cats
        )
        if p_exp >= 1:
            return 1.0
        return (p_obs - p_exp) / (1 - p_exp)

    kappa_l3 = cohen_kappa(a_l3, b_l3)
    kappa_l4 = cohen_kappa(a_l4, b_l4)
    kappa_id = cohen_kappa(a_id, b_id)

    n = len(common)
    print(f"\n{'='*70}")
    print(f"Cohen's Kappa: rater_1 (human) vs {RATER_2_ID} (Claude Opus)")
    print(f"{'='*70}")
    print(f"N co-rated items: {n}")
    print(f"  L3 pass agreement:        {sum(ai==bi for ai,bi in zip(a_l3,b_l3))}/{n} ({sum(ai==bi for ai,bi in zip(a_l3,b_l3))/n*100:.0f}%)")
    print(f"  L4 pass agreement:        {sum(ai==bi for ai,bi in zip(a_l4,b_l4))}/{n} ({sum(ai==bi for ai,bi in zip(a_l4,b_l4))/n*100:.0f}%)")
    print(f"  ID strategy agreement:    {sum(ai==bi for ai,bi in zip(a_id,b_id))}/{n} ({sum(ai==bi for ai,bi in zip(a_id,b_id))/n*100:.0f}%)")
    print()
    print(f"  Cohen's kappa L3 (binary):    {kappa_l3:.3f}")
    print(f"  Cohen's kappa L4 (binary):    {kappa_l4:.3f}")
    print(f"  Cohen's kappa ID (4-level):   {kappa_id:.3f}")
    print()
    print("  Interpretation (Landis & Koch 1977):")
    print("    < 0.00: Poor")
    print("    0.00-0.20: Slight")
    print("    0.21-0.40: Fair")
    print("    0.41-0.60: Moderate")
    print("    0.61-0.80: Substantial")
    print("    0.81-1.00: Almost perfect")

    # Save report
    report = {
        "rater_a": "rater_1 (human)",
        "rater_b": f"{RATER_2_ID} ({RATER_2_MODEL})",
        "n_common": n,
        "kappa_l3_binary": round(kappa_l3, 4),
        "kappa_l4_binary": round(kappa_l4, 4),
        "kappa_id_4level": round(kappa_id, 4),
        "agreement_l3": sum(ai==bi for ai,bi in zip(a_l3,b_l3)) / n,
        "agreement_l4": sum(ai==bi for ai,bi in zip(a_l4,b_l4)) / n,
        "agreement_id": sum(ai==bi for ai,bi in zip(a_id,b_id)) / n,
        "items": [
            {
                "paper_id": p, "model": m,
                "rater_1_id": pairs_r1[(p,m)]["id_strategy_score"],
                "rater_2_id": pairs_r2[(p,m)]["id_strategy_score"],
                "rater_1_l3_pass": pairs_r1[(p,m)]["l3_pass"],
                "rater_2_l3_pass": pairs_r2[(p,m)]["l3_pass"],
                "rater_1_dir": pairs_r1[(p,m)]["direction_score"],
                "rater_2_dir": pairs_r2[(p,m)]["direction_score"],
            }
            for p, m in common
        ],
    }
    out_file = RATINGS_DIR / "kappa_rater1_vs_llm_rater2.json"
    out_file.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved: {out_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true",
                        help="Auto-detect papers from rater_1 ratings")
    parser.add_argument("--papers", nargs="+", default=[],
                        help="Specific paper IDs to rate")
    parser.add_argument("--model", default="moonshot-v1-128k",
                        help="Which LLM output to score")
    parser.add_argument("--kappa", action="store_true",
                        help="Compute kappa after rating")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.auto:
        targets = auto_detect_rater1_papers()
        print(f"Auto-detected {len(targets)} (paper, model) pairs from rater_1")
    elif args.papers:
        targets = [(p, args.model) for p in args.papers]
    else:
        targets = []

    for paper_id, model in targets:
        rate_paper(paper_id, model, force=args.force)
        time.sleep(0.5)

    if args.kappa or args.auto:
        compute_kappa()


if __name__ == "__main__":
    main()
