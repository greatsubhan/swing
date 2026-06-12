from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import httpx
import pandas as pd

from parabolic_exhaustion.ingestion.providers import LiveDataProvider


TIMEFRAME_TO_OANDA_GRANULARITY = {
    "1m": "M1",
    "5m": "M5",
    "1d": "D",
}

OANDA_ENVIRONMENTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaLiveDataProvider(LiveDataProvider):
    def __init__(
        self,
        *,
        api_token: str | None = None,
        environment: str | None = None,
        price_component: str = "M",
        poll_interval_seconds: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_token = api_token or os.getenv("OANDA_API_TOKEN", "")
        self.environment = environment or os.getenv("OANDA_ENV", "practice")
        self.base_url = OANDA_ENVIRONMENTS.get(self.environment, OANDA_ENVIRONMENTS["practice"])
        self.price_component = price_component
        self.poll_interval_seconds = poll_interval_seconds
        self.client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_token}"} if self.api_token else {},
            timeout=10.0,
        )

    async def get_latest_bar(self, symbol: str, timeframe: str) -> pd.Series:
        recent = await self.get_recent_bars(symbol, timeframe, count=2)
        if recent.empty:
            raise ValueError(f"No complete candles returned for {symbol} {timeframe}")
        return recent.iloc[-1].copy()

    async def get_recent_bars(self, symbol: str, timeframe: str, *, count: int) -> pd.DataFrame:
        granularity = TIMEFRAME_TO_OANDA_GRANULARITY[timeframe]
        response = await self.client.get(
            f"/v3/instruments/{symbol}/candles",
            params={
                "granularity": granularity,
                "price": self.price_component,
                "count": count,
            },
        )
        response.raise_for_status()
        candles = response.json()["candles"]
        complete = [candle for candle in candles if candle.get("complete", False)]
        if not complete:
            return pd.DataFrame(
                columns=["timestamp", "symbol", "open", "high", "low", "close", "volume", "timeframe"]
            )
        rows = []
        for candle in complete:
            mid = candle["mid"]
            rows.append(
                {
                    "timestamp": pd.Timestamp(candle["time"]),
                    "symbol": symbol,
                    "open": float(mid["o"]),
                    "high": float(mid["h"]),
                    "low": float(mid["l"]),
                    "close": float(mid["c"]),
                    "volume": float(candle["volume"]),
                    "timeframe": timeframe,
                }
            )
        return pd.DataFrame(rows)

    async def stream_bars(self, symbols: list[str], timeframe: str) -> AsyncIterator[pd.Series]:
        last_seen: dict[str, pd.Timestamp] = {}
        while True:
            for symbol in symbols:
                latest = await self.get_latest_bar(symbol, timeframe)
                timestamp = pd.Timestamp(latest["timestamp"])
                if last_seen.get(symbol) == timestamp:
                    continue
                last_seen[symbol] = timestamp
                yield latest
            await asyncio.sleep(self.poll_interval_seconds)
