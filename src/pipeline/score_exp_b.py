"""
Experiment B — Automated L1-L4 Scorer
=======================================
L1  Task completion    — output file exists, non-empty content
L2a Code present       — R code block extracted from response
L2b Code executable    — R code runs without error (exit code 0)
L3  Method-family agreement (text-level)
L4  Direction agreement (text-level)

Usage:
  python src/pipeline/score_exp_b.py
  python src/pipeline/score_exp_b.py --models moonshot-v1-128k claude-sonnet-4-20250514
  python src/pipeline/score_exp_b.py --csv
  python src/pipeline/score_exp_b.py --execute   # enable L2b execution test
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

SCENARIOS_DIR = Path("experiments/exp_b/scenarios")
OUTPUTS_DIR   = Path("experiments/exp_b/outputs")
FIGURES_DIR   = Path("paper/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

METHOD_KEYWORDS = {
    "DID": [
        r"difference.in.difference", r"\bDID\b", r"diff.in.diff",
        r"parallel trend", r"DiD", r"did\b",
    ],
    "EVENT_STUDY": [
        r"event study", r"event.window", r"abnormal return",
        r"cumulative abnormal", r"\bCAR\b", r"\bAAR\b",
    ],
    "IV": [
        r"instrumental variable", r"\bIV\b(?!\w)", r"two.stage",
        r"\b2SLS\b", r"\binstrument\b", r"first.stage",
    ],
    "RDD": [
        r"regression discontinuity", r"\bRDD\b", r"\bRD\b",
        r"discontinuity", r"running variable", r"bandwidth",
        r"forcing variable", r"cutoff",
    ],
}

DIRECTION_KEYWORDS = {
    "positive": [r"\bpositive\b", r"increase[sd]?", r"higher", r"greater", r"upward", r"\bgain\b"],
    "negative": [r"\bnegative\b", r"decrease[sd]?", r"lower", r"decline[sd]?", r"downward", r"reduc", r"loss"],
}

METHOD_COLORS = {
    "DID":         "#1D9E75",
    "EVENT_STUDY": "#378ADD",
    "IV":          "#7F77DD",
    "RDD":         "#D85A30",
}

MODEL_SHORT = {
    "moonshot-v1-128k":         "Kimi-128k",
    "claude-sonnet-4-20250514": "Claude-Sonnet",
    "gpt-4o":                   "GPT-4o",
}


def extract_r_code(text: str) -> str | None:
    """Return first R code block, or None."""
    m = re.search(r"```r\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    # fallback: ```\n...``` if labelled as plain block
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m and any(kw in m.group(1) for kw in ["library(", "lm(", "read.csv", "<-"]):
        return m.group(1).strip()
    return None


def execute_r_code(code: str, timeout: int = 30) -> tuple[bool, str]:
    """Run R code in a temp file. Returns (success, stderr_snippet)."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".R", mode="w",
                                         delete=False, dir="/tmp") as f:
            f.write(code)
            tmp = f.name
        result = subprocess.run(
            ["Rscript", "--vanilla", tmp],
            capture_output=True, text=True, timeout=timeout,
        )
        os.unlink(tmp)
        ok = result.returncode == 0
        err = result.stderr.strip()[-300:] if result.stderr else ""
        return ok, err
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def detect_method(text: str) -> str | None:
    counts = {}
    for method, patterns in METHOD_KEYWORDS.items():
        hits = sum(len(re.findall(p, text, re.IGNORECASE)) for p in patterns)
        if hits:
            counts[method] = hits
    return max(counts, key=counts.get) if counts else None


def detect_direction(text: str) -> str | None:
    tail = text[len(text) // 2:]
    pos = sum(len(re.findall(p, tail, re.IGNORECASE)) for p in DIRECTION_KEYWORDS["positive"])
    neg = sum(len(re.findall(p, tail, re.IGNORECASE)) for p in DIRECTION_KEYWORDS["negative"])
    if pos == 0 and neg == 0:
        return None
    return "positive" if pos > neg else "negative"


def score_output(scenario: dict, llm_out: dict, execute: bool = False) -> dict:
    content = llm_out["llm_response"]["content"]
    gt = scenario["ground_truth"]
    true_method = scenario["method_family"]
    true_dir    = gt.get("conclusion_direction", "").lower()

    r_code          = extract_r_code(content)
    detected_method = detect_method(content)
    detected_dir    = detect_direction(content)

    l1   = bool(content.strip())
    l2a  = r_code is not None
    l2b  = None   # None = not tested
    l2b_err = ""
    if execute and l2a:
        l2b, l2b_err = execute_r_code(r_code)

    l3 = (detected_method == true_method) if detected_method else False
    l4 = (detected_dir == true_dir) if detected_dir else False

    # l2 (legacy field) = l2a for backward compatibility
    l2 = l2a

    return {
        "scenario_id":        scenario["scenario_id"],
        "method_family":      true_method,
        "difficulty":         scenario["difficulty"],
        "title":              scenario["title"],
        "true_method":        true_method,
        "detected_method":    detected_method,
        "true_direction":     true_dir,
        "detected_direction": detected_dir,
        "r_code_lines":       len(r_code.splitlines()) if r_code else 0,
        "L1_complete":        l1,
        "L2_has_code":        l2a,
        "L2_executable":      l2b,
        "L2b_stderr":         l2b_err,
        "L3_method_agree":    l3,
        "L4_direction_agree": l4,
        # Legacy aliases retained for older tables/figures.
        "L3_strategy":        l3,
        "L4_direction":       l4,
        "all_pass":           l1 and l2 and l3 and l4,
    }


def run_scoring(models: list[str], execute: bool = False) -> dict[str, list[dict]]:
    scenarios = {f.stem: json.loads(f.read_text())
                 for f in sorted(SCENARIOS_DIR.glob("s*.json"))}
    results = {}
    for model in models:
        slug = model.replace("/", "-").replace(":", "-")
        model_res = []
        for sid, sc in sorted(scenarios.items()):
            out_file = OUTPUTS_DIR / f"{sid}_{slug}.json"
            if not out_file.exists():
                model_res.append({
                    "scenario_id": sid, "method_family": sc["method_family"],
                    "difficulty": sc["difficulty"], "title": sc["title"],
                    "L1_complete": False, "L2_has_code": False,
                    "L2_executable": None,
                    "L3_method_agree": False, "L4_direction_agree": False,
                    "L3_strategy": False, "L4_direction": False,
                    "all_pass": False, "detected_method": None,
                    "detected_direction": None, "r_code_lines": 0,
                    "true_method": sc["method_family"],
                    "true_direction": sc["ground_truth"].get("conclusion_direction"),
                })
            else:
                llm_out = json.loads(out_file.read_text())
                model_res.append(score_output(sc, llm_out, execute=execute))
        results[model] = model_res
    return results


def print_table(results: dict[str, list[dict]]):
    models = list(results.keys())
    rows   = results[models[0]]

    print(f"\n{'ID':<6} {'Method':<14} {'Diff':<8}", end="")
    for m in models:
        short = MODEL_SHORT.get(m, m[:14])
        print(f"  {short:<20}", end="")
    print()
    print("-" * (30 + 22 * len(models)))

    for i, row in enumerate(rows):
        print(f"{row['scenario_id']:<6} {row['method_family']:<14} {row['difficulty']:<8}", end="")
        for m in models:
            r = results[m][i]
            flags = ("✅" if r["L1_complete"] else "❌") + \
                    ("✅" if r["L2_has_code"] else "❌") + \
                    ("✅" if r["L3_method_agree"] else "❌") + \
                    ("✅" if r["L4_direction_agree"] else "❌")
            print(f"  {flags} ({r.get('detected_method','?') or '?':>12})", end="")
        print()

    print()
    layers = ["L1_complete", "L2_has_code", "L2_executable", "L3_method_agree", "L4_direction_agree", "all_pass"]
    layer_names = ["L1", "L2a Code", "L2b Exec", "L3 Method", "L4 Direction", "All Pass"]
    for m in models:
        short = MODEL_SHORT.get(m, m)
        rs = results[m]
        scores = []
        for l in layers:
            vals = [r[l] for r in rs if r[l] is not None]
            if not vals:
                scores.append("n/a")
            else:
                scores.append(f"{sum(vals)}/{len(vals)}")
        print(f"{short}: " + "  ".join(f"{n}={s}" for n, s in zip(layer_names, scores)))


def generate_heatmap(results: dict[str, list[dict]]):
    models   = list(results.keys())
    n_models = len(models)
    rows     = results[models[0]]
    n        = len(rows)

    layers      = ["L1_complete", "L2_has_code", "L3_method_agree", "L4_direction_agree"]
    layer_names = ["L1\nComplete", "L2\nCode", "L3\nMethod", "L4\nDirection"]

    fig, axes = plt.subplots(1, n_models, figsize=(4.5 * n_models + 1, 11), sharey=True)
    if n_models == 1:
        axes = [axes]

    y_labels = [
        f"{r['scenario_id']} · {r['method_family'].replace('_',' ')} ({r['difficulty']})"
        for r in rows
    ]

    for ax, model in zip(axes, models):
        rs   = results[model]
        data = np.array([[r[l] for l in layers] for r in rs], dtype=float)

        cmap = plt.cm.RdYlGn
        im   = ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")

        ax.set_xticks(range(4))
        ax.set_xticklabels(layer_names, fontsize=8)
        ax.set_yticks(range(n))
        if ax is axes[0]:
            ax.set_yticklabels(y_labels, fontsize=7)
        else:
            ax.set_yticklabels([])

        # Method color strips
        for i, r in enumerate(rs):
            color = METHOD_COLORS.get(r["method_family"], "#888")
            ax.add_patch(plt.Rectangle((-0.6, i - 0.5), 0.08, 1,
                                        color=color, clip_on=False, zorder=5))

        # Cell text
        for i in range(n):
            for j in range(4):
                val = data[i, j]
                txt = "✓" if val == 1 else "✗"
                c   = "white" if val == 1 else "#700"
                ax.text(j, i, txt, ha="center", va="center",
                        fontsize=9, color=c, fontweight="bold")

        short  = MODEL_SHORT.get(model, model)
        totals = [f"{int(data[:,j].sum())}/30" for j in range(4)]
        ax.set_title(f"{short}\n" + "  ".join(f"{n}={t}" for n, t in zip(layer_names, totals)),
                     fontsize=8.5, fontweight="bold")

    legend_patches = [mpatches.Patch(color=c, label=m.replace("_", " "))
                      for m, c in METHOD_COLORS.items()]
    fig.legend(handles=legend_patches, loc="lower center", ncol=4,
               fontsize=8, title="Method", title_fontsize=8,
               bbox_to_anchor=(0.5, -0.01))

    fig.suptitle("Experiment B — 4-Layer Diagnostic Funnel (100 scenarios)",
                 fontsize=11, fontweight="bold", y=1.01)
    plt.tight_layout()

    out = FIGURES_DIR / "exp_b_funnel_heatmap.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nHeatmap saved → {out}")


def export_csv(results: dict[str, list[dict]]):
    import csv
    models = list(results.keys())
    all_rows = []
    for i, base in enumerate(results[models[0]]):
        row = {"scenario_id": base["scenario_id"],
               "method": base["method_family"],
               "difficulty": base["difficulty"]}
        for m in models:
            short = MODEL_SHORT.get(m, m)
            r = results[m][i]
            for l in ["L1_complete", "L2_has_code", "L3_method_agree", "L4_direction_agree", "all_pass"]:
                row[f"{short}_{l}"] = int(r[l])
            row[f"{short}_L3_strategy"] = int(r["L3_method_agree"])
            row[f"{short}_L4_direction"] = int(r["L4_direction_agree"])
            row[f"{short}_r_lines"] = r["r_code_lines"]
        all_rows.append(row)

    out = Path("experiments/exp_b/auto_scores.csv")
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"CSV saved → {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+",
                        default=["moonshot-v1-128k", "claude-sonnet-4-20250514"])
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--execute", action="store_true",
                        help="Run L2b: execute extracted R code and check exit code")
    args = parser.parse_args()

    results = run_scoring(args.models, execute=args.execute)
    print_table(results)
    generate_heatmap(results)
    if args.csv:
        export_csv(results)


if __name__ == "__main__":
    main()
