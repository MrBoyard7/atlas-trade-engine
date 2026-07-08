"""Shared data models used across the Atlas Trade Engine.

Keeping these types broker-agnostic lets the strategy, risk, and
execution layers stay completely decoupled from any single vendor's
SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    NEW = "new"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class Signal(str, Enum):
    """Trading signal produced by a strategy for the current bar."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"
    HOLD = "hold"


@dataclass
class Bar:
    """A single OHLCV candle."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Order:
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.NEW
    filled_avg_price: Optional[float] = None
    filled_quantity: float = 0.0


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_entry_price: float


@dataclass
class Account:
    equity: float
    cash: float
    buying_power: float
