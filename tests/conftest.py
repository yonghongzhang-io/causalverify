"""Shared pytest configuration for the CausalVerify test-suite.

Makes the repository root importable (the project is not pip-installed; the
pipeline uses ``from src...`` imports rooted here) and provides the synthetic
fixture used by the Inspect-port tests. Nothing here touches real benchmark data.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: Hand-made items/targets/completions. See its README: everything is made up.
SYNTHETIC_ROOT = REPO_ROOT / "tests" / "fixtures" / "synthetic_causalverify_data"
FAKE_RSCRIPT = REPO_ROOT / "tests" / "fixtures" / "fake_rscript" / "Rscript"


@pytest.fixture(scope="session")
def synthetic_root() -> Path:
    return SYNTHETIC_ROOT.resolve()


@pytest.fixture
def fake_rscript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put the stand-in ``Rscript`` first on ``PATH`` (copied and chmod-ed, so a lost exec bit cannot break CI)."""
    bin_dir = tmp_path / "fake-r-bin"
    bin_dir.mkdir()
    target = bin_dir / "Rscript"
    shutil.copy(FAKE_RSCRIPT, target)
    target.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return target


def load_synthetic_outputs(experiment: str) -> dict[str, dict]:
    """Canned completions in the pipeline's ``outputs/*.json`` format, keyed by item id."""
    key = "paper_id" if experiment == "exp_a" else "scenario_id"
    records = {}
    for path in sorted((SYNTHETIC_ROOT / "synthetic_outputs" / experiment).glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        records[rec[key]] = rec
    return records


def load_synthetic_items(experiment: str) -> dict[str, dict]:
    """Full synthetic items (including made-up targets), keyed by item id."""
    if experiment == "exp_a":
        folder, key = SYNTHETIC_ROOT / "experiments" / "exp_a" / "papers", "paper_id"
    else:
        folder, key = SYNTHETIC_ROOT / "experiments" / "exp_b" / "scenarios", "scenario_id"
    items = {}
    for path in sorted(folder.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        items[item[key]] = item
    return items
