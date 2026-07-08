"""Main orchestration loop.

Wires together market data ingestion, the strategy, risk management,
and order execution, and owns the reconnect / safe-shutdown lifecycle.
This is the only module that depends on all the other layers -- the
strategy, risk manager, and broker adapter each stay independently
testable and swappable.
"""

from __future__ import annotations

import asyncio
import signal
from collections import deque
from typing import Deque, Optional

from atlas_trader.brokers.base import BrokerClient
from atlas_trader.config import AppConfig
from atlas_trader.data.market_data_feed import bars_to_dataframe
from atlas_trader.execution.order_manager import OrderManager, OrderSubmissionError
from atlas_trader.logger import get_logger
from atlas_trader.models import Account, Bar, OrderSide, Signal
from atlas_trader.risk.risk_manager import RiskLimitBreached, RiskManager
from atlas_trader.strategy.base_strategy import BaseStrategy

logger = get_logger("engine")


class TradingEngine:
    def __init__(
        self,
        config: AppConfig,
        broker: BrokerClient,
        strategy: BaseStrategy,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        history_size: int = 500,
    ) -> None:
        self._config = config
        self._broker = broker
        self._strategy = strategy
        self._risk = risk_manager
        self._orders = order_manager
        self._bars: Deque[Bar] = deque(maxlen=history_size)
        self._position_side: Optional[OrderSide] = None
        self._shutdown_event = asyncio.Event()

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._shutdown_event.set)
            except NotImplementedError:
                # add_signal_handler is unavailable on some platforms (e.g. Windows).
                pass

    async def run(self) -> None:
        """Connect, start streaming, and block until a shutdown signal
        (SIGINT/SIGTERM) is received, then flatten positions and
        disconnect cleanly.
        """
        self._install_signal_handlers()
        await self._broker.connect()
        account = await self._broker.get_account()
        self._risk.start_session(account)
        logger.info(
            "Engine started in '%s' mode for %s.",
            self._config.engine.mode,
            self._config.strategy.symbol,
        )

        stream_task = asyncio.create_task(self._consume_market_data())
        await self._shutdown_event.wait()

        logger.warning("Shutdown signal received. Beginning safe shutdown.")
        stream_task.cancel()
        await self._safe_shutdown()

    async def _consume_market_data(self) -> None:
        async for bar in self._broker.stream_bars(
            self._config.strategy.symbol, self._config.strategy.timeframe
        ):
            self._bars.append(bar)
            await self._on_bar(bar)

    async def _on_bar(self, bar: Bar) -> None:
        df = bars_to_dataframe(self._bars)

        account = await self._broker.get_account()
        try:
            self._risk.check_daily_loss_limit(account)
        except RiskLimitBreached:
            self._shutdown_event.set()
            return

        signal = self._strategy.generate_signal(df)
        if signal is Signal.HOLD:
            return

        try:
            await self._handle_signal(signal, bar, account)
        except RiskLimitBreached as exc:
            logger.warning("Trade skipped by risk manager: %s", exc)
        except OrderSubmissionError as exc:
            logger.error("Trade skipped after order submission failure: %s", exc)

    async def _handle_signal(self, signal: Signal, bar: Bar, account: Account) -> None:
        side = OrderSide.BUY if signal is Signal.LONG else OrderSide.SELL

        if self._position_side == side:
            return  # already positioned in this direction; nothing to do

        sizing = self._risk.size_position(account, bar.close, side)
        # Re-validate against the latest close as a stand-in for a fresh
        # quote; a live adapter should pass the actual current NBBO here.
        self._risk.validate_slippage(expected_price=bar.close, quoted_price=bar.close)

        await self._orders.place_order(bar.symbol, side, sizing.quantity)
        self._position_side = side
        logger.info(
            "Position opened: %s %s x%.4f (SL=%.4f, TP=%.4f)",
            side.value,
            bar.symbol,
            sizing.quantity,
            sizing.stop_loss_price,
            sizing.take_profit_price,
            extra={"is_trade": True},
        )

    async def _safe_shutdown(self) -> None:
        if not self._config.risk.flatten_on_shutdown:
            await self._broker.disconnect()
            return

        try:
            positions = await self._broker.get_positions()
            for position in positions:
                side_to_close = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
                await self._orders.flatten_position(
                    position.symbol, abs(position.quantity), side_to_close
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error while flattening positions during shutdown: %s", exc)
        finally:
            await self._broker.disconnect()
            logger.info("Safe shutdown complete.")
