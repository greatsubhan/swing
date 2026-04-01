"""Dataset interface for loading OHLCV data."""
from pathlib import Path
import pandas as pd


REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def load_ohlcv_csv(path: str | Path, timestamp_col: str = "timestamp") -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=[timestamp_col]).set_index(timestamp_col).sort_index()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    return df[REQUIRED_COLUMNS]
