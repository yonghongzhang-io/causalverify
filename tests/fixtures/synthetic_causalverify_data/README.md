# Synthetic test fixture — NOT benchmark data

Everything in this directory is **made up** for the unit tests of the Inspect
port (`causalverify_inspect/`). The "papers" cite fictional authors and
journals, the "scenarios" describe invented policies, the "targets"
(`audit/gt_aggregate_decisions.json`, `dgp_truth`, `audit/dgp_verification.json`)
are arbitrary numbers, the CSVs are a handful of hand-typed rows, and the
"model outputs" under `synthetic_outputs/` were written by hand to exercise
specific scoring paths (code that runs, code that fails, no code, empty output).

None of it reconstructs any CausalVerify item or scoring target. Identifiers use
ranges the real benchmark does not (`paper_9xxx`, `s9xx`) so the two can never
be confused. See `REDACTIONS.md` at the repository root for what the public
repository deliberately omits.

Layout (mirrors what `CAUSALVERIFY_DATA` must contain):

    experiments/exp_a/papers/paper_9001.json ... Experiment A items
    audit/gt_aggregate_decisions.json            Experiment A targets
    experiments/exp_b/scenarios/s901.json ...    Experiment B items incl. dgp_truth / ground_truth
    experiments/exp_b/data/s901_data.csv ...     tiny realised datasets
    audit/dgp_verification.json                  canonical baselines (s904 deliberately missing)
    synthetic_outputs/exp_{a,b}/*_synthetic-model.json  canned completions in the pipeline's output format
