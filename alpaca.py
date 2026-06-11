"""
alpaca.py — Pure Alpaca broker wrapper. No strategy logic here.

Covers equities and options on the same account.
Paper trading by default — switch ALPACA_BASE_URL to live when ready.

Options require Level 2 approval on Alpaca:
  alpaca.markets → Account → Options Trading → Enable
  Paper account approval is instant.
"""

import datetime
import httpx


class AlpacaClient:

    def __init__(self, api_key: str, secret_key: str, base_url: str):
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }
        self._base = base_url.rstrip("/")

    def _get(self, path: str, params: dict = None) -> dict | list:
        with httpx.Client(timeout=10) as c:
            r = c.get(f"{self._base}{path}", headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, payload: dict) -> dict:
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{self._base}{path}", headers=self._headers, json=payload)
            r.raise_for_status()
            return r.json()

    def _delete(self, path: str) -> dict:
        with httpx.Client(timeout=10) as c:
            r = c.delete(f"{self._base}{path}", headers=self._headers)
            r.raise_for_status()
            return r.json()

    # ── Account ────────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        return self._get("/v2/account")

    # ── Positions ──────────────────────────────────────────────────────────────

    def get_positions(self) -> list:
        return self._get("/v2/positions")

    def get_equity_positions(self) -> list:
        return [p for p in self.get_positions() if p.get("asset_class") == "us_equity"]

    def get_option_positions(self) -> list:
        return [p for p in self.get_positions() if p.get("asset_class") == "us_option"]

    def close_position(self, symbol: str) -> dict:
        return self._delete(f"/v2/positions/{symbol}")

    # ── Market data ────────────────────────────────────────────────────────────

    def get_bars(self, ticker: str, timeframe: str = "1Day", limit: int = 40) -> list:
        data = self._get("/v2/stocks/bars", params={
            "symbols": ticker,
            "timeframe": timeframe,
            "limit": limit,
            "feed": "iex",
        })
        return data.get("bars", {}).get(ticker, [])

    def get_snapshot(self, ticker: str) -> dict:
        return self._get(f"/v2/stocks/{ticker}/snapshot")

    # ── Equity orders ──────────────────────────────────────────────────────────

    def submit_order(
        self,
        ticker: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: float = None,
        stop_loss_price: float = None,
    ) -> dict:
        payload = {
            "symbol": ticker,
            "qty": qty,
            "side": side,
            "type": order_type,
            "time_in_force": "day",
        }
        if limit_price:
            payload["limit_price"] = str(limit_price)
        if stop_loss_price:
            # Bracket order — Alpaca holds the stop server-side
            payload["order_class"] = "bracket"
            payload["stop_loss"] = {"stop_price": str(round(stop_loss_price, 2))}
        return self._post("/v2/orders", payload)

    def get_recent_closed_orders(self, limit: int = 50, days: int = 7) -> list:
        after = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        try:
            orders = self._get("/v2/orders", params={
                "status": "closed", "limit": limit,
                "after": after, "direction": "desc",
            })
            return [o for o in orders if o.get("filled_at")]
        except Exception:
            return []

    # ── Options ────────────────────────────────────────────────────────────────

    def find_option_contracts(
        self,
        ticker: str,
        option_type: str,
        min_dte: int = 21,
        max_dte: int = 45,
        min_delta: float = 0.30,
        max_delta: float = 0.50,
    ) -> list[dict]:
        """Find contracts matching DTE and delta targets, sorted by delta closest to range midpoint."""
        today = datetime.date.today()
        data = self._get("/v2/options/contracts", params={
            "underlying_symbols": ticker,
            "type": option_type,
            "expiration_date_gte": (today + datetime.timedelta(days=min_dte)).isoformat(),
            "expiration_date_lte": (today + datetime.timedelta(days=max_dte)).isoformat(),
            "limit": 100,
        })
        contracts = data if isinstance(data, list) else data.get("option_contracts", [])
        filtered = [
            c for c in contracts
            if min_delta <= abs(float((c.get("greeks") or {}).get("delta", 0))) <= max_delta
        ]
        mid = (min_delta + max_delta) / 2
        filtered.sort(key=lambda c: abs(abs(float((c.get("greeks") or {}).get("delta", 0))) - mid))
        return filtered

    def get_iv_rank(self, ticker: str) -> float | None:
        """IV rank 0-100. Buy premium when < 30. Returns None if unavailable."""
        try:
            snap = self._get(f"/v2/stocks/{ticker}/snapshot")
            iv = snap.get("impliedVolatility")
            hi = snap.get("impliedVolatilityHigh52Week")
            lo = snap.get("impliedVolatilityLow52Week")
            if iv and hi and lo and (hi - lo) > 0:
                return round(((iv - lo) / (hi - lo)) * 100, 1)
        except Exception:
            pass
        return None

    def submit_option_single(
        self, symbol: str, qty: int, side: str, limit_price: float,
        time_in_force: str = "day",
    ) -> dict:
        """Single-leg options order. Always limit — market orders get wide fills."""
        return self._post("/v2/orders", {
            "symbol": symbol, "qty": str(qty), "side": side,
            "type": "limit", "time_in_force": time_in_force,
            "limit_price": str(round(limit_price, 2)),
        })

    def submit_option_spread(
        self, buy_symbol: str, sell_symbol: str, qty: int, net_debit: float,
    ) -> dict:
        """Two-leg debit spread. net_debit = max you'll pay (buy leg - sell leg premium)."""
        return self._post("/v2/orders", {
            "type": "limit", "order_class": "mleg",
            "time_in_force": "day", "limit_price": str(round(net_debit, 2)),
            "legs": [
                {"symbol": buy_symbol,  "side": "buy",  "qty": str(qty), "position_intent": "bto"},
                {"symbol": sell_symbol, "side": "sell", "qty": str(qty), "position_intent": "sto"},
            ],
        })
