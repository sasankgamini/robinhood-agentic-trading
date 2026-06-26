from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .config import load_config
from .engine import TradingEngine
from .journal import init_journal, record_event, summarize
from .notifications import build_notifier
from .state import reset_portfolio


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run-first Robinhood agentic trading engine")
    parser.add_argument(
        "command",
        choices=[
            "run-once",
            "summary",
            "simulate",
            "reset-state",
            "preflight",
            "test-email",
            "journal-init",
            "journal-record",
            "journal-summary",
        ],
    )
    parser.add_argument("--config", default="config/default.json")
    parser.add_argument("--state-dir", default="state")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--journal", default="data/trading_journal.sqlite")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--event-type")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--symbol")
    parser.add_argument("--order-id")
    parser.add_argument("--payload-json")
    parser.add_argument("--payload-file")
    parser.add_argument("--limit", type=int, default=50)
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
    elif args.command == "journal-init":
        init_journal(Path(args.journal))
        print(json.dumps({"journal": args.journal, "initialized": True}, indent=2))
    elif args.command == "journal-record":
        if not args.event_type:
            raise SystemExit("--event-type is required for journal-record")
        payload = _load_payload(args.payload_json, args.payload_file)
        event_id = record_event(
            path=Path(args.journal),
            event_type=args.event_type,
            source=args.source,
            payload=payload,
            symbol=args.symbol,
            order_id=args.order_id,
        )
        print(json.dumps({"journal": args.journal, "event_id": event_id}, indent=2))
    elif args.command == "journal-summary":
        print(json.dumps(summarize(Path(args.journal), limit=args.limit), indent=2))
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


def _load_payload(payload_json: str | None, payload_file: str | None) -> dict:
    if payload_file:
        return json.loads(Path(payload_file).read_text(encoding="utf-8"))
    if payload_json:
        return json.loads(payload_json)
    return {}


if __name__ == "__main__":
    main()
