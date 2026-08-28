"""
Query OpenAlex for the frequency of causal-inference method names in
published economics literature (2010-2024). Used to test whether the
ES detection gap is explained by training-corpus frequency.

If 'event study' is much rarer than 'difference-in-differences' in the
corpus, that alone could explain the ES gap. If they're comparable but
ES is still harder, the gap is method-inherent.
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

OUT_PATH = Path("experiments/exp_a/method_frequency.json")

# Method queries: each one is a list of synonyms to search for
METHODS = {
    "DID": [
        "difference-in-differences",
        "difference in differences",
        "diff-in-diff",
    ],
    "EVENT_STUDY": [
        "event study",
        "event-study",
    ],
    "IV": [
        "instrumental variable",
        "instrumental variables",
        "two-stage least squares",
    ],
    "RDD": [
        "regression discontinuity",
        "regression-discontinuity",
    ],
}

# Restrict to economics journals via concept filter
# Economics OpenAlex concept ID: C162324750
ECON_CONCEPT = "C162324750"


def openalex_count(query: str, year_from: int = 2010, year_to: int = 2024) -> int:
    """Count works matching query in economics concept, with year filter."""
    params = {
        "search": query,
        "filter": f"concepts.id:{ECON_CONCEPT},publication_year:{year_from}-{year_to}",
        "per-page": "1",
        "mailto": "benchmark@causalbench.org",
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CausalVerify/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return int(data.get("meta", {}).get("count", 0))
    except Exception as e:
        print(f"  ERROR: {e}")
        return -1


def main():
    print("Querying OpenAlex for method frequency in economics (2010-2024)...")
    print()

    results = {}
    for method, synonyms in METHODS.items():
        print(f"{method}:")
        method_total = 0
        by_query = {}
        for q in synonyms:
            n = openalex_count(q)
            print(f"  '{q}': {n:,} papers")
            by_query[q] = n
            method_total += max(0, n)
            time.sleep(0.2)  # rate-limit politeness
        results[method] = {
            "total_or_count": method_total,  # rough sum, may double-count
            "max_single_query": max(by_query.values()),
            "by_query": by_query,
        }
        print(f"  → max single query: {max(by_query.values()):,}")
        print()

    # Ranking
    print("=" * 60)
    print("Method frequency ranking (by max single query):")
    print("=" * 60)
    sorted_methods = sorted(results.items(),
                            key=lambda kv: -kv[1]["max_single_query"])
    for m, data in sorted_methods:
        print(f"  {m:<12}: {data['max_single_query']:>8,} papers")

    # Compare to detection rates
    print()
    print("Compare to L3 detection rates (mean across 6 models, 262 papers):")
    detection_rates = {
        "DID": 0.78, "RDD": 0.78, "IV": 0.54, "EVENT_STUDY": 0.27,
    }
    for m in ["DID", "RDD", "IV", "EVENT_STUDY"]:
        freq = results[m]["max_single_query"]
        det = detection_rates[m]
        print(f"  {m:<12}: freq={freq:>7,} | L3 detection={det*100:.0f}%")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "results": results,
        "detection_rates": detection_rates,
        "note": "L3 detection rates are mean across 6 frontier models, 262 papers"
    }, indent=2))
    print(f"\nSaved: {OUT_PATH}")


if __name__ == "__main__":
    main()
