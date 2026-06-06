"""Price-data loading helpers.

The whole reason this module exists: modern ``yfinance`` returns a
**MultiIndex** column frame ``(field, ticker)`` even for a single ticker, e.g.
``('Close', 'TSLA')`` instead of plain ``'Close'``. Downstream code that does
``df["Close"]`` or ``.agg({"Open": "first"})`` then breaks with
``"Column(s) ['Close', ...] do not exist"``.

These helpers download the data and immediately flatten the columns to a clean,
single-level OHLCV layout so the rest of the codebase never has to think about
it.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _flatten_single_ticker(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a single-ticker MultiIndex column frame to plain field names."""
    if isinstance(df.columns, pd.MultiIndex):
        # Keep the field level ('Open'/'High'/...), drop the ticker level.
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def download_ohlcv(
    ticker: str,
    start: str,
    end: str | None = None,
    interval: str = "1d",
    auto_adjust: bool = True,
) -> pd.DataFrame:
    """Download one ticker and return a clean OHLCV frame with a ``Date`` column.

    Columns are guaranteed to be ``Open, High, Low, Close, Volume`` (plus a
    ``Date`` column after the reset_index), regardless of the yfinance version.
    Returns an empty frame if no data came back.
    """
    df = yf.download(
        ticker,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=auto_adjust,
        progress=False,
    )
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", *_OHLCV])

    df = _flatten_single_ticker(df)
    df = df.reset_index()
    # The index name can be 'Date' (daily) or 'Datetime' (intraday) — normalise.
    df = df.rename(columns={"Datetime": "Date", "index": "Date"})
    return df


def download_closes(
    tickers: list[str],
    start: str,
    end: str | None = None,
    interval: str = "1d",
    auto_adjust: bool = True,
) -> pd.DataFrame:
    """Download many tickers and return a frame of close prices (one col/ticker).

    Used by the pairs trade, which only needs closes to build baskets.
    """
    data = yf.download(
        tickers,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=auto_adjust,
        progress=False,
    )
    # With multiple tickers yfinance returns MultiIndex (field, ticker); pick
    # the Close level. With one ticker it may already be single-level.
    if isinstance(data.columns, pd.MultiIndex):
        closes = data["Close"]
    else:
        closes = data[["Close"]]
        closes.columns = tickers[:1]
    return closes.dropna(how="all")
