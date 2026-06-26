from __future__ import annotations

from .models import NewsItem, Quote, Signal, SignalAction


class Strategy:
    def __init__(self, name: str, profile: dict):
        self.name = name
        self.profile = profile

    def generate(self, quotes: list[Quote], news: list[NewsItem]) -> list[Signal]:
        news_by_symbol = {item.symbol: item for item in news}
        signals: list[Signal] = []
        for quote in quotes:
            item = news_by_symbol.get(quote.symbol)
            news_score = item.score if item else 0.0
            high_impact = bool(item and item.high_impact_event)
            min_momentum = float(self.profile["min_momentum_score"])
            max_volatility = float(self.profile["max_volatility_pct"])

            if high_impact:
                signals.append(self._hold(quote.symbol, "blocked by high-impact event fixture"))
                continue
            if quote.volatility_pct > max_volatility:
                signals.append(self._hold(quote.symbol, f"volatility {quote.volatility_pct}% above limit"))
                continue

            combined = (quote.momentum_score * 0.75) + max(news_score, -1.0) * 0.25
            if combined >= min_momentum:
                signals.append(
                    Signal(
                        symbol=quote.symbol,
                        action=SignalAction.BUY,
                        confidence=round(min(combined, 1.0), 2),
                        reason=f"momentum={quote.momentum_score}, news={news_score}",
                        stop_loss_pct=float(self.profile["stop_loss_pct"]),
                        take_profit_pct=float(self.profile["take_profit_pct"]),
                        target_position_pct=float(self.profile["target_position_pct"]),
                    )
                )
            else:
                signals.append(self._hold(quote.symbol, f"score {combined:.2f} below threshold"))
        return signals

    def _hold(self, symbol: str, reason: str) -> Signal:
        return Signal(
            symbol=symbol,
            action=SignalAction.HOLD,
            confidence=0.0,
            reason=reason,
            stop_loss_pct=float(self.profile["stop_loss_pct"]),
            take_profit_pct=float(self.profile["take_profit_pct"]),
            target_position_pct=float(self.profile["target_position_pct"]),
        )
