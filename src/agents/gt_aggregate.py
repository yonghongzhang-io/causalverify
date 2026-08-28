"""
Stage 3 — Aggregate 4-LLM votes into canonical new GT decisions.

Reads:
  audit/gt_reextract_multi.json      (4 votes per paper)

Writes:
  audit/gt_aggregate_decisions.json  (canonical decision + consensus level per paper)
  audit/gt_adjudication_form.csv     (contested + split papers for user to adjudicate)
  audit/gt_aggregate_summary.md      (human-readable overview)

Aggregation rule
----------------
  For method_family:
    Count votes across {opus_4_7, gpt4o, kimi, gemini}.
    - 4/4 agree → consensus_level="all4_agree",   auto-accept
    - 3/4 agree → consensus_level="3of4_agree",   auto-accept majority
    - 2/2 tie   → consensus_level="2of4_tie",     NEEDS HUMAN
    - 4-way     → consensus_level="split",        NEEDS HUMAN

  Direction is aggregated by the same rule, independently of method.

The CSV `gt_adjudication_form.csv` is what the user fills in to resolve
contested cases. Rows are sorted with 4-way splits first (hardest).
"""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
VOTES_IN  = ROOT / "audit/gt_reextract_multi.json"
DEC_OUT   = ROOT / "audit/gt_aggregate_decisions.json"
CSV_OUT   = ROOT / "audit/gt_adjudication_form.csv"
MD_OUT    = ROOT / "audit/gt_aggregate_summary.md"
PAPERS    = ROOT / "experiments/exp_a/papers"

LLM_KEYS = ("opus_4_7", "gpt4o", "kimi", "gemini")


def aggregate_one(votes: dict) -> dict:
    """Return {method, direction, m_level, d_level, m_votes, d_votes}."""
    m_votes = [votes.get(k, {}).get("method")    for k in LLM_KEYS]
    d_votes = [votes.get(k, {}).get("direction") for k in LLM_KEYS]
    m_votes = [v for v in m_votes if v]
    d_votes = [v for v in d_votes if v]

    def _agg(vs):
        if len(vs) < 2:
            return {"value": None, "level": "error_too_few_votes"}
        c = Counter(vs)
        top, top_count = c.most_common(1)[0]
        if top_count == 4:
            return {"value": top, "level": "all4_agree"}
        if top_count == 3:
            return {"value": top, "level": "3of4_agree"}
        if top_count == 2:
            second = c.most_common(2)[1][1] if len(c) > 1 else 0
            if second == 2:
                return {"value": None, "level": "2of4_tie"}  # needs human
            return {"value": top, "level": "2of4_plurality"} # 2,1,1: majority auto
        return {"value": None, "level": "split"}

    m = _agg(m_votes)
    d = _agg(d_votes)
    return {
        "method":     m["value"],
        "m_level":    m["level"],
        "m_votes":    dict(Counter(m_votes)),
        "direction":  d["value"],
        "d_level":    d["level"],
        "d_votes":    dict(Counter(d_votes)),
    }


def find_paper_file(pid: str) -> Path | None:
    hits = list(PAPERS.glob(f"{pid}_*.json")) + list(PAPERS.glob(f"{pid}.json"))
    return hits[0] if hits else None


def main():
    rows = json.loads(VOTES_IN.read_text())
    print(f"Aggregating {len(rows)} papers...")

    decisions = []
    for r in rows:
        pid = r["paper_id"]
        agg = aggregate_one(r)

        # Load paper for context (title, original GT)
        pf = find_paper_file(pid)
        title, orig_method, orig_direction = "", None, None
        if pf:
            p = json.loads(pf.read_text())
            title          = p.get("title", "")
            orig_method    = p.get("method_family")
            orig_direction = p.get("ground_truth", {}).get("conclusion_direction")

        decisions.append({
            "paper_id":        pid,
            "title":           title,
            "orig_method":     orig_method,
            "orig_direction":  orig_direction,
            "new_method":      agg["method"],
            "new_direction":   agg["direction"],
            "m_level":         agg["m_level"],
            "d_level":         agg["d_level"],
            "m_votes":         agg["m_votes"],
            "d_votes":         agg["d_votes"],
            "votes_raw":       {k: r.get(k) for k in LLM_KEYS},
            "needs_human":     agg["m_level"] in ("2of4_tie", "split") or
                               agg["d_level"] in ("2of4_tie", "split"),
            "method_changed":  (agg["method"] is not None
                                and agg["method"] != orig_method),
            "direction_changed": (agg["direction"] is not None
                                  and agg["direction"] != orig_direction),
        })

    DEC_OUT.write_text(json.dumps(decisions, indent=2, ensure_ascii=False))
    print(f"Wrote {DEC_OUT}")

    # ── Adjudication CSV (for contested + split only) ──
    needs = [d for d in decisions if d["needs_human"]]
    # Sort: 4-way splits first, then 2of4 method ties, then direction-only ties
    def priority(d):
        if d["m_level"] == "split":       return (0, d["paper_id"])
        if d["m_level"] == "2of4_tie":    return (1, d["paper_id"])
        if d["d_level"] == "split":       return (2, d["paper_id"])
        return (3, d["paper_id"])
    needs.sort(key=priority)

    with open(CSV_OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "paper_id", "title", "priority",
            "orig_method", "orig_direction",
            "opus47_method", "gpt4o_method", "kimi_method", "gemini_method",
            "opus47_dir",    "gpt4o_dir",    "kimi_dir",    "gemini_dir",
            "m_level", "d_level",
            # User fills these:
            "your_method",       # DID / EVENT_STUDY / IV / RDD / OTHER / <unchanged>
            "your_direction",    # positive / negative / mixed / unclear / <unchanged>
            "supporting_evidence",  # "page/line/abstract phrase"
        ])
        for d in needs:
            def _get(llm, k):
                x = d["votes_raw"].get(llm) or {}
                return x.get(k, "?")
            w.writerow([
                d["paper_id"], d["title"][:80], priority(d)[0],
                d["orig_method"], d["orig_direction"],
                _get("opus_4_7","method"), _get("gpt4o","method"),
                _get("kimi","method"),    _get("gemini","method"),
                _get("opus_4_7","direction"), _get("gpt4o","direction"),
                _get("kimi","direction"),     _get("gemini","direction"),
                d["m_level"], d["d_level"],
                "", "", "",
            ])
    print(f"Wrote {CSV_OUT}   ({len(needs)} rows for adjudication)")

    # ── Markdown summary ──
    from collections import defaultdict
    m_buckets = defaultdict(int)
    d_buckets = defaultdict(int)
    for d in decisions:
        m_buckets[d["m_level"]] += 1
        d_buckets[d["d_level"]] += 1
    n_method_changed    = sum(1 for d in decisions if d["method_changed"])
    n_direction_changed = sum(1 for d in decisions if d["direction_changed"])
    total = len(decisions)

    md = [
        "# GT Aggregation Summary (Stage 3)",
        "",
        f"**Input**: {VOTES_IN.name} ({total} papers × 4 LLM votes)",
        f"**Output**: {DEC_OUT.name}, {CSV_OUT.name}",
        "",
        "## Consensus distribution — Method family",
        "",
        "| Level | Count | % |",
        "|---|---:|---:|",
    ]
    for lvl in ("all4_agree", "3of4_agree", "2of4_plurality",
                "2of4_tie", "split", "error_too_few_votes"):
        n = m_buckets.get(lvl, 0)
        md.append(f"| {lvl} | {n} | {n/total*100:.0f}% |")

    md += [
        "",
        "## Consensus distribution — Direction",
        "",
        "| Level | Count | % |",
        "|---|---:|---:|",
    ]
    for lvl in ("all4_agree", "3of4_agree", "2of4_plurality",
                "2of4_tie", "split", "error_too_few_votes"):
        n = d_buckets.get(lvl, 0)
        md.append(f"| {lvl} | {n} | {n/total*100:.0f}% |")

    md += [
        "",
        "## Label-change impact",
        "",
        f"- **Method changed from original GPT-4o GT**: {n_method_changed} / {total} "
        f"({n_method_changed/total*100:.0f}%)",
        f"- **Direction changed from original GPT-4o GT**: {n_direction_changed} / {total} "
        f"({n_direction_changed/total*100:.0f}%)",
        "",
        "## What needs human adjudication",
        "",
        f"- **{len(needs)} papers** have `2of4_tie` or `split` on method or direction.",
        f"- Open `{CSV_OUT.name}` and fill in `your_method`, `your_direction`, "
        "and `supporting_evidence` for each row.",
        "- Sort is: 4-way splits first (hardest), then method ties, then direction ties.",
    ]
    MD_OUT.write_text("\n".join(md) + "\n")
    print(f"Wrote {MD_OUT}")

    print()
    print(f"Summary: {total} papers processed")
    print(f"  auto-accept   = {m_buckets['all4_agree'] + m_buckets['3of4_agree'] + m_buckets['2of4_plurality']}")
    print(f"  needs human   = {len(needs)}")
    print(f"  method change = {n_method_changed}")
    print(f"  dir change    = {n_direction_changed}")


if __name__ == "__main__":
    main()
