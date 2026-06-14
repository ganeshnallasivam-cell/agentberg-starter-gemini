"""
journal.py — your agent's trade journal. PRIVATE to you, the operator.

For every closed trade it shows: the thesis the agent entered on, what it expected, what
actually happened, and the variance — each grounded in the real signal and AI reason,
captured at decision time and held to. This is how the agent earns your trust: it states
an expectation up front and reports honestly against it. Nothing here is uploaded to the
network — the network only ever sees verified outcomes, never your reasoning.

    python journal.py
"""

import memory


def main():
    memory.init_db()
    rows = memory.get_journal(30)
    if not rows:
        print("No closed trades yet — the journal fills in as trades close.")
        return

    print(f"\nTrade journal — last {len(rows)} closed trade(s)\n" + "=" * 60)
    for t in rows:
        print(f"\n{t['symbol']}  [{t.get('sector') or '—'}]   {t.get('opened_at') or '?'} → {t.get('closed_at') or '?'}")
        print(f"  Thesis:    {t.get('entry_thesis') or '—'}")
        exp = f"+{t['expected_pct']:.0%}" if t.get('expected_pct') is not None else "—"
        stop = f"-{t['stop_pct']:.0%}" if t.get('stop_pct') is not None else "—"
        print(f"  Expected:  target {exp} / stop {stop}")
        print(f"  Actual:    {(t.get('pnl_pct') or 0):+.1%}  (${(t.get('pnl') or 0):+,.2f})   [{t.get('exit_reason') or '—'}]")
        if t.get('variance_pct') is not None:
            print(f"  Variance:  {t['variance_pct']:+.1%} vs expectation — {t.get('variance_reason') or ''}")


if __name__ == "__main__":
    main()
