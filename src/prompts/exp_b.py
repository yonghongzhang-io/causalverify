"""Experiment B prompt (verbatim from the paper's runner).

``SYSTEM_PROMPT`` and ``USER_PROMPT_TEMPLATE`` are the exact strings used by
``src/pipeline/run_exp_b.py`` for every Experiment B model call, and
``build_user_prompt`` is the exact prompt construction (five-row data preview
plus pandas column types). They live here so that the Inspect port in
``causalverify_inspect/`` can build identical prompts without importing the
runner module, which has import-time side effects (``load_dotenv()``,
creating the outputs directory).

The only addition is the optional ``data_root`` argument of
``build_user_prompt``: when given, the scenario's ``data_file`` is read from
under that directory instead of the current working directory. The prompt text
itself still shows the repository-relative ``data_file`` path, exactly as in
the paper's runs. With ``data_root=None`` the behaviour is unchanged.

Do not edit the text: the published Experiment B outputs were generated with it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SYSTEM_PROMPT = """You are an expert financial economist and econometrician.
You will be given a research scenario with a data description and a sample of the dataset.
Your task is to implement a complete empirical analysis.

Respond in exactly this structure:

## 1. Identification Strategy
[Which causal method (DID / Event Study / IV / RDD) and why. State the key assumption(s).]

## 2. R Code
```r
# Complete, self-contained R code that:
# - Reads the CSV file from the path provided
# - Runs the appropriate causal analysis
# - Prints a clear numerical result (coefficient, CAR, etc.)
# - Includes basic robustness checks
```

## 3. Expected Findings
[What sign and approximate magnitude do you expect? Why?]
"""

USER_PROMPT_TEMPLATE = """Research scenario: {title}

Research question:
{research_question}

Data description:
{data_description}

Data file path: {data_file}

Data preview (first 5 rows):
{data_preview}

Column types:
{col_types}

Please implement the full analysis."""


def build_user_prompt(scenario: dict, data_root: str | Path | None = None) -> str:
    data_file = scenario["data_file"]
    csv_path = Path(data_root) / data_file if data_root is not None else data_file
    df = pd.read_csv(csv_path, nrows=5)
    preview = df.to_string(index=False)
    col_info = "\n".join(f"  {c}: {str(t)}" for c, t in df.dtypes.items())
    return USER_PROMPT_TEMPLATE.format(
        title=scenario["title"],
        research_question=scenario["research_question"],
        data_description=scenario["data_description"],
        data_file=data_file,
        data_preview=preview,
        col_types=col_info,
    )
