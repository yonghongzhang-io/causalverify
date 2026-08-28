#!/usr/bin/env bash
# ============================================================================
#  CausalVerify — re-score the v10 results from existing model outputs.
#
#  This script does NOT make any LLM API calls. It only re-runs the
#  deterministic scoring + ranking pipeline on the model outputs already
#  present in experiments/exp_a/outputs and experiments/exp_b/outputs.
#
#  Run inside the Docker image:
#    docker run --rm -v $(pwd):/app causalverify bash scripts/rescore.sh
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> [1/5] auto_score_exp_a (L1/L2a/L2b/L3/L4 on 262 papers)"
python src/pipeline/auto_score_exp_a.py

echo "==> [2/5] score_l2b_plus (L2b+ on 100 DGP scenarios)"
python src/pipeline/score_l2b_plus.py

echo "==> [3/5] head_to_head_ranking (Kendall tau)"
python src/pipeline/head_to_head_ranking.py

echo "==> [4/5] bootstrap_head_to_head (95% CI for tau)"
python src/pipeline/bootstrap_head_to_head.py

echo "==> [5/5] multi_scorer_l4 (S1-S4 fragility analysis)"
python src/pipeline/multi_scorer_l4.py

echo
echo "==> Refreshing paper figures"
python paper/figures/make_fig2_headline.py
python paper/figures/make_fig3_clean.py
python paper/figures/make_fig4_cascade.py
python paper/figures/make_fig_error_cdf.py
python paper/figures/make_fig_rid_pilot.py

echo
echo "Done. Outputs:"
echo "  experiments/exp_a/auto_scores.csv"
echo "  experiments/exp_a/multi_scorer_l4.csv"
echo "  experiments/exp_b/l2b_plus_scores.csv"
echo "  experiments/exp_b/l2b_plus_summary.json"
echo "  experiments/exp_b/head_to_head_ranking.json"
echo "  experiments/exp_b/head_to_head_bootstrap.json"
echo "  paper/figures/fig*.{pdf,png}"
