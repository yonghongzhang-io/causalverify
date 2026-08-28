# Exp B Robustness Audit

This audit strengthens the interpretation of Exp B without replacing the
frozen headline L2b+ artifacts. It is derived from
`experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv` and does not
make LLM API calls or regenerate model outputs.

## Interpretation

- L2b+ requires L2b, so a raw association between L2b and L2b+ is partly
  structural: code must execute before a coefficient can be checked.
- The conditional metric `P(L2b+ v2 | L2b)` asks a sharper question:
  among outputs whose code executed, how often did the workflow compute
  the canonical treatment-effect estimate on the realised dataset?
- Primary-7 results are kept separate from Llama. Llama-3.3-70B-Instruct
  is retained only as an open-weights robustness check and is not part of
  the primary 7-model Kendall/Spearman ranking.
- L2b+ means coefficient agreement with the canonical estimator on the
  realised dataset, not recovery of the ideal DGP beta parameter.

## Primary-7 Conditional L2b Table

| Model | n | L2b | L2b+ v2 | Executed but not correct | P(L2b+ v2 given L2b) |
|---|---:|---:|---:|---:|---:|
| Kimi | 100 | 45 (0.45) | 10 (0.10) | 35 | 0.22 |
| Sonnet | 100 | 51 (0.51) | 50 (0.50) | 1 | 0.98 |
| GPT-4o | 100 | 78 (0.78) | 62 (0.62) | 16 | 0.79 |
| o3 | 100 | 50 (0.50) | 46 (0.46) | 4 | 0.92 |
| Opus | 100 | 94 (0.94) | 88 (0.88) | 6 | 0.94 |
| Gemini | 100 | 32 (0.32) | 32 (0.32) | 0 | 1.00 |
| GPT-5 | 100 | 76 (0.76) | 72 (0.72) | 4 | 0.95 |

## Llama Robustness-Only Result

| Model | n | L2b | L2b+ v2 | Executed but not correct | P(L2b+ v2 given L2b) |
|---|---:|---:|---:|---:|---:|
| Llama | 100 | 41 (0.41) | 20 (0.20) | 21 | 0.49 |

## Generated Files

- `paper/tables/exp_b_l2b_conditional_primary7.csv`
- `paper/tables/exp_b_scorer_evolution_primary7.csv`
- `paper/tables/exp_b_l2bplus_by_model_method_primary7.csv`
- `paper/tables/exp_b_tolerance_sweep_primary7.csv`
- `audit/exp_b_robustness/l2b_conditional_primary7.json`
- `audit/exp_b_robustness/l2b_conditional_llama_robustness.json`
- `audit/exp_b_robustness/scorer_evolution_primary7.json`
- `audit/exp_b_robustness/l2bplus_by_model_method_primary7.json`
- `audit/exp_b_robustness/tolerance_sweep_primary7.json`
