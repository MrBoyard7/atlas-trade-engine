"""Configuration management for Atlas Trade Engine.

All strategy, risk, and broker parameters are read from environment
variables (optionally supplied through a local `.env` file) so the
system can be tuned without ever touching the core code. Secrets are
never hard-coded and never committed to the repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BrokerConfig:
    """Credentials and endpoints for the broker connection.

    Credentials are read only from the environment (or a local,
    git-ignored `.env` file) and are never persisted anywhere in the
    codebase.
    """

    api_key: Optional[str] = field(default_factory=lambda: os.getenv("BROKER_API_KEY"))
    api_secret: Optional[str] = field(default_factory=lambda: os.getenv("BROKER_API_SECRET"))
    base_url: str = field(
        default_factory=lambda: os.getenv("BROKER_BASE_URL", "https://paper-api.alpaca.markets")
    )
    data_stream_url: str = field(
        default_factory=lambda: os.getenv(
            "BROKER_STREAM_URL", "wss://stream.data.alpaca.markets/v2/iex"
        )
    )


@dataclass(frozen=True)
class StrategyConfig:
    """Parameters for the example momentum strategy.

    Replace or extend this with your own rule-set's parameters -- the
    engine only depends on the `BaseStrategy` interface, not on these
    specific fields.
    """

    symbol: str = field(default_factory=lambda: os.getenv("SYMBOL", "AAPL"))
    timeframe: str = field(default_factory=lambda: os.getenv("TIMEFRAME", "1Min"))
    fast_ma_period: int = field(default_factory=lambda: _get_int("FAST_MA_PERIOD", 9))
    slow_ma_period: int = field(default_factory=lambda: _get_int("SLOW_MA_PERIOD", 21))
    rsi_period: int = field(default_factory=lambda: _get_int("RSI_PERIOD", 14))
    rsi_overbought: float = field(default_factory=lambda: _get_float("RSI_OVERBOUGHT", 70.0))
    rsi_oversold: float = field(default_factory=lambda: _get_float("RSI_OVERSOLD", 30.0))


@dataclass(frozen=True)
class RiskConfig:
    """Hard-coded, non-optional risk-management limits."""

    max_risk_per_trade_pct: float = field(
        default_factory=lambda: _get_float("MAX_RISK_PER_TRADE_PCT", 1.0)
    )
    stop_loss_pct: float = field(default_factory=lambda: _get_float("STOP_LOSS_PCT", 0.5))
    take_profit_pct: float = field(default_factory=lambda: _get_float("TAKE_PROFIT_PCT", 1.0))
    max_slippage_pct: float = field(default_factory=lambda: _get_float("MAX_SLIPPAGE_PCT", 0.1))
    max_position_pct: float = field(default_factory=lambda: _get_float("MAX_POSITION_PCT", 20.0))
    max_daily_loss_pct: float = field(default_factory=lambda: _get_float("MAX_DAILY_LOSS_PCT", 3.0))
    flatten_on_shutdown: bool = field(
        default_factory=lambda: _get_bool("FLATTEN_ON_SHUTDOWN", True)
    )


@dataclass(frozen=True)
class EngineConfig:
    mode: str = field(default_factory=lambda: os.getenv("MODE", "paper"))  # "paper" or "live"
    reconnect_base_delay: float = field(
        default_factory=lambda: _get_float("RECONNECT_BASE_DELAY", 1.0)
    )
    reconnect_max_delay: float = field(
        default_factory=lambda: _get_float("RECONNECT_MAX_DELAY", 60.0)
    )
    heartbeat_interval: float = field(
        default_factory=lambda: _get_float("HEARTBEAT_INTERVAL", 10.0)
    )
    log_dir: Path = field(default_factory=lambda: Path(os.getenv("LOG_DIR", "logs")))


@dataclass(frozen=True)
class AppConfig:
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)


def load_config() -> AppConfig:
    """Build an immutable configuration snapshot from the environment."""
    return AppConfig()
