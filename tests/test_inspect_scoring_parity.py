"""Parity: the Inspect scorers return exactly what the pipeline's scoring code returns.

Experiment A is checked by calling the scorer directly. Experiment B needs a
sandbox for L2b, so it is checked through a full ``inspect_ai.eval`` run with
``mockllm`` replaying the synthetic completions and the ``local`` sandbox
running the stand-in ``Rscript``; the pipeline side runs the very same
functions through their own local executor.
"""

from __future__ import annotations

import asyncio
import json
import math
import re

import pytest
from conftest import load_synthetic_items, load_synthetic_outputs
from inspect_ai import eval as inspect_eval
from inspect_ai.model import (
    ChatMessageUser,
    ModelName,
    ModelOutput,
    ModelUsage,
    get_model,
)
from inspect_ai.scorer import Target
from inspect_ai.solver import TaskState

from causalverify_inspect._repo import encode_target
from causalverify_inspect.judge import es_pass, parse_judge_response
from causalverify_inspect.scorers import exp_a_text_scorer, l4_match
from causalverify_inspect.tasks import causalverify_exp_a, causalverify_exp_b
from src.pipeline import auto_score_exp_a, multi_scorer_l4, score_exp_b, score_l2b_plus

SCORER_A = "exp_a_text_scorer"
SCORER_B = "exp_b_execution_scorer"


def _content(record: dict) -> str:
    return record["llm_response"]["content"]


def _canned(content: str) -> ModelOutput:
    """A replayed completion with explicit usage (mockllm would otherwise count tokens via
    tiktoken, whose encoding download is impossible in offline test environments)."""
    output = ModelOutput.from_content("mockllm", content)
    output.usage = ModelUsage(input_tokens=1, output_tokens=max(1, len(content) // 4), total_tokens=2)
    return output


def _replay_model(completions_by_marker: dict[str, str]):
    """mockllm that answers each prompt with the canned completion whose marker it contains."""

    def respond(messages, tools, tool_choice, config) -> ModelOutput:
        prompt = next(m.text for m in reversed(messages) if m.role == "user")
        for marker, content in completions_by_marker.items():
            if marker in prompt:
                return _canned(content)
        raise AssertionError("no canned completion for prompt: " + prompt[:80])

    return get_model("mockllm/model", custom_outputs=respond, memoize=False)


def _nan_aware_equal(a, b) -> bool:
    return (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b)) or a == b


# ── Experiment A ─────────────────────────────────────────────────────────────


def test_exp_a_scorer_equals_auto_score_exp_a(synthetic_root):
    papers = load_synthetic_items("exp_a")
    outputs = load_synthetic_outputs("exp_a")
    gt_by_pid = auto_score_exp_a.load_gt_aggregate(synthetic_root / "audit" / "gt_aggregate_decisions.json")
    scorer = exp_a_text_scorer()

    for pid, paper in papers.items():
        gt = auto_score_exp_a.gt_for_paper(paper, gt_by_pid)
        content = _content(outputs[pid])
        expected = auto_score_exp_a.score_output(paper, gt, outputs[pid])  # the pipeline, verbatim

        state = TaskState(
            model=ModelName("mockllm/model"), sample_id=pid, epoch=1, input="prompt",
            messages=[ChatMessageUser(content="prompt")],
            output=ModelOutput.from_content("mockllm", content),
            metadata={"paper": {"paper_id": pid, "method_family": paper["method_family"], "difficulty": paper["difficulty"]}},
        )
        score = asyncio.run(scorer(state, Target(encode_target(gt))))

        assert score.metadata["pipeline_row"] == expected
        for key in ("L1_complete", "L3_scoreable", "L3_method_agree", "L4_scoreable", "L4_direction_agree"):
            assert score.value[key] == int(expected[key]), (pid, key)
        s1 = multi_scorer_l4.s1_latter_half(content, gt["direction"])
        s2 = multi_scorer_l4.s2_section6_keyword(content, gt["direction"])
        if content:
            assert score.value["S1_latter_half_match"] == l4_match(s1, gt["direction"])
            assert score.value["S2_section6_match"] == l4_match(s2, gt["direction"])
        else:  # multi_scorer_l4 emits no row for empty outputs
            assert math.isnan(score.value["S1_latter_half_match"]) and math.isnan(score.value["S2_section6_match"])

    # The fixture was designed to hit every branch; make sure it still does.
    def flags(pid):
        gt = auto_score_exp_a.gt_for_paper(papers[pid], gt_by_pid)
        r = auto_score_exp_a.score_output(papers[pid], gt, outputs[pid])
        return r["L1_complete"], r["L3_method_agree"], r["L4_direction_agree"], r["L3_scoreable"]
    assert flags("paper_9001") == (True, True, True, True)
    assert flags("paper_9002") == (True, False, True, True)
    assert flags("paper_9003") == (True, True, False, True)
    assert flags("paper_9004") == (False, False, False, False)


def test_exp_a_end_to_end_metrics_match_pipeline_summary(synthetic_root, tmp_path):
    papers = load_synthetic_items("exp_a")
    outputs = load_synthetic_outputs("exp_a")
    gt_by_pid = auto_score_exp_a.load_gt_aggregate(synthetic_root / "audit" / "gt_aggregate_decisions.json")
    model = _replay_model({p["research_question"]: _content(outputs[pid]) for pid, p in papers.items()})

    log = inspect_eval(causalverify_exp_a(data_root=str(synthetic_root)), model=model,
                       log_dir=str(tmp_path), display="none", log_level="warning")[0]
    assert log.status == "success", log.error
    assert [s.id for s in log.samples] == list(papers)

    rows = {pid: auto_score_exp_a.score_output(p, auto_score_exp_a.gt_for_paper(p, gt_by_pid), outputs[pid])
            for pid, p in papers.items()}
    metrics = next(s for s in log.results.scores if s.scorer == SCORER_A).metrics
    n = len(rows)
    assert metrics["L1_rate"].value == sum(r["L1_complete"] for r in rows.values()) / n
    assert metrics["L3_method_agree_rate"].value == pytest.approx(
        sum(r["L3_method_agree"] for r in rows.values()) / sum(r["L3_scoreable"] for r in rows.values()))
    assert metrics["L4_direction_agree_rate"].value == pytest.approx(
        sum(r["L4_direction_agree"] for r in rows.values()) / sum(r["L4_scoreable"] for r in rows.values()))
    # multi_scorer_l4 rates: over rows with non-empty content only
    scored = [pid for pid in papers if _content(outputs[pid])]
    for name, fn in (("S1_latter_half_l4", multi_scorer_l4.s1_latter_half), ("S2_section6_l4", multi_scorer_l4.s2_section6_keyword)):
        expected = sum(l4_match(fn(_content(outputs[pid]), gt_by_pid[pid]["new_direction"]), gt_by_pid[pid]["new_direction"])
                       for pid in scored) / len(scored)
        assert metrics[name].value == pytest.approx(expected), name
    assert metrics["n"].value == n and metrics["n_L3_scoreable"].value == 3


# ── Experiment B ─────────────────────────────────────────────────────────────


def _run_exp_b(synthetic_root, tmp_path, **task_args):
    scenarios = load_synthetic_items("exp_b")
    outputs = load_synthetic_outputs("exp_b")
    model = _replay_model({s["title"]: _content(outputs[sid]) for sid, s in scenarios.items()})
    model_roles = task_args.pop("_model_roles", None)
    log = inspect_eval(causalverify_exp_b(data_root=str(synthetic_root), **task_args), model=model,
                       sandbox="local", log_dir=str(tmp_path), display="none", log_level="warning",
                       model_roles=model_roles)[0]
    assert log.status == "success", log.error
    return log, scenarios, outputs


@pytest.mark.parametrize("baseline", ["canonical", "dgp"])
def test_exp_b_scores_equal_score_l2b_plus_and_score_exp_b(synthetic_root, tmp_path, fake_rscript, baseline):
    log, scenarios, outputs = _run_exp_b(synthetic_root, tmp_path, baseline=baseline)
    canonical = score_l2b_plus.load_canonical_baselines(synthetic_root / "audit" / "dgp_verification.json")
    assert [s.id for s in log.samples] == list(scenarios)

    for sample in log.samples:
        sid, scenario, record = sample.id, scenarios[sample.id], outputs[sample.id]
        score = sample.scores[SCORER_B]
        # Pipeline side: the same functions, running the stand-in Rscript through their own executor.
        expected_row = score_l2b_plus.score_output(scenario, record, 0.5, baseline, canonical)
        expected_text = score_exp_b.score_output(scenario, record, execute=False)

        assert score.metadata["l2b_plus_row"] == expected_row, sid
        assert score.metadata["exp_b_text_row"] == expected_text, sid
        for key in ("L1", "L2a", "L2b", "L2b_plus", "baseline_available"):
            assert score.value[key] == expected_row[key], (sid, key)
        assert score.value["coefficient_extracted"] == int(expected_row["estimated"] is not None)
        assert score.value["L3_method_agree"] == int(expected_text["L3_method_agree"])
        assert score.value["L4_direction_agree"] == int(expected_text["L4_direction_agree"])
        gt_dir = scenario["dgp_truth"]["direction"]
        s1 = multi_scorer_l4.s1_latter_half(_content(record), gt_dir)
        s2 = multi_scorer_l4.s2_section6_keyword(_content(record), gt_dir)
        assert score.value["S1_latter_half_match"] == l4_match(s1, gt_dir)
        assert score.value["S2_section6_match"] == l4_match(s2, gt_dir)
        assert "L2b_plus_judge" not in score.value  # judge is opt-in

    # Fixture design: every execution branch is exercised.
    by_id = {s.id: s.scores[SCORER_B].value for s in log.samples}
    assert (by_id["s901"]["L2b"], by_id["s901"]["L2b_plus"]) == (1, 1)
    assert (by_id["s902"]["L2b"], by_id["s902"]["L2b_plus"]) == (1, 0)  # CAR[0,+2] vs per-day canonical
    assert (by_id["s903"]["L2a"], by_id["s903"]["L2b"]) == (1, 0)  # R error
    assert (by_id["s904"]["L2b"], by_id["s904"]["coefficient_extracted"]) == (1, 0)
    assert by_id["s904"]["baseline_available"] == (0 if baseline == "canonical" else 1)
    assert (by_id["s905"]["L1"], by_id["s905"]["L2a"]) == (1, 0)  # prose only

    # Aggregate metrics follow score_l2b_plus.run_scoring's summary/diagnostics.
    rows = {sid: score_l2b_plus.score_output(scenarios[sid], outputs[sid], 0.5, baseline, canonical) for sid in scenarios}
    metrics = next(s for s in log.results.scores if s.scorer == SCORER_B).metrics
    n = len(rows)
    for layer in ("L1", "L2a", "L2b", "L2b_plus"):
        assert metrics[f"{layer}_rate"].value == pytest.approx(sum(r[layer] for r in rows.values()) / n), layer
    ran = [r for r in rows.values() if r["L2b"]]
    assert metrics["coefficient_extraction_failure_rate"].value == pytest.approx(
        sum(1 for r in ran if r["estimated"] is None) / len(ran))
    assert metrics["missing_baseline"].value == sum(1 for r in rows.values() if not r["baseline_available"])
    # per-method breakdown (by_method in the pipeline summary)
    did = [r for r in rows.values() if r["method"] == "DID"]
    assert metrics["L2b_plus_rate_DID"].value == pytest.approx(sum(r["L2b_plus"] for r in did) / len(did))
    assert metrics["L2b_rate_EVENT_STUDY"].value == 1.0


def test_exp_b_judge_and_event_study_aware_variant(synthetic_root, tmp_path, fake_rscript):
    """judge=true: grader-model extraction + ES window rule, mirroring the two scripts."""

    def grader(messages, tools, tool_choice, config) -> ModelOutput:
        prompt = messages[-1].text
        stdout = prompt.split("R stdout:\n```\n", 1)[1].split("```", 1)[0]
        m = re.search(r"(?:coef|CAR):\s*(-?\d+\.\d+)", stdout)
        payload = {"effect": float(m.group(1)) if m else None, "rationale": "synthetic grader"}
        # exercise the fenced-JSON path the real judge sometimes produces
        return _canned("```json\n" + json.dumps(payload) + "\n```")

    grader_model = get_model("mockllm/model", custom_outputs=grader, memoize=False)
    log, scenarios, outputs = _run_exp_b(synthetic_root, tmp_path, judge=True, _model_roles={"grader": grader_model})
    canonical = score_l2b_plus.load_canonical_baselines(synthetic_root / "audit" / "dgp_verification.json")
    by_id = {s.id: s.scores[SCORER_B] for s in log.samples}

    # s901: judge agrees with the regex extractor
    assert by_id["s901"].metadata["judge_effect"] == -0.2851
    assert (by_id["s901"].value["L2b_plus_judge"], by_id["s901"].value["L2b_plus_v2"]) == (1, 1)
    # s902: CAR over 3 days fails the per-day comparison but passes the ES window rule (k = 3)
    per_day = canonical["s902"]["effect"]
    ok, k, _ = es_pass(0.0121, per_day, tol=0.5)
    assert (ok, k) == (True, 3)
    assert by_id["s902"].value["L2b_plus"] == 0
    assert by_id["s902"].value["L2b_plus_judge"] == 0
    assert by_id["s902"].value["L2b_plus_v2"] == 1 and by_id["s902"].metadata["es_window_match"] == 3
    # s903 (did not run) and s904 (no coefficient) and s905 (no code) stay 0; judge only called when L2b = 1
    for sid in ("s903", "s904", "s905"):
        assert (by_id[sid].value["L2b_plus_judge"], by_id[sid].value["L2b_plus_v2"]) == (0, 0), sid
    assert by_id["s903"].metadata["judge_raw"] == ""  # never asked
    assert by_id["s904"].metadata["judge_effect"] is None  # asked, answered null

    metrics = next(s for s in log.results.scores if s.scorer == SCORER_B).metrics
    assert metrics["L2b_plus_judge_rate"].value == pytest.approx(1 / 5)
    assert metrics["L2b_plus_v2_rate"].value == pytest.approx(2 / 5)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"effect": -0.2851, "rationale": "coef on treat_x_post"}', (-0.2851, "coef on treat_x_post")),
        ('```json\n{"effect": 0.5, "rationale": "x"}\n```', (0.5, "x")),
        ('{"effect": null, "rationale": "no estimate printed"}', (None, "no estimate printed")),
        ('{"effect": "0.25", "rationale": "string number"}', (0.25, "string number")),
        ('The effect is {"effect": 0.31 ... (truncated', (0.31, 'parse_error: The effect is {"effect": 0.31 ... (truncated')),
        ("I cannot tell.", (None, "parse_error: I cannot tell.")),
        ("42", (None, "parse_error: 42")),
    ],
)
def test_parse_judge_response_mirrors_the_script(raw, expected):
    assert parse_judge_response(raw) == expected


def test_exp_b_without_r_scores_l2b_zero_with_reason(synthetic_root, tmp_path, monkeypatch):
    """No ``Rscript`` on PATH: code is scored as not running (L2b = 0) and the reason is recorded,
    exactly like score_l2b_plus.execute_r_code on a host without R."""
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    log, scenarios, outputs = _run_exp_b(synthetic_root, tmp_path / "logs")
    s901 = next(s for s in log.samples if s.id == "s901").scores[SCORER_B]
    assert (s901.value["L2a"], s901.value["L2b"], s901.value["L2b_plus"]) == (1, 0, 0)
    assert "Rscript" in s901.metadata["l2b_plus_row"]["err_excerpt"]
    expected = score_l2b_plus.score_output(scenarios["s901"], outputs["s901"], 0.5, "canonical",
                                           score_l2b_plus.load_canonical_baselines(synthetic_root / "audit" / "dgp_verification.json"))
    assert s901.metadata["l2b_plus_row"] == expected
