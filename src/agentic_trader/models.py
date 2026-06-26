from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class SignalAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    momentum_score: float
    volatility_pct: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class NewsItem:
    symbol: str
    title: str
    score: float
    high_impact_event: bool = False
    source: str = "fixture"
    url: str | None = None


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: SignalAction
    confidence: float
    reason: str
    stop_loss_pct: float
    take_profit_pct: float
    target_position_pct: float


@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.average_price) * self.quantity


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Side
    quantity: float
    estimated_price: float
    reason: str


@dataclass(frozen=True)
class Fill:
    order: Order
    fill_price: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    peak_equity: float | None = None

    def equity(self, prices: dict[str, float]) -> float:
        position_value = sum(
            position.market_value(prices.get(symbol, position.average_price))
            for symbol, position in self.positions.items()
        )
        return self.cash + position_value
