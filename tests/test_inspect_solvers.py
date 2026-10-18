"""Solver wiring: the Inspect solvers reproduce the paper's single-turn prompting verbatim."""

from __future__ import annotations

import asyncio

from inspect_ai.model import ChatMessageUser, ModelName, ModelOutput
from inspect_ai.solver import TaskState

from causalverify_inspect.solvers import exp_a_protocol, exp_b_protocol
from src.prompts import exp_a as exp_a_prompts
from src.prompts import exp_b as exp_b_prompts


def _run(solver, user_prompt: str) -> TaskState:
    state = TaskState(
        model=ModelName("mockllm/model"),
        sample_id="synthetic",
        epoch=1,
        input=user_prompt,
        messages=[ChatMessageUser(content=user_prompt)],
        metadata={"experiment": "test", "paper": {"paper_id": "p"}},
    )

    async def fake_generate(state: TaskState, tool_calls="loop", **kwargs) -> TaskState:
        state.output = ModelOutput.from_content("mockllm", "synthetic completion")
        return state

    return asyncio.run(solver(state, fake_generate))


def test_exp_a_solver_inserts_the_runners_system_prompt_verbatim():
    state = _run(exp_a_protocol(), "USER TURN {with braces} and {research_question}")
    assert [m.role for m in state.messages] == ["system", "user"]
    assert state.messages[0].text == exp_a_prompts.SYSTEM_PROMPT
    assert state.messages[1].text == "USER TURN {with braces} and {research_question}"
    assert state.output.completion == "synthetic completion"


def test_exp_b_solver_inserts_the_runners_system_prompt_verbatim():
    state = _run(exp_b_protocol(), "Research scenario: SYNTHETIC")
    assert [m.role for m in state.messages] == ["system", "user"]
    assert state.messages[0].text == exp_b_prompts.SYSTEM_PROMPT
    assert "## 2. R Code" in state.messages[0].text  # the paper's three-section format


def test_prompt_modules_hold_the_runners_text(tmp_path, monkeypatch):
    """run_exp_a / run_exp_b still expose the same objects (importers such as run_b2_ablation rely on them)."""
    monkeypatch.chdir(tmp_path)  # the runners create their outputs directory on import
    from src.pipeline import run_exp_a, run_exp_b

    assert run_exp_a.SYSTEM_PROMPT is exp_a_prompts.SYSTEM_PROMPT
    assert run_exp_a.USER_PROMPT_TEMPLATE is exp_a_prompts.USER_PROMPT_TEMPLATE
    assert run_exp_b.SYSTEM_PROMPT is exp_b_prompts.SYSTEM_PROMPT
    assert run_exp_b.USER_PROMPT_TEMPLATE is exp_b_prompts.USER_PROMPT_TEMPLATE
    assert run_exp_b.build_user_prompt is exp_b_prompts.build_user_prompt
