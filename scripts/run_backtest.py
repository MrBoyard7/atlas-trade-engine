"""Simple vectorized backtest runner for the example momentum strategy.

Usage:
    python scripts/run_backtest.py path/to/ohlcv.csv

The CSV must have columns: timestamp, open, high, low, close, volume.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from atlas_trader.config import StrategyConfig  # noqa: E402
from atlas_trader.models import Signal  # noqa: E402
from atlas_trader.strategy.momentum_strategy import MomentumStrategy  # noqa: E402

STARTING_CASH = 100_000.0


def run_backtest(csv_path: str) -> None:
    df = pd.read_csv(csv_path, parse_dates=["timestamp"]).set_index("timestamp")
    strategy = MomentumStrategy(StrategyConfig())

    position = 0.0
    cash = STARTING_CASH
    entry_price = 0.0
    trades = 0

    for i in range(strategy.warmup_bars, len(df)):
        window = df.iloc[: i + 1]
        signal = strategy.generate_signal(window)
        price = window["close"].iloc[-1]

        if signal is Signal.LONG and position <= 0:
            if position < 0:
                cash += position * (entry_price - price)  # close short
            position = 1.0
            entry_price = price
            trades += 1
        elif signal is Signal.SHORT and position >= 0:
            if position > 0:
                cash += position * (price - entry_price)  # close long
            position = -1.0
            entry_price = price
            trades += 1

    final_price = df["close"].iloc[-1]
    open_pnl = position * (final_price - entry_price) if position else 0.0

    print(f"Trades executed:              {trades}")
    print(f"Realized cash PnL:            {cash - STARTING_CASH:.2f}")
    print(f"Unrealized PnL (open pos.):   {open_pnl:.2f}")
    print(f"Total PnL:                    {(cash - STARTING_CASH) + open_pnl:.2f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_backtest.py path/to/ohlcv.csv")
        sys.exit(1)
    run_backtest(sys.argv[1])
