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
                signal_data   TEXT
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


# ── Trade writes ───────────────────────────────────────────────────────────────

def record_trade_open(
    symbol: str,
    sector: str,
    entry_price: float,
    qty: int,
    trade_type: str = "long_stock",
    signal_data: dict | None = None,
) -> int:
    """
    Open a trade. Pass signal_data to record the signals that triggered entry.
    Example: signal_data={"rsi": 44.2, "sma_20": 182.5, "day_change": 0.013}
    """
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO trades
               (symbol, sector, trade_type, entry_price, qty, status, session_date, opened_at, signal_data)
               VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
            (symbol, sector, trade_type, entry_price, qty, today, now,
             json.dumps(signal_data) if signal_data else None),
        )
        return cur.lastrowid


def record_trade_close(trade_id: int, exit_price: float, pnl: float,
                       pnl_pct: float, exit_reason: str):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            """UPDATE trades SET exit_price=?, pnl=?, pnl_pct=?, exit_reason=?,
               status='closed', closed_at=? WHERE id=?""",
            (exit_price, pnl, pnl_pct, exit_reason, now, trade_id),
        )


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
