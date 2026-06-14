"""
memory.py — All local SQLite reads and writes.

This is the agent's long-term memory. Every trade, every session, every
sector snapshot lives here. Strategy logic (agent.py) never touches SQL directly.

Database: agent.db (created automatically on first run)
"""
import json
import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path("agent.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol        TEXT    NOT NULL,
                sector        TEXT,
                trade_type    TEXT    DEFAULT 'long_stock',
                entry_price   REAL,
                exit_price    REAL,
                qty           INTEGER,
                pnl           REAL    DEFAULT 0,
                pnl_pct       REAL    DEFAULT 0,
                exit_reason   TEXT,
                status        TEXT    DEFAULT 'open',
                session_date  TEXT,
                opened_at     TEXT,
                closed_at     TEXT,
                signal_data   TEXT,
                -- Trade rationale (PRIVATE to the operator — never uploaded. See journal.py).
                -- Captured at decision time and held to, so it can't be hallucinated later.
                entry_thesis    TEXT,   -- the logic for entering, grounded in the real signal + AI reason
                expected_pct    REAL,   -- target % the agent was aiming for
                stop_pct        REAL,   -- the stop it set
                variance_pct    REAL,   -- actual minus expected, computed at close
                variance_reason TEXT    -- grounded reason for the variance (from exit_reason + numbers)
            );
            -- signal_data: JSON blob for any signal metadata at entry
            -- e.g. {"rsi": 44.2, "sma_20": 182.5, "day_change": 0.013}

            CREATE TABLE IF NOT EXISTS sessions (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date      TEXT    NOT NULL,
                session_time      TEXT,
                portfolio_value   REAL,
                buying_power      REAL,
                blocked_sectors   TEXT,
                candidates_found  INTEGER DEFAULT 0,
                positions_opened  INTEGER DEFAULT 0,
                positions_closed  INTEGER DEFAULT 0,
                session_pnl       REAL    DEFAULT 0,
                regime            TEXT,
                notes             TEXT
            );

            CREATE TABLE IF NOT EXISTS sector_snapshots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT    NOT NULL,
                sector       TEXT    NOT NULL,
                trade_count  INTEGER DEFAULT 0,
                win_count    INTEGER DEFAULT 0,
                net_pnl      REAL    DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS publish_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date     TEXT    NOT NULL,
                category     TEXT,
                sector       TEXT,
                notes        TEXT
            );
        """)
        # Migrate older agent.db files to add the rationale columns.
        for col, typ in [("entry_thesis", "TEXT"), ("expected_pct", "REAL"),
                         ("stop_pct", "REAL"), ("variance_pct", "REAL"),
                         ("variance_reason", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass  # column already exists


# ── Trade writes ───────────────────────────────────────────────────────────────

def record_trade_open(
    symbol: str,
    sector: str,
    entry_price: float,
    qty: int,
    trade_type: str = "long_stock",
    signal_data: dict | None = None,
    thesis: str | None = None,
    expected_pct: float | None = None,
    stop_pct: float | None = None,
) -> int:
    """
    Open a trade. Pass signal_data to record the entry signals, and the trade
    RATIONALE (private to the operator): `thesis` (why you entered, grounded in the
    real signal + AI reason), `expected_pct` (target), `stop_pct` (stop). These are
    recorded NOW and held to at close, so the rationale can't be hallucinated later.
    """
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO trades
               (symbol, sector, trade_type, entry_price, qty, status, session_date,
                opened_at, signal_data, entry_thesis, expected_pct, stop_pct)
               VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)""",
            (symbol, sector, trade_type, entry_price, qty, today, now,
             json.dumps(signal_data) if signal_data else None,
             thesis, expected_pct, stop_pct),
        )
        return cur.lastrowid


def _variance_reason(exit_reason: str, pnl_pct: float, expected_pct: float | None) -> str:
    """Grounded reason for the gap between expectation and outcome — from observable
    facts (exit_reason + the numbers), never free narration."""
    if exit_reason == "take_profit":
        return f"hit target as expected ({pnl_pct:+.1%})"
    if exit_reason == "stop_loss":
        return f"thesis invalidated — stopped out at {pnl_pct:+.1%}"
    tail = f" vs +{expected_pct:.0%} target" if expected_pct is not None else ""
    return f"exited via {exit_reason} at {pnl_pct:+.1%}{tail}"


def record_trade_close(trade_id: int, exit_price: float, pnl: float,
                       pnl_pct: float, exit_reason: str):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        row = conn.execute("SELECT expected_pct FROM trades WHERE id=?", (trade_id,)).fetchone()
        expected = row["expected_pct"] if row else None
        # Variance is COMPUTED from the recorded expectation vs the real outcome — the
        # numbers can't be confabulated, which is what keeps the journal honest.
        variance_pct = round(pnl_pct - expected, 4) if expected is not None else None
        variance_reason = _variance_reason(exit_reason, pnl_pct, expected)
        conn.execute(
            """UPDATE trades SET exit_price=?, pnl=?, pnl_pct=?, exit_reason=?,
               status='closed', closed_at=?, variance_pct=?, variance_reason=? WHERE id=?""",
            (exit_price, pnl, pnl_pct, exit_reason, now, variance_pct, variance_reason, trade_id),
        )


def get_journal(limit: int = 30) -> list[dict]:
    """Closed trades with their full rationale, newest first — for the human journal."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT symbol, sector, opened_at, closed_at, entry_thesis, expected_pct,
                      stop_pct, pnl, pnl_pct, exit_reason, variance_pct, variance_reason
               FROM trades WHERE status='closed' ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Session writes ─────────────────────────────────────────────────────────────

def record_session(portfolio_value: float, buying_power: float,
                   blocked_sectors: list[str], candidates_found: int,
                   positions_opened: int, positions_closed: int,
                   session_pnl: float, regime: str | None = None,
                   notes: str = ""):
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime("%H:%M")
    with _conn() as conn:
        conn.execute(
            """INSERT INTO sessions
               (session_date, session_time, portfolio_value, buying_power,
                blocked_sectors, candidates_found, positions_opened,
                positions_closed, session_pnl, regime, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (today, now, portfolio_value, buying_power,
             json.dumps(blocked_sectors), candidates_found,
             positions_opened, positions_closed, session_pnl, regime, notes),
        )


def record_sector_snapshot(sector: str, trade_count: int, win_count: int, net_pnl: float):
    today = datetime.date.today().isoformat()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO sector_snapshots (session_date, sector, trade_count, win_count, net_pnl)
               VALUES (?, ?, ?, ?, ?)""",
            (today, sector, trade_count, win_count, net_pnl),
        )


# ── Publish gate ───────────────────────────────────────────────────────────────

def was_published_today(category: str, sector: str | None = None) -> bool:
    today = datetime.date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM publish_log WHERE log_date=? AND category=? AND (sector=? OR sector IS NULL)",
            (today, category, sector),
        ).fetchone()
    return row is not None


def mark_published(category: str, sector: str | None = None, notes: str = ""):
    today = datetime.date.today().isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO publish_log (log_date, category, sector, notes) VALUES (?, ?, ?, ?)",
            (today, category, sector, notes),
        )


# ── Reads / analytics ──────────────────────────────────────────────────────────

def get_summary_stats(days: int = 3650) -> dict:
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with _conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) total, SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) wins,
                      SUM(pnl) net_pnl
               FROM trades WHERE status='closed' AND session_date >= ?""",
            (cutoff,),
        ).fetchone()
    total = row["total"] or 0
    wins  = row["wins"] or 0
    return {
        "total_trades": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total, 3) if total else 0,
        "net_pnl": round(row["net_pnl"] or 0, 2),
    }


def get_risk_metrics() -> dict | None:
    """
    Risk-adjusted track record for the Agentberg knowledge upload — NOT win rate.
    Expectancy (avg P&L/trade), profit factor, and max drawdown can't be reverse-
    engineered into a strategy, so they're safe to share. Returns None if there are
    no closed trades yet (nothing worth uploading).
    """
    with _conn() as conn:
        pnls = [
            r["pnl"] or 0
            for r in conn.execute("SELECT pnl FROM trades WHERE status='closed'").fetchall()
        ]
        equity = [
            r["portfolio_value"]
            for r in conn.execute(
                "SELECT portfolio_value FROM sessions "
                "WHERE portfolio_value IS NOT NULL ORDER BY id"
            ).fetchall()
        ]
    n = len(pnls)
    if n == 0:
        return None
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 3)
    else:
        profit_factor = 999.0 if gross_profit > 0 else 0.0
    # Max drawdown off the portfolio-value curve (peak-to-trough %).
    peak = None
    max_dd = 0.0
    for v in equity:
        if peak is None or v > peak:
            peak = v
        if peak and peak > 0:
            max_dd = max(max_dd, (peak - v) / peak * 100)
    return {
        "expectancy": round(sum(pnls) / n, 4),
        "profit_factor": profit_factor,
        "max_drawdown_pct": round(max_dd, 2),
        "sample_size": n,
    }


def get_sector_performance(days: int = 3650) -> list[dict]:
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT sector,
                      COUNT(*) trade_count,
                      SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) wins,
                      SUM(pnl) net_pnl
               FROM trades WHERE status='closed' AND session_date >= ?
               GROUP BY sector ORDER BY net_pnl DESC""",
            (cutoff,),
        ).fetchall()
    result = []
    for r in rows:
        total = r["trade_count"]
        result.append({
            "sector": r["sector"],
            "trade_count": total,
            "win_rate": round((r["wins"] or 0) / total, 3) if total else 0,
            "net_pnl": round(r["net_pnl"] or 0, 2),
        })
    return result


def get_recent_trades(limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_open_trades() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE status='open' ORDER BY opened_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_history(days: int = 60) -> list[dict]:
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE session_date >= ? ORDER BY id DESC",
            (cutoff,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["blocked_sectors"] = json.loads(d.get("blocked_sectors") or "[]")
        except Exception:
            d["blocked_sectors"] = []
        result.append(d)
    return result


def get_winning_sectors(min_trades: int = 5, min_wr: float = 0.70) -> list[str]:
    rows = get_sector_performance()
    return [r["sector"] for r in rows if r["trade_count"] >= min_trades and r["win_rate"] >= min_wr]


def get_losing_sectors(min_trades: int = 5, max_wr: float = 0.30) -> list[str]:
    rows = get_sector_performance()
    return [r["sector"] for r in rows if r["trade_count"] >= min_trades and r["win_rate"] <= max_wr]


def get_win_rate(days: int = 30, sector: str | None = None) -> dict:
    """
    Rolling win rate. Optionally filter by sector.

    Usage:
        get_win_rate(days=30)                    # rolling 30-day
        get_win_rate(sector="Technology")         # sector-specific, all-time
        get_win_rate(days=14, sector="Energy")    # sector + window
    """
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    params: list = [cutoff]
    sector_clause = ""
    if sector:
        sector_clause = "AND sector = ?"
        params.append(sector)
    with _conn() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) total,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) wins,
                       SUM(pnl) net_pnl
                FROM trades
               WHERE status='closed' AND session_date >= ? {sector_clause}""",
            params,
        ).fetchone()
    total = row["total"] or 0
    wins  = row["wins"] or 0
    return {
        "total": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total, 3) if total else 0,
        "net_pnl": round(row["net_pnl"] or 0, 2),
        "days": days,
        "sector": sector,
    }


def get_portfolio_history(days: int = 60) -> list[dict]:
    """
    Session-by-session portfolio value — use for charting the equity curve.

    Returns one row per session, ordered oldest first.
    """
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT session_date, session_time, portfolio_value,
                      buying_power, session_pnl, regime
               FROM sessions
               WHERE session_date >= ?
               ORDER BY id ASC""",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]
