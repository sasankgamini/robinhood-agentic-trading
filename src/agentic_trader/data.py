from __future__ import annotations

import hashlib
import math
from datetime import date
from urllib.parse import quote
from urllib.request import urlopen
from xml.etree import ElementTree

from .models import NewsItem, Quote


class MarketDataProvider:
    def quote(self, symbol: str) -> Quote:
        raise NotImplementedError


class DeterministicMarketDataProvider(MarketDataProvider):
    """Stable pseudo-market data for dry-run and tests."""

    def quote(self, symbol: str) -> Quote:
        seed = int(hashlib.sha256(f"{symbol}:{date.today()}".encode()).hexdigest()[:10], 16)
        base = 20 + seed % 450
        cycle = math.sin((seed % 360) * math.pi / 180)
        price = round(base * (1 + cycle / 50), 2)
        momentum = round(((seed >> 4) % 100) / 100, 2)
        volatility = round(1 + ((seed >> 12) % 1200) / 100, 2)
        return Quote(symbol=symbol, price=price, momentum_score=momentum, volatility_pct=volatility)


class ResearchProvider:
    def news_for(self, symbols: list[str]) -> list[NewsItem]:
        raise NotImplementedError


class FixtureResearchProvider(ResearchProvider):
    def news_for(self, symbols: list[str]) -> list[NewsItem]:
        items: list[NewsItem] = []
        for symbol in symbols:
            digest = int(hashlib.sha256(symbol.encode()).hexdigest()[:6], 16)
            score = round(((digest % 140) - 40) / 100, 2)
            high_impact = symbol in {"NVDA", "TSLA"} and digest % 5 == 0
            items.append(
                NewsItem(
                    symbol=symbol,
                    title=f"Dry-run sentiment fixture for {symbol}",
                    score=score,
                    high_impact_event=high_impact,
                )
            )
        return items


class RssResearchProvider(ResearchProvider):
    def __init__(self, url_templates: list[str], timeout_seconds: float = 5.0):
        self.url_templates = url_templates
        self.timeout_seconds = timeout_seconds

    def news_for(self, symbols: list[str]) -> list[NewsItem]:
        items: list[NewsItem] = []
        for symbol in symbols:
            headlines: list[tuple[str, str | None]] = []
            for template in self.url_templates:
                url = template.format(symbol=quote(symbol))
                try:
                    with urlopen(url, timeout=self.timeout_seconds) as response:
                        root = ElementTree.fromstring(response.read())
                    for item in root.findall(".//item"):
                        title = item.findtext("title") or ""
                        link = item.findtext("link")
                        if title:
                            headlines.append((title, link))
                except Exception:
                    continue
            items.append(self._score_symbol(symbol, headlines))
        return items

    def _score_symbol(self, symbol: str, headlines: list[tuple[str, str | None]]) -> NewsItem:
        positive = ("beat", "surge", "upgrade", "record", "rally", "strong", "raises")
        negative = ("miss", "probe", "downgrade", "lawsuit", "falls", "weak", "cuts")
        high_impact = ("earnings", "fomc", "cpi", "fed", "guidance")
        titles = [title for title, _ in headlines]
        text = " ".join(titles).lower()
        pos_hits = sum(text.count(word) for word in positive)
        neg_hits = sum(text.count(word) for word in negative)
        score = max(min((pos_hits - neg_hits) / 10, 1.0), -1.0)
        first_title, first_url = headlines[0] if headlines else (f"No RSS headlines found for {symbol}", None)
        return NewsItem(
            symbol=symbol,
            title=first_title,
            score=round(score, 2),
            high_impact_event=any(word in text for word in high_impact),
            source="rss",
            url=first_url,
        )
