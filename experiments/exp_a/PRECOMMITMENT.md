# Experiment A — Pre-commitment Protocol

## Purpose

This document implements the RID (Research Integrity by Design) pre-commitment
for Experiment A. By committing the paper selection, scoring criteria, and
analysis plan before any model outputs are generated, we prevent post-hoc
adjustment of the benchmark to favor particular results.

This also serves as a "dogfooding" demonstration: we apply the same RID
discipline to our own experimental design that we propose to impose on the
AI system under evaluation.

---

## Git Commit Message Template

Use this commit message when locking the Experiment A benchmark:

```
feat(exp_a): pre-commit benchmark paper selection and scoring protocol

RID PRE-COMMITMENT — Experiment A: Replication Test
====================================================

Locked before any model outputs are generated.

PAPER SELECTION (10 papers):
  DID:   paper_01 (easy), paper_02 (medium), paper_03 (hard)
  ES:    paper_04 (easy), paper_05 (medium), paper_06 (hard)
  IV:    paper_07 (medium), paper_08 (hard)
  RDD:   paper_09 (easy), paper_10 (medium)

SELECTION CRITERIA (pre-committed):
  1. Published in JF, JFE, RFS, or AEJ:EP (top-5 finance/econ journals)
  2. Uses one of four method families: DID, Event Study, IV, RDD
  3. Core identification strategy is clearly described and replicable
  4. At least partial data replicability with free/public sources
  5. No more than 3 papers per method family
  6. At least one paper at each difficulty level per method family where feasible

SCORING DIMENSIONS (pre-committed):
  Dimension 1: ID strategy match (0-3 scale)
    3 = exact method match
    2 = same method family, different variant
    1 = related causal logic, different method
    0 = unrelated or no valid identification

  Dimension 2: Conclusion direction (0-1 scale)
    1.0 = same sign and significance
    0.5 = same sign, different significance
    0.0 = wrong sign or no conclusion

  Dimension 3: Effect size proximity (0-1 scale, tier-adjusted)
    Full replication:   1.0 = within 2×; 0.5 = within 5×; 0.0 = >5×
    Partial replication: 1.0 = within 5×; 0.5 = within 10×; 0.0 = >10×
    Proxy replication:   1.0 = correct sign; 0.5 = correct OoM; 0.0 = wrong

REPLICATION TIERS (pre-committed):
  Full:    paper_04, paper_07
  Partial: paper_02, paper_03, paper_05, paper_09, paper_10
  Proxy:   paper_01, paper_06, paper_08

RATER PROTOCOL (pre-committed):
  - 2 independent PhD raters for ID strategy match (Dimension 1)
  - 5 calibration examples before scoring begins
  - Disagreements resolved by 3rd rater adjudication
  - Target: Cohen's κ > 0.7
  - Dimensions 2-3 scored automatically from model outputs

ANALYSIS PLAN (pre-committed):
  Primary output: 10×3 heatmap (papers × dimensions)
  Secondary output: Method-family average scores
  Tertiary output: Difficulty-level regression (score ~ difficulty + method)

EXCLUSION CRITERIA (pre-committed):
  - If model fails to produce any output for a paper: scored as (0, 0, 0)
  - If model produces output but code does not run: L2 fail, scored as (*, 0, 0)
  - No paper will be dropped post-hoc from the benchmark

This commit is the RID anchor for Experiment A.
Any changes after this point must be documented as protocol amendments
with justification, committed separately, and disclosed in the paper.

Hash of this pre-commitment will be recorded in the paper's appendix.
```

---

## How to Use

### Step 1: Finalize paper JSONs
Ensure all 10 `paper_XX.json` files in `experiments/exp_a/papers/` are complete
with ground truth coefficients, identification strategy descriptions, and
data availability assessments.

### Step 2: Commit with the template above
```bash
cd financial-scientist
git add experiments/exp_a/papers/*.json
git add experiments/exp_a/DATA_AVAILABILITY_ASSESSMENT.md
git add experiments/exp_a/PRECOMMITMENT.md
git commit -m "feat(exp_a): pre-commit benchmark paper selection and scoring protocol

<paste full commit message body here>
"
```

### Step 3: Record the commit hash
```bash
git log --oneline -1
# Output: abc1234 feat(exp_a): pre-commit benchmark paper selection and scoring protocol
```

Store this hash in `config.yaml` under `exp_a.precommitment_hash`.

### Step 4: Tag the commit
```bash
git tag -a exp_a_precommit -m "Experiment A pre-commitment anchor"
git push origin exp_a_precommit
```

---

## Protocol Amendments

If any change is needed after the pre-commitment (e.g., replacing a paper
due to discovered data issues), document it as follows:

```
fix(exp_a): protocol amendment — replace paper_XX

AMENDMENT TO RID PRE-COMMITMENT (exp_a_precommit)
Reason: [specific reason, e.g., "HMDA data for paper_02 coverage gap pre-2004"]
Change: [what changed]
Impact on results: [how this could affect conclusions]
Original hash: [abc1234]
```

All amendments will be listed in the paper's appendix for full transparency.
