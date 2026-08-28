# Human vs 4-LLM consensus audit

Labels file: `audit/human_gold/paper_native_labels.csv`
GT file: `audit/gt_aggregate_decisions.json`
Output CSV: `audit/human_gold/human_vs_llm_consensus.csv`

## Progress

- First-pass human labels compared: 30
- Target30 completed: 30/30
- Target30 pending: 0

## Agreement

- Method-family simple agreement: 18/30 = 60.0%
- Method-family Cohen kappa: 0.606
- Direction simple agreement: 10/21 = 47.6%
- Direction Cohen kappa: 0.294

## Method agreement by 4-LLM consensus level

| m_level | n | method match |
|---|---:|---:|
| 2of4_plurality | 16 | 56.2% |
| 2of4_tie | 3 | 0.0% |
| 3of4_agree | 5 | 100.0% |
| all4_agree | 4 | 100.0% |
| split | 2 | 0.0% |

## Interpretation guardrail

This audit validates the 4-LLM consensus labels against a paper-native
human slice. It does not make the full 259-paper Exp A corpus
human-gold labeled. If Target30 is incomplete, report these numbers as
progress-only and do not use them as final paper evidence.
