"""Benchmark items -> Inspect ``Sample`` objects.

Items and targets are read from the directory returned by
:func:`causalverify_inspect._repo.resolve_data_root` (``CAUSALVERIFY_DATA`` or
the ``data_root`` task parameter). The directory mirrors the repository
layout; the relative paths below are the pipeline's own constants, so the
Inspect port reads exactly the files the scoring scripts read.

Nothing in this module invents prompt text: Experiment A prompts are
``src.prompts.exp_a.USER_PROMPT_TEMPLATE`` filled with the item fields, and
Experiment B prompts come from ``src.prompts.exp_b.build_user_prompt`` (five-row
data preview + column types), exactly as in the paper's runs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample

from causalverify_inspect._repo import (
    CausalVerifyDataError,
    encode_target,
    resolve_data_root,
)
from src.pipeline import auto_score_exp_a as exp_a_scoring
from src.pipeline import score_l2b_plus as l2b_plus
from src.prompts import exp_a as exp_a_prompts
from src.prompts import exp_b as exp_b_prompts

logger = logging.getLogger(__name__)

# Relative locations under the data root (identical to the pipeline constants).
EXP_A_PAPERS_DIR: Path = exp_a_scoring.PAPERS_DIR  # experiments/exp_a/papers
EXP_A_GT_PATH: Path = exp_a_scoring.GT_PATH  # audit/gt_aggregate_decisions.json
EXP_B_SCENARIOS_DIR: Path = l2b_plus.SCEN_DIR  # experiments/exp_b/scenarios
EXP_B_CANONICAL_PATH: Path = l2b_plus.CANONICAL_BASELINES  # audit/dgp_verification.json

#: Scenario fields a model is shown (the public ``experiments/exp_b/scenarios``
#: files carry exactly these). Everything else in a scenario is a target.
EXP_B_TASK_FACING_FIELDS = (
    "scenario_id",
    "method_family",
    "difficulty",
    "title",
    "research_question",
    "data_description",
    "data_file",
)

BASELINES = ("dgp", "canonical")


# ── Experiment A ─────────────────────────────────────────────────────────────


def exp_a_paper_files(data_root: Path) -> list[Path]:
    """Paper JSON files in the pipeline's natural order (paper_1, paper_2, ...)."""
    papers_dir = data_root / EXP_A_PAPERS_DIR
    files = sorted(papers_dir.glob("paper_*.json"), key=exp_a_scoring.natural_paper_num)
    if not files:
        raise CausalVerifyDataError(f"No Experiment A items (paper_*.json) found in {papers_dir}")
    return files


def exp_a_sample(paper: dict, gt: dict) -> Sample:
    """Build the Inspect sample for one Experiment A paper.

    ``gt`` is the output of ``auto_score_exp_a.gt_for_paper`` (method, direction,
    scoreable flags, consensus levels). It is stored as the sample target; the
    fields the scorer needs from the paper record are stored in metadata.
    """
    prompt = exp_a_prompts.USER_PROMPT_TEMPLATE.format(
        research_question=paper["research_question"],
        data_description=paper["data_description"],
        institutional_context=paper["institutional_context"],
    )
    return Sample(
        id=paper["paper_id"],
        input=prompt,
        target=encode_target(gt),
        metadata={
            "experiment": "exp_a",
            # Exactly the paper fields auto_score_exp_a.score_output reads.
            "paper": {
                "paper_id": paper["paper_id"],
                "method_family": paper.get("method_family"),
                "difficulty": paper["difficulty"],
            },
            # Group keys for per-method metrics (pipeline's `method_family` column).
            "method_family": gt["method"] or "UNSCORED",
            "difficulty": paper["difficulty"],
        },
    )


def load_exp_a_dataset(data_root: str | Path | None = None) -> MemoryDataset:
    """Experiment A: one sample per paper, targets from the 4-LLM consensus file."""
    root = resolve_data_root(data_root)
    gt_path = root / EXP_A_GT_PATH
    try:
        gt_by_pid = exp_a_scoring.load_gt_aggregate(gt_path)
    except FileNotFoundError as exc:
        raise CausalVerifyDataError(
            f"Experiment A targets not found at {gt_path}. The public repository does not "
            "ship them; point CAUSALVERIFY_DATA at the full benchmark items."
        ) from exc

    samples = []
    for paper_file in exp_a_paper_files(root):
        paper = json.loads(paper_file.read_text(encoding="utf-8"))
        gt = exp_a_scoring.gt_for_paper(paper, gt_by_pid)  # raises KeyError if a target is missing
        samples.append(exp_a_sample(paper, gt))
    return MemoryDataset(samples=samples, name="causalverify_exp_a", location=str(root / EXP_A_PAPERS_DIR))


# ── Experiment B ─────────────────────────────────────────────────────────────


def exp_b_scenario_files(data_root: Path) -> list[Path]:
    """Scenario JSON files in the pipeline's numeric order (s1, s2, ..., s100)."""
    scen_dir = data_root / EXP_B_SCENARIOS_DIR
    files = sorted(scen_dir.glob("s*.json"), key=lambda p: int(p.stem[1:]))
    if not files:
        raise CausalVerifyDataError(f"No Experiment B scenarios (s*.json) found in {scen_dir}")
    return files


def exp_b_sample(scenario: dict, canonical: dict | None, data_root: Path) -> Sample:
    """Build the Inspect sample for one Experiment B scenario.

    The realised dataset is attached via ``Sample.files`` under the scenario's
    repository-relative ``data_file`` path, which is also the path the prompt
    tells the model to read. Inside the sandbox the model's R code therefore
    finds the CSV exactly where the paper's runs did.
    """
    data_path = data_root / scenario["data_file"]
    if not data_path.is_file():
        raise CausalVerifyDataError(
            f"Realised dataset for {scenario['scenario_id']} not found: {data_path}"
        )
    prompt = exp_b_prompts.build_user_prompt(scenario, data_root=data_root)
    target = {
        "dgp_truth": scenario.get("dgp_truth") or {},
        "ground_truth": scenario.get("ground_truth") or {},
        "canonical": canonical,
    }
    return Sample(
        id=scenario["scenario_id"],
        input=prompt,
        target=encode_target(target),
        metadata={
            "experiment": "exp_b",
            "scenario": {k: scenario[k] for k in EXP_B_TASK_FACING_FIELDS if k in scenario},
            "method_family": scenario["method_family"],
            "difficulty": scenario["difficulty"],
        },
        files={scenario["data_file"]: str(data_path)},
    )


def load_exp_b_dataset(
    data_root: str | Path | None = None, baseline: str = "canonical"
) -> MemoryDataset:
    """Experiment B: one sample per scenario, with DGP and canonical targets.

    ``baseline`` selects what L2b+ compares against, as in
    ``score_l2b_plus.py --baseline``: ``"canonical"`` (the paper's headline: the
    canonical estimator on the realised data, from ``audit/dgp_verification.json``)
    or ``"dgp"`` (the ideal DGP parameter in each scenario's ``dgp_truth``).
    """
    if baseline not in BASELINES:
        raise ValueError(f"baseline must be one of {BASELINES}, got {baseline!r}")
    root = resolve_data_root(data_root)

    canonical = l2b_plus.load_canonical_baselines(root / EXP_B_CANONICAL_PATH)
    if baseline == "canonical" and not canonical:
        raise CausalVerifyDataError(
            f"baseline='canonical' requested but {root / EXP_B_CANONICAL_PATH} is missing or "
            "empty (the pipeline raises the same error; run src/agents/dgp_verifier.py or use "
            "-T baseline=dgp)."
        )

    samples, missing_targets = [], []
    for scen_file in exp_b_scenario_files(root):
        scenario = json.loads(scen_file.read_text(encoding="utf-8"))
        if "dgp_truth" not in scenario:
            missing_targets.append(scenario["scenario_id"])
        samples.append(exp_b_sample(scenario, canonical.get(scenario["scenario_id"]), root))

    if missing_targets:
        msg = (
            f"{len(missing_targets)} scenario(s) carry no dgp_truth (e.g. {missing_targets[:3]}). "
            "The public task-facing scenario files omit targets; point CAUSALVERIFY_DATA at the "
            "full benchmark items."
        )
        if baseline == "dgp":
            raise CausalVerifyDataError(msg)
        logger.warning("%s Text-level L4/S1/S2 agreement will be 0 for those scenarios.", msg)

    return MemoryDataset(samples=samples, name="causalverify_exp_b", location=str(root / EXP_B_SCENARIOS_DIR))
