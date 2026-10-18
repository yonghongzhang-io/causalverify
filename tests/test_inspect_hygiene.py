"""Guards: no import side effects, synthetic-only fixture, behaviour-preserving src refactors."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys

import pytest
from conftest import (
    REPO_ROOT,
    SYNTHETIC_ROOT,
    load_synthetic_items,
    load_synthetic_outputs,
)

from src.pipeline import score_l2b_plus

# Columns the CI redaction guard forbids in any tracked CSV header (.github/workflows/ci.yml).
FORBIDDEN_CSV_COLUMNS = {
    "gt_direction", "gt_m_level", "gt_d_level", "true_effect", "true_direction",
    "dgp_effect", "dgp_direction", "baseline_effect", "baseline_direction",
}


def test_importing_the_port_creates_nothing_in_the_working_directory(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    code = (
        "import causalverify_inspect.tasks, causalverify_inspect.scorers, causalverify_inspect.dataset, "
        "src.pipeline.auto_score_exp_a, src.pipeline.score_exp_b, src.pipeline.score_l2b_plus, "
        "src.pipeline.multi_scorer_l4"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, check=True, timeout=120)
    assert list(tmp_path.iterdir()) == [], "importing scoring code must not create paper/ or experiments/ dirs"


def test_fixture_is_clearly_synthetic():
    readme = (SYNTHETIC_ROOT / "README.md").read_text().lower()
    assert "not benchmark data" in readme and "made up" in readme

    papers = load_synthetic_items("exp_a")
    scenarios = load_synthetic_items("exp_b")
    assert all(re.fullmatch(r"paper_9\d{3}", pid) for pid in papers), "ids must stay outside the real range"
    assert all(re.fullmatch(r"s9\d{2}", sid) for sid in scenarios)
    assert all(p["source"] == "synthetic" and "fictional" in p["authors"] for p in papers.values())
    assert all(s["_synthetic"] is True and s["title"].startswith("SYNTHETIC") for s in scenarios.values())
    gt = json.loads((SYNTHETIC_ROOT / "audit" / "gt_aggregate_decisions.json").read_text())
    assert all(row["_synthetic"] is True for row in gt)
    canonical = json.loads((SYNTHETIC_ROOT / "audit" / "dgp_verification.json").read_text())
    assert "SYNTHETIC" in canonical["summary"]["note"]
    for exp in ("exp_a", "exp_b"):
        assert all(rec["_synthetic"] is True for rec in load_synthetic_outputs(exp).values())


def test_fixture_csvs_pass_the_redaction_guard():
    for path in SYNTHETIC_ROOT.rglob("*.csv"):
        with open(path, newline="") as f:
            header = set(next(csv.reader(f)))
        assert not (header & FORBIDDEN_CSV_COLUMNS), path


def test_wrap_r_code_matches_the_original_wrapper():
    code = 'x <- c(1, 2)\nprint({x})\n# {braces} stay literal\n'
    original = f"""
options(warn = -1)
suppressMessages({{
{code}
}})
"""
    assert score_l2b_plus.wrap_r_code(code) == original


def test_execute_r_code_uses_the_wrapper(fake_rscript):
    ok, stdout, err = score_l2b_plus.execute_r_code("# OUT:DID coef: 0.123\n")
    assert (ok, stdout.strip(), err) == (True, "DID coef: 0.123", "")
    ok, stdout, err = score_l2b_plus.execute_r_code("# FAIL\n")
    assert ok is False and "simulated R error" in err


@pytest.mark.parametrize("baseline", ["dgp", "canonical"])
def test_score_output_executor_hook_is_behaviour_preserving(baseline, monkeypatch):
    """Default call vs. injected executor returning the same triple: identical rows."""
    scenarios = load_synthetic_items("exp_b")
    outputs = load_synthetic_outputs("exp_b")
    canonical = score_l2b_plus.load_canonical_baselines(SYNTHETIC_ROOT / "audit" / "dgp_verification.json")
    canned = {"s901": (True, "DID coef: -0.2851\n", ""), "s902": (True, "CAR: 0.0121\n", ""),
              "s903": (False, "", "Error: boom"), "s904": (True, "Analysis complete.\n", "")}
    for sid, scenario in scenarios.items():
        triple = canned.get(sid, (False, "", "unused"))
        monkeypatch.setattr(score_l2b_plus, "execute_r_code", lambda code, _t=triple: _t)
        default_row = score_l2b_plus.score_output(scenario, outputs[sid], 0.5, baseline, canonical)
        injected_row = score_l2b_plus.score_output(
            scenario, outputs[sid], 0.5, baseline, canonical, executor=lambda code, _t=triple: _t
        )
        assert default_row == injected_row
    # Spot-check the synthetic design: s901 passes L2b+, s902 fails on the regex path, s903 fails to run.
    rows = {sid: score_l2b_plus.score_output(scenarios[sid], outputs[sid], 0.5, "canonical", canonical,
                                             executor=lambda code, _t=canned[sid]: _t) for sid in canned}
    assert (rows["s901"]["L2b"], rows["s901"]["L2b_plus"]) == (1, 1)
    assert (rows["s902"]["L2b"], rows["s902"]["L2b_plus"]) == (1, 0)
    assert (rows["s903"]["L2a"], rows["s903"]["L2b"]) == (1, 0)
    assert (rows["s904"]["L2b"], rows["s904"]["estimated"], rows["s904"]["baseline_available"]) == (1, None, 0)
