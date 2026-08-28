"""
Experiment A — Human Scoring Interface
=======================================
Shows LLM output for each paper, walks rater through a structured rubric,
saves scores to experiments/exp_a/human_ratings/.

Scoring rubric (matches proposal):
  ID Strategy: 3=exact, 2=same family, 1=related logic, 0=different
  Direction:   1=correct sign, 0.5=correct but insignificant, 0=wrong
  Failure type: IH / ME / NF / None

Produces Cohen's κ report when ≥2 raters have scored all papers.

Usage:
  # Score as rater_1 using Kimi outputs
  python src/pipeline/human_score_exp_a.py --rater rater_1 --model moonshot-v1-128k

  # Score as rater_2 using Claude outputs
  python src/pipeline/human_score_exp_a.py --rater rater_2 --model claude-sonnet-4-20250514

  # Inter-rater reliability report
  python src/pipeline/human_score_exp_a.py --kappa
"""

import argparse
import json
import sys
from pathlib import Path

PAPERS_DIR   = Path("experiments/exp_a/papers")
OUTPUTS_DIR  = Path("experiments/exp_a/outputs")
RATINGS_DIR  = Path("experiments/exp_a/human_ratings")
RATINGS_DIR.mkdir(parents=True, exist_ok=True)

PAPER_REFS = {
    "paper_01": "Ivashina & Scharfstein (2010, JF)",
    "paper_02": "Duchin & Sosyura (2014, JFE)",
    "paper_03": "Cornaggia et al. (2015, JF)",
    "paper_04": "Bernanke & Kuttner (2005, JF)",
    "paper_05": "Karpoff, Lee & Martin (2008, JFE)",
    "paper_06": "Ahern & Harford (2014, JF)",
    "paper_07": "Greenstone, Mas & Nguyen (2020, JF)",
    "paper_08": "Becker & Ivashina (2014, JFE)",
    "paper_09": "Cunat, Gine & Guadalupe (2012, JF)",
    "paper_10": "Fang, Tian & Tice (2014, JF)",
}


def ask_int(prompt: str, choices: list[int]) -> int:
    while True:
        try:
            val = int(input(prompt).strip())
            if val in choices:
                return val
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"  → Please enter one of {choices}")


def ask_float(prompt: str, choices: list[float]) -> float:
    while True:
        try:
            val = float(input(prompt).strip())
            if val in choices:
                return val
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"  → Please enter one of {choices}")


def score_paper(paper: dict, llm_output: dict, rater_id: str) -> dict:
    pid      = paper["paper_id"]
    method   = paper["method_family"]
    diff     = paper["difficulty"]
    gt       = paper["ground_truth"]
    content  = llm_output["llm_response"]["content"]

    print("\n" + "=" * 70)
    print(f"PAPER: {pid}  |  {PAPER_REFS.get(pid, pid)}")
    print(f"Method family: {method}  |  Difficulty: {diff}")
    print(f"Rater: {rater_id}")
    print("=" * 70)

    print("\n── GROUND TRUTH ──")
    print(f"  Strategy : {gt['identification_strategy']}")
    print(f"  Direction: {gt['conclusion_direction']}")
    print(f"  Detail   : {gt['conclusion_detail']}")

    print("\n── LLM OUTPUT (first 2500 chars) ──")
    print(content[:2500])
    if len(content) > 2500:
        print(f"\n[... {len(content)-2500} more chars — press Enter to continue ...]")
        input()
        print(content[2500:])

    print("\n── SCORING ──")
    print("ID Strategy match:")
    print("  3 = Exact method (DID/Event Study/IV/RDD) correctly identified")
    print("  2 = Same broad family (e.g., says 'regression discontinuity' for RDD)")
    print("  1 = Related logic but different method name")
    print("  0 = Wrong method / no clear identification strategy")
    id_score = ask_int("  Score [0/1/2/3]: ", [0, 1, 2, 3])

    print("\nConclusion direction:")
    print("  1   = Correct sign")
    print("  0.5 = Correct sign but stated as insignificant")
    print("  0   = Wrong sign or contradicts ground truth")
    dir_score = ask_float("  Score [0/0.5/1]: ", [0.0, 0.5, 1.0])

    print("\nFailure classification (if any):")
    print("  IH  = Identification Hallucination (wrong/invalid strategy)")
    print("  ME  = Mechanical Execution (code correct but method inappropriate)")
    print("  NF  = Narrative Fabrication (plausible but factually wrong context)")
    print("  none = No failure")
    ft_raw = input("  Failures (comma-separated, e.g. IH,ME or none): ").strip().upper()
    failure_types = [] if ft_raw in ("", "NONE") else [f.strip() for f in ft_raw.split(",")]

    notes = input("Notes (optional, press Enter to skip): ").strip()

    result = {
        "paper_id": pid,
        "rater_id": rater_id,
        "model":    llm_output["model"],
        "method_family": method,
        "difficulty": diff,
        "id_strategy_score": id_score,
        "direction_score":   dir_score,
        "failure_types":     failure_types,
        "l3_pass": id_score >= 2,   # ≥2 = same family or better
        "notes": notes,
    }
    return result


def run_scoring(rater_id: str, model: str, resume: bool = True):
    papers = sorted(PAPERS_DIR.glob("paper_*.json"))
    slug   = model.replace("/", "-").replace(":", "-")

    print(f"\nStarting scoring session: rater={rater_id}, model={model}")
    print(f"Ratings will be saved to: {RATINGS_DIR}/\n")

    all_results = []
    for p in papers:
        paper    = json.loads(p.read_text())
        pid      = paper["paper_id"]
        out_file = OUTPUTS_DIR / f"{pid}_{slug}.json"
        if not out_file.exists():
            print(f"[SKIP] {pid} — no LLM output found for {model}")
            continue

        # Resume: skip already-rated papers
        rating_file = RATINGS_DIR / f"{pid}_{rater_id}_{slug}.json"
        if rating_file.exists() and resume:
            print(f"[SKIP] {pid} already rated by {rater_id}")
            all_results.append(json.loads(rating_file.read_text()))
            continue

        llm_output = json.loads(out_file.read_text())
        result     = score_paper(paper, llm_output, rater_id)

        rating_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"  → Saved: {rating_file.name}")
        all_results.append(result)

        cont = input("\nContinue to next paper? [Enter=yes, q=quit]: ").strip().lower()
        if cont == "q":
            break

    print(f"\nSession complete. {len(all_results)} papers scored.")
    return all_results


def compute_kappa(rater_a: str, rater_b: str, model: str):
    """Cohen's kappa on binary L3 pass/fail."""
    slug = model.replace("/", "-").replace(":", "-")
    papers = sorted(PAPERS_DIR.glob("paper_*.json"))

    a_scores, b_scores = {}, {}
    for p in papers:
        pid = json.loads(p.read_text())["paper_id"]
        fa  = RATINGS_DIR / f"{pid}_{rater_a}_{slug}.json"
        fb  = RATINGS_DIR / f"{pid}_{rater_b}_{slug}.json"
        if fa.exists():
            a_scores[pid] = json.loads(fa.read_text())["l3_pass"]
        if fb.exists():
            b_scores[pid] = json.loads(fb.read_text())["l3_pass"]

    common = sorted(set(a_scores) & set(b_scores))
    if len(common) < 2:
        print(f"Not enough co-rated papers ({len(common)}). Need ≥2.")
        return

    a = [int(a_scores[p]) for p in common]
    b = [int(b_scores[p]) for p in common]
    n = len(common)

    # Cohen's kappa
    agree  = sum(ai == bi for ai, bi in zip(a, b))
    p_obs  = agree / n
    p_a1   = sum(a) / n
    p_b1   = sum(b) / n
    p_exp  = p_a1 * p_b1 + (1 - p_a1) * (1 - p_b1)
    kappa  = (p_obs - p_exp) / (1 - p_exp) if p_exp < 1 else 1.0

    print(f"\n── Inter-Rater Reliability: {rater_a} vs {rater_b} ──")
    print(f"  N co-rated papers: {n}")
    print(f"  P(observed agreement): {p_obs:.3f}")
    print(f"  P(expected agreement): {p_exp:.3f}")
    print(f"  Cohen's κ: {kappa:.3f}  {'✓ TARGET MET (>0.7)' if kappa>0.7 else '✗ Below target'}")

    print(f"\n  Per-paper comparison:")
    for pid in common:
        a_val = a_scores[pid]
        b_val = b_scores[pid]
        agree_flag = "✓" if a_val == b_val else "✗"
        print(f"    {agree_flag} {pid}: {rater_a}={'pass' if a_val else 'fail'}  "
              f"{rater_b}={'pass' if b_val else 'fail'}")

    # Save report
    report = {
        "raters": [rater_a, rater_b], "model": model,
        "n_papers": n, "p_observed": p_obs, "p_expected": p_exp,
        "kappa": kappa, "target_kappa": 0.70,
        "kappa_achieved": kappa >= 0.70,
        "paper_detail": {p: {"rater_a": a_scores[p], "rater_b": b_scores[p]}
                         for p in common},
    }
    out = RATINGS_DIR / f"kappa_{rater_a}_{rater_b}_{slug}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\n  Report saved → {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rater",  type=str)
    parser.add_argument("--model",  type=str, default="moonshot-v1-128k")
    parser.add_argument("--kappa",  action="store_true")
    parser.add_argument("--rater_a", type=str, default="rater_1")
    parser.add_argument("--rater_b", type=str, default="rater_2")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    if args.kappa:
        compute_kappa(args.rater_a, args.rater_b, args.model)
    elif args.rater:
        run_scoring(args.rater, args.model, resume=not args.no_resume)
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python src/pipeline/human_score_exp_a.py --rater rater_1 --model moonshot-v1-128k")
        print("  python src/pipeline/human_score_exp_a.py --kappa --rater_a rater_1 --rater_b rater_2")


if __name__ == "__main__":
    main()
