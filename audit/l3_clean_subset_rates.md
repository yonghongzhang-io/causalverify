# L3 Rate on Clean Subset (Leaks Excluded)

Recomputed Exp B L3 (method identification) rates after excluding the 21 scenarios with critical method-name leakage.

## Per-model comparison: all 100 vs clean 79

| Model | L3 (all 100) | L3 (clean 79) | Δ |
|---|:---:|:---:|:---:|
| Opus | 99.0% (99/100) | 98.7% (78/79) | -0.3% |
| Sonnet | 99.0% (99/100) | 98.7% (78/79) | -0.3% |
| GPT-4o | 100.0% (100/100) | 100.0% (79/79) | +0.0% |
| o3 | 99.0% (99/100) | 98.7% (78/79) | -0.3% |
| Kimi | 99.0% (99/100) | 98.7% (78/79) | -0.3% |
| Gemini | 100.0% (100/100) | 100.0% (79/79) | +0.0% |

## Per-method L3 on clean 79-scenario subset

| Model | DID | EVENT_STUDY | IV | RDD |
|---|:---:|:---:|:---:|:---:|
| **Opus** | 97% (29/30) | 100% (16/16) | 100% (11/11) | 100% (22/22) |
| **Sonnet** | 97% (29/30) | 100% (16/16) | 100% (11/11) | 100% (22/22) |
| **GPT-4o** | 100% (30/30) | 100% (16/16) | 100% (11/11) | 100% (22/22) |
| **o3** | 97% (29/30) | 100% (16/16) | 100% (11/11) | 100% (22/22) |
| **Kimi** | 100% (30/30) | 94% (15/16) | 100% (11/11) | 100% (22/22) |
| **Gemini** | 100% (30/30) | 100% (16/16) | 100% (11/11) | 100% (22/22) |

## Interpretation

L3 rates are largely unchanged by excluding leaking scenarios. This suggests the leakage was not a dominant driver of L3 performance, though the clean subset remains the more defensible comparison.