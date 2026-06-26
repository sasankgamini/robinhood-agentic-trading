from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def starting_cash(self) -> float:
        return float(self.raw["account"]["starting_cash"])

    @property
    def active_strategy(self) -> str:
        return str(self.raw["strategy"]["active"])

    @property
    def strategy_profile(self) -> dict[str, Any]:
        return dict(self.raw["strategy"]["profiles"][self.active_strategy])

    @property
    def live_enabled(self) -> bool:
        mode = self.raw["mode"]
        return bool(mode["live_trading_enabled"] and mode["i_understand_risk"])


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return AppConfig(raw=raw, path=config_path)
