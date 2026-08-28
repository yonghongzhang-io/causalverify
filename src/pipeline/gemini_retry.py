"""
Gemini-specific retry runner with exponential backoff for 503 errors.
Targets only the missing papers and retries each up to N times.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

PAPERS_DIR = Path("experiments/exp_a/papers")
OUTPUTS_DIR = Path("experiments/exp_a/outputs")
MODEL = "gemini-2.5-flash"
SLUG = MODEL.replace("/", "-").replace(":", "-")

# Reuse the system prompt from run_exp_a
sys.path.insert(0, ".")
from src.pipeline.run_exp_a import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def call_gemini_with_retry(paper: dict, max_attempts: int = 5) -> dict:
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    user_msg = USER_PROMPT_TEMPLATE.format(
        research_question=paper["research_question"],
        data_description=paper["data_description"],
        institutional_context=paper["institutional_context"],
    )

    last_err = None
    for attempt in range(max_attempts):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=16384,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
            return {
                "model": MODEL,
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
                "content": resp.choices[0].message.content,
                "stop_reason": resp.choices[0].finish_reason,
            }
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str:
                wait = (2 ** attempt) * 5  # 5s, 10s, 20s, 40s, 80s
                print(f"    503 retry in {wait}s (attempt {attempt+1}/{max_attempts})", flush=True)
                time.sleep(wait)
                continue
            else:
                raise

    raise last_err


def main():
    papers = sorted(PAPERS_DIR.glob("paper_*.json"),
                    key=lambda p: int(p.stem.split("_")[1]))
    missing = []
    for p_file in papers:
        paper = json.loads(p_file.read_text())
        pid = paper["paper_id"]
        out = OUTPUTS_DIR / f"{pid}_{SLUG}.json"
        if not out.exists():
            missing.append((p_file, paper))

    print(f"[gemini_retry] {len(missing)} missing papers to retry", flush=True)
    if not missing:
        print("All papers already have outputs.")
        return

    success = 0
    fail = 0
    for p_file, paper in missing:
        pid = paper["paper_id"]
        out_file = OUTPUTS_DIR / f"{pid}_{SLUG}.json"
        print(f"[GEMINI] {pid}", flush=True)
        try:
            llm_response = call_gemini_with_retry(paper, max_attempts=5)
            output = {
                "paper_id": pid,
                "source": paper.get("source", ""),
                "method_family": paper.get("method_family", ""),
                "difficulty": paper.get("difficulty", ""),
                "model": MODEL,
                "run_at": datetime.now(timezone.utc).isoformat(),
                "llm_response": llm_response,
                "_ground_truth_path": str(p_file),
            }
            out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False))
            success += 1
            print(f"  ✓ saved ({llm_response.get('input_tokens', '?')}in/"
                  f"{llm_response.get('output_tokens', '?')}out)", flush=True)
        except Exception as e:
            print(f"  ✗ failed after retries: {e}", flush=True)
            fail += 1
        # Pace ourselves: small delay between papers
        time.sleep(2)

    print(f"\nDone: {success} success, {fail} fail")


if __name__ == "__main__":
    main()
