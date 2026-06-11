"""
Alpaca options connector — single-leg (premium buyer) and multi-leg (spreads).
Paper trading by default. Same Alpaca account as equities.

Options require Level 2 options approval on your Alpaca account.
Enable at: alpaca.markets → Account → Options Trading
"""

import datetime
import httpx


class OptionsConnector:

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

    def find_contracts(
        self,
        ticker: str,
        option_type: str,        # "call" or "put"
        min_dte: int = 21,
        max_dte: int = 45,
        min_delta: float = 0.30,
        max_delta: float = 0.50,
    ) -> list[dict]:
        """Find options contracts matching DTE and delta targets.

        Default range (21-45 DTE, 0.30-0.50 delta) is the research-backed
        sweet spot for premium buyers — enough time for the move, not a lottery ticket.
        """
        today = datetime.date.today()
        params = {
            "underlying_symbols": ticker,
            "type": option_type,
            "expiration_date_gte": (today + datetime.timedelta(days=min_dte)).isoformat(),
            "expiration_date_lte": (today + datetime.timedelta(days=max_dte)).isoformat(),
            "limit": 100,
        }
        data = self._get("/v2/options/contracts", params)
        contracts = data if isinstance(data, list) else data.get("option_contracts", [])

        # Filter by delta
        result = []
        for c in contracts:
            greeks = c.get("greeks") or {}
            delta = abs(float(greeks.get("delta", 0)))
            if min_delta <= delta <= max_delta:
                result.append(c)

        # Sort by delta closest to midpoint of range
        mid = (min_delta + max_delta) / 2
        result.sort(key=lambda c: abs(abs(float((c.get("greeks") or {}).get("delta", 0))) - mid))
        return result

    def get_contract(self, symbol: str) -> dict:
        """Get a specific contract with greeks. symbol = OCC format e.g. AAPL260620C00200000"""
        return self._get(f"/v2/options/contracts/{symbol}")

    def get_iv_rank(self, ticker: str) -> float | None:
        """Approximate IV rank from current vs 52-week IV range.

        Returns 0-100. Buy premium when < 30. Avoid buying when > 50.
        Returns None if data unavailable.
        """
        try:
            snapshot = self._get(f"/v2/stocks/{ticker}/snapshot")
            iv = snapshot.get("impliedVolatility")
            iv_high = snapshot.get("impliedVolatilityHigh52Week")
            iv_low = snapshot.get("impliedVolatilityLow52Week")
            if iv and iv_high and iv_low and (iv_high - iv_low) > 0:
                return round(((iv - iv_low) / (iv_high - iv_low)) * 100, 1)
        except Exception:
            pass
        return None

    def submit_single_leg(
        self,
        symbol: str,
        qty: int,
        side: str,              # "buy" or "sell"
        limit_price: float,
        time_in_force: str = "day",
    ) -> dict:
        """Place a single-leg options order (premium buyer).

        Always use limit orders for options — market orders get wide fills.
        symbol: OCC format e.g. AAPL260620C00200000
        """
        return self._post("/v2/orders", {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": "limit",
            "time_in_force": time_in_force,
            "limit_price": str(round(limit_price, 2)),
        })

    def submit_spread(
        self,
        buy_symbol: str,
        sell_symbol: str,
        qty: int,
        net_debit: float,
    ) -> dict:
        """Place a two-leg debit spread (bull call or bear put).

        net_debit: max you'll pay for the spread (buy leg - sell leg premium).
        Rule: never pay more than 33% of spread width.
        """
        return self._post("/v2/orders", {
            "type": "limit",
            "order_class": "mleg",
            "time_in_force": "day",
            "limit_price": str(round(net_debit, 2)),
            "legs": [
                {
                    "symbol": buy_symbol,
                    "side": "buy",
                    "qty": str(qty),
                    "position_intent": "bto",
                },
                {
                    "symbol": sell_symbol,
                    "side": "sell",
                    "qty": str(qty),
                    "position_intent": "sto",
                },
            ],
        })

    def get_option_positions(self) -> list[dict]:
        """All open options positions."""
        positions = self._get("/v2/positions")
        return [p for p in positions if p.get("asset_class") == "us_option"]

    def close_option_position(self, symbol: str) -> dict:
        """Market close an options position."""
        with httpx.Client(timeout=10) as c:
            r = c.delete(f"{self._base}/v2/positions/{symbol}", headers=self._headers)
            r.raise_for_status()
            return r.json()
