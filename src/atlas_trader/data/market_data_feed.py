"""Helper for turning a rolling buffer of `Bar` objects into the
pandas DataFrame shape expected by `BaseStrategy.generate_signal`.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from atlas_trader.models import Bar


def bars_to_dataframe(bars: Iterable[Bar]) -> pd.DataFrame:
    """Convert an iterable of `Bar` objects into a timestamp-indexed
    OHLCV DataFrame, sorted chronologically.
    """
    records = [
        {
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    return df.set_index("timestamp").sort_index()
