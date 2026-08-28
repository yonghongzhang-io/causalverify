# Obfuscation Summary

Obfuscated 100 Exp B scenarios using static scheme.

## Status

- obfuscated: 100

## Obfuscation Schemes


### DID

| Original | Obfuscated |
|---|---|
| `unit_id` | `entity_id` |
| `period` | `wave` |
| `treated` | `group_indicator` |
| `post` | `phase_indicator` |
| `treat_x_post` | `group_phase_interaction` |
| `y` | `outcome` |

### EVENT_STUDY

| Original | Obfuscated |
|---|---|
| `stock_id` | `series_id` |
| `event_day` | `time_offset` |
| `ret` | `observation` |
| `mkt_ret` | `reference_series` |
| `beta` | `sensitivity_coefficient` |

### IV

| Original | Obfuscated |
|---|---|
| `y` | `outcome` |
| `x` | `focal_variable` |
| `z` | `auxiliary_variable` |
| `controls` | `covariate_a` |

### RDD

| Original | Obfuscated |
|---|---|
| `running_var` | `assignment_score` |
| `treated` | `status_flag` |
| `y` | `outcome` |
| `near_cutoff` | `proximity_flag` |

## Usage

To use the obfuscated data for a new LLM evaluation round:

1. In `run_exp_b.py`, replace `data_file` with the obfuscated version:
   ```python
   data_file = str(data_path).replace(
       'experiments/exp_b/data/',
       'experiments/exp_b/data_obfuscated/')
   ```
2. In `score_l2b_plus.py`, when extracting coefficients, apply the reverse
   mapping from `obfuscation_map.json` so that LLM-generated references to
   obfuscated names are understood correctly.

3. Compare L3 results on obfuscated vs. original data to quantify how much
   the method-revealing variable names inflated L3 pass rates.

## Interpretation

✅ **100/100 scenarios successfully obfuscated.**

**Recommended robustness test for v11 paper**: run Exp B on a subset (say 30 scenarios) using the obfuscated CSVs. Report L3 and L2b+ rates on both original and obfuscated data. Large differences indicate that method-revealing names were inflating L3 results.