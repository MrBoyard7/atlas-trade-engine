"""Example moving-average / RSI momentum strategy.

This is a REFERENCE IMPLEMENTATION only, included so the engine is
runnable end-to-end out of the box. Replace the logic inside
`generate_signal` with your own entry/exit rules -- the rest of the
engine (risk management, execution, reconnection, safe shutdown) does
not need to change as long as the new class still implements
`BaseStrategy`.
"""

from __future__ import annotations

import pandas as pd

from atlas_trader.config import StrategyConfig
from atlas_trader.logger import get_logger
from atlas_trader.models import Signal
from atlas_trader.strategy.base_strategy import BaseStrategy
from atlas_trader.strategy.indicators import ema, rsi

logger = get_logger("strategy")


class MomentumStrategy(BaseStrategy):
    """Goes long on a bullish EMA crossover (filtered by RSI) and short
    on a bearish crossover, ignoring signals confirmed while RSI is
    already in overbought/oversold territory.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self._config = config

    @property
    def warmup_bars(self) -> int:
        return max(self._config.slow_ma_period, self._config.rsi_period) + 1

    def generate_signal(self, bars: pd.DataFrame) -> Signal:
        if len(bars) < self.warmup_bars:
            return Signal.HOLD

        close = bars["close"]
        fast = ema(close, self._config.fast_ma_period)
        slow = ema(close, self._config.slow_ma_period)
        momentum = rsi(close, self._config.rsi_period)

        crossed_up = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
        crossed_down = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]

        if crossed_up and momentum.iloc[-1] < self._config.rsi_overbought:
            logger.debug("Bullish crossover detected, RSI=%.2f", momentum.iloc[-1])
            return Signal.LONG

        if crossed_down and momentum.iloc[-1] > self._config.rsi_oversold:
            logger.debug("Bearish crossover detected, RSI=%.2f", momentum.iloc[-1])
            return Signal.SHORT

        return Signal.HOLD
