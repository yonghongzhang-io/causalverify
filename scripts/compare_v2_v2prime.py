"""
Compare V2 (8-page) vs V2' (20-page) outputs on the 20-paper diagnostic sample.

For each paper, per field (research_question / data_description / institutional_context):
  - char_len_delta   : len(V2') - len(V2)
  - jaccard_tokens   : |V2 ∩ V2'| / |V2 ∪ V2'|  (overlap sanity check)
  - new_dates        : count of date/year tokens in V2' not in V2
  - new_numbers      : count of numeric tokens in V2' not in V2
  - new_caps_phrases : count of proper-noun phrases in V2' not in V2

Per paper, compute new_method_signal ∈ {YES, AMBIGUOUS, NO} by counting
methodologically-loaded "new evidence" across the three fields (see THRESHOLDS).

Output:
  audit/v2_vs_v2prime_pilot.csv        — per-paper rows (one per field + summary)
  audit/v2_vs_v2prime_pilot_summary.md — aggregate stats + decision
  audit/v2_vs_v2prime_pilot_pairs.md   — side-by-side text (human sanity-check)
"""

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
V2_JSON  = ROOT / "audit/regen_from_pdf.json"
V2P_JSON = ROOT / "audit/regen_from_pdf_v2prime_pilot.json"
OUT_CSV  = ROOT / "audit/v2_vs_v2prime_pilot.csv"
OUT_SUM  = ROOT / "audit/v2_vs_v2prime_pilot_summary.md"
OUT_PAIRS = ROOT / "audit/v2_vs_v2prime_pilot_pairs.md"

FIELDS = ["research_question", "data_description", "institutional_context"]

# Patterns
YEAR_RE    = re.compile(r"\b(19|20)\d{2}\b")
DATE_RE    = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?\b", re.IGNORECASE)
NUMBER_RE  = re.compile(r"(?<!\w)(?:\$?\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|%|percent|bps|bp)?|\d+(?:\.\d+)?%)(?!\w)")
CAPS_PHRASE_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+(?:of|the|and|for|de|von|van)\s+)?){1,}(?:[A-Z][a-z]+|[A-Z]{2,})\b")
TOKEN_RE   = re.compile(r"[A-Za-z][A-Za-z\-']+")

# Stopwords for jaccard — very small list, we want low-frequency content tokens
STOP = {
    "the","a","an","and","or","of","in","to","for","on","at","by","with",
    "from","as","is","are","was","were","be","been","being","this","that",
    "these","those","which","who","whom","their","its","it","we","our",
    "using","uses","used","based","study","paper","data","analysis","study's"
}

def tokens(s):
    return [t.lower() for t in TOKEN_RE.findall(s or "") if t.lower() not in STOP]

def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)

def extract_dates(s):
    # unique year/date tokens
    items = set()
    for m in YEAR_RE.finditer(s or ""): items.add(m.group(0))
    for m in DATE_RE.finditer(s or ""): items.add(m.group(0).lower())
    return items

def extract_numbers(s):
    items = set()
    for m in NUMBER_RE.finditer(s or ""): items.add(m.group(0))
    return items

def extract_caps_phrases(s):
    items = set()
    for m in CAPS_PHRASE_RE.finditer(s or ""):
        phrase = m.group(0)
        if len(phrase) >= 4:  # skip single capitalized words
            items.add(phrase)
    return items

def load_map(path, field="new_fields"):
    data = json.loads(path.read_text())
    return {r["paper_id"]: r.get(field, {}) for r in data
             if field in r and isinstance(r.get(field), dict)}

def classify_signal(per_field_deltas):
    """Combine per-field new_evidence into a per-paper signal."""
    # sum methodology-bearing "new evidence" across fields
    total_new_dates = sum(d["new_dates_n"] for d in per_field_deltas)
    total_new_nums  = sum(d["new_numbers_n"] for d in per_field_deltas)
    total_new_caps  = sum(d["new_caps_n"] for d in per_field_deltas)
    total_char_gain = sum(max(0, d["char_len_delta"]) for d in per_field_deltas)
    score = 0
    if total_new_dates >= 2: score += 1
    if total_new_nums  >= 3: score += 1
    if total_new_caps  >= 3: score += 1
    if total_char_gain >= 400: score += 1
    if score >= 3: return "YES"
    if score >= 2: return "AMBIGUOUS"
    return "NO"

def main():
    v2  = load_map(V2_JSON)
    v2p = load_map(V2P_JSON)

    sample = []
    with open(ROOT/"audit/v2prime_pilot_sample.csv") as f:
        for r in csv.DictReader(f):
            sample.append((r["paper_id"], r["method_family"]))

    rows = []
    pair_blocks = []
    summary_counts = Counter()
    by_family_signal = {}

    for pid, fam in sample:
        if pid not in v2 or pid not in v2p:
            print(f"  SKIP {pid}: missing in one side")
            continue
        per_field = []
        for fld in FIELDS:
            old = v2[pid].get(fld, "") or ""
            new = v2p[pid].get(fld, "") or ""
            old_d  = extract_dates(old);    new_d  = extract_dates(new)
            old_n  = extract_numbers(old);  new_n  = extract_numbers(new)
            old_c  = extract_caps_phrases(old); new_c = extract_caps_phrases(new)
            new_dates  = new_d - old_d
            new_nums   = new_n - old_n
            new_caps   = new_c - old_c
            per_field.append({
                "paper_id": pid, "method_family": fam, "field": fld,
                "v2_chars": len(old), "v2p_chars": len(new),
                "char_len_delta": len(new) - len(old),
                "jaccard_tokens": round(jaccard(tokens(old), tokens(new)), 3),
                "new_dates_n": len(new_dates),
                "new_numbers_n": len(new_nums),
                "new_caps_n": len(new_caps),
                "new_dates_sample": "; ".join(sorted(new_dates))[:200],
                "new_numbers_sample": "; ".join(sorted(new_nums))[:200],
                "new_caps_sample": "; ".join(sorted(new_caps))[:200],
            })
        signal = classify_signal(per_field)
        summary_counts[signal] += 1
        by_family_signal.setdefault(fam, Counter())[signal] += 1
        for pf in per_field:
            pf["paper_new_method_signal"] = signal
            rows.append(pf)

        # Side-by-side block for human review
        pair_blocks.append(
            f"## {pid}  [{fam}]  signal={signal}\n\n"
            + "\n".join(
                f"### {fld}\n\n"
                f"**V2 (8-page)**:\n> {v2[pid].get(fld,'')[:500]}\n\n"
                f"**V2' (20-page)**:\n> {v2p[pid].get(fld,'')[:500]}\n"
                for fld in FIELDS
            )
        )

    # Write per-row CSV
    with open(OUT_CSV, "w", newline="") as f:
        fieldnames = ["paper_id","method_family","field",
                       "v2_chars","v2p_chars","char_len_delta","jaccard_tokens",
                       "new_dates_n","new_numbers_n","new_caps_n",
                       "new_dates_sample","new_numbers_sample","new_caps_sample",
                       "paper_new_method_signal"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows: w.writerow(r)

    # Summary report
    n_papers = sum(summary_counts.values())
    yes_n    = summary_counts["YES"]
    amb_n    = summary_counts["AMBIGUOUS"]
    no_n     = summary_counts["NO"]
    yes_frac = yes_n / n_papers if n_papers else 0

    # Aggregate deltas
    avg_char_delta = {}
    for fld in FIELDS:
        deltas = [r["char_len_delta"] for r in rows if r["field"] == fld]
        avg_char_delta[fld] = sum(deltas)/len(deltas) if deltas else 0
    avg_jaccard = {}
    for fld in FIELDS:
        js = [r["jaccard_tokens"] for r in rows if r["field"] == fld]
        avg_jaccard[fld] = sum(js)/len(js) if js else 0

    # Decision per pre-registered rule
    if yes_frac >= 0.30:
        decision = ("GREENLIGHT full V2' restructure. "
                     "V2' surfaces materially new methodological evidence "
                     "in enough papers to justify the $220–290 cost.")
    elif yes_frac < 0.15:
        decision = ("KEEP V2. V2' does not surface new methodological "
                     "evidence in enough papers; the 20-page expansion is "
                     "not worth $220–290. Proceed with Option A (strip V1).")
    else:
        decision = ("AMBIGUOUS. Manual review of YES + AMBIGUOUS cases "
                     "below recommended before committing $220.")

    md = [
        "# V2 vs V2' Diagnostic Summary",
        "",
        f"- Sample: **{n_papers} papers** (5 per family x 4 families, seed 20260424)",
        f"- V2  baseline: `audit/regen_from_pdf.json` (8-page, 20K chars)",
        f"- V2' pilot:    `audit/regen_from_pdf_v2prime_pilot.json` (20-page, 60K chars)",
        f"- V2' run cost: **$7.47**",
        "",
        "## Signal distribution",
        "",
        f"| Signal | N | % |",
        f"|---|---|---|",
        f"| YES       | {yes_n} | {100*yes_n/n_papers:.0f}% |",
        f"| AMBIGUOUS | {amb_n} | {100*amb_n/n_papers:.0f}% |",
        f"| NO        | {no_n}  | {100*no_n/n_papers:.0f}% |",
        "",
        "## By method family",
        "",
        "| Family | YES | AMBIG | NO |",
        "|---|---|---|---|",
    ]
    for fam in ["DID","EVENT_STUDY","IV","RDD"]:
        c = by_family_signal.get(fam, Counter())
        md.append(f"| {fam} | {c.get('YES',0)} | {c.get('AMBIGUOUS',0)} | {c.get('NO',0)} |")
    md += [
        "",
        "## Average per-field deltas",
        "",
        "| Field | avg char_delta | avg jaccard |",
        "|---|---|---|",
    ]
    for fld in FIELDS:
        md.append(f"| {fld} | {avg_char_delta[fld]:+.0f} | {avg_jaccard[fld]:.2f} |")
    md += [
        "",
        "## Decision rule (pre-registered)",
        "",
        "- **>= 30% YES** -> greenlight full V2' restructure ($220-290)",
        "- **< 15% YES**  -> keep V2, do Option A (strip V1 only)",
        "- **15-30% YES** -> manual review before committing",
        "",
        f"**Observed: {yes_frac*100:.0f}% YES**",
        "",
        f"### Verdict",
        "",
        f"**{decision}**",
        "",
        "## Files",
        f"- Per-row details: `audit/v2_vs_v2prime_pilot.csv`",
        f"- Side-by-side text: `audit/v2_vs_v2prime_pilot_pairs.md`",
    ]
    OUT_SUM.write_text("\n".join(md))

    OUT_PAIRS.write_text(
        "# V2 vs V2' Side-by-side (20 papers)\n\n"
        + "\n\n---\n\n".join(pair_blocks)
    )

    print("".join([
        f"Processed: {n_papers} papers\n",
        f"  YES:       {yes_n} ({100*yes_n/n_papers:.0f}%)\n",
        f"  AMBIGUOUS: {amb_n} ({100*amb_n/n_papers:.0f}%)\n",
        f"  NO:        {no_n} ({100*no_n/n_papers:.0f}%)\n\n",
        f"Decision: {decision}\n\n",
        f"Wrote:\n",
        f"  {OUT_CSV.relative_to(ROOT)}\n",
        f"  {OUT_SUM.relative_to(ROOT)}\n",
        f"  {OUT_PAIRS.relative_to(ROOT)}\n",
    ]))

if __name__ == "__main__":
    main()
