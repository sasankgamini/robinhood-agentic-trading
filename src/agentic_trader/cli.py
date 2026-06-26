from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .config import load_config
from .engine import TradingEngine
from .notifications import build_notifier
from .state import reset_portfolio


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run-first Robinhood agentic trading engine")
    parser.add_argument("command", choices=["run-once", "summary", "simulate", "reset-state", "preflight", "test-email"])
    parser.add_argument("--config", default="config/default.json")
    parser.add_argument("--state-dir", default="state")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.command == "run-once":
        summary = TradingEngine(config, state_dir=Path(args.state_dir), log_dir=Path(args.log_dir)).run_once()
        print(json.dumps(summary, indent=2))
    elif args.command == "reset-state":
        summary = reset_portfolio(Path(args.state_dir), config.starting_cash)
        print(json.dumps(summary, indent=2))
    elif args.command == "preflight":
        result = {
            "mode": "live" if config.live_enabled else "dry-run",
            "strategy": config.active_strategy,
            "starting_cash": config.starting_cash,
            "live_trading_enabled": config.raw["mode"]["live_trading_enabled"],
            "i_understand_risk": config.raw["mode"]["i_understand_risk"],
            "research_live_news_enabled": config.raw["research"]["enable_live_news"],
            "agentic_account_last4": config.raw["account"].get("agentic_account_last4"),
            "kill_switch_file": config.raw["risk"]["kill_switch_file"],
            "ready_for_live_orders": False,
            "reason": "live MCP execution adapter is intentionally disabled until order review/reconciliation is wired",
        }
        print(json.dumps(result, indent=2))
    elif args.command == "test-email":
        notifier = build_notifier({**config.raw["notifications"], "email_enabled": True})
        notifier.send(
            "Robinhood agentic trader email test",
            "Email alerts are configured for the Robinhood agentic trading dry-run system.",
        )
        print(json.dumps({"sent": True}, indent=2))
    elif args.command == "summary":
        path = Path(args.state_dir) / "portfolio.json"
        if path.exists():
            print(path.read_text(encoding="utf-8"))
        else:
            print(json.dumps({"cash": config.starting_cash, "positions": {}}, indent=2))
    elif args.command == "simulate":
        with tempfile.TemporaryDirectory() as state_dir, tempfile.TemporaryDirectory() as log_dir:
            summaries = []
            peak = config.starting_cash
            max_drawdown = 0.0
            for _ in range(args.cycles):
                summary = TradingEngine(config, state_dir=Path(state_dir), log_dir=Path(log_dir)).run_once()
                summaries.append(summary)
                peak = max(peak, summary["equity_after"])
                drawdown = peak - summary["equity_after"]
                max_drawdown = max(max_drawdown, drawdown)
            fills = sum(item["fills"] for item in summaries)
            result = {
                "cycles": args.cycles,
                "strategy": config.active_strategy,
                "starting_equity": config.starting_cash,
                "ending_equity": summaries[-1]["equity_after"] if summaries else config.starting_cash,
                "max_drawdown_dollars": round(max_drawdown, 2),
                "total_fills": fills,
                "last_positions": summaries[-1]["positions"] if summaries else [],
            }
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
