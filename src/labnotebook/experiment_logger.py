"""
ExperimentLogger — a lightweight "lab notebook" helper for CausalVerify.

Usage in any script:

    from src.logging.experiment_logger import ExperimentLogger

    exp = ExperimentLogger(
        run_name="gt_reextract_multi_llm",
        script_path=__file__,
        hypothesis=(
            "4 independent LLMs reading the same abstract will agree on "
            "method_family for ≥75% of papers; disagreements concentrate "
            "in EVENT_STUDY vs DID boundary cases."
        ),
        config={
            "models":       ["opus-4-7", "gpt-4o", "kimi-latest", "gemini-2.5-flash"],
            "prompt_id":    "gt_extract_strict__v2",
            "n_papers":     262,
            "max_tokens":   300,
        },
    )

    # Use throughout the run
    exp.log_prompt("system", SYSTEM_PROMPT)
    exp.log_event("start_paper", paper_id="paper_01")
    exp.log_llm_call(model="opus-4-7", input_tokens=1500, output_tokens=80,
                     response_summary="method=DID direction=negative")
    exp.log_event("finish_paper", paper_id="paper_01", outcome="success")

    # At the end
    exp.finish(
        status="success",
        results={
            "all4_agree": 103, "3of4_agree": 93, "2of4_tie": 63, "split": 3,
        },
        interpretation=(
            "Method-family agreement 74% hit ≥3-of-4, slightly below hypothesis. "
            "Direction agreement only 30% hit ≥3-of-4, MUCH worse than expected — "
            "this itself is a new finding (F4 extension)."
        ),
    )

Each run produces:
    experiments_log/runs/YYYY-MM-DD/NNN__<run_name>/
        config.json, prompt_used.txt, events.jsonl, summary.md
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).parent.parent.parent   # v11/
LOG_ROOT = ROOT / "experiments_log"


def _git_commit() -> str:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "no_git"
    except Exception:
        return "no_git"


def _next_run_slot(date_dir: Path) -> int:
    date_dir.mkdir(parents=True, exist_ok=True)
    existing = [p.name for p in date_dir.iterdir() if p.is_dir()]
    nums = [int(n.split("__")[0]) for n in existing
             if n.split("__")[0].isdigit()]
    return (max(nums) + 1) if nums else 1


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


class ExperimentLogger:
    def __init__(self,
                 run_name: str,
                 script_path: str,
                 hypothesis: str = "",
                 config: Optional[Dict[str, Any]] = None):
        self.run_name = run_name
        self.script_name = Path(script_path).name
        self.config = config or {}
        self.hypothesis = hypothesis
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.git_commit = _git_commit()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir = LOG_ROOT / "runs" / today
        slot = _next_run_slot(date_dir)
        self.run_dir = date_dir / f"{slot:03d}__{run_name}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.events: List[Dict[str, Any]] = []
        self.prompts: Dict[str, Dict[str, str]] = {}   # {prompt_role: {text, hash}}
        self.llm_calls: List[Dict[str, Any]] = []

        # Write initial config.json
        self._write_config()
        print(f"[ExperimentLogger] started: {self.run_dir.relative_to(ROOT)}")

    def _write_config(self):
        (self.run_dir / "config.json").write_text(json.dumps({
            "run_name":    self.run_name,
            "script":      self.script_name,
            "started_at":  self.started_at,
            "git_commit":  self.git_commit,
            "hypothesis":  self.hypothesis,
            "config":      self.config,
        }, indent=2, ensure_ascii=False))

    def log_prompt(self, role: str, text: str):
        """Record a prompt template used (system/user/etc.)."""
        h = _sha256_text(text)
        self.prompts[role] = {"text": text, "hash": h}
        # Write to run dir immediately
        (self.run_dir / f"prompt_{role}.txt").write_text(text)
        # Also register in the prompts/ registry (idempotent)
        self._register_prompt(role, text, h)
        self.events.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "prompt_registered",
            "role": role, "hash": h, "length": len(text),
        })
        self._flush_events()

    def _register_prompt(self, role: str, text: str, h: str):
        registry_dir = LOG_ROOT / "prompts"
        registry_dir.mkdir(parents=True, exist_ok=True)
        idx_file = registry_dir / "REGISTRY.md"
        prompt_id = f"{self.run_name}__{role}__{h}"
        prompt_file = registry_dir / f"{prompt_id}.txt"
        if prompt_file.exists():
            return   # already registered, idempotent
        prompt_file.write_text(text)
        # Append to registry table
        header_needed = not idx_file.exists()
        with open(idx_file, "a") as f:
            if header_needed:
                f.write("# Prompt Registry\n\n")
                f.write("| Prompt ID | Role | SHA256-short | First used run |\n")
                f.write("|---|---|---|---|\n")
            f.write(f"| `{prompt_id}` | {role} | `{h}` | "
                    f"`{self.run_name}` @ {self.started_at[:10]} |\n")

    def log_event(self, event_type: str, **kwargs):
        self.events.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **kwargs,
        })
        if len(self.events) % 10 == 0:
            self._flush_events()

    def log_llm_call(self, model: str,
                     input_tokens: int = 0,
                     output_tokens: int = 0,
                     response_summary: str = "",
                     cost_usd: Optional[float] = None,
                     **extra):
        call = {
            "ts":               datetime.now(timezone.utc).isoformat(),
            "model":            model,
            "input_tokens":     input_tokens,
            "output_tokens":    output_tokens,
            "response_summary": response_summary[:400],
            "cost_usd":         cost_usd,
            **extra,
        }
        self.llm_calls.append(call)
        self.events.append({"type": "llm_call",
                            "ts":   call["ts"],
                            "model": model,
                            "in":   input_tokens, "out": output_tokens})
        if len(self.llm_calls) % 5 == 0:
            self._flush_llm_calls()

    def _flush_events(self):
        path = self.run_dir / "events.jsonl"
        with open(path, "w") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def _flush_llm_calls(self):
        (self.run_dir / "llm_calls.jsonl").write_text(
            "\n".join(json.dumps(c, ensure_ascii=False)
                      for c in self.llm_calls) + "\n"
        )

    def attach_output(self, name: str, path):
        """Record that a file was produced by this run."""
        p = Path(path)
        self.events.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "output_attached",
            "name": name,
            "relative_path": str(p.relative_to(ROOT)) if p.is_absolute() else str(p),
            "size_bytes": p.stat().st_size if p.exists() else 0,
        })

    def finish(self,
               status: str = "success",
               results: Optional[Dict[str, Any]] = None,
               interpretation: str = ""):
        finished_at = datetime.now(timezone.utc).isoformat()
        self._flush_events()
        self._flush_llm_calls()

        # Compute aggregate stats
        total_in  = sum(c.get("input_tokens", 0)  for c in self.llm_calls)
        total_out = sum(c.get("output_tokens", 0) for c in self.llm_calls)
        total_cost = sum((c.get("cost_usd") or 0) for c in self.llm_calls)

        outputs = [e for e in self.events if e.get("type") == "output_attached"]

        # Write summary.md
        md = [
            f"# Run: {self.run_name}",
            "",
            f"- **Status**: {status}",
            f"- **Started**: {self.started_at}",
            f"- **Finished**: {finished_at}",
            f"- **Git commit**: `{self.git_commit}`",
            f"- **Script**: `{self.script_name}`",
            f"- **Run dir**: `{self.run_dir.relative_to(ROOT)}`",
            "",
            "## Hypothesis",
            "",
            self.hypothesis or "_(not pre-registered)_",
            "",
            "## Configuration",
            "```json",
            json.dumps(self.config, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
        if self.prompts:
            md.append("## Prompts used")
            md.append("")
            for role, info in self.prompts.items():
                md.append(f"- **{role}**: hash=`{info['hash']}` "
                          f"(length {len(info['text'])} chars) — see `prompt_{role}.txt`")
            md.append("")

        md += [
            "## LLM usage",
            "",
            f"- Total calls: {len(self.llm_calls)}",
            f"- Total input tokens: {total_in:,}",
            f"- Total output tokens: {total_out:,}",
            f"- Total cost (if provided): ${total_cost:.2f}",
            "",
            "## Outputs",
            "",
        ]
        for o in outputs:
            md.append(f"- `{o['relative_path']}` ({o['size_bytes']:,} bytes)")
        if not outputs: md.append("_(none attached)_")

        md += [
            "",
            "## Results",
            "```json",
            json.dumps(results or {}, indent=2, ensure_ascii=False),
            "```",
            "",
            "## Interpretation",
            "",
            interpretation or "_(add your reading of the results here)_",
        ]
        (self.run_dir / "summary.md").write_text("\n".join(md) + "\n")

        # Update runs/INDEX.md
        self._update_index(status, results or {}, finished_at)

        print(f"[ExperimentLogger] finished: {self.run_dir.relative_to(ROOT)} "
              f"(status={status}, tokens={total_in}+{total_out})")

    def _update_index(self, status: str, results: Dict[str, Any],
                      finished_at: str):
        idx = LOG_ROOT / "runs" / "INDEX.md"
        header_needed = not idx.exists()
        with open(idx, "a") as f:
            if header_needed:
                f.write("# Run Index\n\n")
                f.write("| Date | Run | Status | Commit | Key result |\n")
                f.write("|---|---|---|---|---|\n")
            key = list(results.items())[:1]
            key_str = f"{key[0][0]}={key[0][1]}" if key else "—"
            f.write(f"| {self.started_at[:10]} | "
                    f"[{self.run_dir.name}]({self.run_dir.relative_to(LOG_ROOT)}) | "
                    f"{status} | `{self.git_commit}` | {key_str} |\n")
