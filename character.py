"""
character.py — the agent's persistent CHARACTER (persona, risk appetite, goals).

Captured once via the standard onboarding questionnaire (run `python setup.py`, or
the agent asks the questions per AGENTS.md), stored in character.json, and applied
on top of config.py's defaults. It persists across runs and only changes when the
human explicitly asks. Any question the human defers ("let the agent decide") keeps
the kit's default — so behaviour is consistent and predictable either way.
"""

import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "character.json")

# ── The standard onboarding questionnaire ───────────────────────────────────────
# Every agent asks THIS list, the same way, on first setup. `default: None` means
# "use the kit default from config.py" when the human defers.
QUESTIONS = [
    {"id": "agent_name", "q": "Agent name (your identity on Agentberg)", "type": "text", "required": True},
    {"id": "instruments", "q": "Trade equity, options, or both?", "type": "choice",
     "options": ["equity", "options", "both"], "default": "equity"},
    {"id": "goal", "q": "Goal — income, growth, or preservation?", "type": "text", "default": "balanced growth"},
    {"id": "time_horizon", "q": "By when? (e.g. 3 months, 1 year, open-ended)", "type": "text", "default": "open-ended"},
    {"id": "risk_tolerance", "q": "Risk tolerance — conservative, balanced, or aggressive?", "type": "choice",
     "options": ["conservative", "balanced", "aggressive"], "default": "balanced"},
    {"id": "max_loss_per_trade_pct", "q": "Max loss per trade before stopping out (%)", "type": "pct", "default": None},
    {"id": "take_profit_pct", "q": "Take profit per trade at what gain (%)", "type": "pct", "default": None},
    {"id": "max_position_pct", "q": "Max % of portfolio in one position", "type": "pct", "default": None},
    {"id": "max_positions", "q": "Max concurrent open positions", "type": "int", "default": None},
    {"id": "preferred_sectors", "q": "Preferred sectors (comma-separated, or none)", "type": "list", "default": []},
    {"id": "must_include", "q": "Stocks to always watch (tickers, comma-separated)", "type": "list", "default": []},
    {"id": "must_exclude", "q": "Stocks or sectors to NEVER trade (comma-separated)", "type": "list", "default": []},
    {"id": "trade_in_bear", "q": "Trade during a bear-market regime?", "type": "yesno", "default": False},
    {"id": "mandate", "q": "Anything else the agent must respect? (free text)", "type": "text", "default": ""},
]


def coerce(q: dict, raw: str):
    """Turn a raw string answer into the field's typed value."""
    t = q["type"]
    if t == "list":
        return [x.strip() for x in raw.split(",") if x.strip()]
    if t == "int":
        return int(float(raw))
    if t == "pct":
        return float(str(raw).replace("%", "").strip())
    if t == "yesno":
        return str(raw).strip().lower() in ("y", "yes", "true", "1")
    if t == "choice":
        v = raw.strip().lower()
        return v if v in q["options"] else q.get("default")
    return raw.strip()


def load() -> dict:
    if os.path.exists(_PATH):
        try:
            with open(_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save(character: dict) -> None:
    with open(_PATH, "w") as f:
        json.dump(character, f, indent=2)


def is_set() -> bool:
    return bool(load().get("agent_name"))


def summary() -> str:
    c = load()
    if not c:
        return "no character set — run `python setup.py`"
    return (f"{c.get('agent_name','?')} · {c.get('instruments','equity')} · "
            f"{c.get('risk_tolerance','balanced')} · goal: {c.get('goal','—')}")
