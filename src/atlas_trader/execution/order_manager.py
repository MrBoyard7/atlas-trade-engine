"""Order submission with retries, idempotent client order IDs, and
full audit logging of every fill.
"""

from __future__ import annotations

import uuid
from typing import Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from atlas_trader.brokers.base import BrokerClient
from atlas_trader.logger import get_logger
from atlas_trader.models import Order, OrderSide, OrderType

logger = get_logger("order_manager")


class OrderSubmissionError(Exception):
    """Raised once all retry attempts to submit an order have failed."""


class OrderManager:
    def __init__(self, broker: BrokerClient, max_attempts: int = 3) -> None:
        self._broker = broker
        self._max_attempts = max_attempts

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
    ) -> Order:
        """Submit an order with automatic retries on transient failures.

        Each order gets a unique client-generated ID so a retried
        submission is idempotent on the broker side (no duplicate fills
        from a network blip during the original request).
        """
        client_order_id = f"atlas-{uuid.uuid4().hex[:12]}"

        @retry(
            reraise=True,
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=0.5, max=5),
            retry=retry_if_exception_type(Exception),
        )
        async def _submit() -> Order:
            return await self._broker.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                client_order_id=client_order_id,
            )

        try:
            order = await _submit()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Order submission failed after %d attempt(s): %s %s x%s (%s)",
                self._max_attempts,
                side.value,
                symbol,
                quantity,
                exc,
                extra={"is_trade": True},
            )
            raise OrderSubmissionError(str(exc)) from exc

        logger.info(
            "Order acknowledged: id=%s status=%s filled=%s@%s",
            order.client_order_id,
            order.status.value,
            order.filled_quantity,
            order.filled_avg_price,
            extra={"is_trade": True},
        )
        return order

    async def flatten_position(
        self, symbol: str, quantity: float, side_to_close: OrderSide
    ) -> Order:
        """Send an immediate market order to close out an open position.

        Used by the engine's safe-shutdown routine.
        """
        logger.warning("Flattening position: %s x%s", symbol, quantity, extra={"is_trade": True})
        return await self.place_order(symbol, side_to_close, quantity, OrderType.MARKET)
