"""Gemini reasoning client for the Agentberg starter agent.

Uses Gemini's OpenAI-compatible endpoint — no extra SDK needed.
Get your free API key at aistudio.google.com
"""

import json
import os


def rank_candidates(candidates, regime, risk_level, health_label, blocked_sectors):
    if not candidates:
        return candidates
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Run: pip install openai")

    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    )
    model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")

    prompt = f"""You are a disciplined trading agent reviewing candidates for today's session.

Market context:
- Regime: {regime or "unknown"}
- Risk level: {risk_level or "unknown"}
- Market health: {health_label or "unknown"}
- Blocked sectors (do not trade): {blocked_sectors or "none"}

Candidates identified by momentum signal:
{json.dumps(candidates, indent=2)}

Review each candidate. For each one, decide: TRADE or SKIP.
Criteria:
- Skip if sector is blocked
- Skip if regime is bear and direction is bullish
- Skip if risk level is high and the move is weak (< 1.5%)
- Prefer stronger moves and sectors with tailwinds in this regime
- Keep at most 3 candidates

Respond with a JSON array of candidates to TRADE, in priority order.
Each object must have: ticker, sector, direction, price, day_change, reason (one sentence).
Return only valid JSON. No explanation outside the array."""

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
        print(f"    [gemini/{model}] filtered {len(candidates)} → {len(ranked)} candidate(s)")
        for c in ranked:
            print(f"    [gemini] TRADE {c['ticker']}: {c.get('reason', '')}")
        return ranked
    except Exception as e:
        print(f"    [gemini] reasoning unavailable ({e}) — using rule-based candidates")
        return candidates
