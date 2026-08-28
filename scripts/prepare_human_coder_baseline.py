#!/usr/bin/env python3
"""Prepare a blinded human-coder baseline task packet for Exp B.

A trained human coder receives the same fields the LLMs received (title,
research_question, data_description, data_file path, data preview, column
types) and writes R code that prints the treatment-effect coefficient in
a fixed format. Submissions are scored later by
``scripts/score_human_coder_baseline.py`` against the frozen canonical
estimator on the realised dataset.

The packet is BLINDED:
- Does not include the canonical estimator or L2b+ label.
- Does not include DGP truth (``dgp_truth.effect`` / ``direction``).
- Does not include any model output, judge output, or per-cell scores.

Cost: $0. Pure file generation; no LLM API calls.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / "experiments/exp_b/scenarios"
PACKET_DIR = ROOT / "audit/human_coder_baseline/task_packet"
SUBMIT_DIR = ROOT / "audit/human_coder_baseline/submissions"

INSTRUCTIONS = """\
# Human Coder Baseline — Task Packet

You will receive {n} blinded Exp B scenarios stratified across DID, Event
Study, IV, and RDD. Each scenario lives in its own ``{{sid}}_task.md``
file in this directory.

## Your task

For each scenario:

1. Read ``{{sid}}_task.md``. It contains the research question, the data
   description, the path to a CSV file, a preview of that file, and the
   column types. This is the **same** information the evaluated LLMs
   received.

2. Write a standalone R script that:
   - reads the CSV from the path printed in the task,
   - implements the appropriate causal-inference design,
   - prints the treatment-effect estimate in EXACTLY this format on its
     own line:

     ```r
     cat("treatment_effect_estimate:", estimate, "\\n")
     ```

3. Save the script as
   ``audit/human_coder_baseline/submissions/{{sid}}_submission.R``.

## What you do NOT see

Per the blinding protocol you do NOT see the canonical estimator's
output, the L2b+ pass label, the DGP parameter ``dgp_truth.effect``, the
LLM model outputs, or any judge output. Do not look these up before
finishing your submissions.

## What this baseline measures

This is a **solvability audit**. A submission is L2b-correct if your R
script executes without error; it is L2b+-correct if your printed
``treatment_effect_estimate`` matches the canonical estimator on the
realised dataset within the same tolerance the paper uses (relative
error ≤ 50 %, with ES-window-aware acceptance for Event Study). The
audit is *not* a population estimate of expert performance.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20,
                    help="Total number of scenarios to sample (default: 20).")
    ap.add_argument("--seed", type=int, default=20260505,
                    help="Random seed for stratified sampling.")
    ap.add_argument("--include-preview-rows", type=int, default=5)
    args = ap.parse_args()

    PACKET_DIR.mkdir(parents=True, exist_ok=True)
    SUBMIT_DIR.mkdir(parents=True, exist_ok=True)

    scenarios = [json.loads(p.read_text()) for p in
                 sorted(SCEN_DIR.glob("s*.json"), key=lambda p: int(p.stem[1:]))]
    by_method: dict[str, list[dict]] = defaultdict(list)
    for s in scenarios:
        by_method[s["method_family"]].append(s)

    rng = random.Random(args.seed)
    target_per_family = max(1, args.n // max(1, len(by_method)))
    picked: list[dict] = []
    for fam, lst in sorted(by_method.items()):
        picked.extend(rng.sample(lst, min(target_per_family, len(lst))))
    while len(picked) < args.n:
        candidates = [s for s in scenarios if s not in picked]
        if not candidates:
            break
        picked.append(rng.choice(candidates))
    picked = picked[: args.n]

    print(f"Sampled {len(picked)} scenarios "
          f"(target {args.n}, seed {args.seed}, stratified):")
    by_method_picked: dict[str, list[str]] = defaultdict(list)
    for s in picked:
        by_method_picked[s["method_family"]].append(s["scenario_id"])
    for fam in sorted(by_method_picked):
        ids = ", ".join(sorted(by_method_picked[fam], key=lambda x: int(x[1:])))
        print(f"  {fam:<12} ({len(by_method_picked[fam]):>2}) {ids}")

    # Write per-scenario task files.
    for s in picked:
        sid = s["scenario_id"]
        df = pd.read_csv(s["data_file"], nrows=args.include_preview_rows)
        preview = df.to_string(index=False)
        col_types = "\n".join(f"  {c}: {t}" for c, t in df.dtypes.items())

        lines = [
            f"# Task: {sid}",
            "",
            f"**Title.** {s['title']}",
            "",
            "## Research question",
            "",
            s["research_question"].strip(),
            "",
            "## Data description",
            "",
            s["data_description"].strip(),
            "",
            f"**Data file path.** `{s['data_file']}`",
            "",
            "## Data preview (first rows)",
            "",
            "```",
            preview,
            "```",
            "",
            "## Column types",
            "",
            "```",
            col_types,
            "```",
            "",
            "## Output requirement",
            "",
            "Your R script must print exactly one line in this format:",
            "",
            "```r",
            'cat("treatment_effect_estimate:", estimate, "\\n")',
            "```",
            "",
            "Save the script at "
            f"`audit/human_coder_baseline/submissions/{sid}_submission.R`.",
            "",
        ]
        (PACKET_DIR / f"{sid}_task.md").write_text("\n".join(lines), encoding="utf-8")

        # Submission placeholder (do not include any solution).
        sub_path = SUBMIT_DIR / f"{sid}_submission.R"
        if not sub_path.exists():
            sub_path.write_text(
                "# Placeholder — replace this comment with the human coder's R "
                "script.\n"
                "# Read the corresponding task file at\n"
                f"#   audit/human_coder_baseline/task_packet/{sid}_task.md\n"
                "# and remove this placeholder before submitting.\n",
                encoding="utf-8",
            )

    # Top-level instructions + manifest.
    (PACKET_DIR / "INSTRUCTIONS.md").write_text(
        INSTRUCTIONS.format(n=len(picked)), encoding="utf-8")
    manifest = {
        "n_sampled": len(picked),
        "seed": args.seed,
        "scenario_ids_by_method": {
            fam: sorted(by_method_picked[fam], key=lambda x: int(x[1:]))
            for fam in sorted(by_method_picked)
        },
        "blinding": {
            "canonical_estimator_excluded": True,
            "l2b_plus_label_excluded": True,
            "dgp_truth_excluded": True,
            "model_outputs_excluded": True,
        },
    }
    (PACKET_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")

    print()
    print(f"Task packet : {PACKET_DIR}")
    print(f"Submissions : {SUBMIT_DIR} (placeholders only)")
    print("Status      : incomplete (no human submissions yet).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
