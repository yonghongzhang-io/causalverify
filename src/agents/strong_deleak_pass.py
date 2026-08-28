"""
A4 · Strong de-leakage LLM review agent.

Takes each paper's Phase 1 synthesis (research_question, data_description,
institutional_context) and runs an LLM review pass that rewrites any
method-revealing phrases into neutral language, guided by the 117-cue
taxonomy in src/deleakage/cue_taxonomy.json.

This is a genuine LLM agent (not a deterministic script): for each paper
the LLM decides WHICH cues actually leak method (vs. incidental matches
like "data-collection instrument" being flagged as an IV cue), proposes
rewrites that preserve research-question content, and self-verifies its
output.

Pipeline (per paper):
  1. Regex pre-scan: find all cue matches across the 5 method families
  2. If no matches ^ no subtle mechanism cues → passthrough (copy original)
  3. If matches → call Opus 4.7 with:
       - original synthesis fields
       - list of matched cues (as hints, not mandates)
       - few-shot neutral rewrite examples from taxonomy
       - schema-constrained output
  4. Post-check: verify the rewrite does NOT contain any HARD cues
  5. Save to audit/regen_strong_deleak.json

Outputs:
  audit/regen_strong_deleak.json           per-paper new fields + provenance
  audit/deleakage_audit.csv                cue retention stats
  experiments_log/runs/YYYY-MM-DD/NNN__a4_strong_deleak_pass/

Usage:
  python3 src/agents/strong_deleak_pass.py --pilot        # 10 papers
  python3 src/agents/strong_deleak_pass.py --all          # 261 papers
  python3 src/agents/strong_deleak_pass.py --papers paper_05,paper_07
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from labnotebook.experiment_logger import ExperimentLogger

# ─── paths
REGEN_IN       = ROOT / "audit/regen_from_pdf.json"
TAXONOMY_PATH  = ROOT / "src/deleakage/cue_taxonomy.json"
OUT_JSON       = ROOT / "audit/regen_strong_deleak.json"
OUT_AUDIT_CSV  = ROOT / "audit/deleakage_audit.csv"

# ─── config
MODEL = "claude-opus-4-7"
FIELDS_TO_REWRITE = ("research_question", "data_description",
                     "institutional_context")
# Which cue categories trigger LLM review? "hard" only — soft cues are
# flagged but reviewed only when a hard cue is also present, to avoid
# over-scrubbing neutral text.
TRIGGER_CATEGORIES = ("design_cues_hard",)


SYSTEM_PROMPT = """You are a benchmark-construction editor. You rewrite
three fields of a paper description so that a language model reading
them could not easily identify the paper's causal-identification method
from surface wording, while preserving the substantive research
question, data, and institutional context.

PROHIBITED TERMS (never appear in output for any field):
- "difference-in-differences", "DID", "DiD"
- "event study", "event-study methodology", "abnormal returns", "CARs"
- "instrumental variable", "instrument", "2SLS", "first stage",
  "exclusion restriction"
- "regression discontinuity", "RDD", "running variable", "cutoff",
  "threshold", "bandwidth"
- "parallel trends", "two-way fixed effects", "TWFE"

NEUTRAL LANGUAGE POLICY
- Describe the identifying shock as a real-world event (e.g., "a policy
  change", "a staggered regulatory rollout", "sharp eligibility rules")
  without naming the estimator.
- Describe data as what was measured, not how it will be analyzed.
- The research_question should sound like a question a reader with no
  econometrics training would ask.

REWRITING RULES
- Keep substantive content: sample period, country, treatment domain,
  outcome variable, unit of observation.
- Keep sentence count roughly similar (do not compress or expand
  dramatically).
- When in doubt, err on the side of more neutral / more vague about
  method — NEVER more specific.

You will be given the original fields plus a list of detected cues that
may reveal the method. Treat the cue list as hints, not commands;
sometimes a flagged phrase is contextual (e.g., "data-collection
instrument" is not the same as an instrumental variable Z) and should
be left untouched.

Respond with strict JSON only, no prose, no code fences:

{
  "research_question":      "<rewritten or copied>",
  "data_description":       "<rewritten or copied>",
  "institutional_context":  "<rewritten or copied>",
  "cues_addressed":         ["<cue>", ...],
  "cues_left_unchanged":    [{"cue": "<cue>", "reason": "<why>"}],
  "method_revealed_after":  false
}

`method_revealed_after` is your self-check: after your rewrite, could a
careful reader still identify the method family from the three fields
together? If yes, set true and try harder."""


USER_TEMPLATE = """Paper title: {title}

Original Phase 1 synthesis:

[research_question]
{rq}

[data_description]
{dd}

[institutional_context]
{ic}

Detected method cues (method_family — matched phrase):
{cue_list}

Few-shot neutral-rewrite examples (from the curated library):
{examples}

Rewrite the three fields per the system prompt. Return JSON only."""


# ═══════════════════════════════════════════════════════════════
#  Taxonomy + scanning
# ═══════════════════════════════════════════════════════════════

def load_taxonomy() -> dict:
    return json.loads(TAXONOMY_PATH.read_text())


def compile_cue_regexes(taxonomy: dict) -> list[tuple[str, str, str, re.Pattern]]:
    """Return list of (method, category, cue_phrase, compiled_regex)."""
    out = []
    for method, cats in taxonomy.items():
        if not isinstance(cats, dict): continue
        for cat_name in ("design_cues_hard", "design_cues_soft"):
            for phrase in cats.get(cat_name, []):
                # Word-boundary-ish match, case-insensitive
                pattern = re.compile(r'\b' + re.escape(phrase) + r'\b',
                                      re.IGNORECASE)
                out.append((method, cat_name, phrase, pattern))
    return out


def scan_text(text: str,
              cue_regexes: list[tuple[str, str, str, re.Pattern]]
              ) -> list[dict]:
    """Return list of {method, category, phrase, match_count} for all hits."""
    hits = []
    for method, cat, phrase, pat in cue_regexes:
        matches = pat.findall(text or "")
        if matches:
            hits.append({
                "method":      method,
                "category":    cat,
                "phrase":      phrase,
                "match_count": len(matches),
            })
    return hits


def should_rewrite(scan_hits: list[dict]) -> bool:
    """Policy: rewrite if any HARD cue fired; soft alone is not enough."""
    return any(h["category"] == "design_cues_hard" for h in scan_hits)


# ═══════════════════════════════════════════════════════════════
#  Prompt assembly
# ═══════════════════════════════════════════════════════════════

def _cue_block(scan_hits_by_field: dict[str, list[dict]]) -> str:
    lines = []
    for field, hits in scan_hits_by_field.items():
        if not hits: continue
        lines.append(f"  [{field}]")
        for h in hits[:12]:
            lines.append(f"    - {h['method']} / {h['category']}: \"{h['phrase']}\" "
                         f"(×{h['match_count']})")
    return "\n".join(lines) if lines else "  (none)"


def _examples_block(taxonomy: dict, max_examples: int = 3) -> str:
    ex = taxonomy.get("neutral_rewrites_library", {}).get("examples", [])[:max_examples]
    out = []
    for i, e in enumerate(ex, 1):
        out.append(f"  Example {i}:")
        out.append(f"    LEAKING: {e['bad']}")
        out.append(f"    NEUTRAL: {e['neutral']}")
    return "\n".join(out)


def build_user_prompt(paper: dict, scan_hits_by_field: dict, taxonomy: dict) -> str:
    return USER_TEMPLATE.format(
        title=paper.get("title", "")[:200],
        rq=paper["new_fields"].get("research_question", "")[:2500],
        dd=paper["new_fields"].get("data_description", "")[:2500],
        ic=paper["new_fields"].get("institutional_context", "")[:2500],
        cue_list=_cue_block(scan_hits_by_field),
        examples=_examples_block(taxonomy),
    )


# ═══════════════════════════════════════════════════════════════
#  LLM call + validation
# ═══════════════════════════════════════════════════════════════

def call_opus(system: str, user: str) -> Tuple[dict, int, int]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    r = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = r.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip("` \n")
    return json.loads(raw), r.usage.input_tokens, r.usage.output_tokens


def post_check_hard_cues(new_fields: dict,
                         cue_regexes) -> list[dict]:
    """After rewrite, scan the three fields; any HARD cue surviving is a fail."""
    survivors = []
    for field in FIELDS_TO_REWRITE:
        text = new_fields.get(field, "")
        hits = [h for h in scan_text(text, cue_regexes)
                if h["category"] == "design_cues_hard"]
        for h in hits:
            survivors.append({"field": field, **h})
    return survivors


# ═══════════════════════════════════════════════════════════════
#  Per-paper processing
# ═══════════════════════════════════════════════════════════════

def process_paper(paper: dict, taxonomy: dict,
                  cue_regexes: list,
                  exp: ExperimentLogger) -> dict:
    pid = paper["paper_id"]

    orig = paper.get("new_fields", {})
    if not orig:
        return {"paper_id": pid, "error": "no new_fields in source"}

    # 1. Pre-scan for cue matches, per field
    scan_by_field = {
        field: scan_text(orig.get(field, ""), cue_regexes)
        for field in FIELDS_TO_REWRITE
    }
    all_hits = [h for hits in scan_by_field.values() for h in hits]
    n_hard = sum(1 for h in all_hits if h["category"] == "design_cues_hard")
    n_soft = sum(1 for h in all_hits if h["category"] == "design_cues_soft")

    # 2. If no HARD cues: passthrough
    if not should_rewrite(all_hits):
        exp.log_event("passthrough", paper_id=pid,
                      hard_cues=n_hard, soft_cues=n_soft)
        return {
            "paper_id":        pid,
            "source_type":     paper.get("source_type"),
            "rewrite_action":  "passthrough",
            "hard_cues_original": n_hard,
            "soft_cues_original": n_soft,
            "new_fields":      dict(orig),
            "original_fields": dict(orig),
            "cues_addressed":  [],
            "cues_surviving":  [],
            "llm_input_tokens":  0,
            "llm_output_tokens": 0,
            "llm_cost_usd":      0.0,
        }

    # 3. Build prompt + call Opus
    user_prompt = build_user_prompt(paper, scan_by_field, taxonomy)
    try:
        verdict, in_tok, out_tok = call_opus(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        exp.log_event("llm_error", paper_id=pid, error=str(e)[:200])
        return {
            "paper_id": pid,
            "error":    f"llm_error: {str(e)[:200]}",
            "rewrite_action": "failed",
        }

    # Opus pricing ~$15/M input + $75/M output
    cost = round(in_tok * 15 / 1e6 + out_tok * 75 / 1e6, 4)
    exp.log_llm_call(model=MODEL, input_tokens=in_tok,
                     output_tokens=out_tok, cost_usd=cost,
                     paper_id=pid, hard_cues_input=n_hard,
                     response_summary=f"addressed={len(verdict.get('cues_addressed',[]))} "
                                       f"self_reveal={verdict.get('method_revealed_after')}")

    # 4. Post-check
    new_fields = {
        "research_question":     verdict.get("research_question", orig["research_question"]),
        "data_description":      verdict.get("data_description",  orig["data_description"]),
        "institutional_context": verdict.get("institutional_context", orig["institutional_context"]),
    }
    survivors = post_check_hard_cues(new_fields, cue_regexes)

    return {
        "paper_id":               pid,
        "source_type":            paper.get("source_type"),
        "rewrite_action":         "rewritten",
        "hard_cues_original":     n_hard,
        "soft_cues_original":     n_soft,
        "hard_cues_after":        len(survivors),
        "surviving_cues":         survivors,
        "new_fields":             new_fields,
        "original_fields":        dict(orig),
        "cues_addressed":         verdict.get("cues_addressed", []),
        "cues_left_unchanged":    verdict.get("cues_left_unchanged", []),
        "llm_self_reveal_flag":   verdict.get("method_revealed_after", False),
        "llm_input_tokens":       in_tok,
        "llm_output_tokens":      out_tok,
        "llm_cost_usd":           cost,
    }


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def write_audit_csv(results: list[dict]) -> None:
    OUT_AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_AUDIT_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "paper_id", "rewrite_action", "hard_cues_original",
            "soft_cues_original", "hard_cues_after", "self_reveal_flag",
            "llm_cost_usd",
        ])
        for r in results:
            w.writerow([
                r.get("paper_id"),
                r.get("rewrite_action", "?"),
                r.get("hard_cues_original", 0),
                r.get("soft_cues_original", 0),
                r.get("hard_cues_after", 0),
                r.get("llm_self_reveal_flag", ""),
                r.get("llm_cost_usd", 0),
            ])


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pilot", action="store_true",
                   help="Process 10 papers (5 with many cues, 5 with few)")
    g.add_argument("--all",   action="store_true",
                   help="Process all 261 Phase 1 records")
    g.add_argument("--papers", type=str, default=None,
                   help="Comma-separated paper_ids")
    ap.add_argument("--input", type=Path, default=REGEN_IN,
                    help="Regen JSON to read 'new_fields' from. Default: V2 baseline. "
                         "Pass audit/regen_from_pdf_v2primeprime.json or "
                         "audit/regen_from_pdf_v2primeprime_with_leakage.json for V2''.")
    ap.add_argument("--out", type=Path, default=None,
                    help="Override output path (audit/regen_strong_deleak.json). "
                         "Use this when running on the leaky-only artifact to avoid "
                         "overwriting the main strong-deleak output.")
    args = ap.parse_args()

    taxonomy = load_taxonomy()
    cue_regexes = compile_cue_regexes(taxonomy)

    print(f"Reading: {args.input}")
    regen_rows = json.loads(args.input.read_text())
    regen_by_id = {r["paper_id"]: r for r in regen_rows
                   if "new_fields" in r}
    print(f"  rows with new_fields: {len(regen_by_id)}")

    out_path = args.out if args.out is not None else OUT_JSON
    print(f"Writing: {out_path}")

    if args.pilot:
        # Pick 5 with many cues, 5 with few, from a quick pre-scan
        scored = []
        for pid, paper in regen_by_id.items():
            text = " ".join(paper["new_fields"].get(f, "")
                            for f in FIELDS_TO_REWRITE)
            hits = scan_text(text, cue_regexes)
            hard = sum(1 for h in hits if h["category"] == "design_cues_hard")
            scored.append((pid, hard))
        scored.sort(key=lambda x: -x[1])
        top5 = [p for p, _ in scored[:5]]
        bot5 = [p for p, _ in scored[-5:]]
        target_ids = top5 + bot5
    elif args.all:
        target_ids = sorted(regen_by_id.keys(),
                             key=lambda s: int(s.split("_")[1]))
    else:
        target_ids = [p.strip() for p in args.papers.split(",") if p.strip()]

    exp = ExperimentLogger(
        run_name="a4_strong_deleak_pass"
                 + ("_pilot" if args.pilot else "_full" if args.all else "_explicit"),
        script_path=__file__,
        hypothesis=(
            "Applying an LLM review pass with the 117-cue taxonomy rewrites "
            "method-revealing phrases to neutral language while preserving "
            "research-question content. Target: < 2% of papers retain a HARD "
            "cue after rewrite; < 5% of papers have `method_revealed_after = true`."
        ),
        config={
            "model":                MODEL,
            "trigger_categories":   list(TRIGGER_CATEGORIES),
            "fields_rewritten":     list(FIELDS_TO_REWRITE),
            "taxonomy":             str(TAXONOMY_PATH.relative_to(ROOT)),
            "target_n":             len(target_ids),
            "mode":                 "pilot" if args.pilot else "all"
                                    if args.all else "explicit",
        },
    )
    exp.log_prompt("system", SYSTEM_PROMPT)
    exp.log_prompt("user_template", USER_TEMPLATE)

    # Resume from cache if present
    cache = {}
    if out_path.exists():
        for r in json.loads(out_path.read_text()):
            cache[r["paper_id"]] = r

    print(f"Strong de-leakage: processing {len(target_ids)} papers "
          f"(cached: {sum(1 for p in target_ids if p in cache)})")
    print(f"Model: {MODEL}")
    print()

    n_rewritten = n_passthrough = n_failed = 0
    for i, pid in enumerate(target_ids, 1):
        if pid in cache and "rewrite_action" in cache[pid]:
            row = cache[pid]
            print(f"  [{i}/{len(target_ids)}] {pid}: cached "
                  f"({row['rewrite_action']})")
        else:
            paper = regen_by_id.get(pid)
            if not paper:
                print(f"  [{i}/{len(target_ids)}] {pid}: not in regen source, skip")
                continue
            row = process_paper(paper, taxonomy, cue_regexes, exp)
            cache[pid] = row
            action = row.get("rewrite_action", "error")
            if action == "rewritten":
                mark = "✎"
            elif action == "passthrough":
                mark = "·"
            else:
                mark = "✗"
            surv = row.get("hard_cues_after", "?")
            cost = row.get("llm_cost_usd", 0)
            print(f"  [{i}/{len(target_ids)}] {pid}: {mark} {action} "
                  f"(hard_cues {row.get('hard_cues_original',0)} → {surv}, "
                  f"${cost:.4f})")

        if row.get("rewrite_action") == "rewritten":     n_rewritten += 1
        elif row.get("rewrite_action") == "passthrough": n_passthrough += 1
        else:                                             n_failed += 1

        if i % 5 == 0:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(list(cache.values()),
                                            indent=2, ensure_ascii=False))
        time.sleep(0.3)

    out_path.write_text(json.dumps(list(cache.values()),
                                    indent=2, ensure_ascii=False))
    exp.attach_output("regen_json", out_path)

    results = [cache[p] for p in target_ids if p in cache]
    write_audit_csv(results)
    exp.attach_output("audit_csv", OUT_AUDIT_CSV)

    # Summary stats
    total_cost = sum(r.get("llm_cost_usd", 0) for r in results)
    survivors_total = sum(r.get("hard_cues_after", 0) for r in results
                           if r.get("rewrite_action") == "rewritten")
    self_reveal_flag_n = sum(1 for r in results
                              if r.get("llm_self_reveal_flag") is True)

    print()
    print(f"=== Summary ===")
    print(f"  Rewritten:   {n_rewritten}")
    print(f"  Passthrough: {n_passthrough}")
    print(f"  Failed:      {n_failed}")
    print(f"  Total LLM cost: ${total_cost:.2f}")
    print(f"  Papers with HARD cues surviving rewrite: "
          f"{sum(1 for r in results if r.get('hard_cues_after', 0) > 0)}")
    print(f"  Papers flagged `method_revealed_after = true` by Opus: "
          f"{self_reveal_flag_n}")

    exp.finish(
        status="success" if n_failed == 0 else "partial",
        results={
            "n_rewritten":          n_rewritten,
            "n_passthrough":        n_passthrough,
            "n_failed":             n_failed,
            "total_cost_usd":       round(total_cost, 3),
            "hard_cues_surviving_papers": sum(1 for r in results
                                               if r.get("hard_cues_after", 0) > 0),
            "self_reveal_flag_papers":    self_reveal_flag_n,
        },
        interpretation=(
            f"Strong de-leakage processed {len(results)} papers at "
            f"${total_cost:.2f} total. "
            f"{n_passthrough} needed no rewrite (no hard cues in Phase 1 synthesis); "
            f"{n_rewritten} were rewritten. "
            f"Post-check found {sum(1 for r in results if r.get('hard_cues_after', 0) > 0)} "
            f"papers still containing a HARD cue after rewrite — "
            f"these are candidates for a second pass or manual review."
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
