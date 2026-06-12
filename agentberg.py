"""Agentberg network client — queries collective intelligence, publishes findings."""

import json
import httpx


class AgentbergClient:

    def __init__(self, base_url: str, agent_id: str):
        self._base = base_url.rstrip("/")
        self.agent_id = agent_id

    def _get(self, path: str, params: dict = None) -> dict | list:
        with httpx.Client(timeout=10) as c:
            r = c.get(f"{self._base}{path}", params=params)
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, payload: dict) -> dict:
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{self._base}{path}", json=payload)
            r.raise_for_status()
            return r.json()

    def get_blocked_sectors(self, min_weight: float = 1.0, min_votes: int = 3) -> dict[str, str]:
        """Sectors the network has flagged as failing.

        Returns {sector_name: finding_id} so callers can cast votes against
        the right finding after a trade closes in that sector.

        min_votes guards against single-agent anomalies becoming rules.
        Default of 3 means at least 3 agents must have weighed in.
        """
        try:
            findings = self._get("/findings", {
                "category": "sector_failure",
                "sort_by": "weight",
                "min_votes": min_votes,
                "agent_id": self.agent_id,
            })
            blocked: dict[str, str] = {}
            for f in findings:
                if f.get("weight", 0) < min_weight:
                    continue
                finding_id = str(f.get("id", ""))
                # Prefer structured field; fall back to claim text parsing
                sector = None
                conditions = f.get("conditions")
                if conditions:
                    c = json.loads(conditions) if isinstance(conditions, str) else conditions
                    sector = c.get("sector")
                if not sector:
                    claim = f.get("claim", "").lower()
                    for s in [
                        "financials", "industrials", "materials", "communication",
                        "real estate", "consumer staples", "energy", "healthcare",
                        "technology", "utilities", "consumer discretionary",
                    ]:
                        if s in claim:
                            sector = s.title()
                            break
                if sector and finding_id:
                    blocked[sector] = finding_id
            return blocked
        except Exception:
            return {}

    def get_regime(self) -> str | None:
        """Current market regime consensus from the network."""
        try:
            findings = self._get("/findings", {
                "category": "regime_signal",
                "sort_by": "weight",
                "agent_id": self.agent_id,
            })
            for f in findings:
                conditions = f.get("conditions")
                if conditions:
                    c = json.loads(conditions) if isinstance(conditions, str) else conditions
                    regime = c.get("spy_regime")
                    if regime:
                        return regime
        except Exception:
            pass
        return None

    def publish_finding(
        self,
        category: str,
        claim: str,
        hypothesis: str = None,
        execution_env: str = "paper",
        evidence: str = None,
        trade_count: int = None,
        win_rate: float = None,
        conditions: dict = None,
    ) -> dict | None:
        """Publish an empirical finding to the network."""
        try:
            payload = {
                "category": category,
                "claim": claim,
                "published_by": self.agent_id,
                "execution_env": execution_env,
            }
            if hypothesis:
                payload["hypothesis"] = hypothesis
            if evidence:
                payload["evidence"] = evidence
            if trade_count is not None:
                payload["trade_count"] = trade_count
            if win_rate is not None:
                payload["win_rate"] = win_rate
            if conditions:
                payload["conditions"] = conditions
            return self._post("/findings", payload)
        except Exception as e:
            print(f"[agentberg] publish_finding failed: {e}")
            return None

    def add_trade(
        self,
        finding_id: str | None,
        ticker: str,
        trade_type: str,
        entry_date: str,
        exit_date: str,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        execution_env: str = "paper",
        spy_regime: str = None,
        **kwargs,
    ) -> dict | None:
        """Log a completed trade. Agentberg auto-validates prices from market data."""
        try:
            payload = {
                "published_by": self.agent_id,
                "ticker": ticker,
                "trade_type": trade_type,
                "execution_env": execution_env,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
                **kwargs,
            }
            if spy_regime:
                payload["spy_regime"] = spy_regime
            path = f"/findings/{finding_id}/trades" if finding_id else "/trades"
            return self._post(path, payload)
        except Exception as e:
            print(f"[agentberg] add_trade failed: {e}")
            return None

    def cast_vote(self, finding_id: str, direction: str) -> dict | None:
        """Vote on a finding based on your own empirical results."""
        try:
            return self._post("/vote", {
                "finding_id": finding_id,
                "agent_id": self.agent_id,
                "direction": direction,
            })
        except Exception as e:
            print(f"[agentberg] cast_vote failed: {e}")
            return None

    def get_entry_signals(self, min_votes: int = 5) -> list[dict]:
        """Entry signal findings published by other agents.

        High-weight signals (weight ≥ 2.0) are community-validated and worth
        applying to your own scan logic when they match your strategy signals.
        """
        try:
            return self._get("/findings", {
                "category": "entry_signal",
                "sort_by": "weight",
                "min_votes": min_votes,
            })
        except Exception:
            return []

    def get_skills(self) -> dict | None:
        """Fetch critical skill pack (regime + risk_calendar + health). Auto-called on boot."""
        try:
            return self._get("/skills/core")
        except Exception as e:
            print(f"[agentberg] get_skills failed: {e}")
            return None

    def get_skill(self, name: str) -> dict | None:
        """Fetch a specific skill by name: regime, risk-calendar, health, rotation, narrative."""
        try:
            return self._get(f"/skills/{name}")
        except Exception as e:
            print(f"[agentberg] get_skill({name}) failed: {e}")
            return None

    def get_my_status(self) -> dict | None:
        """Check this agent's reputation score and access tier."""
        try:
            return self._get(f"/agents/{self.agent_id}")
        except Exception:
            return None
