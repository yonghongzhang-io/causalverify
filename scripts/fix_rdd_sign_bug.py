"""
Fix: RDD sign-reversal bug (Issue C1 from Stage 0 Audit)
=========================================================

Background
----------
In extend_exp_b_to_100.py:267, `effect=abs(params["effect"])` strips the
sign before passing to make_rdd(). The synthetic data is generated with
|effect| (positive), but the scenario JSON records the original signed
effect (possibly negative). This creates a contradiction: the DGP_truth
JSON disagrees with the actual data.

Affected scenarios (all from extend_exp_b_to_100.py rdd_effects list
at negative indices 1,3,5,7,9,12,14):
    s86: true=-0.20 (data has +0.20)
    s88: true=-0.15 (data has +0.15)
    s90: true=-0.25 (data has +0.25)
    s92: true=-0.30 (data has +0.30)
    s94: true=-0.22 (data has +0.22)
    s97: true=-0.18 (data has +0.18)
    s99: true=-0.25 (data has +0.25)

Fix strategy
------------
Update the JSON ground truth to match the actual data (positive).
This is the honest fix: the data is what was actually generated;
the JSON metadata needs to reflect that.

We do NOT regenerate the CSVs — the data is correct. We do NOT
re-run LLMs — their outputs were generated against the correct data.
We only fix the JSON ground-truth to match what the DGP actually did.

Usage
-----
    python3 scripts/fix_rdd_sign_bug.py               # apply fix
    python3 scripts/fix_rdd_sign_bug.py --dry-run     # preview only
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).parent.parent
SCEN_DIR = PROJECT_ROOT / "experiments/exp_b/scenarios"

# Scenarios with sign-reversal bug
AFFECTED = ["s86", "s88", "s90", "s92", "s94", "s97", "s99"]

# ISO timestamp for the audit note
NOW = datetime.now(timezone.utc).isoformat()


def fix_scenario(sid: str, dry_run: bool) -> dict:
    path = SCEN_DIR / f"{sid}.json"
    if not path.exists():
        return {"scenario_id": sid, "status": "missing"}

    d = json.load(open(path))
    dgp = d.get("dgp_truth", {})
    old_effect = dgp.get("effect")
    old_direction = dgp.get("direction", "")
    old_gt_direction = d.get("ground_truth", {}).get("conclusion_direction", "")

    if old_effect is None:
        return {"scenario_id": sid, "status": "no_effect_field"}

    if old_effect >= 0:
        # Already positive, no fix needed
        return {"scenario_id": sid, "status": "no_change_needed", "effect": old_effect}

    new_effect = abs(old_effect)
    new_direction = "positive"

    record = {
        "scenario_id": sid,
        "status": "would_fix" if dry_run else "fixed",
        "old_effect": old_effect,
        "new_effect": new_effect,
        "old_direction": old_direction,
        "new_direction": new_direction,
        "old_gt_direction": old_gt_direction,
    }

    if dry_run:
        return record

    # Apply fix
    d["dgp_truth"]["effect"] = new_effect
    d["dgp_truth"]["direction"] = new_direction
    if "ground_truth" in d:
        d["ground_truth"]["conclusion_direction"] = new_direction

    # Audit trail
    d["_fix_notes"] = d.get("_fix_notes", [])
    d["_fix_notes"].append({
        "fix_id": "issue_C1_rdd_sign_reversal",
        "applied_at": NOW,
        "description": (
            "Ground-truth effect and direction corrected to match actual "
            "data. Root cause: extend_exp_b_to_100.py:267 applied abs() "
            "before passing effect to make_rdd(), so the synthetic CSV "
            "has positive effect while the JSON recorded the original "
            "signed value. Data file unchanged; only JSON metadata updated."
        ),
        "before": {"dgp_truth.effect": old_effect,
                   "dgp_truth.direction": old_direction,
                   "ground_truth.conclusion_direction": old_gt_direction},
        "after": {"dgp_truth.effect": new_effect,
                  "dgp_truth.direction": new_direction,
                  "ground_truth.conclusion_direction": new_direction},
    })

    with open(path, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing files")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "APPLYING FIX"
    print(f"[{mode}] Fixing RDD sign-reversal bug in {len(AFFECTED)} scenarios:\n")

    results = []
    for sid in AFFECTED:
        r = fix_scenario(sid, args.dry_run)
        results.append(r)
        if r["status"] in ("would_fix", "fixed"):
            print(f"  {sid}: effect {r['old_effect']:+.3f} → {r['new_effect']:+.3f}, "
                  f"direction '{r['old_direction']}' → '{r['new_direction']}'")
        else:
            print(f"  {sid}: {r['status']}")

    print()
    n_fixed = sum(1 for r in results if r["status"] in ("would_fix", "fixed"))
    print(f"{'Would fix' if args.dry_run else 'Fixed'}: {n_fixed}/{len(AFFECTED)} scenarios")

    if not args.dry_run:
        print()
        print("Next steps:")
        print("  1. Re-run DGP Verifier to confirm the 7 scenarios now VERIFY:")
        print("       python3 src/agents/dgp_verifier.py")
        print("  2. Re-run L2b+ scoring against corrected ground truth:")
        print("       python3 src/pipeline/score_l2b_plus.py")
        print("  3. Regenerate Figures 2-5 using updated scores.")


if __name__ == "__main__":
    main()
