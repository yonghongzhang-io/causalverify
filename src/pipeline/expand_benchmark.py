"""
Expand CausalVerify Exp A corpus from 137 to 300 papers.

Step 1: Generate candidate CSV via GPT-4o
Step 2: Validate against OpenAlex
Step 3: Generate paper JSONs (reuse generate_paper_jsons.py)

Usage:
  # Step 1: Generate candidate list
  python src/pipeline/expand_benchmark.py --step suggest --target 163

  # Step 2: Validate candidates with OpenAlex
  python src/pipeline/expand_benchmark.py --step validate

  # Step 3: Generate paper JSONs
  python src/pipeline/expand_benchmark.py --step generate

  # Or run all steps:
  python src/pipeline/expand_benchmark.py --step all --target 163
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

CSV_OUT = Path("experiments/exp_a/benchmark_300_candidates.csv")
VALIDATED_CSV = Path("experiments/exp_a/benchmark_300_validated.csv")
PAPERS_DIR = Path("experiments/exp_a/papers")
EXISTING_CSV = Path("experiments/exp_a/benchmark_125_candidates.csv")

# Current counts (137 papers total)
CURRENT = {"DID": 41, "EVENT_STUDY": 29, "IV": 34, "RDD": 33}
TARGET_TOTAL = 300
TARGET_PER_METHOD = 75  # 300 / 4

# Domain allocation for new papers (163 total)
# Expand existing domains + add 2 new ones
DOMAIN_METHOD_NEEDS = {
    # (domain, method_abbrev): count_needed
    # Finance
    ("finance", "DID"): 3, ("finance", "ES"): 5, ("finance", "IV"): 4, ("finance", "RDD"): 3,
    # Labor
    ("labor", "DID"): 3, ("labor", "ES"): 5, ("labor", "IV"): 4, ("labor", "RDD"): 3,
    # Development
    ("development", "DID"): 3, ("development", "ES"): 4, ("development", "IV"): 3, ("development", "RDD"): 3,
    # Health
    ("health", "DID"): 3, ("health", "ES"): 4, ("health", "IV"): 3, ("health", "RDD"): 3,
    # Education
    ("education", "DID"): 3, ("education", "ES"): 4, ("education", "IV"): 3, ("education", "RDD"): 3,
    # Public / political economy
    ("public", "DID"): 3, ("public", "ES"): 4, ("public", "IV"): 4, ("public", "RDD"): 3,
    # Trade / international
    ("trade", "DID"): 3, ("trade", "ES"): 4, ("trade", "IV"): 3, ("trade", "RDD"): 3,
    # Environment (NEW domain)
    ("environment", "DID"): 4, ("environment", "ES"): 4, ("environment", "IV"): 4, ("environment", "RDD"): 4,
    # Urban / housing (NEW domain)
    ("urban", "DID"): 3, ("urban", "ES"): 4, ("urban", "IV"): 4, ("urban", "RDD"): 4,
    # Agriculture / resource (NEW domain)
    ("agriculture", "DID"): 3, ("agriculture", "ES"): 4, ("agriculture", "IV"): 4, ("agriculture", "RDD"): 4,
}

# Difficulty cycle for balanced assignment
DIFFICULTIES = ["easy", "medium", "hard"]


def load_existing_titles():
    """Collect titles of all existing papers to avoid duplicates."""
    titles = set()
    for f in PAPERS_DIR.glob("paper_*.json"):
        try:
            d = json.loads(f.read_text())
            titles.add(d.get("title", "").lower().strip())
        except Exception:
            pass
    # Also from existing CSV
    if EXISTING_CSV.exists():
        with open(EXISTING_CSV) as f:
            for row in csv.DictReader(f):
                titles.add(row.get("title", "").lower().strip())
    return titles


def suggest_papers_gpt4o(domain: str, method: str, count: int,
                          existing_titles: set) -> list[dict]:
    """Ask GPT-4o to suggest real published papers for a domain × method cell."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    method_names = {
        "DID": "Difference-in-Differences (DID)",
        "ES": "Event Study",
        "IV": "Instrumental Variables (IV / 2SLS)",
        "RDD": "Regression Discontinuity Design (RDD)",
    }
    domain_desc = {
        "finance": "corporate finance, asset pricing, banking, financial markets",
        "labor": "labor economics, employment, wages, immigration",
        "development": "development economics, growth, poverty, institutions",
        "health": "health economics, healthcare policy, epidemiology",
        "education": "education economics, school policy, returns to education",
        "public": "public economics, taxation, public goods, political economy",
        "trade": "international trade, trade policy, globalization",
        "environment": "environmental economics, climate policy, pollution regulation, energy",
        "urban": "urban economics, housing markets, transportation, land use, real estate",
        "agriculture": "agricultural economics, food policy, natural resources, water",
    }

    prompt = f"""List exactly {count + 3} real, well-known published empirical economics papers that use **{method_names[method]}** as their primary identification strategy, in the domain of **{domain_desc[domain]}**.

Requirements:
- Papers must be REAL and published in peer-reviewed journals (top-5 econ journals, field journals, or equivalent)
- Published between 1990 and 2024
- Must have clear causal identification using {method_names[method]}
- Must have a clear positive or negative main finding direction
- Include a mix of difficulty levels (some classic/easy, some technically demanding/hard)

For each paper, provide EXACTLY this JSON array format:
[
  {{
    "authors": "LastName1 & LastName2",
    "year": 2005,
    "journal": "AER",
    "title": "Full Paper Title Here",
    "direction": "positive",
    "difficulty": "easy"
  }}
]

Use standard journal abbreviations: AER, QJE, JPE, Econometrica, REStat, JF, JFE, RFS, JPublE, JHR, JOLE, JDE, JUE, JEEM, AEJ:Applied, AEJ:EP, JIE, etc.

Difficulty guidelines:
- easy: classic paper, clean natural experiment, textbook example
- medium: standard application with some identification challenges
- hard: complex identification, multiple endogeneity concerns, technical subtlety

CRITICAL: Only suggest papers you are CONFIDENT actually exist with the correct identification method. Do NOT fabricate papers.

Output ONLY the JSON array, nothing else."""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert empirical economist who knows the published literature thoroughly. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
        temperature=0.4,
    )

    content = resp.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3].strip()

    papers = json.loads(content)

    # Filter out duplicates
    results = []
    for p in papers:
        title_lower = p["title"].lower().strip()
        if title_lower in existing_titles:
            print(f"    [DUP] {p['authors']} ({p['year']}) — already in benchmark")
            continue
        existing_titles.add(title_lower)
        results.append(p)
        if len(results) >= count:
            break

    return results


def step_suggest(target: int):
    """Step 1: Generate candidate CSV."""
    existing_titles = load_existing_titles()
    print(f"Loaded {len(existing_titles)} existing titles for dedup")

    all_candidates = []
    total_needed = sum(DOMAIN_METHOD_NEEDS.values())
    print(f"\nTarget: {target} new papers ({total_needed} planned across {len(DOMAIN_METHOD_NEEDS)} cells)")
    print("=" * 70)

    diff_idx = 0  # cycling difficulty assignment
    for (domain, method), count in sorted(DOMAIN_METHOD_NEEDS.items()):
        print(f"\n[{domain}/{method}] Requesting {count} papers...")
        try:
            papers = suggest_papers_gpt4o(domain, method, count, existing_titles)
            for p in papers:
                # Override difficulty with balanced cycling if not assigned well
                all_candidates.append({
                    "domain": domain,
                    "method": method,
                    "difficulty": p.get("difficulty", DIFFICULTIES[diff_idx % 3]),
                    "direction": p["direction"],
                    "authors": p["authors"],
                    "year": p["year"],
                    "journal": p["journal"],
                    "title": p["title"],
                })
                diff_idx += 1
            print(f"    Got {len(papers)} papers")
            time.sleep(0.5)  # rate limit courtesy
        except Exception as e:
            print(f"    [ERROR] {e}")

    # Write CSV
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "method", "difficulty", "direction",
                                                 "authors", "year", "journal", "title"])
        writer.writeheader()
        writer.writerows(all_candidates)

    print(f"\n{'=' * 70}")
    print(f"Wrote {len(all_candidates)} candidates to {CSV_OUT}")

    # Distribution summary
    from collections import Counter
    method_counts = Counter(c["method"] for c in all_candidates)
    domain_counts = Counter(c["domain"] for c in all_candidates)
    diff_counts = Counter(c["difficulty"] for c in all_candidates)
    print(f"\nBy method:     {dict(method_counts)}")
    print(f"By domain:     {dict(domain_counts)}")
    print(f"By difficulty: {dict(diff_counts)}")


def step_validate():
    """Step 2: Validate candidates against OpenAlex."""
    import urllib.request
    import urllib.parse

    if not CSV_OUT.exists():
        print(f"ERROR: {CSV_OUT} not found. Run --step suggest first.")
        return

    with open(CSV_OUT) as f:
        rows = list(csv.DictReader(f))

    print(f"Validating {len(rows)} candidates against OpenAlex...")
    print("=" * 70)

    validated = []
    rejected = []
    email = "benchmark@causalbench.org"  # polite pool

    for i, row in enumerate(rows):
        title = row["title"]
        authors = row["authors"]
        year = row["year"]

        # Search OpenAlex
        query = urllib.parse.quote(title)
        url = f"https://api.openalex.org/works?search={query}&filter=publication_year:{year}&per_page=3&mailto={email}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CausalVerify/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            results = data.get("results", [])
            if not results:
                print(f"  [{i+1:3d}] NOT FOUND: {authors} ({year}) — {title[:50]}")
                row["oa_status"] = "not_found"
                rejected.append(row)
                continue

            # Check title similarity
            best = results[0]
            oa_title = best.get("title", "").lower()
            our_title = title.lower()

            # Token overlap
            our_tokens = set(our_title.split())
            oa_tokens = set(oa_title.split())
            if len(our_tokens) == 0:
                overlap = 0
            else:
                overlap = len(our_tokens & oa_tokens) / len(our_tokens)

            if overlap >= 0.5:
                print(f"  [{i+1:3d}] VALID ({overlap:.0%}): {authors} ({year})")
                row["oa_status"] = "validated"
                row["oa_doi"] = best.get("doi", "")
                row["oa_cited_by"] = best.get("cited_by_count", 0)
                validated.append(row)
            else:
                print(f"  [{i+1:3d}] MISMATCH ({overlap:.0%}): {authors} ({year}) — OA: {oa_title[:60]}")
                row["oa_status"] = "mismatch"
                rejected.append(row)

            time.sleep(0.15)  # rate limit

        except Exception as e:
            print(f"  [{i+1:3d}] ERROR: {authors} ({year}) — {e}")
            row["oa_status"] = "error"
            rejected.append(row)

    # Write validated CSV
    fieldnames = ["domain", "method", "difficulty", "direction", "authors", "year",
                  "journal", "title", "oa_status", "oa_doi", "oa_cited_by"]
    with open(VALIDATED_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(validated)

    print(f"\n{'=' * 70}")
    print(f"Validated: {len(validated)} / {len(rows)}")
    print(f"Rejected:  {len(rejected)} (not found: {sum(1 for r in rejected if r.get('oa_status')=='not_found')}, "
          f"mismatch: {sum(1 for r in rejected if r.get('oa_status')=='mismatch')}, "
          f"error: {sum(1 for r in rejected if r.get('oa_status')=='error')})")
    print(f"Validated CSV: {VALIDATED_CSV}")

    if rejected:
        rej_path = Path("experiments/exp_a/benchmark_300_rejected.csv")
        with open(rej_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["domain", "method", "difficulty", "direction",
                                                     "authors", "year", "journal", "title", "oa_status"])
            writer.writeheader()
            for r in rejected:
                writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
        print(f"Rejected CSV: {rej_path}")


def step_generate():
    """Step 3: Generate paper JSONs from validated CSV."""
    csv_path = VALIDATED_CSV if VALIDATED_CSV.exists() else CSV_OUT

    if not csv_path.exists():
        print(f"ERROR: No candidate CSV found. Run --step suggest first.")
        return

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    # Find next paper number
    existing_nums = []
    for p in PAPERS_DIR.glob("paper_*.json"):
        try:
            num = int(p.stem.split("_")[1])
            existing_nums.append(num)
        except (IndexError, ValueError):
            pass
    start_num = max(existing_nums) + 1 if existing_nums else 138

    print(f"Generating paper JSONs starting from paper_{start_num:03d}")
    print(f"Source: {csv_path} ({len(rows)} candidates)")
    print(f"Using generate_paper_jsons.py pipeline...")
    print("=" * 70)

    # Write a temporary CSV in the format expected by generate_paper_jsons.py
    # (same columns but without oa_* fields)
    tmp_csv = Path("experiments/exp_a/_tmp_expand.csv")
    with open(tmp_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "method", "difficulty", "direction",
                                                 "authors", "year", "journal", "title"])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})

    end_num = start_num + len(rows) - 1
    print(f"\nRun this command to generate JSONs:")
    print(f"  python src/pipeline/generate_paper_jsons.py \\")
    print(f"    --csv {tmp_csv} --start {start_num} --end {end_num}")
    print(f"\nOr with dry-run first:")
    print(f"  python src/pipeline/generate_paper_jsons.py \\")
    print(f"    --csv {tmp_csv} --start {start_num} --end {end_num} --dry-run")


def main():
    parser = argparse.ArgumentParser(description="Expand CausalVerify Exp A corpus to 300 papers")
    parser.add_argument("--step", choices=["suggest", "validate", "generate", "all"],
                        required=True, help="Which step to run")
    parser.add_argument("--target", type=int, default=163, help="Number of new papers")
    args = parser.parse_args()

    if args.step in ("suggest", "all"):
        step_suggest(args.target)

    if args.step in ("validate", "all"):
        step_validate()

    if args.step in ("generate", "all"):
        step_generate()


if __name__ == "__main__":
    main()
