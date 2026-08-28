"""
Method-Family Validity Checklists
===================================
Five-item checklists for each of the four causal identification families.
Used by PhD raters to score Layer 3 (identification validity) in Exp A & B.

Layer 3 passes when a paper scores ≥ 4 / 5 items.

Scoring protocol
----------------
Each item is binary: 1 = clearly satisfied, 0 = absent or violated.
Raters score independently; adjudication required when Δ ≥ 1.

Usage
-----
    from src.evaluation.validity_checklists import ValidityScorer

    scorer = ValidityScorer("DID")
    result = scorer.score(
        rater_responses=[1, 1, 1, 0, 1],
        rater_id="rater_1",
        paper_id="paper_03",
        notes="C4 unclear — clustering at state vs bank level"
    )
    print(result["layer3_pass"])   # True (4/5)
"""

import json
import os
from datetime import datetime, timezone

# ── Checklists ────────────────────────────────────────────────────────

CHECKLISTS = {
    "DID": [
        "C1: Treatment and control groups clearly defined and non-overlapping",
        "C2: Treatment is not universally applied (variation in exposure exists)",
        "C3: Pre-treatment parallel trends addressed (visual or statistical test)",
        "C4: Standard errors clustered at the treatment-unit level",
        "C5: No obvious confounding event in the same window",
    ],
    "EVENT_STUDY": [
        "C1: Event date precisely identified with source citation",
        "C2: Event was plausibly unanticipated (or anticipation addressed)",
        "C3: Estimation window and event window clearly specified",
        "C4: No contamination from confounding events in the window",
        "C5: Abnormal return model specified (market model / Fama-French / etc.)",
    ],
    "IV": [
        "C1: Instrument clearly stated and economically motivated",
        "C2: Relevance: first-stage F-statistic reported and > 10",
        "C3: Exclusion restriction discussed (not just asserted)",
        "C4: Instrument is not a direct determinant of the outcome",
        "C5: Reduced-form results reported alongside 2SLS",
    ],
    "RDD": [
        "C1: Running variable and cutoff clearly identified",
        "C2: Manipulation test reported (McCrary density or equivalent)",
        "C3: Bandwidth selection method stated (e.g. MSE-optimal)",
        "C4: Local randomization argument is credible for this cutoff",
        "C5: Robustness to bandwidth and polynomial order checked",
    ],
}

# Aliases
CHECKLISTS["DIFF_IN_DIFF"] = CHECKLISTS["DID"]
CHECKLISTS["DIFFERENCE_IN_DIFFERENCES"] = CHECKLISTS["DID"]
CHECKLISTS["EVENT"] = CHECKLISTS["EVENT_STUDY"]
CHECKLISTS["INSTRUMENTAL_VARIABLES"] = CHECKLISTS["IV"]
CHECKLISTS["REGRESSION_DISCONTINUITY"] = CHECKLISTS["RDD"]

PASS_THRESHOLD = 4  # out of 5

# ── Failure taxonomy ──────────────────────────────────────────────────

FAILURE_TYPES = {
    "IH": "Identification Hallucination — claims a natural experiment / IV / discontinuity that does not exist or whose core assumptions are violated",
    "ME": "Mechanical Execution — code correctly implements a method that is inappropriate for the research setting",
    "NF": "Narrative Fabrication — institutional background is fluent but contains factual errors",
}


class ValidityScorer:

    def __init__(self, method: str, output_dir: str = "evaluation/rater_data"):
        method_key = method.upper().replace(" ", "_").replace("-", "_")
        if method_key not in CHECKLISTS:
            raise ValueError(
                f"Unknown method '{method}'. "
                f"Choose from: {list(CHECKLISTS.keys())}"
            )
        self.method = method_key
        self.checklist = CHECKLISTS[method_key]
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def score(
        self,
        rater_responses: list,
        rater_id: str = "rater_1",
        paper_id: str = "unknown",
        failure_types: list = None,
        id_strategy_score: int | None = None,
        conclusion_score: float | None = None,
        effect_size_score: float | None = None,
        notes: str = "",
        save: bool = True,
    ) -> dict:
        """
        Score one AI output against the method-specific checklist.

        Parameters
        ----------
        rater_responses : list of int  (1 = pass, 0 = fail), length 5
        rater_id        : str
        paper_id        : str
        failure_types   : list of str  subset of ["IH", "ME", "NF"]
        notes           : str          freeform rater notes

        Returns
        -------
        dict with keys: paper_id, method, pass_count, layer3_pass,
                        items, failure_types, id_strategy_score,
                        conclusion_score, effect_size_score, notes
        """
        if len(rater_responses) != 5:
            raise ValueError("rater_responses must have exactly 5 items")
        if not all(r in (0, 1) for r in rater_responses):
            raise ValueError("Each response must be 0 or 1")

        pass_count = sum(rater_responses)
        layer3_pass = pass_count >= PASS_THRESHOLD

        if failure_types is None:
            failure_types = []
        invalid_ft = [f for f in failure_types if f not in FAILURE_TYPES]
        if invalid_ft:
            raise ValueError(f"Unknown failure types: {invalid_ft}. "
                             f"Valid: {list(FAILURE_TYPES)}")
        if id_strategy_score is not None and id_strategy_score not in (0, 1, 2, 3):
            raise ValueError("id_strategy_score must be one of 0, 1, 2, 3")
        if conclusion_score is not None and conclusion_score not in (0.0, 0.5, 1.0):
            raise ValueError("conclusion_score must be one of 0, 0.5, 1")
        if effect_size_score is not None and effect_size_score not in (0.0, 0.5, 1.0):
            raise ValueError("effect_size_score must be one of 0, 0.5, 1")

        result = {
            "paper_id": paper_id,
            "rater_id": rater_id,
            "method": self.method,
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "pass_count": pass_count,
            "total_items": 5,
            "layer3_pass": layer3_pass,
            "items": {
                item: bool(resp)
                for item, resp in zip(self.checklist, rater_responses)
            },
            "failure_types": failure_types,
            "failure_descriptions": {
                ft: FAILURE_TYPES[ft] for ft in failure_types
            },
            "id_strategy_score": id_strategy_score,
            "conclusion_score": conclusion_score,
            "effect_size_score": effect_size_score,
            "notes": notes,
        }

        if save:
            fname = os.path.join(
                self.output_dir,
                f"{paper_id}_{rater_id}.json"
            )
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

        verdict = "PASS" if layer3_pass else "FAIL"
        ft_str = f"  failures={failure_types}" if failure_types else ""
        print(f"[Eval] {paper_id} | {self.method} | {pass_count}/5 | "
              f"Layer3={verdict}{ft_str}")
        return result

    def print_checklist(self):
        print(f"\n{self.method} Validity Checklist")
        print("=" * 50)
        for item in self.checklist:
            print(f"  {item}")
        print(f"\nPass threshold: ≥{PASS_THRESHOLD}/5 items")


# ── Inter-rater reliability ───────────────────────────────────────────

def cohen_kappa(scores_r1: list, scores_r2: list) -> float:
    """
    Cohen's κ for two raters on binary (0/1) items.
    scores_r1, scores_r2: lists of equal length with values in {0, 1}.
    """
    if len(scores_r1) != len(scores_r2):
        raise ValueError("Score lists must have equal length")
    n = len(scores_r1)
    if n == 0:
        return float("nan")

    agree = sum(a == b for a, b in zip(scores_r1, scores_r2))
    po = agree / n

    p1 = sum(scores_r1) / n
    p2 = sum(scores_r2) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)

    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def compute_reliability_report(
    ratings: list,
    target_kappa: float = 0.70,
) -> dict:
    """
    Compute inter-rater reliability across all scored papers.

    ratings : list of dicts, each with keys "paper_id", "rater_id",
              "layer3_pass" (bool), "items" (dict of 5 bools)

    Returns a report dict with overall κ and per-item κ.
    """
    from collections import defaultdict

    by_paper = defaultdict(dict)
    for r in ratings:
        by_paper[r["paper_id"]][r["rater_id"]] = r

    rater_ids = sorted({r["rater_id"] for r in ratings})
    if len(rater_ids) < 2:
        return {"error": "Need at least 2 raters"}

    r1_id, r2_id = rater_ids[0], rater_ids[1]

    binary_r1, binary_r2 = [], []
    item_scores_r1 = [[] for _ in range(5)]
    item_scores_r2 = [[] for _ in range(5)]

    checklist_keys = None

    for pid, rater_map in by_paper.items():
        if r1_id not in rater_map or r2_id not in rater_map:
            continue
        s1 = rater_map[r1_id]
        s2 = rater_map[r2_id]

        binary_r1.append(int(s1["layer3_pass"]))
        binary_r2.append(int(s2["layer3_pass"]))

        if checklist_keys is None:
            checklist_keys = list(s1["items"].keys())

        for i, key in enumerate(checklist_keys):
            item_scores_r1[i].append(int(s1["items"].get(key, 0)))
            item_scores_r2[i].append(int(s2["items"].get(key, 0)))

    overall_kappa = cohen_kappa(binary_r1, binary_r2)
    per_item_kappa = {}
    if checklist_keys:
        for i, key in enumerate(checklist_keys):
            per_item_kappa[key] = cohen_kappa(item_scores_r1[i], item_scores_r2[i])

    report = {
        "n_papers": len(binary_r1),
        "raters": [r1_id, r2_id],
        "overall_kappa": round(overall_kappa, 3),
        "target_kappa": target_kappa,
        "kappa_achieved": overall_kappa >= target_kappa,
        "per_item_kappa": {k: round(v, 3) for k, v in per_item_kappa.items()},
        "note": "κ > 0.70 target for binary screening; κ > 0.65 for per-item",
    }
    return report
