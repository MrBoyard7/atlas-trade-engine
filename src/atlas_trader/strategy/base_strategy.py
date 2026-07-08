"""Strategy interface.

A strategy consumes a rolling window of OHLCV bars and returns a
trading signal. Concrete strategies must never touch broker or risk
logic directly -- `TradingEngine` wires everything together, so a new
rule-set can be dropped in without changing execution or risk code.
"""

from __future__ import annotations

import abc

import pandas as pd

from atlas_trader.models import Signal


class BaseStrategy(abc.ABC):
    @abc.abstractmethod
    def generate_signal(self, bars: pd.DataFrame) -> Signal:
        """Return a signal given a DataFrame indexed by timestamp with
        columns: open, high, low, close, volume.
        """

    @property
    @abc.abstractmethod
    def warmup_bars(self) -> int:
        """Minimum number of bars required before signals are valid."""
