# GT Aggregation Summary (Stage 3)

**Input**: gt_reextract_multi.json (259 papers × 4 LLM votes)
**Output**: gt_aggregate_decisions.json, gt_adjudication_form.csv

## Consensus distribution — Method family

| Level | Count | % |
|---|---:|---:|
| all4_agree | 51 | 20% |
| 3of4_agree | 92 | 36% |
| 2of4_plurality | 84 | 32% |
| 2of4_tie | 12 | 5% |
| split | 20 | 8% |
| error_too_few_votes | 0 | 0% |

## Consensus distribution — Direction

| Level | Count | % |
|---|---:|---:|
| all4_agree | 0 | 0% |
| 3of4_agree | 20 | 8% |
| 2of4_plurality | 160 | 62% |
| 2of4_tie | 0 | 0% |
| split | 79 | 31% |
| error_too_few_votes | 0 | 0% |

## Label-change impact

- **Method changed from original GPT-4o GT**: 95 / 259 (37%)
- **Direction changed from original GPT-4o GT**: 180 / 259 (69%)

## What needs human adjudication

- **97 papers** have `2of4_tie` or `split` on method or direction.
- Open `gt_adjudication_form.csv` and fill in `your_method`, `your_direction`, and `supporting_evidence` for each row.
- Sort is: 4-way splits first (hardest), then method ties, then direction ties.
