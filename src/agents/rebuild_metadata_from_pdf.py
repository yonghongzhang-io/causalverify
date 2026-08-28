"""
Rebuild RQ/DD/IC fields from paper PDFs (highest-fidelity ground truth).

For each paper with a local PDF:
  1. Extract text from PDF (first ~5 pages, usually covers abstract + intro)
  2. Feed to Claude Opus 4.7 with strict schema prompt
  3. Opus outputs the 3 fields, grounded in actual paper content
  4. Save to audit/regen_from_pdf.json (before writing back to paper JSON)

For papers without PDF but with OpenAlex real_abstract:
  Fall back to abstract-based regeneration (same schema, smaller input).

Usage:
  # Pilot on 10 papers (5 PDF + 5 abstract)
  python3 src/agents/rebuild_metadata_from_pdf.py --pilot

  # Full: all 214 papers with PDF or abstract
  python3 src/agents/rebuild_metadata_from_pdf.py --all

  # Specific list
  python3 src/agents/rebuild_metadata_from_pdf.py --papers paper_01,paper_04
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

# Lab notebook logger
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from labnotebook.experiment_logger import ExperimentLogger

ROOT       = Path(__file__).parent.parent.parent
PDF_DIR    = ROOT / "audit/pdfs"
REAL_ABS   = ROOT / "audit/real_abstracts.json"
PAPERS     = ROOT / "experiments/exp_a/papers"
OUT_JSON   = ROOT / "audit/regen_from_pdf.json"

MODEL = "claude-opus-4-7"

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


def extract_pdf_text(pdf_path: Path, max_chars: int = 20000) -> str:
    """Extract text from first few pages of a PDF."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                if i >= 8: break  # first 8 pages usually cover abstract+intro+data
                txt = page.extract_text() or ""
                text_parts.append(txt)
                if sum(len(t) for t in text_parts) > max_chars: break
        return "\n\n".join(text_parts)[:max_chars]
    except Exception as e:
        # Fallback to pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
            text_parts = []
            for i, page in enumerate(reader.pages):
                if i >= 8: break
                text_parts.append(page.extract_text() or "")
                if sum(len(t) for t in text_parts) > max_chars: break
            return "\n\n".join(text_parts)[:max_chars]
        except Exception as e2:
            return ""


def call_opus(title: str, authors: str, text: str, source_type: str,
              exp: Optional[ExperimentLogger] = None,
              paper_id: str = "") -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    user = USER_TEMPLATE.format(
        title=title[:200], authors=authors[:200],
        source_type=source_type, char_count=len(text),
        text=text[:18000],
    )
    r = client.messages.create(
        model=MODEL, max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    # Log token usage for provenance
    if exp:
        # Opus 4.7 pricing: $15/M input + $75/M output
        cost = (r.usage.input_tokens * 15 / 1_000_000
                + r.usage.output_tokens * 75 / 1_000_000)
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
    return json.loads(raw)


def find_paper_file(pid: str) -> Optional[Path]:
    hits = list(PAPERS.glob(f"{pid}_*.json")) + list(PAPERS.glob(f"{pid}.json"))
    return hits[0] if hits else None


def process_one(pid: str, real_abs_by_id: dict, cache: dict,
                 exp: Optional[ExperimentLogger] = None) -> dict:
    if pid in cache and "new_fields" in cache[pid]:
        return cache[pid]

    pf = find_paper_file(pid)
    if not pf:
        if exp: exp.log_event("skip", paper_id=pid, reason="paper_json_not_found")
        return {"paper_id": pid, "error": "paper_json_not_found"}
    paper = json.loads(pf.read_text())
    title = paper.get("title", "")
    authors = paper.get("authors", "")

    pdf_path = PDF_DIR / f"{pid}.pdf"
    text = ""
    source_type = "none"
    if pdf_path.exists():
        text = extract_pdf_text(pdf_path)
        if text:
            source_type = "pdf_first_8_pages"
    if not text and pid in real_abs_by_id:
        abs_row = real_abs_by_id[pid]
        if abs_row.get("real_abstract"):
            text = abs_row["real_abstract"]
            source_type = "openalex_abstract"

    if not text:
        if exp: exp.log_event("skip", paper_id=pid, reason="no_source_text")
        return {"paper_id": pid, "error": "no_source_text",
                "source_type": "none"}

    if exp:
        exp.log_event("start_paper", paper_id=pid,
                       source_type=source_type, source_chars=len(text))
    try:
        new_fields = call_opus(title, authors, text, source_type,
                                exp=exp, paper_id=pid)
    except Exception as e:
        if exp: exp.log_event("error", paper_id=pid,
                                reason=f"opus_error: {str(e)[:150]}")
        return {"paper_id": pid, "error": f"opus_error: {str(e)[:200]}",
                "source_type": source_type}

    if exp:
        exp.log_event("finish_paper", paper_id=pid, status="success")

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
    }


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pilot", action="store_true",
                    help="Test on 10 papers (5 PDF + 5 abstract)")
    g.add_argument("--all",   action="store_true",
                    help="Full run: all papers with PDF or abstract")
    g.add_argument("--papers", type=str, default=None,
                    help="Comma-separated paper_ids")
    args = ap.parse_args()

    real_abs_by_id = {r["paper_id"]: r
                       for r in json.loads(REAL_ABS.read_text())}

    # Pick target list
    if args.pilot:
        # 5 with PDF, 5 with abstract only
        pdf_pids = sorted([p.stem for p in PDF_DIR.glob("paper_*.pdf")],
                           key=lambda s: int(s.split("_")[1]))[:5]
        abs_only = [pid for pid, r in real_abs_by_id.items()
                     if r.get("real_abstract")
                     and not (PDF_DIR / f"{pid}.pdf").exists()][:5]
        pids = pdf_pids + abs_only
        print(f"Pilot: {len(pids)} papers "
              f"({len(pdf_pids)} PDF + {len(abs_only)} abstract-only)")
    elif args.all:
        candidate = set()
        candidate.update(p.stem for p in PDF_DIR.glob("paper_*.pdf"))
        candidate.update(pid for pid, r in real_abs_by_id.items()
                         if r.get("real_abstract"))
        pids = sorted(candidate, key=lambda s: int(s.split("_")[1]))
        print(f"Full run: {len(pids)} papers total")
    else:
        pids = [p.strip() for p in args.papers.split(",") if p.strip()]
        print(f"Specified: {len(pids)} papers")

    # Initialize lab notebook logger
    exp = ExperimentLogger(
        run_name="pdf_regen_full_260",
        script_path=__file__,
        hypothesis=(
            "Source-grounded regeneration (PDF first 8 pages, falling back "
            "to OpenAlex abstract) with Opus 4.7 produces faithful RQ/DD/IC "
            "for ≥95% of papers — materially better than the original "
            "GPT-4o 48.8% faithful rate."
        ),
        config={
            "primary_model":     MODEL,
            "source_preference": "pdf_first_8_pages > openalex_abstract",
            "n_target_papers":   len(pids),
            "max_pdf_chars":     20000,
            "max_abstract_chars": 2500,
            "output_file":       str(OUT_JSON.relative_to(
                Path(__file__).parent.parent.parent)),
        },
    )
    exp.log_prompt("system", SYSTEM)
    exp.log_prompt("user_template", USER_TEMPLATE)

    # Load cache
    cache = {}
    if OUT_JSON.exists():
        cache = {r["paper_id"]: r for r in json.loads(OUT_JSON.read_text())}

    results = list(cache.values())
    n_ok = 0
    n_pdf_source = 0
    n_abstract_source = 0
    for i, pid in enumerate(pids, 1):
        row = process_one(pid, real_abs_by_id, cache, exp=exp)
        cache[pid] = row
        results = [r for r in results if r["paper_id"] != pid] + [row]
        if "new_fields" in row:
            n_ok += 1
            st = row.get("source_type", "?")
            if st == "pdf_first_8_pages":   n_pdf_source += 1
            elif st == "openalex_abstract": n_abstract_source += 1
            print(f"  [{i}/{len(pids)}] ✓ {pid} ({st}, {row['source_chars']} chars)")
        else:
            print(f"  [{i}/{len(pids)}] ✗ {pid}: "
                  f"{row.get('error','?')[:80]}")
        if i % 5 == 0:
            OUT_JSON.write_text(json.dumps(list(cache.values()),
                                           indent=2, ensure_ascii=False))
        time.sleep(0.3)

    OUT_JSON.write_text(json.dumps(list(cache.values()),
                                   indent=2, ensure_ascii=False))
    exp.attach_output("regen_from_pdf.json", OUT_JSON)
    print()
    print(f"Regenerated {n_ok} / {len(pids)} papers")
    print(f"  from PDF:      {n_pdf_source}")
    print(f"  from abstract: {n_abstract_source}")
    print(f"Saved to: {OUT_JSON}")

    # Close logger with summary
    exp.finish(
        status="success" if n_ok >= len(pids) * 0.9 else "partial",
        results={
            "target_papers":            len(pids),
            "regenerated_ok":           n_ok,
            "from_pdf_source":          n_pdf_source,
            "from_abstract_source":     n_abstract_source,
            "failed":                   len(pids) - n_ok,
        },
        interpretation=(
            f"Source-grounded regeneration processed {n_ok}/{len(pids)} "
            f"papers ({n_pdf_source} from PDF text, {n_abstract_source} "
            "from OpenAlex abstract). Pilot validation (run 006) showed "
            "100% faithful rate; full-run fidelity check pending. "
            f"Per-paper provenance and token cost in this run's "
            "llm_calls.jsonl."
        ),
    )

    # Show sample if pilot
    if args.pilot and n_ok:
        print("\n── Sample new RQ ──")
        for r in results[-3:]:
            if "new_fields" in r:
                print(f"\n{r['paper_id']} ({r['source_type']}):")
                print(f"  RQ (new):  {r['new_fields'].get('research_question','')[:250]}")
                print(f"  RQ (orig): {r['old_fields'].get('research_question','')[:250]}")


if __name__ == "__main__":
    main()
