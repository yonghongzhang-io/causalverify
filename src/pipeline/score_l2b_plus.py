"""
L2b+ Scoring: Execution + Coefficient Match against Canonical Estimator
=======================================================================

Beyond L2b (code executes), L2b+ also requires that the model's estimated
treatment effect matches the canonical estimator on the realised dataset
within a tolerance.

L2b   = code runs (exit code 0)                           [necessary]
L2b+  = code runs AND |β_model - β_canonical| / |β_canonical| < TOL

This is only computable for Exp B, where realised synthetic datasets and
pre-specified canonical estimators are available. The canonical baseline is
not the ideal DGP parameter; this avoids penalizing models for finite-sample
deviations that the canonical estimator also exhibits.

Usage:
  python src/pipeline/score_l2b_plus.py
  python src/pipeline/score_l2b_plus.py --tolerance 0.5
  python src/pipeline/score_l2b_plus.py --models claude-opus-4-6 gpt-4o
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

SCEN_DIR = Path("experiments/exp_b/scenarios")
OUT_DIR = Path("experiments/exp_b/outputs")
RESULTS_DIR = Path("experiments/exp_b")
CANONICAL_BASELINES = Path("audit/dgp_verification.json")

MODELS = [
    ("moonshot-v1-128k", "Kimi"),
    ("claude-sonnet-4-20250514", "Sonnet"),
    ("gpt-4o", "GPT-4o"),
    ("o3", "o3"),
    ("claude-opus-4-6", "Opus"),
    ("gemini-2.5-flash", "Gemini"),
    ("gpt-5", "GPT-5"),
    # Open-weights cross-vendor robustness check (Nebius API).
    # File slugs replace "/" with "-" via run_exp_b.py:run_scenario.
    ("meta-llama-Llama-3.3-70B-Instruct", "Llama"),
]

# Default tolerance: |estimated - true| / |true| < 0.5 (within 50% of truth)
DEFAULT_TOL = 0.5


def load_canonical_baselines(path: Path = CANONICAL_BASELINES) -> dict[str, dict]:
    """Load canonical estimator baselines from the DGP verifier output.

    Current audit/dgp_verification.json schema is:
      {"summary": ..., "results": [{"scenario_id": "s01", "estimated": ...}, ...]}

    The canonical baseline is the verifier's standard estimator on the same
    synthetic data, not the ideal DGP parameter. This avoids penalizing LLMs
    for finite-sample deviations that the canonical estimator also exhibits.
    """
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    out = {}
    for row in rows:
        sid = row.get("scenario_id")
        estimated = row.get("estimated")
        if sid is None or estimated is None:
            continue
        out[sid] = {
            "effect": float(estimated),
            "direction": "positive" if float(estimated) > 0 else "negative",
            "status": row.get("status", ""),
            "rel_error_vs_dgp": row.get("rel_error"),
            "standard_error": row.get("standard_error"),
            "source": str(path),
        }
    return out


def output_paths_for_baseline(baseline: str) -> tuple[Path, Path]:
    """Preserve the original DGP-baseline outputs; suffix canonical outputs."""
    if baseline == "dgp":
        return RESULTS_DIR / "l2b_plus_scores.csv", RESULTS_DIR / "l2b_plus_summary.json"
    return (
        RESULTS_DIR / f"l2b_plus_scores_{baseline}.csv",
        RESULTS_DIR / f"l2b_plus_summary_{baseline}.json",
    )


def freeze_dgp_baseline_if_needed() -> Path | None:
    """Snapshot the existing DGP-baseline CSV before a non-DGP run can clobber
    downstream artifacts. Returns the path to the frozen copy, or None if no
    snapshot was needed.

    Why this matters
    ----------------
    The v10 paper figures and tables reference l2b_plus_scores.csv as the
    canonical L2b+ artifact under the DGP baseline. A naive `--baseline dgp`
    rerun (e.g. for fresh diagnostics) would overwrite that file in place. We
    freeze it once with a clear name so the v10 numbers stay reproducible.
    """
    dgp_csv = RESULTS_DIR / "l2b_plus_scores.csv"
    frozen = RESULTS_DIR / "l2b_plus_scores_dgp_v10frozen.csv"
    dgp_json = RESULTS_DIR / "l2b_plus_summary.json"
    frozen_json = RESULTS_DIR / "l2b_plus_summary_dgp_v10frozen.json"
    if dgp_csv.exists() and not frozen.exists():
        frozen.write_bytes(dgp_csv.read_bytes())
        if dgp_json.exists() and not frozen_json.exists():
            frozen_json.write_bytes(dgp_json.read_bytes())
        print(f"Snapshot: froze {dgp_csv.name} -> {frozen.name} (preserves v10 paper numbers)")
        return frozen
    return None


# ── R code extraction (from existing score_exp_b.py) ─────────────────────

def extract_r_code(text: str) -> str | None:
    """Extract first R code block from a markdown response."""
    # Markdown fence with r/R
    m = re.search(r"```(?:r|R)\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Generic fence containing R idioms
    m = re.search(r"```\n((?:[^`]+library\([^`]*|[^`]+lm\([^`]*))\n```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def execute_r_code(code: str, timeout: int = 60) -> tuple[bool, str, str]:
    """Run R code and return (success, stdout, stderr)."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".R", mode="w", delete=False, dir="/tmp") as f:
            # Wrap to print all coefficients clearly
            wrapper = f"""
options(warn = -1)
suppressMessages({{
{code}
}})
"""
            f.write(wrapper)
            tmp = f.name
        result = subprocess.run(
            ["Rscript", "--vanilla", tmp],
            capture_output=True, text=True, timeout=timeout,
        )
        os.unlink(tmp)
        return result.returncode == 0, result.stdout, result.stderr.strip()[-500:]
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


# ── Coefficient extraction from R output ─────────────────────────────────

# Patterns that match common ways R prints regression coefficients.
# Each pattern captures one number (or two — see below).
# Order matters: most specific first.
NUM = r"(-?\d+\.?\d*(?:[eE][-+]?\d+)?)"

# Tier 1: explicit labeled output like "DID coef: -0.2387" or "ATT: 0.215"
LABELED_PATTERNS = [
    rf"(?:DID|DiD|did)\s*(?:coef(?:ficient)?|estimate)\s*[:=]\s*{NUM}",
    rf"(?:ATT|ate|att|ATE)\s*(?:\([^)]*\))?\s*[:=]\s*{NUM}",
    rf"(?:treatment\s*effect|main\s*effect|causal\s*effect)\s*[:=]?\s*{NUM}",
    rf"(?:CAR|car|cumulative\s*abnormal\s*return)\s*[:=]?\s*{NUM}",
    rf"(?:IV|2sls|2SLS)\s*(?:coef|estimate)\s*[:=]?\s*{NUM}",
    rf"(?:RD|RDD)\s*(?:coef|estimate)\s*[:=]?\s*{NUM}",
    rf"(?:beta|β|coefficient)[\s_]*(?:on|of)?[\s_]*(?:treat|treatment|did|x|D)\s*[:=]?\s*{NUM}",
    rf"\(Intercept\)[^\n]*\n.*?(?:treat|did|x_treat|treat_x_post|treated_post|post:treated)[^\n]*?{NUM}",
]

# Tier 2: line-position patterns (lm/felm summary tables)
LINE_PATTERNS = [
    # treat:post 0.215 (after coefficient name)
    rf"^(?:treat[_:x*]post|treat_x_post|treated:post|post:treated|did|treated_post|tariff_post|treatedTRUE|treat\d?)\s+{NUM}",
    rf"^treat(?:ed)?\s+{NUM}",
    # IV: x estimate
    rf"^(?:x|X|D|d)\s+{NUM}\s+[\d.]+",
    # RDD: rdrobust output
    rf"^(?:Robust|Conventional|Bias-Corrected)\s+{NUM}\s+[\d.]+",
    # GLM/quasi
    rf"(?:treat|did)[\w]*\s+{NUM}\s+[\d.]+\s+[-\d.]+\s+[\d.e-]+",
]


def extract_coefficient(stdout: str, method: str) -> float | None:
    """Try to extract the main treatment effect from R stdout.

    Strategy:
    1. First try labeled output ('DID coef: X', 'ATT: X')
    2. Then try line-position patterns (lm summary table)
    3. Fallback: find lines with 'treat' and pull the first plausible number
    """
    def is_plausible(v: float) -> bool:
        return -2.0 < v < 2.0 and abs(v) >= 1e-5

    # Tier 1: labeled patterns (most reliable)
    for pat in LABELED_PATTERNS:
        for m in re.finditer(pat, stdout, re.IGNORECASE | re.MULTILINE | re.DOTALL):
            try:
                v = float(m.group(1))
                if is_plausible(v):
                    return v
            except (ValueError, IndexError):
                continue

    # Tier 2: line-position patterns
    for pat in LINE_PATTERNS:
        for m in re.finditer(pat, stdout, re.IGNORECASE | re.MULTILINE):
            try:
                v = float(m.group(1))
                if is_plausible(v):
                    return v
            except (ValueError, IndexError):
                continue

    # Tier 3: fallback — scan lines containing "treat" or method-specific words
    method_lower = method.lower()
    keywords = {
        "DID": ["treat", "did", "post"],
        "EVENT_STUDY": ["car", "abnormal", "ar"],
        "IV": ["x", "endog", "iv"],
        "RDD": ["treat", "above", "rd"],
    }.get(method, ["treat"])

    for line in stdout.splitlines():
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords):
            # Skip header/label lines
            if any(skip in line_lower for skip in ["estimate std", "coef se", "===", "---",
                                                     "interpretation", "summary"]):
                continue
            nums = re.findall(rf"{NUM}", line)
            for n in nums:
                try:
                    v = float(n)
                    if is_plausible(v):
                        return v
                except ValueError:
                    continue
    return None


# ── Per-output scoring ───────────────────────────────────────────────────

def score_output(
    scenario: dict,
    llm_output: dict,
    tolerance: float = DEFAULT_TOL,
    baseline: str = "dgp",
    canonical_baselines: dict[str, dict] | None = None,
) -> dict:
    """Compute L1, L2a, L2b, L2b+ for a single output."""
    content = llm_output.get("llm_response", {}).get("content", "")
    sid = scenario["scenario_id"]
    method = scenario["method_family"]
    dgp = scenario.get("dgp_truth", {})
    dgp_effect = dgp.get("effect")
    dgp_direction = dgp.get("direction", "")
    baseline_effect = dgp_effect
    baseline_direction = dgp_direction
    baseline_source = "dgp_truth.effect"
    baseline_available = True
    canonical_status = ""

    if baseline == "canonical":
        canonical = (canonical_baselines or {}).get(sid)
        if canonical:
            baseline_effect = canonical["effect"]
            baseline_direction = canonical["direction"]
            baseline_source = canonical["source"]
            canonical_status = canonical.get("status", "")
        else:
            baseline_effect = None
            baseline_direction = ""
            baseline_source = "missing_canonical_baseline"
            baseline_available = False

    # L1: non-empty output
    l1 = bool(content.strip())

    # L2a: has R code block
    code = extract_r_code(content)
    l2a = code is not None

    # L2b: code executes
    l2b = False
    estimated = None
    err = ""
    stdout_excerpt = ""
    if l2a:
        # Run code as-is; cwd inherited from the python process (project root)
        ok, stdout, err = execute_r_code(code)
        l2b = ok
        if ok and stdout:
            estimated = extract_coefficient(stdout, method)
            stdout_excerpt = stdout[-400:]

    # L2b+: code runs AND coefficient matches the selected baseline
    l2b_plus = False
    rel_error = None
    if l2b and estimated is not None and baseline_effect is not None and abs(baseline_effect) > 1e-6:
        rel_error = abs(estimated - baseline_effect) / abs(baseline_effect)
        l2b_plus = rel_error < tolerance

    return {
        "scenario_id": sid,
        "method": method,
        "dgp_effect": dgp_effect,
        "dgp_direction": dgp_direction,
        # Backward-compatible aliases used by older tables/scripts. Under
        # canonical mode these refer to the selected scoring baseline.
        "true_effect": baseline_effect,
        "true_direction": baseline_direction,
        "baseline": baseline,
        "baseline_effect": baseline_effect,
        "baseline_direction": baseline_direction,
        "baseline_source": baseline_source,
        "baseline_available": int(baseline_available),
        "canonical_status": canonical_status,
        "L1": int(l1),
        "L2a": int(l2a),
        "L2b": int(l2b),
        "estimated": estimated,
        "rel_error": round(rel_error, 4) if rel_error is not None else None,
        "L2b_plus": int(l2b_plus),
        "err_excerpt": err[:200] if err else "",
    }


# ── Main pipeline ───────────────────────────────────────────────────────

def run_scoring(model_filter: list[str] | None, tolerance: float, baseline: str):
    scenarios = sorted(SCEN_DIR.glob("s*.json"), key=lambda p: int(p.stem[1:]))
    # Always freeze the DGP-baseline CSV before any rerun so v10 numbers
    # stay reproducible whether we are about to overwrite (--baseline dgp)
    # or shift to a new baseline.
    freeze_dgp_baseline_if_needed()

    canonical_baselines = load_canonical_baselines() if baseline == "canonical" else {}
    rows = []
    print(f"Scoring L2b+ on {len(scenarios)} scenarios × {len(MODELS)} models "
          f"(tolerance={tolerance}, baseline={baseline})", flush=True)
    if baseline == "canonical":
        print(f"Canonical baselines loaded: {len(canonical_baselines)}", flush=True)
        if not canonical_baselines:
            raise SystemExit(
                "ERROR: --baseline canonical requested but audit/dgp_verification.json "
                "is empty or missing. Run src/agents/dgp_verifier.py first."
            )
    print("=" * 80, flush=True)

    for s_file in scenarios:
        scenario = json.load(open(s_file))
        sid = scenario["scenario_id"]

        for model_slug, model_short in MODELS:
            if model_filter and model_slug not in model_filter:
                continue
            out_file = OUT_DIR / f"{sid}_{model_slug}.json"
            if not out_file.exists():
                continue
            llm_output = json.load(open(out_file))
            result = score_output(scenario, llm_output, tolerance, baseline, canonical_baselines)
            result["model"] = model_short
            result["model_slug"] = model_slug
            rows.append(result)
            tag = "+" if result["L2b_plus"] else ("✓" if result["L2b"] else ("c" if result["L2a"] else "."))
            est_str = f"{result['estimated']:.3f}" if result['estimated'] is not None else "?"
            true_str = f"{result['baseline_effect']:.3f}" if result['baseline_effect'] is not None else "?"
            print(f"  {sid} {model_short:<8} L2a={result['L2a']} L2b={result['L2b']} "
                  f"L2b+={result['L2b_plus']} [{tag}] est={est_str} true={true_str}", flush=True)

    # Write CSV
    csv_out, json_out = output_paths_for_baseline(baseline)
    if rows:
        with open(csv_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSaved: {csv_out}")

    # Per-model summary
    summary = {}
    for _, model_short in MODELS:
        m_rows = [r for r in rows if r["model"] == model_short]
        if not m_rows:
            continue
        n = len(m_rows)
        summary[model_short] = {
            "n": n,
            "L1": sum(r["L1"] for r in m_rows),
            "L2a": sum(r["L2a"] for r in m_rows),
            "L2b": sum(r["L2b"] for r in m_rows),
            "L2b_plus": sum(r["L2b_plus"] for r in m_rows),
            "L1_rate": round(sum(r["L1"] for r in m_rows)/n, 3),
            "L2a_rate": round(sum(r["L2a"] for r in m_rows)/n, 3),
            "L2b_rate": round(sum(r["L2b"] for r in m_rows)/n, 3),
            "L2b_plus_rate": round(sum(r["L2b_plus"] for r in m_rows)/n, 3),
        }

    by_method = {}
    for method in sorted({r["method"] for r in rows}):
        method_rows = [r for r in rows if r["method"] == method]
        n = len(method_rows)
        by_method[method] = {
            "n": n,
            "L2b": sum(r["L2b"] for r in method_rows),
            "L2b_plus": sum(r["L2b_plus"] for r in method_rows),
            "L2b_rate": round(sum(r["L2b"] for r in method_rows) / n, 3) if n else 0,
            "L2b_plus_rate": round(sum(r["L2b_plus"] for r in method_rows) / n, 3) if n else 0,
        }

    diagnostics = {
        "rows": len(rows),
        "missing_baseline": sum(1 for r in rows if not r["baseline_available"]),
        "executed_without_coefficient": sum(
            1 for r in rows if r["L2b"] and r["estimated"] is None
        ),
        "coefficient_extraction_failure_rate": round(
            sum(1 for r in rows if r["L2b"] and r["estimated"] is None)
            / max(1, sum(r["L2b"] for r in rows)),
            4,
        ),
    }

    json_out.write_text(json.dumps({
        "tolerance": tolerance,
        "baseline": baseline,
        "canonical_baselines_loaded": len(canonical_baselines),
        "diagnostics": diagnostics,
        "by_model": summary,
        "by_method": by_method,
    }, indent=2))
    print(f"Saved: {json_out}")

    # Print summary table
    print("\n" + "=" * 80)
    print(f"L2b+ Summary (tolerance = ±{tolerance*100:.0f}%)")
    print("=" * 80)
    print(f"{'Model':<10} {'L1':>5} {'L2a':>5} {'L2b':>5} {'L2b+':>6}  "
          f"{'L2b%':>6} {'L2b+%':>7}  Δ(L2b - L2b+)")
    print("-" * 80)
    for ms in [m for _, m in MODELS]:
        if ms not in summary:
            continue
        s = summary[ms]
        delta = s["L2b"] - s["L2b_plus"]
        print(f"{ms:<10} {s['L1']:>5}/{s['n']} {s['L2a']:>3}/{s['n']} "
              f"{s['L2b']:>3}/{s['n']} {s['L2b_plus']:>4}/{s['n']}  "
              f"{s['L2b_rate']*100:>5.0f}% {s['L2b_plus_rate']*100:>6.0f}%   "
              f"{delta:>3}/{s['n']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOL,
                        help="Relative error tolerance (default 0.5 = 50%%)")
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--baseline", choices=["dgp", "canonical"], default="dgp",
                        help="Baseline for true effect: dgp (original) or canonical (from dgp_verification.json)")
    args = parser.parse_args()
    run_scoring(args.models, args.tolerance, args.baseline)


if __name__ == "__main__":
    main()
