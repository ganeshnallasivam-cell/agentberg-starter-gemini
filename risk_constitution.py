"""
Risk Constitution
-----------------
The rules your agent follows. Read every line.
Change the values to match your own risk tolerance.
This is not financial advice — these are mechanical limits you define and own.
"""


class RiskConstitution:

    # ── Execution ──────────────────────────────────────────────────────────────
    # "paper" until you have tested thoroughly and are confident
    ALLOWED_EXEC_ENV: str = "paper"

    # ── Strategy mode ──────────────────────────────────────────────────────────
    # "equity"         — buy/sell stocks only
    # "premium_buyer"  — buy calls and puts directionally
    # "spreads"        — debit spreads (bull call / bear put)
    STRATEGY_MODE: str = "premium_buyer"

    # ── Position sizing ────────────────────────────────────────────────────────
    # Options are leveraged — use half the size you would for equities.
    # Equity: 5% max. Options: 2-3% max. Spreads: 2% max (max loss = debit paid).
    MAX_EQUITY_POSITION_PCT: float = 0.05
    MAX_OPTION_POSITION_PCT: float = 0.02   # % of portfolio per single-leg options trade
    MAX_SPREAD_POSITION_PCT: float = 0.02   # % of portfolio per spread (max loss = debit)

    # Maximum simultaneous open positions
    MAX_OPEN_POSITIONS: int = 10

    # ── Stop loss ──────────────────────────────────────────────────────────────
    # For options: exit if position loses more than this % of premium paid.
    # Research: cutting losers at 50% of premium preserves capital better than
    # holding to expiry hoping for recovery.
    STOP_LOSS_PCT: float = 0.50             # exit options if down 50% of premium paid
    EQUITY_STOP_LOSS_PCT: float = 0.02      # exit equity if down 2%

    # ── Profit taking ─────────────────────────────────────────────────────────
    # Research (tastytrade, CBOE): taking profit at 50% of max gain on options
    # produces better risk-adjusted returns than holding to expiry.
    TAKE_PROFIT_PCT: float = 1.00           # exit at 100% gain on premium (2× paid)

    # ── DTE (Days to Expiration) ───────────────────────────────────────────────
    # Sweet spot for premium buyers: 21-45 DTE.
    # < 21 DTE: gamma risk spikes, move needed is too precise.
    # > 45 DTE: too much premium at risk for too long.
    # Spreads: 30-45 DTE optimal for theta decay rate.
    MIN_DTE: int = 21
    MAX_DTE: int = 45

    # ── Delta targeting ────────────────────────────────────────────────────────
    # Delta = probability of expiring ITM (rough approximation).
    # 0.30-0.50: moderate conviction, not a lottery ticket, not equity-like.
    # < 0.15: far OTM, very low win rate, lottery ticket.
    # > 0.70: deep ITM, expensive, behaves like stock — just trade the stock.
    MIN_DELTA: float = 0.30
    MAX_DELTA: float = 0.50

    # ── IV Rank (Implied Volatility Rank) ──────────────────────────────────────
    # IVR measures current IV relative to its 52-week range (0-100).
    # Premium buyers: buy when IV is relatively cheap (IVR < 30).
    # Avoid buying when IVR > 50 — you're overpaying for volatility.
    # IVR > 80: vol is extremely elevated, premium is very expensive — skip.
    MAX_IV_RANK_TO_BUY: float = 30.0

    # ── Spreads: debit cap ─────────────────────────────────────────────────────
    # Never pay more than 33% of the spread width as net debit.
    # Example: $5-wide spread → max debit $1.65.
    # Paying more shifts the risk/reward unfavourably — you need a large move
    # just to break even, which defeats the purpose of the defined-risk structure.
    MAX_SPREAD_DEBIT_PCT: float = 0.33      # max debit as % of spread width

    # ── Earnings blackout ──────────────────────────────────────────────────────
    # Do not open new options positions within this many days of earnings.
    # IV crush after earnings destroys long premium — the stock can move in
    # your direction and you still lose because IV collapses.
    EARNINGS_BLACKOUT_DAYS: int = 5

    # ── Network rules (populated from Agentberg on startup) ───────────────────
    # Sectors the network has flagged as failing (requires min 3 agent votes).
    # You can add your own permanent blocks here too.
    BLOCKED_SECTORS: list[str] = []

    # Regimes this agent will not trade in
    BLOCKED_REGIMES: list[str] = ["bear"]

    # ── Checks ────────────────────────────────────────────────────────────────

    def check_equity(
        self,
        ticker: str,
        sector: str,
        regime: str | None,
        position_value: float,
        portfolio_equity: float,
        open_positions: int,
    ) -> tuple[bool, str]:
        """Returns (allowed, reason) for equity trades."""
        if sector in self.BLOCKED_SECTORS:
            return False, f"{sector} blocked by network consensus"
        if regime and regime in self.BLOCKED_REGIMES:
            return False, f"Regime '{regime}' blocked — no new longs"
        if open_positions >= self.MAX_OPEN_POSITIONS:
            return False, f"At max positions ({self.MAX_OPEN_POSITIONS})"
        if portfolio_equity > 0:
            pct = position_value / portfolio_equity
            if pct > self.MAX_EQUITY_POSITION_PCT:
                return False, f"Position {pct:.1%} exceeds {self.MAX_EQUITY_POSITION_PCT:.1%} limit"
        return True, "ok"

    def check_option(
        self,
        ticker: str,
        sector: str,
        regime: str | None,
        portfolio_equity: float,
        open_positions: int,
        premium: float,
        dte: int,
        delta: float,
        iv_rank: float | None = None,
    ) -> tuple[bool, str]:
        """Returns (allowed, reason) for single-leg options trades."""
        if sector in self.BLOCKED_SECTORS:
            return False, f"{sector} blocked by network consensus"
        if regime and regime in self.BLOCKED_REGIMES:
            return False, f"Regime '{regime}' blocked — no new longs"
        if open_positions >= self.MAX_OPEN_POSITIONS:
            return False, f"At max positions ({self.MAX_OPEN_POSITIONS})"
        if dte < self.MIN_DTE:
            return False, f"{dte} DTE below minimum {self.MIN_DTE} — gamma risk too high"
        if dte > self.MAX_DTE:
            return False, f"{dte} DTE above maximum {self.MAX_DTE}"
        if not (self.MIN_DELTA <= abs(delta) <= self.MAX_DELTA):
            return False, f"Delta {delta:.2f} outside target range {self.MIN_DELTA}-{self.MAX_DELTA}"
        if iv_rank is not None and iv_rank > self.MAX_IV_RANK_TO_BUY:
            return False, f"IV Rank {iv_rank:.0f} too high — premium too expensive (max {self.MAX_IV_RANK_TO_BUY})"
        cost = premium * 100  # 1 contract = 100 shares
        if portfolio_equity > 0:
            pct = cost / portfolio_equity
            if pct > self.MAX_OPTION_POSITION_PCT:
                return False, f"Premium cost {pct:.1%} exceeds {self.MAX_OPTION_POSITION_PCT:.1%} limit"
        return True, "ok"

    def check_spread(
        self,
        ticker: str,
        sector: str,
        regime: str | None,
        portfolio_equity: float,
        open_positions: int,
        net_debit: float,
        spread_width: float,
        dte: int,
    ) -> tuple[bool, str]:
        """Returns (allowed, reason) for debit spread trades."""
        if sector in self.BLOCKED_SECTORS:
            return False, f"{sector} blocked by network consensus"
        if regime and regime in self.BLOCKED_REGIMES:
            return False, f"Regime '{regime}' blocked — no new longs"
        if open_positions >= self.MAX_OPEN_POSITIONS:
            return False, f"At max positions ({self.MAX_OPEN_POSITIONS})"
        if dte < self.MIN_DTE:
            return False, f"{dte} DTE below minimum {self.MIN_DTE}"
        if dte > self.MAX_DTE:
            return False, f"{dte} DTE above maximum {self.MAX_DTE}"
        if spread_width > 0:
            debit_pct = net_debit / spread_width
            if debit_pct > self.MAX_SPREAD_DEBIT_PCT:
                return False, f"Debit {debit_pct:.0%} of spread width exceeds {self.MAX_SPREAD_DEBIT_PCT:.0%} cap"
        max_loss = net_debit * 100  # per contract
        if portfolio_equity > 0:
            pct = max_loss / portfolio_equity
            if pct > self.MAX_SPREAD_POSITION_PCT:
                return False, f"Max loss {pct:.1%} exceeds {self.MAX_SPREAD_POSITION_PCT:.1%} limit"
        return True, "ok"

    # Legacy method — kept for backward compatibility with equity-only agents
    def check(self, ticker, sector, regime, position_value, portfolio_equity, open_positions):
        return self.check_equity(ticker, sector, regime, position_value, portfolio_equity, open_positions)
