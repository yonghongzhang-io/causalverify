"""Repository paths, benchmark-data location and target (de)serialisation."""

from __future__ import annotations

import json
import os
from pathlib import Path

from inspect_ai.scorer import Target

#: Root of the public repository checkout (parent of this package).
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Environment variable naming the directory that holds the benchmark items
#: *with* their scoring targets. That directory is distributed separately and
#: must never be committed here (see REDACTIONS.md).
DATA_ENV_VAR = "CAUSALVERIFY_DATA"

#: Layout expected under the data root. It mirrors the repository layout so
#: that the author's full (private) checkout can be used directly.
DATA_LAYOUT = """\
<data root>/
  experiments/exp_a/papers/paper_*.json      Experiment A items (task-facing fields)
  audit/gt_aggregate_decisions.json          Experiment A targets (new_method, new_direction, ...)
  experiments/exp_b/scenarios/s*.json        Experiment B items incl. dgp_truth / ground_truth
  experiments/exp_b/data/s*_data.csv         realised Experiment B datasets
  audit/dgp_verification.json                canonical-estimator baselines (baseline="canonical")
"""


class CausalVerifyDataError(RuntimeError):
    """The benchmark items/targets could not be located or are incomplete."""


def resolve_data_root(data_root: str | os.PathLike[str] | None = None) -> Path:
    """Return the directory holding the benchmark items and targets.

    ``data_root`` wins over the ``CAUSALVERIFY_DATA`` environment variable.
    Relative paths are tried against the current working directory and then
    against the repository root (Inspect changes directory into the task file's
    folder while creating tasks, so a repository-relative path keeps working).
    """
    raw = str(data_root if data_root is not None else os.environ.get(DATA_ENV_VAR, "")).strip()
    if not raw:
        raise CausalVerifyDataError(
            "No benchmark data location given. Set the CAUSALVERIFY_DATA environment "
            "variable or pass -T data_root=<dir>. The public repository does not ship "
            "the benchmark targets (see REDACTIONS.md); the expected layout is:\n"
            + DATA_LAYOUT
        )
    path = Path(raw).expanduser()
    candidates = [path] if path.is_absolute() else [Path.cwd() / path, REPO_ROOT / path]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    tried = ", ".join(str(c) for c in candidates)
    raise CausalVerifyDataError(
        f"Benchmark data directory not found: {raw!r} (tried {tried}). Expected layout:\n"
        + DATA_LAYOUT
    )


def encode_target(payload: dict) -> str:
    """Serialise a scoring target dict into the ``Sample.target`` string."""
    return json.dumps(payload, sort_keys=True, default=str)


def decode_target(target: Target | str) -> dict:
    """Inverse of :func:`encode_target` for use inside scorers."""
    text = target if isinstance(target, str) else target.text
    return json.loads(text)
