"""Inspect tasks for the CausalVerify benchmark.

Run from the repository root, e.g.::

    export CAUSALVERIFY_DATA=/path/to/benchmark/items
    inspect eval causalverify_inspect/tasks.py@causalverify_exp_a --model openai/gpt-4o
    inspect eval causalverify_inspect/tasks.py@causalverify_exp_b --model anthropic/claude-opus-4-6

Experiment B executes model-written R code; by default this happens in a
Docker sandbox built from the repository ``Dockerfile`` (see ``compose.yaml``
next to this file). ``--sandbox local`` runs ``Rscript`` from the host instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Inspect loads this file by path (not as part of the package), so make the
# repository root importable for `causalverify_inspect.*` and `src.*`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from inspect_ai import Task, task  # noqa: E402

from causalverify_inspect.dataset import (  # noqa: E402
    load_exp_a_dataset,
    load_exp_b_dataset,
)
from causalverify_inspect.scorers import (  # noqa: E402
    exp_a_text_scorer,
    exp_b_execution_scorer,
)
from causalverify_inspect.solvers import exp_a_protocol, exp_b_protocol  # noqa: E402
from src.pipeline.score_l2b_plus import DEFAULT_TOL  # noqa: E402

#: Docker sandbox definition, resolved by Inspect relative to this file.
SANDBOX_COMPOSE = "compose.yaml"

_PAPER = {"benchmark": "CausalVerify", "paper": "arXiv:2609.07944"}


@task
def causalverify_exp_a(data_root: str | None = None) -> Task:
    """CausalVerify Experiment A: identification-strategy plans for published papers.

    Text-level layers L1 (non-empty), L3 (method-family agreement) and L4
    (direction agreement), plus the S1/S2 direction scorers. No code execution.

    Args:
      data_root: directory with the benchmark items and targets
        (default: ``$CAUSALVERIFY_DATA``).
    """
    return Task(
        dataset=load_exp_a_dataset(data_root),
        solver=exp_a_protocol(),
        scorer=exp_a_text_scorer(),
        metadata={**_PAPER, "experiment": "A", "layers": ["L1", "L3", "L4", "S1", "S2"]},
    )


@task
def causalverify_exp_b(
    data_root: str | None = None,
    tolerance: float = DEFAULT_TOL,
    baseline: str = "canonical",
    judge: bool = False,
    r_timeout: int = 60,
) -> Task:
    """CausalVerify Experiment B: executable R analyses of synthetic DGP scenarios.

    Execution-grounded layers L1, L2a (R code present), L2b (code runs) and
    L2b+ (estimate matches the baseline within ``tolerance``), plus text-level
    L3/L4 and S1/S2.

    Args:
      data_root: directory with the benchmark items and targets
        (default: ``$CAUSALVERIFY_DATA``).
      tolerance: L2b+ relative-error tolerance (paper: 0.5).
      baseline: ``"canonical"`` (paper headline) or ``"dgp"``.
      judge: enable the LLM-judge coefficient extraction and event-study-aware
        L2b+ (``--model-role grader=...``; defaults to the paper's judge model).
      r_timeout: seconds allowed per R script (paper: 60).
    """
    return Task(
        dataset=load_exp_b_dataset(data_root, baseline=baseline),
        solver=exp_b_protocol(),
        scorer=exp_b_execution_scorer(
            tolerance=tolerance, baseline=baseline, judge=judge, r_timeout=r_timeout
        ),
        sandbox=("docker", SANDBOX_COMPOSE),
        metadata={
            **_PAPER,
            "experiment": "B",
            "layers": ["L1", "L2a", "L2b", "L2b+", "L3", "L4", "S1", "S2"],
            "tolerance": tolerance,
            "baseline": baseline,
            "judge": judge,
        },
    )
