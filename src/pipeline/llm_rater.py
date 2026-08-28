"""
LLM-as-Rater — Automated scoring of Experiment A outputs
=========================================================
Uses 3 LLMs (GPT-4o, Claude, Gemini) as independent raters
to score L3 (strategy) and L4 (direction) for all Exp A outputs.
Computes Fleiss' κ for inter-rater reliability.

Usage:
  python src/pipeline/llm_rater.py --run       # Score all outputs with 3 LLM raters
  python src/pipeline/llm_rater.py --kappa     # Compute Fleiss' κ from existing scores
  python src/pipeline/llm_rater.py --compare   # Compare LLM raters to human rater_1
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

PAPERS_DIR  = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/exp_a/outputs")
RATINGS_DIR = Path("experiments/exp_a/llm_ratings")
RATINGS_DIR.mkdir(parents=True, exist_ok=True)

# Models to use as raters (different from the models being evaluated)
RATER_MODELS = {
    "rater_gpt4o":  {"provider": "openai",  "model": "gpt-4o"},
    "rater_claude": {"provider": "anthropic","model": "claude-sonnet-4-20250514"},
    "rater_gemini": {"provider": "gemini",   "model": "gemini-2.5-flash"},
}

SCORING_PROMPT = """\
You are an expert econometrician scoring an AI model's output for a causal inference benchmark.

## Ground Truth
- **Paper:** {paper_title} ({paper_authors}, {paper_source})
- **Ground truth identification strategy:** {gt_strategy}
- **Ground truth conclusion direction:** {gt_direction}
- **Ground truth main effect:** {gt_effect}

## AI Model Output (first 2000 characters)
{model_output}

## Scoring Instructions

Score the AI output on two dimensions:

### 1. Strategy Match (0-3)
- 3 = Strong match: correct method family and key features
- 2 = Mostly right: correct broad family, or hybrid framing that includes the correct method
- 1 = Partially related: wrong method but some conceptual overlap
- 0 = Wrong: completely different method family

### 2. Direction Match (0, 0.5, or 1)
- 1 = Correct direction, clearly stated
- 0.5 = Correct direction but hedged/ambiguous
- 0 = Wrong direction or not stated

### 3. Failure Types (list, or empty if no failure)
- IH = Identification Hallucination (wrong strategy)
- ME = Mechanical Execution (right strategy, wrong implementation)
- NF = Narrative Fabrication (wrong direction)

## Response Format
Respond with ONLY a JSON object, no other text:
{{"strategy_score": <0-3>, "direction_score": <0|0.5|1>, "failure_types": [<list>], "reasoning": "<brief explanation>"}}
"""


def call_rater(rater_id: str, prompt: str) -> dict:
    """Call a rater LLM and parse its JSON response."""
    config = RATER_MODELS[rater_id]

    if config["provider"] == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model=config["model"], max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    elif config["provider"] == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=config["model"], max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])

    elif config["provider"] == "gemini":
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("GOOGLE_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        resp = client.chat.completions.create(
            model=config["model"], max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])


def score_output(paper: dict, output: dict, rater_id: str) -> dict:
    """Score a single model output using a rater LLM."""
    gt = paper.get("ground_truth", {})
    prompt = SCORING_PROMPT.format(
        paper_title=paper.get("title", ""),
        paper_authors=paper.get("authors", ""),
        paper_source=paper.get("source", ""),
        gt_strategy=gt.get("identification_strategy", ""),
        gt_direction=gt.get("conclusion_direction", ""),
        gt_effect=gt.get("main_effect", ""),
        model_output=output["llm_response"]["content"][:2000],
    )

    try:
        result = call_rater(rater_id, prompt)
        result["rater_id"] = rater_id
        result["paper_id"] = paper["paper_id"]
        result["scored_model"] = output.get("model", "")
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception as e:
        return {
            "rater_id": rater_id,
            "paper_id": paper["paper_id"],
            "scored_model": output.get("model", ""),
            "error": str(e),
        }


def run_all_ratings():
    """Score all Exp A outputs with all 3 LLM raters."""
    papers = {}
    for pf in sorted(PAPERS_DIR.glob("paper_*.json")):
        d = json.load(open(pf))
        papers[d["paper_id"]] = d

    # Find all outputs for papers that have ground truth
    outputs = sorted(OUTPUTS_DIR.glob("paper_*.json"))

    total = 0
    for rater_id in RATER_MODELS:
        print(f"\n{'='*60}")
        print(f"Rater: {rater_id}")
        print(f"{'='*60}")

        for out_file in outputs:
            out = json.load(open(out_file))
            pid = out.get("paper_id", "")
            if pid not in papers:
                continue

            scored_model = out.get("model", "unknown")
            rating_file = RATINGS_DIR / f"{pid}_{scored_model}_{rater_id}.json"

            if rating_file.exists():
                print(f"  [SKIP] {pid} × {scored_model} — already scored")
                continue

            paper = papers[pid]
            print(f"  [SCORE] {pid} × {scored_model} ...", end=" ", flush=True)

            result = score_output(paper, out, rater_id)

            rating_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            s = result.get("strategy_score", "?")
            d = result.get("direction_score", "?")
            print(f"L3={s} L4={d}")
            total += 1

    print(f"\nDone: {total} ratings saved to {RATINGS_DIR}")


def compute_kappa():
    """Compute Fleiss' κ from LLM rater scores."""
    from collections import defaultdict
    import numpy as np

    rating_files = sorted(RATINGS_DIR.glob("*.json"))
    if not rating_files:
        print(f"No rating files found in {RATINGS_DIR}")
        return

    # Group ratings by (paper_id, scored_model)
    grouped = defaultdict(dict)
    for rf in rating_files:
        r = json.load(open(rf))
        if "error" in r:
            continue
        key = (r["paper_id"], r["scored_model"])
        grouped[key][r["rater_id"]] = r

    # Build L3 binary matrix (pass = strategy_score >= 2)
    rater_ids = sorted(RATER_MODELS.keys())
    items = []
    l3_matrix = []  # N items × K raters
    l4_matrix = []

    for key in sorted(grouped.keys()):
        ratings = grouped[key]
        if len(ratings) < 2:
            continue
        items.append(key)
        l3_row = []
        l4_row = []
        for rid in rater_ids:
            if rid in ratings:
                l3_row.append(1 if ratings[rid].get("strategy_score", 0) >= 2 else 0)
                l4_row.append(1 if ratings[rid].get("direction_score", 0) >= 0.75 else 0)
            else:
                l3_row.append(None)
                l4_row.append(None)
        l3_matrix.append(l3_row)
        l4_matrix.append(l4_row)

    def fleiss_kappa(matrix):
        """Compute Fleiss' kappa for a binary rating matrix."""
        mat = np.array(matrix, dtype=float)
        # Remove items with missing raters
        valid = ~np.isnan(mat).any(axis=1)
        mat = mat[valid]
        N = mat.shape[0]
        k = mat.shape[1]
        if N == 0:
            return float("nan")

        # Count agreements
        p_pos = mat.mean(axis=1)  # fraction of raters saying 1 per item
        p_neg = 1 - p_pos

        # Per-item agreement
        P_i = (p_pos**2 + p_neg**2) * k / (k - 1) - 1 / (k - 1)
        P_bar = P_i.mean()

        # Expected agreement
        p_e_pos = mat.mean()
        p_e_neg = 1 - p_e_pos
        P_e = p_e_pos**2 + p_e_neg**2

        if P_e == 1:
            return 1.0
        return (P_bar - P_e) / (1 - P_e)

    kappa_l3 = fleiss_kappa(l3_matrix)
    kappa_l4 = fleiss_kappa(l4_matrix)

    print(f"\n{'='*50}")
    print(f"Fleiss' κ — LLM-as-Rater Inter-Rater Reliability")
    print(f"{'='*50}")
    print(f"  Items scored by ≥2 raters: {len(items)}")
    print(f"  Raters: {rater_ids}")
    print(f"  L3 (strategy, binary ≥2): κ = {kappa_l3:.3f}"
          f"  {'✓ TARGET MET' if kappa_l3 >= 0.70 else '✗ BELOW TARGET'}")
    print(f"  L4 (direction, binary ≥0.75): κ = {kappa_l4:.3f}"
          f"  {'✓ TARGET MET' if kappa_l4 >= 0.70 else '✗ BELOW TARGET'}")

    report = {
        "n_items": len(items),
        "raters": rater_ids,
        "kappa_l3": round(kappa_l3, 4),
        "kappa_l4": round(kappa_l4, 4),
        "target": 0.70,
        "l3_achieved": bool(kappa_l3 >= 0.70),
        "l4_achieved": bool(kappa_l4 >= 0.70),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out = RATINGS_DIR / "fleiss_kappa_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nSaved to {out}")
    return report


def compare_to_human():
    """Compare LLM rater scores to human rater_1 scores."""
    human_dir = Path("experiments/exp_a/human_ratings")
    if not human_dir.exists():
        human_dir = Path("experiments/exp_a/ratings")

    human_files = sorted(human_dir.glob("*rater_1*.json"))
    if not human_files:
        print("No human rater_1 files found")
        return

    print(f"\nComparing LLM raters to human rater_1 ({len(human_files)} papers)")
    print("-" * 60)

    for hf in human_files:
        h = json.load(open(hf))
        pid = h.get("paper_id", hf.stem.split("_rater")[0])
        h_l3 = h.get("id_strategy_score", h.get("strategy_score", "?"))
        h_l4 = h.get("conclusion_score", h.get("direction_score", "?"))

        print(f"\n{pid}: human L3={h_l3} L4={h_l4}")
        llm_files = sorted(RATINGS_DIR.glob(f"{pid}_*_rater_*.json"))
        for lf in llm_files:
            r = json.load(open(lf))
            if "error" in r:
                continue
            print(f"  {r['rater_id']}: L3={r.get('strategy_score','?')} "
                  f"L4={r.get('direction_score','?')}")


def main():
    parser = argparse.ArgumentParser(description="LLM-as-Rater scoring pipeline")
    parser.add_argument("--run", action="store_true", help="Score all outputs with 3 LLM raters")
    parser.add_argument("--kappa", action="store_true", help="Compute Fleiss' κ")
    parser.add_argument("--compare", action="store_true", help="Compare to human rater_1")
    args = parser.parse_args()

    if args.run:
        run_all_ratings()
    elif args.kappa:
        compute_kappa()
    elif args.compare:
        compare_to_human()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
