"""
RID Layer 1 — Pre-commitment
=============================
Locks a research plan before data access via a SHA-256 hash.
The hash acts as an immutable timestamp: any change to the plan
after locking produces a different hash, making HARKing detectable.

Usage
-----
    from src.rid.precommitment import PrecommitmentLock

    lock = PrecommitmentLock(output_dir="experiments/exp_a/rid_plans")
    plan = {
        "paper_id": "paper_01",
        "hypothesis": "Basel III reduces bank lending growth",
        "identification": "DID — staggered implementation by country",
        "outcome": "loan growth (quarterly)",
        "treatment": "banks in Basel III adopting countries",
        "control": "banks in non-adopting countries",
        "allowed_specifications": [
            {"controls": "none", "fe": "bank+time"},
            {"controls": "size+capital", "fe": "bank+time"},
            {"controls": "size+capital+macro", "fe": "bank+time"},
        ],
        "falsification_plan": "placebo_dates",
    }
    plan_hash = lock.lock(plan)
    print(f"Plan locked: {plan_hash}")
"""

import hashlib
import json
import os
from datetime import datetime, timezone


class PrecommitmentLock:

    def __init__(self, output_dir: str = "experiments"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._locked_plan: dict = None
        self._hash: str = None
        self._locked_at: str = None

    # ── Core ────────────────────────────────────────────────────────

    def lock(self, research_plan: dict) -> str:
        """
        Hash and persist a research plan. Must be called BEFORE data access.
        Returns the SHA-256 hex digest (first 16 chars used as plan ID).
        """
        if self._hash is not None:
            raise RuntimeError(
                f"A plan is already locked (hash={self._hash[:12]}). "
                "Create a new PrecommitmentLock instance for a new study."
            )

        canonical = json.dumps(research_plan, sort_keys=True, ensure_ascii=False)
        full_hash = hashlib.sha256(canonical.encode()).hexdigest()

        self._locked_plan = research_plan
        self._hash = full_hash
        self._locked_at = datetime.now(timezone.utc).isoformat()

        record = {
            "hash": full_hash,
            "locked_at": self._locked_at,
            "plan": research_plan,
        }

        fname = os.path.join(self.output_dir, f"plan_{full_hash[:12]}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

        print(f"[RID] Plan locked  hash={full_hash[:12]}  at={self._locked_at}")
        print(f"[RID] Saved to     {fname}")
        return full_hash

    def verify(self, plan_hash: str = None) -> bool:
        """
        Confirm the locked plan has not changed since locking.
        Optionally cross-check against an external hash.
        """
        if self._hash is None:
            raise RuntimeError("No plan has been locked yet.")
        canonical = json.dumps(self._locked_plan, sort_keys=True, ensure_ascii=False)
        current_hash = hashlib.sha256(canonical.encode()).hexdigest()
        integrity_ok = current_hash == self._hash
        if plan_hash:
            integrity_ok = integrity_ok and (current_hash == plan_hash)
        return integrity_ok

    def get_allowed_specifications(self) -> list:
        if self._locked_plan is None:
            raise RuntimeError("No plan locked.")
        return self._locked_plan.get("allowed_specifications", [])

    @property
    def hash(self) -> str:
        return self._hash

    @property
    def plan(self) -> dict:
        return self._locked_plan

    # ── Load from file ───────────────────────────────────────────────

    @classmethod
    def load(cls, plan_file: str) -> "PrecommitmentLock":
        """Reload a previously saved plan from its JSON file."""
        with open(plan_file, encoding="utf-8") as f:
            record = json.load(f)

        instance = cls.__new__(cls)
        instance.output_dir = os.path.dirname(plan_file)
        instance._locked_plan = record["plan"]
        instance._hash = record["hash"]
        instance._locked_at = record["locked_at"]

        # Verify integrity
        canonical = json.dumps(record["plan"], sort_keys=True, ensure_ascii=False)
        recomputed = hashlib.sha256(canonical.encode()).hexdigest()
        if recomputed != record["hash"]:
            raise ValueError(
                f"INTEGRITY VIOLATION: plan file {plan_file} has been tampered with."
            )
        print(f"[RID] Plan loaded  hash={record['hash'][:12]}  integrity=OK")
        return instance
