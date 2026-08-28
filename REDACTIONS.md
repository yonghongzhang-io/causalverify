# Redactions in this repository

This repository is the public home of the CausalVerify project. It deliberately
does **not** publish the quantities the benchmark scores against.

Every per-item result table below is a redacted copy. The `*_public.csv` file
keeps the identifier, the model, and the outcome of scoring; it drops the target
itself and any column from which the target can be reconstructed.

Two reconstruction paths drove most of these decisions:

1. A model's raw prediction plus its agreement flag recovers the target
   (`Kimi-128k_direction` + `Kimi-128k_L4_direction_agree` gives the true direction).
2. A model's numeric estimate plus its relative error recovers the target
   (`estimated` + `rel_error` gives `true_effect`).

So predictions are dropped and agreement/error columns are kept, not the reverse.

## `experiments/exp_a/auto_scores_public.csv`

Source: `experiments/exp_a/auto_scores.csv` — 259 rows, 33 columns kept.

Dropped: `method`, `orig_method`, `gt_m_level`, `gt_d_level`, `Kimi-128k_detected`, `Kimi-128k_direction`, `Claude-Sonnet_detected`, `Claude-Sonnet_direction`, `GPT-4o_detected`, `GPT-4o_direction`, `o3_detected`, `o3_direction`, `Claude-Opus_detected`, `Claude-Opus_direction`, `Gemini-2.5_detected`, `Gemini-2.5_direction`, `GPT-5_detected`, `GPT-5_direction`

Reason: per-paper method/direction targets; model predictions removed because prediction + *_agree flag reconstructs the target

## `experiments/exp_a/multi_scorer_l4_public.csv`

Source: `experiments/exp_a/multi_scorer_l4.csv` — 822 rows, 7 columns kept.

Dropped: `method`, `gt_direction`, `S1_latter_half_pred`, `S2_section6_pred`, `S3_llm_judge_pred`, `S4_structured_pred`

Reason: same reconstruction path via *_pred + *_match

## `experiments/exp_a/benchmark_300_validated_public.csv`

Source: `experiments/exp_a/benchmark_300_validated.csv` — 89 rows, 9 columns kept.

Dropped: `method`, `direction`

Reason: benchmark definition retains the paper list; scored targets removed

## `experiments/exp_a/benchmark_300_rejected_public.csv`

Source: `experiments/exp_a/benchmark_300_rejected.csv` — 27 rows, 7 columns kept.

Dropped: `method`, `direction`

Reason: benchmark definition retains the paper list; scored targets removed

## `experiments/exp_b/l2b_plus_scores_canonical_judge_v2_public.csv`

Source: `experiments/exp_b/l2b_plus_scores_canonical_judge_v2.csv` — 800 rows, 20 columns kept.

Dropped: `dgp_effect`, `dgp_direction`, `true_effect`, `true_direction`, `baseline_effect`, `baseline_direction`, `estimated`, `regex_estimated`, `judge_effect`, `judge_rationale`

Reason: hidden numerical targets; estimated/regex_estimated/judge_effect removed because value + rel_error reconstructs the target; judge_rationale states the effect in prose

## `experiments/exp_b/calibration_scores_public.csv`

Source: `experiments/exp_b/calibration_scores.csv` — 646 rows, 10 columns kept.

Dropped: `true_effect`, `estimated`

Reason: same reconstruction path

## `data/benchmark_80_new_papers_public.csv`

Source: `data/benchmark_80_new_papers.csv` — 80 rows, 6 columns kept.

Dropped: `method`, `direction`

Reason: benchmark definition retains the paper list; scored targets removed

## Not copied at all

| path | reason |
|---|---|
| `audit/human_gold/sample_manifest_SEALED.csv` | per-paper `direction` ground truth |
| `audit/human_gold/paper_native_labels.csv` | per-paper human `method` / `direction` labels |
| `audit/human_gold/human_vs_llm_consensus.csv` | same labels joined to model consensus |
| `audit/l2b_judge_human_validation/annotation_form.csv` | `human_effect` and `r_stdout_excerpt` carry the coefficient an executed run reported; for scenarios a model got right this approximates the canonical target. `summary.md`, `summary.json`, and `sample_distribution.json` report the validation result without it. |
| `experiments/exp_b/scenarios/*` `ground_truth`, `dgp_truth`, `design_note`, `verified_empirical_car`, `_fix_notes` fields | scenario targets and generator parameters |
| `experiments/exp_b/data/`, `experiments/exp_b/data_obfuscated/` | realised DGP data |
| `experiments/exp_a/ground_truth_extractions/` | per-paper extracted ground truth |
| `experiments/exp_a/pdfs/`, `audit/pdfs/` | third-party source papers, not ours to redistribute |
| `experiments/exp_a/outputs/`, `experiments/exp_a/outputs_v1_legacy/`, `experiments/exp_b/outputs/`, `experiments/exp_a/llm_ratings/` | raw model outputs; released separately |
| all `*_cache/` directories | reconstructible caches |

## Historical note

An earlier anonymous release of this project published several of these files in
full. That release is retained unchanged as a frozen submission archive. Not
copying those files forward does not retract what was already published; it keeps
this repository — the project's long-term home — free of scoring targets, and it
keeps the same discipline available for benchmark material that has never been
released.
