"""First-pass backtest for the Advanced Engulfing trend-pullback strategy."""
from __future__ import annotations

import argparse
from bisect import bisect_left
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
from research.advanced_engulfing_universe import CONFIG_PATH, filter_universe
from signal_platform.env import load_dotenv

DEFAULT_START = "2025-01-01"
DEFAULT_END = "2026-04-01"
OANDA_ENV = "practice"
OANDA_CACHE_DIR = Path("research_data/advanced_engulfing")
OUTPUT_DIR = Path("reports/advanced_engulfing")

FRACTAL_LOOKBACK = 2
MAX_BARS_HELD = 48
ENABLE_EMA_SLOPE_FILTER = False
TIMEFRAME_TO_GRANULARITY = {
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
}


@dataclass
class Position:
    symbol: str
    timeframe: str
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    target_price: float
    risk_per_unit: float
    bars_held: int = 0
    exit_time: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    r_multiple: float | None = None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def stop_extra_buffer(atr_value: float) -> float:
    if atr_value < 40:
        return 5.0
    if atr_value < 50:
        return 10.0
    if atr_value <= 200:
        return 20.0
    return 20.0


def with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["ema50"] = enriched["close"].ewm(span=50, adjust=False).mean()
    enriched["atr14"] = atr(enriched, 14)
    enriched["body_high"] = enriched[["open", "close"]].max(axis=1)
    enriched["body_low"] = enriched[["open", "close"]].min(axis=1)
    enriched["range"] = enriched["high"] - enriched["low"]
    enriched["avg_range_5"] = enriched["range"].rolling(5).mean()
    return enriched


def load_oanda_history(symbol: str, granularity: str, start: str, end: str) -> pd.DataFrame:
    ensure_dir(OANDA_CACHE_DIR / symbol)
    csv_path = OANDA_CACHE_DIR / symbol / f"{granularity}_{start}_{end}.csv"
    if csv_path.exists():
        cached = pd.read_csv(csv_path, parse_dates=["timestamp"])
        return cached.set_index("timestamp")

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            fetched = fetch_oanda_ohlcv(symbol, granularity, start=start, end=end, environment=OANDA_ENV)
            break
        except Exception as exc:  # pragma: no cover
            last_error = exc
            time.sleep(2 + attempt * 2)
    else:
        raise RuntimeError(f"Failed fetching {symbol} {granularity}") from last_error

    df = fetched.df.reset_index()
    df.to_csv(csv_path, index=False)
    return fetched.df


def compute_fractals(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    swing_high = pd.Series(False, index=frame.index)
    swing_low = pd.Series(False, index=frame.index)
    for idx in range(FRACTAL_LOOKBACK, len(frame) - FRACTAL_LOOKBACK):
        high = frame["high"].iloc[idx]
        low = frame["low"].iloc[idx]
        if all(high > frame["high"].iloc[idx - offset] for offset in (1, 2)) and all(
            high > frame["high"].iloc[idx + offset] for offset in (1, 2)
        ):
            swing_high.iloc[idx] = True
        if all(low < frame["low"].iloc[idx - offset] for offset in (1, 2)) and all(
            low < frame["low"].iloc[idx + offset] for offset in (1, 2)
        ):
            swing_low.iloc[idx] = True
    return swing_high, swing_low


def consecutive_candles(frame: pd.DataFrame, end_idx: int, bullish: bool) -> int:
    count = 0
    cursor = end_idx
    while cursor >= 0:
        row = frame.iloc[cursor]
        is_bullish = float(row["close"]) > float(row["open"])
        is_bearish = float(row["close"]) < float(row["open"])
        ok = is_bullish if bullish else is_bearish
        if not ok:
            break
        count += 1
        cursor -= 1
    return count


def advanced_bullish(frame: pd.DataFrame, idx: int) -> bool:
    row = frame.iloc[idx]
    prev = frame.iloc[idx - 1]
    if float(row["close"]) <= float(row["open"]):
        return False
    if float(row["body_low"]) > float(prev["body_low"]) or float(row["body_high"]) < float(prev["body_high"]):
        return False
    if float(row["close"]) <= float(prev["high"]):
        return False
    expanded = float(row["range"]) >= float(row["atr14"]) * 1.2 or float(row["range"]) >= float(row["avg_range_5"])
    if not expanded:
        return False
    candle_range = float(row["high"] - row["low"])
    if candle_range <= 0:
        return False
    return (float(row["close"]) - float(row["low"])) / candle_range >= 0.7


def advanced_bearish(frame: pd.DataFrame, idx: int) -> bool:
    row = frame.iloc[idx]
    prev = frame.iloc[idx - 1]
    if float(row["close"]) >= float(row["open"]):
        return False
    if float(row["body_low"]) > float(prev["body_low"]) or float(row["body_high"]) < float(prev["body_high"]):
        return False
    if float(row["close"]) >= float(prev["low"]):
        return False
    expanded = float(row["range"]) >= float(row["atr14"]) * 1.2 or float(row["range"]) >= float(row["avg_range_5"])
    if not expanded:
        return False
    candle_range = float(row["high"] - row["low"])
    if candle_range <= 0:
        return False
    return (float(row["high"]) - float(row["close"])) / candle_range >= 0.7


def latest_swings_before(indices: list[int], idx: int, count: int = 2) -> list[int]:
    end = bisect_left(indices, idx)
    start = max(0, end - count)
    return indices[start:end]


def long_signal(
    frame: pd.DataFrame,
    swing_high_indices: list[int],
    swing_low_indices: list[int],
    idx: int,
) -> dict[str, float] | None:
    row = frame.iloc[idx]
    if idx < 5 or pd.isna(row["ema50"]) or pd.isna(row["atr14"]):
        return None
    if float(row["close"]) <= float(row["ema50"]):
        return None
    if ENABLE_EMA_SLOPE_FILTER and float(frame["ema50"].iloc[idx]) <= float(frame["ema50"].iloc[idx - 1]):
        return None
    high_indices = latest_swings_before(swing_high_indices, idx)
    if len(high_indices) < 2:
        return None
    hh_idx = high_indices[-1]
    prev_hh_idx = high_indices[-2]
    if float(frame["high"].iloc[hh_idx]) <= float(frame["high"].iloc[prev_hh_idx]):
        return None
    low_indices = latest_swings_before(swing_low_indices, hh_idx, count=1)
    if not low_indices:
        return None
    anchor_low_idx = low_indices[-1]
    pullback_start = hh_idx + 1
    if pullback_start >= idx:
        return None
    if consecutive_candles(frame, idx - 1, bullish=False) < 2:
        return None
    pullback_slice = frame.iloc[pullback_start : idx + 1]
    if pullback_slice.empty:
        return None
    if float(pullback_slice["low"].min()) <= float(frame["low"].iloc[anchor_low_idx]):
        return None
    if not advanced_bullish(frame, idx):
        return None
    swing_low_loc = pullback_start + int(pullback_slice["low"].values.argmin())
    if idx not in {swing_low_loc, swing_low_loc + 1}:
        return None
    if float(row["close"]) > float(frame["body_high"].iloc[hh_idx]):
        return None
    swing_low_price = float(frame["low"].iloc[swing_low_loc])
    buffer = float(row["atr14"]) + stop_extra_buffer(float(row["atr14"]))
    stop_price = swing_low_price - buffer
    entry_price = float(row["close"])
    if stop_price >= entry_price:
        return None
    risk = entry_price - stop_price
    target_price = entry_price + risk
    return {
        "side": "long",
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "risk": risk,
    }


def short_signal(
    frame: pd.DataFrame,
    swing_high_indices: list[int],
    swing_low_indices: list[int],
    idx: int,
) -> dict[str, float] | None:
    row = frame.iloc[idx]
    if idx < 5 or pd.isna(row["ema50"]) or pd.isna(row["atr14"]):
        return None
    if float(row["close"]) >= float(row["ema50"]):
        return None
    if ENABLE_EMA_SLOPE_FILTER and float(frame["ema50"].iloc[idx]) >= float(frame["ema50"].iloc[idx - 1]):
        return None
    low_indices = latest_swings_before(swing_low_indices, idx)
    if len(low_indices) < 2:
        return None
    ll_idx = low_indices[-1]
    prev_ll_idx = low_indices[-2]
    if float(frame["low"].iloc[ll_idx]) >= float(frame["low"].iloc[prev_ll_idx]):
        return None
    high_indices = latest_swings_before(swing_high_indices, ll_idx, count=1)
    if not high_indices:
        return None
    anchor_high_idx = high_indices[-1]
    pullback_start = ll_idx + 1
    if pullback_start >= idx:
        return None
    if consecutive_candles(frame, idx - 1, bullish=True) < 2:
        return None
    pullback_slice = frame.iloc[pullback_start : idx + 1]
    if pullback_slice.empty:
        return None
    if float(pullback_slice["high"].max()) >= float(frame["high"].iloc[anchor_high_idx]):
        return None
    if not advanced_bearish(frame, idx):
        return None
    swing_high_loc = pullback_start + int(pullback_slice["high"].values.argmax())
    if idx not in {swing_high_loc, swing_high_loc + 1}:
        return None
    if float(row["close"]) < float(frame["body_low"].iloc[ll_idx]):
        return None
    swing_high_price = float(frame["high"].iloc[swing_high_loc])
    buffer = float(row["atr14"]) + stop_extra_buffer(float(row["atr14"]))
    stop_price = swing_high_price + buffer
    entry_price = float(row["close"])
    if stop_price <= entry_price:
        return None
    risk = stop_price - entry_price
    target_price = entry_price - risk
    return {
        "side": "short",
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "risk": risk,
    }


def close_position(position: Position, exit_price: float, exit_time: pd.Timestamp, reason: str) -> Position:
    if position.side == "long":
        r_multiple = (exit_price - position.entry_price) / position.risk_per_unit
    else:
        r_multiple = (position.entry_price - exit_price) / position.risk_per_unit
    position.exit_price = exit_price
    position.exit_time = str(exit_time)
    position.exit_reason = reason
    position.r_multiple = r_multiple
    return position


def run_backtest(symbol: str, timeframe_label: str, start: str, end: str, group_id: str) -> dict[str, object]:
    granularity = TIMEFRAME_TO_GRANULARITY[timeframe_label]
    frame = with_indicators(load_oanda_history(symbol, granularity, start, end))
    swing_high, swing_low = compute_fractals(frame)
    swing_high_indices = [idx for idx, flag in enumerate(swing_high.tolist()) if flag]
    swing_low_indices = [idx for idx, flag in enumerate(swing_low.tolist()) if flag]
    open_position: Position | None = None
    closed: list[Position] = []

    for idx in range(120, len(frame)):
        timestamp = frame.index[idx]
        row = frame.iloc[idx]

        if open_position is not None:
            open_position.bars_held += 1
            if open_position.side == "long":
                if float(row["low"]) <= open_position.stop_price and float(row["high"]) >= open_position.target_price:
                    closed.append(close_position(open_position, open_position.stop_price, timestamp, "sl_hit"))
                    open_position = None
                elif float(row["low"]) <= open_position.stop_price:
                    closed.append(close_position(open_position, open_position.stop_price, timestamp, "sl_hit"))
                    open_position = None
                elif float(row["high"]) >= open_position.target_price:
                    closed.append(close_position(open_position, open_position.target_price, timestamp, "tp_hit"))
                    open_position = None
            else:
                if float(row["high"]) >= open_position.stop_price and float(row["low"]) <= open_position.target_price:
                    closed.append(close_position(open_position, open_position.stop_price, timestamp, "sl_hit"))
                    open_position = None
                elif float(row["high"]) >= open_position.stop_price:
                    closed.append(close_position(open_position, open_position.stop_price, timestamp, "sl_hit"))
                    open_position = None
                elif float(row["low"]) <= open_position.target_price:
                    closed.append(close_position(open_position, open_position.target_price, timestamp, "tp_hit"))
                    open_position = None
            if open_position is not None and open_position.bars_held >= MAX_BARS_HELD:
                closed.append(close_position(open_position, float(row["close"]), timestamp, "time_exit"))
                open_position = None

        if open_position is not None:
            continue

        long_candidate = long_signal(frame, swing_high_indices, swing_low_indices, idx)
        short_candidate = short_signal(frame, swing_high_indices, swing_low_indices, idx)
        signal = long_candidate if long_candidate is not None else short_candidate
        if signal is None:
            continue
        open_position = Position(
            symbol=symbol,
            timeframe=timeframe_label,
            side=str(signal["side"]),
            entry_time=timestamp,
            entry_price=float(signal["entry_price"]),
            stop_price=float(signal["stop_price"]),
            target_price=float(signal["target_price"]),
            risk_per_unit=float(signal["risk"]),
        )

    if open_position is not None:
        last_bar = frame.iloc[-1]
        closed.append(close_position(open_position, float(last_bar["close"]), frame.index[-1], "eod_exit"))

    if not closed:
        return {
            "symbol": symbol,
            "group": group_id,
            "timeframe": timeframe_label,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_r": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_r": 0.0,
            "max_win_streak": 0,
            "max_loss_streak": 0,
        }

    r_values = [float(position.r_multiple or 0.0) for position in closed]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    max_win_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0
    for value in r_values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        if value > 0:
            current_win_streak += 1
            current_loss_streak = 0
        elif value < 0:
            current_loss_streak += 1
            current_win_streak = 0
        else:
            current_win_streak = 0
            current_loss_streak = 0
        max_win_streak = max(max_win_streak, current_win_streak)
        max_loss_streak = max(max_loss_streak, current_loss_streak)

    result = {
        "symbol": symbol,
        "group": group_id,
        "timeframe": timeframe_label,
        "trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed), 4),
        "avg_r": round(sum(r_values) / len(r_values), 4),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 4) if losses else 0.0,
        "max_drawdown_r": round(abs(max_drawdown), 4),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "total_r": round(sum(r_values), 4),
        "tp_hits": sum(1 for position in closed if position.exit_reason == "tp_hit"),
        "sl_hits": sum(1 for position in closed if position.exit_reason == "sl_hit"),
        "time_exits": sum(1 for position in closed if position.exit_reason == "time_exit"),
        "eod_exits": sum(1 for position in closed if position.exit_reason == "eod_exit"),
    }
    return result


def verdict_for(row: dict[str, object]) -> str:
    trades = int(row["trades"])
    if trades == 0:
        return "No sample"
    if float(row["profit_factor"]) >= 1.2 and float(row["avg_r"]) > 0:
        return "Promising"
    if float(row["profit_factor"]) >= 1.0 and float(row["avg_r"]) >= 0:
        return "Mixed"
    return "Weak"


def summarize_groups(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    group_summary: dict[str, dict[str, object]] = {}
    group_ids = sorted({str(row["group"]) for row in rows})
    for group_id in group_ids:
        group_rows = [row for row in rows if str(row["group"]) == group_id]
        tested = [row for row in group_rows if int(row["trades"]) > 0]
        group_summary[group_id] = {
            "symbols": len(group_rows),
            "symbols_with_trades": len(tested),
            "promising": sum(1 for row in group_rows if verdict_for(row) == "Promising"),
            "mixed": sum(1 for row in group_rows if verdict_for(row) == "Mixed"),
            "weak": sum(1 for row in group_rows if verdict_for(row) == "Weak"),
            "mean_avg_r": round(
                sum(float(row["avg_r"]) for row in tested) / len(tested),
                4,
            )
            if tested
            else 0.0,
            "mean_profit_factor": round(
                sum(float(row["profit_factor"]) for row in tested) / len(tested),
                4,
            )
            if tested
            else 0.0,
        }
    return group_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Advanced engulfing batch backtest")
    parser.add_argument("--start", default=DEFAULT_START, help="Start date, e.g. 2025-01-01")
    parser.add_argument("--end", default=DEFAULT_END, help="End date, e.g. 2026-04-01")
    parser.add_argument("--symbols", default=None, help="Optional comma-separated canonical or alias symbols")
    parser.add_argument("--groups", default=None, help="Optional comma-separated group ids")
    parser.add_argument("--out", default=str(OUTPUT_DIR), help="Output directory for summary files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    output_dir = Path(args.out)
    ensure_dir(output_dir)
    requested_symbols = [item.strip() for item in str(args.symbols).split(",") if item.strip()] if args.symbols else None
    requested_groups = [item.strip() for item in str(args.groups).split(",") if item.strip()] if args.groups else None
    universe = filter_universe(symbols=requested_symbols, groups=requested_groups)
    if not universe:
        raise SystemExit("No symbols matched the requested advanced engulfing universe filters.")

    rows: list[dict[str, object]] = []
    unavailable: list[dict[str, str]] = []
    for item in universe:
        symbol = str(item["symbol"])
        timeframe = str(item["minimum_timeframe"])
        group_id = str(item["group_id"])
        if timeframe not in TIMEFRAME_TO_GRANULARITY:
            unavailable.append(
                {
                    "symbol": symbol,
                    "group": group_id,
                    "timeframe": timeframe,
                    "error": f"Unsupported timeframe mapping: {timeframe}",
                }
            )
            continue
        try:
            rows.append(run_backtest(symbol, timeframe, args.start, args.end, group_id))
        except Exception as exc:
            unavailable.append(
                {
                    "symbol": symbol,
                    "group": group_id,
                    "timeframe": timeframe,
                    "error": str(exc),
                }
            )

    summary = {
        "config": {
            "start": args.start,
            "end": args.end,
            "universe_config": str(CONFIG_PATH.relative_to(ROOT)),
            "assets": [str(item["symbol"]) for item in universe],
            "groups": sorted({str(item["group_id"]) for item in universe}),
            "ema_slope_filter": ENABLE_EMA_SLOPE_FILTER,
            "target": "1R",
            "max_bars_held": MAX_BARS_HELD,
        },
        "group_summary": summarize_groups(rows),
        "rows": rows,
        "unavailable": unavailable,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    lines = [
        "# Advanced Engulfing Batch",
        "",
        "## Setup",
        "",
        f"- Date range: `{args.start}` to `{args.end}`",
        f"- Universe config: `{CONFIG_PATH.relative_to(ROOT)}`",
        f"- Symbols requested: `{len(universe)}`",
        "- Trend filter: price above/below `EMA(50)`",
        "- Structure: confirmed fractal `HH` / `LL`",
        "- Pullback: at least `2` opposite-color candles",
        "- Entry: strict advanced engulfing definition",
        "- Target: fixed `1R`",
        "- EMA slope filter: off in Phase 1",
        "",
        "## Results",
        "",
        "| Group | Symbol | TF | Trades | Win Rate | Avg R | PF | Max DD R | Win Streak | Loss Streak | TP | SL | Verdict |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        verdict = verdict_for(row)
        lines.append(
            f"| `{row['group']}` | `{row['symbol']}` | `{row['timeframe']}` | {row['trades']} | {row['win_rate'] * 100:.2f}% | "
            f"{row['avg_r']:.3f} | {row['profit_factor']:.2f} | {row['max_drawdown_r']:.2f} | "
            f"{row['max_win_streak']} | {row['max_loss_streak']} | {row['tp_hits']} | {row['sl_hits']} | {verdict} |"
        )
    if unavailable:
        lines.extend(
            [
                "",
                "## Unavailable",
                "",
            ]
        )
        for item in unavailable:
            lines.append(
                f"- `{item['symbol']}` (`{item['timeframe']}`, `{item['group']}`): {item['error']}"
            )
    (output_dir / "FIRST_PASS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
