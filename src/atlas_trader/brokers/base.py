"""Abstract broker interface.

Any broker integration (Alpaca, Interactive Brokers, Binance via ccxt,
etc.) must implement this contract so the rest of the engine never
depends on a specific vendor SDK. Swapping brokers means writing one
new adapter class -- the strategy, risk, and execution layers never
change.
"""

from __future__ import annotations

import abc
from typing import AsyncIterator, Iterable, Optional

from atlas_trader.models import Account, Bar, Order, OrderSide, OrderType, Position


class BrokerClient(abc.ABC):
    """Common contract every broker adapter must satisfy."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Open REST/WebSocket sessions and authenticate."""

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Cleanly close all open connections."""

    @abc.abstractmethod
    async def get_account(self) -> Account:
        """Return current account equity, cash, and buying power."""

    @abc.abstractmethod
    async def get_positions(self) -> Iterable[Position]:
        """Return all currently open positions."""

    @abc.abstractmethod
    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """Submit an order and return the broker's acknowledgement."""

    @abc.abstractmethod
    async def cancel_order(self, client_order_id: str) -> None:
        """Cancel a resting order by its client order id."""

    @abc.abstractmethod
    def stream_bars(self, symbol: str, timeframe: str) -> AsyncIterator[Bar]:
        """Yield bars as they arrive from the broker's market data feed.

        Implementations are responsible for reconnecting on dropped
        connections -- with exponential backoff -- and for backfilling
        any bars missed while offline whenever the broker's REST API
        supports it, so the strategy never silently skips data.
        """
