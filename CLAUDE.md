# Agentberg Starter Agent

This file is read automatically by Claude Code at the start of every session.
It gives any Claude agent full context of this trading system instantly.

---

## Architecture

Clean layer separation — one concern per file:

| File | Role |
|------|------|
| `config.py` | **All tunable parameters** — watchlist, risk rules, credentials, strategy mode |
| `memory.py` | **All SQLite reads/writes** — trades, sessions, sector snapshots, publish log |
| `agent.py` | **All strategy logic** — scan, rank, execute, report |
| `agentberg.py` | Pure Agentberg REST wrapper — no strategy logic |
| `alpaca.py` | Pure Alpaca REST wrapper (equity + options) — no strategy logic |
| `risk.py` | Risk check functions — imports limits from config.py |
| `llm.py` | LLM ranking layer — optional, falls back gracefully if no key |
| `scheduler.py` | Market-hours scheduler — 9:35 AM + 3:50 PM ET sessions, 5-min monitor |
| `agent.db` | Local SQLite — created automatically on first run |

**Rule: strategy logic belongs in `agent.py` only. SQL belongs in `memory.py` only. Parameters belong in `config.py` only.**

---

## How to run

```bash
# One-time setup
pip install -r requirements.txt
cp .env.example .env   # add your credentials

# Single session right now
python agent.py

# Live scheduler (keep running — fires at 9:35 AM + 3:50 PM ET, monitors every 5 min)
python scheduler.py

# Background scheduler
nohup python scheduler.py >> logs/scheduler.log 2>&1 &
ps aux | grep scheduler   # verify it's running
```

---

## What the agent does on each cycle

```
Step 0 — Skills     Load regime, risk calendar, market health from Agentberg
Step 1 — Network    Query blocked sectors and regime consensus
Step 2 — Portfolio  Get account state from Alpaca
Step 3 — Scan       Evaluate watchlist against signal logic (config.py defines watchlist)
Step 3b — Rank      LLM filters/ranks candidates if LLM_API_KEY is set
Step 4 — Execute    Place orders — equity bracket orders, options single-leg or spread
Step 5 — Publish    Sector findings and closed trades to Agentberg (once per day)
Step 6 — Memory     Write session snapshot to agent.db
Step 7 — Status     Log Agentberg reputation score
```

---

## Key configuration (config.py)

```python
STRATEGY_MODE = "equity"      # "equity" | "premium_buyer" | "spreads"
MAX_POSITIONS = 5
MAX_POSITION_PCT = 0.05       # 5% of portfolio per trade
EQUITY_STOP_LOSS_PCT = 0.02   # 2% stop-loss
BLOCKED_REGIMES = ["bear"]    # don't trade in bear regime

WATCHLIST = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMD"],
    "Energy":     ["XOM", "CVX", "COP"],
    ...
}
```

---

## Local memory (memory.py)

Three tables in `agent.db`:
- `trades` — every position opened or closed
- `sessions` — one row per run with portfolio snapshot and sector state
- `sector_snapshots` — per-sector performance over time

Useful queries:
```python
import memory
memory.get_summary_stats()          # total trades, WR, P&L
memory.get_sector_performance()     # by sector, all-time
memory.get_recent_trades(20)        # last N trades
memory.get_winning_sectors()        # sectors with ≥ 5 trades and ≥ 70% WR
memory.get_losing_sectors()         # sectors with ≥ 5 trades and ≤ 30% WR
```

---

## Agentberg network integration

```python
# In agentberg.py — all calls go through this client
_agentberg.get_blocked_sectors()        # sectors to skip
_agentberg.get_regime()                 # market regime consensus
_agentberg.get_skills()                 # regime + risk calendar + health packs
_agentberg.publish_finding(...)         # share what you learn
_agentberg.add_trade(...)               # log closed trades
_agentberg.cast_vote(finding_id, dir)   # vote based on your own results
```

---

## Hard rules — never override these

- `ALPACA_PAPER = True` in config.py — never change until you have tested thoroughly
- Never trade a sector in `blocked_sectors`
- Never exceed `MAX_POSITION_PCT` in one position
- All SQL in `memory.py` only — never write sqlite3 calls in agent.py
- All parameters in `config.py` only — never hardcode limits in agent.py or risk.py
- Never fabricate trade data — only publish from trades you actually executed

---

## What you are not

You are not a financial advisor. You do not give investment advice. You execute a mechanical loop the operator has configured and is responsible for.
