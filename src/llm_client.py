"""
Shared LLM client for CausalVerify.

Provides a unified interface for calling Anthropic, OpenAI, Moonshot (Kimi),
and Google (Gemini) APIs. All providers return a normalized response dict:

    {
        "model": str,
        "input_tokens": int,
        "output_tokens": int,
        "content": str,
        "stop_reason": str,
    }

Usage:
    from src.llm_client import call_llm

    response = call_llm(
        model="claude-opus-4-6",
        system_prompt="You are an expert econometrician.",
        user_message="Propose an identification strategy...",
        max_tokens=8192,
    )
    print(response["content"])

Replaces the duplicated call_llm() functions in:
    - src/pipeline/run_exp_a.py
    - src/pipeline/run_exp_b.py
    - src/pipeline/run_exp_c_v2.py
    - src/pipeline/run_prompt_sensitivity.py
"""

import os

from dotenv import load_dotenv
load_dotenv()


def _call_anthropic(model: str, system_prompt: str, user_message: str,
                    max_tokens: int = 8192) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return {
        "model": model,
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
        "content": msg.content[0].text,
        "stop_reason": msg.stop_reason,
    }


def _call_openai(model: str, system_prompt: str, user_message: str,
                 max_tokens: int = 4096) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Reasoning / newer-generation models use 'max_completion_tokens'
    # instead of 'max_tokens'. This includes the o-series (o1/o3/o4)
    # and GPT-5 family.
    is_reasoning = (
        model.startswith("o3")
        or model.startswith("o1")
        or model.startswith("o4")
        or model.startswith("gpt-5")
    )
    token_kwarg = "max_completion_tokens" if is_reasoning else "max_tokens"

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        **{token_kwarg: max_tokens},
    )
    return {
        "model": model,
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "content": resp.choices[0].message.content,
        "stop_reason": resp.choices[0].finish_reason,
    }


def _call_kimi(model: str, system_prompt: str, user_message: str,
               max_tokens: int = 4096) -> dict:
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("KIMI_API_KEY"),
        base_url="https://api.moonshot.cn/v1",
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
    )
    return {
        "model": model,
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "content": resp.choices[0].message.content,
        "stop_reason": resp.choices[0].finish_reason,
    }


def _call_gemini(model: str, system_prompt: str, user_message: str,
                 max_tokens: int = 16384) -> dict:
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return {
        "model": model,
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "content": resp.choices[0].message.content,
        "stop_reason": resp.choices[0].finish_reason,
    }


def call_llm(model: str, system_prompt: str, user_message: str,
             max_tokens: int | None = None) -> dict:
    """Dispatch to the right provider based on model name.

    Args:
        model: API model identifier (e.g. "claude-opus-4-6", "gpt-4o", "o3",
               "moonshot-v1-128k", "gemini-2.5-flash")
        system_prompt: System message for the conversation
        user_message: User message content
        max_tokens: Override default max output tokens. Defaults vary by provider:
                    Anthropic 8192, OpenAI 4096, Kimi 4096, Gemini 16384.

    Returns:
        Normalized response dict with model, token counts, content, stop_reason.

    Raises:
        ValueError: If model name doesn't match any known provider.
    """
    m = model.lower()

    if "claude" in m:
        return _call_anthropic(model, system_prompt, user_message,
                               max_tokens or 8192)
    if "gpt" in m or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        return _call_openai(model, system_prompt, user_message,
                            max_tokens or 4096)
    if "moonshot" in m or "kimi" in m:
        return _call_kimi(model, system_prompt, user_message,
                          max_tokens or 4096)
    if "gemini" in m:
        return _call_gemini(model, system_prompt, user_message,
                            max_tokens or 16384)

    raise ValueError(
        f"Unknown model provider for: {model}. "
        "Supported prefixes: claude, gpt, o3, o1, o4, moonshot, kimi, gemini"
    )
