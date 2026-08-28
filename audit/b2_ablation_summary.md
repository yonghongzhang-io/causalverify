# B2 Truncation Ablation Summary

- Sample: 20 papers x 2 versions x 2 models = 80 valid V2+V2' pairs
- Models: claude-opus-4-7 (Claude Opus 4.7), gpt-5 (GPT-5)
- Prompt: identical to src/pipeline/run_exp_a.py (full Exp A SYSTEM+USER)
- Cost spent: **$15.22**

## Per-model flip rates

| Model | N | method_flips | direction_flips | either_flips | method_flip_rate |
|---|---|---|---|---|---|
| claude-opus-4-7 | 20 | 7 | 3 | 9 | 35% |
| gpt-5 | 20 | 6 | 5 | 11 | 30% |

## Aggregate (all models pooled)

- method_flip_rate: **32%** (13/40)
- direction_flip_rate: 20% (8/40)
- either_flip_rate: 50% (20/40)

## Decision rule (pre-registered)

- **method_flip_rate < 10%**  -> KEEP V2
- **method_flip_rate > 25%**  -> GO V2' (full restructure)
- **10-25%**                  -> AMBIGUOUS, manual review

### Verdict

**GO V2'. Method predictions flip on > 25% of papers when input source expands. V2 is too thin; proceed with full restructure (Step 2, ~$220-290).**

## Flip detail (only rows where V2 != V2')

| paper_id | model | V2 method | V2' method | V2 dir | V2' dir |
|---|---|---|---|---|---|
| paper_120 | gpt-5 | EVENT_STUDY | DID | negative | negative |
| paper_126 | claude-opus-4-7 | RDD | RDD | None | negative |
| paper_126 | gpt-5 | DID | DID | negative | positive |
| paper_129 | claude-opus-4-7 | DID | EVENT_STUDY | positive | negative |
| paper_138 | gpt-5 | DID | DID | positive | negative |
| paper_154 | gpt-5 | IV | EVENT_STUDY | positive | positive |
| paper_170 | gpt-5 | DID | IV | negative | negative |
| paper_194 | claude-opus-4-7 | IV | None | negative | negative |
| paper_194 | gpt-5 | IV | IV | negative | positive |
| paper_233 | gpt-5 | EVENT_STUDY | RDD | negative | negative |
| paper_30 | claude-opus-4-7 | DID | EVENT_STUDY | positive | positive |
| paper_30 | gpt-5 | DID | EVENT_STUDY | positive | positive |
| paper_36 | claude-opus-4-7 | RDD | RDD | positive | negative |
| paper_36 | gpt-5 | RDD | RDD | negative | positive |
| paper_64 | claude-opus-4-7 | DID | EVENT_STUDY | positive | positive |
| paper_64 | gpt-5 | EVENT_STUDY | DID | negative | negative |
| paper_66 | claude-opus-4-7 | None | IV | negative | negative |
| paper_78 | claude-opus-4-7 | EVENT_STUDY | DID | positive | positive |
| paper_98 | claude-opus-4-7 | EVENT_STUDY | DID | negative | negative |
| paper_98 | gpt-5 | DID | DID | negative | positive |

## Files
- Per-call CSV: `audit/b2_ablation_predictions.csv`
- Raw outputs: `audit/b2_ablation_outputs/*.json`