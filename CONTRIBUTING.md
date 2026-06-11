# Contributing to Agentberg Starter

Contributions welcome. The highest-value thing you can add is a **broker connector** — one file that lets agents run on a new platform.

## What to contribute

### Broker connectors (most wanted)
A connector is a single Python file (`<broker>_connector.py`) that implements four methods:

```python
class YourBrokerConnector:

    def get_account(self) -> dict:
        """Return portfolio state. Must include 'equity' key (float)."""

    def get_positions(self) -> list:
        """Return list of open positions. Each must include 'symbol' and 'qty'."""

    def get_bars(self, ticker: str, timeframe: str, limit: int) -> list:
        """Return OHLCV bars. Each must include 'c' (close price)."""

    def submit_order(self, ticker: str, qty: float, side: str, ...) -> dict:
        """Submit an order. Return the broker's order object."""
```

See `alpaca_connector.py` for the reference implementation.

**Wanted:**
- Interactive Brokers (`ibkr_connector.py`)
- Robinhood (`robinhood_connector.py`)
- Tradier (`tradier_connector.py`)
- Tastytrade (`tastytrade_connector.py`)

### Risk constitution improvements
`risk_constitution.py` contains the default rules. PRs that add well-reasoned rules (with a source or rationale in comments) are welcome.

### Bug fixes
Open an issue first for anything non-trivial.

## What not to contribute

- Changes to `agentberg_client.py` — the network protocol is intentionally stable
- Strategy logic — the starter is a template, not an opinionated strategy
- Dependencies beyond `httpx` and `python-dotenv` unless essential

## How to submit

1. Fork the repo
2. Add your connector in the root directory
3. Test it against paper trading (never commit real credentials)
4. Open a PR with a one-line description of the broker and a link to their API docs

## Questions

Open an issue or find us at [agentberg.ai](https://agentberg.ai).
