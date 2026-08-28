# L2b Judge Human-Validation Audit

This directory contains a completed blinded human-validation audit for the
coefficient-extraction judge used in Exp B L2b+ scoring.

## Purpose

The purpose is to validate coefficient extraction, not causal correctness.
The human annotator sees executed R code/stdout and identifies the scalar
treatment-effect coefficient reported by that code. The target is the
coefficient the code reports, not whether the code used the right method.

## Blinding Protocol

- The annotator form omits model identity, L2b+ labels, canonical estimates,
  judge effects, regex effects, and primary-ranking information.
- The hidden metadata key (`annotation_key_private.csv`) is **intentionally
  withheld from the public release** because it contains
  unblinding information (model identity, canonical estimates, judge
  effects, and L2b+ labels). The completed reviewer-facing audit summary
  is available in `summary.md` and `summary.json`.

## Files

- `annotation_form.csv`: blinded form (released).
- `summary.md` / `summary.json`: completed audit summary (released).
- `sample_distribution.json`: realised sample distribution and replay status (released).
- `annotation_key_private.csv`: hidden unblinding metadata. **Withheld from
  the public release.** Reviewers should consult `summary.md` /
  `summary.json` for the audit results.

## Annotation Columns

- `human_effect`: scalar coefficient value reported in stdout.
- `effect_present`: `1` if a treatment-effect coefficient is present, else `0`.
- `ambiguity_flag`: `1` if multiple plausible target coefficients exist.
- `target_term`: variable/term name used for the coefficient.
- `human_rationale`: short explanation for the extraction decision.

## Status

The audit is complete for the 50 sampled primary-panel L2b=1 cells. The
completed summary reports:

- N annotated: 50
- Numeric agreement: 40/44 = 90.9% among comparable audited cells
- Induced L2b+ pass/fail agreement: 39/44 = 88.6% among comparable audited cells
- Ambiguity rate: 15/50 = 30.0%

This is a validation audit of coefficient extraction, not a change to frozen
headline L2b+ rates.

## Reproduce

The completed audit numbers are pre-recorded in `summary.md` and
`summary.json`. The `summarize` script gracefully reports this when the
private unblinding key is absent (the public-release case):

```bash
python3 scripts/summarize_l2b_judge_human_validation.py
```

To re-run the full audit pipeline with a private unblinding key (not
included in this release), use the prepare script first:

```bash
python3 scripts/prepare_l2b_judge_human_validation.py --n 50 --seed 20260502
python3 scripts/summarize_l2b_judge_human_validation.py
```

## Realised Sample Distribution

- Requested N: 50
- Seed: 20260502
- Sampled rows: 50
- Replay OK rows: 50
- By method: `{'DID': 13, 'EVENT_STUDY': 12, 'IV': 11, 'RDD': 14}`
- By hidden model: `{'GPT-4o': 9, 'Opus': 6, 'GPT-5': 10, 'Gemini': 5, 'Kimi': 7, 'Sonnet': 6, 'o3': 7}`
- By L2b+ v2 label in hidden key: `{'1': 35, '0': 15}`
- Scorer-disagreement rows: 35
