from agentic_trader.models import Portfolio, Quote, Signal, SignalAction
from agentic_trader.risk import RiskManager


def risk_config() -> dict:
    return {
        "kill_switch_file": "state/NO_TEST_KILL_SWITCH",
        "max_daily_loss": 200,
        "max_weekly_loss": 300,
        "max_total_drawdown_pct": 45,
        "max_open_positions": 3,
        "max_position_pct": 25,
        "max_symbol_allocation_pct": 30,
        "risk_per_trade_pct": 3,
    }


def test_risk_blocks_daily_loss_limit() -> None:
    manager = RiskManager(risk_config(), 650)
    signal = Signal("TQQQ", SignalAction.BUY, 0.8, "test", 6, 12, 20)
    quote = Quote("TQQQ", 100, 0.8, 3)
    decision = manager.evaluate(signal, quote, Portfolio(cash=650), {"TQQQ": 100}, -201, 0)
    assert not decision.allowed
    assert "daily loss" in decision.reason


def test_risk_sizes_order_by_stop_risk() -> None:
    manager = RiskManager(risk_config(), 650)
    signal = Signal("TQQQ", SignalAction.BUY, 0.8, "test", 6, 12, 20)
    quote = Quote("TQQQ", 100, 0.8, 3)
    decision = manager.evaluate(signal, quote, Portfolio(cash=650), {"TQQQ": 100}, 0, 0)
    assert decision.allowed
    assert decision.order is not None
    assert decision.order.quantity <= 1.3


if __name__ == "__main__":
    test_risk_blocks_daily_loss_limit()
    test_risk_sizes_order_by_stop_risk()
    print("2 tests passed")
