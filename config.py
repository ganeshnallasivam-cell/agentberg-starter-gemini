"""
config.py — All tunable parameters in one place.

This is the only file you need to edit to configure your agent.
Read every line. Change values to match your own strategy and risk tolerance.

DISCLAIMER: This is a software template, not investment advice.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Identity ───────────────────────────────────────────────────────────────────
AGENT_ID       = os.environ["AGENT_ID"]                          # unique name on Agentberg network
AGENTBERG_URL  = os.environ.get("AGENTBERG_URL", "https://agentberg.ai")

# ── Broker credentials ─────────────────────────────────────────────────────────
ALPACA_API_KEY    = os.environ["ALPACA_API_KEY"]
ALPACA_SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
ALPACA_BASE_URL   = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
ALPACA_PAPER      = True   # hardcoded — never change until you are ready and have tested

# ── Strategy mode ──────────────────────────────────────────────────────────────
# "equity"         — buy/sell stocks
# "premium_buyer"  — buy calls/puts directionally
# "spreads"        — debit spreads (bull call / bear put)
STRATEGY_MODE: str = "equity"

# ── Watchlist ──────────────────────────────────────────────────────────────────
# Grouped by sector so blocked-sector rules apply automatically.
# Add or remove tickers freely. Agentberg will skip any sector it has flagged.
WATCHLIST: dict[str, list[str]] = {
    "Technology":           ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMD"],
    "Energy":               ["XOM", "CVX", "COP"],
    "Financials":           ["JPM", "BAC", "GS"],
    "Healthcare":           ["UNH", "JNJ", "ABT"],
    "Industrials":          ["CAT", "DE", "HON"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD"],
}

# ── Position sizing ────────────────────────────────────────────────────────────
MAX_POSITIONS:       int   = 5      # max concurrent open positions
MAX_POSITION_PCT:    float = 0.05   # 5% of portfolio per equity trade
MAX_OPTION_PCT:      float = 0.02   # 2% per single-leg options trade
MAX_SPREAD_PCT:      float = 0.02   # 2% per spread (max loss = debit paid)
MAX_NEW_PER_CYCLE:   int   = 3      # cap new positions opened in one session

# ── Stop loss / take profit ────────────────────────────────────────────────────
EQUITY_STOP_LOSS_PCT:   float = 0.02   # exit equity if down 2%
OPTION_STOP_LOSS_PCT:   float = 0.50   # exit option if down 50% of premium paid
TAKE_PROFIT_PCT:        float = 1.00   # exit at 100% gain on premium (2× paid)

# ── Options DTE window ─────────────────────────────────────────────────────────
MIN_DTE: int = 21    # < 21 DTE: gamma risk spikes
MAX_DTE: int = 45    # > 45 DTE: too much premium at risk for too long

# ── Options delta targeting ────────────────────────────────────────────────────
MIN_DELTA: float = 0.30    # below this: lottery ticket
MAX_DELTA: float = 0.50    # above this: just trade the stock

# ── IV Rank ────────────────────────────────────────────────────────────────────
MAX_IV_RANK_TO_BUY: float = 30.0   # don't buy when IV is expensive

# ── Spreads ────────────────────────────────────────────────────────────────────
MAX_SPREAD_DEBIT_PCT:  float = 0.33   # max debit as % of spread width
EARNINGS_BLACKOUT_DAYS: int = 5       # don't open options within 5 days of earnings

# ── Network rules ──────────────────────────────────────────────────────────────
# Blocked sectors are populated from Agentberg at runtime — no need to set here.
# Add permanent manual blocks if you want to avoid certain sectors regardless.
MANUAL_BLOCKED_SECTORS: list[str] = []

# Regimes to sit out entirely. "bear" means no new longs.
BLOCKED_REGIMES: list[str] = ["bear"]
