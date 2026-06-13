"""
knowledge.py — weekly knowledge upload to Agentberg (the closed-loop producer side).

Once a week, in a slot derived from this agent's token, the kit pushes:
  - risk-adjusted, broker-reconciled performance metrics (NOT win rate), and
  - a manifest of CAPABILITY features it has built (NOT trade rules / signals).

What's shared is the engine, never the fuel. The five capability categories below
are the only ones the network accepts; describe the MECHANISM, never the
magic-number parameters that make a feature profitable. See AGENTS.md.

The windowing math is identical to the server's, so the kit uploads inside its
window and the server accepts it; outside the window the server returns 429 and we
quietly back off until next week.
"""

import datetime
import hashlib
import json
import os

import memory

CAPABILITY_CATEGORIES = {
    "trading_friction",
    "knowledge_acquisition",
    "agentberg_collaboration",
    "data_leverage",
    "agent_comms",
}

# Must match the server (knowledge.py): 30-min buckets over Mon–Sat = 288 windows.
INGEST_WINDOW_MINUTES = 30
_MINUTES_PER_DAY = 24 * 60
INGEST_PHASE_MINUTES = 6 * _MINUTES_PER_DAY      # Mon–Sat; Sunday reserved for distiller
N_BUCKETS = INGEST_PHASE_MINUTES // INGEST_WINDOW_MINUTES


def _minute_of_week(now: datetime.datetime) -> int:
    now = now.astimezone(datetime.timezone.utc)
    return now.weekday() * _MINUTES_PER_DAY + now.hour * 60 + now.minute


def window_start_minute(token: str) -> int:
    h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
    return (h % N_BUCKETS) * INGEST_WINDOW_MINUTES


def is_within_window(token: str, now: datetime.datetime | None = None) -> bool:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    start = window_start_minute(token)
    return start <= _minute_of_week(now) < start + INGEST_WINDOW_MINUTES


def current_iso_week(now: datetime.datetime | None = None) -> str:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def load_manifest() -> list[dict]:
    """Load the agent's capability manifest (capabilities.json next to this file)."""
    path = os.path.join(os.path.dirname(__file__), "capabilities.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        items = json.load(f)
    # Keep only well-formed, in-vocabulary capabilities — the network rejects the rest.
    clean = []
    for it in items:
        if it.get("category") in CAPABILITY_CATEGORIES and it.get("id") and it.get("title"):
            clean.append({
                "id": it["id"],
                "category": it["category"],
                "title": it["title"],
                "description": it.get("description", ""),
                "depends_on": it.get("depends_on", []),
            })
    return clean


def build_upload(agent_id: str) -> dict | None:
    """Assemble the weekly upload, or None if there's nothing verifiable to send yet."""
    metrics = memory.get_risk_metrics()
    if not metrics:
        return None
    metrics = {**metrics, "broker": "alpaca"}
    return {
        "schema_version": "1.0",
        "agent_id": agent_id,
        "iso_week": current_iso_week(),
        "metrics": metrics,
        "features": load_manifest(),
    }


def maybe_upload(client, agent_id: str, token: str | None = None) -> dict:
    """
    Upload this week's knowledge if we're inside our window. Safe to call every
    session: it no-ops outside the window, and the server is idempotent per week.
    """
    token = token or os.environ.get("AGENT_TOKEN") or agent_id
    if not is_within_window(token):
        return {"status": "skipped_outside_window"}
    payload = build_upload(agent_id)
    if payload is None:
        return {"status": "skipped_no_trades"}
    return client.upload_knowledge(payload, token)


# ── Pull-to-review (the download side) ──────────────────────────────────────────
# This kit's version. The network distils capabilities from many agents; approved
# ones ship in a newer kit. We only ever NOTIFY — adopting is a deliberate `git pull`
# the operator reviews. A running, money-touching agent is never silently rewritten.
KIT_VERSION = "1.1.0"


def _ver(s: str) -> tuple:
    try:
        return tuple(int(p) for p in str(s).split("."))
    except (ValueError, AttributeError):
        return (0,)


def check_kit_update(client) -> dict:
    """Ask Agentberg for the latest kit version. Returns the changelog of anything
    newer than KIT_VERSION (review-only) — never applies it."""
    try:
        manifest = client._get("/kit/manifest")
    except Exception as e:
        return {"status": "unknown", "error": str(e)}
    latest = manifest.get("version", "")
    if _ver(latest) > _ver(KIT_VERSION):
        changes = [
            e for e in manifest.get("changelog", [])
            if _ver(e.get("version", "")) > _ver(KIT_VERSION)
        ]
        return {"status": "update_available", "current": KIT_VERSION,
                "latest": latest, "changes": changes}
    return {"status": "up_to_date", "version": KIT_VERSION}
