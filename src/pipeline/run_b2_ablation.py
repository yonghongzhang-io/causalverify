"""
B2 Truncation Ablation: does the Phase-1 source length (V2=8pg vs V2'=20pg)
change the downstream Exp A prediction?

For each of 20 diagnostic papers x 2 input versions (V2, V2') x 2 models
(Claude Opus 4.7, GPT-5):
  1. Build the paper dict with the right research_question / data_description /
     institutional_context (swapped between V2 and V2')
  2. Call the full Exp A prompt (from run_exp_a.py — same SYSTEM + USER template
     that the 7-LLM full benchmark uses)
  3. Score with auto_score_exp_a.detect_method / detect_direction (regex,
     no LLM, free)
  4. Save raw output per (paper, version, model) and a row in the summary CSV

Output:
  audit/b2_ablation_outputs/{paper_id}__{version}__{model}.json  (raw LLM output)
  audit/b2_ablation_predictions.csv                                (per-call row)
  audit/b2_ablation_summary.md                                     (flip rates)

Decision rule (pre-registered):
  - flip_rate < 10%  -> KEEP V2  (classification concordance >= 90%)
  - flip_rate > 25%  -> GO V2'   (input too thin, go full restructure)
  - 10-25%           -> AMBIGUOUS, needs manual review
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Reuse the exact Exp A prompt and LLM dispatch
from src.pipeline.run_exp_a import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, call_llm
from src.pipeline.auto_score_exp_a import detect_method, detect_direction
from src.labnotebook.experiment_logger import ExperimentLogger

ROOT       = Path(__file__).parent.parent.parent
SAMPLE_CSV = ROOT / "audit/v2prime_pilot_sample.csv"
V2_JSON    = ROOT / "audit/regen_from_pdf.json"
V2P_JSON   = ROOT / "audit/regen_from_pdf_v2prime_pilot.json"
OUT_DIR    = ROOT / "audit/b2_ablation_outputs"
OUT_CSV    = ROOT / "audit/b2_ablation_predictions.csv"
OUT_SUM    = ROOT / "audit/b2_ablation_summary.md"
PAPERS_DIR = ROOT / "experiments/exp_a/papers"

MODELS = [
    ("claude-opus-4-7", "Claude Opus 4.7"),
    ("gpt-5",           "GPT-5"),
]

BUDGET_WARN_USD = 35.0

# Cost table for soft estimation (per million tokens)
COST = {
    "claude-opus-4-7": (15.0, 75.0),   # input / output $/M
    "gpt-5":           (1.25, 10.0),   # as of late 2025 (est.); soft estimate only
}

def est_cost(model, in_tok, out_tok):
    ci, co = COST.get(model, (10.0, 30.0))
    return in_tok * ci / 1_000_000 + out_tok * co / 1_000_000


def find_paper_file(pid):
    hits = list(PAPERS_DIR.glob(f"{pid}_*.json")) + list(PAPERS_DIR.glob(f"{pid}.json"))
    return hits[0] if hits else None


def load_inputs():
    v2_map  = {r["paper_id"]: r.get("new_fields", {})
                for r in json.loads(V2_JSON.read_text())
                if "new_fields" in r}
    v2p_map = {r["paper_id"]: r.get("new_fields", {})
                for r in json.loads(V2P_JSON.read_text())
                if "new_fields" in r}
    return v2_map, v2p_map


def build_paper_dict(pid, fields, original_paper):
    """Build the paper dict that run_exp_a's call_llm expects."""
    return {
        "paper_id":               pid,
        "research_question":      fields.get("research_question", ""),
        "data_description":       fields.get("data_description", ""),
        "institutional_context":  fields.get("institutional_context", ""),
        "method_family":          original_paper.get("method_family", ""),
        "difficulty":             original_paper.get("difficulty", ""),
    }


def main():
    if not SAMPLE_CSV.exists():
        print(f"ERROR: {SAMPLE_CSV} missing")
        sys.exit(1)
    if not V2P_JSON.exists():
        print(f"ERROR: {V2P_JSON} missing (run rebuild_metadata_v2prime.py first)")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(SAMPLE_CSV) as f:
        sample = [(r["paper_id"], r["method_family"]) for r in csv.DictReader(f)]
    print(f"B2 ablation: {len(sample)} papers x 2 versions x {len(MODELS)} models "
           f"= {len(sample) * 2 * len(MODELS)} calls")
    print(f"Budget soft warning at ${BUDGET_WARN_USD:.0f}")

    v2_map, v2p_map = load_inputs()

    exp = ExperimentLogger(
        run_name="b2_truncation_ablation",
        script_path=__file__,
        hypothesis=(
            "If 8-page (V2) Phase-1 source is methodologically sufficient, "
            "LLM predictions of method_family should NOT flip when the input "
            "is switched to 20-page (V2'). Measured on 20 papers x 2 models. "
            "Flip rate < 10% -> keep V2; > 25% -> go V2'."
        ),
        config={
            "n_papers":       len(sample),
            "versions":       ["V2_8pg", "V2p_20pg"],
            "models":         [m for m,_ in MODELS],
            "prompt_source":  "src/pipeline/run_exp_a.py (identical to full Exp A)",
            "output_dir":     str(OUT_DIR.relative_to(ROOT)),
            "budget_warn":    BUDGET_WARN_USD,
        },
    )
    exp.log_prompt("system", SYSTEM_PROMPT)
    exp.log_prompt("user_template", USER_PROMPT_TEMPLATE)

    rows = []
    total_cost = 0.0
    warned = False
    idx = 0
    total_calls = len(sample) * 2 * len(MODELS)

    for pid, fam in sample:
        pf = find_paper_file(pid)
        if not pf:
            print(f"  SKIP {pid}: paper JSON not found")
            continue
        original_paper = json.loads(pf.read_text())

        for version_label, fields_map in [("V2_8pg", v2_map), ("V2p_20pg", v2p_map)]:
            fields = fields_map.get(pid)
            if not fields:
                print(f"  SKIP {pid}/{version_label}: missing fields")
                continue
            paper_dict = build_paper_dict(pid, fields, original_paper)

            for model_id, model_pretty in MODELS:
                idx += 1
                slug = model_id.replace("/", "-").replace(":", "-")
                out_file = OUT_DIR / f"{pid}__{version_label}__{slug}.json"

                if out_file.exists():
                    # Cache hit — load, score, continue
                    cached = json.loads(out_file.read_text())
                    resp = cached["llm_response"]
                    print(f"  [{idx:>3}/{total_calls}] CACHED {pid}/{version_label}/{model_id}")
                else:
                    try:
                        t0 = time.time()
                        resp = call_llm(paper_dict, model_id)
                        elapsed = time.time() - t0
                    except Exception as e:
                        print(f"  [{idx:>3}/{total_calls}] ERR {pid}/{version_label}/{model_id}: {str(e)[:120]}")
                        exp.log_event("error", paper_id=pid, version=version_label,
                                       model=model_id, reason=str(e)[:200])
                        rows.append({
                            "paper_id": pid, "method_family_true": fam,
                            "version": version_label, "model": model_id,
                            "detected_method": None, "detected_direction": None,
                            "error": str(e)[:200],
                        })
                        continue

                    cost = est_cost(model_id,
                                     resp.get("input_tokens", 0),
                                     resp.get("output_tokens", 0))
                    total_cost += cost
                    exp.log_llm_call(
                        model=model_id,
                        input_tokens=resp.get("input_tokens", 0),
                        output_tokens=resp.get("output_tokens", 0),
                        cost_usd=round(cost, 4),
                        paper_id=pid,
                        version=version_label,
                        response_summary=(resp.get("content", "") or "")[:200],
                    )
                    out_file.write_text(json.dumps({
                        "paper_id":        pid,
                        "method_family":   original_paper.get("method_family", ""),
                        "difficulty":      original_paper.get("difficulty", ""),
                        "version":         version_label,
                        "model":           model_id,
                        "run_at":          datetime.now(timezone.utc).isoformat(),
                        "llm_response":    resp,
                        "input_fields_source": version_label,
                    }, indent=2, ensure_ascii=False))
                    print(f"  [{idx:>3}/{total_calls}] OK {pid}/{version_label}/{model_id}  "
                           f"({elapsed:.1f}s, this=${cost:.3f}, cum=${total_cost:.2f})")

                # Score
                content = resp.get("content", "") or ""
                det_m = detect_method(content)
                det_d = detect_direction(content)
                rows.append({
                    "paper_id": pid,
                    "method_family_true": fam,
                    "version": version_label,
                    "model": model_id,
                    "detected_method": det_m,
                    "detected_direction": det_d,
                    "error": "",
                })

                if (not warned) and total_cost >= BUDGET_WARN_USD:
                    print(f"\n  ** BUDGET WARNING: cumulative ${total_cost:.2f} "
                           f">= ${BUDGET_WARN_USD:.2f} ** (continuing)")
                    warned = True

                time.sleep(0.3)

    # Write per-call CSV
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "paper_id","method_family_true","version","model",
            "detected_method","detected_direction","error"
        ])
        w.writeheader()
        for r in rows: w.writerow(r)

    # Pivot: for each (paper, model), compare V2 vs V2' predictions
    pivot = defaultdict(dict)   # (pid, model) -> {V2_8pg: (m,d), V2p_20pg: (m,d)}
    for r in rows:
        pivot[(r["paper_id"], r["model"])][r["version"]] = (
            r["detected_method"], r["detected_direction"]
        )

    per_model_flips = defaultdict(lambda: {"method_flips": 0, "direction_flips": 0,
                                             "either_flips": 0, "n": 0})
    for (pid, model), versions in pivot.items():
        v2   = versions.get("V2_8pg")
        v2p  = versions.get("V2p_20pg")
        if not v2 or not v2p: continue
        per_model_flips[model]["n"] += 1
        mf = v2[0] != v2p[0]
        df = v2[1] != v2p[1]
        if mf: per_model_flips[model]["method_flips"] += 1
        if df: per_model_flips[model]["direction_flips"] += 1
        if mf or df: per_model_flips[model]["either_flips"] += 1

    # Aggregate
    agg = {"method_flips": 0, "direction_flips": 0, "either_flips": 0, "n": 0}
    for d in per_model_flips.values():
        for k in ["method_flips","direction_flips","either_flips","n"]:
            agg[k] += d[k]
    method_flip_rate = agg["method_flips"] / agg["n"] if agg["n"] else 0

    if method_flip_rate < 0.10:
        decision = ("KEEP V2. Classification concordance across the 8- to 20-page "
                     "input change is >= 90%. Paper Methods can report: "
                     f"'8-page vs 20-page classification concordance: "
                     f"{(1-method_flip_rate)*100:.0f}%'.")
    elif method_flip_rate > 0.25:
        decision = ("GO V2'. Method predictions flip on > 25% of papers when "
                     "input source expands. V2 is too thin; proceed with full "
                     "restructure (Step 2, ~$220-290).")
    else:
        decision = ("AMBIGUOUS. Flip rate in 10-25% gray zone. Manual review "
                     "of flips needed.")

    # Report
    md = [
        "# B2 Truncation Ablation Summary",
        "",
        f"- Sample: 20 papers x 2 versions x {len(MODELS)} models = "
        f"{agg['n']*2} valid V2+V2' pairs",
        f"- Models: {', '.join(f'{m} ({p})' for m,p in MODELS)}",
        f"- Prompt: identical to src/pipeline/run_exp_a.py (full Exp A SYSTEM+USER)",
        f"- Cost spent: **${total_cost:.2f}**",
        "",
        "## Per-model flip rates",
        "",
        "| Model | N | method_flips | direction_flips | either_flips | method_flip_rate |",
        "|---|---|---|---|---|---|",
    ]
    for model, d in per_model_flips.items():
        rate = d["method_flips"] / d["n"] if d["n"] else 0
        md.append(f"| {model} | {d['n']} | {d['method_flips']} | "
                   f"{d['direction_flips']} | {d['either_flips']} | "
                   f"{rate*100:.0f}% |")
    md += [
        "",
        "## Aggregate (all models pooled)",
        "",
        f"- method_flip_rate: **{method_flip_rate*100:.0f}%** ({agg['method_flips']}/{agg['n']})",
        f"- direction_flip_rate: {(agg['direction_flips']/agg['n']*100) if agg['n'] else 0:.0f}% "
        f"({agg['direction_flips']}/{agg['n']})",
        f"- either_flip_rate: {(agg['either_flips']/agg['n']*100) if agg['n'] else 0:.0f}% "
        f"({agg['either_flips']}/{agg['n']})",
        "",
        "## Decision rule (pre-registered)",
        "",
        "- **method_flip_rate < 10%**  -> KEEP V2",
        "- **method_flip_rate > 25%**  -> GO V2' (full restructure)",
        "- **10-25%**                  -> AMBIGUOUS, manual review",
        "",
        f"### Verdict",
        "",
        f"**{decision}**",
        "",
        "## Flip detail (only rows where V2 != V2')",
        "",
        "| paper_id | model | V2 method | V2' method | V2 dir | V2' dir |",
        "|---|---|---|---|---|---|",
    ]
    for (pid, model), versions in sorted(pivot.items()):
        v2 = versions.get("V2_8pg")
        v2p = versions.get("V2p_20pg")
        if not v2 or not v2p: continue
        if v2 != v2p:
            md.append(f"| {pid} | {model} | {v2[0]} | {v2p[0]} | "
                       f"{v2[1]} | {v2p[1]} |")
    md += [
        "",
        "## Files",
        f"- Per-call CSV: `audit/b2_ablation_predictions.csv`",
        f"- Raw outputs: `audit/b2_ablation_outputs/*.json`",
    ]
    OUT_SUM.write_text("\n".join(md))

    exp.attach_output("b2_ablation_predictions.csv", OUT_CSV)
    exp.attach_output("b2_ablation_summary.md", OUT_SUM)
    exp.finish(
        status="success",
        results={
            "total_calls":         len(rows),
            "paired_n":            agg["n"],
            "method_flip_rate":    round(method_flip_rate, 4),
            "direction_flip_rate": round(agg["direction_flips"]/agg["n"], 4) if agg["n"] else 0,
            "total_cost_usd":      round(total_cost, 4),
            "decision":            decision[:100],
        },
        interpretation=decision,
    )

    print()
    print(f"Done. Cost: ${total_cost:.2f}. Flip rate (method): {method_flip_rate*100:.0f}%")
    print(f"Decision: {decision}")
    print(f"Details: {OUT_SUM.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
