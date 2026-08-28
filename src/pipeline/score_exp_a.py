"""
Experiment A — Scoring & Heatmap Generator
============================================
Loads rater JSON scores and LLM outputs, computes:
  - Inter-rater Cohen's κ
  - 10×3 replication heatmap (Figure 3)
  - Failure taxonomy distribution (Table 1 contribution)

Usage:
  # Score one paper manually (interactive)
  python src/pipeline/score_exp_a.py --score --paper paper_01 --rater rater_1

  # Compute reliability after both raters have scored all 10 papers
  python src/pipeline/score_exp_a.py --reliability

  # Generate heatmap figure
  python src/pipeline/score_exp_a.py --heatmap
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.evaluation.validity_checklists import ValidityScorer, compute_reliability_report

PAPERS_DIR  = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/exp_a/outputs")
RATINGS_DIR = Path("experiments/exp_a/ratings")
RATINGS_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_RATINGS_DIR = Path("evaluation/rater_data")
FIGURES_DIR = Path("paper/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

METHOD_COLORS = {
    "DID":         "#1D9E75",
    "EVENT_STUDY": "#378ADD",
    "IV":          "#7F77DD",
    "RDD":         "#D85A30",
}


def load_rating_files() -> list[Path]:
    files = list(RATINGS_DIR.glob("paper_*_rater_*.json"))
    files += list(RATINGS_DIR.glob("score_paper_*_rater_*.json"))
    if LEGACY_RATINGS_DIR.exists():
        files += list(LEGACY_RATINGS_DIR.glob("paper_*_rater_*.json"))
        files += list(LEGACY_RATINGS_DIR.glob("score_paper_*_rater_*.json"))
    return sorted({f.resolve() for f in files})


def prompt_score(prompt: str, valid_values: tuple[str, ...]) -> str:
    while True:
        val = input(prompt).strip()
        if val in valid_values:
            return val
        print(f"  Please enter one of: {', '.join(valid_values)}")

# ── Interactive scoring ───────────────────────────────────────────────

def interactive_score(paper_id: str, rater_id: str, model: str = "claude-opus-4-20250514"):
    """Walk a rater through scoring one paper interactively."""
    # Load paper metadata
    matches = list(PAPERS_DIR.glob(f"{paper_id}*.json"))
    if not matches:
        print(f"Paper not found: {paper_id}")
        return
    paper = json.loads(matches[0].read_text())
    method = paper["method_family"]

    # Load LLM output
    model_slug = model.replace("/", "-").replace(":", "-")
    out_file = OUTPUTS_DIR / f"{paper_id}_{model_slug}.json"
    if not out_file.exists():
        print(f"LLM output not found: {out_file}")
        print(f"Run: python src/pipeline/run_exp_a.py --paper {paper_id} --model {model}")
        return

    llm_output = json.loads(out_file.read_text())
    ai_text = llm_output["llm_response"]["content"]

    scorer = ValidityScorer(method, output_dir=str(RATINGS_DIR))

    print("\n" + "=" * 65)
    print(f"SCORING: {paper_id}  |  {method}  |  {paper.get('difficulty','')}")
    print(f"Rater: {rater_id}")
    print("=" * 65)
    print("\n--- AI OUTPUT (truncated to first 2000 chars) ---")
    print(ai_text[:2000])
    if len(ai_text) > 2000:
        print(f"\n[... {len(ai_text)-2000} more characters ...]")

    print("\n--- VALIDITY CHECKLIST ---")
    scorer.print_checklist()

    print("\nEnter 1 (pass) or 0 (fail) for each item:")
    responses = []
    for i, item in enumerate(scorer.checklist, 1):
        while True:
            val = input(f"  C{i}: {item[:60]}... [0/1]: ").strip()
            if val in ("0", "1"):
                responses.append(int(val))
                break
            print("  Please enter 0 or 1")

    print("\n--- FAILURE CLASSIFICATION ---")
    print("  IH = Identification Hallucination")
    print("  ME = Mechanical Execution without Understanding")
    print("  NF = Narrative Fabrication")
    ft_input = input("Failure types (comma-separated, or blank if L3 passes): ").strip()
    failure_types = [f.strip().upper() for f in ft_input.split(",") if f.strip()]

    ground_truth = paper.get("ground_truth", {})
    print("\n--- REPLICATION ALIGNMENT SCORING ---")
    print("Score the AI output against the paper's ground truth:")
    print(f"  Ground-truth strategy:  {ground_truth.get('identification_strategy', 'N/A')}")
    print(f"  Ground-truth direction: {ground_truth.get('conclusion_direction', 'N/A')}")
    print(f"  Ground-truth effect:    {ground_truth.get('main_effect', 'N/A')}")
    print("  ID strategy score: 0=wrong, 1=partially related, 2=mostly right, 3=strong match")
    id_strategy_score = int(prompt_score("ID strategy score [0/1/2/3]: ", ("0", "1", "2", "3")))
    print("  Conclusion score: 0=wrong sign/conclusion, 0.5=partially aligned, 1=aligned")
    conclusion_score = float(prompt_score("Conclusion alignment [0/0.5/1]: ", ("0", "0.5", "1")))
    print("  Effect-size score: 0=far off, 0.5=direction right but magnitude off, 1=close")
    effect_size_score = float(prompt_score("Effect-size proximity [0/0.5/1]: ", ("0", "0.5", "1")))

    notes = input("Notes (optional): ").strip()

    result = scorer.score(
        responses,
        rater_id=rater_id,
        paper_id=paper_id,
        failure_types=failure_types,
        id_strategy_score=id_strategy_score,
        conclusion_score=conclusion_score,
        effect_size_score=effect_size_score,
        notes=notes,
        save=True,
    )

    print(f"\nScore saved: {RATINGS_DIR}/{paper_id}_{rater_id}.json")
    return result


# ── Reliability ───────────────────────────────────────────────────────

def compute_reliability():
    rating_files = load_rating_files()
    if not rating_files:
        print(f"No rating files found in {RATINGS_DIR}")
        return

    ratings = [json.loads(Path(f).read_text()) for f in rating_files]
    report = compute_reliability_report(ratings, target_kappa=0.70)
    if "error" in report:
        print(report["error"])
        return report

    print("\n=== Inter-Rater Reliability Report ===")
    print(f"  N papers scored by ≥2 raters: {report['n_papers']}")
    print(f"  Raters: {report['raters']}")
    print(f"  Overall κ (binary Layer 3): {report['overall_kappa']:.3f}  "
          f"{'✓ TARGET MET' if report['kappa_achieved'] else '✗ BELOW TARGET'}")
    print(f"  Target κ: {report['target_kappa']}")
    print("\n  Per-item κ:")
    for item, k in report.get("per_item_kappa", {}).items():
        flag = "✓" if k >= 0.65 else "✗"
        print(f"    {flag} {k:.3f}  {item[:70]}")

    out = RATINGS_DIR / "reliability_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nSaved to {out}")
    return report


# ── Heatmap ───────────────────────────────────────────────────────────

def generate_heatmap(model: str = "claude-opus-4-20250514"):
    """Generate the 10×3 replication heatmap (Figure 3)."""
    papers = sorted(PAPERS_DIR.glob("paper_*.json"))
    if not papers:
        print("No paper JSON files found")
        return

    paper_meta = [json.loads(p.read_text()) for p in papers]
    model_slug = model.replace("/", "-").replace(":", "-")

    # Collect scores (average across raters if multiple)
    from collections import defaultdict
    scores_by_paper = defaultdict(list)
    for f in load_rating_files():
        r = json.loads(Path(f).read_text())
        scores_by_paper[r["paper_id"]].append(r)

    # Build score matrix: rows=papers, cols=[id_strategy, conclusion, effect_size]
    # id_strategy: 0-3, conclusion: 0/0.5/1, effect_size: 0/0.5/1
    # Prefer explicit rater-entered figure scores; fall back to layer3_pass only when
    # older rating files do not include the expanded schema.
    id_scores    = []
    concl_scores = []
    effect_scores = []
    labels = []
    methods = []

    for pm in paper_meta:
        pid = pm["paper_id"]
        method = pm["method_family"]
        labels.append(f"{pid} · {method.replace('_', ' ')}")
        methods.append(method)

        # Load LLM output for conclusion/effect comparison
        out_file = OUTPUTS_DIR / f"{pid}_{model_slug}.json"

        paper_scores = scores_by_paper.get(pid, [])
        if paper_scores:
            explicit_id = [s.get("id_strategy_score") for s in paper_scores
                           if s.get("id_strategy_score") is not None]
            explicit_concl = [s.get("conclusion_score") for s in paper_scores
                              if s.get("conclusion_score") is not None]
            explicit_effect = [s.get("effect_size_score") for s in paper_scores
                               if s.get("effect_size_score") is not None]

            if explicit_id:
                id_s = float(np.mean(explicit_id))
            else:
                avg_pass = np.mean([s["layer3_pass"] for s in paper_scores])
                id_s = float(3 * avg_pass)
            concl_s = float(np.mean(explicit_concl)) if explicit_concl else np.nan
            effect_s = float(np.mean(explicit_effect)) if explicit_effect else np.nan
        else:
            id_s = np.nan
            concl_s = np.nan
            effect_s = np.nan

        id_scores.append(id_s)
        concl_scores.append(concl_s)
        effect_scores.append(effect_s)

    # Plot
    data = np.array([id_scores, concl_scores, effect_scores]).T  # 10×3

    fig, ax = plt.subplots(figsize=(8, 6))
    cmap = plt.cm.Blues
    cmap.set_bad("#EEEDE8")

    # Normalize id_scores to 0-1
    plot_data = data.copy()
    plot_data[:, 0] = plot_data[:, 0] / 3.0  # rescale 0-3 to 0-1

    im = ax.imshow(plot_data, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    # Axis labels
    col_labels = ["ID Strategy\nMatch (0–3)", "Conclusion\nDirection", "Effect Size\nProximity"]
    ax.set_xticks(range(3))
    ax.set_xticklabels(col_labels, fontsize=9)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)

    # Method color strips
    for i, m in enumerate(methods):
        color = METHOD_COLORS.get(m, "#888")
        ax.add_patch(plt.Rectangle((-0.55, i - 0.5), 0.08, 1,
                                    color=color, clip_on=False, zorder=5))

    # Cell text
    for i in range(len(paper_meta)):
        for j in range(3):
            val = data[i, j]
            if np.isnan(val):
                txt, c = "—", "#888780"
            else:
                txt = f"{val:.1f}" if j == 0 else f"{val:.2f}"
                c = "white" if plot_data[i, j] > 0.5 else "#333"
            ax.text(j, i, txt, ha="center", va="center", fontsize=9, color=c)

    # Legend
    legend_patches = [mpatches.Patch(color=c, label=m.replace("_", " "))
                      for m, c in METHOD_COLORS.items()]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=8,
              title="Method", title_fontsize=8)
    plt.colorbar(im, ax=ax, label="Normalized score", shrink=0.6)

    pending_count = sum(np.isnan(d) for d in id_scores)
    ax.set_title(
        f"Experiment A · Replication Heatmap\n"
        f"Model: {model}  |  {len(paper_meta)-pending_count}/{len(paper_meta)} papers scored",
        fontsize=9.5, fontweight="bold"
    )

    plt.tight_layout()
    out_path = FIGURES_DIR / "replication_heatmap.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Heatmap saved to {out_path}")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--score", action="store_true",
                        help="Interactively score one paper")
    parser.add_argument("--paper", type=str, default="paper_01")
    parser.add_argument("--rater", type=str, default="rater_1")
    parser.add_argument("--model", type=str, default="claude-opus-4-20250514")
    parser.add_argument("--reliability", action="store_true",
                        help="Compute inter-rater reliability")
    parser.add_argument("--heatmap", action="store_true",
                        help="Generate replication heatmap")
    args = parser.parse_args()

    if args.score:
        interactive_score(args.paper, args.rater, args.model)
    elif args.reliability:
        compute_reliability()
    elif args.heatmap:
        generate_heatmap(args.model)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
