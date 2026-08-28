"""
P1-2 Leakage Scanner
====================

Purpose
-------
Detect whether research_question / data_description in Exp B scenario JSONs
accidentally leak the method family name (DID / event study / IV / RDD).

Why it matters
--------------
The prompt to GPT-4o that generated s31–s100 said:
  "Do NOT mention the method family name in research_question or
   data_description."

But GPT-4o @ temperature=0.4 is not guaranteed to follow. If a scenario
leaks its method name in the prompt, the L3 (method identification) result
for that scenario is inflated — the model didn't "identify" the method,
it just echoed the leak.

This scanner performs three levels of detection:
  1. Literal keyword match (e.g., "difference-in-differences")
  2. Strong abbreviation match (e.g., "DID", "RDD", "2SLS")
  3. Structural hint match (e.g., "instrumental variable", "running variable")

Output
------
v11/audit/leakage_scan.json  — per-scenario findings
v11/audit/leakage_scan_summary.md — human-readable summary

Usage
-----
  python3 src/agents/leakage_scanner.py
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCEN_DIR = PROJECT_ROOT / "experiments/exp_b/scenarios"
OUT_JSON = PROJECT_ROOT / "audit/leakage_scan.json"
OUT_MD = PROJECT_ROOT / "audit/leakage_scan_summary.md"


# ── Leakage patterns ─────────────────────────────────────────────────
# Organized by severity:
#   'critical': the method name itself (most obvious leak)
#   'strong':   abbreviations / tight synonyms
#   'weak':     structural hints that almost always imply the method

METHOD_PATTERNS = {
    "DID": {
        "critical": [
            r"\bdifference[- ]in[- ]differences?\b",
            r"\bdiff[- ]in[- ]diff\b",
            r"\bdid\s+estimator\b",
            r"\bdid\s+design\b",
            r"\bdid\s+method\b",
        ],
        "strong": [
            r"\btwo[- ]way\s+fixed\s+effects?\b",
            r"\btwfe\b",
            r"\bcallaway[- ]sant['’]anna\b",
            r"\bsun[- ]abraham\b",
            r"\bgoodman[- ]bacon\b",
        ],
        "weak": [
            r"\bparallel\s+trends?\b",
            r"\bpre[- ]treatment\s+period\b",
            r"\bpost[- ]treatment\s+period\b",
        ],
    },
    "EVENT_STUDY": {
        "critical": [
            r"\bevent[- ]study\b",
            r"\bevent\s+study\s+design\b",
        ],
        "strong": [
            r"\bmarket\s+model\b",
            r"\bcumulative\s+abnormal\s+returns?\b",
            r"\bCAR\s*\[",
            r"\bcar\s+window\b",
        ],
        "weak": [
            r"\bannouncement\s+effect\b",
            r"\babnormal\s+returns?\b",
            r"\bestimation\s+window\b",
        ],
    },
    "IV": {
        "critical": [
            r"\binstrumental\s+variable\b",
            r"\biv\s+approach\b",
            r"\biv\s+estimat\w+",
            r"\biv\s+strategy\b",
        ],
        "strong": [
            r"\b2sls\b",
            r"\btwo[- ]stage\s+least\s+squares\b",
            r"\bfirst[- ]stage\b",
            r"\bexclusion\s+restriction\b",
        ],
        "weak": [
            r"\binstrument\s+for\b",
            r"\bas\s+an\s+instrument\b",
            r"\bendogeneity\b",
        ],
    },
    "RDD": {
        "critical": [
            r"\bregression\s+discontinuity\b",
            r"\brdd\s+design\b",
            r"\brd\s+design\b",
        ],
        "strong": [
            r"\brdrobust\b",
            r"\bsharp\s+rdd?\b",
            r"\bfuzzy\s+rdd?\b",
            r"\bmccrary\s+density\b",
        ],
        "weak": [
            r"\brunning\s+variable\b",
            r"\bforcing\s+variable\b",
            r"\bat\s+the\s+cutoff\b",
        ],
    },
}


@dataclass
class LeakageFinding:
    scenario_id: str
    method_family: str   # ground-truth method (what leakage scanner is checking against)
    leaked_methods: list  # ordered list of (method, severity, pattern, match_snippet)
    has_critical_leak: bool
    has_any_leak: bool
    scanned_text_chars: int
    research_question_len: int
    data_description_len: int
    notes: list = field(default_factory=list)


def scan_text(text: str) -> list:
    """Return list of (method, severity, pattern, match_snippet) tuples."""
    text_lower = text.lower()
    findings = []
    for method, severity_groups in METHOD_PATTERNS.items():
        for severity, patterns in severity_groups.items():
            for pat in patterns:
                for m in re.finditer(pat, text_lower, re.IGNORECASE):
                    snippet = text_lower[max(0, m.start()-30): m.end()+30]
                    findings.append((method, severity, pat, snippet))
    return findings


def scan_scenario(scenario_path: Path) -> LeakageFinding:
    with open(scenario_path) as f:
        scen = json.load(f)

    sid = scen["scenario_id"]
    method = scen["method_family"]
    rq = scen.get("research_question", "")
    dd = scen.get("data_description", "")
    title = scen.get("title", "")

    # Combine all text given to the LLM (title + research question + data description)
    full_text = f"{title}\n\n{rq}\n\n{dd}"
    findings = scan_text(full_text)

    # Only count leaks for the CORRECT method (self-leak is the issue;
    # mentioning a different method is not a "leak" of this scenario's answer)
    self_leaks = [f for f in findings if f[0] == method]

    critical = any(sev == "critical" for _, sev, _, _ in self_leaks)

    return LeakageFinding(
        scenario_id=sid,
        method_family=method,
        leaked_methods=[{
            "method": m,
            "severity": sev,
            "pattern": pat,
            "snippet": snip,
        } for m, sev, pat, snip in findings],  # keep ALL findings (self + cross)
        has_critical_leak=critical,
        has_any_leak=bool(self_leaks),
        scanned_text_chars=len(full_text),
        research_question_len=len(rq),
        data_description_len=len(dd),
    )


def main():
    scenarios = sorted(
        SCEN_DIR.glob("s*.json"),
        key=lambda p: int(p.stem[1:])
    )
    print(f"Scanning {len(scenarios)} scenarios for method-name leakage...\n")

    all_findings = []
    for scen_path in scenarios:
        f = scan_scenario(scen_path)
        all_findings.append(f)
        if f.has_critical_leak:
            print(f"  [CRITICAL] {f.scenario_id} ({f.method_family}): "
                  f"self-leaks {sum(1 for x in f.leaked_methods if x['method']==f.method_family and x['severity']=='critical')}"
                  f" critical patterns")
        elif f.has_any_leak:
            print(f"  [weak]     {f.scenario_id} ({f.method_family}): "
                  f"self-leaks {sum(1 for x in f.leaked_methods if x['method']==f.method_family)} patterns")

    # Aggregates
    n_total = len(all_findings)
    n_critical = sum(1 for f in all_findings if f.has_critical_leak)
    n_any = sum(1 for f in all_findings if f.has_any_leak)

    per_method = Counter()
    per_method_critical = Counter()
    for f in all_findings:
        if f.has_any_leak:
            per_method[f.method_family] += 1
        if f.has_critical_leak:
            per_method_critical[f.method_family] += 1

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump({
            "summary": {
                "total_scenarios": n_total,
                "scenarios_with_critical_leak": n_critical,
                "scenarios_with_any_leak": n_any,
                "per_method_critical": dict(per_method_critical),
                "per_method_any": dict(per_method),
            },
            "findings": [asdict(f) for f in all_findings],
        }, f, indent=2)

    # Write markdown summary
    lines = []
    lines.append("# Leakage Scan Summary\n")
    lines.append(f"Scanned: {n_total} scenarios\n")
    lines.append("## Aggregate\n")
    lines.append(f"- Critical leaks (method name literally appears): **{n_critical}/{n_total}** "
                 f"({n_critical/n_total:.1%})")
    lines.append(f"- Any leaks (incl. weak structural hints): **{n_any}/{n_total}** "
                 f"({n_any/n_total:.1%})\n")

    lines.append("## Per-method critical leak rates\n")
    lines.append("| Method | Critical Leaks | Any Leaks |")
    lines.append("|---|---:|---:|")
    for method in ["DID", "EVENT_STUDY", "IV", "RDD"]:
        crit = per_method_critical.get(method, 0)
        anyl = per_method.get(method, 0)
        method_total = sum(1 for f in all_findings if f.method_family == method)
        lines.append(f"| {method} | {crit}/{method_total} ({crit/max(method_total,1):.0%}) | "
                     f"{anyl}/{method_total} ({anyl/max(method_total,1):.0%}) |")

    if n_critical:
        lines.append("\n## Scenarios with Critical Leaks (need manual review)\n")
        for f in all_findings:
            if f.has_critical_leak:
                own_critical = [x for x in f.leaked_methods
                                if x["method"] == f.method_family and x["severity"] == "critical"]
                lines.append(f"\n### {f.scenario_id} ({f.method_family})")
                for leak in own_critical:
                    lines.append(f"- Pattern: `{leak['pattern']}`")
                    lines.append(f"  Snippet: `...{leak['snippet'].strip()}...`")

    lines.append("\n## Interpretation\n")
    if n_critical == 0:
        lines.append("✅ **No critical leaks detected.** Scenario prompts do not literally "
                     "name their own method family.")
    elif n_critical / n_total < 0.05:
        lines.append(f"⚠️  **{n_critical} scenarios have critical leaks ({n_critical/n_total:.1%}).** "
                     f"These scenarios should be manually reviewed and either rewritten or "
                     f"excluded from L3 evaluation.")
    else:
        lines.append(f"🚨 **{n_critical} scenarios have critical leaks ({n_critical/n_total:.1%}).** "
                     f"This is a systematic problem. All L3 results on Exp B must be re-evaluated "
                     f"after cleaning the scenarios.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote: {OUT_JSON}")
    print(f"Wrote: {OUT_MD}")
    print(f"\nSummary: {n_critical}/{n_total} critical leaks, {n_any}/{n_total} any leaks")


if __name__ == "__main__":
    main()
