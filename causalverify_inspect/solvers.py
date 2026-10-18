"""Solvers reproducing the paper's prompting protocol.

Both experiments were run as a single turn: the experiment's system prompt,
one user message (the formatted research setup, which is the sample input),
one completion. No tools, no retries, no chain-of-thought scaffolding. The
system prompt text is imported from ``src/prompts`` and inserted verbatim.
"""

from __future__ import annotations

from inspect_ai.solver import Solver, chain, generate, solver, system_message

from src.prompts import exp_a as exp_a_prompts
from src.prompts import exp_b as exp_b_prompts


@solver
def exp_a_protocol() -> Solver:
    """Experiment A protocol of ``src/pipeline/run_exp_a.py``.

    System prompt ``src.prompts.exp_a.SYSTEM_PROMPT``; the user turn is the
    sample input (``USER_PROMPT_TEMPLATE`` filled with research question, data
    description and institutional context); then one ``generate()``.
    """
    return chain(system_message(exp_a_prompts.SYSTEM_PROMPT), generate())


@solver
def exp_b_protocol() -> Solver:
    """Experiment B protocol of ``src/pipeline/run_exp_b.py``.

    System prompt ``src.prompts.exp_b.SYSTEM_PROMPT`` (asks for identification
    strategy, complete R code, expected findings); the user turn is the sample
    input built by ``build_user_prompt`` (scenario, data path, five-row preview,
    column types); then one ``generate()``.
    """
    return chain(system_message(exp_b_prompts.SYSTEM_PROMPT), generate())
