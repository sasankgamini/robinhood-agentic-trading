from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import Portfolio, Position


def load_portfolio(path: Path, starting_cash: float) -> Portfolio:
    if not path.exists():
        return Portfolio(cash=starting_cash, peak_equity=starting_cash)
    raw = json.loads(path.read_text(encoding="utf-8"))
    positions = {
        symbol: Position(**position)
        for symbol, position in raw.get("positions", {}).items()
    }
    return Portfolio(
        cash=float(raw["cash"]),
        positions=positions,
        realized_pnl=float(raw.get("realized_pnl", 0.0)),
        peak_equity=raw.get("peak_equity"),
    )


def save_portfolio(path: Path, portfolio: Portfolio) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = asdict(portfolio)
    path.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")


def reset_portfolio(state_dir: Path, starting_cash: float) -> dict:
    state_dir.mkdir(parents=True, exist_ok=True)
    portfolio_path = state_dir / "portfolio.json"
    portfolio = Portfolio(cash=starting_cash, peak_equity=starting_cash)
    save_portfolio(portfolio_path, portfolio)
    return {
        "state_file": str(portfolio_path),
        "cash": starting_cash,
        "positions": [],
        "realized_pnl": 0.0,
        "peak_equity": starting_cash,
    }
