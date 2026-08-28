# Ground-Truth Cross-Validation Summary

**Independent extractor**: claude-opus-4-6
**Papers checked**: 50 (errors: 0, usable: 50)

## Headline agreement

- Method family:       34/50 = **68.0%**
- Conclusion direction: 33/50 = **66.0%**

## Per-method method-family agreement

| Method (as original GT) | Agree | Total | Rate |
|---|---:|---:|---:|
| DID | 9 | 14 | 64% |
| EVENT_STUDY | 5 | 12 | 42% |
| IV | 10 | 12 | 83% |
| RDD | 10 | 12 | 83% |

## Interpretation

- **Method agreement ≥ 90%**: GT is robust. Any remaining disagreements are probably honest ambiguities (e.g., DID-with-event-study-plots).
- **Method agreement 80-90%**: GT has some noise. Consider human-adjudicating the disagreeing rows before final submission.
- **Method agreement < 80%**: GT is unreliable. Either re-extract with a better prompt, or escalate to human labeling for the full set.

## Disagreeing papers (for manual inspection)

| paper_id | orig method | indep method | orig dir | indep dir |
|---|---|---|---|---|
| paper_61 | DID | OTHER | negative | negative |
| paper_202 | IV | DID | negative | negative |
| paper_58 | DID | OTHER | positive | mixed |
| paper_55 | IV | IV | negative | positive |
| paper_56 | DID | OTHER | positive | positive |
| paper_208 | RDD | RDD | positive | mixed |
| paper_207 | EVENT_STUDY | OTHER | positive | mixed |
| paper_157 | EVENT_STUDY | OTHER | positive | positive |
| paper_43 | IV | IV | positive | mixed |
| paper_47 | IV | IV | negative | unclear |
| paper_248 | IV | DID | positive | positive |
| paper_44 | RDD | RDD | negative | positive |
| paper_60 | DID | DID | positive | mixed |
| paper_82 | IV | IV | negative | mixed |
| paper_101 | EVENT_STUDY | DID | negative | mixed |
| paper_198 | DID | DID | neutral | unclear |
| paper_122 | EVENT_STUDY | OTHER | negative | negative |
| paper_147 | RDD | OTHER | negative | negative |
| paper_90 | EVENT_STUDY | OTHER | negative | negative |
| paper_26 | DID | RDD | negative | negative |
| paper_240 | EVENT_STUDY | DID | negative | negative |
| paper_96 | RDD | RDD | negative | positive |
| paper_258 | RDD | RDD | positive | unclear |
| paper_150 | EVENT_STUDY | OTHER | positive | positive |
| paper_127 | RDD | DID | negative | negative |
| paper_217 | RDD | RDD | positive | unclear |
| paper_107 | RDD | RDD | negative | positive |
| paper_229 | DID | DID | positive | negative |
| paper_219 | DID | IV | positive | positive |
| paper_66 | IV | IV | positive | mixed |
