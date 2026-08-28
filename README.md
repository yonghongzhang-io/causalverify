<h1 align="center">CausalVerify</h1>

<p align="center">
  <b>An execution-grounded benchmark for LLM causal inference workflows.</b>
</p>

<p align="center">
  <a href="LICENSE"><img alt="Code: MIT" src="https://img.shields.io/badge/Code-MIT-blue.svg"></a>
  <a href="LICENSE_DATA.md"><img alt="Data license notes" src="https://img.shields.io/badge/Data-component--level-lightgrey.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-green.svg">
  <img alt="R" src="https://img.shields.io/badge/R-4.4.2-blueviolet.svg">
</p>

Yonghong Zhang<sup>1</sup> · Ricardo Correia<sup>1</sup> · Isabel M. Parra<sup>1</sup> · Yong Xie<sup>2</sup>

<sup>1</sup> Department of Finance, Universidad Autónoma de Madrid, Madrid, Spain
<sup>2</sup> Spanish National Research Council (CSIC), Madrid, Spain

---

## Why CausalVerify

When LLMs are used to produce policy-relevant causal estimates, who verifies that
the model's code actually computes the right number? Existing causal-inference
benchmarks answer this through **text inspection**: they read what the model
*says* and check it against a text-based answer key. A benchmark of language is
not the same as a benchmark of computation — executable code is not necessarily
causally correct, and only **execution-grounded evaluation** can detect that gap.

CausalVerify evaluates LLM causal-inference workflows over **259 active published
economics papers** (Experiment A) and **100 synthetic data-generating processes**
(Experiment B). Its central methodological contribution is **L2b+**, a scoring
layer that runs each model's generated R code against synthetic data and checks
that the estimated treatment effect matches the canonical estimator on the
*realised* dataset — rather than the ideal DGP parameter, which would penalise
models for finite-sample deviation.

## The layered evaluation framework

| Layer | Question | Scoring | Requires DGP |
|---|---|---|---|
| **L1** | Output is non-empty? | Deterministic (length) | No |
| **L2a** | Contains R code block? | Deterministic (regex) | No |
| **L2b** | Code executes without error? | Deterministic (`Rscript`) | No |
| **L2b+** | Estimated coefficient matches canonical estimator? | Execution + judge extraction + numeric check | **Yes** |
| **L3** | Method-family agreement (text-level)? | Text inspection, fragile | No |
| **L4** | Direction agreement (text-level)? | Text inspection, fragile | No |

L2b+ is the only layer combining executed code with a numeric correctness check.
It is computable on Experiment B only; Experiment A contributes ecological
breadth and text-level agreement diagnostics.

## Headline results (Experiment B, N = 100 DGPs, 7 primary models)

| Statement | Evidence |
|---|---|
| L2b (code executes) ranks models tightly with ground truth | Kendall τ = +0.81; Spearman ρ = +0.93 |
| L4 text scoring is essentially uncorrelated with ground truth | τ ∈ [−0.20, +0.10] across the S1/S2 text-direction scorers |
| Code that runs is not code that computes correctly | L2b spans 32–94%; ES-aware canonical L2b+ spans 10–88% |
| Text-level scores are supporting diagnostics | L3/L4 measure method-family and direction agreement, not method-blind detection |

Llama-3.3-70B-Instruct is retained as an open-weights Experiment B robustness
check and is excluded from the primary ranking.

## What is in this repository

| Path | Contents |
|---|---|
| `src/` | Pipeline, agents, scoring, de-leakage, analysis |
| `scripts/` | Analysis, re-scoring, and figure-build entry points |
| `experiments/exp_a/` | Experiment A benchmark definition, pre-commitment, methodology notes, redacted score tables |
| `experiments/exp_b/scenarios/` | 100 task-facing scenario definitions |
| `experiments/exp_b/` | Aggregate summaries, ranking, calibration, redacted per-scenario score tables |
| `audit/` | Audit methodology, human-validation summaries, robustness analyses |
| `paper/` | Manuscript source, figures, tables |
| `docs/` | Pipeline walkthrough |

### What is deliberately not here

This repository does **not** publish the quantities the benchmark scores
against: per-scenario `dgp_truth` / `true_effect`, per-paper `direction` and
`method` labels, canonical hidden targets, or sealed manifests. Per-item result
tables are published as redacted copies that keep the identifier, the model, and
the scoring outcome, and drop the target together with any column from which the
target could be reconstructed.

[`REDACTIONS.md`](REDACTIONS.md) documents every dropped column and the reason.

Raw model outputs, realised DGP datasets, and the source-paper corpus are not
tracked in git. Source-paper PDFs are third-party publications and are not
redistributed.

## Dataset

Large artifacts — realised scenario datasets and cached model outputs — are
released separately:

    https://huggingface.co/datasets/yonghongzhang/causalverify

Croissant metadata for Experiment B: [`experiments/exp_b/croissant.json`](experiments/exp_b/croissant.json).
Datasheet: [`DATASHEET.md`](DATASHEET.md). Licensing: [`LICENSE_DATA.md`](LICENSE_DATA.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

L2b / L2b+ execute generated R code, so an R installation is required:

```r
install.packages(c("fixest", "did", "rdrobust", "AER", "sandwich", "lmtest", "broom"))
```

API keys:

```bash
cp sample.env .env
# edit .env with OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, MOONSHOT_API_KEY
```

> L2b / L2b+ run model-generated R code. Run new scoring inside the provided
> container (`Dockerfile`) rather than on a host you care about.

## Reproduction

Aggregate results and every figure in the paper are reproducible from the files
in this repository. Reproducing per-item scoring additionally requires the
realised datasets and cached outputs from the dataset release above, plus the
scoring-side targets.

```bash
bash scripts/rescore.sh        # re-run scoring
bash scripts/build_paper.sh    # rebuild figures and the manuscript
```

## Models evaluated

| Model | Provider | Identifier |
|---|---|---|
| Claude Opus | Anthropic | `claude-opus-4-6` |
| Claude Sonnet | Anthropic | `claude-sonnet-4-20250514` |
| GPT-4o | OpenAI | `gpt-4o` |
| o3 | OpenAI | `o3` |
| GPT-5 | OpenAI | `gpt-5` |
| Kimi | Moonshot | `moonshot-v1-128k` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` |

Gemini responses are truncation-limited in parts of the benchmark, especially
calibration; tables mark incomplete coverage explicitly.

## Relation to the earlier anonymous release

An anonymous release of this project accompanied its first submission and is
retained unchanged as a frozen archive at
[`causalverify/causalverify`](https://github.com/causalverify/causalverify).
This repository is the project's long-term home; it does not inherit that
history, and it does not carry the truth-bearing files that release contained.

## Citation

```bibtex
@misc{zhang2026causalverify,
  title  = {CausalVerify: An Execution-Grounded Benchmark for LLM Causal Inference Workflows},
  author = {Zhang, Yonghong and Correia, Ricardo and Parra, Isabel M. and Xie, Yong},
  year   = {2026},
  url    = {https://github.com/yonghongzhang-io/causalverify}
}
```

See also [`CITATION.cff`](CITATION.cff).

## License

| Component | License |
|---|---|
| Code | MIT — see [`LICENSE`](LICENSE) |
| Data (scenarios, scored outputs, summaries) | CC BY 4.0 |
| Benchmark documentation | See [`DATASHEET.md`](DATASHEET.md) |
