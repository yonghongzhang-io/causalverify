"""
Round 2: Fill gaps in the 300-paper expansion.
Targets specific domain × method cells that are still short.
"""

import csv
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

CSV_ROUND1 = Path("experiments/exp_a/benchmark_300_validated.csv")
CSV_OUT = Path("experiments/exp_a/benchmark_300_round2.csv")
PAPERS_DIR = Path("experiments/exp_a/papers")

# Gaps to fill: method → count needed
GAPS = {
    "DID": 13,
    "ES": 18,
    "IV": 18,
    "RDD": 25,
}

# Distribute across domains — focus on cells less covered
ROUND2_CELLS = [
    # DID: 13 more
    ("finance", "DID", 2), ("labor", "DID", 2), ("health", "DID", 2),
    ("public", "DID", 2), ("trade", "DID", 2), ("environment", "DID", 2),
    ("urban", "DID", 1),
    # ES: 18 more
    ("finance", "ES", 3), ("labor", "ES", 3), ("development", "ES", 2),
    ("health", "ES", 2), ("education", "ES", 2), ("public", "ES", 2),
    ("trade", "ES", 2), ("agriculture", "ES", 2),
    # IV: 18 more
    ("finance", "IV", 2), ("labor", "IV", 3), ("development", "IV", 2),
    ("health", "IV", 2), ("education", "IV", 2), ("public", "IV", 3),
    ("trade", "IV", 2), ("urban", "IV", 2),
    # RDD: 25 more
    ("finance", "RDD", 3), ("labor", "RDD", 3), ("development", "RDD", 3),
    ("health", "RDD", 3), ("education", "RDD", 3), ("public", "RDD", 3),
    ("environment", "RDD", 3), ("trade", "RDD", 2), ("urban", "RDD", 2),
]

DIFFICULTIES = ["easy", "medium", "hard"]


def load_all_existing_titles():
    titles = set()
    for f in PAPERS_DIR.glob("paper_*.json"):
        try:
            d = json.loads(f.read_text())
            titles.add(d.get("title", "").lower().strip())
        except Exception:
            pass
    # Round 1 validated
    if CSV_ROUND1.exists():
        with open(CSV_ROUND1) as f:
            for row in csv.DictReader(f):
                titles.add(row.get("title", "").lower().strip())
    return titles


def suggest_papers(domain, method, count, existing_titles):
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
        "labor": "labor economics, employment, wages, immigration, minimum wage",
        "development": "development economics, growth, poverty, institutions, microfinance",
        "health": "health economics, healthcare policy, insurance, mortality",
        "education": "education economics, school policy, returns to education, teacher quality",
        "public": "public economics, taxation, public goods, fiscal policy, crime",
        "trade": "international trade, trade agreements, tariffs, globalization, FDI",
        "environment": "environmental economics, climate, pollution, energy policy, carbon",
        "urban": "urban economics, housing, transportation, land use, real estate, zoning",
        "agriculture": "agricultural economics, food policy, farming, land, water resources",
    }

    # Build exclusion list (sample from existing)
    sample_exclusions = list(existing_titles)[:50]
    exclusion_text = "\n".join(f"- {t}" for t in sample_exclusions[:30])

    prompt = f"""List exactly {count + 4} real, published empirical economics papers that use **{method_names[method]}** as their primary identification strategy, in **{domain_desc.get(domain, domain)}**.

STRICT requirements:
- Must be REAL papers published in recognized economics journals (AER, QJE, JPE, Econometrica, REStat, JF, JFE, RFS, JPublE, JHR, JOLE, JDE, JUE, JEEM, AEJ journals, JIE, EJ, RAND, etc.)
- Published between 1990 and 2024
- Must have a CLEAR causal identification using {method_names[method]}
- Each paper must have a definitive positive or negative main finding

DO NOT suggest any of these papers (already in the benchmark):
{exclusion_text}

For each paper, output a JSON array:
[
  {{
    "authors": "LastName1 & LastName2",
    "year": 2005,
    "journal": "AER",
    "title": "Exact Full Paper Title",
    "direction": "positive",
    "difficulty": "easy"
  }}
]

Difficulty: easy = classic/clean, medium = standard, hard = technically complex.
Output ONLY the JSON array."""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert empirical economist. Output only valid JSON arrays."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
        temperature=0.5,
    )

    content = resp.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3].strip()

    papers = json.loads(content)
    results = []
    for p in papers:
        t = p["title"].lower().strip()
        if t in existing_titles:
            continue
        existing_titles.add(t)
        results.append(p)
        if len(results) >= count:
            break
    return results


def validate_openalex(title, year):
    import urllib.request, urllib.parse
    query = urllib.parse.quote(title)
    url = f"https://api.openalex.org/works?search={query}&filter=publication_year:{year}&per_page=3&mailto=benchmark@causalbench.org"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CausalVerify/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        if not results:
            return False, "not_found"
        oa_title = results[0].get("title", "").lower()
        our_tokens = set(title.lower().split())
        oa_tokens = set(oa_title.split())
        overlap = len(our_tokens & oa_tokens) / max(len(our_tokens), 1)
        if overlap >= 0.5:
            return True, results[0].get("doi", "")
        return False, "mismatch"
    except Exception as e:
        return False, str(e)


def main():
    existing_titles = load_all_existing_titles()
    print(f"Loaded {len(existing_titles)} existing titles")

    all_candidates = []
    diff_idx = 0

    for domain, method, count in ROUND2_CELLS:
        print(f"\n[{domain}/{method}] Requesting {count} papers...")
        try:
            papers = suggest_papers(domain, method, count, existing_titles)
            # Validate each
            for p in papers:
                valid, info = validate_openalex(p["title"], p["year"])
                status = "OK" if valid else f"SKIP({info})"
                print(f"    {status}: {p['authors']} ({p['year']}) — {p['title'][:60]}")
                if valid:
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
                time.sleep(0.15)
            time.sleep(0.5)
        except Exception as e:
            print(f"    [ERROR] {e}")

    with open(CSV_OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "method", "difficulty", "direction",
                                                 "authors", "year", "journal", "title"])
        writer.writeheader()
        writer.writerows(all_candidates)

    from collections import Counter
    mc = Counter(c["method"] for c in all_candidates)
    print(f"\n{'='*70}")
    print(f"Round 2: {len(all_candidates)} validated candidates")
    print(f"By method: {dict(mc)}")
    print(f"Saved to: {CSV_OUT}")


if __name__ == "__main__":
    main()
