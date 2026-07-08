"""Deterministic, in-memory simulated broker.

Used for local development, automated tests, and paper trading when
no live broker credentials are configured. Orders fill instantly at
the last known price, which lets the rest of the engine (strategy,
risk manager, order manager, reconnect logic) be exercised end-to-end
without ever touching a real account. This is the default broker used
by `main.py` in `paper` mode.
"""

from __future__ import annotations

import asyncio
import itertools
import random
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Iterable, Optional

from atlas_trader.brokers.base import BrokerClient
from atlas_trader.logger import get_logger
from atlas_trader.models import (
    Account,
    Bar,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)

logger = get_logger("paper_broker")


class PaperBroker(BrokerClient):
    """In-memory broker simulator with a reproducible random-walk feed."""

    def __init__(self, starting_cash: float = 100_000.0, seed: int = 42) -> None:
        self._cash = starting_cash
        self._positions: Dict[str, Position] = {}
        self._order_ids = itertools.count(1)
        self._rng = random.Random(seed)
        self._connected = False
        self._last_bar: Optional[Bar] = None

    async def connect(self) -> None:
        self._connected = True
        logger.info("Paper broker connected (simulated, no real funds involved).")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Paper broker disconnected.")

    async def get_account(self) -> Account:
        equity = self._cash + sum(
            p.quantity * self._last_price(p.symbol) for p in self._positions.values()
        )
        return Account(equity=equity, cash=self._cash, buying_power=self._cash)

    async def get_positions(self) -> Iterable[Position]:
        return list(self._positions.values())

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        fill_price = limit_price or self._last_price(symbol)
        client_order_id = client_order_id or f"paper-{next(self._order_ids)}"

        cost = fill_price * quantity
        self._cash += -cost if side is OrderSide.BUY else cost

        signed_qty = quantity if side is OrderSide.BUY else -quantity
        existing = self._positions.get(symbol)
        if existing is None:
            self._positions[symbol] = Position(symbol, signed_qty, fill_price)
        else:
            new_qty = existing.quantity + signed_qty
            if new_qty == 0:
                del self._positions[symbol]
            else:
                self._positions[symbol] = Position(symbol, new_qty, fill_price)

        order = Order(
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            status=OrderStatus.FILLED,
            filled_avg_price=fill_price,
            filled_quantity=quantity,
        )
        logger.info(
            "Simulated fill: %s %s x%.4f @ %.4f (order_id=%s)",
            side.value,
            symbol,
            quantity,
            fill_price,
            client_order_id,
            extra={"is_trade": True},
        )
        return order

    async def cancel_order(self, client_order_id: str) -> None:
        logger.info(
            "Simulated cancel for order_id=%s (no-op: paper fills are instant).",
            client_order_id,
        )

    async def stream_bars(self, symbol: str, timeframe: str) -> AsyncIterator[Bar]:
        price = 100.0
        while self._connected:
            drift = self._rng.gauss(0, 0.15)
            price = max(0.01, price + drift)
            bar = Bar(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                open=price,
                high=price + abs(drift),
                low=price - abs(drift),
                close=price,
                volume=self._rng.uniform(1_000, 5_000),
            )
            self._last_bar = bar
            yield bar
            await asyncio.sleep(1)

    def _last_price(self, symbol: str) -> float:
        return self._last_bar.close if self._last_bar else 100.0
