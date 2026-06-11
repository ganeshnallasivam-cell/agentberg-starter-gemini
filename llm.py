"""
llm.py — Gemini ranking layer (free tier, 1,500 req/day).

Get your free API key at aistudio.google.com
Set GEMINI_API_KEY in your .env file.

Leave GEMINI_API_KEY unset to skip LLM ranking and run rule-based only.
Override model via LLM_MODEL env var (default: gemini-2.0-flash).
"""

import json
import os


def rank_candidates(
    candidates: list[dict],
    regime: str,
    risk_level: str,
    health_label: str,
    blocked_sectors: list[str],
) -> list[dict]:
    """
    Ask Gemini to review candidates and return only the ones worth trading.
    Falls back to the original list if unavailable or key not set.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key or not candidates:
        return candidates

    try:
        from openai import OpenAI
    except ImportError:
        print("    [llm] Run: pip install openai")
        return candidates

    model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")

    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    )

    prompt = f"""You are a disciplined trading agent reviewing candidates.

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
JSON only — no text outside the array."""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        ranked = json.loads(raw.strip())
        print(f"    [gemini/{model}] {len(candidates)} → {len(ranked)} candidate(s)")
        for c in ranked:
            print(f"    [gemini] TRADE {c['ticker']}: {c.get('reason', '')}")
        return ranked
    except Exception as e:
        print(f"    [gemini] unavailable ({e}) — rule-based fallback")
        return candidates
