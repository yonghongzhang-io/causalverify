"""
Ground-Truth Cross-Validator — sanity check on Exp A method_family and
conclusion_direction fields.

The original GT for these two fields was extracted by GPT-4o from paper
abstracts at ingestion time. This script re-extracts them with a DIFFERENT
LLM (Claude Opus) using a stricter prompt, then compares.

Scope:
  --sample 50      re-extract only the 50 papers in the human-rating sample
                   (cheap: ~$0.50, 5 min)
  --all            re-extract all 262 Exp A papers (~$3, 30 min)
  --papers IDS     re-extract a specific list (e.g. paper_14,paper_61)

Output:
  audit/gt_cross_validation.json        per-paper: original / independent / agree?
  audit/gt_cross_validation_summary.md  aggregate disagreement rate by method

If the independent extractor disagrees with the original GT on > 10% of
method_family labels, the paper's L1 scoring is on shaky ground and we
need human adjudication on the disagreeing subset.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

ROOT       = Path(__file__).parent.parent.parent
PAPERS_DIR = ROOT / "experiments/exp_a/papers"
SAMPLE_CSV = ROOT / "human_rating/sampling/sample_50.csv"
OUT_JSON   = ROOT / "audit/gt_cross_validation.json"
OUT_MD     = ROOT / "audit/gt_cross_validation_summary.md"

# Use Opus 4.6 — a different provider/model family than GPT-4o used originally
# so the comparison is maximally independent.
MODEL = "claude-opus-4-6"

SYSTEM = (
    "You are an expert empirical-finance econometrician. Given a paper's "
    "title, research question, and abstract, classify its causal-inference "
    "method and direction of main finding. Respond with ONLY a JSON object "
    "— no prose, no markdown fences.\n\n"
    "Schema:\n"
    "{\n"
    '  "method_family": "DID" | "EVENT_STUDY" | "IV" | "RDD" | "OTHER",\n'
    '  "direction":     "positive" | "negative" | "mixed" | "unclear",\n'
    '  "confidence":    "high" | "medium" | "low"\n'
    "}\n\n"
    "Definitions:\n"
    "- DID: difference-in-differences comparing change in treated vs "
    "  untreated groups around a policy/event.\n"
    "- EVENT_STUDY: abnormal returns / outcomes in a short window around "
    "  an identifiable event date (e.g. CARs). Event-study plots INSIDE a "
    "  DID are still DID, not Event Study.\n"
    "- IV: instrumental variable / 2SLS with a stated instrument.\n"
    "- RDD: regression discontinuity with a running-variable cutoff.\n"
    "- OTHER: structural, synthetic control, matching-only, etc.\n"
    "If the method is genuinely ambiguous from the abstract, pick your "
    "best guess and mark confidence=low."
)

USER_TEMPLATE = (
    "Title: {title}\n\n"
    "Research question: {rq}\n\n"
    "Abstract / institutional context: {abstract}\n\n"
    "Classify per the schema."
)


def call_opus(paper: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = USER_TEMPLATE.format(
        title=paper.get("title", ""),
        rq=paper.get("research_question", ""),
        abstract=paper.get("institutional_context", "")[:2000],
    )
    r = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=SYSTEM,
        messages=[{"role": "user", "content": msg}],
    )
    raw = r.content[0].text.strip()
    # strip any ```json wrappers if model disobeyed
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip("` \n")
    return json.loads(raw)


def find_paper_file(pid: str) -> Path | None:
    hits = list(PAPERS_DIR.glob(f"{pid}_*.json")) + \
           list(PAPERS_DIR.glob(f"{pid}.json"))
    return hits[0] if hits else None


def load_paper_ids(mode: str, explicit: str | None) -> list[str]:
    if mode == "sample":
        import pandas as pd
        df = pd.read_csv(SAMPLE_CSV)
        return list(df["paper_id"])
    if mode == "all":
        return sorted([p.stem.split("_")[0] + "_" + p.stem.split("_")[1]
                       for p in PAPERS_DIR.glob("paper_*.json")])
    if mode == "explicit":
        return [x.strip() for x in explicit.split(",") if x.strip()]
    raise ValueError(mode)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sample", action="store_true",
                   help="Cross-validate the 50 papers in the human-rating sample")
    g.add_argument("--all",    action="store_true",
                   help="Cross-validate all 262 Exp A papers")
    g.add_argument("--papers", type=str, default=None,
                   help="Comma-separated paper IDs (e.g. paper_14,paper_61)")
    ap.add_argument("--force", action="store_true",
                    help="Re-query even if cached result exists")
    args = ap.parse_args()

    mode = "sample" if args.sample else ("all" if args.all else "explicit")
    paper_ids = load_paper_ids(mode, args.papers)
    print(f"Cross-validating {len(paper_ids)} paper(s) with {MODEL}...")

    # Load cache if it exists (incremental re-run friendly)
    cache = {}
    if OUT_JSON.exists() and not args.force:
        cache = {r["paper_id"]: r for r in json.loads(OUT_JSON.read_text())}
        print(f"  loaded {len(cache)} cached results")

    results = []
    for i, pid in enumerate(paper_ids, 1):
        if pid in cache and not args.force:
            results.append(cache[pid])
            continue

        pf = find_paper_file(pid)
        if pf is None:
            print(f"  [{i}/{len(paper_ids)}] {pid}: MISSING FILE")
            continue

        paper = json.loads(pf.read_text())
        orig_method    = paper.get("method_family")
        orig_direction = paper.get("ground_truth", {}).get("conclusion_direction")

        try:
            indep = call_opus(paper)
        except Exception as e:
            print(f"  [{i}/{len(paper_ids)}] {pid}: ERROR {e}")
            results.append({
                "paper_id":        pid,
                "orig_method":     orig_method,
                "orig_direction":  orig_direction,
                "error":           str(e),
            })
            continue

        # Normalize
        indep_method = indep.get("method_family", "").upper().replace(" ", "_")
        indep_dir    = indep.get("direction", "").lower()

        method_agree    = (indep_method == orig_method)
        direction_agree = (indep_dir    == orig_direction)

        row = {
            "paper_id":         pid,
            "orig_method":      orig_method,
            "indep_method":     indep_method,
            "method_agree":     method_agree,
            "orig_direction":   orig_direction,
            "indep_direction":  indep_dir,
            "direction_agree":  direction_agree,
            "indep_confidence": indep.get("confidence"),
        }
        results.append(row)
        mark_m = "✓" if method_agree    else "✗"
        mark_d = "✓" if direction_agree else "✗"
        print(f"  [{i}/{len(paper_ids)}] {pid} | method {mark_m} "
              f"({orig_method}→{indep_method}) | dir {mark_d} "
              f"({orig_direction}→{indep_dir})")

        # Flush cache every 10 calls
        if i % 10 == 0:
            OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
            OUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        time.sleep(0.3)

    # Final save
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    # Summary
    n        = len(results)
    errors   = sum(1 for r in results if "error" in r)
    usable   = n - errors
    m_ok     = sum(1 for r in results if r.get("method_agree"))
    d_ok     = sum(1 for r in results if r.get("direction_agree"))

    # Per-method disagreement
    from collections import defaultdict
    by_method = defaultdict(lambda: {"total": 0, "agree": 0})
    for r in results:
        if "error" in r: continue
        m = r["orig_method"] or "?"
        by_method[m]["total"] += 1
        if r["method_agree"]: by_method[m]["agree"] += 1

    md = [
        "# Ground-Truth Cross-Validation Summary",
        "",
        f"**Independent extractor**: {MODEL}",
        f"**Papers checked**: {n} (errors: {errors}, usable: {usable})",
        "",
        "## Headline agreement",
        "",
        f"- Method family:       {m_ok}/{usable} = **{m_ok/usable*100:.1f}%**" if usable else "- no data",
        f"- Conclusion direction: {d_ok}/{usable} = **{d_ok/usable*100:.1f}%**" if usable else "",
        "",
        "## Per-method method-family agreement",
        "",
        "| Method (as original GT) | Agree | Total | Rate |",
        "|---|---:|---:|---:|",
    ]
    for m, v in sorted(by_method.items()):
        rate = v["agree"] / v["total"] if v["total"] else 0
        md.append(f"| {m} | {v['agree']} | {v['total']} | {rate*100:.0f}% |")

    md += [
        "",
        "## Interpretation",
        "",
        "- **Method agreement ≥ 90%**: GT is robust. Any remaining disagreements "
        "are probably honest ambiguities (e.g., DID-with-event-study-plots).",
        "- **Method agreement 80-90%**: GT has some noise. Consider "
        "human-adjudicating the disagreeing rows before final submission.",
        "- **Method agreement < 80%**: GT is unreliable. Either re-extract "
        "with a better prompt, or escalate to human labeling for the full set.",
        "",
        "## Disagreeing papers (for manual inspection)",
        "",
        "| paper_id | orig method | indep method | orig dir | indep dir |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        if "error" in r: continue
        if not r["method_agree"] or not r["direction_agree"]:
            md.append(
                f"| {r['paper_id']} | {r['orig_method']} | {r['indep_method']} | "
                f"{r['orig_direction']} | {r['indep_direction']} |")

    OUT_MD.write_text("\n".join(md) + "\n")

    print()
    print(f"Results: {OUT_JSON}")
    print(f"Summary: {OUT_MD}")
    print()
    print(f"Method agreement:    {m_ok}/{usable} = {m_ok/usable*100:.1f}%")
    print(f"Direction agreement: {d_ok}/{usable} = {d_ok/usable*100:.1f}%")


if __name__ == "__main__":
    main()
