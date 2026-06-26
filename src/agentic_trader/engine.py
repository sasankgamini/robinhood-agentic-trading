from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .data import DeterministicMarketDataProvider, FixtureResearchProvider, RssResearchProvider
from .execution import DryRunExecutionClient, RobinhoodMcpExecutionClient, apply_fill
from .logging_utils import JsonlLogger
from .models import Portfolio
from .notifications import build_notifier
from .risk import RiskManager
from .state import load_portfolio, save_portfolio
from .strategy import Strategy


class TradingEngine:
    def __init__(self, config: AppConfig, state_dir: Path = Path("state"), log_dir: Path = Path("logs")):
        self.config = config
        self.state_dir = state_dir
        self.log = JsonlLogger(log_dir / "trades.jsonl")
        self.market_data = DeterministicMarketDataProvider()
        research_config = config.raw["research"]
        self.research = (
            RssResearchProvider(research_config["rss_url_templates"])
            if research_config.get("enable_live_news")
            else FixtureResearchProvider()
        )
        self.notifier = build_notifier(config.raw["notifications"])
        self.risk = RiskManager(config.raw["risk"], config.starting_cash)
        self.execution = (
            RobinhoodMcpExecutionClient()
            if config.live_enabled
            else DryRunExecutionClient(config.raw["execution"]["slippage_bps"])
        )

    def run_once(self) -> dict:
        profile = self.config.strategy_profile
        symbols = list(profile["symbols"])
        strategy = Strategy(self.config.active_strategy, profile)
        portfolio = load_portfolio(self.state_dir / "portfolio.json", self.config.starting_cash)

        quotes = [self.market_data.quote(symbol) for symbol in symbols]
        prices = {quote.symbol: quote.price for quote in quotes}
        equity_before = portfolio.equity(prices)
        portfolio.peak_equity = max(portfolio.peak_equity or equity_before, equity_before)
        news = self.research.news_for(symbols)
        for item in news:
            self.log.event(
                "research_context",
                {
                    "symbol": item.symbol,
                    "source": item.source,
                    "title": item.title,
                    "url": item.url,
                    "score": item.score,
                    "high_impact_event": item.high_impact_event,
                },
            )
        signals = strategy.generate(quotes, news)

        decisions = []
        fills = []
        for signal in signals:
            quote = prices[signal.symbol]
            decision = self.risk.evaluate(
                signal=signal,
                quote=next(item for item in quotes if item.symbol == signal.symbol),
                portfolio=portfolio,
                prices=prices,
                daily_pnl=portfolio.realized_pnl,
                weekly_pnl=portfolio.realized_pnl,
            )
            decisions.append((signal, decision))
            self.log.event(
                "risk_decision",
                {
                    "symbol": signal.symbol,
                    "action": signal.action,
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                },
            )
            if decision.allowed and decision.order:
                fill = self.execution.place_order(decision.order)
                apply_fill(portfolio, fill)
                fills.append(fill)
                self.log.event(
                    "fill",
                    {
                        "symbol": fill.order.symbol,
                        "side": fill.order.side,
                        "quantity": fill.order.quantity,
                        "fill_price": fill.fill_price,
                        "reason": fill.order.reason,
                    },
                )

        equity_after = portfolio.equity(prices)
        portfolio.peak_equity = max(portfolio.peak_equity or equity_after, equity_after)
        save_portfolio(self.state_dir / "portfolio.json", portfolio)

        summary = {
            "mode": "live" if self.config.live_enabled else "dry-run",
            "strategy": self.config.active_strategy,
            "equity_before": round(equity_before, 2),
            "equity_after": round(equity_after, 2),
            "cash": round(portfolio.cash, 2),
            "positions": sorted(portfolio.positions),
            "fills": len(fills),
            "blocked": len([decision for _, decision in decisions if not decision.allowed]),
            "research": [
                {
                    "symbol": item.symbol,
                    "title": item.title,
                    "url": item.url,
                    "score": item.score,
                    "high_impact_event": item.high_impact_event,
                }
                for item in news
            ],
        }
        self.log.event("run_summary", summary)
        if fills:
            self.notifier.send("Trading bot dry-run fills", str(summary))
        return summary
