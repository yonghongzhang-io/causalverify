"""Dataset loader of the Inspect port, exercised on the synthetic fixture."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from conftest import load_synthetic_items

from causalverify_inspect._repo import (
    DATA_ENV_VAR,
    CausalVerifyDataError,
    decode_target,
    resolve_data_root,
)
from causalverify_inspect.dataset import (
    EXP_B_TASK_FACING_FIELDS,
    load_exp_a_dataset,
    load_exp_b_dataset,
)
from src.pipeline import auto_score_exp_a, score_l2b_plus
from src.prompts import exp_a as exp_a_prompts
from src.prompts import exp_b as exp_b_prompts

# ── data root resolution ─────────────────────────────────────────────────────


def test_data_root_param_wins_over_env(synthetic_root, tmp_path, monkeypatch):
    monkeypatch.setenv(DATA_ENV_VAR, str(tmp_path))
    assert resolve_data_root(str(synthetic_root)) == synthetic_root
    assert resolve_data_root() == tmp_path.resolve()


def test_data_root_missing_is_a_clear_error(monkeypatch):
    monkeypatch.delenv(DATA_ENV_VAR, raising=False)
    with pytest.raises(CausalVerifyDataError, match="CAUSALVERIFY_DATA"):
        resolve_data_root()
    with pytest.raises(CausalVerifyDataError, match="not found"):
        resolve_data_root("/definitely/not/here")


def test_relative_data_root_falls_back_to_repo_root(tmp_path, monkeypatch, synthetic_root):
    # Inspect chdirs into the task file's directory while creating tasks; a
    # repository-relative path must keep working from anywhere.
    monkeypatch.chdir(tmp_path)
    assert resolve_data_root("tests/fixtures/synthetic_causalverify_data") == synthetic_root


# ── Experiment A ─────────────────────────────────────────────────────────────


def test_exp_a_samples_use_the_papers_prompt_and_consensus_targets(synthetic_root):
    dataset = load_exp_a_dataset(synthetic_root)
    items = load_synthetic_items("exp_a")
    gt_by_pid = auto_score_exp_a.load_gt_aggregate(synthetic_root / "audit" / "gt_aggregate_decisions.json")

    assert [s.id for s in dataset] == ["paper_9001", "paper_9002", "paper_9003", "paper_9004"]
    for sample in dataset:
        paper = items[sample.id]
        expected_prompt = exp_a_prompts.USER_PROMPT_TEMPLATE.format(
            research_question=paper["research_question"],
            data_description=paper["data_description"],
            institutional_context=paper["institutional_context"],
        )
        assert sample.input == expected_prompt
        assert decode_target(sample.target) == auto_score_exp_a.gt_for_paper(paper, gt_by_pid)
        assert sample.metadata["paper"] == {
            "paper_id": paper["paper_id"],
            "method_family": paper["method_family"],
            "difficulty": paper["difficulty"],
        }
        assert sample.metadata["experiment"] == "exp_a"
        # The model-facing prompt never carries target fields.
        assert "new_method" not in sample.input and "new_direction" not in sample.input

    unscoreable = next(s for s in dataset if s.id == "paper_9004")
    target = decode_target(unscoreable.target)
    assert target["method_scoreable"] is False and target["direction_scoreable"] is False
    # grouping key follows the pipeline's `method_family` column (`true_method or "UNSCORED"`)
    assert unscoreable.metadata["method_family"] == "OTHER"


def test_exp_a_requires_the_targets_file(synthetic_root, tmp_path):
    root = tmp_path / "data"
    shutil.copytree(synthetic_root, root)
    (root / "audit" / "gt_aggregate_decisions.json").unlink()
    with pytest.raises(CausalVerifyDataError, match="targets not found"):
        load_exp_a_dataset(root)


# ── Experiment B ─────────────────────────────────────────────────────────────


def test_exp_b_samples_reproduce_the_runner_prompt_and_attach_data(synthetic_root, monkeypatch):
    dataset = load_exp_b_dataset(synthetic_root, baseline="canonical")
    items = load_synthetic_items("exp_b")
    canonical = score_l2b_plus.load_canonical_baselines(synthetic_root / "audit" / "dgp_verification.json")

    assert [s.id for s in dataset] == ["s901", "s902", "s903", "s904", "s905"]
    monkeypatch.chdir(synthetic_root)  # run_exp_b builds the preview relative to cwd
    for sample in dataset:
        scenario = items[sample.id]
        assert sample.input == exp_b_prompts.build_user_prompt(scenario)  # original, cwd-relative behaviour
        assert sample.input == exp_b_prompts.build_user_prompt(scenario, data_root=synthetic_root)
        assert f"Data file path: {scenario['data_file']}" in sample.input
        assert sample.files == {scenario["data_file"]: str(synthetic_root / scenario["data_file"])}
        assert Path(sample.files[scenario["data_file"]]).is_file()
        assert set(sample.metadata["scenario"]) == set(EXP_B_TASK_FACING_FIELDS)
        target = decode_target(sample.target)
        assert target["dgp_truth"] == scenario["dgp_truth"]
        assert target["ground_truth"] == scenario["ground_truth"]
        assert target["canonical"] == canonical.get(sample.id)
        # Target fields stay out of the model-facing prompt.
        for forbidden in ("dgp_truth", "ground_truth", "conclusion_direction", "main_effect", "made-up"):
            assert forbidden not in sample.input

    assert decode_target(next(s for s in dataset if s.id == "s904").target)["canonical"] is None


def test_exp_b_baseline_validation(synthetic_root, tmp_path):
    assert len(load_exp_b_dataset(synthetic_root, baseline="dgp")) == 5
    with pytest.raises(ValueError, match="baseline"):
        load_exp_b_dataset(synthetic_root, baseline="bogus")

    root = tmp_path / "data"
    shutil.copytree(synthetic_root, root)
    (root / "audit" / "dgp_verification.json").unlink()
    with pytest.raises(CausalVerifyDataError, match="canonical"):
        load_exp_b_dataset(root, baseline="canonical")
    assert len(load_exp_b_dataset(root, baseline="dgp")) == 5  # dgp baseline needs no canonical file


def test_exp_b_refuses_public_task_facing_items_for_dgp_baseline(synthetic_root, tmp_path):
    """Pointing at the public repo (scenarios without targets) must fail loudly, not score zeros."""
    root = tmp_path / "data"
    shutil.copytree(synthetic_root, root)
    for path in (root / "experiments" / "exp_b" / "scenarios").glob("s*.json"):
        scenario = json.loads(path.read_text())
        path.write_text(json.dumps({k: scenario[k] for k in EXP_B_TASK_FACING_FIELDS}))
    with pytest.raises(CausalVerifyDataError, match="dgp_truth"):
        load_exp_b_dataset(root, baseline="dgp")
    # With canonical baselines the eval can still run (text-level layers degrade to 0).
    assert len(load_exp_b_dataset(root, baseline="canonical")) == 5
