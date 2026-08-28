#!/usr/bin/env python3
"""Score the human-coder baseline submissions for Exp B.

Reads each submitted R script in
``audit/human_coder_baseline/submissions/{sid}_submission.R``, executes
it deterministically with ``Rscript --vanilla``, parses the printed
``treatment_effect_estimate`` line, and compares against the frozen
canonical estimator on the realised dataset.

Cost: $0. No LLM API calls. No model outputs touched. No frozen
CSV/JSON artifact modified.

Status semantics
----------------
A scenario submission counts as ``completed`` iff its
``{sid}_submission.R`` is non-placeholder. Placeholder detection: the
file content contains the marker string written by
``prepare_human_coder_baseline.py``. If no completed submissions exist,
the script writes an ``incomplete`` summary and exits 0 successfully.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET_DIR = ROOT / "audit/human_coder_baseline/task_packet"
SUBMIT_DIR = ROOT / "audit/human_coder_baseline/submissions"
DGP_VERIF = ROOT / "audit/dgp_verification.json"
SCEN_DIR = ROOT / "experiments/exp_b/scenarios"
SUMMARY_JSON = ROOT / "audit/human_coder_baseline/summary.json"
SUMMARY_MD = ROOT / "audit/human_coder_baseline/summary.md"

ES_MAX_WINDOW = 11
PLACEHOLDER_MARKER = "Placeholder — replace this comment"


def load_canonical() -> dict[str, float]:
    payload = json.loads(DGP_VERIF.read_text())
    return {r["scenario_id"]: float(r["estimated"])
            for r in payload["results"]
            if r.get("estimated") is not None}


def is_placeholder(path: Path) -> bool:
    if not path.exists():
        return True
    text = path.read_text(encoding="utf-8")
    if PLACEHOLDER_MARKER in text:
        return True
    # Empty / comments-only files do not constitute a submission.
    code_lines = [ln for ln in text.splitlines()
                  if ln.strip() and not ln.lstrip().startswith("#")]
    return not code_lines


def run_r(code_path: Path, timeout: int = 120) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            ["Rscript", "--vanilla", str(code_path)],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode == 0, result.stdout, result.stderr.strip()[-500:]
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except FileNotFoundError:
        return False, "", "Rscript not found in PATH"
    except Exception as e:
        return False, "", str(e)[:300]


def parse_estimate(stdout: str) -> float | None:
    m = re.search(
        r"treatment_effect_estimate\s*:?\s*(-?\d+\.?\d*(?:[eE][-+]?\d+)?)",
        stdout,
    )
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def es_pass(est: float | None, per_day: float | None,
            tol: float, max_k: int = ES_MAX_WINDOW) -> bool:
    if est is None or per_day is None or abs(per_day) < 1e-9:
        return False
    for k in range(1, max_k + 1):
        target = per_day * k
        if abs(target) < 1e-9:
            continue
        if abs(est - target) / abs(target) < tol:
            return True
    return False


def write_incomplete_summary(picked: list[str], reason: str) -> None:
    payload = {
        "status": "incomplete",
        "n_picked": len(picked),
        "n_completed_submissions": 0,
        "scenario_ids": picked,
        "message": reason,
        "L2b_rate": None,
        "L2b_plus_rate": None,
    }
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_lines = [
        "# Human Coder Baseline — Summary",
        "",
        "**Status:** incomplete",
        "",
        reason,
        "",
        f"- Scenarios prepared: {len(picked)}",
        "- Submissions completed: 0",
        "",
        "Re-run `python3 scripts/score_human_coder_baseline.py` after the "
        "human coder commits non-placeholder R scripts to "
        "`audit/human_coder_baseline/submissions/`.",
        "",
    ]
    SUMMARY_MD.write_text("\n".join(md_lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=0.5,
                    help="Relative error tolerance (default 0.5).")
    args = ap.parse_args()

    if not PACKET_DIR.exists():
        print(f"task packet missing: {PACKET_DIR}\n"
              f"run `python3 scripts/prepare_human_coder_baseline.py` first.")
        return 0

    manifest_path = PACKET_DIR / "manifest.json"
    if not manifest_path.exists():
        write_incomplete_summary([], "task packet manifest is missing")
        return 0
    manifest = json.loads(manifest_path.read_text())
    picked: list[str] = []
    for ids in manifest.get("scenario_ids_by_method", {}).values():
        picked.extend(ids)
    picked = sorted(picked, key=lambda x: int(x[1:]))

    if not picked:
        write_incomplete_summary([], "no scenarios in manifest")
        return 0

    canonical = load_canonical()
    scenarios = {p.stem: json.loads(p.read_text())
                 for p in SCEN_DIR.glob("s*.json")}

    rows: list[dict] = []
    completed = 0
    l2b = 0
    l2bp = 0
    rcode_paths_for_each_sid: dict[str, Path] = {
        sid: SUBMIT_DIR / f"{sid}_submission.R" for sid in picked
    }

    for sid in picked:
        rcode = rcode_paths_for_each_sid[sid]
        method = scenarios.get(sid, {}).get("method_family", "?")
        canon = canonical.get(sid)

        if is_placeholder(rcode):
            rows.append({
                "scenario_id": sid, "method": method, "submitted": 0,
                "L2b": 0, "L2b_plus": 0, "estimate": None, "canonical": canon,
                "rel_error": None, "stderr": "(no submission)",
            })
            continue

        completed += 1
        ok, stdout, stderr = run_r(rcode)
        est = parse_estimate(stdout) if ok else None
        passes = False
        rel_err = None
        if ok and est is not None and canon is not None and abs(canon) > 1e-9:
            if method == "EVENT_STUDY":
                passes = es_pass(est, canon, args.tolerance)
            else:
                rel_err = abs(est - canon) / abs(canon)
                passes = rel_err < args.tolerance

        if ok:
            l2b += 1
        if passes:
            l2bp += 1
        rows.append({
            "scenario_id": sid, "method": method, "submitted": 1,
            "L2b": int(ok), "L2b_plus": int(passes),
            "estimate": est, "canonical": canon,
            "rel_error": (round(rel_err, 4) if rel_err is not None else None),
            "stderr": stderr if not ok else "",
        })
        tag = "+" if passes else ("V" if ok else ".")
        est_s = f"{est:+.4f}" if est is not None else "?"
        canon_s = f"{canon:+.4f}" if canon is not None else "?"
        print(f"  {sid} {method:<12} L2b={int(ok)} L2b+={int(passes)} "
              f"[{tag}] est={est_s} canon={canon_s}")

    if completed == 0:
        write_incomplete_summary(
            picked,
            "all submissions are placeholder files; no human R code has "
            "been committed yet")
        print("\nstatus: incomplete (0 submissions). summary written.")
        return 0

    summary = {
        "status": "completed" if completed == len(picked) else "partial",
        "n_picked": len(picked),
        "n_completed_submissions": completed,
        "tolerance": args.tolerance,
        "L2b_rate": round(l2b / completed, 3) if completed else None,
        "L2b_plus_rate": round(l2bp / completed, 3) if completed else None,
        "by_scenario": rows,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Human Coder Baseline — Summary",
        "",
        f"**Status:** {summary['status']}",
        "",
        f"- Scenarios prepared: {len(picked)}",
        f"- Submissions completed: {completed}",
        f"- Tolerance: relative error ≤ {args.tolerance:.0%} "
        "(ES-window-aware acceptance for Event Study)",
        f"- L2b rate (executes): "
        f"{l2b}/{completed} = {summary['L2b_rate']*100:.1f}%",
        f"- L2b+ rate (canonical match): "
        f"{l2bp}/{completed} = {summary['L2b_plus_rate']*100:.1f}%",
        "",
        "## Per-scenario",
        "",
        "| sid | method | submitted | L2b | L2b+ | rel.err |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        md.append(
            f"| {r['scenario_id']} | {r['method']} | {r['submitted']} | "
            f"{r['L2b']} | {r['L2b_plus']} | "
            f"{r['rel_error'] if r['rel_error'] is not None else ''} |"
        )
    SUMMARY_MD.write_text("\n".join(md), encoding="utf-8")

    print()
    print(f"Wrote: {SUMMARY_JSON}")
    print(f"Wrote: {SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
