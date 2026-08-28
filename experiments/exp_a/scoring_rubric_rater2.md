# CAUSAL-BENCH Scoring Rubric — Rater 2 Instructions

## Overview

You will score **40 LLM outputs** (10 papers × 4 models) for Experiment A of the CAUSAL-BENCH project. Each output is a model's proposed identification strategy and R code for a published finance/economics paper. You score two dimensions:

**Estimated time: 5-6 hours (8 min per output)**

## Scoring Dimensions

### Dimension 1: Strategy Match (L3) — Score 0-3

Compare the model's proposed identification strategy to the paper's published strategy.

| Score | Meaning | Example |
|-------|---------|---------|
| **3** | Strong match: model names the correct method family and key features | GT=Event Study, Model says "Event study with [-2,+2] CAR window" |
| **2** | Mostly right: correct broad family but misses key features, OR hybrid framing that includes the correct method | GT=Event Study, Model says "Event study combined with DID" |
| **1** | Partially related: wrong method but shares some conceptual overlap | GT=Event Study, Model says "DID using announcement date as treatment timing" |
| **0** | Wrong: completely different method family | GT=Event Study, Model says "Instrumental variables using rainfall" |

**L3 pass** = score ≥ 2

### Dimension 2: Direction Match (L4) — Score 0 / 0.5 / 1

Compare the model's predicted effect direction to the paper's published conclusion.

| Score | Meaning | Example |
|-------|---------|---------|
| **1** | Correct direction, clearly stated | GT=negative, Model says "we expect a negative effect" |
| **0.5** | Correct direction but hedged/ambiguous | GT=positive, Model says "the effect could be positive or negative but likely positive" |
| **0** | Wrong direction or not stated | GT=negative, Model says "we expect a positive effect" |

### Dimension 3: Failure Type — IH / ME / NF / none

If L3 < 2, classify the failure:
- **IH** (Identification Hallucination): model proposes the wrong causal strategy
- **ME** (Mechanical Execution): model names the right strategy but implements it wrong in code
- **NF** (Narrative Fabrication): model predicts the wrong direction of the effect
- **none**: if L3 ≥ 2 and L4 = 1

## Ground Truth Reference

For each paper, you will receive:
1. The paper's **title, authors, and journal**
2. The **ground truth identification strategy** (e.g., "Event study with [-2,+2] window around M&A announcements")
3. The **ground truth conclusion direction** (positive or negative)
4. The **model's full output** (truncated to first 2000 characters)

## Calibration Examples (5 examples to align scoring)

### Example 1: Paper 01 — Ivashina & Scharfstein (2010)
- **GT Strategy:** DID — crisis (2008) as treatment, comparing syndicated vs. non-syndicated lending
- **GT Direction:** negative (lending declined during crisis)
- **Model says:** "Difference-in-differences... comparing lending volumes before and after the Lehman collapse"
- **Score:** Strategy = 3, Direction = 1, Failure = none

### Example 2: Paper 06 — Ahern & Harford (2014)
- **GT Strategy:** Event study + network propagation (industry merger waves through supply chain links)
- **GT Direction:** positive (supply chain links increase M&A probability)
- **Model says:** "Difference-in-differences: compare industries with and without merger waves"
- **Score:** Strategy = 0 (calls it DID, misses the event study component entirely), Direction = 1, Failure = IH

### Example 3: Paper 05 — Karpoff, Lee & Martin (2008)
- **GT Strategy:** Event study of stock price reactions to SEC enforcement actions
- **GT Direction:** negative (enforcement leads to negative abnormal returns)
- **Model says:** "Event study combined with DID framework to measure abnormal returns around SEC enforcement"
- **Score:** Strategy = 2 (hybrid framing but includes event study), Direction = 1, Failure = none

### Example 4: Paper 08 — Becker & Ivashina (2014)
- **GT Strategy:** IV — using bank demand for Treasury securities as instrument for credit supply
- **GT Direction:** negative (credit supply contraction → reduced lending)
- **Model says:** "DID comparing banks with high vs. low Treasury exposure before and after crisis"
- **Score:** Strategy = 0 (DID, not IV), Direction = 0 (says positive effect), Failure = IH, NF

### Example 5: Paper 07 — Greenstone, Mas & Nguyen (2020)
- **GT Strategy:** IV — using bank-level lending shocks as instruments for local credit supply
- **GT Direction:** positive (credit supply → positive effect on employment/output)
- **Model says:** "IV using bank failures as instrument for credit supply changes in local economies"
- **Score:** Strategy = 3 (correct IV with appropriate instrument), Direction = 0 (says negative), Failure = NF

## Scoring Procedure

For each of the 40 outputs:
1. Read the ground truth (provided)
2. Read the model output (first 2000 characters)
3. Score Strategy (0-3)
4. Score Direction (0 / 0.5 / 1)
5. Classify failure type (IH / ME / NF / none)
6. Add optional notes if the scoring is borderline

## Output Format

Please fill in this table for each output:

```
paper_id | model | strategy_score | direction_score | failure_types | notes
paper_01 | kimi  | 3              | 1               | none          |
paper_01 | claude| 3              | 1               | none          |
...
```

Or use the JSON format:
```json
{
  "paper_id": "paper_01",
  "model": "moonshot-v1-128k",
  "rater_id": "rater_2",
  "strategy_score": 3,
  "direction_score": 1,
  "failure_types": [],
  "notes": ""
}
```

## Important Notes

- Score **independently** — do not look at Rater 1's scores
- If you're unsure between two scores, choose the **lower** one (conservative)
- The ground truth is the **published paper's** strategy, not what you personally think is best
- Some models use hybrid framings (e.g., "event study + DID") — score based on whether the correct method is included, not whether extra methods are mentioned
