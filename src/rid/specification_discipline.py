"""
RID Layer 2 — Specification Discipline
========================================
Enforces K ≤ 5 specifications and mandates reporting of ALL results,
including null/negative findings. Prevents p-hacking by design.

Usage
-----
    from src.rid.specification_discipline import SpecificationDiscipline

    sd = SpecificationDiscipline(max_specs=5, paper_id="paper_01")

    # Record each attempted specification
    sd.record(
        spec={"controls": "none", "fe": "bank+time", "cluster": "bank"},
        result={"beta": -0.034, "se": 0.012, "t": -2.83, "p": 0.005,
                "n_obs": 4200, "r2": 0.41},
        notes="Main specification"
    )

    # At the end, get the full disclosure report
    report = sd.report()
"""

import json
import os
from datetime import datetime, timezone
from typing import Any


class SpecificationDiscipline:
    MAX_SPECS_HARD_LIMIT = 10  # absolute ceiling even if user raises max_specs

    def __init__(self, max_specs: int = 5, paper_id: str = "unknown",
                 output_dir: str = "experiments"):
        if max_specs > self.MAX_SPECS_HARD_LIMIT:
            raise ValueError(f"max_specs cannot exceed {self.MAX_SPECS_HARD_LIMIT}")
        self.max_specs = max_specs
        self.paper_id = paper_id
        self.output_dir = output_dir
        self._specs: list = []
        self._created_at = datetime.now(timezone.utc).isoformat()
        os.makedirs(output_dir, exist_ok=True)

    # ── Recording ────────────────────────────────────────────────────

    def record(self, spec: dict, result: dict, notes: str = "") -> int:
        """
        Record one specification attempt and its result.
        Raises if K > max_specs.

        Returns the 1-based index of this specification.
        """
        if len(self._specs) >= self.max_specs:
            raise RuntimeError(
                f"[RID] Specification limit reached (K={self.max_specs}). "
                "Cannot attempt additional specifications. "
                "This limit prevents p-hacking."
            )

        entry = {
            "k": len(self._specs) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spec": spec,
            "result": result,
            "notes": notes,
            "significant_5pct": self._is_significant(result, 0.05),
            "significant_10pct": self._is_significant(result, 0.10),
        }
        self._specs.append(entry)

        sig = "p<0.05" if entry["significant_5pct"] else \
              ("p<0.10" if entry["significant_10pct"] else "n.s.")
        print(f"[RID] Spec {entry['k']}/{self.max_specs} recorded  "
              f"beta={result.get('beta', '?')}  {sig}")
        return entry["k"]

    @staticmethod
    def _is_significant(result: dict, alpha: float) -> bool:
        p = result.get("p")
        t = result.get("t")
        if p is not None:
            return float(p) < alpha
        if t is not None:
            return abs(float(t)) > (1.96 if alpha == 0.05 else 1.645)
        return False

    # ── Reporting ────────────────────────────────────────────────────

    def report(self, save: bool = True) -> dict:
        """
        Generate the full-disclosure report.
        MUST be called even if not all specs were used.
        """
        n_sig_5 = sum(s["significant_5pct"] for s in self._specs)
        n_sig_10 = sum(s["significant_10pct"] for s in self._specs)

        # Inflation check: if ALL specs reported as significant, flag it
        cherry_picking_flag = (
            len(self._specs) > 1 and n_sig_5 == len(self._specs)
        )

        # Effect range (beta)
        betas = [s["result"].get("beta") for s in self._specs
                 if s["result"].get("beta") is not None]
        beta_range = (min(betas), max(betas)) if betas else None

        report = {
            "paper_id": self.paper_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_specs_attempted": len(self._specs),
            "n_specs_allowed": self.max_specs,
            "n_significant_5pct": n_sig_5,
            "n_significant_10pct": n_sig_10,
            "cherry_picking_flag": cherry_picking_flag,
            "beta_range": beta_range,
            "specifications": self._specs,
            "disclosure_note": (
                "All specification attempts are reported, including null results, "
                "per RID specification discipline protocol."
            ),
        }

        if save:
            fname = os.path.join(
                self.output_dir,
                f"spec_report_{self.paper_id}.json"
            )
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"[RID] Spec report saved to {fname}")

        if cherry_picking_flag:
            print(f"[RID] WARNING: All {len(self._specs)} specs significant — "
                  "possible cherry-picking. Review before reporting.")

        return report

    @property
    def n_attempted(self) -> int:
        return len(self._specs)

    @property
    def remaining(self) -> int:
        return self.max_specs - len(self._specs)
