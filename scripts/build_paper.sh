#!/usr/bin/env bash
# ============================================================================
#  CausalVerify — build the manuscript (author version)
#  (causalverify_neurips2026.pdf)
#
#  Run from the repository root. Requires Docker with the texlive image.
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

docker run --rm -v "$(pwd)/paper:/paper" -w /paper/latex \
    texlive/texlive:latest bash -c "
        pdflatex -interaction=nonstopmode causalverify_neurips2026.tex &&
        bibtex   causalverify_neurips2026 &&
        pdflatex -interaction=nonstopmode causalverify_neurips2026.tex &&
        pdflatex -interaction=nonstopmode causalverify_neurips2026.tex
    "

echo
echo "Built: paper/latex/causalverify_neurips2026.pdf"
