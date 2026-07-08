"""Entry point for Atlas Trade Engine.

Usage:
    python -m atlas_trader.main --mode paper
    python -m atlas_trader.main --mode live
"""

from __future__ import annotations

import argparse
import asyncio

from atlas_trader.brokers.paper_broker import PaperBroker
from atlas_trader.config import AppConfig, load_config
from atlas_trader.engine import TradingEngine
from atlas_trader.execution.order_manager import OrderManager
from atlas_trader.logger import setup_logging
from atlas_trader.risk.risk_manager import RiskManager
from atlas_trader.strategy.momentum_strategy import MomentumStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Atlas Trade Engine")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default=None,
        help="Override the MODE environment variable ('paper' or 'live').",
    )
    return parser.parse_args()


def build_broker(mode: str, config: AppConfig):
    if mode == "live":
        # Imported lazily so 'paper' mode never requires the Alpaca SDK
        # or live credentials to be present.
        from atlas_trader.brokers.alpaca_broker import AlpacaBroker

        return AlpacaBroker(config.broker, config.engine)
    return PaperBroker()


async def main() -> None:
    args = parse_args()
    config = load_config()
    mode = args.mode or config.engine.mode

    setup_logging(config.engine.log_dir)

    broker = build_broker(mode, config)
    strategy = MomentumStrategy(config.strategy)
    risk_manager = RiskManager(config.risk)
    order_manager = OrderManager(broker)

    engine = TradingEngine(config, broker, strategy, risk_manager, order_manager)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
