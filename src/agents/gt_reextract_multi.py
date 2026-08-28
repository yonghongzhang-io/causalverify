"""
Multi-LLM Ground-Truth Re-extraction — Stage 1+2 combined.

For every Exp A paper (default: all 262), runs a strict re-extraction of
method_family + conclusion_direction using four LLMs:

  Primary:  Claude Opus 4.7 (frontier, NOT in benchmark pool → clean primary)
  Cross 1:  GPT-4o          (ORIGINAL extractor, pulled from cached paper JSON)
  Cross 2:  Kimi (Moonshot) (vendor independence)
  Cross 3:  Gemini 2.5 Flash (vendor independence)

Each new LLM is called with an identical strict prompt (see STRICT_PROMPT
below) that explicitly handles the common confusion cases we observed in
the 50-sample pilot:
  - DID with event-study plots → DID (not EVENT_STUDY)
  - Shift-share IV with regional comparison → DID
  - EVENT_STUDY reserved for CARs around specific event dates
  - Structural / matching / synthetic control → OTHER

Output: audit/gt_reextract_multi.json, one row per paper with 4 votes.

Usage:
  python3 src/agents/gt_reextract_multi.py --all          # 262 papers
  python3 src/agents/gt_reextract_multi.py --limit 10     # smoke test
  python3 src/agents/gt_reextract_multi.py --resume       # pick up from cache

This script is incremental and resumable — partial runs flush to JSON
every 10 papers; re-running skips papers already done per LLM.
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
OUT_JSON   = ROOT / "audit/gt_reextract_multi.json"
OUT_MD     = ROOT / "audit/gt_reextract_multi_summary.md"

PRIMARY_MODEL = "claude-opus-4-7"
KIMI_MODEL    = "kimi-latest"
GEMINI_MODEL  = "gemini-2.5-flash"

STRICT_PROMPT_SYS = (
    "You are a senior empirical-finance econometrician classifying papers for "
    "a NeurIPS benchmark dataset. Your classifications will be used as ground "
    "truth for evaluating LLM causal-inference capabilities, so accuracy "
    "matters more than speed.\n\n"
    "Return ONLY a JSON object — no prose, no markdown fences, no "
    "explanation. Schema:\n\n"
    "{\n"
    '  "method_family":    "DID" | "EVENT_STUDY" | "IV" | "RDD" | "OTHER",\n'
    '  "secondary_method": "DID" | "EVENT_STUDY" | "IV" | "RDD" | "OTHER" | null,\n'
    '  "direction":        "positive" | "negative" | "mixed" | "unclear",\n'
    '  "confidence":       "high" | "medium" | "low"\n'
    "}\n\n"
    "STRICT CLASSIFICATION RULES (read carefully):\n\n"
    "METHOD FAMILY:\n"
    "• DID: compares CHANGES (post − pre) between a treated and an "
    "untreated group around a policy/shock. Includes two-period, staggered, "
    "and triple-difference designs. IMPORTANT: event-study PLOTS used inside "
    "a DID paper are still DID — not Event Study. Papers that compare effects "
    "across regions via a shift-share instrument are DID, not IV.\n\n"
    "• EVENT_STUDY: core identification is ABNORMAL RETURNS / OUTCOMES in a "
    "SHORT WINDOW around a SPECIFIC EVENT DATE. Paper typically reports "
    "cumulative abnormal returns (CARs). Use this ONLY if the paper's "
    "headline number is a CAR or similar short-window abnormal-outcome "
    "metric. If the paper merely pools multiple events and runs a DID, it "
    "is DID, not Event Study.\n\n"
    "• IV: uses an instrumental variable / 2SLS / GMM where a specific "
    "instrument is NAMED and an exclusion-restriction argument is made. "
    "If the paper's identification is 'we compare X across places that "
    "differ in Y' — that's DID, not IV, unless Y is explicitly framed "
    "as an instrument for another variable.\n\n"
    "• RDD: uses a running-variable cutoff (sharp / fuzzy / geographic). "
    "Paper discusses bandwidth, local linear regression, or discontinuity.\n\n"
    "• OTHER: structural estimation, synthetic control, propensity-score "
    "matching only, calibrated simulation, pure OLS with no identification "
    "strategy. Also use OTHER for methods that genuinely don't fit above.\n\n"
    "If a paper uses TWO methods, put the PRIMARY method (the one producing "
    "the headline estimate) in method_family and the secondary method in "
    "secondary_method. E.g., a DID with an IV robustness check: "
    'method_family="DID", secondary_method="IV".\n\n'
    "DIRECTION:\n"
    "• positive: headline coefficient/effect is positive, statistically and "
    "economically meaningful.\n"
    "• negative: headline effect is negative.\n"
    "• mixed: paper EXPLICITLY frames the finding as heterogeneous across "
    "subsamples/outcomes AS THE MAIN FINDING (not as a secondary caveat).\n"
    "• unclear: cannot determine from abstract alone.\n\n"
    "Work ONLY from the text provided. If the abstract is ambiguous, pick "
    "your best guess and set confidence=low. Do not invent details."
)

USER_TEMPLATE = (
    "Paper title:\n{title}\n\n"
    "Research question:\n{rq}\n\n"
    "Abstract / institutional context:\n{abstract}\n\n"
    "Classify per the schema."
)


# ── LLM callers ────────────────────────────────────────────────────────

def build_user(paper: dict) -> str:
    return USER_TEMPLATE.format(
        title=paper.get("title", ""),
        rq=paper.get("research_question", ""),
        abstract=paper.get("institutional_context", "")[:2500],
    )


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip("` \n")
    return raw


def call_opus(paper: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    r = client.messages.create(
        model=PRIMARY_MODEL,
        max_tokens=300,
        system=STRICT_PROMPT_SYS,
        messages=[{"role": "user", "content": build_user(paper)}],
    )
    return json.loads(_strip_fences(r.content[0].text))


def call_kimi(paper: dict) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("KIMI_API_KEY"),
                    base_url="https://api.moonshot.cn/v1")
    r = client.chat.completions.create(
        model=KIMI_MODEL,
        max_tokens=300,
        messages=[{"role": "system", "content": STRICT_PROMPT_SYS},
                  {"role": "user",   "content": build_user(paper)}],
    )
    return json.loads(_strip_fences(r.choices[0].message.content))


def call_gemini(paper: dict) -> dict:
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    # Gemini 2.5 Flash silently consumes ~1.5K "thinking" tokens before
    # emitting visible output. 300 truncates the JSON mid-field.
    r = client.chat.completions.create(
        model=GEMINI_MODEL,
        max_tokens=2048,
        messages=[{"role": "system", "content": STRICT_PROMPT_SYS},
                  {"role": "user",   "content": build_user(paper)}],
    )
    return json.loads(_strip_fences(r.choices[0].message.content))


# ── Orchestration ─────────────────────────────────────────────────────

def _norm_method(x: str | None) -> str | None:
    if not x: return None
    return x.upper().replace(" ", "_").replace("-", "_")


def _norm_dir(x: str | None) -> str | None:
    if not x: return None
    return x.lower().strip()


def process_paper(paper: dict, cached_row: dict | None,
                  skip: set[str]) -> dict:
    pid = paper["paper_id"]
    # Existing GPT-4o label from paper JSON (no new API call)
    gpt4o_method    = _norm_method(paper.get("method_family"))
    gpt4o_direction = _norm_dir(paper.get("ground_truth", {})
                                       .get("conclusion_direction"))

    row = cached_row or {"paper_id": pid}
    row["gpt4o"] = {"method": gpt4o_method,
                    "direction": gpt4o_direction,
                    "source": "cached_from_paper_json"}

    for label, caller in [("opus_4_7", call_opus),
                          ("kimi",     call_kimi),
                          ("gemini",   call_gemini)]:
        if label in skip: continue
        if label in row and row[label].get("method"):
            continue   # resumed
        try:
            resp = caller(paper)
            row[label] = {
                "method":           _norm_method(resp.get("method_family")),
                "secondary_method": _norm_method(resp.get("secondary_method")),
                "direction":        _norm_dir(resp.get("direction")),
                "confidence":       resp.get("confidence"),
            }
        except Exception as e:
            row[label] = {"error": str(e)[:200]}
        time.sleep(0.15)

    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all",    action="store_true")
    ap.add_argument("--limit",  type=int, default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--skip",   type=str, default="",
                    help="Comma list of LLMs to skip: opus_4_7,kimi,gemini")
    args = ap.parse_args()

    skip = set(x.strip() for x in args.skip.split(",") if x.strip())

    # Load all papers
    paper_files = sorted(PAPERS_DIR.glob("paper_*.json"),
                         key=lambda p: int(p.stem.split("_")[1]))
    if args.limit:
        paper_files = paper_files[:args.limit]
    if not args.all and not args.limit:
        print("ERROR: specify --all or --limit N", file=sys.stderr)
        sys.exit(1)

    # Load cache
    cache = {}
    if OUT_JSON.exists() and (args.resume or True):
        cache = {r["paper_id"]: r
                 for r in json.loads(OUT_JSON.read_text())}
        print(f"Loaded {len(cache)} cached rows from {OUT_JSON}")

    print(f"Processing {len(paper_files)} papers "
          f"(skip={skip or 'none'}, primary={PRIMARY_MODEL})")
    print("=" * 60)

    rows = []
    for i, pf in enumerate(paper_files, 1):
        paper = json.loads(pf.read_text())
        pid   = paper["paper_id"]
        cached = cache.get(pid)

        # If fully cached, skip API
        need_api = False
        for label in ("opus_4_7", "kimi", "gemini"):
            if label in skip: continue
            if not cached or not cached.get(label, {}).get("method"):
                need_api = True; break

        if not need_api:
            rows.append(cached)
            if i % 20 == 0: print(f"  [{i}/{len(paper_files)}] {pid}: cached")
            continue

        row = process_paper(paper, cached, skip)
        rows.append(row)
        cache[pid] = row

        # compact log
        o = row.get("opus_4_7", {}).get("method", "?")
        g4 = row["gpt4o"]["method"]
        k  = row.get("kimi",     {}).get("method", "?")
        ge = row.get("gemini",   {}).get("method", "?")
        print(f"  [{i}/{len(paper_files)}] {pid}: "
              f"Opus47={o} | GPT4o={g4} | Kimi={k} | Gemini={ge}")

        # Flush every 10
        if i % 10 == 0:
            OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
            OUT_JSON.write_text(json.dumps(list(cache.values()),
                                           indent=2, ensure_ascii=False))

    # Final flush
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(list(cache.values()),
                                   indent=2, ensure_ascii=False))

    # Summary: bucket by vote count
    buckets = {"all4_agree": 0, "3of4_agree": 0,
               "2of4_agree": 0, "split":      0, "error":      0}
    for r in rows:
        methods = []
        for k in ("opus_4_7", "gpt4o", "kimi", "gemini"):
            v = r.get(k, {})
            if "error" in v or not v.get("method"):
                continue
            methods.append(v["method"])
        if len(methods) < 2:
            buckets["error"] += 1; continue
        from collections import Counter
        c = Counter(methods)
        top = c.most_common(1)[0][1]
        if top == 4:  buckets["all4_agree"] += 1
        elif top == 3: buckets["3of4_agree"] += 1
        elif top == 2: buckets["2of4_agree"] += 1
        else:         buckets["split"]       += 1

    print()
    print("Method-family vote distribution:")
    total = sum(buckets.values())
    for k, v in buckets.items():
        pct = v / total * 100 if total else 0
        print(f"  {k:<14} {v:>4}  ({pct:.0f}%)")
    print()
    print(f"Full results: {OUT_JSON}")


if __name__ == "__main__":
    main()
