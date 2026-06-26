from __future__ import annotations

from .models import Fill, Order, Portfolio, Side


class ExecutionClient:
    def place_order(self, order: Order) -> Fill:
        raise NotImplementedError


class DryRunExecutionClient(ExecutionClient):
    def __init__(self, slippage_bps: float):
        self.slippage_bps = slippage_bps

    def place_order(self, order: Order) -> Fill:
        multiplier = 1 + (self.slippage_bps / 10000) if order.side == Side.BUY else 1 - (self.slippage_bps / 10000)
        return Fill(order=order, fill_price=round(order.estimated_price * multiplier, 4))


class RobinhoodMcpExecutionClient(ExecutionClient):
    def place_order(self, order: Order) -> Fill:
        raise RuntimeError(
            "Live Robinhood MCP execution is intentionally disabled in this dry-run build. "
            "Enable only after connecting the MCP server, verifying supported tools, and setting live risk flags."
        )


def apply_fill(portfolio: Portfolio, fill: Fill) -> None:
    order = fill.order
    gross = fill.fill_price * order.quantity
    if order.side == Side.BUY:
        portfolio.cash -= gross
        current = portfolio.positions.get(order.symbol)
        if current:
            new_qty = current.quantity + order.quantity
            current.average_price = ((current.average_price * current.quantity) + gross) / new_qty
            current.quantity = new_qty
        else:
            from .models import Position

            portfolio.positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=order.quantity,
                average_price=fill.fill_price,
            )
    else:
        current = portfolio.positions[order.symbol]
        realized = (fill.fill_price - current.average_price) * order.quantity
        portfolio.realized_pnl += realized
        portfolio.cash += gross
        current.quantity -= order.quantity
        if current.quantity <= 0:
            del portfolio.positions[order.symbol]
