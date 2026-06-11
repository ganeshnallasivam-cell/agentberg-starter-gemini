"""Alpaca broker connector — paper trading by default."""

import datetime
import httpx


class AlpacaConnector:

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

    def get_account(self) -> dict:
        return self._get("/v2/account")

    def get_positions(self) -> list:
        return self._get("/v2/positions")

    def get_bars(self, ticker: str, timeframe: str = "1Day", limit: int = 20) -> list:
        data = self._get("/v2/stocks/bars", params={
            "symbols": ticker,
            "timeframe": timeframe,
            "limit": limit,
            "feed": "iex",
        })
        return data.get("bars", {}).get(ticker, [])

    def submit_order(
        self,
        ticker: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: float = None,
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
        return self._post("/v2/orders", payload)

    def get_recent_closed_orders(self, limit: int = 50) -> list:
        """Returns filled orders from the last 7 days, most recent first."""
        after = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        try:
            orders = self._get("/v2/orders", params={
                "status": "closed",
                "limit": limit,
                "after": after,
                "direction": "desc",
            })
            return [o for o in orders if o.get("filled_at")]
        except Exception:
            return []

    def close_position(self, ticker: str) -> dict:
        with httpx.Client(timeout=10) as c:
            r = c.delete(
                f"{self._base}/v2/positions/{ticker}",
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
