"""Part B — Multi-timeframe trend-following breakout on high-beta stocks.

Entry requires three things to line up:

1. **Daily uptrend**  — close above its 5-day moving average.
2. **Weekly uptrend** — weekly close above its 3-week moving average (the
   higher-timeframe filter).
3. **Bullish breakout** — today is a green bar following a red bar and closes
   above the prior close/high.

Risk is managed per trade with an ATR (Average True Range) bracket:
take-profit at ``+atr_tp_mult * ATR``, stop-loss at ``-atr_sl_mult * ATR``,
and a time-stop after ``max_hold_bars`` bars.

This is the strategy that never ran in the original notebook because of the
yfinance MultiIndex-column bug; here it consumes ``data.download_ohlcv`` which
returns clean single-level columns, so it works.
"""
from __future__ import annotations

import pandas as pd

try:  # works both as `python -m src.breakout` and `from src import breakout`
    from .data import download_ohlcv
except ImportError:  # pragma: no cover - fallback for direct script execution
    from data import download_ohlcv


def average_true_range(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder-style ATR via a simple rolling mean of True Range."""
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Attach trend, breakout, long_signal and ATR columns to a daily frame."""
    df = df.copy()

    # Daily uptrend
    df["daily_uptrend"] = df["Close"] > df["Close"].rolling(5).mean()

    # Weekly uptrend, mapped back onto daily rows
    weekly = (
        df.set_index("Date")
        .resample("W")
        .agg({"Open": "first", "High": "max", "Low": "min",
              "Close": "last", "Volume": "sum"})
        .dropna()
        .reset_index()
    )
    weekly["weekly_uptrend"] = weekly["Close"] > weekly["Close"].rolling(3).mean()
    df = pd.merge_asof(
        df.sort_values("Date"),
        weekly[["Date", "weekly_uptrend"]].sort_values("Date"),
        on="Date",
        direction="backward",
    )
    df["weekly_uptrend"] = df["weekly_uptrend"].ffill()

    # Bullish breakout: green bar after a red bar, closing above prior close/high
    bull = df["Close"] > df["Open"]
    prev_bear = df["Close"].shift(1) < df["Open"].shift(1)
    breakout = bull & prev_bear & (
        (df["Close"] > df["Close"].shift(1)) | (df["Close"] > df["High"].shift(1))
    )
    df["long_signal"] = df["daily_uptrend"] & df["weekly_uptrend"] & breakout

    df["atr"] = average_true_range(df)
    return df


def backtest_breakout(
    df: pd.DataFrame,
    atr_tp_mult: float = 2.0,
    atr_sl_mult: float = 1.0,
    max_hold_bars: int = 10,
) -> pd.DataFrame:
    """Simulate ATR-bracketed long trades. Returns a per-trade DataFrame."""
    df = df.reset_index(drop=True)
    trades = []

    for i in range(len(df) - 1):
        if not df.loc[i, "long_signal"]:
            continue
        atr = df.loc[i, "atr"]
        if pd.isna(atr):
            continue

        entry_idx = i + 1
        entry_price = df.loc[entry_idx, "Open"]
        tp = entry_price + atr_tp_mult * atr
        sl = entry_price - atr_sl_mult * atr

        exit_price, status = None, "Timeout"
        last = min(entry_idx + max_hold_bars, len(df) - 1)
        for j in range(entry_idx, last + 1):
            if df.loc[j, "High"] >= tp:
                exit_price, status = tp, "TP"
                break
            if df.loc[j, "Low"] <= sl:
                exit_price, status = sl, "SL"
                break
        if exit_price is None:
            exit_price = df.loc[last, "Close"]

        trades.append({
            "entry_time": df.loc[entry_idx, "Date"],
            "exit_time": df.loc[last, "Date"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": exit_price - entry_price,
            "result": status,
        })

    return pd.DataFrame(trades)


def run_ticker(ticker: str, start: str, end: str | None, **bt_kwargs) -> pd.DataFrame:
    """Download, sign, and backtest one ticker end to end."""
    df = download_ohlcv(ticker, start=start, end=end, interval="1d")
    if df.empty:
        return pd.DataFrame()
    return backtest_breakout(add_signals(df), **bt_kwargs)
