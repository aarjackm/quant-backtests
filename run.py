"""Run both backtests from config.yaml and print a summary.

Usage:
    python run.py                 # run both strategies
    python run.py --plot          # also save equity/PnL charts to outputs/

All parameters (tickers, dates, thresholds) come from config.yaml.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

from data import download_closes, download_ohlcv  # noqa: E402
from pairs_trade import backtest_spread, build_spread, zscore  # noqa: E402
from breakout import add_signals, backtest_breakout  # noqa: E402


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run_pairs_trade(cfg: dict, plot: bool) -> None:
    print("=" * 64)
    print("PART A — Risk-On vs Risk-Off pairs trade")
    print("=" * 64)
    long_t, short_t = cfg["long_tickers"], cfg["short_tickers"]
    closes = download_closes(long_t + short_t, start=cfg["start"], end=cfg["end"])
    returns = closes.pct_change(fill_method=None).dropna()
    spread = build_spread(returns, long_t, short_t)
    z = zscore(spread)
    equity = backtest_spread(spread, z, entry_z=cfg["entry_z"], exit_z=cfg["exit_z"])

    print(f"  {len(returns)} days, {returns.index.min().date()} -> {returns.index.max().date()}")
    print(f"  final cumulative PnL: {equity.iloc[-1]:+.4f} (spread units)")

    if plot:
        _plot_pairs(z, equity, cfg)


def run_breakout(cfg: dict, plot: bool) -> None:
    print("=" * 64)
    print("PART B — Multi-timeframe breakout")
    print("=" * 64)
    curves = {}
    for ticker in cfg["tickers"]:
        df = download_ohlcv(ticker, start=cfg["start"], end=cfg["end"])
        if df.empty:
            print(f"  {ticker}: no data, skipping")
            continue
        trades = backtest_breakout(
            add_signals(df),
            atr_tp_mult=cfg["atr_tp_mult"],
            atr_sl_mult=cfg["atr_sl_mult"],
            max_hold_bars=cfg["max_hold_bars"],
        )
        if trades.empty:
            print(f"  {ticker}: 0 trades triggered")
            continue
        wins = (trades["result"] == "TP").sum()
        print(
            f"  {ticker}: {len(trades)} trades, win rate {wins/len(trades):.0%}, "
            f"total PnL ${trades['pnl'].sum():+.2f}"
        )
        curves[ticker] = trades["pnl"].cumsum()

    if plot and curves:
        _plot_breakout(curves)


def _plot_pairs(z, equity, cfg) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    Path("outputs").mkdir(exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    ax1.plot(z.index, z, label="spread z-score")
    ax1.axhline(cfg["entry_z"], color="red", ls="--")
    ax1.axhline(-cfg["entry_z"], color="green", ls="--")
    ax1.set_title("Risk-On vs Risk-Off spread z-score")
    ax1.legend()
    ax2.plot(equity.index, equity, color="black", label="cumulative PnL")
    ax2.axhline(0, color="grey", ls="--")
    ax2.set_title("Pairs-trade equity curve")
    ax2.legend()
    fig.tight_layout()
    fig.savefig("outputs/pairs_trade.png", dpi=120)
    print("  saved outputs/pairs_trade.png")


def _plot_breakout(curves) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    Path("outputs").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 7))
    for ticker, pnl in curves.items():
        ax.plot(pnl.values, label=f"{ticker}")
    ax.set_xlabel("trade number")
    ax.set_ylabel("cumulative PnL ($)")
    ax.set_title("Multi-timeframe breakout — cumulative PnL by ticker")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    fig.savefig("outputs/breakout.png", dpi=120)
    print("  saved outputs/breakout.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the backtests from config.yaml")
    parser.add_argument("--plot", action="store_true", help="save charts to outputs/")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    run_pairs_trade(cfg["pairs_trade"], args.plot)
    print()
    run_breakout(cfg["breakout"], args.plot)


if __name__ == "__main__":
    main()
