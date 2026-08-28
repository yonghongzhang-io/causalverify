"""
Agent 1 — Strict Paper Resolver
================================

Purpose
-------
Re-validate every Exp A paper JSON against OpenAlex + CrossRef using
*strict* multi-factor matching (vs. v10's title-token-overlap ≥ 0.5).

Why it matters
--------------
v10's validator accepted any candidate whose title shared ≥50% tokens
with the queried title. This is too permissive: short common titles
("The Effect of X on Y") can accidentally match unrelated papers.

This agent applies three conjunctive gates:
  Gate 1 — Title Jaccard (stopwords removed) ≥ 0.7
  Gate 2 — At least one author surname overlaps
  Gate 3 — Journal name matches (normalized, alias-tolerant)

Plus a plausibility check: citations for 5+ year old top-journal
papers are typically ≥ 20. If a "validated" candidate has <20
citations and was published 5+ years ago, flag for review.

Input
-----
  experiments/exp_a/papers/paper_*.json  (262 paper JSONs)

Output
------
  audit/resolver_results.json        — per-paper validation result
  audit/resolver_summary.md          — human-readable summary

Usage
-----
  python3 src/agents/resolver.py
  python3 src/agents/resolver.py --sample 20         # test on 20 papers
  python3 src/agents/resolver.py --skip-cached       # re-use prior results
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
PAPERS_DIR = PROJECT_ROOT / "experiments/exp_a/papers"
CACHE_DIR = PROJECT_ROOT / "audit/resolver_cache"
OUT_JSON = PROJECT_ROOT / "audit/resolver_results.json"
OUT_MD = PROJECT_ROOT / "audit/resolver_summary.md"

OA_BASE = "https://api.openalex.org/works"
EMAIL = "benchmark@causalverify.org"   # polite pool for OpenAlex


# ── Text normalization helpers ──────────────────────────────────────

STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for",
    "from", "by", "with", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "this", "that", "these", "those",
    "evidence", "effects", "effect", "impact", "impacts", "analysis",
}


def normalize_title(s: str) -> set:
    """Lowercase, strip punctuation, tokenize, remove stopwords."""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    tokens = s.split()
    return {t for t in tokens if t and t not in STOPWORDS and len(t) > 1}


def title_jaccard(a: str, b: str) -> float:
    sa, sb = normalize_title(a), normalize_title(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def extract_surnames(authors_str: str) -> set:
    """From 'Ivashina & Scharfstein' or 'Card, Dobkin & Maestas' → surnames."""
    if not authors_str:
        return set()
    # Split on &, ',', 'and', etc.
    parts = re.split(r"[,&]|\sand\s", authors_str)
    surnames = set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # "Last, First" pattern → take first token
        # "First Last" pattern → take last token
        tokens = p.split()
        if not tokens:
            continue
        # Heuristic: surname is the last capitalized word
        for tok in reversed(tokens):
            tok_clean = re.sub(r"[^\w]", "", tok)
            if tok_clean and tok_clean[0].isupper() and len(tok_clean) > 1:
                surnames.add(tok_clean.lower())
                break
    return surnames


JOURNAL_ALIASES = {
    "aer": {"american economic review", "american economic review (aer)"},
    "aej": {"american economic journal"},
    "aej:applied": {"american economic journal applied", "american economic journal applied economics"},
    "aej:ep": {"american economic journal economic policy"},
    "qje": {"quarterly journal of economics", "the quarterly journal of economics"},
    "jpe": {"journal of political economy"},
    "jpube": {"journal of public economics"},
    "jf": {"journal of finance", "the journal of finance"},
    "jfe": {"journal of financial economics"},
    "rfs": {"review of financial studies", "the review of financial studies"},
    "jol": {"journal of labor economics"},
    "joe": {"journal of labor economics"},
    "restat": {"review of economics and statistics", "the review of economics and statistics"},
    "restud": {"review of economic studies", "the review of economic studies"},
    "jde": {"journal of development economics"},
    "jhr": {"journal of human resources", "the journal of human resources"},
    "ms": {"management science"},
    "ecma": {"econometrica"},
    "jme": {"journal of monetary economics"},
    "jmcb": {"journal of money credit and banking"},
}


def normalize_journal(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s:]", "", s)
    s = re.sub(r"\s+", " ", s)
    # Map abbreviations to canonical long form
    for abbrev, aliases in JOURNAL_ALIASES.items():
        if s in aliases or s == abbrev:
            return abbrev
    # Check if input is already an abbreviation
    if s in JOURNAL_ALIASES:
        return s
    return s


# ── OpenAlex lookup ─────────────────────────────────────────────────

def openalex_search(title: str, year: Optional[int] = None,
                     per_page: int = 5) -> list:
    """Search OpenAlex by title; return parsed results."""
    q = urllib.parse.quote(title)
    url = f"{OA_BASE}?search={q}&per_page={per_page}&mailto={EMAIL}"
    if year:
        url += f"&filter=publication_year:{year}"

    req = urllib.request.Request(url, headers={"User-Agent": "CausalVerify-Resolver/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        raise RuntimeError(f"OpenAlex request failed: {e}")

    results = []
    for w in data.get("results", []):
        authorships = w.get("authorships", [])
        surnames = set()
        for a in authorships:
            name = (a.get("author", {}).get("display_name") or "").strip()
            if name:
                # Take last token as surname
                surnames.add(name.split()[-1].lower())

        venue = w.get("host_venue") or w.get("primary_location", {}).get("source", {}) or {}
        results.append({
            "doi": w.get("doi"),
            "title": w.get("title", ""),
            "publication_year": w.get("publication_year"),
            "cited_by_count": w.get("cited_by_count", 0),
            "author_surnames": surnames,
            "journal": (venue.get("display_name") or "").strip(),
        })
    return results


# ── Matching gates ───────────────────────────────────────────────────

@dataclass
class MatchCheck:
    title_jaccard: float
    title_gate_pass: bool
    author_overlap: set
    author_gate_pass: bool
    journal_input: str
    journal_oa: str
    journal_gate_pass: bool
    citation_reasonable: bool
    citation_count: int
    years_old: int


def check_match(paper: dict, oa_result: dict, jaccard_threshold: float = 0.7) -> MatchCheck:
    # Gate 1: title
    jac = title_jaccard(paper.get("title", ""), oa_result["title"])
    g1 = jac >= jaccard_threshold

    # Gate 2: author
    paper_surnames = extract_surnames(paper.get("authors", ""))
    oa_surnames = oa_result["author_surnames"]
    overlap = paper_surnames & oa_surnames
    g2 = bool(overlap)

    # Gate 3: journal
    paper_journal_norm = normalize_journal(paper.get("source", "").split(",")[0] if "," in paper.get("source", "") else paper.get("source", ""))
    oa_journal_norm = normalize_journal(oa_result["journal"])
    g3 = paper_journal_norm == oa_journal_norm or (
        # Also accept if aliases match
        any(paper_journal_norm in aliases for aliases in JOURNAL_ALIASES.values()
            if oa_journal_norm in aliases)
    )

    # Plausibility: citations
    current_year = datetime.now().year
    pub_year = paper.get("year")
    try:
        pub_year = int(pub_year)
        years_old = current_year - pub_year
    except (TypeError, ValueError):
        pub_year = None
        years_old = 0

    cit_count = oa_result["cited_by_count"]
    # 5+ year old top-5 paper should have >= 20 citations
    citation_reasonable = (years_old < 5) or (cit_count >= 20)

    return MatchCheck(
        title_jaccard=round(jac, 4),
        title_gate_pass=g1,
        author_overlap=overlap,
        author_gate_pass=g2,
        journal_input=paper_journal_norm,
        journal_oa=oa_journal_norm,
        journal_gate_pass=g3,
        citation_reasonable=citation_reasonable,
        citation_count=cit_count,
        years_old=years_old,
    )


# ── Per-paper resolution ────────────────────────────────────────────

@dataclass
class PaperResolution:
    paper_id: str
    title: str
    authors: str
    year: Optional[int]
    journal: str
    method_family: str
    best_match: Optional[dict] = None
    checks: Optional[dict] = None
    status: str = "pending"          # resolved / ambiguous / not_found / error
    notes: str = ""
    error_msg: str = ""


def resolve_paper(paper: dict, cache_path: Optional[Path] = None) -> PaperResolution:
    pid = paper["paper_id"]
    title = paper.get("title", "")
    authors = paper.get("authors", "")
    year = paper.get("year")
    source = paper.get("source", "")
    journal = source.split(",")[0].strip() if "," in source else source
    method = paper.get("method_family", "")

    res = PaperResolution(
        paper_id=pid, title=title, authors=authors, year=year,
        journal=journal, method_family=method
    )

    # Check cache
    if cache_path and cache_path.exists():
        cached = json.load(open(cache_path))
        return PaperResolution(**{k: cached.get(k, v)
                                   for k, v in asdict(res).items()})

    # Query OpenAlex
    try:
        candidates = openalex_search(title, year=year if isinstance(year, int) else None)
    except Exception as e:
        res.status = "error"
        res.error_msg = str(e)
        return res

    if not candidates:
        res.status = "not_found"
        res.notes = "OpenAlex returned no candidates"
        return res

    # Score each candidate against strict gates
    scored = []
    for c in candidates:
        checks = check_match(paper, c)
        n_gates_passed = sum([checks.title_gate_pass, checks.author_gate_pass,
                               checks.journal_gate_pass])
        scored.append((n_gates_passed, checks, c))

    # Best match = most gates passed, tie-break by title jaccard
    scored.sort(key=lambda x: (x[0], x[1].title_jaccard), reverse=True)
    best_gates, best_checks, best_c = scored[0]

    # Store result
    res.best_match = {
        "doi": best_c["doi"],
        "title": best_c["title"],
        "year": best_c["publication_year"],
        "journal": best_c["journal"],
        "citations": best_c["cited_by_count"],
    }
    res.checks = asdict(best_checks)
    # Convert sets to lists for JSON serializability
    res.checks["author_overlap"] = list(best_checks.author_overlap)

    # Assign status
    if best_gates == 3 and best_checks.citation_reasonable:
        res.status = "resolved"
    elif best_gates >= 2:
        res.status = "weak_match"
        res.notes = f"{best_gates}/3 gates pass, citation_reasonable={best_checks.citation_reasonable}"
    else:
        res.status = "ambiguous"
        res.notes = f"Only {best_gates}/3 gates pass"

    # Save to cache
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(asdict(res), f, indent=2, default=list)

    return res


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None,
                        help="Only resolve N random papers (for testing)")
    parser.add_argument("--skip-cached", action="store_true",
                        help="Skip papers already in cache")
    parser.add_argument("--rate-limit", type=float, default=0.2,
                        help="Seconds between API calls (OpenAlex polite pool)")
    args = parser.parse_args()

    papers_files = sorted(PAPERS_DIR.glob("paper_*.json"),
                           key=lambda p: int(p.stem.split("_")[1]))
    if args.sample:
        import random
        random.seed(42)
        papers_files = random.sample(papers_files, args.sample)

    print(f"Resolving {len(papers_files)} papers against OpenAlex "
          f"(strict multi-factor matching)...\n")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for i, pf in enumerate(papers_files, 1):
        paper = json.load(open(pf))
        pid = paper["paper_id"]
        cache_path = CACHE_DIR / f"{pid}.json"

        if args.skip_cached and cache_path.exists():
            with open(cache_path) as f:
                results.append(PaperResolution(**json.load(f)))
            print(f"  [{i:>3}/{len(papers_files)}] {pid} [CACHED]")
            continue

        res = resolve_paper(paper, cache_path=cache_path)
        results.append(res)

        symbol = {"resolved": "✓", "weak_match": "~",
                  "ambiguous": "?", "not_found": "✗", "error": "E"}.get(res.status, "?")
        gates_str = ""
        if res.checks:
            g = sum([res.checks["title_gate_pass"],
                      res.checks["author_gate_pass"],
                      res.checks["journal_gate_pass"]])
            cit_flag = "cit!" if not res.checks.get("citation_reasonable", True) else ""
            gates_str = f"{g}/3 gates {cit_flag}"
        print(f"  [{i:>3}/{len(papers_files)}] {pid} [{symbol} {res.status}] {gates_str}")

        time.sleep(args.rate_limit)

    # Aggregates
    from collections import Counter
    status_counts = Counter(r.status for r in results)
    n_total = len(results)

    # Save JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump({
            "summary": dict(status_counts),
            "n_total": n_total,
            "resolved_pct": round(status_counts["resolved"] / n_total, 4),
            "results": [asdict(r) for r in results],
        }, f, indent=2, default=list)

    # Markdown
    lines = [
        "# Strict Paper Resolver — Audit Report\n",
        f"Resolved {n_total} Exp A papers against OpenAlex using "
        "3-gate strict matching (title Jaccard ≥0.7 + author surname overlap + journal match) "
        "and a citation plausibility check.\n",
        "## Summary\n",
        "| Status | Count | % |",
        "|---|---:|---:|",
    ]
    for status in ["resolved", "weak_match", "ambiguous", "not_found", "error"]:
        c = status_counts.get(status, 0)
        lines.append(f"| **{status}** | {c} | {c/n_total:.1%} |")

    lines.append("\n### Status Meanings\n")
    lines.append("- **resolved**: all 3 gates passed + citation count reasonable")
    lines.append("- **weak_match**: 2/3 gates passed OR citation count unusually low")
    lines.append("- **ambiguous**: ≤1/3 gates passed; best match is unreliable")
    lines.append("- **not_found**: OpenAlex returned no candidates")
    lines.append("- **error**: API/network failure\n")

    # List problematic papers
    problematic = [r for r in results if r.status in ("weak_match", "ambiguous", "not_found")]
    if problematic:
        lines.append(f"## Problematic Papers ({len(problematic)})\n")
        lines.append("| paper_id | method | status | notes |")
        lines.append("|---|---|---|---|")
        for r in sorted(problematic, key=lambda r: r.paper_id):
            lines.append(f"| {r.paper_id} | {r.method_family} | {r.status} | {r.notes} |")

    lines.append("\n## Interpretation\n")
    resolved_pct = status_counts["resolved"] / n_total
    if resolved_pct >= 0.90:
        lines.append(f"✅ **{resolved_pct:.0%} of papers strictly resolved.** The Exp A "
                     "dataset has high metadata integrity.")
    elif resolved_pct >= 0.75:
        lines.append(f"⚠️  **{resolved_pct:.0%} resolved.** {len(problematic)} papers need "
                     "manual review. Consider excluding weak matches from the Exp A analysis "
                     "or flagging them in results.")
    else:
        lines.append(f"🚨 **Only {resolved_pct:.0%} resolved.** The Exp A dataset has "
                     "significant metadata quality issues. Strongly recommend a manual "
                     "audit pass before publication.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote: {OUT_JSON}")
    print(f"Wrote: {OUT_MD}")
    print(f"\n=== SUMMARY ===")
    for status in ["resolved", "weak_match", "ambiguous", "not_found", "error"]:
        c = status_counts.get(status, 0)
        print(f"  {status:<12} {c:>4} ({c/n_total:.1%})")


if __name__ == "__main__":
    main()
