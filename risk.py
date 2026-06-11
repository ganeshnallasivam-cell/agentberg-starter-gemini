"""
risk.py — Risk check functions.

All tunable parameters live in config.py.
This module is pure logic — checks return (allowed: bool, reason: str).
"""
import config as cfg


def check_equity(
    ticker: str,
    sector: str,
    regime: str | None,
    blocked_sectors: list[str],
    position_value: float,
    portfolio_equity: float,
    open_positions: int,
) -> tuple[bool, str]:
    if sector in blocked_sectors:
        return False, f"{sector} blocked by network consensus"
    if regime and regime in cfg.BLOCKED_REGIMES:
        return False, f"Regime '{regime}' blocked — no new longs"
    if open_positions >= cfg.MAX_POSITIONS:
        return False, f"At max positions ({cfg.MAX_POSITIONS})"
    if portfolio_equity > 0 and (position_value / portfolio_equity) > cfg.MAX_POSITION_PCT:
        return False, f"Position {position_value/portfolio_equity:.1%} exceeds {cfg.MAX_POSITION_PCT:.1%} limit"
    return True, "ok"


def check_option(
    ticker: str,
    sector: str,
    regime: str | None,
    blocked_sectors: list[str],
    portfolio_equity: float,
    open_positions: int,
    premium: float,
    dte: int,
    delta: float,
    iv_rank: float | None = None,
) -> tuple[bool, str]:
    if sector in blocked_sectors:
        return False, f"{sector} blocked by network consensus"
    if regime and regime in cfg.BLOCKED_REGIMES:
        return False, f"Regime '{regime}' blocked — no new longs"
    if open_positions >= cfg.MAX_POSITIONS:
        return False, f"At max positions ({cfg.MAX_POSITIONS})"
    if dte < cfg.MIN_DTE:
        return False, f"{dte} DTE below minimum {cfg.MIN_DTE} — gamma risk too high"
    if dte > cfg.MAX_DTE:
        return False, f"{dte} DTE above maximum {cfg.MAX_DTE}"
    if not (cfg.MIN_DELTA <= abs(delta) <= cfg.MAX_DELTA):
        return False, f"Delta {delta:.2f} outside target range {cfg.MIN_DELTA}–{cfg.MAX_DELTA}"
    if iv_rank is not None and iv_rank > cfg.MAX_IV_RANK_TO_BUY:
        return False, f"IV Rank {iv_rank:.0f} too high — premium too expensive (max {cfg.MAX_IV_RANK_TO_BUY})"
    cost = premium * 100
    if portfolio_equity > 0 and (cost / portfolio_equity) > cfg.MAX_OPTION_PCT:
        return False, f"Premium cost {cost/portfolio_equity:.1%} exceeds {cfg.MAX_OPTION_PCT:.1%} limit"
    return True, "ok"


def check_spread(
    ticker: str,
    sector: str,
    regime: str | None,
    blocked_sectors: list[str],
    portfolio_equity: float,
    open_positions: int,
    net_debit: float,
    spread_width: float,
    dte: int,
) -> tuple[bool, str]:
    if sector in blocked_sectors:
        return False, f"{sector} blocked by network consensus"
    if regime and regime in cfg.BLOCKED_REGIMES:
        return False, f"Regime '{regime}' blocked — no new longs"
    if open_positions >= cfg.MAX_POSITIONS:
        return False, f"At max positions ({cfg.MAX_POSITIONS})"
    if dte < cfg.MIN_DTE:
        return False, f"{dte} DTE below minimum {cfg.MIN_DTE}"
    if dte > cfg.MAX_DTE:
        return False, f"{dte} DTE above maximum {cfg.MAX_DTE}"
    if spread_width > 0 and (net_debit / spread_width) > cfg.MAX_SPREAD_DEBIT_PCT:
        return False, f"Debit {net_debit/spread_width:.0%} of width exceeds {cfg.MAX_SPREAD_DEBIT_PCT:.0%} cap"
    max_loss = net_debit * 100
    if portfolio_equity > 0 and (max_loss / portfolio_equity) > cfg.MAX_SPREAD_PCT:
        return False, f"Max loss {max_loss/portfolio_equity:.1%} exceeds {cfg.MAX_SPREAD_PCT:.1%} limit"
    return True, "ok"
