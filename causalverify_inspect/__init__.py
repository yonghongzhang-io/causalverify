"""Inspect (UK AISI ``inspect_ai``) port of the CausalVerify benchmark.

The port is a thin wrapper around the repository's own benchmark code:

* prompts come from :mod:`src.prompts.exp_a` / :mod:`src.prompts.exp_b`
  (the exact text used by ``src/pipeline/run_exp_a.py`` / ``run_exp_b.py``);
* scores are computed by calling the existing scoring functions in
  :mod:`src.pipeline.auto_score_exp_a`, :mod:`src.pipeline.score_l2b_plus`,
  :mod:`src.pipeline.score_exp_b` and :mod:`src.pipeline.multi_scorer_l4`,
  so an Inspect run produces the same per-item scores as ``scripts/rescore.sh``.

Tasks are defined in :mod:`causalverify_inspect.tasks` and run with::

    export CAUSALVERIFY_DATA=/path/to/benchmark/items   # not in this repository
    inspect eval causalverify_inspect/tasks.py@causalverify_exp_b --model <provider/model>

This module deliberately does not import ``tasks`` (Inspect loads the task
file by path; importing it here as well would register every task twice).
"""

__version__ = "0.1.0"
