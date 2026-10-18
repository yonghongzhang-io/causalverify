"""Optional LLM-judge coefficient extraction and event-study-aware L2b+.

The paper's headline L2b+ ("canonical judge v2") does not rely on the regex
coefficient extractor alone: for every output whose R code ran (L2b = 1), an
LLM judge reads the executed code and its stdout and returns the treatment
effect (``scripts/l2b_llm_judge_extract.py``), and event-study outputs are
accepted when they match the canonical per-day abnormal return over *any*
post-event window of 1..11 days (``scripts/recompute_l2b_plus_es_aware.py``).

This module reuses those scripts' artefacts rather than re-typing them:

* the judge prompts (``SYSTEM_PROMPT``, ``USER_TEMPLATE``, ``METHOD_GUIDANCE``)
  and the paper's judge model id are read from the judge script's source with
  ``ast`` (importing the script would re-import the scorer under a second
  module name and load ``.env``);
* ``es_pass`` and ``ES_MAX_WINDOW_DAYS`` are imported from the (side-effect
  free) ES-aware re-scoring script.

In Inspect the judge is the ``grader`` model role::

    inspect eval ... -T judge=true --model-role grader=anthropic/claude-haiku-4-5-20251001
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, GenerateConfig, Model

from causalverify_inspect._repo import REPO_ROOT

JUDGE_SCRIPT = REPO_ROOT / "scripts" / "l2b_llm_judge_extract.py"
ES_AWARE_SCRIPT = REPO_ROOT / "scripts" / "recompute_l2b_plus_es_aware.py"

#: Inspect model role used for the judge (``--model-role grader=...``).
JUDGE_ROLE = "grader"


def _literal_constants(path: Path, names: tuple[str, ...]) -> dict[str, Any]:
    """Return module-level literal assignments ``name = <literal>`` from a source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in names:
                found[target.id] = ast.literal_eval(node.value)
    missing = set(names) - set(found)
    if missing:
        raise RuntimeError(f"{path} no longer defines {sorted(missing)}")
    return found


def _load_script_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_JUDGE = _literal_constants(
    JUDGE_SCRIPT, ("SYSTEM_PROMPT", "USER_TEMPLATE", "METHOD_GUIDANCE", "JUDGE_MODEL")
)
JUDGE_SYSTEM_PROMPT: str = _JUDGE["SYSTEM_PROMPT"]
JUDGE_USER_TEMPLATE: str = _JUDGE["USER_TEMPLATE"]
METHOD_GUIDANCE: dict[str, str] = _JUDGE["METHOD_GUIDANCE"]
#: The paper's judge model, as an Inspect model name (used when no ``grader`` role is bound).
DEFAULT_JUDGE_MODEL = f"anthropic/{_JUDGE['JUDGE_MODEL']}"

_ES = _load_script_module(ES_AWARE_SCRIPT, "causalverify_recompute_l2b_plus_es_aware")
es_pass = _ES.es_pass
ES_MAX_WINDOW_DAYS: int = _ES.ES_MAX_WINDOW_DAYS

# Same truncation limits as l2b_llm_judge_extract.call_judge.
_TITLE_CHARS, _CODE_CHARS, _STDOUT_CHARS, _MAX_TOKENS = 200, 4000, 6000, 200


def build_judge_messages(method: str, title: str, r_code: str, stdout: str) -> list:
    """Judge conversation exactly as ``call_judge`` builds it."""
    user = JUDGE_USER_TEMPLATE.format(
        method=method,
        method_guidance=METHOD_GUIDANCE.get(method, "(no method guidance)"),
        title=title[:_TITLE_CHARS],
        r_code=r_code[:_CODE_CHARS],
        stdout=stdout[:_STDOUT_CHARS],
    )
    return [ChatMessageSystem(content=JUDGE_SYSTEM_PROMPT), ChatMessageUser(content=user)]


def parse_judge_response(raw: str) -> tuple[float | None, str]:
    """Parse the judge's ``{"effect": ..., "rationale": ...}`` reply (as ``call_judge`` does)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip("` \n")
    parsed: Any
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        parsed = {"effect": None, "rationale": f"parse_error: {raw[:120]}"}
        m = re.search(r'"effect"\s*:\s*(-?\d+\.?\d*(?:[eE][-+]?\d+)?|null)', raw)
        if m and m.group(1) != "null":
            try:
                parsed["effect"] = float(m.group(1))
            except ValueError:
                pass
    effect = parsed.get("effect")
    if isinstance(effect, str):
        try:
            effect = float(effect)
        except ValueError:
            effect = None
    if isinstance(effect, bool) or not isinstance(effect, (int, float)):
        effect = None
    return (float(effect) if effect is not None else None), str(parsed.get("rationale", ""))[:200]


async def judge_treatment_effect(
    model: Model, method: str, title: str, r_code: str, stdout: str
) -> dict[str, Any]:
    """Ask the judge model for the treatment effect in ``stdout``."""
    output = await model.generate(
        build_judge_messages(method, title, r_code, stdout),
        config=GenerateConfig(max_tokens=_MAX_TOKENS),
    )
    effect, rationale = parse_judge_response(output.completion)
    return {"judge_effect": effect, "judge_rationale": rationale, "judge_raw": output.completion}


def judge_l2b_plus(
    judge_effect: float | None, baseline_effect: float | None, method: str, tolerance: float
) -> dict[str, Any]:
    """Judge-based L2b+ and the event-study-aware v2 variant.

    * ``L2b_plus_judge``: ``|judge - baseline| / |baseline| < tolerance``
      (``l2b_llm_judge_extract.py``).
    * ``L2b_plus_v2``: for EVENT_STUDY, ``es_pass`` accepts a match to
      ``baseline x k`` for any window length ``k`` in 1..ES_MAX_WINDOW_DAYS;
      for every other method it equals ``L2b_plus_judge``
      (``recompute_l2b_plus_es_aware.py``).
    """
    rel_error = None
    l2b_plus_judge = 0
    if judge_effect is not None and baseline_effect is not None and abs(baseline_effect) > 1e-9:
        rel_error = abs(judge_effect - baseline_effect) / abs(baseline_effect)
        l2b_plus_judge = int(rel_error < tolerance)

    if method == "EVENT_STUDY":
        ok, best_k, rel_error_v2 = es_pass(judge_effect, baseline_effect, tol=tolerance)
        l2b_plus_v2 = int(ok)
    else:
        ok, best_k, rel_error_v2 = bool(l2b_plus_judge), None, rel_error
        l2b_plus_v2 = l2b_plus_judge

    return {
        "rel_error_judge": rel_error,
        "L2b_plus_judge": l2b_plus_judge,
        "L2b_plus_v2": l2b_plus_v2,
        "es_window_match": best_k,
        "rel_error_v2": rel_error_v2,
    }
