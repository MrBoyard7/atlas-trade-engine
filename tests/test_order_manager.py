"""Unit tests for OrderManager retry and audit-logging behavior."""

import pytest

from atlas_trader.brokers.paper_broker import PaperBroker
from atlas_trader.execution.order_manager import OrderManager
from atlas_trader.models import OrderSide, OrderStatus


@pytest.mark.asyncio
async def test_place_order_returns_filled_order() -> None:
    broker = PaperBroker()
    await broker.connect()
    manager = OrderManager(broker)

    order = await manager.place_order("AAPL", OrderSide.BUY, quantity=10)

    assert order.status is OrderStatus.FILLED
    assert order.filled_quantity == 10


@pytest.mark.asyncio
async def test_place_order_retries_on_transient_failure(monkeypatch) -> None:
    broker = PaperBroker()
    await broker.connect()
    manager = OrderManager(broker, max_attempts=3)

    attempts = {"count": 0}
    original_submit = broker.submit_order

    async def flaky_submit(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ConnectionError("simulated network blip")
        return await original_submit(*args, **kwargs)

    monkeypatch.setattr(broker, "submit_order", flaky_submit)

    order = await manager.place_order("AAPL", OrderSide.BUY, quantity=5)

    assert attempts["count"] == 2
    assert order.status is OrderStatus.FILLED


@pytest.mark.asyncio
async def test_place_order_raises_after_exhausting_retries(monkeypatch) -> None:
    from atlas_trader.execution.order_manager import OrderSubmissionError

    broker = PaperBroker()
    await broker.connect()
    manager = OrderManager(broker, max_attempts=2)

    async def always_fails(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(broker, "submit_order", always_fails)

    with pytest.raises(OrderSubmissionError):
        await manager.place_order("AAPL", OrderSide.BUY, quantity=5)
