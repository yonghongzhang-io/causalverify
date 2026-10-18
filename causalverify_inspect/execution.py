"""Run model-generated R code inside the sample's Inspect sandbox.

This is the sandbox counterpart of ``score_l2b_plus.execute_r_code``: it writes
the *same* wrapped script (``wrap_r_code``), runs ``Rscript --vanilla`` with the
same timeout semantics, and returns the same ``(success, stdout, stderr)``
triple, so that ``score_l2b_plus.score_output(..., executor=...)`` can do all of
the actual scoring.

Where the code runs is decided by the eval's sandbox: the task's default is the
Docker image built from the repository ``Dockerfile`` (R 4.4.2 + fixest, AER,
rdrobust, ...); ``--sandbox local`` runs ``Rscript`` from the host ``PATH``
inside a per-sample temporary directory.
"""

from __future__ import annotations

from inspect_ai.util import sandbox

from src.pipeline.score_l2b_plus import wrap_r_code

#: Name of the script written into the sandbox working directory.
R_SCRIPT_NAME = "causalverify_l2b_plus.R"


async def execute_r_code_in_sandbox(code: str, timeout: int = 60) -> tuple[bool, str, str]:
    """Execute ``code`` in the current sample's sandbox.

    Mirrors ``execute_r_code``: ``(returncode == 0, stdout, last 500 chars of
    stderr)``; a timeout yields ``(False, "", "timeout")`` and any other failure
    to run (no sandbox, no ``Rscript`` binary, ...) yields ``(False, "", <error>)``
    so that L2b is scored 0 with the reason recorded, exactly as the pipeline
    does on a host without R.
    """
    try:
        sb = sandbox()
        await sb.write_file(R_SCRIPT_NAME, wrap_r_code(code))
        result = await sb.exec(
            ["Rscript", "--vanilla", R_SCRIPT_NAME],
            timeout=timeout,
            timeout_retry=False,  # the pipeline does not retry timed-out scripts
        )
        return result.returncode == 0, result.stdout, result.stderr.strip()[-500:]
    except TimeoutError:
        return False, "", "timeout"
    except Exception as exc:  # noqa: BLE001 - same contract as execute_r_code
        return False, "", str(exc)
