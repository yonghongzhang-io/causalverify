#!/usr/bin/env python3
"""
A2 Task 2.2.1+ — Leave-One-Model-Out (LOO) GT robustness analysis.

For each annotator model in {opus_4_7, gpt4o, kimi, gemini}, construct
an alternative ground truth by dropping that annotator and re-aggregating
the remaining 3 votes. Produce:

  Task 2.2.1 — 5 GT versions (Full + 4 LOO) written to audit/gt_loo/.
  Task 2.2.2 — "own-family vs other-family LOO" L3/L4 delta per evaluated
               model (requires a scoring file with per-paper labels —
               see `--scoring` flag).
  Task 2.2.3 — 7-model × 5-GT Kendall tau matrix for ranking stability.
  Task 2.2.5 — Conclusion-flip rate: how many papers get a different
               method or direction label across GT versions.

Does NOT call any LLM APIs. Uses only audit/gt_reextract_multi.json
(the weak-deleak 4-LLM votes already on disk).

Usage:
    python3 scripts/gt_loo_analysis.py                     # full run
    python3 scripts/gt_loo_analysis.py --no-score          # skip scoring
    python3 scripts/gt_loo_analysis.py --verbose

Outputs:
    audit/gt_loo/                            (5 GT variant JSONs)
    audit/gt_loo/flip_matrix.csv             (per-paper label changes)
    audit/gt_loo/ranking_stability.csv       (model × GT-version pass rates)
    paper/tables/loo_ranking_correlations.tex
    paper/figures/loo_robustness_heatmap.pdf
    experiments_log/runs/YYYY-MM-DD/NNN__a2_gt_loo_analysis/
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOTES_IN = ROOT / "audit/gt_reextract_multi.json"
LOO_DIR = ROOT / "audit/gt_loo"
FLIP_CSV = LOO_DIR / "flip_matrix.csv"
STABILITY_CSV = LOO_DIR / "ranking_stability.csv"
OUT_TEX = ROOT / "paper/tables/loo_ranking_correlations.tex"

sys.path.insert(0, str(ROOT / "src"))
from labnotebook.experiment_logger import ExperimentLogger

ANNOTATORS = ["opus_4_7", "gpt4o", "kimi", "gemini"]

# Mapping from evaluated-model "family" to annotator key.
# Used for "own-family vs other-family LOO" analysis (Task 2.2.2).
MODEL_FAMILY = {
    "Opus":   "opus_4_7",     # evaluated Opus 4.6; same vendor as annotator Opus 4.7
    "Sonnet": "opus_4_7",     # also Anthropic
    "GPT-4o": "gpt4o",
    "GPT-5":  "gpt4o",        # OpenAI family
    "o3":     "gpt4o",        # OpenAI family
    "Kimi":   "kimi",
    "Gemini": "gemini",
}


# ---------------------------------------------------------- aggregation

def _majority(votes: list[str | None]) -> str | None:
    """Return majority element, or None if tie / no clear winner."""
    votes = [v for v in votes if v]
    if not votes:
        return None
    c = Counter(votes)
    top, top_n = c.most_common(1)[0]
    # Require strict plurality; ties return None
    second_n = c.most_common(2)[1][1] if len(c) > 1 else 0
    if top_n > second_n:
        return top
    return None


def aggregate_gt(rows: list[dict], annotators: list[str]) -> dict:
    """Aggregate votes from the given set of annotators.

    Each row in gt_reextract_multi.json looks like:
        {"paper_id": ..., "opus_4_7": {"method": "...", "direction": "..."},
         "gpt4o": {"method": "...", "direction": "..."}, ...}
    """
    out = {}
    for r in rows:
        pid = r["paper_id"]
        m_votes = [(r.get(a) or {}).get("method") for a in annotators]
        d_votes = [(r.get(a) or {}).get("direction") for a in annotators]
        out[pid] = {
            "method":   _majority(m_votes),
            "direction": _majority(d_votes),
            "n_annotators": sum(1 for v in m_votes if v),
        }
    return out


# ---------------------------------------------------------- LOO generation

def generate_loo_variants(rows: list[dict]) -> dict[str, dict]:
    """Return {variant_name: {paper_id: labels}} for Full + 4 LOO variants."""
    variants = {
        "full_4": aggregate_gt(rows, ANNOTATORS),
    }
    for dropped in ANNOTATORS:
        remaining = [a for a in ANNOTATORS if a != dropped]
        variants[f"loo_drop_{dropped}"] = aggregate_gt(rows, remaining)
    return variants


# ---------------------------------------------------------- flip analysis

def flip_matrix(variants: dict[str, dict]) -> list[dict]:
    """Per-paper table: does the label change across GT variants?"""
    pids = sorted(variants["full_4"].keys(),
                  key=lambda p: int(p.split("_")[1]))
    rows = []
    for pid in pids:
        row = {"paper_id": pid}
        for v_name, v in variants.items():
            row[f"{v_name}_method"]    = v.get(pid, {}).get("method") or ""
            row[f"{v_name}_direction"] = v.get(pid, {}).get("direction") or ""
        # Count distinct non-null method labels across variants
        methods = {v.get(pid, {}).get("method")
                   for v in variants.values()
                   if v.get(pid, {}).get("method")}
        directions = {v.get(pid, {}).get("direction")
                      for v in variants.values()
                      if v.get(pid, {}).get("direction")}
        row["method_flips"]    = len(methods) - 1       # 0 = stable
        row["direction_flips"] = len(directions) - 1
        rows.append(row)
    return rows


def flip_summary(flip_rows: list[dict]) -> dict:
    n = len(flip_rows)
    method_flip_n    = sum(1 for r in flip_rows if r["method_flips"]    > 0)
    direction_flip_n = sum(1 for r in flip_rows if r["direction_flips"] > 0)
    return {
        "n_papers":               n,
        "method_flipped":         method_flip_n,
        "method_flip_rate":       round(method_flip_n / n, 3) if n else 0,
        "direction_flipped":      direction_flip_n,
        "direction_flip_rate":    round(direction_flip_n / n, 3) if n else 0,
    }


# ---------------------------------------------------------- scoring

def load_scoring(path: Path) -> list[dict] | None:
    """Load a scoring CSV. Expected cols: paper_id, model, method (LLM-proposed), direction."""
    if not path.exists():
        return None
    with path.open() as f:
        return list(csv.DictReader(f))


def pass_rates_by_variant(
    scoring: list[dict],
    variants: dict[str, dict],
    axis: str,
) -> dict[tuple[str, str], float]:
    """For each (model, variant), fraction of scoring rows matching variant GT on `axis`."""
    rates: dict[tuple[str, str], float] = {}
    models = sorted({r["model"] for r in scoring})
    for m in models:
        subset = [r for r in scoring if r["model"] == m]
        for v_name, v in variants.items():
            matched = 0
            total = 0
            for r in subset:
                pid = r["paper_id"]
                gt = v.get(pid, {}).get(axis)
                if not gt:
                    continue       # skip papers without a majority GT
                total += 1
                if (r.get(axis) or "").strip() == gt:
                    matched += 1
            rates[(m, v_name)] = round(matched / total, 4) if total else float("nan")
    return rates


def kendall_tau(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return float("nan")
    c = d = 0
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            s = (x[i] - x[j]) * (y[i] - y[j])
            if s > 0: c += 1
            elif s < 0: d += 1
    total = len(x) * (len(x) - 1) / 2
    return (c - d) / total if total else float("nan")


def ranking_correlations(
    rates: dict[tuple[str, str], float],
) -> dict[tuple[str, str], float]:
    """Kendall tau between every pair of GT variants, over the shared model set."""
    models = sorted({m for m, _ in rates.keys()})
    variants = sorted({v for _, v in rates.keys()})
    out = {}
    for va, vb in combinations(variants, 2):
        xa = [rates.get((m, va), float("nan")) for m in models]
        xb = [rates.get((m, vb), float("nan")) for m in models]
        # skip NaN-polluted entries
        pairs = [(a, b) for a, b in zip(xa, xb)
                 if a == a and b == b]           # not NaN
        if len(pairs) < 2:
            out[(va, vb)] = float("nan")
            continue
        xa_clean = [p[0] for p in pairs]
        xb_clean = [p[1] for p in pairs]
        out[(va, vb)] = kendall_tau(xa_clean, xb_clean)
    return out


# ---------------------------------------------------------- LaTeX table

def write_ranking_table(
    rates: dict[tuple[str, str], float],
    taus: dict[tuple[str, str], float],
    tex_path: Path,
) -> None:
    models = sorted({m for m, _ in rates.keys()})
    variants = ["full_4"] + [f"loo_drop_{a}" for a in ANNOTATORS]

    lines = [
        "% Auto-generated by scripts/gt_loo_analysis.py",
        "% Module 2.2 · LOO ranking stability (Task 2.2.3)",
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\caption{Per-model L3 pass rate under each ground-truth variant. "
        "`full\\_4' uses all four annotators; `loo\\_drop\\_X' drops "
        "annotator X and re-aggregates the remaining three. "
        "Kendall's $\\tau$ between each LOO variant's model ranking and "
        "the full-4 ranking is reported at the bottom.}",
        "\\label{tab:loo-ranking}",
        "\\begin{tabular}{l" + "c" * len(variants) + "}",
        "\\toprule",
        "Model & " + " & ".join(
            v.replace("loo_drop_", "$\\setminus$").replace("_", "\\_").replace("full\\_4", "Full")
            for v in variants) + " \\\\",
        "\\midrule",
    ]
    # Sort models by full_4 pass rate descending
    models.sort(key=lambda m: -rates.get((m, "full_4"), 0))
    for m in models:
        cells = " & ".join(
            (f"{rates[(m, v)]*100:.1f}\\%" if (m, v) in rates and rates[(m, v)] == rates[(m, v)]
             else "---")
            for v in variants)
        lines.append(f"{m} & {cells} \\\\")
    lines.append("\\midrule")
    # Tau row against full_4
    kr = ["$1.00$"]   # full_4 vs itself
    for v in variants[1:]:
        tau = taus.get(("full_4", v)) or taus.get((v, "full_4"))
        kr.append(f"${tau:.2f}$" if tau is not None and tau == tau else "---")
    lines.append("Kendall $\\tau$ vs Full & " + " & ".join(kr) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scoring", type=Path, default=None,
                    help="CSV with columns {paper_id, model, method, direction}; "
                         "if absent, skip ranking-stability analysis.")
    ap.add_argument("--no-score", action="store_true",
                    help="Skip scoring-based analysis entirely.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    exp = ExperimentLogger(
        run_name="a2_gt_loo_analysis",
        script_path=__file__,
        hypothesis=(
            "Dropping any single annotator from the 4-LLM GT aggregation "
            "changes canonical method labels on fewer than 15% of papers "
            "and preserves the 6-model ranking with Kendall tau >= 0.85 "
            "vs the full-4 ranking."
        ),
        config={
            "annotators":     ANNOTATORS,
            "votes_input":    str(VOTES_IN.relative_to(ROOT)),
            "scoring_input":  str(args.scoring) if args.scoring else None,
            "tie_rule":       "strict plurality; tie returns None",
        },
    )

    # Step 1: load votes, build 5 variants
    rows = json.loads(VOTES_IN.read_text())
    exp.log_event("loaded_votes", n_papers=len(rows))

    variants = generate_loo_variants(rows)
    LOO_DIR.mkdir(parents=True, exist_ok=True)
    for name, v in variants.items():
        (LOO_DIR / f"{name}.json").write_text(
            json.dumps(v, indent=2, ensure_ascii=False)
        )
        exp.log_event("wrote_variant", name=name, n_papers=len(v))

    # Step 2: flip matrix + summary
    flips = flip_matrix(variants)
    with FLIP_CSV.open("w", newline="") as f:
        if flips:
            w = csv.DictWriter(f, fieldnames=list(flips[0].keys()))
            w.writeheader()
            w.writerows(flips)
    flip_stats = flip_summary(flips)
    exp.attach_output("flip_matrix", FLIP_CSV)

    print("=== LOO variants built ===")
    for name, v in variants.items():
        methods = sum(1 for r in v.values() if r["method"])
        dirs = sum(1 for r in v.values() if r["direction"])
        print(f"  {name:<22} method_labeled={methods:>3}/{len(v)}  "
              f"direction_labeled={dirs:>3}/{len(v)}")
    print()
    print("=== Label flip summary ===")
    print(f"  papers with method label changing across variants:    "
          f"{flip_stats['method_flipped']} / {flip_stats['n_papers']}  "
          f"({flip_stats['method_flip_rate']*100:.1f}%)")
    print(f"  papers with direction label changing across variants: "
          f"{flip_stats['direction_flipped']} / {flip_stats['n_papers']}  "
          f"({flip_stats['direction_flip_rate']*100:.1f}%)")

    # Step 3: ranking stability (requires scoring)
    rates_out = None
    taus = None
    if not args.no_score:
        scoring = None
        if args.scoring:
            scoring = load_scoring(args.scoring)
        if scoring is None:
            print()
            print("Scoring-based ranking-stability analysis SKIPPED "
                  "(no scoring CSV provided).")
            print("Re-run with --scoring path/to/L3_scores.csv once "
                  "Phase 4 scoring is refactored.")
        else:
            rates = pass_rates_by_variant(scoring, variants, axis="method")
            rates_out = rates
            taus = ranking_correlations(rates)
            write_ranking_table(rates, taus, OUT_TEX)
            exp.attach_output("ranking_tex", OUT_TEX)

            # Also write long-format CSV
            with STABILITY_CSV.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["model", "gt_variant", "pass_rate"])
                for (m, v), r in rates.items():
                    w.writerow([m, v, r])
            exp.attach_output("stability_csv", STABILITY_CSV)

            print()
            print("=== Ranking stability (L3 pass rate × GT variant) ===")
            variant_order = ["full_4"] + [f"loo_drop_{a}" for a in ANNOTATORS]
            models = sorted({m for m, _ in rates.keys()},
                            key=lambda m: -rates.get((m, "full_4"), 0))
            header = f"{'model':<10} " + " ".join(f"{v[:12]:>13}" for v in variant_order)
            print(header)
            for m in models:
                row = " ".join(
                    f"{rates.get((m, v), float('nan'))*100:>12.1f}%"
                    for v in variant_order
                )
                print(f"{m:<10} {row}")
            print()
            print("Kendall tau vs Full:")
            for v in variant_order[1:]:
                t = taus.get(("full_4", v)) or taus.get((v, "full_4"))
                print(f"  {v:<22} tau = {t:+.3f}" if t is not None and t == t
                      else f"  {v:<22} tau = nan")

    exp.finish(
        status="success",
        results={
            "n_papers":               len(rows),
            "flip_stats":             flip_stats,
            "variants_written":       list(variants.keys()),
            "scoring_used":           bool(rates_out),
            "min_tau_vs_full":        (
                round(min((t for k, t in (taus or {}).items()
                           if "full_4" in k and t == t), default=float("nan")), 3)
                if taus else None
            ),
        },
        interpretation=(
            f"Label-flip rate: {flip_stats['method_flip_rate']*100:.1f}% on method, "
            f"{flip_stats['direction_flip_rate']*100:.1f}% on direction. "
            + ("Ranking stability analysis is pending: re-run with --scoring "
               "once Phase 4 scoring refactor is complete (Module 4.1)."
               if not rates_out else
               "See LaTeX table for per-model ranking.")
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
