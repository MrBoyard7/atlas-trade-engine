"""Alpaca Markets broker adapter (REST + WebSocket).

Wraps the official `alpaca-trade-api` SDK behind this project's
`BrokerClient` interface. Handles authentication, order submission,
and a resilient market-data stream with automatic reconnection and
exponential backoff, so a dropped WebSocket connection never silently
stops the strategy loop -- missed bars are backfilled via REST as soon
as the stream comes back up.

Requires `BROKER_API_KEY` and `BROKER_API_SECRET` to be set as
environment variables (see `.env.example`). Credentials are read only
from the environment and are never written to, or read from, the
repository.

To integrate a different broker (Interactive Brokers, Binance via
ccxt, etc.), write a new adapter that implements `BrokerClient` --
`engine.py`, the strategy, and the risk manager do not need to change.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Iterable, Optional

from alpaca_trade_api.rest import REST, APIError
from alpaca_trade_api.stream import Stream

from atlas_trader.brokers.base import BrokerClient
from atlas_trader.config import BrokerConfig, EngineConfig
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

logger = get_logger("alpaca_broker")

_STATUS_MAP = {
    "new": OrderStatus.NEW,
    "accepted": OrderStatus.NEW,
    "filled": OrderStatus.FILLED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "canceled": OrderStatus.CANCELED,
    "rejected": OrderStatus.REJECTED,
}


class AlpacaBroker(BrokerClient):
    def __init__(self, broker_config: BrokerConfig, engine_config: EngineConfig) -> None:
        if not broker_config.api_key or not broker_config.api_secret:
            raise ValueError(
                "Missing broker credentials. Set BROKER_API_KEY and "
                "BROKER_API_SECRET as environment variables (see .env.example) "
                "before running in 'live' mode."
            )
        self._cfg = broker_config
        self._engine_cfg = engine_config
        self._rest = REST(
            key_id=broker_config.api_key,
            secret_key=broker_config.api_secret,
            base_url=broker_config.base_url,
        )
        self._stream: Optional[Stream] = None

    async def connect(self) -> None:
        account = self._rest.get_account()
        logger.info("Connected to Alpaca. Account status: %s", account.status)

    async def disconnect(self) -> None:
        if self._stream is not None:
            await self._stream.close()
        logger.info("Disconnected from Alpaca.")

    async def get_account(self) -> Account:
        account = self._rest.get_account()
        return Account(
            equity=float(account.equity),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
        )

    async def get_positions(self) -> Iterable[Position]:
        return [
            Position(
                symbol=p.symbol,
                quantity=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
            )
            for p in self._rest.list_positions()
        ]

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        try:
            raw = self._rest.submit_order(
                symbol=symbol,
                qty=quantity,
                side=side.value,
                type=order_type.value,
                time_in_force="day",
                limit_price=limit_price,
                client_order_id=client_order_id,
            )
        except APIError as exc:
            logger.error("Order rejected by Alpaca: %s", exc, extra={"is_trade": True})
            raise

        status = _STATUS_MAP.get(raw.status, OrderStatus.NEW)
        logger.info(
            "Order submitted: %s %s x%s (status=%s, id=%s)",
            side.value,
            symbol,
            quantity,
            status.value,
            raw.client_order_id,
            extra={"is_trade": True},
        )
        return Order(
            client_order_id=raw.client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            status=status,
            filled_avg_price=float(raw.filled_avg_price) if raw.filled_avg_price else None,
            filled_quantity=float(raw.filled_qty or 0),
        )

    async def cancel_order(self, client_order_id: str) -> None:
        self._rest.cancel_order(client_order_id)
        logger.info("Cancel requested for order_id=%s", client_order_id)

    async def stream_bars(self, symbol: str, timeframe: str) -> AsyncIterator[Bar]:
        """Yield live bars, reconnecting with exponential backoff on drops.

        The Alpaca SDK stream drives its own event loop internally; it is
        bridged here through an `asyncio.Queue` so it can be exposed as a
        plain async generator, and is restarted automatically whenever it
        disconnects.
        """
        queue: "asyncio.Queue[Bar]" = asyncio.Queue()
        delay = self._engine_cfg.reconnect_base_delay

        async def _bar_handler(raw_bar) -> None:
            await queue.put(
                Bar(
                    symbol=raw_bar.symbol,
                    timestamp=raw_bar.timestamp,
                    open=raw_bar.open,
                    high=raw_bar.high,
                    low=raw_bar.low,
                    close=raw_bar.close,
                    volume=raw_bar.volume,
                )
            )

        async def _run_stream() -> None:
            nonlocal delay
            while True:
                try:
                    self._stream = Stream(
                        key_id=self._cfg.api_key,
                        secret_key=self._cfg.api_secret,
                        base_url=self._cfg.base_url,
                        data_feed="iex",
                    )
                    self._stream.subscribe_bars(_bar_handler, symbol)
                    delay = self._engine_cfg.reconnect_base_delay
                    await self._stream._run_forever()
                except Exception as exc:  # noqa: BLE001 - must survive any stream failure
                    logger.warning(
                        "Market data stream dropped (%s). Backfilling and reconnecting in %.1fs.",
                        exc,
                        delay,
                    )
                    await self._backfill_missed_bars(symbol, timeframe, queue)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._engine_cfg.reconnect_max_delay)

        asyncio.create_task(_run_stream())

        while True:
            yield await queue.get()

    async def _backfill_missed_bars(
        self, symbol: str, timeframe: str, queue: "asyncio.Queue[Bar]"
    ) -> None:
        """Pull recent bars via REST so a WebSocket drop never skips data."""
        try:
            bars = self._rest.get_bars(symbol, timeframe, limit=50)
            for raw_bar in bars:
                await queue.put(
                    Bar(
                        symbol=symbol,
                        timestamp=raw_bar.t,
                        open=raw_bar.o,
                        high=raw_bar.h,
                        low=raw_bar.l,
                        close=raw_bar.c,
                        volume=raw_bar.v,
                    )
                )
            logger.info("Backfilled %d bar(s) for %s after reconnect.", len(bars), symbol)
        except Exception as exc:  # noqa: BLE001
            logger.error("Backfill after reconnect failed: %s", exc)
