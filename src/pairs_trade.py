"""Part A — Risk-On vs Risk-Off pairs trade (z-score mean reversion).

Idea
----
Build a *risk-on* basket (high-beta growth/crypto names) and a *risk-off*
basket (defensive sectors, bonds, gold), each inverse-volatility weighted so no
single name dominates. The **spread** = risk_on_return - risk_off_return is the
tradable series. When the spread's z-score gets extreme it tends to revert:

* z >  entry_z  -> spread unusually high  -> **short** the spread (position -1)
* z < -entry_z  -> spread unusually low   -> **long**  the spread (position +1)
* |z| < exit_z  -> reverted to the mean   -> flatten

PnL accounting (the bug that was fixed)
---------------------------------------
The original notebook tracked PnL with ``current_pnl += unrealized - current_pnl``
*while a trade was open*, which silently overwrites accumulated **realized** PnL
with the latest single-trade **unrealized** value — so the equity curve was wrong
whenever more than one trade had occurred.

The correct accounting keeps two things separate and sums them for the curve:

    equity[t] = realized_pnl_so_far + mark_to_market_of_open_trade
"""
from __future__ import annotations

import pandas as pd


def inverse_vol_weights(returns: pd.DataFrame) -> pd.Series:
    """Inverse-volatility weights that sum to 1 (lower vol -> larger weight)."""
    vols = returns.std()
    w = 1.0 / vols
    return w / w.sum()


def build_spread(
    returns: pd.DataFrame,
    long_tickers: list[str],
    short_tickers: list[str],
) -> pd.Series:
    """Inverse-vol-weighted long-basket return minus short-basket return."""
    lw = inverse_vol_weights(returns[long_tickers])
    sw = inverse_vol_weights(returns[short_tickers])
    long_basket = (returns[long_tickers] * lw).sum(axis=1)
    short_basket = (returns[short_tickers] * sw).sum(axis=1)
    return long_basket - short_basket


def zscore(series: pd.Series) -> pd.Series:
    """Plain full-sample z-score (kept simple to match the notebook intent)."""
    return (series - series.mean()) / series.std(ddof=0)


def backtest_spread(
    spread: pd.Series,
    spread_z: pd.Series,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
) -> pd.Series:
    """Run the mean-reversion backtest and return a cumulative-equity series.

    The returned series is realized PnL plus the mark-to-market of any open
    position at each timestamp, indexed like ``spread``.
    """
    realized = 0.0
    position = 0          # -1 short spread, 0 flat, +1 long spread
    entry_price = 0.0
    equity = []

    z = spread_z.to_numpy()
    px = spread.to_numpy()

    for i in range(len(px)):
        if position == 0:
            if z[i] > entry_z:
                position, entry_price = -1, px[i]
            elif z[i] < -entry_z:
                position, entry_price = 1, px[i]
        else:
            if abs(z[i]) < exit_z:
                realized += (px[i] - entry_price) * position
                position = 0

        mark_to_market = (px[i] - entry_price) * position if position != 0 else 0.0
        equity.append(realized + mark_to_market)

    return pd.Series(equity, index=spread.index, name="equity")
