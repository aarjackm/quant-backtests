"""Unit tests on synthetic data — prove the logic is correct without network.

These assert exact numbers, so they pin down the two bug fixes:
  * pairs trade: realized PnL accumulates correctly across trades
  * breakout:    ATR take-profit / stop-loss exits fire at the right price
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pairs_trade import backtest_spread, inverse_vol_weights  # noqa: E402
from breakout import average_true_range, backtest_breakout  # noqa: E402


# --------------------------------------------------------------------------- #
# Part A — pairs trade
# --------------------------------------------------------------------------- #
def test_inverse_vol_weights_sum_to_one():
    returns = pd.DataFrame({"A": [0.01, -0.01, 0.02], "B": [0.05, -0.05, 0.04]})
    w = inverse_vol_weights(returns)
    assert w.sum() == pytest.approx(1.0)
    # The lower-vol asset (A) must get the larger weight.
    assert w["A"] > w["B"]


def test_backtest_spread_single_trade():
    # z crosses +2 at i=1 (enter short), reverts below 0.5 at i=3 (exit).
    spread = pd.Series([10.0, 12.0, 11.0, 9.0, 9.0])
    z = pd.Series([0.0, 3.0, 1.0, 0.0, 0.0])
    eq = backtest_spread(spread, z, entry_z=2.0, exit_z=0.5)

    assert eq.iloc[0] == 0.0           # flat before entry
    assert eq.iloc[2] == pytest.approx(1.0)   # open short, marked to market: (11-12)*-1
    # Exit at 9 from short entry 12 -> realized (9-12)*-1 = +3
    assert eq.iloc[-1] == pytest.approx(3.0)


def test_backtest_spread_accumulates_two_trades():
    # Two complete short trades; realized PnL must ADD, not get overwritten
    # (this is exactly what the original buggy accounting got wrong).
    spread = pd.Series([10, 13, 9, 10, 13, 9, 9], dtype=float)
    z = pd.Series([0, 3, 0, 0, 3, 0, 0], dtype=float)
    eq = backtest_spread(spread, z, entry_z=2.0, exit_z=0.5)
    # Trade 1: short @13 -> cover @9 = +4. Trade 2: short @13 -> cover @9 = +4.
    assert eq.iloc[-1] == pytest.approx(8.0)


# --------------------------------------------------------------------------- #
# Part B — breakout
# --------------------------------------------------------------------------- #
def test_average_true_range_simple():
    df = pd.DataFrame({
        "High":  [10, 11, 12],
        "Low":   [9, 10, 11],
        "Close": [9.5, 10.5, 11.5],
    })
    atr = average_true_range(df, period=2)
    # TR[1] = max(11-10, |11-9.5|, |10-9.5|) = 1.5 ; TR[2] = max(1, 1.5, 0.5) = 1.5
    assert atr.iloc[-1] == pytest.approx(1.5)


def _bracket_df(high_seq, low_seq):
    """Build a minimal signed frame: signal on row 0, atr=1, entry on row 1."""
    n = len(high_seq)
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open":  [100.0] * n,
        "High":  high_seq,
        "Low":   low_seq,
        "Close": [100.0] * n,
        "long_signal": [True] + [False] * (n - 1),
        "atr": [1.0] * n,
    })


def test_breakout_take_profit_exit():
    # entry 100, atr 1 -> tp 102, sl 99. High hits 103 on bar 2 -> TP, pnl +2.
    df = _bracket_df([100, 101, 103, 100], [100, 100, 102, 99])
    trades = backtest_breakout(df, atr_tp_mult=2.0, atr_sl_mult=1.0)
    assert len(trades) == 1
    assert trades.loc[0, "result"] == "TP"
    assert trades.loc[0, "pnl"] == pytest.approx(2.0)


def test_breakout_stop_loss_exit():
    # entry 100, atr 1 -> sl 99. Low hits 98 on bar 1 -> SL, pnl -1.
    df = _bracket_df([100, 100, 100, 100], [100, 98, 98, 98])
    trades = backtest_breakout(df, atr_tp_mult=2.0, atr_sl_mult=1.0)
    assert len(trades) == 1
    assert trades.loc[0, "result"] == "SL"
    assert trades.loc[0, "pnl"] == pytest.approx(-1.0)
