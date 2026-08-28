"""
Patch: accept NBER working paper + SSRN preprint as valid cross-version
matches for top journal papers.

Rationale: Many economics papers appear as NBER WP or SSRN preprints before
(or concurrent with) journal publication. OpenAlex often returns the WP
version. When our paper JSON says "AER, 2014" and OpenAlex returns
"National Bureau of Economic Research, 2013" for the same authors and
nearly-identical title, that's the SAME paper, just a different version.

This script re-evaluates the existing resolver_results.json with a relaxed
journal gate: if Gate 3 (journal match) fails BUT title Jaccard >= 0.85
AND author overlap is non-empty, promote the match to 'resolved_crossver'.

Input:  audit/resolver_results.json
Output: audit/resolver_results_v2.json + audit/resolver_summary_v2.md
"""

import json
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent

# Journals/sources that are legitimate cross-versions of published papers
CROSS_VERSION_SOURCES = {
    "national bureau of economic research",
    "ssrn electronic journal",
    "ssrn",
    "nber",
    "federal reserve",
    "cepr",
    "iza",
    "econstor",
    "openicpsr",
}


def reevaluate(record: dict) -> dict:
    """Re-check this record with relaxed cross-version rule."""
    if record.get("status") == "resolved":
        return record  # already fine

    checks = record.get("checks") or {}
    # Must have strong title match + author overlap
    title_jac = checks.get("title_jaccard", 0)
    author_overlap = checks.get("author_overlap") or []
    journal_oa = (checks.get("journal_oa") or "").lower()

    if (title_jac >= 0.85
        and author_overlap
        and journal_oa in CROSS_VERSION_SOURCES):
        record = dict(record)
        record["status"] = "resolved_crossver"
        record["notes"] = (record.get("notes", "")
                           + f" [cross-version: OA journal='{journal_oa}' matches "
                             f"working-paper/preprint version of same paper]").strip()
    return record


def main():
    src = PROJECT_ROOT / "audit/resolver_results.json"
    out_json = PROJECT_ROOT / "audit/resolver_results_v2.json"
    out_md = PROJECT_ROOT / "audit/resolver_summary_v2.md"

    data = json.load(open(src))
    results = data["results"]

    promoted = 0
    new_results = []
    for r in results:
        original_status = r.get("status")
        r_new = reevaluate(r)
        if r_new.get("status") != original_status:
            promoted += 1
        new_results.append(r_new)

    # Re-aggregate
    status_counts = Counter(r.get("status") for r in new_results)
    n_total = len(new_results)

    out = {
        "n_total": n_total,
        "summary": dict(status_counts),
        "resolved_pct": round(
            (status_counts.get("resolved", 0) + status_counts.get("resolved_crossver", 0))
            / n_total, 4),
        "promoted_from_weak_match": promoted,
        "cross_version_sources": sorted(CROSS_VERSION_SOURCES),
        "results": new_results,
    }
    with open(out_json, "w") as f:
        json.dump(out, f, indent=2, default=list)

    # Markdown
    lines = [
        "# Strict Resolver — Cross-Version Revised\n",
        f"Re-evaluated {n_total} Exp A papers. {promoted} weak_match entries "
        "were promoted to `resolved_crossver` because OpenAlex returned a "
        "working-paper or preprint version of the same paper (same title + "
        "authors, different source).\n",
        "## Summary\n",
        "| Status | Count | % |",
        "|---|---:|---:|",
    ]
    for status in ["resolved", "resolved_crossver", "weak_match",
                    "ambiguous", "not_found", "error"]:
        c = status_counts.get(status, 0)
        if c > 0:
            lines.append(f"| **{status}** | {c} | {c/n_total:.1%} |")

    total_resolved = status_counts.get("resolved", 0) + status_counts.get("resolved_crossver", 0)
    lines.append(f"\n**Effective resolution rate: {total_resolved}/{n_total} "
                 f"({total_resolved/n_total:.1%})**\n")

    lines.append("## Interpretation\n")
    rate = total_resolved / n_total
    if rate >= 0.90:
        lines.append(f"✅ **{rate:.0%}** — the Exp A dataset metadata is highly reliable.")
    elif rate >= 0.75:
        lines.append(f"⚠️  **{rate:.0%}** — still leaves {n_total - total_resolved} papers "
                     "that warrant manual review.")
    else:
        lines.append(f"🚨 **{rate:.0%}** — significant remaining issues; manual audit needed.")

    with open(out_md, "w") as f:
        f.write("\n".join(lines))

    print(f"Promoted {promoted} weak_match entries to 'resolved_crossver'")
    print(f"Effective resolved rate: {total_resolved}/{n_total} ({total_resolved/n_total:.1%})")
    print(f"\nNew status distribution:")
    for status, c in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status:<22} {c:>4} ({c/n_total:.1%})")
    print(f"\nWrote: {out_json}")
    print(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
