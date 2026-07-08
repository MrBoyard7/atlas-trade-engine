"""Centralized logging for Atlas Trade Engine.

Every signal, fill, and error is logged with a consistent, structured
format across both the console and rotating log files, so that trades
can be audited after the fact and issues can be debugged quickly.
Records tagged with `is_trade=True` are additionally routed to a
dedicated `trades.log` file for a clean execution audit trail.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Configure and return the root application logger.

    Safe to call more than once; subsequent calls are no-ops so
    handlers are never duplicated.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("atlas_trader")
    root_logger.setLevel(level)
    root_logger.propagate = False

    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(_LOG_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_dir / "atlas_trader.log", maxBytes=5_000_000, backupCount=5
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    trade_handler = RotatingFileHandler(log_dir / "trades.log", maxBytes=5_000_000, backupCount=10)
    trade_handler.setFormatter(formatter)
    trade_handler.addFilter(lambda record: getattr(record, "is_trade", False))
    root_logger.addHandler(trade_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"atlas_trader.{name}")
