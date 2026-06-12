"""Backtest a secular-bear pullback strategy on crypto/ETH pairs."""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

CACHE_DIR = Path("research_data/binance_vision")
OUTPUT_DIR = Path("reports/secular_bear")

SYMBOLS = [
    {"symbol": "BCCETH", "label": "BCCETH"},
    {"symbol": "ATOMETH", "label": "ATOMETH"},
    {"symbol": "DASHETH", "label": "DASHETH"},
]

DATASET_CACHE: dict[tuple[str, str], pd.DataFrame] = {}


@dataclass
class Position:
    symbol: str
    side: str
    entry_time: str
    entry_price: float
    stop_price: float
    target_price: float | None
    exit_mode: str
    risk_per_unit: float
    tranche_id: int
    bars_held: int = 0
    exit_time: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    r_multiple: float | None = None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def month_range(start_year: int, start_month: int, end_year: int, end_month: int) -> Iterable[tuple[int, int]]:
    year = start_year
    month = start_month
    while (year, month) <= (end_year, end_month):
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1


def vision_url(symbol: str, interval: str, year: int, month: int) -> str:
    return (
        "https://data.binance.vision/data/spot/monthly/klines/"
        f"{symbol}/{interval}/{symbol}-{interval}-{year:04d}-{month:02d}.zip"
    )


def load_binance_month(symbol: str, interval: str, year: int, month: int) -> pd.DataFrame | None:
    ensure_dir(CACHE_DIR / symbol / interval)
    zip_path = CACHE_DIR / symbol / interval / f"{symbol}-{interval}-{year:04d}-{month:02d}.zip"
    missing_marker = zip_path.with_suffix(".missing")

    if missing_marker.exists():
        return None

    if not zip_path.exists():
        response = requests.get(vision_url(symbol, interval, year, month), timeout=30)
        if response.status_code == 404:
            missing_marker.write_text("missing")
            return None
        response.raise_for_status()
        zip_path.write_bytes(response.content)

    with zipfile.ZipFile(zip_path) as archive:
        member = archive.namelist()[0]
        raw = archive.read(member)
    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trade_count",
        "taker_base_volume",
        "taker_quote_volume",
        "ignore",
    ]
    df = pd.read_csv(io.BytesIO(raw), header=None, names=columns)
    if df.empty:
        return None
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")
    return df[["open", "high", "low", "close", "volume"]].dropna()


def load_history(symbol: str, interval: str) -> pd.DataFrame:
    cache_key = (symbol, interval)
    if cache_key in DATASET_CACHE:
        return DATASET_CACHE[cache_key].copy()
    frames: list[pd.DataFrame] = []
    for year, month in month_range(2017, 1, 2026, 4):
        frame = load_binance_month(symbol, interval, year, month)
        if frame is not None:
            frames.append(frame)
    if not frames:
        raise RuntimeError(f"No data available for {symbol} {interval}")
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    DATASET_CACHE[cache_key] = df
    return df.copy()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def smma(series: pd.Series, period: int) -> pd.Series:
    values: list[float | None] = [None] * len(series)
    raw = series.tolist()
    if len(raw) < period:
        return pd.Series(values, index=series.index, dtype="float64")
    initial = sum(raw[:period]) / period
    values[period - 1] = initial
    previous = initial
    for idx in range(period, len(raw)):
        previous = ((previous * (period - 1)) + raw[idx]) / period
        values[idx] = previous
    return pd.Series(values, index=series.index, dtype="float64")


def with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    median_price = (enriched["high"] + enriched["low"]) / 2
    enriched["ema20"] = enriched["close"].ewm(span=20, adjust=False).mean()
    enriched["ema50"] = enriched["close"].ewm(span=50, adjust=False).mean()
    enriched["ema200"] = enriched["close"].ewm(span=200, adjust=False).mean()
    enriched["atr14"] = atr(enriched, 14)
    enriched["jaw"] = smma(median_price, 13).shift(8)
    enriched["teeth"] = smma(median_price, 8).shift(5)
    enriched["lips"] = smma(median_price, 5).shift(3)
    return enriched


def regime_bearish(frame: pd.DataFrame, regime: str, idx: int) -> bool:
    row = frame.iloc[idx]
    if regime == "ema":
        if pd.isna(row["ema200"]) or pd.isna(row["ema50"]):
            return False
        ema200_prev = frame["ema200"].iloc[idx - 5] if idx >= 5 else row["ema200"]
        return (
            row["close"] < row["ema200"]
            and row["ema20"] < row["ema50"] < row["ema200"]
            and row["ema200"] < ema200_prev
        )
    if pd.isna(row["jaw"]) or pd.isna(row["teeth"]) or pd.isna(row["lips"]):
        return False
    jaw_prev = frame["jaw"].iloc[idx - 5] if idx >= 5 else row["jaw"]
    return row["lips"] < row["teeth"] < row["jaw"] and row["close"] < row["lips"] and row["jaw"] < jaw_prev


def pullback_signal(frame: pd.DataFrame, regime: str, idx: int) -> dict[str, float] | None:
    row = frame.iloc[idx]
    prev = frame.iloc[idx - 1]
    if pd.isna(row["atr14"]) or row["atr14"] <= 0:
        return None

    if regime == "ema":
        zone_low = min(row["ema20"], row["ema50"])
        zone_high = max(row["ema20"], row["ema50"])
    else:
        zone_low = min(row["lips"], row["teeth"])
        zone_high = max(row["jaw"], row["teeth"])

    if pd.isna(zone_low) or pd.isna(zone_high):
        return None

    recent = frame.iloc[max(0, idx - 8) : idx + 1]
    pullback_size = row["high"] - recent["low"].min()
    touched_zone = row["high"] >= zone_low and row["low"] <= zone_high
    bearish_rejection = row["close"] < row["open"] and row["close"] <= prev["low"]
    lower_half_close = row["close"] <= (row["low"] + (row["high"] - row["low"]) * 0.45)
    meaningful_pullback = pullback_size >= row["atr14"] * 0.75

    if touched_zone and bearish_rejection and lower_half_close and meaningful_pullback:
        swing_high = recent["high"].max()
        return {"swing_high": float(swing_high), "atr": float(row["atr14"])}
    return None


def mark_to_market(position: Position, price: float) -> float:
    if position.side == "short":
        return (position.entry_price - price) / position.risk_per_unit
    return (price - position.entry_price) / position.risk_per_unit


def run_backtest(symbol: str, execution_interval: str, regime: str, exit_mode: str) -> dict[str, object]:
    if execution_interval == "1d":
        execution = with_indicators(load_history(symbol, "1d"))
        trend_view = execution
    else:
        execution = with_indicators(load_history(symbol, "4h"))
        trend_view = with_indicators(load_history(symbol, "1d"))

    positions: list[Position] = []
    closed: list[Position] = []
    tranche_id = 0

    for idx in range(220, len(execution) - 1):
        bar = execution.iloc[idx]
        bar_time = execution.index[idx]
        if execution_interval == "4h":
            daily_slice = trend_view[trend_view.index <= bar_time]
            if len(daily_slice) < 220:
                continue
            trend_ok = regime_bearish(daily_slice, regime, len(daily_slice) - 1)
        else:
            trend_ok = regime_bearish(execution, regime, idx)

        signal = pullback_signal(execution, regime, idx) if trend_ok else None
        basket_positive = not positions or sum(mark_to_market(position, bar["close"]) for position in positions) > 0

        if signal and basket_positive:
            next_bar = execution.iloc[idx + 1]
            entry_price = float(next_bar["open"])
            stop_price = float(signal["swing_high"] + signal["atr"])
            if stop_price > entry_price:
                risk = stop_price - entry_price
                target_price: float | None
                if exit_mode == "tp2":
                    target_price = entry_price - 2.0 * risk
                elif exit_mode == "tp3":
                    target_price = entry_price - 3.0 * risk
                else:
                    target_price = None
                tranche_id += 1
                positions.append(
                    Position(
                        symbol=symbol,
                        side="short",
                        entry_time=str(execution.index[idx + 1]),
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        exit_mode=exit_mode,
                        risk_per_unit=risk,
                        tranche_id=tranche_id,
                    )
                )

        remaining: list[Position] = []
        for position in positions:
            position.bars_held += 1
            stop_hit = bar["high"] >= position.stop_price
            target_hit = position.target_price is not None and bar["low"] <= position.target_price
            trend_break = False
            if exit_mode == "trail":
                if execution_interval == "4h":
                    daily_slice = trend_view[trend_view.index <= bar_time]
                    trend_break = len(daily_slice) > 220 and not regime_bearish(daily_slice, regime, len(daily_slice) - 1)
                else:
                    trend_break = not regime_bearish(execution, regime, idx)

            if stop_hit:
                exit_price = position.stop_price
                exit_reason = "stop"
            elif target_hit:
                exit_price = float(position.target_price)
                exit_reason = "target"
            elif trend_break:
                exit_price = float(bar["close"])
                exit_reason = "trend_break"
            else:
                remaining.append(position)
                continue

            position.exit_time = str(bar_time)
            position.exit_price = exit_price
            position.exit_reason = exit_reason
            position.r_multiple = (position.entry_price - exit_price) / position.risk_per_unit
            closed.append(position)
        positions = remaining

    for position in positions:
        final_close = float(execution.iloc[-1]["close"])
        position.exit_time = str(execution.index[-1])
        position.exit_price = final_close
        position.exit_reason = "final_mark"
        position.r_multiple = (position.entry_price - final_close) / position.risk_per_unit
        closed.append(position)

    r_values = [position.r_multiple for position in closed if position.r_multiple is not None]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in r_values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    return {
        "symbol": symbol,
        "execution_interval": execution_interval,
        "regime_filter": regime,
        "exit_mode": exit_mode,
        "trades": len(r_values),
        "win_rate": round((len(wins) / len(r_values)) * 100, 2) if r_values else 0.0,
        "avg_r": round(sum(r_values) / len(r_values), 3) if r_values else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
        "total_r": round(sum(r_values), 3),
        "max_drawdown_r": round(max_drawdown, 3),
        "avg_bars_held": round(sum(position.bars_held for position in closed) / len(closed), 2) if closed else 0.0,
        "closed_positions": [asdict(position) for position in closed],
    }


def main() -> None:
    ensure_dir(OUTPUT_DIR)
    summary_rows: list[dict[str, object]] = []
    for symbol in SYMBOLS:
        for execution_interval in ["4h", "1d"]:
            for regime in ["ema", "alligator"]:
                for exit_mode in ["tp2", "tp3", "trail"]:
                    result = run_backtest(symbol["symbol"], execution_interval, regime, exit_mode)
                    summary_rows.append({key: value for key, value in result.items() if key != "closed_positions"})
                    detail_path = OUTPUT_DIR / f"{symbol['symbol']}_{execution_interval}_{regime}_{exit_mode}.json"
                    detail_path.write_text(json.dumps(result, indent=2))
                    print(json.dumps({key: value for key, value in result.items() if key != "closed_positions"}))
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary_rows, indent=2))


if __name__ == "__main__":
    main()
