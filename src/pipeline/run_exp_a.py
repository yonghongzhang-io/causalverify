"""
Experiment A Pipeline — AI Replication Runner
==============================================
For each paper in experiments/exp_a/papers/, this pipeline:
  1. Loads the paper JSON (research_question + data_description + institutional_context)
  2. Sends a structured prompt to Claude (or GPT-4o / Gemini)
  3. Saves the raw LLM output
  4. Extracts the proposed identification strategy and R code stub
  5. Prepares the output for human rater scoring

Requirements:
  - ANTHROPIC_API_KEY in .env
  - pip install anthropic

Usage:
  python src/pipeline/run_exp_a.py --paper paper_01 --model claude-opus-4-20250514
  python src/pipeline/run_exp_a.py --all --model claude-opus-4-20250514
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PAPERS_DIR  = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/exp_a/outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Prompt template ───────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a financial economist with expertise in empirical methods including
difference-in-differences, event studies, instrumental variables, and regression
discontinuity designs. You are helping conduct original empirical research.

Your task: Given a research question, available data, and institutional context,
propose a rigorous identification strategy and outline the empirical methodology.

IMPORTANT: Do NOT read ahead or guess the actual paper's methodology. Work only
from the information provided. Propose what YOU would do given this setup.
"""

USER_PROMPT_TEMPLATE = """\
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
State clearly which causal identification strategy you would use (DID, event study,
IV, RDD, or other). Justify why this strategy is appropriate for this research
question and data.

## 2. Treatment and Control
Define precisely:
- Treatment variable (what constitutes "treated")
- Control group (what serves as counterfactual)
- Treatment timing / event date (if applicable)
- Running variable and cutoff (if RDD)

## 3. Key Identifying Assumptions
List the main assumptions required for your strategy to yield causal estimates.
For each assumption, discuss whether it is plausible given the institutional context.

## 4. Threats to Identification
Identify the 2–3 most important threats to your identification strategy.
How would you address each threat?

## 5. R Code Outline
Write executable R code for the main specification. Include:
- Data loading steps (assume data is in CSV format)
- Variable construction
- Main regression using appropriate package (fixest, rdrobust, ivreg, etc.)
- At least one robustness check

## 6. Expected Results
State your prior expectation for the direction of the main effect and its
approximate magnitude (if you can form a prior from economic theory).

## 7. Validity Checklist Self-Assessment
Rate yourself on the 5-item validity checklist for your chosen method
(1 = clearly satisfied, 0 = questionable or absent):
- C1: [checklist item 1]
- C2: [checklist item 2]
- C3: [checklist item 3]
- C4: [checklist item 4]
- C5: [checklist item 5]
"""

# ── LLM caller ────────────────────────────────────────────────────────

def call_anthropic(paper: dict, model: str) -> dict:
    try:
        import anthropic
    except ImportError:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_msg = USER_PROMPT_TEMPLATE.format(
        research_question=paper["research_question"],
        data_description=paper["data_description"],
        institutional_context=paper["institutional_context"],
    )

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    return {
        "model": model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "content": message.content[0].text,
        "stop_reason": message.stop_reason,
    }


def call_openai(paper: dict, model: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("pip install openai")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    user_msg = USER_PROMPT_TEMPLATE.format(
        research_question=paper["research_question"],
        data_description=paper["data_description"],
        institutional_context=paper["institutional_context"],
    )

    # Reasoning / GPT-5 family uses max_completion_tokens and needs more budget
    is_reasoning = (model.startswith("o3") or model.startswith("o1")
                    or model.startswith("o4") or model.startswith("gpt-5"))
    token_kwarg = "max_completion_tokens" if is_reasoning else "max_tokens"
    max_out = 16384 if is_reasoning else 4096
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
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


def call_kimi(paper: dict, model: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("pip install openai")

    client = OpenAI(
        api_key=os.getenv("KIMI_API_KEY"),
        base_url="https://api.moonshot.cn/v1",
    )
    user_msg = USER_PROMPT_TEMPLATE.format(
        research_question=paper["research_question"],
        data_description=paper["data_description"],
        institutional_context=paper["institutional_context"],
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=4096,
    )

    return {
        "model": model,
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "content": resp.choices[0].message.content,
        "stop_reason": resp.choices[0].finish_reason,
    }


def call_llm(paper: dict, model: str) -> dict:
    if "claude" in model.lower():
        return call_anthropic(paper, model)
    elif "gpt" in model.lower() or "o1" in model.lower() or model.startswith("o3"):
        return call_openai(paper, model)
    elif "moonshot" in model.lower():
        return call_kimi(paper, model)
    elif "gemini" in model.lower():
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("GOOGLE_API_KEY"),
                        base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        user_msg = USER_PROMPT_TEMPLATE.format(
            research_question=paper["research_question"],
            data_description=paper["data_description"],
            institutional_context=paper["institutional_context"],
        )
        resp = client.chat.completions.create(
            model=model, max_tokens=16384,  # thinking models need headroom
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user_msg}],
        )
        return {"model": model,
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
                "content": resp.choices[0].message.content,
                "stop_reason": resp.choices[0].finish_reason}
    else:
        raise ValueError(f"Unknown model provider for: {model}. "
                         "Supported prefixes: claude, gpt, o3, moonshot, gemini")


# ── Main runner ───────────────────────────────────────────────────────

def run_paper(paper_file: Path, model: str, force: bool = False) -> dict:
    with open(paper_file, encoding="utf-8") as f:
        paper = json.load(f)

    paper_id = paper["paper_id"]
    model_slug = model.replace("/", "-").replace(":", "-")
    out_file = OUTPUTS_DIR / f"{paper_id}_{model_slug}.json"

    if out_file.exists() and not force:
        print(f"  [SKIP] {paper_id} — output exists. Use --force to rerun.")
        return json.loads(out_file.read_text())

    print(f"  [RUN ] {paper_id} | {paper['method_family']} | {paper['difficulty']}")
    print(f"         model={model}")

    try:
        llm_response = call_llm(paper, model)
    except Exception as e:
        print(f"  [ERR ] {paper_id}: {e}")
        return {"error": str(e), "paper_id": paper_id}

    content = llm_response.get("content")
    if not isinstance(content, str) or not content.strip():
        err = (f"empty_content: provider returned no usable text "
               f"(output_tokens={llm_response.get('output_tokens')}, "
               f"stop_reason={llm_response.get('stop_reason')})")
        print(f"  [ERR ] {paper_id}: {err}")
        return {"error": err, "paper_id": paper_id, "llm_response": llm_response}

    output = {
        "paper_id": paper_id,
        "source": paper.get("source", ""),
        "method_family": paper.get("method_family", ""),
        "difficulty": paper.get("difficulty", ""),
        "model": model,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "llm_response": llm_response,
        # Ground truth stored separately for blind scoring
        "_ground_truth_path": str(paper_file),
    }

    out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"  [DONE] saved → {out_file}")
    print(f"         tokens: {llm_response.get('input_tokens', '?')} in / "
          f"{llm_response.get('output_tokens', '?')} out")
    return output


def run_all(model: str, force: bool = False, limit: int = None,
            shard: str = None) -> list:
    papers = sorted(PAPERS_DIR.glob("paper_*.json"),
                    key=lambda p: int(p.stem.split("_")[1]))
    if not papers:
        print(f"No paper JSON files found in {PAPERS_DIR}")
        return []

    if shard:
        k, n = (int(x) for x in shard.split("/"))
        papers = [p for i, p in enumerate(papers) if i % n == (k - 1)]
        print(f"  [shard {k}/{n}] taking {len(papers)} papers")

    if limit:
        papers = papers[:limit]

    print(f"\nRunning Experiment A: {len(papers)} papers × model={model}")
    print("=" * 60)

    results = []
    for p in papers:
        result = run_paper(p, model, force=force)
        results.append(result)

    n_ok = sum(1 for r in results if "error" not in r)
    print(f"\nDone: {n_ok}/{len(papers)} succeeded")
    return results


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run Experiment A: AI replication of 10 JF/JFE/RFS papers"
    )
    parser.add_argument("--paper", type=str, default=None,
                        help="Paper ID to run (e.g. paper_01). Omit to run all.")
    parser.add_argument("--all", action="store_true",
                        help="Run all 10 papers")
    parser.add_argument("--model", type=str,
                        default="claude-opus-4-20250514",
                        help="LLM model to use")
    parser.add_argument("--force", action="store_true",
                        help="Re-run even if output already exists")
    parser.add_argument("--list", action="store_true",
                        help="List available papers and exit")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only run the first N papers (sorted by paper_id)")
    parser.add_argument("--shard", type=str, default=None,
                        help="Shard selector k/N (1-indexed); e.g. 1/4 takes every 4th paper starting from index 0")

    args = parser.parse_args()

    if args.list:
        papers = sorted(PAPERS_DIR.glob("paper_*.json"))
        for p in papers:
            d = json.loads(p.read_text())
            print(f"  {d['paper_id']:12} {d['method_family']:15} {d['difficulty']:8} "
                  f"{d.get('authors','')}")
        return

    if args.all or args.paper is None:
        run_all(args.model, force=args.force, limit=args.limit,
                shard=args.shard)
    else:
        matches = list(PAPERS_DIR.glob(f"{args.paper}*.json"))
        if not matches:
            print(f"Paper not found: {args.paper}")
            sys.exit(1)
        run_paper(matches[0], args.model, force=args.force)


if __name__ == "__main__":
    main()
