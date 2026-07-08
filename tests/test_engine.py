"""Integration-style tests for the trading engine's bar-handling and
safe-shutdown logic, using the in-memory paper broker.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from atlas_trader.brokers.paper_broker import PaperBroker
from atlas_trader.config import AppConfig, RiskConfig, StrategyConfig
from atlas_trader.engine import TradingEngine
from atlas_trader.execution.order_manager import OrderManager
from atlas_trader.models import Bar, OrderSide
from atlas_trader.risk.risk_manager import RiskManager
from atlas_trader.strategy.momentum_strategy import MomentumStrategy


def _make_engine() -> TradingEngine:
    config = AppConfig(
        strategy=StrategyConfig(fast_ma_period=3, slow_ma_period=8, rsi_period=5),
        risk=RiskConfig(max_daily_loss_pct=50.0),  # generous limit so the test isn't halted
    )
    broker = PaperBroker()
    strategy = MomentumStrategy(config.strategy)
    risk_manager = RiskManager(config.risk)
    order_manager = OrderManager(broker)
    return TradingEngine(config, broker, strategy, risk_manager, order_manager)


@pytest.mark.asyncio
async def test_engine_opens_position_on_bullish_crossover() -> None:
    engine = _make_engine()
    await engine._broker.connect()
    account = await engine._broker.get_account()
    engine._risk.start_session(account)

    base = datetime.now(timezone.utc)
    # Flat prices first, then a clean uptrend: this ensures the EMA
    # crossover the strategy looks for happens *while* the engine is
    # observing bars, rather than before the feed even starts.
    flat = np.full(15, 100.0)
    uptrend = np.linspace(100, 120, 20)
    prices = np.concatenate([flat, uptrend])
    for i, price in enumerate(prices):
        bar = Bar(
            symbol="AAPL",
            timestamp=base + timedelta(minutes=i),
            open=price,
            high=price + 0.1,
            low=price - 0.1,
            close=price,
            volume=1000,
        )
        engine._bars.append(bar)
        await engine._on_bar(bar)

    positions = list(await engine._broker.get_positions())
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_safe_shutdown_flattens_open_positions() -> None:
    engine = _make_engine()
    await engine._broker.connect()

    await engine._orders.place_order("AAPL", OrderSide.BUY, quantity=10)
    assert list(await engine._broker.get_positions())

    await engine._safe_shutdown()

    assert list(await engine._broker.get_positions()) == []
