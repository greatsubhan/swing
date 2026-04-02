"""Market data fetchers for Yahoo Finance and OANDA."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


YAHOO_INTERVAL_TO_TIMEFRAME = {
    "1m": "1m",
    "2m": "2m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "1h",
    "90m": "90m",
    "1h": "1h",
    "1d": "1d",
    "5d": "5d",
    "1wk": "1w",
    "1mo": "1mo",
    "3mo": "3mo",
}

OANDA_GRANULARITY_TO_TIMEFRAME = {
    "S5": "5s",
    "S10": "10s",
    "S15": "15s",
    "S30": "30s",
    "M1": "1m",
    "M2": "2m",
    "M4": "4m",
    "M5": "5m",
    "M10": "10m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H2": "2h",
    "H3": "3h",
    "H4": "4h",
    "H6": "6h",
    "H8": "8h",
    "H12": "12h",
    "D": "1d",
    "W": "1w",
    "M": "1mo",
}

OANDA_GRANULARITY_TO_DELTA = {
    "S5": timedelta(seconds=5),
    "S10": timedelta(seconds=10),
    "S15": timedelta(seconds=15),
    "S30": timedelta(seconds=30),
    "M1": timedelta(minutes=1),
    "M2": timedelta(minutes=2),
    "M4": timedelta(minutes=4),
    "M5": timedelta(minutes=5),
    "M10": timedelta(minutes=10),
    "M15": timedelta(minutes=15),
    "M30": timedelta(minutes=30),
    "H1": timedelta(hours=1),
    "H2": timedelta(hours=2),
    "H3": timedelta(hours=3),
    "H4": timedelta(hours=4),
    "H6": timedelta(hours=6),
    "H8": timedelta(hours=8),
    "H12": timedelta(hours=12),
    "D": timedelta(days=1),
    "W": timedelta(days=7),
    "M": timedelta(days=30),
}

REQUIRED_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass
class FetchedMarketData:
    provider: str
    symbol: str
    timeframe: str
    asset_class: str
    df: pd.DataFrame


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_ohlcv(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    rename_map = {}
    for column in df.columns:
        label = str(column).strip().lower()
        if label in {"datetime", "date"}:
            rename_map[column] = timestamp_col
        elif label == "open":
            rename_map[column] = "open"
        elif label == "high":
            rename_map[column] = "high"
        elif label == "low":
            rename_map[column] = "low"
        elif label == "close":
            rename_map[column] = "close"
        elif label == "volume":
            rename_map[column] = "volume"

    normalized = df.rename(columns=rename_map).copy()

    if timestamp_col not in normalized.columns:
        normalized = normalized.reset_index()
        if timestamp_col not in normalized.columns:
            first_column = normalized.columns[0]
            normalized = normalized.rename(columns={first_column: timestamp_col})

    missing = [column for column in [timestamp_col, *REQUIRED_OHLCV_COLUMNS] if column not in normalized.columns]
    if missing:
        raise ValueError(f"Fetched dataset is missing columns: {missing}")

    normalized = normalized[[timestamp_col, *REQUIRED_OHLCV_COLUMNS]].copy()
    normalized[timestamp_col] = pd.to_datetime(normalized[timestamp_col], utc=True)
    normalized = normalized.dropna(subset=["open", "high", "low", "close"]).sort_values(timestamp_col)
    normalized["volume"] = normalized["volume"].fillna(0)
    return normalized


def fetch_yahoo_ohlcv(
    symbol: str,
    interval: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    period: Optional[str] = None,
) -> FetchedMarketData:
    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise RuntimeError("yfinance is not installed. Run `pip install yfinance`.") from exc

    download_kwargs = {
        "tickers": symbol,
        "interval": interval,
        "auto_adjust": False,
        "progress": False,
        "group_by": "column",
    }

    if start or end:
        download_kwargs["start"] = start
        download_kwargs["end"] = end
    else:
        download_kwargs["period"] = period or "1y"

    df = yf.download(**download_kwargs)
    normalized = _normalize_ohlcv(df.reset_index())

    return FetchedMarketData(
        provider="yahoo",
        symbol=symbol,
        timeframe=YAHOO_INTERVAL_TO_TIMEFRAME.get(interval, interval),
        asset_class=_infer_asset_class(symbol),
        df=normalized.set_index("timestamp"),
    )


def _oanda_base_url(environment: str) -> str:
    env = environment.lower()
    if env == "live":
        return "https://api-fxtrade.oanda.com"
    return "https://api-fxpractice.oanda.com"


def _fetch_oanda_candle_batch(
    instrument: str,
    granularity: str,
    start: Optional[datetime],
    end: Optional[datetime],
    price: str,
    token: str,
    environment: str,
    count: Optional[int] = None,
) -> list[dict]:
    params: dict[str, str | int] = {
        "price": price,
        "granularity": granularity,
    }

    if count:
        params["count"] = count
    if start:
        params["from"] = start.isoformat().replace("+00:00", "Z")
    if end:
        params["to"] = end.isoformat().replace("+00:00", "Z")

    url = f"{_oanda_base_url(environment)}/v3/instruments/{instrument}/candles?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept-Datetime-Format": "RFC3339",
        },
    )

    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return payload.get("candles", [])


def fetch_oanda_ohlcv(
    instrument: str,
    granularity: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    price: str = "M",
    token: Optional[str] = None,
    environment: str = "practice",
) -> FetchedMarketData:
    auth_token = token or os.getenv("OANDA_API_TOKEN")
    if not auth_token:
        raise RuntimeError("OANDA token not provided. Pass --oanda-token or set OANDA_API_TOKEN.")

    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    delta = OANDA_GRANULARITY_TO_DELTA.get(granularity)

    if delta is None:
        raise ValueError(f"Unsupported OANDA granularity: {granularity}")

    candles: list[dict] = []

    if start_dt and end_dt:
        cursor = start_dt
        chunk_span = delta * 4500

        while cursor < end_dt:
            batch_end = min(cursor + chunk_span, end_dt)
            batch = _fetch_oanda_candle_batch(
                instrument=instrument,
                granularity=granularity,
                start=cursor,
                end=batch_end,
                price=price,
                token=auth_token,
                environment=environment,
            )
            if not batch:
                break

            candles.extend(batch)
            last_complete = batch[-1]["time"]
            cursor = _parse_datetime(last_complete) + delta
    else:
        candles = _fetch_oanda_candle_batch(
            instrument=instrument,
            granularity=granularity,
            start=None,
            end=None,
            price=price,
            token=auth_token,
            environment=environment,
            count=4500,
        )

    rows = []
    price_key = {"M": "mid", "B": "bid", "A": "ask"}[price.upper()]

    for candle in candles:
        if not candle.get("complete", False):
            continue

        price_data = candle.get(price_key)
        if not price_data:
            continue

        rows.append(
            {
                "timestamp": candle["time"],
                "open": float(price_data["o"]),
                "high": float(price_data["h"]),
                "low": float(price_data["l"]),
                "close": float(price_data["c"]),
                "volume": float(candle.get("volume", 0)),
            }
        )

    if not rows:
        raise RuntimeError("No complete OANDA candles were returned for the selected range.")

    df = pd.DataFrame(rows)
    normalized = _normalize_ohlcv(df)

    return FetchedMarketData(
        provider="oanda",
        symbol=instrument,
        timeframe=OANDA_GRANULARITY_TO_TIMEFRAME.get(granularity, granularity),
        asset_class="forex",
        df=normalized.set_index("timestamp"),
    )


def save_ohlcv_csv(df: pd.DataFrame, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index().to_csv(output_path, index=False)
    return output_path


def _infer_asset_class(symbol: str) -> str:
    upper = symbol.upper()
    if "=" in upper or "_" in upper:
        return "forex"
    if "-" in upper:
        return "crypto"
    return "equity"
