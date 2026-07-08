"""Unit tests for indicator math and the example momentum strategy."""

import numpy as np
import pandas as pd
import pytest

from atlas_trader.config import StrategyConfig
from atlas_trader.models import Signal
from atlas_trader.strategy.indicators import rsi, sma
from atlas_trader.strategy.momentum_strategy import MomentumStrategy


def test_sma_matches_manual_average() -> None:
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, period=3)
    assert result.iloc[-1] == pytest.approx((3 + 4 + 5) / 3)


def test_rsi_is_bounded_between_0_and_100() -> None:
    rng = np.random.default_rng(0)
    series = pd.Series(100 + rng.standard_normal(200).cumsum())
    values = rsi(series, period=14).dropna()
    assert values.between(0, 100).all()


def _make_flat_then_uptrend_bars(flat_bars: int = 25, trend_bars: int = 25) -> pd.DataFrame:
    """Flat prices followed by a clean uptrend, so the EMA crossover this
    fixture is meant to exercise happens *after* the strategy's warmup
    window rather than before the test even starts observing signals.
    """
    flat = np.full(flat_bars, 100.0)
    up = np.linspace(100, 130, trend_bars)
    prices = np.concatenate([flat, up])
    index = pd.date_range("2026-01-01", periods=len(prices), freq="min")
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.1,
            "low": prices - 0.1,
            "close": prices,
            "volume": 1000,
        },
        index=index,
    )


def test_momentum_strategy_holds_before_warmup() -> None:
    config = StrategyConfig(fast_ma_period=9, slow_ma_period=21, rsi_period=14)
    strategy = MomentumStrategy(config)
    bars = _make_flat_then_uptrend_bars(flat_bars=5, trend_bars=0)

    assert strategy.generate_signal(bars) is Signal.HOLD


def test_momentum_strategy_detects_bullish_crossover() -> None:
    config = StrategyConfig(fast_ma_period=3, slow_ma_period=8, rsi_period=5, rsi_overbought=90)
    strategy = MomentumStrategy(config)
    bars = _make_flat_then_uptrend_bars()

    signals = [
        strategy.generate_signal(bars.iloc[: i + 1]) for i in range(strategy.warmup_bars, len(bars))
    ]
    assert Signal.LONG in signals
