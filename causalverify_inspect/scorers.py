"""Scorers wrapping the repository's scoring functions.

Nothing here re-implements a scoring rule. Each scorer builds the
``{"llm_response": {"content": ...}}`` record the pipeline scripts consume,
calls the pipeline function, and copies its booleans into a dict-valued Inspect
``Score`` (the full pipeline row is kept in ``Score.metadata``):

===========================  =========================================================
Inspect score key            Pipeline source
===========================  =========================================================
Experiment A
  L1_complete, L3_scoreable,  ``auto_score_exp_a.score_output`` (L1 / L3 method-family
  L3_method_agree,            / L4 direction agreement, text-level, section-aware)
  L4_scoreable, L4_direction_agree
  S1_latter_half_match,       ``multi_scorer_l4.s1_latter_half`` / ``s2_section6_keyword``
  S2_section6_match           + the ``*_match`` rule of ``multi_scorer_l4.run_scoring``
Experiment B
  L1, L2a, L2b, L2b_plus,     ``score_l2b_plus.score_output`` (R code extracted, executed
  baseline_available,         in the Inspect sandbox, coefficient extracted, compared with
  coefficient_extracted       the DGP or canonical baseline within ``tolerance``)
  L3_method_agree,            ``score_exp_b.score_output(execute=False)`` (text-level)
  L4_direction_agree
  S1_latter_half_match,       as above, against ``dgp_truth.direction``
  S2_section6_match           (``head_to_head_ranking.compute_exp_b_l4_rates``)
  L2b_plus_judge, L2b_plus_v2 optional LLM judge + event-study-aware rule (``judge.py``)
===========================  =========================================================
"""

from __future__ import annotations

from typing import Any

from inspect_ai.model import get_model
from inspect_ai.scorer import Score, Scorer, Target, grouped, scorer
from inspect_ai.solver import TaskState

from causalverify_inspect._repo import decode_target
from causalverify_inspect.execution import execute_r_code_in_sandbox
from causalverify_inspect.judge import (
    DEFAULT_JUDGE_MODEL,
    JUDGE_ROLE,
    judge_l2b_plus,
    judge_treatment_effect,
)
from causalverify_inspect.metrics import (
    NOT_APPLICABLE,
    exp_a_summary,
    exp_b_summary,
    level_rate,
)
from src.pipeline import auto_score_exp_a as exp_a_scoring
from src.pipeline import score_exp_b as exp_b_text_scoring
from src.pipeline import score_l2b_plus as l2b_plus
from src.pipeline.multi_scorer_l4 import s1_latter_half, s2_section6_keyword

STDOUT_EXCERPT_CHARS = 400  # as score_l2b_plus.score_output's stdout_excerpt


def _completion(state: TaskState) -> str:
    return state.output.completion if state.output is not None else ""


def _llm_output(content: str) -> dict:
    """The record shape ``experiments/*/outputs/*.json`` has and the scorers read."""
    return {"llm_response": {"content": content}}


def l4_match(pred: str | None, gt_direction: str) -> int:
    """``multi_scorer_l4.run_scoring``: match iff the prediction is a direction and equals the target."""
    return int(pred == gt_direction) if pred in ("positive", "negative") else 0


def s1_s2_values(content: str, gt_direction: str) -> tuple[dict[str, float], dict[str, str]]:
    """S1/S2 match flags (NaN when the pipeline would have no row, i.e. empty output)."""
    if not content:
        return (
            {"S1_latter_half_match": NOT_APPLICABLE, "S2_section6_match": NOT_APPLICABLE},
            {"S1_latter_half_pred": "", "S2_section6_pred": ""},
        )
    s1 = s1_latter_half(content, gt_direction)
    s2 = s2_section6_keyword(content, gt_direction)
    return (
        {"S1_latter_half_match": l4_match(s1, gt_direction), "S2_section6_match": l4_match(s2, gt_direction)},
        {"S1_latter_half_pred": s1 or "", "S2_section6_pred": s2 or ""},
    )


# ── Experiment A ─────────────────────────────────────────────────────────────


@scorer(metrics=[exp_a_summary()])
def exp_a_text_scorer() -> Scorer:
    """Experiment A text-level layers: L1, L3 (method family), L4 (direction), S1/S2.

    Calls ``auto_score_exp_a.score_output`` with the paper record stored in the
    sample metadata and the consensus target stored in ``Sample.target``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        content = _completion(state)
        gt = decode_target(target)
        paper = state.metadata["paper"]

        row = exp_a_scoring.score_output(paper, gt, _llm_output(content))
        gt_direction = gt.get("direction") or ""
        s_values, s_preds = s1_s2_values(content, gt_direction)

        value: dict[str, Any] = {
            "L1_complete": int(row["L1_complete"]),
            "L3_scoreable": int(row["L3_scoreable"]),
            "L3_method_agree": int(row["L3_method_agree"]),
            "L4_scoreable": int(row["L4_scoreable"]),
            "L4_direction_agree": int(row["L4_direction_agree"]),
            **s_values,
        }
        detected = f"method={row['detected_method'] or 'none'}, direction={row['detected_direction'] or 'none'}"
        explanation = (
            f"L1={value['L1_complete']} "
            f"L3={value['L3_method_agree']} (scoreable={value['L3_scoreable']}) "
            f"L4={value['L4_direction_agree']} (scoreable={value['L4_scoreable']}); detected {detected}"
        )
        return Score(
            value=value,
            answer=detected,
            explanation=explanation,
            metadata={"pipeline_row": row, **s_preds},
        )

    return score


# ── Experiment B ─────────────────────────────────────────────────────────────


@scorer(
    metrics=[
        exp_b_summary(),
        grouped(level_rate("L2b"), "method_family", all=False, name_template="L2b_rate_{group_name}"),
        grouped(level_rate("L2b_plus"), "method_family", all=False, name_template="L2b_plus_rate_{group_name}"),
    ]
)
def exp_b_execution_scorer(
    tolerance: float = l2b_plus.DEFAULT_TOL,
    baseline: str = "canonical",
    judge: bool = False,
    r_timeout: int = 60,
) -> Scorer:
    """Experiment B execution-grounded layers L1, L2a, L2b, L2b+ (plus text-level L3/L4, S1/S2).

    Args:
      tolerance: relative-error tolerance for L2b+ (paper: 0.5).
      baseline: ``"canonical"`` (canonical estimator on the realised data, the
        paper's headline) or ``"dgp"`` (ideal DGP parameter).
      judge: also run the LLM-judge coefficient extraction and the
        event-study-aware rule on every output whose code ran. Uses the Inspect
        ``grader`` model role (``--model-role grader=...``), defaulting to the
        paper's judge model.
      r_timeout: seconds allowed for ``Rscript`` (paper: 60).
    """

    async def score(state: TaskState, target: Target) -> Score:
        content = _completion(state)
        tgt = decode_target(target)
        scenario = dict(state.metadata["scenario"])
        scenario["dgp_truth"] = tgt.get("dgp_truth") or {}
        scenario["ground_truth"] = tgt.get("ground_truth") or {}
        sid = scenario["scenario_id"]
        canonical = {sid: tgt["canonical"]} if tgt.get("canonical") else {}
        llm_output = _llm_output(content)

        # L2b execution happens in the sandbox; score_output is then given the
        # result through its `executor` hook and performs every scoring step
        # (code extraction, coefficient extraction, baseline comparison) itself.
        code = l2b_plus.extract_r_code(content)
        execution: tuple[bool, str, str] | None = None
        if code is not None:
            execution = await execute_r_code_in_sandbox(code, timeout=r_timeout)

        def executor(_code: str) -> tuple[bool, str, str]:
            return execution if execution is not None else (False, "", "not executed")

        row = l2b_plus.score_output(
            scenario,
            llm_output,
            tolerance=tolerance,
            baseline=baseline,
            canonical_baselines=canonical,
            executor=executor,
        )
        text_row = exp_b_text_scoring.score_output(scenario, llm_output, execute=False)
        dgp_direction = scenario["dgp_truth"].get("direction") or ""
        s_values, s_preds = s1_s2_values(content, dgp_direction)

        value: dict[str, Any] = {
            "L1": int(row["L1"]),
            "L2a": int(row["L2a"]),
            "L2b": int(row["L2b"]),
            "L2b_plus": int(row["L2b_plus"]),
            "coefficient_extracted": int(row["estimated"] is not None),
            "baseline_available": int(row["baseline_available"]),
            "L3_method_agree": int(text_row["L3_method_agree"]),
            "L4_direction_agree": int(text_row["L4_direction_agree"]),
            **s_values,
        }
        stdout = execution[1] if execution is not None else ""
        metadata: dict[str, Any] = {
            "l2b_plus_row": row,
            "exp_b_text_row": text_row,
            "stdout_excerpt": stdout[-STDOUT_EXCERPT_CHARS:],
            **s_preds,
        }

        if judge:
            judge_info: dict[str, Any] = {"judge_effect": None, "judge_rationale": "", "judge_raw": ""}
            if row["L2b"] and code is not None:
                grader = get_model(role=JUDGE_ROLE, default=DEFAULT_JUDGE_MODEL)
                judge_info = await judge_treatment_effect(
                    grader, scenario["method_family"], scenario.get("title", ""), code, stdout
                )
            verdict = judge_l2b_plus(
                judge_info["judge_effect"], row["baseline_effect"], scenario["method_family"], tolerance
            )
            value["L2b_plus_judge"] = verdict["L2b_plus_judge"]
            value["L2b_plus_v2"] = verdict["L2b_plus_v2"]
            metadata.update(judge_info)
            metadata.update(verdict)

        if not row["L2a"]:
            answer = "no R code block"
        elif not row["L2b"]:
            answer = f"R error: {row['err_excerpt'] or 'non-zero exit'}"
        elif row["estimated"] is None:
            answer = "ran; no coefficient extracted"
        else:
            answer = f"estimate={row['estimated']}"
        explanation = (
            f"L1={value['L1']} L2a={value['L2a']} L2b={value['L2b']} L2b+={value['L2b_plus']} "
            f"(baseline={baseline}, tolerance={tolerance}, rel_error={row['rel_error']}); "
            f"text-level L3={value['L3_method_agree']} L4={value['L4_direction_agree']}"
        )
        return Score(value=value, answer=answer, explanation=explanation, metadata=metadata)

    return score
