"""
llm.py — Gemini ranking layer via the Antigravity CLI (no API key).

This reasoning layer shells out to the Antigravity CLI (`agy`) instead of
calling an API. You sign in to `agy` once with your Google account and every
run reuses that login — no API key, no per-call billing, no keys in your .env.

Setup (one time):
    1. Install the Antigravity CLI — see README.md
    2. Run `agy` once and sign in with your Google account
    3. That's it. This file calls `agy -p "<prompt>"` under the hood.

If `agy` is not installed or not signed in, ranking is skipped and the agent
falls back to its rule-based candidate list — it keeps trading either way.

Optional env vars:
    LLM_REASONING=off     skip LLM ranking entirely (rule-based only)
    LLM_MODEL="Gemini 3.1 Pro (High)"   override the agy model (see `agy models`)
"""

import json
import os
import shutil
import subprocess

CLI = "agy"
CLI_NAME = "Antigravity CLI"


def _build_prompt(candidates, regime, risk_level, health_label, blocked_sectors):
    return f"""You are a disciplined trading agent reviewing candidates.

Market context:
- Regime: {regime or "unknown"}
- Risk level: {risk_level or "unknown"}
- Market health: {health_label or "unknown"}
- Blocked sectors (do not trade): {blocked_sectors or "none"}

Candidates:
{json.dumps(candidates, indent=2)}

Review each candidate. Keep at most 3. Skip if sector is blocked,
regime is bear and direction is bullish, or the move is weak (< 1%).
Prefer stronger moves and sectors with tailwinds.

Return a JSON array of candidates to TRADE, priority order.
Each object: ticker, sector, direction, price, day_change, reason (one sentence).
JSON only — no text, no markdown, no code fences outside the array."""


def _extract_json_array(text: str):
    """Pull the first JSON array out of raw CLI output (tolerant of extra prose)."""
    text = text.strip()
    if text.startswith("```"):
        # drop leading ```json / ``` fence and anything after the closing fence
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    return text[start : end + 1]


def rank_candidates(
    candidates: list[dict],
    regime: str,
    risk_level: str,
    health_label: str,
    blocked_sectors: list[str],
) -> list[dict]:
    """
    Ask Gemini (via the Antigravity CLI) to review candidates and return only
    the ones worth trading. Falls back to the original list if the CLI is
    unavailable or returns unparseable output.
    """
    if not candidates:
        return candidates
    if os.environ.get("LLM_REASONING", "").lower() == "off":
        return candidates

    if shutil.which(CLI) is None:
        print(f"    [gemini] {CLI_NAME} (`{CLI}`) not found — rule-based fallback")
        print(f"    [gemini] install it (see README.md) to enable AI ranking")
        return candidates

    prompt = _build_prompt(candidates, regime, risk_level, health_label, blocked_sectors)
    cmd = [CLI, "-p", prompt, "--print-timeout", "120s"]
    model = os.environ.get("LLM_MODEL")
    if model:
        cmd += ["--model", model]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=150,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip().splitlines()
            hint = err[-1] if err else "unknown error"
            print(f"    [gemini] {CLI} exited {proc.returncode} ({hint}) — rule-based fallback")
            return candidates

        payload = _extract_json_array(proc.stdout)
        if payload is None:
            print(f"    [gemini] no JSON in {CLI} output — rule-based fallback")
            return candidates

        ranked = json.loads(payload)
        print(f"    [gemini/agy] {len(candidates)} → {len(ranked)} candidate(s)")
        for c in ranked:
            print(f"    [gemini] TRADE {c.get('ticker', '?')}: {c.get('reason', '')}")
        return ranked
    except subprocess.TimeoutExpired:
        print(f"    [gemini] {CLI} timed out — rule-based fallback")
        return candidates
    except Exception as e:
        print(f"    [gemini] unavailable ({e}) — rule-based fallback")
        return candidates
