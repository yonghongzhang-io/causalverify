"""
Verify fidelity of regenerated institutional_context vs real abstract.
Mirrors check_abstract_fidelity.py but reads NEW fields from a regen
JSON instead of the paper JSON.

Usage:
  # V2 baseline (default)
  python3 src/agents/check_new_fidelity.py

  # V2'' pilot smoke test (5 papers)
  python3 src/agents/check_new_fidelity.py \
      --input audit/regen_from_pdf_v2primeprime.json \
      --out   audit/new_fidelity_v2primeprime_pilot.json \
      --papers paper_01,paper_02,paper_03,paper_04,paper_05
"""

import argparse
import json
import os
import time
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

ROOT       = Path(__file__).parent.parent.parent
REAL_ABS   = ROOT / "audit/real_abstracts.json"
REGEN      = ROOT / "audit/regen_from_pdf.json"
OUT_JSON   = ROOT / "audit/new_fidelity.json"

MODEL = "claude-opus-4-7"

SYSTEM = """You are evaluating whether a benchmark dataset's
institutional_context faithfully represents the abstract of a paper.

Return ONLY JSON:
{"fidelity": "faithful"|"partial"|"diverges",
 "key_discrepancies": [<1-line discrepancy>, ...],
 "confidence": "high"|"medium"|"low"}

- "faithful": institutional_context accurately represents the paper's
  setting, method (without naming it), and main finding as stated in
  the abstract.
- "partial": general topic is right but missing key elements or has
  minor inaccuracies.
- "diverges": materially wrong subject matter, wrong setup, or
  fabricated details not in the abstract.
"""

USER_TEMPLATE = """Paper title: {title}

Real abstract (from OpenAlex):
{real_abstract}

institutional_context (under evaluation):
{institutional}

Return the JSON now."""


def call_opus(title, real_abs, institutional):
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    user = USER_TEMPLATE.format(
        title=title[:200],
        real_abstract=real_abs[:2500],
        institutional=institutional[:2500],
    )
    r = client.messages.create(
        model=MODEL, max_tokens=600, system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    raw = r.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip("` \n")
    return json.loads(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=REGEN,
                    help="Regen JSON to evaluate (default: V2 baseline)")
    ap.add_argument("--out", type=Path, default=OUT_JSON,
                    help="Output JSON path (default: audit/new_fidelity.json)")
    ap.add_argument("--papers", type=str, default=None,
                    help="Comma-separated paper_ids; omit to evaluate all")
    args = ap.parse_args()

    real_by_id = {r["paper_id"]: r
                   for r in json.loads(REAL_ABS.read_text())
                   if r.get("real_abstract")}
    regen_by_id = {r["paper_id"]: r
                    for r in json.loads(args.input.read_text())
                    if "new_fields" in r}

    # Only evaluate papers that have both a real abstract AND new fields
    pids = [pid for pid in regen_by_id if pid in real_by_id]
    if args.papers:
        wanted = {p.strip() for p in args.papers.split(",") if p.strip()}
        pids = [p for p in pids if p in wanted]
    print(f"Input:  {args.input}")
    print(f"Output: {args.out}")
    print(f"Evaluating {len(pids)} papers with both real_abstract + new_fields")

    results = []
    for i, pid in enumerate(pids, 1):
        real_abs = real_by_id[pid]["real_abstract"]
        new_ic   = regen_by_id[pid]["new_fields"].get("institutional_context", "")
        title    = regen_by_id[pid].get("title", "")

        try:
            v = call_opus(title, real_abs, new_ic)
            row = {"paper_id": pid, "fidelity": v.get("fidelity"),
                   "key_discrepancies": v.get("key_discrepancies", []),
                   "source_type": regen_by_id[pid].get("source_type")}
        except Exception as e:
            row = {"paper_id": pid, "fidelity": "error",
                   "error": str(e)[:200]}
        results.append(row)
        m = {"faithful":"✓","partial":"~","diverges":"✗"}.get(row["fidelity"],"?")
        print(f"  [{i}/{len(pids)}] {pid}: {m} {row.get('fidelity','?')}")
        time.sleep(0.2)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    c = Counter(r["fidelity"] for r in results)
    n_judged = c.get("faithful",0) + c.get("partial",0) + c.get("diverges",0)
    if n_judged:
        rate = c.get("faithful",0) / n_judged * 100
        print()
        print(f"NEW fidelity: {c.get('faithful',0)} faithful, "
              f"{c.get('partial',0)} partial, {c.get('diverges',0)} diverges")
        print(f"Faithful rate: {rate:.1f}%  (OLD was 48.8%)")
        if rate >= 85: print("→ ✅ Safe to scale to full run")
        elif rate >= 70: print("→ 🟡 Usable but investigate diverges")
        else: print("→ 🔴 Quality degraded, investigate")


if __name__ == "__main__":
    main()
