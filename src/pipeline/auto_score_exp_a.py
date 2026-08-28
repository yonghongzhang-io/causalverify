"""
Experiment A — Automated L1/L3/L4 Text-Level Agreement Scorer
============================================================
Scores all LLM outputs against ground truth without human interaction.

Layers evaluated:
  L1  Task completion     — output file exists and is non-empty
  L3  Method-family agreement (text-level)
  L4  Direction agreement (text-level)

Usage:
  python src/pipeline/auto_score_exp_a.py
  python src/pipeline/auto_score_exp_a.py --models moonshot-v1-128k claude-sonnet-4-20250514
  python src/pipeline/auto_score_exp_a.py --csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

PAPERS_DIR  = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/exp_a/outputs")
GT_PATH     = Path("audit/gt_aggregate_decisions.json")
FIGURES_DIR = Path("paper/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# Keywords that indicate each method family (section-aware weighted scoring)
STRATEGY_KEYWORDS = {
    "DID": [
        "difference-in-differences", "diff-in-diff", "dif-in-dif",
        "differences-in-differences", "double difference",
        "staggered did", "staggered diff", "twfe",
        "two-way fixed effect", "canonical did",
    ],
    "EVENT_STUDY": [
        "event study", "event-study", "cumulative abnormal return",
        "announcement return", "abnormal return", "car ",
    ],
    "IV": [
        "instrumental variable", "two-stage least squares", "2sls",
        "iv approach", "iv estimat", "instrument for",
    ],
    "RDD": [
        "regression discontinuity", "rd design", "rdrobust",
        "sharp cutoff", "running variable", "fuzzy rd",
        "discontinuity design",
    ],
}

DIRECTION_POS = [
    "positive", "increase", "higher", "gain", "improve",
    "larger", "upward", "beneficial", "raises",
]
DIRECTION_NEG = [
    "negative", "decrease", "lower", "decline", "worse",
    "reduces", "destroy", "underperform", "fall", "drop",
]

METHOD_COLORS = {
    "DID":         "#1D9E75",
    "EVENT_STUDY": "#378ADD",
    "IV":          "#7F77DD",
    "RDD":         "#D85A30",
}

MODEL_SHORT = {
    "moonshot-v1-128k":        "Kimi-128k",
    "claude-sonnet-4-20250514": "Claude-Sonnet",
    "gpt-4o":                  "GPT-4o",
    "o3":                      "o3",
    "claude-opus-4-6":         "Claude-Opus",
    "gemini-2.5-flash":        "Gemini-2.5",
    "gpt-5":                   "GPT-5",
}

SCOREABLE_METHODS = {"DID", "EVENT_STUDY", "IV", "RDD"}
SCOREABLE_DIRECTIONS = {"positive", "negative"}


def natural_paper_num(p: Path) -> int:
    """Extract paper number for natural sorting (paper_01 → 1, paper_100 → 100)."""
    try:
        return int(p.stem.split("_")[1])
    except (IndexError, ValueError):
        return 999999


def detect_method(text: str) -> str | None:
    """Detect primary identification strategy using section-aware weighted scoring.

    Ported from evaluate.py: gives 3x weight to Section 1 mentions,
    applies DID/ES disambiguation rule.
    """
    s = text.lower()

    # Isolate Section 1 (Identification Strategy) window
    sec1_start = -1
    for marker in ["1. identification", "## 1", "identification strategy"]:
        pos = s.find(marker)
        if pos >= 0 and (sec1_start < 0 or pos < sec1_start):
            sec1_start = pos
    if sec1_start >= 0:
        sec1_end = sec1_start + 1500
        for next_sec in ["## 2", "2. treatment", "## 3", "3. key"]:
            ns = s.find(next_sec, sec1_start + 20)
            if ns > 0:
                sec1_end = min(sec1_end, ns)
        sec1 = s[sec1_start:sec1_end]
    else:
        sec1 = s[:1500]

    full_window = s[:4000]

    scores = {}
    for method, keywords in STRATEGY_KEYWORDS.items():
        sec1_count = sum(sec1.count(kw) for kw in keywords)
        full_count = sum(full_window.count(kw) for kw in keywords)
        score = sec1_count * 3 + full_count

        # First-position tiebreaker
        first_pos = 9999
        for kw in keywords:
            idx = full_window.find(kw)
            if idx >= 0:
                first_pos = min(first_pos, idx)
        if first_pos < 9999:
            score += max(0, 2 - first_pos / 2000)

        if score > 0:
            scores[method] = score

    if not scores:
        return None

    # DID/ES disambiguation: modern DID papers often include event-study plots
    did_core = ["difference-in-differences", "diff-in-diff", "dif-in-dif",
                "differences-in-differences", "double difference"]
    if "DID" in scores and "EVENT_STUDY" in scores:
        has_core_did = any(sec1.count(kw) > 0 for kw in did_core)
        if has_core_did:
            scores["EVENT_STUDY"] *= 0.5

    return max(scores, key=scores.get)


def detect_direction(text: str) -> str | None:
    """Return 'positive' or 'negative' based on Expected Results section.

    Ported from evaluate.py: looks specifically at Section 6 / Expected Results,
    not the arbitrary latter half of the text.
    """
    tl = text.lower()

    # Find Expected Results section
    seg = ""
    for marker in ["6. expected", "## 6", "expected results",
                   "6. prior", "prior expectation"]:
        pos = tl.find(marker)
        if pos >= 0:
            end = pos + 1200
            for stop in ["## 7", "7. validity", "validity checklist",
                         "self-assessment", "c1:", "c1 "]:
                spos = tl.find(stop, pos + 20)
                if spos > 0:
                    end = min(end, spos)
            seg = tl[pos:end]
            break

    if not seg:
        # Fallback: last substantive paragraph before checklist
        checklist_start = len(tl)
        for ck in ["validity checklist", "self-assessment",
                   "c1:", "## 7", "7. validity"]:
            cp = tl.rfind(ck)
            if cp > len(tl) // 2:
                checklist_start = min(checklist_start, cp)
        seg = tl[max(0, checklist_start - 800):checklist_start]

    if not seg:
        seg = tl[-800:]

    pos_count = sum(seg.count(kw) for kw in DIRECTION_POS)
    neg_count = sum(seg.count(kw) for kw in DIRECTION_NEG)

    if pos_count == 0 and neg_count == 0:
        return None
    return "positive" if pos_count > neg_count else "negative"


def load_gt_aggregate(path: Path = GT_PATH) -> dict[str, dict]:
    """Load Stage 8.2 4-LLM consensus GT.

    V2'' merge intentionally moves legacy paper-level ``ground_truth`` to
    ``_legacy_v1_ground_truth``. Exp A scoring must therefore use the
    post-revote aggregate file, not the old ingestion label inside paper JSONs.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found; run Stage 8.2 GT aggregation before scoring Exp A"
        )
    rows = json.loads(path.read_text())
    return {r["paper_id"]: r for r in rows}


def gt_for_paper(paper: dict, gt_by_pid: dict[str, dict]) -> dict:
    pid = paper["paper_id"]
    if pid not in gt_by_pid:
        raise KeyError(f"{pid} missing from {GT_PATH}")
    gt = gt_by_pid[pid]
    method = gt.get("new_method")
    direction = (gt.get("new_direction") or "").lower()
    return {
        "method": method,
        "direction": direction,
        "method_scoreable": method in SCOREABLE_METHODS,
        "direction_scoreable": direction in SCOREABLE_DIRECTIONS,
        "m_level": gt.get("m_level"),
        "d_level": gt.get("d_level"),
        "needs_human": bool(gt.get("needs_human")),
    }


def score_output(paper: dict, gt: dict, llm_output: dict) -> dict:
    content = llm_output["llm_response"]["content"]
    true_method = gt["method"]
    true_direction = gt["direction"]
    method_scoreable = gt["method_scoreable"]
    direction_scoreable = gt["direction_scoreable"]

    detected_method = detect_method(content)
    detected_direction = detect_direction(content)

    l1 = bool(content.strip())
    l3_method_agree = (
        method_scoreable and detected_method == true_method
    ) if detected_method else False
    l4_direction_agree = (
        direction_scoreable and detected_direction == true_direction
    ) if detected_direction else False

    return {
        "paper_id": paper["paper_id"],
        "method_family": true_method or "UNSCORED",
        "orig_method_family": paper.get("method_family"),
        "difficulty": paper["difficulty"],
        "true_method": true_method or "",
        "detected_method": detected_method,
        "true_direction": true_direction,
        "detected_direction": detected_direction,
        "gt_m_level": gt["m_level"],
        "gt_d_level": gt["d_level"],
        "needs_human": gt["needs_human"],
        "L3_scoreable": method_scoreable,
        "L4_scoreable": direction_scoreable,
        "L1_complete": l1,
        "L3_method_agree": l3_method_agree,
        "L4_direction_agree": l4_direction_agree,
        # Legacy aliases retained for older tables/figures.
        "L3a_strategy": l3_method_agree,
        "L3b_direction": l4_direction_agree,
        "L3_pass": l3_method_agree and l4_direction_agree,
    }


def run_scoring(models: list[str]) -> dict[str, list[dict]]:
    gt_by_pid = load_gt_aggregate()
    papers = sorted(PAPERS_DIR.glob("paper_*.json"), key=natural_paper_num)
    results = {}

    for model in models:
        model_slug = model.replace("/", "-").replace(":", "-")
        model_results = []
        for p in papers:
            paper = json.loads(p.read_text())
            pid = paper["paper_id"]
            gt = gt_for_paper(paper, gt_by_pid)
            out_file = OUTPUTS_DIR / f"{pid}_{model_slug}.json"
            if not out_file.exists():
                model_results.append({
                    "paper_id": pid,
                    "method_family": gt["method"] or "UNSCORED",
                    "orig_method_family": paper.get("method_family"),
                    "difficulty": paper["difficulty"],
                    "L1_complete": False,
                    "L3_method_agree": False,
                    "L4_direction_agree": False,
                    "L3_scoreable": gt["method_scoreable"],
                    "L4_scoreable": gt["direction_scoreable"],
                    "L3a_strategy": False,
                    "L3b_direction": False,
                    "L3_pass": False,
                    "detected_method": None,
                    "detected_direction": None,
                    "true_method": gt["method"] or "",
                    "true_direction": gt["direction"],
                    "gt_m_level": gt["m_level"],
                    "gt_d_level": gt["d_level"],
                    "needs_human": gt["needs_human"],
                })
                continue
            llm_output = json.loads(out_file.read_text())
            model_results.append(score_output(paper, gt, llm_output))
        results[model] = model_results
    return results


def print_table(results: dict[str, list[dict]]):
    models = list(results.keys())
    papers = results[models[0]]

    header = f"{'Paper':<12} {'Method':<14} {'Diff':<8}"
    for m in models:
        short = MODEL_SHORT.get(m, m[:14])
        header += f"  {short:<16}"
    print(header)
    print("-" * len(header))

    for i, row in enumerate(papers):
        line = f"{row['paper_id']:<12} {row['method_family']:<14} {row['difficulty']:<8}"
        for m in models:
            r = results[m][i]
            l3a = "✅" if r["L3_method_agree"] else "❌"
            l3b = "✅" if r["L4_direction_agree"] else "❌"
            det = r.get("detected_method", "?") or "?"
            line += f"  {l3a}{l3b} ({det:<12})"
        print(line)

    print()
    for m in models:
        rs = results[m]
        l3a_score = sum(r["L3_method_agree"] for r in rs)
        l3b_score = sum(r["L4_direction_agree"] for r in rs)
        short = MODEL_SHORT.get(m, m)
        n = len(rs)
        l3n = sum(r["L3_scoreable"] for r in rs)
        l4n = sum(r["L4_scoreable"] for r in rs)
        print(
            f"{short}: Method agreement {l3a_score}/{l3n} scoreable "
            f"({n} rows)  Direction agreement {l3b_score}/{l4n} scoreable"
        )


def generate_heatmap(results: dict[str, list[dict]]):
    models = list(results.keys())
    n_models = len(models)
    papers = results[models[0]]
    n_papers = len(papers)

    # Build score matrix: rows = papers, cols = models × [L3, L4 agreement]
    fig, axes = plt.subplots(1, n_models, figsize=(4 * n_models + 1, 7), sharey=True)
    if n_models == 1:
        axes = [axes]

    y_labels = [
        f"{r['paper_id']} · {r['method_family'].replace('_',' ')} ({r['difficulty']})"
        for r in papers
    ]

    for ax, model in zip(axes, models):
        rs = results[model]
        data = np.array([[r["L3_method_agree"], r["L4_direction_agree"]] for r in rs], dtype=float)

        cmap = plt.cm.RdYlGn
        im = ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")

        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Method\nAgreement", "Direction\nAgreement"], fontsize=8)
        ax.set_yticks(range(n_papers))
        if ax == axes[0]:
            ax.set_yticklabels(y_labels, fontsize=7.5)
        else:
            ax.set_yticklabels([])

        # Method color strips
        for i, r in enumerate(rs):
            color = METHOD_COLORS.get(r["method_family"], "#888")
            ax.add_patch(plt.Rectangle((-0.6, i - 0.5), 0.1, 1,
                                        color=color, clip_on=False, zorder=5))

        # Cell text
        for i in range(n_papers):
            for j in range(2):
                val = data[i, j]
                txt = "✓" if val == 1 else "✗"
                c = "white" if val == 1 else "#600"
                ax.text(j, i, txt, ha="center", va="center", fontsize=11, color=c,
                        fontweight="bold")

        short = MODEL_SHORT.get(model, model)
        l3a = sum(r["L3_method_agree"] for r in rs)
        l3b = sum(r["L4_direction_agree"] for r in rs)
        ax.set_title(f"{short}\nMethod {l3a}/10 · Direction {l3b}/10",
                     fontsize=9, fontweight="bold")

    # Legend
    legend_patches = [mpatches.Patch(color=c, label=m.replace("_", " "))
                      for m, c in METHOD_COLORS.items()]
    fig.legend(handles=legend_patches, loc="lower center", ncol=4,
               fontsize=8, title="Method Family", title_fontsize=8,
               bbox_to_anchor=(0.5, -0.02))

    fig.suptitle("Experiment A — L3/L4 Text-Level Agreement",
                 fontsize=11, fontweight="bold", y=1.01)
    plt.tight_layout()

    out_path = FIGURES_DIR / "exp_a_auto_scores.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nHeatmap saved → {out_path}")


def export_csv(results: dict[str, list[dict]]):
    import csv, io
    models = list(results.keys())
    rows = []
    for i, row in enumerate(results[models[0]]):
        r = {"paper_id": row["paper_id"], "method": row["method_family"],
             "orig_method": row.get("orig_method_family", ""),
             "difficulty": row["difficulty"],
             "gt_m_level": row.get("gt_m_level", ""),
             "gt_d_level": row.get("gt_d_level", ""),
             "needs_human": int(row.get("needs_human", False)),
             "L3_scoreable": int(row.get("L3_scoreable", False)),
             "L4_scoreable": int(row.get("L4_scoreable", False))}
        for m in models:
            short = MODEL_SHORT.get(m, m)
            mr = results[m][i]
            r[f"{short}_L3_method_agree"] = int(mr["L3_method_agree"])
            r[f"{short}_L4_direction_agree"] = int(mr["L4_direction_agree"])
            # Legacy columns retained for compatibility with existing figures.
            r[f"{short}_L3a"] = int(mr["L3_method_agree"])
            r[f"{short}_L3b"] = int(mr["L4_direction_agree"])
            r[f"{short}_detected"] = mr.get("detected_method", "")
            r[f"{short}_direction"] = mr.get("detected_direction", "")
        rows.append(r)
    out = Path("experiments/exp_a/auto_scores.csv")
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV saved → {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+",
                        default=["moonshot-v1-128k", "claude-sonnet-4-20250514",
                                 "gpt-4o", "o3", "claude-opus-4-6",
                                 "gemini-2.5-flash", "gpt-5"])
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args()

    results = run_scoring(args.models)
    print_table(results)
    generate_heatmap(results)
    if args.csv:
        export_csv(results)


if __name__ == "__main__":
    main()
