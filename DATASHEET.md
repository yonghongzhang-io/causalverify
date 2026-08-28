# Datasheet for CausalVerify

This datasheet follows the spirit of "Datasheets for Datasets" and describes
the final CausalVerify NeurIPS 2026 submission artifact. It is intended to make clear
what the benchmark can support, what it cannot support, and which parts of the
repository are reusable data versus code, derived context, model output, or
local-only provenance.

## Motivation

**For what purpose was CausalVerify created?**

CausalVerify was created to evaluate large language model (LLM)
causal-inference workflows with an emphasis on execution-grounded verification.
The benchmark separates four kinds of evidence that are often conflated:

1. text-level agreement about method family and effect direction,
2. code generation,
3. executable numerical estimator recovery, and
4. retrospective self-assessment calibration.

The central claim is not that CausalVerify measures universal "causal
intelligence." The claim is narrower: causal-workflow evaluation should
distinguish what a model says from what its executable workflow computes.

**Who created the dataset and on behalf of which entity?**

The benchmark was created by the paper authors. Author identity is withheld in
the review artifact where required by the review policy and will be disclosed
in this release.

**Who funded the creation of the dataset?**

API and compute costs were self-funded by the authors. No external funding is
claimed in the submission artifact.

## Composition

CausalVerify has two main experimental components plus a calibration audit.

### Experiment A: real-paper text-agreement diagnostic

- Active corpus: 259 published economics papers.
- Quarantined papers: 2 (`paper_187`, `paper_203`) due to OCR/source or
  PDF/metadata mismatch issues.
- Task representation: reconstructed research question (RQ), data description
  (DD), and institutional context (IC).
- Labels: 4-LLM consensus labels for method family and effect direction, with
  a 30-paper human ambiguity audit used to estimate label ambiguity rather than
  convert the full corpus into human-gold ground truth.
- Primary reported layers: L1, L3, and L4. L3/L4 are text-level agreement
  metrics, not verified causal-correctness metrics.

### Experiment B: synthetic DGP execution benchmark

- Scenarios: 100 synthetic data-generating processes (DGPs).
- Method families: difference-in-differences, event study, instrumental
  variables, and regression discontinuity.
- Each scenario includes a scenario JSON, a realised fixed-seed CSV dataset,
  and a canonical estimator result computed on that realised dataset.
- Primary reported layer: L2b+, which checks whether executed model-generated
  R code recovers the canonical estimator on the same realised data.

### Calibration audit

- Records: 646 retrospective self-assessment records across seven models.
- Protocol: each model is shown its own prior Exp B answer without the hidden
  truth and asked for confidence scores.
- Reported use: compares self-reported confidence with final L2b+ correctness.

### Model output coverage

- Exp A primary panel: 7 models x 259 papers = 1813 outputs.
- Exp B primary panel: 7 models x 100 scenarios = 700 execution cells.
- Calibration: 646 valid retrospective confidence records.
- Open-weights robustness: Llama-3.3-70B-Instruct is reported only as a
  robustness check where present; it is not part of the primary 7-model
  headline leaderboard.

## Instance fields

### Exp A paper-context records

Typical fields include:

- `paper_id`
- bibliographic metadata where available
- reconstructed `research_question`
- reconstructed `data_description`
- reconstructed `institutional_context`
- source/provenance fields for the reconstruction pass
- consensus labels and aggregation status
- model outputs for each evaluated LLM
- automatic text-level scores

Exp A should be interpreted as a realistic-context diagnostic. Its labels are
consensus labels under ambiguity, not executable ground truth.

### Exp B scenario records

Typical fields include:

- `scenario_id`
- `method_family`
- scenario text and data description
- CSV filename
- DGP metadata
- canonical estimator result on the realised dataset
- model-generated analysis and code
- execution status
- extracted treatment-effect estimate
- L2b+ pass/fail under the frozen canonical-judge-v2 scorer

Exp B is the component that supports execution-grounded correctness claims.

## Collection and generation process

**Experiment A.** Published economics papers were converted into structured
prompt fields using a PDF-to-context reconstruction pipeline. The reconstruction
pipeline applied hard anti-leakage checks to avoid explicit method-name leakage
in RQ/DD/IC fields. A later human audit estimated the ambiguity of consensus
labels on a 30-paper blinded slice.

**Experiment B.** DGP mathematics, realised datasets, canonical estimators, and
ground-truth correctness checks are fixed by the benchmark code. LLMs may write
natural-language analysis and R code, but they do not define the answer key.
The answer key is the canonical estimator evaluated on the fixed realised data.

**Calibration.** Calibration records were generated retrospectively from each
model's own Exp B outputs. Hidden correctness labels were not shown to the
model during confidence elicitation.

## Intended uses

CausalVerify is intended for:

- evaluating LLM causal-inference workflow reliability,
- comparing text-level agreement with execution-grounded correctness,
- studying whether code execution is a useful proxy for numerical correctness,
- studying whether models know when their causal workflow is wrong, and
- reproducing or auditing the frozen benchmark claims.

## Out-of-scope uses and misuses

CausalVerify should not be used to claim:

- that Exp A measures verified causal correctness on published papers,
- that L3/L4 are method-blind causal understanding scores,
- that L2b (code executes) is equivalent to numerical correctness,
- that Exp B covers the full practice of empirical economics,
- that a model passing L2b+ is a complete empirical researcher, or
- that model confidence is a reliable correctness signal without calibration.

Exp B intentionally uses stylized, controlled DGPs so numerical correctness can
be verified. Full empirical-economics competence also involves data cleaning,
identification judgment, robustness analysis, institutional interpretation, and
assumption checking, which are outside the direct scope of L2b+.

## Known limitations

- Exp A labels are consensus labels under real-paper ambiguity. The 30-paper
  human audit should be read as an ambiguity bound rather than a full human-gold
  validation of all 259 papers.
- Exp B uses controlled synthetic DGPs and does not capture every complication
  of empirical economics.
- L2b+ uses a coefficient-extraction judge for robust parsing of heterogeneous
  R outputs. This is documented and should be audited when extending the
  benchmark to new outputs.
- L2b+ pass rates depend on the frozen tolerance and canonical-judge-v2 scorer.
- Calibration coverage is not perfectly balanced across models because some
  provider responses failed or were truncated.
- Model identities refer to provider snapshots available at run time; API model
  behavior may change over time.

## Distribution

The release artifact should include:

- code and scoring scripts,
- synthetic DGP scenarios and realised CSV data,
- scored model outputs and frozen summaries,
- paper-derived structured contexts and metadata,
- consensus labels and audit summaries,
- figures/tables used in the paper, and
- reproducibility manifests.

Original published article PDFs are not licensed by this repository. Public
release artifacts should provide DOI/source metadata, hashes/provenance, and
derived prompt fields rather than redistributing publisher PDFs unless
redistribution rights are confirmed.

## Licensing

See `LICENSE_DATA.md` for component-level licensing. In brief:

- Code: MIT License.
- Synthetic DGP scenarios, generated CSV data, and benchmark scoring outputs:
  CC BY 4.0 where applicable.
- Model outputs: redistributed only where provider terms permit.
- Published article PDFs: not licensed by this repository and excluded from
  the public CC BY data claim unless redistribution rights are confirmed.
- Paper-derived structured contexts: released as derived research metadata
  subject to the stated provenance and licensing caveats.

## Maintenance

The final CausalVerify NeurIPS 2026 submission package is documented by:

- `README.md`
- `RELEASE_NAVIGATION.md`
- `ARTIFACT_MANIFEST.json`
- `audit/V11_ACCEPTANCE_GATES.md`
- `audit/SUBMISSION_BUILD_SUMMARY.md`
- `audit/V11_FREEZE_PDF_SHA.md`

Future updates should change the release manifest and rerun claim-consistency
checks before new numbers are reported.

## Citation

If you use CausalVerify, please cite the corresponding paper. In
review artifacts:

```bibtex
@misc{zhang2026causalverify,
  title={CausalVerify: An Execution-Grounded Benchmark for LLM Causal Inference Workflows},
  author={Zhang, Yonghong and Correia, Ricardo and Parra, Isabel M. and Xie, Yong},
  year={2026},
  url={https://github.com/yonghongzhang-io/causalverify}
}
```
