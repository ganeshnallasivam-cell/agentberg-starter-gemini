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
# Once registered, the network may have handed us a UNIQUE id (if our chosen one was
# taken). That confirmed id is persisted in .agent_id and takes precedence so our
# reputation and findings stay ours. See agent.py _ensure_registered().
_ID_FILE = os.path.join(os.path.dirname(__file__), ".agent_id")
if os.path.exists(_ID_FILE):
    _confirmed = open(_ID_FILE).read().strip()
    if _confirmed:
        AGENT_ID = _confirmed
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
# Grouped by sector. Add or remove tickers freely. Sectors the NETWORK has flagged are
# advisory (weighed in AI ranking, not skipped); only YOUR own MANUAL_BLOCKED_SECTORS
# (below) are hard-skipped.
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

# ── Character overlay ──────────────────────────────────────────────────────────
# If onboarding is complete (character.json), apply the operator's persona ON TOP of
# the defaults above. Anything the human deferred keeps the kit default. The agent
# operates by this until the human asks to change it. See character.py / setup.py.
try:
    import character as _character
    _c = _character.load()
except Exception:
    _c = {}

# Descriptive persona (kept for logging + future AI-ranking context).
GOAL: str = _c.get("goal", "")
TIME_HORIZON: str = _c.get("time_horizon", "")
RISK_TOLERANCE: str = _c.get("risk_tolerance", "")
PREFERRED_SECTORS: list[str] = _c.get("preferred_sectors", []) or []
MANDATE: str = _c.get("mandate", "")

if _c:
    _instr = _c.get("instruments")
    if _instr == "equity":
        STRATEGY_MODE = "equity"
    elif _instr in ("options", "both"):
        STRATEGY_MODE = "premium_buyer"

    if _c.get("max_loss_per_trade_pct") is not None:
        EQUITY_STOP_LOSS_PCT = float(_c["max_loss_per_trade_pct"]) / 100.0
    if _c.get("take_profit_pct") is not None:
        TAKE_PROFIT_PCT = float(_c["take_profit_pct"]) / 100.0
    if _c.get("max_position_pct") is not None:
        MAX_POSITION_PCT = float(_c["max_position_pct"]) / 100.0
    if _c.get("max_positions") is not None:
        MAX_POSITIONS = int(_c["max_positions"])
    if _c.get("trade_in_bear") is True:
        BLOCKED_REGIMES = [r for r in BLOCKED_REGIMES if r != "bear"]

    # Never-trade list: sector names become blocked sectors; everything else is
    # treated as a ticker and removed from the watchlist entirely.
    for _item in _c.get("must_exclude", []):
        _s = _item.strip()
        if not _s:
            continue
        if _s.title() in WATCHLIST:
            MANUAL_BLOCKED_SECTORS = list(set(MANUAL_BLOCKED_SECTORS + [_s.title()]))
        else:
            for _sec in WATCHLIST:
                WATCHLIST[_sec] = [t for t in WATCHLIST[_sec] if t.upper() != _s.upper()]

    # Always-watch tickers the human insisted on.
    _incl = [x.strip().upper() for x in _c.get("must_include", []) if x.strip()]
    if _incl:
        WATCHLIST["Preferred"] = sorted(set(WATCHLIST.get("Preferred", []) + _incl))
