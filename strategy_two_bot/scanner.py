"""Live scanner for strategy #2."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from little_rzy_bot.market_data import fetch_oanda_ohlcv

from .watchlists import asset_class_for

TIMEFRAME_TO_OANDA = {
    "H4": "H4",
    "4H": "H4",
    "D": "D",
    "1D": "D",
}

TIMEFRAME_LABEL = {
    "H4": "4h",
    "D": "1d",
}


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
    enriched["atr14"] = atr(enriched, 14)
    enriched["jaw"] = smma(median_price, 13).shift(8)
    enriched["teeth"] = smma(median_price, 8).shift(5)
    enriched["lips"] = smma(median_price, 5).shift(3)
    return enriched


def regime_bearish(frame: pd.DataFrame, idx: int) -> bool:
    row = frame.iloc[idx]
    if pd.isna(row["jaw"]) or pd.isna(row["teeth"]) or pd.isna(row["lips"]):
        return False
    jaw_prev = frame["jaw"].iloc[idx - 5] if idx >= 5 else row["jaw"]
    return bool(
        row["lips"] < row["teeth"] < row["jaw"]
        and row["close"] < row["lips"]
        and row["jaw"] < jaw_prev
    )


def pullback_signal(frame: pd.DataFrame, idx: int) -> dict[str, float] | None:
    row = frame.iloc[idx]
    prev = frame.iloc[idx - 1]
    if pd.isna(row["atr14"]) or float(row["atr14"]) <= 0:
        return None

    zone_low = min(float(row["lips"]), float(row["teeth"]))
    zone_high = max(float(row["jaw"]), float(row["teeth"]))
    recent = frame.iloc[max(0, idx - 8) : idx + 1]
    pullback_size = float(row["high"]) - float(recent["low"].min())
    touched_zone = float(row["high"]) >= zone_low and float(row["low"]) <= zone_high
    bearish_rejection = float(row["close"]) < float(row["open"]) and float(row["close"]) <= float(prev["low"])
    lower_half_close = float(row["close"]) <= (float(row["low"]) + (float(row["high"]) - float(row["low"])) * 0.45)
    meaningful_pullback = pullback_size >= float(row["atr14"]) * 0.75

    if touched_zone and bearish_rejection and lower_half_close and meaningful_pullback:
        return {
            "swing_high": float(recent["high"].max()),
            "atr": float(row["atr14"]),
            "pullback_size": round(pullback_size, 6),
            "zone_low": round(zone_low, 6),
            "zone_high": round(zone_high, 6),
        }
    return None


def _quality(signal: dict[str, float], row: pd.Series) -> tuple[int, str]:
    score = 50
    atr_value = float(row["atr14"])
    if atr_value > 0 and signal["pullback_size"] >= atr_value:
        score += 15
    if float(row["close"]) < float(row["lips"]):
        score += 10
    if float(row["close"]) <= (float(row["low"]) + (float(row["high"]) - float(row["low"])) * 0.35):
        score += 10
    if float(row["jaw"]) > float(row["teeth"]) > float(row["lips"]):
        score += 10
    score = min(score, 95)
    if score >= 85:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 65:
        grade = "C"
    else:
        grade = "D"
    return score, grade


def _granularity_code(value: str) -> str:
    key = value.upper()
    if key not in TIMEFRAME_TO_OANDA:
        raise ValueError(f"Unsupported strategy #2 granularity: {value}")
    return TIMEFRAME_TO_OANDA[key]


def _timeframe_label(value: str) -> str:
    return TIMEFRAME_LABEL[_granularity_code(value)]


def scan_oanda_symbols(
    symbols: list[str],
    granularity: str,
    higher_timeframe: str,
    environment: str,
    token: str | None,
    price: str,
) -> list[dict[str, object]]:
    exec_code = _granularity_code(granularity)
    trend_code = _granularity_code(higher_timeframe)
    timeframe = _timeframe_label(granularity)
    rows: list[dict[str, object]] = []

    for symbol in symbols:
        execution = with_indicators(
            fetch_oanda_ohlcv(symbol, exec_code, token=token, environment=environment, price=price).df
        )
        trend_view = with_indicators(
            fetch_oanda_ohlcv(symbol, trend_code, token=token, environment=environment, price=price).df
        )

        row: dict[str, object] = {
            "symbol": symbol,
            "asset_class": asset_class_for(symbol),
            "timeframe": timeframe,
            "trend_timeframe": _timeframe_label(higher_timeframe),
            "alert": "",
            "latest_signal": None,
        }
        if len(execution) < 220 or len(trend_view) < 220:
            row["error"] = "Not enough history"
            rows.append(row)
            continue

        idx = len(execution) - 1
        bar = execution.iloc[idx]
        bar_time = execution.index[idx]
        trend_slice = trend_view[trend_view.index <= bar_time]
        if len(trend_slice) < 220 or not regime_bearish(trend_slice, len(trend_slice) - 1):
            rows.append(row)
            continue

        signal = pullback_signal(execution, idx)
        if not signal:
            rows.append(row)
            continue

        entry_price = float(bar["close"])
        stop_price = float(signal["swing_high"] + signal["atr"])
        risk = stop_price - entry_price
        if risk <= 0:
            rows.append(row)
            continue
        target_1 = entry_price - (risk * 2.0)
        score, grade = _quality(signal, bar)
        latest = {
            "symbol": symbol,
            "asset_class": asset_class_for(symbol),
            "timeframe": timeframe,
            "signal_type": "short",
            "timestamp": bar_time.isoformat(),
            "setup_id": f"strategy_two:{symbol}:{timeframe}:{bar_time.isoformat()}",
            "reason_summary": (
                f"Daily Alligator trend remains bearish and the latest {timeframe} pullback rejected the "
                f"Alligator zone. Entry models continuation lower with a structure stop above the swing high plus ATR."
            ),
            "quality_score": score,
            "quality_grade": grade,
            "risk_reward": 2.0,
            "entry": round(entry_price, 6),
            "stop_loss": round(stop_price, 6),
            "target_1": round(target_1, 6),
            "swing_high": round(signal["swing_high"], 6),
            "atr": round(signal["atr"], 6),
            "pullback_size": signal["pullback_size"],
            "zone_low": signal["zone_low"],
            "zone_high": signal["zone_high"],
        }
        row["latest_signal"] = latest
        row["alert"] = (
            f"{symbol} {timeframe.upper()} SHORT | entry {latest['entry']:.6f} | "
            f"stop {latest['stop_loss']:.6f} | tp1 {latest['target_1']:.6f} | "
            f"score {score}/{grade}"
        )
        rows.append(row)

    return rows


def save_scan_outputs(output_dir: str | Path, rows: list[dict[str, object]]) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scan_results.json").write_text(json.dumps(rows, indent=2))
    alerts = [str(row["alert"]) for row in rows if row.get("alert")]
    (out / "alerts.txt").write_text("\n".join(alerts))

