"""
V2' DIAGNOSTIC PILOT: rebuild RQ/DD/IC from first 20 PDF pages (vs V2's 8).

Fork of rebuild_metadata_from_pdf.py with exactly three changes:
  1. PDF page cutoff:  8  -> 20
  2. max chars:        20_000 -> 60_000
  3. user-text cap:    18_000 -> 58_000
  Plus: separate output file, reads paper_ids from a CSV, $15 soft warning.

Runs on the 20-paper diagnostic sample (audit/v2prime_pilot_sample.csv) only.
Does NOT touch audit/regen_from_pdf.json (the V2 baseline stays intact).
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from labnotebook.experiment_logger import ExperimentLogger

ROOT       = Path(__file__).parent.parent.parent
PDF_DIR    = ROOT / "audit/pdfs"
REAL_ABS   = ROOT / "audit/real_abstracts.json"
PAPERS     = ROOT / "experiments/exp_a/papers"
SAMPLE_CSV = ROOT / "audit/v2prime_pilot_sample.csv"
OUT_JSON   = ROOT / "audit/regen_from_pdf_v2prime_pilot.json"

MODEL = "claude-opus-4-7"
MAX_PAGES = 20
MAX_CHARS = 60_000
MAX_USER_TEXT = 58_000
BUDGET_WARN_USD = 15.0

SYSTEM = """You are an empirical-finance econometrician building a
benchmark. Given the actual content of a published paper, write three
concise fields that match a strict schema.

Return ONLY a JSON object — no prose, no fences:
{
  "research_question":      "<2-3 sentences stating the core causal RQ.
                              DO NOT mention the method family name
                              (DID/event study/IV/RDD). Phrase it so an
                              LLM could identify the method from context.>",
  "data_description":       "<~100-150 words: sources, frequency, key
                              variables, sample period, unit of
                              observation. Be specific and factual.>",
  "institutional_context":  "<~100-150 words: the institutional setting
                              or event that enables causal identification
                              (policy change, threshold, instrument, etc.).
                              Do NOT name the method.>"
}

CONSTRAINTS
- Work ONLY from the provided text. Do not invent details.
- If the text covers the full paper, extract facts about the ACTUAL
  setting and data — not a paraphrase of what the abstract hints at.
- research_question and data_description MUST NOT contain the words
  "difference-in-differences", "event study", "instrumental variable",
  "regression discontinuity" (anti-leakage).
- Be faithful: if the paper says "we study X using Y", the
  research_question is about X, not about Y (Y belongs in
  institutional_context).
"""

USER_TEMPLATE = """Paper title: {title}

Authors: {authors}

Source text ({source_type}, {char_count} chars):
{text}

Return the JSON now."""


def extract_pdf_text(pdf_path: Path, max_chars: int = MAX_CHARS) -> str:
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                if i >= MAX_PAGES: break
                txt = page.extract_text() or ""
                parts.append(txt)
                if sum(len(t) for t in parts) > max_chars: break
        return "\n\n".join(parts)[:max_chars]
    except Exception:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
            parts = []
            for i, page in enumerate(reader.pages):
                if i >= MAX_PAGES: break
                parts.append(page.extract_text() or "")
                if sum(len(t) for t in parts) > max_chars: break
            return "\n\n".join(parts)[:max_chars]
        except Exception:
            return ""


def call_opus(title, authors, text, source_type, exp=None, paper_id=""):
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    user = USER_TEMPLATE.format(
        title=title[:200], authors=authors[:200],
        source_type=source_type, char_count=len(text),
        text=text[:MAX_USER_TEXT],
    )
    r = client.messages.create(
        model=MODEL, max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    cost = (r.usage.input_tokens * 15 / 1_000_000
            + r.usage.output_tokens * 75 / 1_000_000)
    if exp:
        exp.log_llm_call(
            model=MODEL,
            input_tokens=r.usage.input_tokens,
            output_tokens=r.usage.output_tokens,
            cost_usd=round(cost, 4),
            paper_id=paper_id,
            source_type=source_type,
            response_summary=r.content[0].text[:200],
        )
    raw = r.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip("` \n")
    return json.loads(raw), cost


def find_paper_file(pid):
    hits = list(PAPERS.glob(f"{pid}_*.json")) + list(PAPERS.glob(f"{pid}.json"))
    return hits[0] if hits else None


def process_one(pid, real_abs_by_id, cache, exp=None):
    if pid in cache and "new_fields" in cache[pid]:
        return cache[pid], 0.0

    pf = find_paper_file(pid)
    if not pf:
        return {"paper_id": pid, "error": "paper_json_not_found"}, 0.0
    paper = json.loads(pf.read_text())
    title = paper.get("title", "")
    authors = paper.get("authors", "")

    pdf_path = PDF_DIR / f"{pid}.pdf"
    text = ""
    source_type = "none"
    if pdf_path.exists():
        text = extract_pdf_text(pdf_path)
        if text: source_type = f"pdf_first_{MAX_PAGES}_pages"
    if not text and pid in real_abs_by_id:
        abs_row = real_abs_by_id[pid]
        if abs_row.get("real_abstract"):
            text = abs_row["real_abstract"]
            source_type = "openalex_abstract"

    if not text:
        return {"paper_id": pid, "error": "no_source_text",
                "source_type": "none"}, 0.0

    if exp:
        exp.log_event("start_paper", paper_id=pid,
                       source_type=source_type, source_chars=len(text))
    try:
        new_fields, cost = call_opus(title, authors, text, source_type,
                                      exp=exp, paper_id=pid)
    except Exception as e:
        if exp: exp.log_event("error", paper_id=pid,
                                reason=f"opus_error: {str(e)[:150]}")
        return {"paper_id": pid, "error": f"opus_error: {str(e)[:200]}",
                "source_type": source_type}, 0.0

    if exp: exp.log_event("finish_paper", paper_id=pid, status="success")
    return {
        "paper_id":     pid,
        "source_type":  source_type,
        "source_chars": len(text),
        "title":        title,
        "new_fields":   new_fields,
        "old_fields": {
            "research_question":     paper.get("research_question", "")[:500],
            "data_description":      paper.get("data_description", "")[:500],
            "institutional_context": paper.get("institutional_context", "")[:500],
        },
    }, cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-csv", default=str(SAMPLE_CSV),
                     help="CSV with paper_id column")
    args = ap.parse_args()

    with open(args.sample_csv) as f:
        pids = [r["paper_id"] for r in csv.DictReader(f)]
    print(f"V2' diagnostic pilot: {len(pids)} papers "
           f"({MAX_PAGES} pages, {MAX_CHARS} chars max)")
    print(f"Budget warning at ${BUDGET_WARN_USD:.0f} — will keep going (soft warn)")

    real_abs_by_id = {r["paper_id"]: r
                       for r in json.loads(REAL_ABS.read_text())}

    exp = ExperimentLogger(
        run_name="pilot_v2prime_20pages",
        script_path=__file__,
        hypothesis=(
            "Expanding Phase 1 source text from 8 -> 20 PDF pages "
            "surfaces methodological signatures (IV names, RD bandwidths, "
            "event dates, DID treatment rules) that are absent in V2. "
            "Diagnostic on 5 per-family x 4 method families = 20 papers."
        ),
        config={
            "primary_model":  MODEL,
            "max_pdf_pages":  MAX_PAGES,
            "max_pdf_chars":  MAX_CHARS,
            "max_user_text":  MAX_USER_TEXT,
            "n_papers":       len(pids),
            "sample_csv":     str(Path(args.sample_csv).relative_to(ROOT)),
            "output_file":    str(OUT_JSON.relative_to(ROOT)),
            "budget_warn_usd": BUDGET_WARN_USD,
        },
    )
    exp.log_prompt("system", SYSTEM)
    exp.log_prompt("user_template", USER_TEMPLATE)

    cache = {}
    if OUT_JSON.exists():
        cache = {r["paper_id"]: r for r in json.loads(OUT_JSON.read_text())}

    total_cost = 0.0
    warned = False
    n_ok = 0
    for i, pid in enumerate(pids, 1):
        row, cost = process_one(pid, real_abs_by_id, cache, exp=exp)
        cache[pid] = row
        total_cost += cost
        if "new_fields" in row:
            n_ok += 1
            print(f"  [{i:>2}/{len(pids)}] OK {pid:<11} "
                   f"({row['source_chars']:>5}c)  "
                   f"this=${cost:.3f}  cum=${total_cost:.2f}")
        else:
            print(f"  [{i:>2}/{len(pids)}] ERR {pid}: "
                   f"{row.get('error','?')[:80]}")
        if (not warned) and total_cost >= BUDGET_WARN_USD:
            print(f"\n  ** BUDGET WARNING: cumulative ${total_cost:.2f} "
                   f">= ${BUDGET_WARN_USD:.2f} ** "
                   f"(continuing; no hard cap)")
            warned = True
        if i % 5 == 0:
            OUT_JSON.write_text(json.dumps(list(cache.values()),
                                           indent=2, ensure_ascii=False))
        time.sleep(0.3)

    OUT_JSON.write_text(json.dumps(list(cache.values()),
                                   indent=2, ensure_ascii=False))
    exp.attach_output("regen_from_pdf_v2prime_pilot.json", OUT_JSON)
    print()
    print(f"Done: {n_ok}/{len(pids)} papers regenerated")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Saved: {OUT_JSON.relative_to(ROOT)}")

    exp.finish(
        status="success" if n_ok >= len(pids) * 0.9 else "partial",
        results={
            "target_papers":  len(pids),
            "regenerated_ok": n_ok,
            "total_cost_usd": round(total_cost, 4),
        },
        interpretation=(
            f"V2' (20-page) diagnostic ran on {n_ok}/{len(pids)} papers "
            f"for ${total_cost:.2f}. Next: compare against V2 baseline in "
            "audit/regen_from_pdf.json via compare_v2_v2prime.py."
        ),
    )


if __name__ == "__main__":
    main()
