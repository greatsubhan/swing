from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pandas as pd

from parabolic_exhaustion.ingestion.providers import LiveDataProvider


class PlaybackLiveDataProvider(LiveDataProvider):
    def __init__(self, bars_by_timeframe: dict[str, pd.DataFrame]) -> None:
        self.bars_by_timeframe = {
            timeframe: frame.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
            for timeframe, frame in bars_by_timeframe.items()
        }

    async def get_latest_bar(self, symbol: str, timeframe: str) -> pd.Series:
        frame = self.bars_by_timeframe[timeframe]
        latest = frame.loc[frame["symbol"] == symbol].iloc[-1].copy()
        latest["timeframe"] = timeframe
        return latest

    async def stream_bars(self, symbols: list[str], timeframe: str) -> AsyncIterator[pd.Series]:
        frame = self.bars_by_timeframe[timeframe]
        filtered = frame.loc[frame["symbol"].isin(symbols)].copy()
        for _, row in filtered.iterrows():
            payload = row.copy()
            payload["timeframe"] = timeframe
            yield payload
            await asyncio.sleep(0)
