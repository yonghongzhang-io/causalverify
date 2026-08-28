"""
V2'' FULL-TEXT REBUILD: rebuild RQ/DD/IC from full PDF body (no 8/20-page cap).

Decision driver: B2 truncation ablation showed method_flip_rate = 32% between
V2 (8-page) and V2' (20-page). User chose Option C: no truncation, give Opus
the full paper body so identification details are never cut off.

Parameter design:
  pages = 50          # effectively unlimited for typical empirical finance papers
  max_chars = 250000  # ~62K tokens; covers very long papers without truncating
                       # body+conclusion. Opus 4.7 has 200K-token context, so
                       # 62K input + 1.5K output + small system = well within.
  user-text cap = 248000

Output: audit/regen_from_pdf_v2primeprime.json (separate from V2 baseline)

Usage:
  python3 src/agents/rebuild_metadata_v2primeprime.py --all       # 261 papers
  python3 src/agents/rebuild_metadata_v2primeprime.py --pilot     # first 5
  python3 src/agents/rebuild_metadata_v2primeprime.py --papers paper_01,paper_05
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from labnotebook.experiment_logger import ExperimentLogger

ROOT       = Path(__file__).parent.parent.parent
PDF_DIR    = ROOT / "audit/pdfs"
REAL_ABS   = ROOT / "audit/real_abstracts.json"
PAPERS     = ROOT / "experiments/exp_a/papers"
OUT_JSON   = ROOT / "audit/regen_from_pdf_v2primeprime.json"

MODEL = "claude-opus-4-7"
MAX_PAGES = 50
MAX_CHARS = 250_000
MAX_USER_TEXT = 248_000
BUDGET_WARN_USD = 200.0
BUDGET_HARD_STOP_USD = 280.0  # ~40% safety margin over target; halt run, save cache

# Anti-leakage: phrases banned in ALL THREE Phase-1 fields (RQ + DD + IC).
# These fields feed both Phase 2 GT voting and Phase 3 Exp A evaluation, so
# any method name in any field would leak the answer.
LEAK_PHRASES = [
    "difference-in-differences", "difference in differences",
    "diff-in-diff", "diff in diff", "two-way fixed effects", "twfe",
    "event study", "event-study", "abnormal return", "abnormal returns",
    "cumulative abnormal return", "cumulative abnormal returns",
    "instrumental variable", "instrumental variables",
    "two-stage least squares", "2sls",
    "regression discontinuity", "rd design",
]
# Acronyms are case-sensitive so ordinary prose like "Did the policy..." is
# not misclassified as a DID leak.
LEAK_ACRONYMS = ["DID", "DiD", "IV", "RDD"]
REQUIRED_FIELDS = ["research_question", "data_description", "institutional_context"]

# False positives for acronym-only checks. These are Roman numerals or named
# data products, not causal-method disclosures.
ACRONYM_CONTEXT_ALLOWLIST = {
    "IV": [
        r"\bPolity\s+IV\b",
        r"\b\d{4}:IV\b",
        r"\b\d{4}QIV\b",
        r"\bQIV\b",
        r"\bWorld\s+War\s+IV\b",  # defensive; not expected in corpus
    ],
}

# Same SYSTEM and USER_TEMPLATE as V2 / V2' for fair comparison
SYSTEM = """You are an empirical-finance econometrician building a
benchmark. Given the actual content of a published paper, write three
concise fields that match a strict schema.

Return ONLY a JSON object — no prose, no fences:
{
  "research_question":      "<2-3 sentences stating the core causal RQ.
                              Do not mention or hint at the method family.
                              Phrase the substantive question only.>",
  "data_description":       "<~100-150 words: sources, frequency, key
                              variables, sample period, unit of
                              observation. Be specific and factual.>",
  "institutional_context":  "<~100-150 words: the institutional setting
                              or event that motivates the comparison.
                              Describe the setting without naming the
                              econometric design.>"
}

CONSTRAINTS
- Work ONLY from the provided text. Do not invent details.
- If the text covers the full paper, extract facts about the ACTUAL
  setting and data — not a paraphrase of what the abstract hints at.
- research_question, data_description, and institutional_context MUST NOT
  contain method names or near-synonyms, including but not limited to:
  "difference-in-differences", "DID", "event study", "abnormal return",
  "instrumental variable", "IV", "2SLS", "regression discontinuity",
  "RDD", or "RD design" (anti-leakage).
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
    """Extract up to MAX_PAGES pages or MAX_CHARS chars, whichever comes first."""
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


class EmptyOpusResponse(Exception):
    """Opus 4.7 returned 200 OK but with content=[] and no text. Caller
    should consider an alternate source (e.g. OpenAlex abstract) rather
    than retry the same input, because this has been reproducible per
    input on a small set of papers (see Stage-4 audit)."""
    def __init__(self, stop_reason: str, cost: float):
        super().__init__(f"empty_content (stop={stop_reason})")
        self.stop_reason = stop_reason
        self.cost = cost


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

    # Defensive check: Opus very occasionally returns content=[] with stop_reason
    # like "end_turn" (paper_07/103/129/187 in run 003). Treat as empty so the
    # caller can fall back instead of crashing on r.content[0].
    has_text = bool(r.content) and bool(getattr(r.content[0], "text", "").strip())
    if exp:
        exp.log_llm_call(
            model=MODEL,
            input_tokens=r.usage.input_tokens,
            output_tokens=r.usage.output_tokens,
            cost_usd=round(cost, 4),
            paper_id=paper_id,
            source_type=source_type,
            response_summary=(r.content[0].text[:200] if has_text else f"<empty_content stop={r.stop_reason}>"),
        )
    if not has_text:
        raise EmptyOpusResponse(stop_reason=str(r.stop_reason), cost=cost)
    raw = r.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip("` \n")
    return json.loads(raw), cost


def check_leakage(fields):
    """Check if any of the three fields contain banned leakage phrases."""
    text_raw = " ".join(str(fields.get(k, "")) for k in REQUIRED_FIELDS)
    text = text_raw.lower()
    for phrase in LEAK_PHRASES:
        if phrase.lower() in text:
            return f"phrase_leak: {phrase}"
    for acronym in LEAK_ACRONYMS:
        for match in re.finditer(rf"\b{re.escape(acronym)}\b", text_raw):
            window = text_raw[max(0, match.start() - 30): match.end() + 30]
            allowed = any(
                re.search(pattern, window)
                for pattern in ACRONYM_CONTEXT_ALLOWLIST.get(acronym, [])
            )
            if not allowed:
                return f"acronym_leak: {acronym}"
    return None


def validate_fields(fields):
    """Return an error string if the model response is not the expected schema."""
    if not isinstance(fields, dict):
        return "schema_error: response is not a JSON object"
    missing = [k for k in REQUIRED_FIELDS if not str(fields.get(k, "")).strip()]
    if missing:
        return "schema_error: missing_or_empty_fields=" + ",".join(missing)
    return None


def report_failures(results):
    """Print list of papers that failed regeneration."""
    failures = [r for r in results if "error" in r or "leakage" in r]
    ok = [r for r in results if "new_fields" in r]
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            pid = f["paper_id"]
            reason = f.get("error", f.get("leakage", "?"))
            print(f"  {pid}: {reason}")
    else:
        print("\nNo failures.")
    print(f"Success rows with new_fields: {len(ok)} / {len(results)}")


def find_paper_file(pid):
    hits = list(PAPERS.glob(f"{pid}_*.json")) + list(PAPERS.glob(f"{pid}.json"))
    return hits[0] if hits else None


def process_one(pid, real_abs_by_id, cache, exp=None):
    # Skip cache hits for both successful regenerations and previously-flagged
    # leakage. Pre-registered rule (see L252-254): leaked papers go to A4
    # strong-deleak, not back through Phase 1, so a rerun must not re-bill.
    if pid in cache and ("new_fields" in cache[pid] or "leakage" in cache[pid]):
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
        if text: source_type = f"pdf_full_text_up_to_{MAX_PAGES}pg_{MAX_CHARS}c"
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
        schema_error = validate_fields(new_fields)
        if schema_error:
            if exp: exp.log_event("schema_error", paper_id=pid, reason=schema_error)
            return {"paper_id": pid, "error": schema_error,
                    "source_type": source_type}, cost
        leak = check_leakage(new_fields)
        if leak:
            # Pre-registered rule: do not retry in Phase 1. Mark the paper and
            # let A4 strong-deleak / later gates decide whether prompt changes
            # or targeted rewrites are needed. This keeps V2'' cost bounded.
            if exp: exp.log_event("leakage_detected", paper_id=pid, reason=leak)
            return {"paper_id": pid, "error": leak,
                    "source_type": source_type, "leakage": leak}, cost
    except EmptyOpusResponse as ee:
        # Reproducible per-input edge case (paper_07/103/129/187 in run 003).
        # Don't retry the same input; fall back to OpenAlex abstract once if
        # available. If we already used the abstract, mark as failed.
        if exp:
            exp.log_event("opus_empty_response", paper_id=pid,
                           reason=str(ee), source_type=source_type)
        if source_type.startswith("pdf_full_text") and pid in real_abs_by_id:
            abs_text = real_abs_by_id[pid].get("real_abstract", "") or ""
            if abs_text.strip():
                if exp:
                    exp.log_event("retry_with_abstract", paper_id=pid)
                try:
                    new_fields, cost2 = call_opus(
                        title, authors, abs_text,
                        "openalex_abstract_after_pdf_empty",
                        exp=exp, paper_id=pid,
                    )
                    total_cost = ee.cost + cost2
                    schema_error = validate_fields(new_fields)
                    if schema_error:
                        if exp: exp.log_event("schema_error", paper_id=pid, reason=schema_error)
                        return {"paper_id": pid, "error": schema_error,
                                "source_type": "openalex_abstract_after_pdf_empty"}, total_cost
                    leak = check_leakage(new_fields)
                    if leak:
                        if exp: exp.log_event("leakage_detected", paper_id=pid, reason=leak)
                        return {"paper_id": pid, "error": leak,
                                "source_type": "openalex_abstract_after_pdf_empty",
                                "leakage": leak}, total_cost
                    if exp: exp.log_event("finish_paper", paper_id=pid,
                                            status="success_via_abstract_fallback")
                    return {
                        "paper_id":     pid,
                        "source_type":  "openalex_abstract_after_pdf_empty",
                        "source_chars": len(abs_text),
                        "title":        title,
                        "new_fields":   new_fields,
                        "old_fields": {
                            "research_question":     paper.get("research_question", "")[:500],
                            "data_description":      paper.get("data_description", "")[:500],
                            "institutional_context": paper.get("institutional_context", "")[:500],
                        },
                    }, total_cost
                except EmptyOpusResponse as ee2:
                    return {"paper_id": pid,
                            "error": f"opus_empty_then_empty_on_abstract: {ee2}",
                            "source_type": source_type}, ee.cost + ee2.cost
                except Exception as e2:
                    return {"paper_id": pid,
                            "error": f"opus_empty_then_{type(e2).__name__}: {str(e2)[:160]}",
                            "source_type": source_type}, ee.cost
        return {"paper_id": pid,
                "error": f"opus_empty_no_abstract_fallback: {ee}",
                "source_type": source_type}, ee.cost
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
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pilot", action="store_true",
                    help="Test on first 5 papers")
    g.add_argument("--all",   action="store_true",
                    help="Full run: all papers with PDF or abstract")
    g.add_argument("--papers", type=str, default=None,
                    help="Comma-separated paper_ids")
    args = ap.parse_args()

    real_abs_by_id = {r["paper_id"]: r
                       for r in json.loads(REAL_ABS.read_text())}

    if args.pilot:
        pdf_pids = sorted([p.stem for p in PDF_DIR.glob("paper_*.pdf")],
                           key=lambda s: int(s.split("_")[1]))[:5]
        pids = pdf_pids
        print(f"Pilot: {len(pids)} papers")
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

    print(f"Settings: max_pages={MAX_PAGES}, max_chars={MAX_CHARS}")
    print(f"Budget warn at ${BUDGET_WARN_USD:.0f} (soft)")
    print(f"Budget hard stop at ${BUDGET_HARD_STOP_USD:.0f}")

    exp = ExperimentLogger(
        run_name="v2primeprime_full_text_rebuild",
        script_path=__file__,
        hypothesis=(
            "Removing the 8/20-page truncation cap and feeding full paper body "
            "(up to 50 pages, 250K chars) to Opus 4.7 produces RQ/DD/IC fields "
            "that capture identification strategy details that V2 (8pg) and "
            f"V2' (20pg) cut off. B2 ablation showed 32% method-flip rate "
            "between V2 and V2', justifying full-text input."
        ),
        config={
            "primary_model":     MODEL,
            "max_pages":         MAX_PAGES,
            "max_chars":         MAX_CHARS,
            "max_user_text":     MAX_USER_TEXT,
            "n_target_papers":   len(pids),
            "output_file":       str(OUT_JSON.relative_to(ROOT)),
            "budget_warn_usd":   BUDGET_WARN_USD,
            "budget_hard_stop_usd": BUDGET_HARD_STOP_USD,
            "trigger_evidence":  "audit/b2_ablation_summary.md",
        },
    )
    exp.log_prompt("system", SYSTEM)
    exp.log_prompt("user_template", USER_TEMPLATE)

    cache = {}
    if OUT_JSON.exists():
        cache = {r["paper_id"]: r for r in json.loads(OUT_JSON.read_text())}

    results = list(cache.values())
    n_ok = 0
    n_pdf_source = 0
    n_abstract_source = 0
    total_cost = 0.0
    warned = False
    for i, pid in enumerate(pids, 1):
        row, cost = process_one(pid, real_abs_by_id, cache, exp=exp)
        cache[pid] = row
        total_cost += cost
        results = [r for r in results if r["paper_id"] != pid] + [row]
        if "new_fields" in row:
            n_ok += 1
            st = row.get("source_type", "?")
            if st.startswith("pdf_full"):  n_pdf_source += 1
            elif st == "openalex_abstract": n_abstract_source += 1
            print(f"  [{i:>3}/{len(pids)}] OK {pid:<11} "
                   f"({row['source_chars']:>6}c)  this=${cost:.3f}  cum=${total_cost:.2f}")
        else:
            print(f"  [{i:>3}/{len(pids)}] ERR {pid}: "
                   f"{row.get('error','?')[:80]}")
        if (not warned) and total_cost >= BUDGET_WARN_USD:
            print(f"\n  ** BUDGET WARNING: cumulative ${total_cost:.2f} "
                   f">= ${BUDGET_WARN_USD:.2f} ** (continuing)")
            warned = True
        if total_cost >= BUDGET_HARD_STOP_USD:
            print(f"\n  ** HARD BUDGET STOP: cumulative ${total_cost:.2f} "
                   f">= ${BUDGET_HARD_STOP_USD:.2f} **")
            break
        if i % 10 == 0:
            OUT_JSON.write_text(json.dumps(list(cache.values()),
                                           indent=2, ensure_ascii=False))
        time.sleep(0.3)

    OUT_JSON.write_text(json.dumps(list(cache.values()),
                                   indent=2, ensure_ascii=False))
    exp.attach_output("regen_from_pdf_v2primeprime.json", OUT_JSON)
    print()
    print(f"Regenerated {n_ok} / {len(pids)} papers")
    print(f"  from PDF (full text): {n_pdf_source}")
    print(f"  from abstract:        {n_abstract_source}")
    print(f"  total cost:           ${total_cost:.2f}")
    print(f"Saved to: {OUT_JSON.relative_to(ROOT)}")

    report_failures(results)

    exp.finish(
        status="success" if n_ok >= len(pids) * 0.9 else "partial",
        results={
            "target_papers":     len(pids),
            "regenerated_ok":    n_ok,
            "from_pdf_source":   n_pdf_source,
            "from_abstract":     n_abstract_source,
            "total_cost_usd":    round(total_cost, 4),
        },
        interpretation=(
            f"V2'' full-text rebuild on {n_ok}/{len(pids)} papers for "
            f"${total_cost:.2f}. Compare against audit/regen_from_pdf.json "
            "(V2 baseline, 8-page) and audit/regen_from_pdf_v2prime_pilot.json "
            "(V2' 20-page). Downstream: A4 deleak rerun, 4-LLM GT revote, "
            "Exp A 7-LLM rerun all required (RESTRUCTURE_PLAN Steps 5-9)."
        ),
    )


if __name__ == "__main__":
    main()
