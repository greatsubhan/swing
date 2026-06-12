from __future__ import annotations

from pathlib import Path

import pandas as pd

from .providers import HistoricalBarRequest, HistoricalDataProvider


REQUIRED_BAR_COLUMNS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")


class LocalParquetHistoricalDataProvider(HistoricalDataProvider):
    """Load bars from a local parquet layout under a configurable root path."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def load_daily_bars(self, request: HistoricalBarRequest) -> pd.DataFrame:
        return self._load(request, base_dir=self.root / "daily")

    def load_intraday_bars(self, request: HistoricalBarRequest) -> pd.DataFrame:
        return self._load(request, base_dir=self.root / "intraday" / request.timeframe)

    def _load(self, request: HistoricalBarRequest, base_dir: Path) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for symbol in request.symbols:
            path = base_dir / f"{symbol}.parquet"
            if not path.exists():
                raise FileNotFoundError(f"Missing parquet file for {symbol}: {path}")
            frame = pd.read_parquet(path)
            frame = self._normalize_frame(frame, symbol=symbol)
            frames.append(frame)

        if not frames:
            return pd.DataFrame(columns=REQUIRED_BAR_COLUMNS)

        data = pd.concat(frames, ignore_index=True)
        if request.start is not None:
            data = data[data["timestamp"] >= pd.Timestamp(request.start)]
        if request.end is not None:
            data = data[data["timestamp"] <= pd.Timestamp(request.end)]
        return data.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    @staticmethod
    def _normalize_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
        data = frame.copy()
        if "symbol" not in data.columns:
            data["symbol"] = symbol
        data["timestamp"] = pd.to_datetime(data["timestamp"], utc=False)
        missing = [column for column in REQUIRED_BAR_COLUMNS if column not in data.columns]
        if missing:
            raise ValueError(f"Bar frame for {symbol} is missing columns: {missing}")
        return data.loc[:, REQUIRED_BAR_COLUMNS]
