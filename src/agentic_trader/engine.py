from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .data import DeterministicMarketDataProvider, FixtureResearchProvider, RssResearchProvider
from .execution import DryRunExecutionClient, RobinhoodMcpExecutionClient, apply_fill
from .logging_utils import JsonlLogger
from .models import Portfolio, Signal, SignalAction
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

        ordered_signals = sorted(
            signals,
            key=lambda signal: (signal.action == SignalAction.BUY, signal.confidence),
            reverse=True,
        )
        decisions = []
        fills = []
        new_entries = 0
        new_deployed = 0.0
        new_groups: set[str] = set()
        new_single_stocks = 0
        for signal in ordered_signals:
            quote = prices[signal.symbol]
            decision = self.risk.evaluate(
                signal=signal,
                quote=next(item for item in quotes if item.symbol == signal.symbol),
                portfolio=portfolio,
                prices=prices,
                daily_pnl=portfolio.realized_pnl,
                weekly_pnl=portfolio.realized_pnl,
            )
            if decision.allowed and decision.order:
                cap_reason = self._profile_cap_reason(
                    profile=profile,
                    signal=signal,
                    portfolio=portfolio,
                    prices=prices,
                    order_value=decision.order.quantity * decision.order.estimated_price,
                    new_entries=new_entries,
                    new_deployed=new_deployed,
                    new_groups=new_groups,
                    new_single_stocks=new_single_stocks,
                )
                if cap_reason:
                    decision = type(decision)(False, cap_reason)
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
                order_value = fill.order.quantity * fill.fill_price
                new_entries += 1
                new_deployed += order_value
                group = self._exposure_group(profile, signal.symbol)
                if group:
                    new_groups.add(group)
                if signal.symbol in set(profile.get("single_stock_symbols", [])):
                    new_single_stocks += 1
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

    def _profile_cap_reason(
        self,
        profile: dict,
        signal: Signal,
        portfolio: Portfolio,
        prices: dict[str, float],
        order_value: float,
        new_entries: int,
        new_deployed: float,
        new_groups: set[str],
        new_single_stocks: int,
    ) -> str | None:
        max_entries = profile.get("max_new_positions_per_day")
        if max_entries is not None and new_entries >= int(max_entries):
            return "profile cap: max new positions per day reached"

        min_order = float(profile.get("min_order_notional", 0))
        if order_value < min_order:
            return f"profile cap: order value below ${min_order:.0f} minimum"

        max_new_deployed = profile.get("max_total_new_deployed")
        if max_new_deployed is not None and new_deployed + order_value > float(max_new_deployed):
            return "profile cap: max total new deployed reached"

        strategy_symbols = set(profile.get("symbols", []))
        strategy_exposure = sum(
            position.market_value(prices.get(symbol, position.average_price))
            for symbol, position in portfolio.positions.items()
            if symbol in strategy_symbols
        )
        max_strategy_exposure = profile.get("max_total_strategy_exposure")
        if max_strategy_exposure is not None and strategy_exposure + order_value > float(max_strategy_exposure):
            return "profile cap: max total strategy exposure reached"

        group = self._exposure_group(profile, signal.symbol)
        if group:
            existing_group_symbols = set(profile.get("exposure_groups", {}).get(group, []))
            if group in new_groups:
                return f"profile cap: exposure group {group} already selected today"
            if any(symbol in portfolio.positions for symbol in existing_group_symbols):
                return f"profile cap: exposure group {group} already has an open position"

        single_stocks = set(profile.get("single_stock_symbols", []))
        if signal.symbol in single_stocks:
            max_single_positions = int(profile.get("max_single_stock_positions", 999))
            existing_single_stocks = sum(1 for symbol in portfolio.positions if symbol in single_stocks)
            if existing_single_stocks + new_single_stocks >= max_single_positions:
                return "profile cap: max single-stock positions reached"
            max_single_notional = profile.get("max_single_stock_notional")
            if max_single_notional is not None and order_value > float(max_single_notional):
                return "profile cap: single-stock notional cap reached"

        leveraged = set(profile.get("leveraged_symbols", []))
        if signal.symbol in leveraged:
            max_leveraged_notional = profile.get("max_leveraged_etf_notional")
            if max_leveraged_notional is not None and order_value > float(max_leveraged_notional):
                return "profile cap: leveraged ETF/ETN notional cap reached"

        return None

    def _exposure_group(self, profile: dict, symbol: str) -> str | None:
        for group, symbols in profile.get("exposure_groups", {}).items():
            if symbol in symbols:
                return group
        return None
