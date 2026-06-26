from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Order, Portfolio, Quote, Side, Signal, SignalAction


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    order: Order | None = None


class RiskManager:
    def __init__(self, risk_config: dict, starting_cash: float):
        self.risk_config = risk_config
        self.starting_cash = starting_cash

    def evaluate(
        self,
        signal: Signal,
        quote: Quote,
        portfolio: Portfolio,
        prices: dict[str, float],
        daily_pnl: float,
        weekly_pnl: float,
    ) -> RiskDecision:
        kill_switch = Path(self.risk_config["kill_switch_file"])
        if kill_switch.exists():
            return RiskDecision(False, f"kill switch present at {kill_switch}")
        if daily_pnl <= -float(self.risk_config["max_daily_loss"]):
            return RiskDecision(False, "daily loss limit reached")
        if weekly_pnl <= -float(self.risk_config["max_weekly_loss"]):
            return RiskDecision(False, "weekly loss limit reached")

        equity = portfolio.equity(prices)
        peak = portfolio.peak_equity or max(equity, self.starting_cash)
        drawdown_pct = ((peak - equity) / peak) * 100 if peak else 0.0
        if drawdown_pct >= float(self.risk_config["max_total_drawdown_pct"]):
            return RiskDecision(False, "total drawdown limit reached")

        if signal.action == SignalAction.HOLD:
            return RiskDecision(False, signal.reason)
        if signal.symbol not in portfolio.positions and len(portfolio.positions) >= int(self.risk_config["max_open_positions"]):
            return RiskDecision(False, "max open positions reached")

        target_pct = min(
            signal.target_position_pct,
            float(self.risk_config["max_position_pct"]),
            float(self.risk_config["max_symbol_allocation_pct"]),
        )
        current_position = portfolio.positions.get(signal.symbol)
        current_symbol_value = current_position.market_value(quote.price) if current_position else 0.0
        max_symbol_value = equity * (float(self.risk_config["max_symbol_allocation_pct"]) / 100)
        desired_symbol_value = equity * (target_pct / 100)
        available_symbol_room = max_symbol_value - current_symbol_value
        desired_add_value = desired_symbol_value - current_symbol_value
        if available_symbol_room <= 0 or desired_add_value <= 0:
            return RiskDecision(False, "symbol already at or above target allocation")

        risk_budget = equity * (float(self.risk_config["risk_per_trade_pct"]) / 100)
        stop_risk_value = signal.stop_loss_pct / 100
        max_value_by_stop = risk_budget / stop_risk_value if stop_risk_value else desired_add_value
        cash_with_slippage_buffer = portfolio.cash * 0.995
        order_value = min(desired_add_value, available_symbol_room, max_value_by_stop, cash_with_slippage_buffer)
        if order_value < 5:
            return RiskDecision(False, "order value below $5 minimum")

        quantity = round(order_value / quote.price, 6)
        return RiskDecision(
            True,
            "approved by risk guardrails",
            Order(
                symbol=signal.symbol,
                side=Side.BUY,
                quantity=quantity,
                estimated_price=quote.price,
                reason=signal.reason,
            ),
        )
