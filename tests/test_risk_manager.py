"""Unit tests for the risk manager's hard-coded safety rules."""

import pytest

from atlas_trader.config import RiskConfig
from atlas_trader.models import Account, OrderSide
from atlas_trader.risk.risk_manager import RiskLimitBreached, RiskManager


@pytest.fixture
def risk_manager() -> RiskManager:
    config = RiskConfig(
        max_risk_per_trade_pct=1.0,
        stop_loss_pct=0.5,
        take_profit_pct=1.0,
        max_slippage_pct=0.1,
        max_position_pct=20.0,
        max_daily_loss_pct=3.0,
        flatten_on_shutdown=True,
    )
    return RiskManager(config)


def test_size_position_respects_risk_per_trade() -> None:
    # The exposure cap only stays out of the way if
    # max_position_pct > 100 * max_risk_per_trade_pct / stop_loss_pct
    # (100 * 1.0 / 0.5 = 200 here), so it's set comfortably above that
    # threshold to isolate the risk-per-trade math in this test.
    config = RiskConfig(
        max_risk_per_trade_pct=1.0,
        stop_loss_pct=0.5,
        take_profit_pct=1.0,
        max_slippage_pct=0.1,
        max_position_pct=300.0,
        max_daily_loss_pct=3.0,
    )
    risk_manager = RiskManager(config)
    account = Account(equity=100_000, cash=100_000, buying_power=100_000)
    sizing = risk_manager.size_position(account, entry_price=100.0, side=OrderSide.BUY)

    # risk_amount = 1% of 100,000 = 1,000; stop distance = 0.5% of 100 = 0.5
    assert sizing.quantity == pytest.approx(1000 / 0.5, rel=1e-3)
    assert sizing.stop_loss_price == pytest.approx(99.5)
    assert sizing.take_profit_price == pytest.approx(101.0)


def test_size_position_caps_total_exposure(risk_manager: RiskManager) -> None:
    account = Account(equity=1_000, cash=1_000, buying_power=1_000)
    sizing = risk_manager.size_position(account, entry_price=100.0, side=OrderSide.BUY)

    max_quantity = (1_000 * 0.20) / 100.0
    assert sizing.quantity <= max_quantity + 1e-6


def test_daily_loss_limit_halts_trading(risk_manager: RiskManager) -> None:
    risk_manager.start_session(Account(equity=100_000, cash=100_000, buying_power=100_000))

    with pytest.raises(RiskLimitBreached):
        risk_manager.check_daily_loss_limit(
            Account(equity=96_000, cash=96_000, buying_power=96_000)
        )

    assert risk_manager.is_halted is True


def test_slippage_guard_blocks_excessive_deviation(risk_manager: RiskManager) -> None:
    with pytest.raises(RiskLimitBreached):
        risk_manager.validate_slippage(expected_price=100.0, quoted_price=100.5)


def test_slippage_guard_allows_small_deviation(risk_manager: RiskManager) -> None:
    # 0.05% deviation is within the 0.1% configured buffer.
    risk_manager.validate_slippage(expected_price=100.0, quoted_price=100.05)
