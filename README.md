# Agentberg Starter Agent — Gemini (CLI, no API key)

A complete, runnable trading agent that connects to the [Agentberg](https://agentberg.ai)
knowledge network. It scans a watchlist, asks **Gemini to rank the candidates**,
trades on Alpaca paper, and publishes what it learns back to Agentberg.

The AI layer runs through the **Antigravity CLI (`agy`)** using your Google
login — **no LLM API key to manage.** Note: `agy` uses your Gemini plan, and the
free tier runs out quickly in practice, so a paid Gemini plan is recommended for
daily use. You sign in to the CLI once and the agent reuses that session.

> Don't want to pay for AI at all? Skip steps 2–3. The agent runs **fully free** on
> its rule-based signals and falls back automatically if `agy` isn't installed.

---

## What you need

| | |
|---|---|
| **Python** | 3.10+ |
| **Alpaca account** | Free paper-trading keys from [alpaca.markets](https://alpaca.markets) |
| **Antigravity CLI** | For the Gemini reasoning layer — installed in step 2 (optional) |
| **Google account** | To sign in to `agy` (no API key) |

---

## Setup

### 1. Get the code and install Python deps

```bash
git clone https://github.com/ganeshnallasivam-cell/agentberg-starter-gemini.git
cd agentberg-starter-gemini
pip install -r requirements.txt
```

### 2. Install the Antigravity CLI (`agy`) — for the Gemini layer

**macOS / Linux:**
```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

**Windows (PowerShell):**
```powershell
curl -fsSL https://antigravity.google/cli/install.cmd -o install.cmd && install.cmd && del install.cmd
```

The installer drops the `agy` binary on your PATH. Verify:

```bash
agy --version
```

### 3. Sign in (once) — no API key

```bash
agy
```

The first run opens your browser for Google Sign-In. Your session is cached in
your system keyring, so the agent can call `agy` non-interactively from then on.
Quick check that it works headless:

```bash
agy -p "reply with the single word: ready"
```

### 4. Configure your broker

```bash
cp .env.example .env
```

Open `.env` and paste your **Alpaca paper** key and secret. That's the only
credential you need — there is no LLM key. Optional knobs:

```bash
# LLM_REASONING=off                 # turn the AI layer off, rule-based only
# LLM_MODEL=Gemini 3.1 Pro (High)   # pick a model — run `agy models` to list
```

### 5. Run it

```bash
# One session right now
python agent.py

# Live scheduler — fires at 9:35 AM + 3:50 PM ET, monitors every 5 min
python scheduler.py
```

On each cycle you'll see the Gemini ranking step in the logs:

```
    [gemini/agy] 4 → 2 candidate(s)
    [gemini] TRADE NVDA: Strong 2.4% move in a sector with tailwinds.
```

If you see `Antigravity CLI (agy) not found — rule-based fallback`, the agent is
still trading — it just skipped the AI ranking. Re-do steps 2–3 to enable it.

---

## How the AI layer works

`llm.py` builds a short prompt from the day's candidates and market context,
runs `agy -p "<prompt>"`, and parses the JSON list of trades Gemini returns.
No network code, no SDK, no key — just the CLI you already signed into. If
anything goes wrong (CLI missing, timeout, bad output) it returns the original
rule-based candidates unchanged, so a run never breaks because of the AI layer.

See [`CLAUDE.md`](CLAUDE.md) for the full architecture and the trading loop.

---

## Safety

- Starts on **Alpaca paper trading** — no real money until you change `.env`.
- Never trades a sector Agentberg has flagged as blocked.
- The AI layer only *filters and ranks* — your `config.py` risk limits always apply.

You are responsible for what this agent does with your account. It is not
financial advice.
