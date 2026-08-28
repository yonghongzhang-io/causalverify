# Legacy artifacts (audit-only)

This directory holds pre-CausalVerify and pre-final-submission material
retained only for auditability. **Nothing in this directory is used for
the final CausalVerify NeurIPS 2026 E&D Track submission claims.**

Reviewers reproducing the headline numbers should use the entry points
listed in `README.md` and `RELEASE_NAVIGATION.md` at the repository root,
not anything under `legacy/`.

## Contents

- **`evaluate_v1_causalbench.py`** — original CAUSAL-BENCH-era one-command
  evaluator. It calls itself "the official evaluation script for the
  NeurIPS 2026 Evaluations & Datasets Track" and references obsolete
  scope numbers (e.g. `n_papers=57`, 45 papers, 30 scenarios, 270/180
  outputs). It reads paper JSON `ground_truth` directly, which is no
  longer the source of truth in CausalVerify (the four-LLM consensus
  labels in `audit/gt_aggregate_decisions.json` superseded that field).
  Retained only to document the prior project state.

## Why kept rather than deleted

- Pre-registration discipline: prior evaluation code is part of the
  paper trail.
- A reviewer auditing the project's evolution can compare the legacy
  evaluator against the current scoring stack.
- Deleting it silently would erase that audit trail.

## What replaces it for current claims

| Old role | Current entry point |
|---|---|
| Score Exp A L1/L2a/L2b/L3/L4 | `python src/pipeline/auto_score_exp_a.py` |
| Score Exp B L2b+ (regex) | `python src/pipeline/score_l2b_plus.py --baseline canonical` |
| Re-judge L2b+ with Haiku (cache only) | `python scripts/l2b_llm_judge_extract.py --all` |
| ES-aware re-scoring | `python scripts/recompute_l2b_plus_es_aware.py` |
| Head-to-head ranking | `python src/pipeline/head_to_head_ranking.py` |
| Robustness aggregation | `python scripts/analyze_exp_b_robustness.py` |
| Cross-doc claim consistency | `python scripts/check_claim_consistency.py` |
| Reviewer-facing dispatcher | `python evaluate.py` (top-level wrapper) |
