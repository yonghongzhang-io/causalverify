"""
Generate paper JSON metadata for new benchmark papers using GPT-4o.

Usage:
  python src/pipeline/generate_paper_jsons.py --csv experiments/exp_a/benchmark_125_candidates.csv --start 58 --end 137
  python src/pipeline/generate_paper_jsons.py --csv experiments/exp_a/benchmark_125_candidates.csv --start 58 --end 70  # test batch
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

PAPERS_DIR = Path("experiments/exp_a/papers")
PAPERS_DIR.mkdir(parents=True, exist_ok=True)

METHOD_MAP = {
    "DID": "DID",
    "ES": "EVENT_STUDY",
    "IV": "IV",
    "RDD": "RDD",
}

DIFFICULTY_SUFFIX = {
    "DID": {"easy": "did_easy", "medium": "did_medium", "hard": "did_hard"},
    "EVENT_STUDY": {"easy": "event_easy", "medium": "event_medium", "hard": "event_hard"},
    "IV": {"easy": "iv_easy", "medium": "iv_medium", "hard": "iv_hard"},
    "RDD": {"easy": "rdd_easy", "medium": "rdd_medium", "hard": "rdd_hard"},
}

SYSTEM_PROMPT = """You are an expert empirical economist. Given a published paper's metadata, generate a JSON object with the following fields. Be precise and factual — these will be used as ground truth for an LLM benchmark.

Output ONLY valid JSON, no markdown fences, no explanation.

Required JSON structure:
{
  "research_question": "The paper's core causal research question, written as a prompt for an LLM (2-3 sentences). Do NOT reveal the identification strategy or results.",
  "data_description": "Description of the data used in the paper (sources, frequency, key variables, sample period, unit of observation). Be specific enough that an LLM could identify the appropriate method. ~150 words.",
  "institutional_context": "The institutional setting and background that makes the identification strategy work (natural experiment, policy change, threshold, etc.). Do NOT name the method. ~150 words.",
  "ground_truth": {
    "identification_strategy": "One-line description: METHOD — treatment = X, control = Y; shock/instrument/cutoff = Z",
    "key_variables": {
      "treatment": "description of treatment variable",
      "control": "description of control group",
      "outcome": "main outcome variable(s)",
      "time_period": "sample period"
    },
    "conclusion_direction": "positive or negative",
    "conclusion_detail": "One sentence describing the main finding with direction",
    "main_effect": "Key magnitude (e.g. '~15% increase', 'β = -0.23')",
    "key_robustness": ["robustness check 1", "robustness check 2", "robustness check 3"]
  }
}

CRITICAL:
- research_question and data_description must NOT mention the method name (DID, event study, IV, RDD)
- institutional_context should describe the setting that enables causal identification WITHOUT naming the method
- conclusion_direction must be exactly "positive" or "negative"
- Be factually accurate about the paper's actual findings"""


def generate_paper_json(row, paper_num):
    """Call GPT-4o to generate paper JSON metadata."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    method_full = METHOD_MAP[row["method"]]
    user_msg = f"""Generate the JSON metadata for this paper:

Title: {row['title']}
Authors: {row['authors']}
Year: {row['year']}
Journal: {row['journal']}
Domain: {row['domain']}
Identification method: {row['method']} ({method_full})
Difficulty: {row['difficulty']}
Main finding direction: {row['direction']}

Remember: research_question and data_description must NOT reveal the method. institutional_context should describe the setting without naming the method."""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2000,
        temperature=0.3,
    )

    content = resp.choices[0].message.content.strip()
    # Strip markdown fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]

    generated = json.loads(content)

    # Build full paper JSON
    paper_id = f"paper_{paper_num:02d}"
    suffix = DIFFICULTY_SUFFIX[method_full][row["difficulty"]]
    filename = f"{paper_id}_{suffix}.json"

    paper = {
        "paper_id": paper_id,
        "source": f"{row['journal']}, {row['year']}",
        "authors": row["authors"],
        "method_family": method_full,
        "difficulty": row["difficulty"],
        "domain": row["domain"],
        "title": row["title"],
        "research_question": generated["research_question"],
        "data_description": generated["data_description"],
        "institutional_context": generated["institutional_context"],
        "ground_truth": generated["ground_truth"],
    }

    out_path = PAPERS_DIR / filename
    out_path.write_text(json.dumps(paper, indent=2, ensure_ascii=False))
    return filename, paper_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to candidates CSV")
    parser.add_argument("--start", type=int, default=58, help="Starting paper number")
    parser.add_argument("--end", type=int, default=137, help="Ending paper number (inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    args = parser.parse_args()

    with open(args.csv) as f:
        rows = list(csv.DictReader(f))

    n_to_generate = args.end - args.start + 1
    if n_to_generate > len(rows):
        print(f"Warning: only {len(rows)} rows in CSV, but requested {n_to_generate}")
        n_to_generate = len(rows)

    print(f"Generating paper JSONs: paper_{args.start:02d} to paper_{args.end:02d}")
    print(f"Papers to generate: {n_to_generate}")
    print("=" * 60)

    if args.dry_run:
        for i, row in enumerate(rows[:n_to_generate]):
            num = args.start + i
            method_full = METHOD_MAP[row["method"]]
            suffix = DIFFICULTY_SUFFIX[method_full][row["difficulty"]]
            print(f"  paper_{num:02d}_{suffix}.json | {row['authors']} ({row['year']}) | {row['domain']}/{row['method']}/{row['difficulty']}")
        return

    success = 0
    for i, row in enumerate(rows[:n_to_generate]):
        num = args.start + i
        method_full = METHOD_MAP[row["method"]]
        suffix = DIFFICULTY_SUFFIX[method_full][row["difficulty"]]
        existing = PAPERS_DIR / f"paper_{num:02d}_{suffix}.json"

        if existing.exists():
            print(f"  [SKIP] paper_{num:02d} — already exists")
            success += 1
            continue

        try:
            print(f"  [GEN ] paper_{num:02d} | {row['authors']} ({row['year']}) | {row['domain']}/{row['method']}/{row['difficulty']}")
            fname, pid = generate_paper_json(row, num)
            print(f"  [DONE] {fname}")
            success += 1
        except Exception as e:
            print(f"  [ERR ] paper_{num:02d}: {e}")

    print(f"\nDone: {success}/{n_to_generate} generated")


if __name__ == "__main__":
    main()
