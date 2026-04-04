"""Run the secular-bear pullback strategy across a broader OANDA basket."""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from little_rzy_bot.market_data import fetch_oanda_ohlcv
from signal_platform.env import load_dotenv

OANDA_CACHE_DIR = Path("research_data/oanda")
OUTPUT_DIR = Path("reports/secular_bear_oanda")
START = "2020-01-01"
END = "2026-04-01"

ASSETS = [
    {"category": "forex", "symbol": "EUR_USD"},
    {"category": "forex", "symbol": "GBP_USD"},
    {"category": "forex", "symbol": "USD_JPY"},
    {"category": "forex", "symbol": "AUD_USD"},
    {"category": "forex", "symbol": "AUD_CHF"},
    {"category": "forex", "symbol": "USD_CAD"},
    {"category": "forex", "symbol": "USD_CHF"},
    {"category": "forex", "symbol": "NZD_USD"},
    {"category": "forex", "symbol": "EUR_GBP"},
    {"category": "forex", "symbol": "EUR_JPY"},
    {"category": "forex", "symbol": "GBP_JPY"},
    {"category": "index", "symbol": "FR40_EUR"},
    {"category": "index", "symbol": "ESPIX_EUR"},
    {"category": "index", "symbol": "JP225_USD"},
    {"category": "index", "symbol": "UK100_GBP"},
    {"category": "index", "symbol": "NAS100_USD"},
    {"category": "index", "symbol": "US30_USD"},
    {"category": "index", "symbol": "SPX500_USD"},
    {"category": "metal", "symbol": "XAU_USD"},
    {"category": "metal", "symbol": "XAG_USD"},
    {"category": "energy", "symbol": "WTICO_USD"},
    {"category": "energy", "symbol": "BCO_USD"},
    {"category": "crypto", "symbol": "BTC_USD"},
    {"category": "crypto", "symbol": "ETH_USD"},
    {"category": "crypto", "symbol": "LTC_USD"},
    {"category": "crypto", "symbol": "BCH_USD"},
]


@dataclass
class Position:
    symbol: str
    entry_price: float
    stop_price: float
    risk_per_unit: float
    bars_held: int = 0


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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
    previous = sum(raw[:period]) / period
    values[period - 1] = previous
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
        return {"swing_high": float(recent["high"].max()), "atr": float(row["atr14"])}
    return None


def mark_to_market(position: Position, price: float) -> float:
    return (position.entry_price - price) / position.risk_per_unit


def load_oanda_history(symbol: str, granularity: str) -> pd.DataFrame:
    ensure_dir(OANDA_CACHE_DIR / symbol)
    csv_path = OANDA_CACHE_DIR / symbol / f"{granularity}_{START}_{END}.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        return df.set_index("timestamp")

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            fetched = fetch_oanda_ohlcv(symbol, granularity, start=START, end=END, environment="practice")
            break
        except Exception as exc:  # pragma: no cover - research retry path
            last_error = exc
            time.sleep(2 + attempt * 2)
    else:
        raise RuntimeError(f"Failed fetching {symbol} {granularity}") from last_error
    df = fetched.df.reset_index()
    df.to_csv(csv_path, index=False)
    return fetched.df


def run_backtest(symbol: str, execution_interval: str, regime: str) -> dict[str, object]:
    if execution_interval == "1d":
        execution = with_indicators(load_oanda_history(symbol, "D"))
        trend_view = execution
    else:
        execution = with_indicators(load_oanda_history(symbol, "H4"))
        trend_view = with_indicators(load_oanda_history(symbol, "D"))

    positions: list[Position] = []
    r_values: list[float] = []
    bars_held: list[int] = []
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0

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
                positions.append(Position(symbol=symbol, entry_price=entry_price, stop_price=stop_price, risk_per_unit=risk))

        remaining: list[Position] = []
        for position in positions:
            position.bars_held += 1
            stop_hit = bar["high"] >= position.stop_price
            if execution_interval == "4h":
                daily_slice = trend_view[trend_view.index <= bar_time]
                trend_break = len(daily_slice) > 220 and not regime_bearish(daily_slice, regime, len(daily_slice) - 1)
            else:
                trend_break = not regime_bearish(execution, regime, idx)

            if stop_hit:
                exit_price = position.stop_price
            elif trend_break:
                exit_price = float(bar["close"])
            else:
                remaining.append(position)
                continue

            r_multiple = (position.entry_price - exit_price) / position.risk_per_unit
            r_values.append(float(r_multiple))
            bars_held.append(position.bars_held)
            equity += r_multiple
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity - peak)
        positions = remaining

    for position in positions:
        exit_price = float(execution.iloc[-1]["close"])
        r_multiple = (position.entry_price - exit_price) / position.risk_per_unit
        r_values.append(float(r_multiple))
        bars_held.append(position.bars_held)
        equity += r_multiple
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    return {
        "symbol": symbol,
        "execution_interval": execution_interval,
        "regime_filter": regime,
        "trades": len(r_values),
        "win_rate": round((len(wins) / len(r_values)) * 100, 2) if r_values else 0.0,
        "avg_r": round(sum(r_values) / len(r_values), 3) if r_values else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
        "total_r": round(sum(r_values), 3),
        "max_drawdown_r": round(max_drawdown, 3),
        "avg_bars_held": round(sum(bars_held) / len(bars_held), 2) if bars_held else 0.0,
    }


def main() -> None:
    load_dotenv(".env")
    ensure_dir(OUTPUT_DIR)
    summary: list[dict[str, object]] = []
    for asset in ASSETS:
        for execution_interval in ["4h", "1d"]:
            for regime in ["ema", "alligator"]:
                result = run_backtest(asset["symbol"], execution_interval, regime)
                result["category"] = asset["category"]
                summary.append(result)
                print(json.dumps(result))
    (OUTPUT_DIR / "oanda_matrix.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
