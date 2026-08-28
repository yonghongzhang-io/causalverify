# V2 vs V2' Diagnostic Summary

- Sample: **20 papers** (5 per family x 4 families, seed 20260424)
- V2  baseline: `audit/regen_from_pdf.json` (8-page, 20K chars)
- V2' pilot:    `audit/regen_from_pdf_v2prime_pilot.json` (20-page, 60K chars)
- V2' run cost: **$7.47**

## Signal distribution

| Signal | N | % |
|---|---|---|
| YES       | 0 | 0% |
| AMBIGUOUS | 16 | 80% |
| NO        | 4  | 20% |

## By method family

| Family | YES | AMBIG | NO |
|---|---|---|---|
| DID | 0 | 4 | 1 |
| EVENT_STUDY | 0 | 4 | 1 |
| IV | 0 | 4 | 1 |
| RDD | 0 | 4 | 1 |

## Average per-field deltas

| Field | avg char_delta | avg jaccard |
|---|---|---|
| research_question | +9 | 0.38 |
| data_description | +60 | 0.29 |
| institutional_context | +19 | 0.27 |

## Decision rule (pre-registered)

- **>= 30% YES** -> greenlight full V2' restructure ($220-290)
- **< 15% YES**  -> keep V2, do Option A (strip V1 only)
- **15-30% YES** -> manual review before committing

**Observed: 0% YES**

### Verdict

**KEEP V2. V2' does not surface new methodological evidence in enough papers; the 20-page expansion is not worth $220–290. Proceed with Option A (strip V1).**

## Files
- Per-row details: `audit/v2_vs_v2prime_pilot.csv`
- Side-by-side text: `audit/v2_vs_v2prime_pilot_pairs.md`