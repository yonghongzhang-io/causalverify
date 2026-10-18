"""Metrics reporting the per-level rates the paper reports.

Scores in this port are dictionaries (one key per layer), so the metrics below
receive the full ``SampleScore`` list and compute conditional rates themselves:

* a value of ``NaN`` means "no row in the pipeline's table" (e.g. the
  multi-scorer L4 table only has rows for non-empty outputs) and is skipped;
* ``among`` restricts the denominator to samples whose flag is 1 (e.g. L3
  agreement is reported "per scoreable paper", as ``auto_score_exp_a`` prints).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from inspect_ai.scorer import Metric, SampleScore, Value, metric

#: Marker for "this sample has no row in the corresponding pipeline table".
NOT_APPLICABLE = float("nan")


def score_field(sample_score: SampleScore, key: str) -> float | None:
    """Numeric value of ``key`` in a dict-valued score, or ``None`` if absent/NaN."""
    value = sample_score.score.value
    if not isinstance(value, Mapping) or key not in value:
        return None
    item = value[key]
    if item is None or isinstance(item, str):
        return None
    number = float(item)
    return None if math.isnan(number) else number


def rate(scores: list[SampleScore], key: str, among: str | None = None) -> float | None:
    """Mean of ``key`` over samples where it is defined (and ``among`` is 1)."""
    values = []
    for sample_score in scores:
        item = score_field(sample_score, key)
        if item is None:
            continue
        if among is not None and not score_field(sample_score, among):
            continue
        values.append(item)
    return sum(values) / len(values) if values else None


def count(scores: list[SampleScore], key: str) -> int:
    """Number of samples with ``key`` == 1."""
    return int(sum(1 for s in scores if score_field(s, key)))


def _drop_none(table: dict[str, float | int | None]) -> Value:
    return {k: v for k, v in table.items() if v is not None}


@metric
def level_rate(key: str, among: str | None = None) -> Metric:
    """Pass rate of one layer (optionally among samples where ``among`` is 1)."""

    def metric_fn(scores: list[SampleScore]) -> Value:
        value = rate(scores, key, among)
        return NOT_APPLICABLE if value is None else value

    return metric_fn


@metric
def exp_a_summary() -> Metric:
    """Experiment A table: L1 rate, L3/L4 agreement per scoreable paper, S1/S2 L4 rates.

    Matches what ``auto_score_exp_a.print_table`` prints ("Method agreement x/n
    scoreable", "Direction agreement x/n scoreable") and the per-model
    ``S1_latter_half_l4`` / ``S2_section6_l4`` rates of ``multi_scorer_l4``.
    """

    def metric_fn(scores: list[SampleScore]) -> Value:
        return _drop_none(
            {
                "L1_rate": rate(scores, "L1_complete"),
                "L3_method_agree_rate": rate(scores, "L3_method_agree", among="L3_scoreable"),
                "L4_direction_agree_rate": rate(scores, "L4_direction_agree", among="L4_scoreable"),
                "S1_latter_half_l4": rate(scores, "S1_latter_half_match"),
                "S2_section6_l4": rate(scores, "S2_section6_match"),
                "n": len(scores),
                "n_L3_scoreable": count(scores, "L3_scoreable"),
                "n_L4_scoreable": count(scores, "L4_scoreable"),
            }
        )

    return metric_fn


@metric
def exp_b_summary() -> Metric:
    """Experiment B table: L1/L2a/L2b/L2b+ rates and diagnostics, text-level L3/L4, S1/S2.

    ``L*_rate`` and ``coefficient_extraction_failure_rate`` / ``missing_baseline``
    follow ``score_l2b_plus.run_scoring``'s ``by_model`` and ``diagnostics``
    blocks; ``L2b_plus_judge_rate`` / ``L2b_plus_v2_rate`` appear when the task
    runs with ``judge=true`` (``recompute_l2b_plus_es_aware.py`` summary).
    """

    def metric_fn(scores: list[SampleScore]) -> Value:
        extracted_given_run = rate(scores, "coefficient_extracted", among="L2b")
        return _drop_none(
            {
                "L1_rate": rate(scores, "L1"),
                "L2a_rate": rate(scores, "L2a"),
                "L2b_rate": rate(scores, "L2b"),
                "L2b_plus_rate": rate(scores, "L2b_plus"),
                "L2b_plus_judge_rate": rate(scores, "L2b_plus_judge"),
                "L2b_plus_v2_rate": rate(scores, "L2b_plus_v2"),
                "L3_method_agree_rate": rate(scores, "L3_method_agree"),
                "L4_direction_agree_rate": rate(scores, "L4_direction_agree"),
                "S1_latter_half_l4": rate(scores, "S1_latter_half_match"),
                "S2_section6_l4": rate(scores, "S2_section6_match"),
                "coefficient_extraction_failure_rate": (
                    None if extracted_given_run is None else 1.0 - extracted_given_run
                ),
                "missing_baseline": len(scores) - count(scores, "baseline_available"),
                "n": len(scores),
            }
        )

    return metric_fn
