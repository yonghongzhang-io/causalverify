"""
RID Layer 3 — Falsification Gates
===================================
Method-specific validity checks that must PASS before a result
can be reported. A failing gate triggers a mandatory warning and
records the failure in the audit log.

Gates by method family
-----------------------
DID         : Parallel pre-trends (F-test + visual)
Event Study : Placebo event date (AR not significant on fake date)
IV          : First-stage F-statistic > 10 (Stock & Yogo 2005)
RDD         : McCrary density test (no sorting at cutoff)

Usage
-----
    from src.rid.falsification_gates import FalsificationGates

    gates = FalsificationGates(paper_id="paper_01", method="DID")

    passed = gates.check_parallel_trends(
        pre_coefs=[
            {"period": "t-3", "beta": 0.002, "se": 0.008},
            {"period": "t-2", "beta": -0.003, "se": 0.007},
            {"period": "t-1", "beta": 0.001, "se": 0.009},
        ]
    )
    gates.save_log()
"""

import json
import os
from datetime import datetime, timezone
import numpy as np
from scipy import stats


class FalsificationGates:
    T_THRESHOLD    = 1.96   # 5% two-sided
    F_IV_MIN       = 10.0   # Stock & Yogo (2005)
    MCCRARY_ALPHA  = 0.05   # RDD density test

    def __init__(self, paper_id: str = "unknown", method: str = "DID",
                 output_dir: str = "experiments"):
        self.paper_id = paper_id
        self.method = method.upper()
        self.output_dir = output_dir
        self._log: list = []
        os.makedirs(output_dir, exist_ok=True)

    # ── DID: Parallel pre-trends ─────────────────────────────────────

    def check_parallel_trends(self, pre_coefs: list) -> bool:
        """
        Test that pre-treatment coefficients are jointly insignificant.

        pre_coefs : list of dicts with keys "period", "beta", "se"
                    (or "t" instead of beta+se)
        Returns   : True if parallel trends assumption holds
        """
        t_stats = []
        for c in pre_coefs:
            if "t" in c:
                t_stats.append(float(c["t"]))
            elif "beta" in c and "se" in c and float(c["se"]) > 0:
                t_stats.append(float(c["beta"]) / float(c["se"]))

        if not t_stats:
            return self._record("parallel_trends", False,
                                "No pre-treatment coefficients provided")

        # Individual check: none should be significant
        any_sig = any(abs(t) > self.T_THRESHOLD for t in t_stats)

        # Joint F-test (approximate: mean of squared t-stats ~ F/k)
        n = len(t_stats)
        f_approx = np.mean(np.array(t_stats) ** 2)
        p_joint = 1 - stats.f.cdf(f_approx, dfn=n, dfd=max(n * 10, 100))

        passed = not any_sig and (p_joint > 0.10)
        detail = (f"n_periods={n}, max|t|={max(abs(t) for t in t_stats):.3f}, "
                  f"F_approx={f_approx:.3f}, p_joint={p_joint:.3f}")
        return self._record("parallel_trends", passed, detail)

    # ── Event Study: Placebo date ─────────────────────────────────────

    def check_placebo_event(self, placebo_car: float, placebo_t: float) -> bool:
        """
        Verify that a placebo event date produces no significant abnormal returns.
        placebo_car : cumulative abnormal return on placebo date
        placebo_t   : t-statistic for that CAR
        """
        passed = abs(placebo_t) < self.T_THRESHOLD
        detail = f"placebo_CAR={placebo_car:.4f}, placebo_t={placebo_t:.3f}"
        return self._record("placebo_event", passed, detail)

    # ── IV: First-stage F-statistic ───────────────────────────────────

    def check_first_stage_f(self, f_stat: float, n_instruments: int = 1) -> bool:
        """
        Stock & Yogo (2005): F > 10 for single instrument.
        For multiple instruments, threshold scales up.
        """
        threshold = self.F_IV_MIN * max(1.0, n_instruments ** 0.5)
        passed = f_stat > threshold
        detail = (f"F={f_stat:.2f}, threshold={threshold:.1f}, "
                  f"n_instruments={n_instruments}")
        return self._record("first_stage_f", passed, detail)

    # ── RDD: McCrary density test ─────────────────────────────────────

    def check_rdd_density(self, mccrary_t: float, mccrary_p: float) -> bool:
        """
        No sorting at the cutoff: density should be continuous.
        Passes when McCrary test is NOT significant (p > alpha).
        """
        passed = mccrary_p > self.MCCRARY_ALPHA
        detail = f"McCrary t={mccrary_t:.3f}, p={mccrary_p:.3f}"
        return self._record("rdd_density", passed, detail)

    # ── Generic override (with justification) ────────────────────────

    def override(self, gate_name: str, justification: str) -> bool:
        """
        Override a failing gate with explicit written justification.
        Records the override in the audit log (visible to raters).
        """
        print(f"[RID] OVERRIDE: {gate_name} — {justification}")
        return self._record(gate_name, True,
                            f"OVERRIDE: {justification}", is_override=True)

    # ── Internals ────────────────────────────────────────────────────

    def _record(self, gate: str, passed: bool, detail: str,
                is_override: bool = False) -> bool:
        entry = {
            "gate": gate,
            "passed": passed,
            "is_override": is_override,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._log.append(entry)
        status = "PASS" if passed else "FAIL"
        override_note = " [OVERRIDE]" if is_override else ""
        print(f"[RID] Gate {gate}: {status}{override_note}  — {detail}")
        return passed

    def all_passed(self) -> bool:
        """True if every recorded gate passed (or was overridden)."""
        return all(e["passed"] for e in self._log)

    def save_log(self) -> str:
        record = {
            "paper_id": self.paper_id,
            "method": self.method,
            "all_passed": self.all_passed(),
            "n_gates": len(self._log),
            "n_failed": sum(not e["passed"] for e in self._log),
            "gates": self._log,
        }
        fname = os.path.join(self.output_dir, f"gates_{self.paper_id}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        print(f"[RID] Gate log saved to {fname}")
        return fname

    @property
    def log(self) -> list:
        return list(self._log)
