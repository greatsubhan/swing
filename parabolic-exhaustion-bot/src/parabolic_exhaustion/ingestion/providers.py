from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator

import pandas as pd


@dataclass(frozen=True)
class HistoricalBarRequest:
    symbols: tuple[str, ...]
    timeframe: str
    start: datetime | None = None
    end: datetime | None = None


class HistoricalDataProvider(ABC):
    @abstractmethod
    def load_daily_bars(self, request: HistoricalBarRequest) -> pd.DataFrame:
        """Load daily OHLCV bars for one or more symbols."""

    @abstractmethod
    def load_intraday_bars(self, request: HistoricalBarRequest) -> pd.DataFrame:
        """Load intraday OHLCV bars for one or more symbols."""


class LiveDataProvider(ABC):
    @abstractmethod
    async def get_latest_bar(self, symbol: str, timeframe: str) -> pd.Series:
        """Fetch the latest bar for a symbol."""

    @abstractmethod
    async def stream_bars(
        self, symbols: list[str], timeframe: str
    ) -> AsyncIterator[pd.Series]:
        """Yield new bars as they arrive."""


class AssetMetadataProvider(ABC):
    @abstractmethod
    def load_metadata(self, symbols: list[str]) -> pd.DataFrame:
        """Load per-symbol metadata such as market cap bucket and theme flags."""
