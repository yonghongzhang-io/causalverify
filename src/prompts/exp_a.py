"""Experiment A prompt (verbatim from the paper's runner).

These two strings are the exact system prompt and user-prompt template used
by ``src/pipeline/run_exp_a.py`` for every Experiment A model call. They
live here so that other entry points (``run_b2_ablation.py``,
``gemini_retry.py``, the Inspect port in ``causalverify_inspect/``) can
import the prompt text without importing the runner module, which has
import-time side effects (``load_dotenv()``, creating the outputs directory).

Do not edit the text: the published Experiment A outputs were generated with it.
"""

SYSTEM_PROMPT = """\
You are a financial economist with expertise in empirical methods including
difference-in-differences, event studies, instrumental variables, and regression
discontinuity designs. You are helping conduct original empirical research.

Your task: Given a research question, available data, and institutional context,
propose a rigorous identification strategy and outline the empirical methodology.

IMPORTANT: Do NOT read ahead or guess the actual paper's methodology. Work only
from the information provided. Propose what YOU would do given this setup.
"""

USER_PROMPT_TEMPLATE = """\
# Research Setup

## Research Question
{research_question}

## Available Data
{data_description}

## Institutional Context
{institutional_context}

---

Please provide a complete empirical research plan with the following sections:

## 1. Identification Strategy
State clearly which causal identification strategy you would use (DID, event study,
IV, RDD, or other). Justify why this strategy is appropriate for this research
question and data.

## 2. Treatment and Control
Define precisely:
- Treatment variable (what constitutes "treated")
- Control group (what serves as counterfactual)
- Treatment timing / event date (if applicable)
- Running variable and cutoff (if RDD)

## 3. Key Identifying Assumptions
List the main assumptions required for your strategy to yield causal estimates.
For each assumption, discuss whether it is plausible given the institutional context.

## 4. Threats to Identification
Identify the 2–3 most important threats to your identification strategy.
How would you address each threat?

## 5. R Code Outline
Write executable R code for the main specification. Include:
- Data loading steps (assume data is in CSV format)
- Variable construction
- Main regression using appropriate package (fixest, rdrobust, ivreg, etc.)
- At least one robustness check

## 6. Expected Results
State your prior expectation for the direction of the main effect and its
approximate magnitude (if you can form a prior from economic theory).

## 7. Validity Checklist Self-Assessment
Rate yourself on the 5-item validity checklist for your chosen method
(1 = clearly satisfied, 0 = questionable or absent):
- C1: [checklist item 1]
- C2: [checklist item 2]
- C3: [checklist item 3]
- C4: [checklist item 4]
- C5: [checklist item 5]
"""
