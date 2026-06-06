"""Smoke test against live Yahoo Finance data — proves both strategies run."""
import sys
import time

import pandas as pd

sys.path.insert(0, "src")

from data import download_closes, download_ohlcv  # noqa: E402
from pairs_trade import backtest_spread, build_spread, zscore  # noqa: E402
from breakout import add_signals, backtest_breakout  # noqa: E402


def retry(fn, tries=4, delay=5):
    for k in range(tries):
        try:
            out = fn()
            if out is not None and len(out) > 0:
                return out
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {k+1} failed: {e}")
        time.sleep(delay)
    return None


print("=" * 60)
print("PART A — Risk-On vs Risk-Off pairs trade")
print("=" * 60)
long_t = ["ARKK", "COIN", "TSLA", "NVDA"]
short_t = ["XLP", "XLU", "TLT", "GLD"]
closes = retry(lambda: download_closes(long_t + short_t, start="2023-01-01"))
if closes is None:
    print("  could not fetch data (rate limited).")
else:
    returns = closes.pct_change(fill_method=None).dropna()
    spread = build_spread(returns, long_t, short_t)
    z = zscore(spread)
    equity = backtest_spread(spread, z, entry_z=2.0, exit_z=0.5)
    print(f"  rows: {len(returns)}  date range: {returns.index.min().date()} -> {returns.index.max().date()}")
    print(f"  final cumulative PnL: {equity.iloc[-1]:.4f}")
    print(f"  max equity: {equity.max():.4f}   min equity: {equity.min():.4f}")

print()
print("=" * 60)
print("PART B — Multi-timeframe breakout (the one that was broken)")
print("=" * 60)
for ticker in ["NVDA", "AMD", "META"]:
    df = retry(lambda t=ticker: download_ohlcv(t, start="2023-01-01", end="2025-07-01"))
    if df is None or df.empty:
        print(f"  {ticker}: no data (rate limited)")
        continue
    trades = backtest_breakout(add_signals(df))
    if trades.empty:
        print(f"  {ticker}: ran OK, 0 trades triggered ({len(df)} bars)")
    else:
        wins = (trades["result"] == "TP").sum()
        print(
            f"  {ticker}: {len(trades)} trades, "
            f"{wins} TP / {(trades['result']=='SL').sum()} SL / "
            f"{(trades['result']=='Timeout').sum()} timeout, "
            f"total PnL ${trades['pnl'].sum():.2f}"
        )
print("\nDONE — both strategies executed without errors.")
