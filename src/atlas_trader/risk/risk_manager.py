"""Hard-coded risk-management rules.

These checks run before every order submission and are never
optional: position sizing based on account equity, stop-loss /
take-profit distances, a slippage buffer, and a daily loss circuit
breaker that halts trading for the rest of the session. None of these
limits can be bypassed by a strategy signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from atlas_trader.config import RiskConfig
from atlas_trader.logger import get_logger
from atlas_trader.models import Account, OrderSide

logger = get_logger("risk_manager")


@dataclass
class TradeSizing:
    quantity: float
    stop_loss_price: float
    take_profit_price: float


class RiskLimitBreached(Exception):
    """Raised when a proposed trade would violate a hard risk limit."""


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self._config = config
        self._session_start_equity: Optional[float] = None
        self._halted = False

    def start_session(self, account: Account) -> None:
        """Record the equity baseline used by the daily loss breaker."""
        self._session_start_equity = account.equity
        self._halted = False

    @property
    def is_halted(self) -> bool:
        return self._halted

    def check_daily_loss_limit(self, account: Account) -> None:
        """Raise if the session drawdown has breached the configured limit."""
        if self._session_start_equity is None:
            self.start_session(account)
            return

        drawdown_pct = (
            (self._session_start_equity - account.equity) / self._session_start_equity * 100
        )
        if drawdown_pct >= self._config.max_daily_loss_pct:
            self._halted = True
            logger.error(
                "Daily loss limit breached: -%.2f%% >= -%.2f%%. Trading halted for the session.",
                drawdown_pct,
                self._config.max_daily_loss_pct,
            )
            raise RiskLimitBreached("Daily loss limit breached; trading halted.")

    def size_position(self, account: Account, entry_price: float, side: OrderSide) -> TradeSizing:
        """Compute a position size that risks at most `max_risk_per_trade_pct`
        of equity to the configured stop distance, capped by
        `max_position_pct` total exposure.
        """
        if entry_price <= 0:
            raise ValueError("entry_price must be positive")

        risk_amount = account.equity * (self._config.max_risk_per_trade_pct / 100)
        stop_distance = entry_price * (self._config.stop_loss_pct / 100)
        take_profit_distance = entry_price * (self._config.take_profit_pct / 100)

        if stop_distance <= 0:
            raise ValueError("stop_loss_pct must be positive")

        quantity = risk_amount / stop_distance

        max_position_value = account.equity * (self._config.max_position_pct / 100)
        max_quantity_by_exposure = max_position_value / entry_price
        quantity = min(quantity, max_quantity_by_exposure)
        quantity = float(round(quantity, 4))

        if quantity <= 0:
            raise RiskLimitBreached("Computed position size is zero; skipping trade.")

        if side is OrderSide.BUY:
            stop_loss_price = entry_price - stop_distance
            take_profit_price = entry_price + take_profit_distance
        else:
            stop_loss_price = entry_price + stop_distance
            take_profit_price = entry_price - take_profit_distance

        return TradeSizing(
            quantity=quantity,
            stop_loss_price=round(stop_loss_price, 4),
            take_profit_price=round(take_profit_price, 4),
        )

    def validate_slippage(self, expected_price: float, quoted_price: float) -> None:
        """Block the trade if the live quote has moved further than the
        configured slippage buffer since the signal was generated.
        """
        slippage_pct = abs(quoted_price - expected_price) / expected_price * 100
        if slippage_pct > self._config.max_slippage_pct:
            logger.warning(
                "Slippage guard triggered: %.3f%% > %.3f%% allowed. Order skipped.",
                slippage_pct,
                self._config.max_slippage_pct,
            )
            raise RiskLimitBreached("Slippage exceeds configured buffer.")
