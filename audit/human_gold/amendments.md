# Protocol Amendments and Deviations Log

This file records all deviations from `labeling_protocol.md` v1.0 —
pre-labeling (sampling-stage) or in-flight. Required reading before any
downstream analysis: anyone interpreting `paper_native_labels.csv` must
understand what was changed and why.

**Entry types**:

- **Pre-labeling deviation**: documented once before labeling begins; no
  version bump if the protocol itself permits the fallback (e.g., §2.3
  rule 4).
- **Minor clarification** (v1.0 → v1.1, v1.1 → v1.2, ...): rubric example
  added, typo fixed, edge case clarified. Does **not** require re-label.
- **Rubric change** (v1.0 → v2.0, ...): changes the label a prior paper
  would have received. **Requires re-labeling** all affected papers per
  §10.

**Current protocol version**: v1.0

---

## A-001 — Cell shortfalls in sampling (pre-labeling)

**Date**: 2026-04-23
**Type**: Pre-labeling deviation (protocol §2.3 rule 4 explicitly permits)
**Version**: v1.0 (no bump)
**Source**: `sample_selection.log`, seed = 20260423
**Affects**: 5 of 10 method × difficulty cells; final n = 80 preserved.

### Shortfall detail

| Cell                  | Eligible in corpus | Target | Drew | Cause            |
|-----------------------|--------------------|--------|------|------------------|
| EVENT_STUDY × hard    | 2                  | 8      | 2    | corpus scarcity  |
| RDD × hard            | 3                  | 8      | 3    | corpus scarcity  |
| OTHER × hard          | 3                  | 8      | 3    | corpus scarcity  |
| OTHER × easy          | 5                  | 8      | 5    | corpus scarcity  |
| IV × hard             | 7                  | 8      | 7    | corpus scarcity  |

Total shortfall: **20 papers** below the 80-paper full-factorial target.

### Backfill

20 papers drawn from nearest-population cells (those with the largest
eligible pools) to restore n = 80. The exact list is recoverable from
`sample_manifest_SEALED.csv` by filtering to cells with count > 8:

- DID × easy  : +7  (15 in final sample vs target 8)
- DID × hard  : +4  (12 vs 8)
- EVENT_STUDY × easy : +3  (11 vs 8)
- IV × easy   : +3  (11 vs 8)
- RDD × easy  : +3  (11 vs 8)

### Resulting per-cell counts (verified against sample_manifest_SEALED.csv)

|              | easy | hard |
|--------------|------|------|
| DID          | 15   | 12   |
| EVENT_STUDY  | 11   |  2   |
| IV           | 11   |  7   |
| RDD          | 11   |  3   |
| OTHER        |  5   |  3   |

### Implications for downstream use

- `audit_labels.py` will flag EVENT_STUDY × hard, RDD × hard,
  OTHER × easy, and OTHER × hard as below its 75%-of-8 threshold. These
  warnings are **expected and not an audit failure**.
- Per-cell statistical power is low on EVENT_STUDY × hard (n=2),
  RDD × hard (n=3), and OTHER × hard (n=3). Any κ or accuracy claim
  restricted to these cells must report n and be flagged as exploratory.
- A3 dual-track comparison (§9.2) should pool easy + hard within method
  family where sample sizes thin out; avoid per-cell point estimates for
  n < 5.

### Disclosure requirement

Methods section must state: *"Five of ten method × difficulty cells fell
short of the n = 8 target due to corpus-level scarcity of EVENT_STUDY × hard,
RDD × hard, and OTHER papers. Shortfalls were backfilled from
nearest-population cells to preserve n = 80. See `amendments.md` A-001."*

---

## A-002 — paper_159 excluded from Target30 in-flight labeling

**Date**: 2026-05-01
**Type**: In-flight deviation / sample exclusion
**Version**: v1.0 (no rubric change)
**Triggered by**: `paper_159`
**Affects**: Target30 human-gold validation slice

### What changed

`paper_159` was removed from the active Target30 labeling queue and marked
`excluded_pdf_appendix_only_unblinded` in
`target30_manifest_blinded.csv`. No row was added to
`paper_native_labels.csv`.

### Reason

During labeling, the annotator reported that the available PDF appears to be
the appendix rather than the full article, so the paper-native method/result
evidence needed for human adjudication was not available. The labeling helper
session was aborted before any label was saved. In the subsequent file search,
the sealed manifest line for `paper_159` was accidentally surfaced, so the
paper is no longer blind for the current annotator even if a correct PDF is
later obtained.

### Re-labeling requirement

- [x] Do not label `paper_159` in the current Target30 pass.
- [ ] Select a replacement from the unsealed A1 sample metadata only
      (`sample_manifest.csv`), without opening `sample_manifest_SEALED.csv`
      or any GT files.

### Verification

`paper_159` should remain absent from `paper_native_labels.csv`. The Target30
manifest should show it as `excluded_pdf_appendix_only_unblinded`, and a
replacement should be documented before claiming 30 completed human labels.

---

## A-XXX — [Template — copy and fill for future entries]

**Date**: YYYY-MM-DD
**Type**: [Pre-labeling deviation | Minor clarification | Rubric change]
**Version**: [no bump | v1.0 → v1.1 | v1.0 → v2.0]
**Triggered by**: [paper_XX / audit run / Gate 1 / co-author discussion]
**Affects**: [which papers / which cells / which rubric sections]

### What changed

Describe the old rule or practice, then the new one. Be concrete enough
that a reader with no memory of this conversation can apply the new rule.

### Reason

Why was the change necessary? Cite specific papers, Gate-1 disagreements,
or empirical patterns seen in the data.

### Re-labeling requirement

- [ ] None — clarification only.
- [ ] Re-label specific papers: paper_XX, paper_YY, ...
- [ ] Re-label and re-run Gate 1 κ.

### Verification

How and when will you confirm the amendment has been applied? (E.g.,
"paper_XX re-labeled 2026-05-12, row 87 in paper_native_labels.csv;
Gate 1 κ re-run 2026-05-15, see session_log.")

---
