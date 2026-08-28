# Human-gold 30-paper plan

Date: 2026-05-01

Purpose: create the minimum paper-native human-gold validation subset needed
to defend Exp A ground-truth quality in the CausalVerify submission.

## Goal

Produce **30 first-pass human labels** for the submission-facing validation
slice. This goal is complete as of 2026-05-01.

This does **not** replace the full 80-paper A1 target in
`labeling_protocol.md`. It is the minimum submission-facing validation slice:

- enough to report a concrete human-vs-4-LLM consensus sanity check,
- large enough to cover hard disagreement cases,
- small enough to finish before paper revisions.

## Final state

Status: **completed** on 2026-05-01.

- First-pass human labels: 30 papers.
- Target30 completion: 30/30.
- Replacement: `paper_159` was excluded because the available PDF was
  appendix-only; `paper_17` was added from the unsealed manifest as a blinded
  replacement.
- Human vs 4-LLM consensus:
  - Method-family simple agreement: 18/30 = 60.0%.
  - Method-family Cohen kappa: 0.606.
  - Direction simple agreement: 10/21 = 47.6%.
  - Direction Cohen kappa: 0.294.
- Source files:
  - `audit/human_gold/paper_native_labels.csv`
  - `audit/human_gold/human_vs_llm_consensus.md`
  - `audit/human_gold/human_vs_llm_consensus.csv`

Interpretation: this is a submission-facing validation audit, not a complete
human-gold replacement for the 259-paper Exp A corpus. The low-to-moderate
agreement with 4-LLM consensus supports the paper's claim that real-paper
method/direction labels are ambiguous and that Exp A should be treated as
text-level agreement diagnostics rather than the primary correctness endpoint.

## Initial state

- Existing first-pass human labels: 10 papers
  (`paper_05`, `paper_08`, `paper_10`, `paper_64`, `paper_66`,
  `paper_68`, `paper_78`, `paper_90`, `paper_113`, `paper_114`).
- Remaining first-pass labels needed for the 30-paper validation slice: 20.
- Full protocol target remains 80 papers.

Human adjudication is conducted after the automated benchmark freeze as a
validation audit, not as a training, prompting, or tuning input. Human labels
are therefore not used to construct model prompts, select model outputs, or
tune scoring thresholds.

## Blinded target file

Use:

```text
audit/human_gold/target30_manifest_blinded.csv
```

That file contains only:

- target order,
- paper ID,
- difficulty tier,
- PDF path,
- current label status.

It intentionally does **not** expose Phase-2 method labels, direction labels,
LLM votes, or 4-LLM consensus labels.

The 30-paper target was selected from the existing sealed A1 sample so that
the hidden method-family coverage is balanced, but the annotator should not
open `sample_manifest_SEALED.csv` during labeling.

## Non-negotiable blinding rules

During human labeling, do **not** open:

- `audit/human_gold/sample_manifest_SEALED.csv`
- `audit/gt_aggregate_decisions.json`
- `audit/gt_reextract_multi.json`
- `experiments/exp_a/papers/paper_*.json`
- existing model outputs for the target paper
- any LLM chat about the target paper

Allowed files:

- original PDF,
- `SIGNATURE_CHEATSHEET.md`,
- `labeling_protocol.md`,
- `rubric/*.md`,
- `target30_manifest_blinded.csv`,
- `paper_native_labels.csv`.

## Recommended daily pace

Do not rush this. Bad human-gold is worse than no human-gold.

- Normal day: 3 papers.
- Maximum day: 5 papers.
- Stop if fatigue is 4/5 or 5/5.
- Keep supporting sentences short, direct, and verbatim from the PDF.

At 27 remaining papers, this is roughly:

- 9 days at 3 papers/day, or
- 6 days at 4-5 papers/day.

## How to label

From repo root:

```bash
cd audit/human_gold
python3 label_helper.py --paper paper_64 --once
```

Then continue through `target30_manifest_blinded.csv` in order, replacing
`paper_64` with the next pending paper.

For an interactive session that automatically advances through the original
80-paper manifest:

```bash
cd audit/human_gold
python3 label_helper.py
```

However, for the 30-paper submission slice, the safer workflow is one paper
at a time with `--paper ... --once`, following the target30 file.

## After every session

Run:

```bash
cd audit/human_gold
python3 audit_labels.py \
  --labels paper_native_labels.csv \
  --sealed-manifest sample_manifest_SEALED.csv \
  --out-dir .
```

This uses the sealed manifest only for audit reporting after labels are
saved. Do not inspect the sealed manifest manually while labeling.

## Reliability check

After the first 20 first-pass rows are complete, draw a blind relabel subset:

```bash
cd audit/human_gold
python3 compute_reliability.py \
  --sample \
  --labels paper_native_labels.csv \
  --n-initial 20 \
  --n-relabel 4 \
  --seed 20260501
```

Then wait at least 7 days before relabeling those papers from scratch.
After relabel rows are added:

```bash
cd audit/human_gold
python3 compute_reliability.py \
  --evaluate \
  --labels paper_native_labels.csv
```

Protocol gates:

- method-family intra-rater kappa >= 0.80
- direction intra-rater kappa >= 0.70

For the submission draft, report the 30-paper first-pass human-vs-4-LLM
agreement as a validation audit and state that intra-rater or second-annotator
reliability would be follow-up work rather than a completed claim.

## Submission-facing language

Use language like:

> We additionally constructed a paper-native human validation slice of 30
> papers sampled from the sealed A1 manifest. The annotator labeled method
> family and direction from the original PDFs under a blinded protocol, without
> access to Phase-2 LLM votes or consensus labels. We report agreement between
> this human-gold slice and the 4-LLM consensus labels as a validation check:
> 60.0% for method family and 47.6% for direction among scoreable cases. The
> audit is used to characterize Exp A label ambiguity, not to replace the
> frozen 4-LLM consensus labels.

Do **not** claim the entire Exp A corpus is human-gold labeled.
