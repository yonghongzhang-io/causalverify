"""``inspect eval`` runs end to end on the synthetic fixture with mockllm and writes a log."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from inspect_ai.log import read_eval_log

TASK_FILE = "causalverify_inspect/tasks.py"
FIXTURE_REL = "tests/fixtures/synthetic_causalverify_data"  # relative on purpose (resolved against the repo root)


def _inspect_eval(task: str, log_dir: Path, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "inspect_ai", "eval", f"{TASK_FILE}@{task}", "--model", "mockllm/model",
           "--log-dir", str(log_dir), "--log-format", "eval", "--display", "none",
           "-T", f"data_root={FIXTURE_REL}", *extra]
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env or os.environ.copy(), capture_output=True, text=True, timeout=600)


@pytest.fixture(scope="module", autouse=True)
def _require_mockllm_token_counting():
    """mockllm fills in usage by counting tokens with tiktoken's o200k_base encoding, which is
    downloaded on first use. Offline (no cache), the CLI run cannot succeed, so skip rather
    than report a spurious failure. The in-process eval tests replay completions with explicit
    usage and therefore run fully offline."""
    try:
        import tiktoken

        tiktoken.get_encoding("o200k_base")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"tiktoken o200k_base encoding unavailable offline ({type(exc).__name__}); "
                    "set TIKTOKEN_CACHE_DIR to a pre-populated cache to run the CLI tests")


def _single_log(log_dir: Path):
    logs = list(log_dir.glob("*.eval"))
    assert len(logs) == 1, logs
    return read_eval_log(str(logs[0]))


def test_cli_exp_a_with_mockllm(tmp_path):
    proc = _inspect_eval("causalverify_exp_a", tmp_path)
    assert proc.returncode == 0, proc.stderr[-2000:]
    log = _single_log(tmp_path)
    assert log.status == "success" and log.eval.task == "causalverify_exp_a"
    assert len(log.samples) == 4 and all("exp_a_text_scorer" in s.scores for s in log.samples)
    metrics = next(s for s in log.results.scores if s.scorer == "exp_a_text_scorer").metrics
    assert metrics["L1_rate"].value == 1.0  # mockllm's default completion is non-empty text
    assert metrics["L3_method_agree_rate"].value == 0.0


def test_cli_exp_b_with_mockllm_and_local_sandbox(tmp_path, fake_rscript):
    proc = _inspect_eval("causalverify_exp_b", tmp_path, "--sandbox", "local", "-T", "baseline=canonical")
    assert proc.returncode == 0, proc.stderr[-2000:]
    log = _single_log(tmp_path)
    assert log.status == "success" and log.eval.task == "causalverify_exp_b"
    assert log.eval.task_args["baseline"] == "canonical"
    assert len(log.samples) == 5 and all("exp_b_execution_scorer" in s.scores for s in log.samples)
    metrics = next(s for s in log.results.scores if s.scorer == "exp_b_execution_scorer").metrics
    assert metrics["L1_rate"].value == 1.0 and metrics["L2a_rate"].value == 0.0  # default mock text has no R code
    assert metrics["L2b_plus_rate"].value == 0.0
