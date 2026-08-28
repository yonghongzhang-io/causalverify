# Exp B scenario consistency audit

Input scenarios: `experiments/exp_b/scenarios`
Canonical baseline source: `audit/dgp_verification.json`

## Summary

- Scenarios audited: 100
- Hard-pass scenarios: 100/100 (100.0%)
- This audit checks benchmark consistency, not external economic realism.
- `FLAGGED` canonical verifier cases are warnings, not hard failures, because v11 scores against canonical beta-hat on the realized data rather than ideal beta-star.

## By method

| Method | hard pass | total |
|---|---:|---:|
| DID | 30 | 30 |
| EVENT_STUDY | 24 | 24 |
| IV | 24 | 24 |
| RDD | 22 | 22 |

## By origin

| Origin | hard pass | total |
|---|---:|---:|
| human_written | 30 | 30 |
| llm_templated | 70 | 70 |

## Hard issues

- None

## Warnings

- canonical_beta_hat_differs_from_beta_star_gt_10pct: 58
- text_may_not_name_outcome_column: 14
- canonical_sign_differs_from_dgp: 2

### Canonical sign differs from beta-star

These are retained for execution scoring because L2b+ compares student estimates to the canonical estimate on the realized data, not to the ideal DGP parameter. They should be described as finite-sample/prior-data conflict cases if discussed in text.

| Scenario | Method | beta-star | beta-hat canonical | verifier status |
|---|---|---:|---:|---|
| s46 | DID | 0.08 (positive) | -0.178946 | FLAGGED |
| s82 | IV | -0.25 (negative) | 0.003635 | FLAGGED |

## Interpretation for paper

Exp B scenarios are treated as reliable for execution-grounded scoring when they have valid schema, readable CSV data, aligned DGP labels, and available canonical baselines. Natural-language descriptions are not treated as self-validating ground truth; they are prompt surfaces for models whose numerical outputs are judged against canonical estimators.
