# Exp A Stage 8 score summary

**Source**: `experiments/exp_a/auto_scores.csv` (259 papers × 7 models)
**GT source**: `audit/gt_aggregate_decisions.json` (V2'' 4-LLM consensus)
**Scoreable subsets**: L3=187/259, L4=92/259

## Per-model L3 / L4 with 95% bootstrap CI (n=10,000)

| Model | L3 method | 95% CI | L4 direction | 95% CI |
|---|---:|:---:|---:|:---:|
| Kimi-128k | 82.4% | [76.5, 87.7] | 81.5% | [72.8, 89.1] |
| Claude-Sonnet | 80.7% | [74.9, 86.1] | 85.9% | [78.3, 92.4] |
| GPT-4o | 88.8% | [84.0, 93.0] | 81.5% | [72.8, 89.1] |
| o3 | 78.1% | [72.2, 84.0] | 76.1% | [67.4, 84.8] |
| Claude-Opus | 78.1% | [72.2, 84.0] | 83.7% | [76.1, 91.3] |
| Gemini-2.5 | 77.5% | [71.7, 83.4] | 79.3% | [70.7, 87.0] |
| GPT-5 | 67.4% | [60.4, 73.8] | 81.5% | [72.8, 89.1] |

## Per-method × per-model L3 (method-family agreement)

| Model | DID | EVENT_STUDY | IV | RDD |
|---|---:|---:|---:|---:|
| Kimi-128k | 97.0% (n=101) | 61.5% (n=13) | 56.2% (n=32) | 73.2% (n=41) |
| Claude-Sonnet | 78.2% (n=101) | 61.5% (n=13) | 87.5% (n=32) | 87.8% (n=41) |
| GPT-4o | 90.1% (n=101) | 84.6% (n=13) | 81.2% (n=32) | 92.7% (n=41) |
| o3 | 77.2% (n=101) | 53.8% (n=13) | 87.5% (n=32) | 80.5% (n=41) |
| Claude-Opus | 68.3% (n=101) | 76.9% (n=13) | 90.6% (n=32) | 92.7% (n=41) |
| Gemini-2.5 | 72.3% (n=101) | 46.2% (n=13) | 93.8% (n=32) | 87.8% (n=41) |
| GPT-5 | 58.4% (n=101) | 61.5% (n=13) | 87.5% (n=32) | 75.6% (n=41) |

## Per-method × per-model L4 (direction agreement)

The per-method L4 table is restricted to the four canonical method families (76/92 direction-scoreable papers). The remaining 16 direction-scoreable papers have `OTHER` or unresolved method labels and are included in the overall L4 rates above.

| Model | DID | EVENT_STUDY | IV | RDD |
|---|---:|---:|---:|---:|
| Kimi-128k | 79.5% (n=39) | 66.7% (n=6) | 88.9% (n=18) | 84.6% (n=13) |
| Claude-Sonnet | 76.9% (n=39) | 83.3% (n=6) | 100.0% (n=18) | 100.0% (n=13) |
| GPT-4o | 79.5% (n=39) | 66.7% (n=6) | 83.3% (n=18) | 84.6% (n=13) |
| o3 | 69.2% (n=39) | 66.7% (n=6) | 83.3% (n=18) | 84.6% (n=13) |
| Claude-Opus | 74.4% (n=39) | 50.0% (n=6) | 94.4% (n=18) | 100.0% (n=13) |
| Gemini-2.5 | 76.9% (n=39) | 83.3% (n=6) | 83.3% (n=18) | 100.0% (n=13) |
| GPT-5 | 76.9% (n=39) | 100.0% (n=6) | 83.3% (n=18) | 84.6% (n=13) |

## L3 ranking (highest → lowest)

1. **GPT-4o** — 88.8% L3 (95% CI [84.0, 93.0])
2. **Kimi-128k** — 82.4% L3 (95% CI [76.5, 87.7])
3. **Claude-Sonnet** — 80.7% L3 (95% CI [74.9, 86.1])
4. **o3** — 78.1% L3 (95% CI [72.2, 84.0])
5. **Claude-Opus** — 78.1% L3 (95% CI [72.2, 84.0])
6. **Gemini-2.5** — 77.5% L3 (95% CI [71.7, 83.4])
7. **GPT-5** — 67.4% L3 (95% CI [60.4, 73.8])

## L4 ranking (highest → lowest)

1. **Claude-Sonnet** — 85.9% L4 (95% CI [78.3, 92.4])
2. **Claude-Opus** — 83.7% L4 (95% CI [76.1, 91.3])
3. **Kimi-128k** — 81.5% L4 (95% CI [72.8, 89.1])
4. **GPT-4o** — 81.5% L4 (95% CI [72.8, 89.1])
5. **GPT-5** — 81.5% L4 (95% CI [72.8, 89.1])
6. **Gemini-2.5** — 79.3% L4 (95% CI [70.7, 87.0])
7. **o3** — 76.1% L4 (95% CI [67.4, 84.8])

## Notes for paper §5

- L3/L4 are **text-level agreement**, not detection. L3 is computed on the 187/259 papers where the 4-LLM consensus produced one of the four canonical method-family labels. L4 is computed on the 92/259 papers where the 4-LLM consensus produced a positive/negative direction label.
- Per-method L4 rows cover 76/92 L4-scoreable papers; the remaining 16 have `OTHER` or unresolved method labels but still have scoreable directions.
- Rankings differ between L3 and L4 (e.g., GPT-4o leads L3 at 88.8%, Claude-Sonnet leads L4 at 85.9%); this is the F4 fragility result.
- For execution-grounded correctness, see Exp B L2b+ (canonical-baseline judge_v2).
