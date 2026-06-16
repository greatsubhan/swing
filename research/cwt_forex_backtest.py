"""First-pass CWT / Cambist + Alligator backtest on forex majors.

This runner intentionally focuses on setup quality first:

- H1 bias
- M5 / M15 execution
- Scenario 1 and Scenario 2 only
- fixed 1R exit and Jaw-trailing exit variants

It uses an MT5-style ZigZag approximation for the Cambist structure layer:

- Depth = 12
- Deviation = 5 points
- Backstep = 3
"""
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

START = "2025-01-01"
END = "2026-04-01"
OANDA_ENV = "practice"
OANDA_CACHE_DIR = Path("research_data/cwt_oanda")
OUTPUT_DIR = Path("reports/cwt_forex")

ASSETS = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "NZD_USD",
    "USD_CHF",
]

EXECUTION_CONFIGS = [
    {"granularity": "M5", "label": "5m"},
    {"granularity": "M15", "label": "15m"},
]

EXIT_MODES = [
    {"name": "rr1", "label": "Fixed 1R"},
    {"name": "jaw_trail", "label": "Jaw Trail"},
]

ZIGZAG_DEPTH = 12
ZIGZAG_DEVIATION_POINTS = 5
ZIGZAG_BACKSTEP = 3
PULLBACK_LOOKBACK = 10
ALLIGATOR_SPREAD_FRACTION = 0.08
BUFFER_ATR_FRACTION = 0.05
MAX_BARS_HELD = 96

# --- Regime & Alligator quality constants (research-backed) ---
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 20.0  # ADX >= 20 indicates a trending market
ADX_STRONG_TREND = 25.0     # ADX >= 25 indicates a strong trend
ALLIGATOR_SLEEP_THRESHOLD = 0.03  # mouth spread as fraction of ATR; below this = sleeping
ALLIGATOR_AWAKENING_BARS = 3      # bars since sleep ended to qualify as awakening


@dataclass
class Position:
    symbol: str
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    target_price: float | None
    initial_risk: float
    scenario: str
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


def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha = pd.DataFrame(index=df.index)
    ha["ha_close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ha_open_values: list[float] = []
    for idx, row in enumerate(df.itertuples()):
        if idx == 0:
            ha_open_values.append((row.open + row.close) / 2)
        else:
            ha_open_values.append((ha_open_values[-1] + float(ha["ha_close"].iloc[idx - 1])) / 2)
    ha["ha_open"] = ha_open_values
    ha["ha_high"] = pd.concat([df["high"], ha["ha_open"], ha["ha_close"]], axis=1).max(axis=1)
    ha["ha_low"] = pd.concat([df["low"], ha["ha_open"], ha["ha_close"]], axis=1).min(axis=1)
    return ha


def adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.Series:
    """Compute Average Directional Index (ADX) for regime detection.

    ADX measures trend strength regardless of direction.
    - ADX < 20: ranging / no clear trend (Alligator should sleep)
    - ADX 20-25: emerging trend
    - ADX >= 25: strong trend (Alligator conditions favorable)
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_smooth = true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr_smooth)

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10) * 100
    adx_value = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return adx_value.rename("adx14")


def alligator_mouth_width(row: pd.Series) -> float:
    """Measure Alligator mouth width as lips-jaw spread normalised by ATR.

    A wider mouth indicates a stronger, more established trend.
    Returns a dimensionless ratio: spread / ATR.
    """
    if pd.isna(row["jaw"]) or pd.isna(row["lips"]) or pd.isna(row["atr14"]) or row["atr14"] == 0:
        return 0.0
    return abs(float(row["lips"]) - float(row["jaw"])) / float(row["atr14"])


def alligator_sleeping(row: pd.Series) -> bool:
    """Detect if the Alligator is 'sleeping' (lines intertwined / flat).

    Bill Williams described this as the mouth being closed — the three lines
    are close together or crossing each other. In this state the Alligator
    gives no directional signal and any trade based on it is noise.

    The detection uses the mouth-width normalised by ATR: if the spread
    between lips and jaw is smaller than ALLIGATOR_SLEEP_THRESHOLD * ATR,
    the Alligator is sleeping.
    """
    width = alligator_mouth_width(row)
    return width < ALLIGATOR_SLEEP_THRESHOLD


def alligator_awakening(idx: int, frame: pd.DataFrame, lookback: int = ALLIGATOR_AWAKENING_BARS) -> bool:
    """Detect when the Alligator transitions from sleeping to waking.

    Returns True if the current bar has a mouth width above the sleep
    threshold AND at least one of the previous `lookback` bars was sleeping.
    This marks the earliest moments of a new trend — historically the
    highest-probability entry window for Alligator-based strategies.
    """
    if idx < lookback:
        return False
    current_row = frame.iloc[idx]
    if alligator_sleeping(current_row):
        return False
    for back in range(1, lookback + 1):
        prev_row = frame.iloc[idx - back]
        if alligator_sleeping(prev_row):
            return True
    return False


def with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    median_price = (enriched["high"] + enriched["low"]) / 2
    enriched["atr14"] = atr(enriched, 14)
    enriched["jaw"] = smma(median_price, 13).shift(8)
    enriched["teeth"] = smma(median_price, 8).shift(5)
    enriched["lips"] = smma(median_price, 5).shift(3)
    ha = heikin_ashi(enriched)
    for column in ha.columns:
        enriched[column] = ha[column]

    # --- Regime & Alligator quality columns ---
    enriched["adx14"] = adx(enriched, ADX_PERIOD)
    enriched["mouth_width"] = enriched.apply(alligator_mouth_width, axis=1)
    enriched["alligator_sleeping"] = enriched.apply(alligator_sleeping, axis=1)

    return enriched


def load_oanda_history(symbol: str, granularity: str, start: str = START, end: str = END) -> pd.DataFrame:
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
        except Exception as exc:  # pragma: no cover - research retry path
            last_error = exc
            time.sleep(2 + attempt * 2)
    else:
        raise RuntimeError(f"Failed fetching {symbol} {granularity}") from last_error

    df = fetched.df.reset_index()
    df.to_csv(csv_path, index=False)
    return fetched.df


def alligator_bias(row: pd.Series, previous_row: pd.Series) -> int:
    if pd.isna(row["jaw"]) or pd.isna(row["teeth"]) or pd.isna(row["lips"]):
        return 0
    spread = abs(row["lips"] - row["jaw"])
    if row["close"] > row["lips"] > row["teeth"] > row["jaw"] and row["jaw"] > previous_row["jaw"]:
        if spread >= row["atr14"] * ALLIGATOR_SPREAD_FRACTION:
            return 1
    if row["close"] < row["lips"] < row["teeth"] < row["jaw"] and row["jaw"] < previous_row["jaw"]:
        if spread >= row["atr14"] * ALLIGATOR_SPREAD_FRACTION:
            return -1
    return 0


def compute_bias_series(frame: pd.DataFrame) -> pd.Series:
    signals = [0]
    for idx in range(1, len(frame)):
        signals.append(alligator_bias(frame.iloc[idx], frame.iloc[idx - 1]))
    return pd.Series(signals, index=frame.index, dtype="int64")


def infer_point_size(frame: pd.DataFrame, symbol: str) -> float:
    if "JPY" in symbol:
        return 0.001
    if symbol in {"EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD", "USD_CAD", "USD_CHF", "EUR_GBP", "EUR_CHF"}:
        return 0.00001

    sample = frame["close"].dropna().head(200)
    decimal_places: list[int] = []
    for value in sample:
        rendered = f"{float(value):.10f}".rstrip("0").rstrip(".")
        if "." in rendered:
            decimal_places.append(len(rendered.split(".")[1]))
        else:
            decimal_places.append(0)
    max_decimals = max(decimal_places) if decimal_places else 2
    return 10 ** (-max_decimals)


def compute_mt5_zigzag(frame: pd.DataFrame, symbol: str) -> tuple[pd.Series, pd.Series]:
    """Approximate MT5 ZigZag confirmation using Depth / Deviation / Backstep.

    This remains an approximation, but it is materially closer to the lecture
    screenshots than the earlier generic pivot window.
    """

    pivot_high = pd.Series(False, index=frame.index)
    pivot_low = pd.Series(False, index=frame.index)
    highs = frame["high"].reset_index(drop=True)
    lows = frame["low"].reset_index(drop=True)
    deviation_abs = ZIGZAG_DEVIATION_POINTS * infer_point_size(frame, symbol)

    last_high_idx: int | None = None
    last_low_idx: int | None = None
    last_confirmed_price: float | None = None
    last_confirmed_side: str | None = None

    for confirm_idx in range(ZIGZAG_DEPTH, len(frame)):
        pivot_idx = confirm_idx - ZIGZAG_DEPTH
        left = max(0, pivot_idx - ZIGZAG_DEPTH)
        right = min(len(frame) - 1, pivot_idx + ZIGZAG_DEPTH)

        high_window = highs.iloc[left : right + 1]
        low_window = lows.iloc[left : right + 1]
        pivot_high_candidate = highs.iloc[pivot_idx] == high_window.max()
        pivot_low_candidate = lows.iloc[pivot_idx] == low_window.min()

        if pivot_high_candidate:
            if last_high_idx is not None and pivot_idx - last_high_idx <= ZIGZAG_BACKSTEP:
                if highs.iloc[pivot_idx] >= highs.iloc[last_high_idx]:
                    pivot_high.iloc[last_high_idx] = False
                    last_high_idx = pivot_idx
                else:
                    pivot_high_candidate = False
            else:
                last_high_idx = pivot_idx

            if pivot_high_candidate:
                candidate_price = float(highs.iloc[pivot_idx])
                if last_confirmed_side == "high" and last_confirmed_price is not None:
                    if candidate_price >= last_confirmed_price:
                        previous_idx = pivot_high[pivot_high].index[-1] if pivot_high.any() else None
                        if previous_idx is not None:
                            pivot_high.loc[previous_idx] = False
                        pivot_high.iloc[pivot_idx] = True
                        last_confirmed_price = candidate_price
                    continue
                if last_confirmed_price is None or abs(candidate_price - last_confirmed_price) >= deviation_abs:
                    pivot_high.iloc[pivot_idx] = True
                    last_confirmed_price = candidate_price
                    last_confirmed_side = "high"

        if pivot_low_candidate:
            if last_low_idx is not None and pivot_idx - last_low_idx <= ZIGZAG_BACKSTEP:
                if lows.iloc[pivot_idx] <= lows.iloc[last_low_idx]:
                    pivot_low.iloc[last_low_idx] = False
                    last_low_idx = pivot_idx
                else:
                    pivot_low_candidate = False
            else:
                last_low_idx = pivot_idx

            if pivot_low_candidate:
                candidate_price = float(lows.iloc[pivot_idx])
                if last_confirmed_side == "low" and last_confirmed_price is not None:
                    if candidate_price <= last_confirmed_price:
                        previous_idx = pivot_low[pivot_low].index[-1] if pivot_low.any() else None
                        if previous_idx is not None:
                            pivot_low.loc[previous_idx] = False
                        pivot_low.iloc[pivot_idx] = True
                        last_confirmed_price = candidate_price
                    continue
                if last_confirmed_price is None or abs(candidate_price - last_confirmed_price) >= deviation_abs:
                    pivot_low.iloc[pivot_idx] = True
                    last_confirmed_price = candidate_price
                    last_confirmed_side = "low"

    return pivot_high, pivot_low


def project_cambist_levels(frame: pd.DataFrame, pivot_high: pd.Series, pivot_low: pd.Series) -> pd.DataFrame:
    projected = pd.DataFrame(index=frame.index)
    projected["active_blue"] = float("nan")
    projected["active_red"] = float("nan")

    for idx in range(len(frame) - ZIGZAG_DEPTH):
        if pivot_high.iloc[idx]:
            projected.iloc[idx + ZIGZAG_DEPTH, projected.columns.get_loc("active_blue")] = float(frame["high"].iloc[idx])
        if pivot_low.iloc[idx]:
            projected.iloc[idx + ZIGZAG_DEPTH, projected.columns.get_loc("active_red")] = float(frame["low"].iloc[idx])

    projected["active_blue"] = projected["active_blue"].ffill()
    projected["active_red"] = projected["active_red"].ffill()
    return projected


def scenario_one_long(frame: pd.DataFrame, idx: int, bias: int) -> dict[str, float] | None:
    if bias != 1:
        return None
    row = frame.iloc[idx]
    previous = frame.iloc[idx - 1]
    if pd.isna(row["jaw"]) or pd.isna(row["atr14"]):
        return None
    recent = frame.iloc[max(0, idx - PULLBACK_LOOKBACK) : idx + 1]
    touched_pullback_zone = recent["low"].min() <= recent["teeth"].max()
    bullish_heiken = row["ha_close"] > row["ha_open"]
    above_lips = row["ha_low"] > row["lips"]
    open_mouth = row["lips"] > row["teeth"] > row["jaw"]
    expanding = row["lips"] > previous["lips"] and row["jaw"] >= previous["jaw"]
    breakout = row["close"] > previous["high"]
    if touched_pullback_zone and bullish_heiken and above_lips and open_mouth and expanding and breakout:
        return {"stop_anchor": float(row["jaw"]), "atr": float(row["atr14"]), "scenario": "scenario1"}
    return None


def scenario_one_short(frame: pd.DataFrame, idx: int, bias: int) -> dict[str, float] | None:
    if bias != -1:
        return None
    row = frame.iloc[idx]
    previous = frame.iloc[idx - 1]
    if pd.isna(row["jaw"]) or pd.isna(row["atr14"]):
        return None
    recent = frame.iloc[max(0, idx - PULLBACK_LOOKBACK) : idx + 1]
    touched_pullback_zone = recent["high"].max() >= recent["teeth"].min()
    bearish_heiken = row["ha_close"] < row["ha_open"]
    below_lips = row["ha_high"] < row["lips"]
    open_mouth = row["lips"] < row["teeth"] < row["jaw"]
    expanding = row["lips"] < previous["lips"] and row["jaw"] <= previous["jaw"]
    breakdown = row["close"] < previous["low"]
    if touched_pullback_zone and bearish_heiken and below_lips and open_mouth and expanding and breakdown:
        return {"stop_anchor": float(row["jaw"]), "atr": float(row["atr14"]), "scenario": "scenario1"}
    return None


def scenario_two_long(frame: pd.DataFrame, idx: int, bias: int, active_red: float | None) -> dict[str, float] | None:
    if bias != 1 or active_red is None:
        return None
    row = frame.iloc[idx]
    previous = frame.iloc[idx - 1]
    if pd.isna(row["jaw"]) or pd.isna(row["atr14"]):
        return None
    mouth_pointing_down = previous["lips"] < previous["teeth"] < previous["jaw"]
    close_back_above_jaw = row["close"] > row["jaw"] and previous["close"] <= previous["jaw"]
    bullish_heiken = row["ha_close"] > row["ha_open"]
    if mouth_pointing_down and close_back_above_jaw and bullish_heiken:
        return {"stop_anchor": active_red, "atr": float(row["atr14"]), "scenario": "scenario2"}
    return None


def scenario_two_short(frame: pd.DataFrame, idx: int, bias: int, active_blue: float | None) -> dict[str, float] | None:
    if bias != -1 or active_blue is None:
        return None
    row = frame.iloc[idx]
    previous = frame.iloc[idx - 1]
    if pd.isna(row["jaw"]) or pd.isna(row["atr14"]):
        return None
    mouth_pointing_up = previous["lips"] > previous["teeth"] > previous["jaw"]
    close_back_below_jaw = row["close"] < row["jaw"] and previous["close"] >= previous["jaw"]
    bearish_heiken = row["ha_close"] < row["ha_open"]
    if mouth_pointing_up and close_back_below_jaw and bearish_heiken:
        return {"stop_anchor": active_blue, "atr": float(row["atr14"]), "scenario": "scenario2"}
    return None


def trailing_stop(position: Position, row: pd.Series) -> float:
    buffer = row["atr14"] * BUFFER_ATR_FRACTION if not pd.isna(row["atr14"]) else 0.0
    if position.side == "long":
        return max(position.stop_price, float(row["jaw"] - buffer))
    return min(position.stop_price, float(row["jaw"] + buffer))


def run_backtest(
    symbol: str,
    execution_granularity: str,
    execution_label: str,
    exit_mode: str,
    start: str = START,
    end: str = END,
) -> dict[str, object]:
    execution = with_indicators(load_oanda_history(symbol, execution_granularity, start=start, end=end))
    bias_frame = with_indicators(load_oanda_history(symbol, "H1", start=start, end=end))
    pivot_high, pivot_low = compute_mt5_zigzag(execution, symbol)
    cambist = project_cambist_levels(execution, pivot_high, pivot_low)
    bias_frame = bias_frame.copy()
    bias_frame["bias_signal"] = compute_bias_series(bias_frame)
    execution = execution.sort_index().copy()
    execution["timestamp"] = execution.index
    execution["ts_key"] = pd.Index(execution.index).asi8
    bias_lookup = bias_frame[["bias_signal"]].sort_index().copy()
    bias_lookup["ts_key"] = pd.Index(bias_lookup.index).asi8
    execution = pd.merge_asof(
        execution,
        bias_lookup[["ts_key", "bias_signal"]],
        on="ts_key",
        direction="backward",
    )
    execution = execution.set_index("timestamp").drop(columns=["ts_key"])
    execution["bias_signal"] = execution["bias_signal"].fillna(0).astype("int64")
    execution["active_blue"] = cambist["active_blue"]
    execution["active_red"] = cambist["active_red"]

    position: Position | None = None
    trade_log: list[dict[str, object]] = []
    scenario_counts = {"scenario1": 0, "scenario2": 0}

    for idx in range(120, len(execution) - 1):
        row = execution.iloc[idx]
        bar_time = execution.index[idx]
        if pd.isna(row["atr14"]) or pd.isna(row["jaw"]):
            continue

        bias = int(row["bias_signal"])
        active_blue = float(row["active_blue"]) if pd.notna(row["active_blue"]) else None
        active_red = float(row["active_red"]) if pd.notna(row["active_red"]) else None

        if position is not None:
            position.bars_held += 1
            if exit_mode == "jaw_trail":
                previous_row = execution.iloc[idx - 1]
                position.stop_price = trailing_stop(position, previous_row)

            exit_price: float | None = None
            reason: str | None = None
            if position.side == "long":
                if row["low"] <= position.stop_price:
                    exit_price = position.stop_price
                    reason = "stop"
                elif position.target_price is not None and row["high"] >= position.target_price:
                    exit_price = position.target_price
                    reason = "target"
                elif bias == -1:
                    exit_price = float(row["close"])
                    reason = "bias_flip"
            else:
                if row["high"] >= position.stop_price:
                    exit_price = position.stop_price
                    reason = "stop"
                elif position.target_price is not None and row["low"] <= position.target_price:
                    exit_price = position.target_price
                    reason = "target"
                elif bias == 1:
                    exit_price = float(row["close"])
                    reason = "bias_flip"

            if exit_price is None and position.bars_held >= MAX_BARS_HELD:
                exit_price = float(row["close"])
                reason = "timeout"

            if exit_price is not None and reason is not None:
                if position.side == "long":
                    r_multiple = (exit_price - position.entry_price) / position.initial_risk
                else:
                    r_multiple = (position.entry_price - exit_price) / position.initial_risk
                trade_log.append(
                    {
                        "symbol": symbol,
                        "side": position.side,
                        "entry_time": position.entry_time.isoformat(),
                        "exit_time": bar_time.isoformat(),
                        "entry_price": round(position.entry_price, 6),
                        "exit_price": round(exit_price, 6),
                        "bars_held": position.bars_held,
                        "r_multiple": round(float(r_multiple), 3),
                        "reason": reason,
                        "scenario": position.scenario,
                    }
                )
                position = None
                continue

        if position is not None:
            continue

        long_signal = scenario_one_long(execution, idx, bias)
        short_signal = scenario_one_short(execution, idx, bias)
        if long_signal is None and short_signal is None:
            long_signal = scenario_two_long(execution, idx, bias, active_red)
            short_signal = scenario_two_short(execution, idx, bias, active_blue)

        signal = long_signal if long_signal is not None else short_signal
        if signal is None:
            continue

        next_bar = execution.iloc[idx + 1]
        entry_time = execution.index[idx + 1]
        entry_price = float(next_bar["open"])
        buffer = signal["atr"] * BUFFER_ATR_FRACTION
        if signal is long_signal:
            side = "long"
            stop_price = float(signal["stop_anchor"] - buffer)
            if stop_price >= entry_price:
                continue
            risk = entry_price - stop_price
            target = entry_price + risk if exit_mode == "rr1" else None
        else:
            side = "short"
            stop_price = float(signal["stop_anchor"] + buffer)
            if stop_price <= entry_price:
                continue
            risk = stop_price - entry_price
            target = entry_price - risk if exit_mode == "rr1" else None

        if risk <= 0:
            continue

        scenario_counts[signal["scenario"]] += 1
        position = Position(
            symbol=symbol,
            side=side,
            entry_time=entry_time,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target,
            initial_risk=risk,
            scenario=signal["scenario"],
        )

    if position is not None:
        final_bar = execution.iloc[-1]
        final_price = float(final_bar["close"])
        if position.side == "long":
            r_multiple = (final_price - position.entry_price) / position.initial_risk
        else:
            r_multiple = (position.entry_price - final_price) / position.initial_risk
        trade_log.append(
            {
                "symbol": symbol,
                "side": position.side,
                "entry_time": position.entry_time.isoformat(),
                "exit_time": execution.index[-1].isoformat(),
                "entry_price": round(position.entry_price, 6),
                "exit_price": round(final_price, 6),
                "bars_held": position.bars_held,
                "r_multiple": round(float(r_multiple), 3),
                "reason": "final_bar",
                "scenario": position.scenario,
            }
        )

    r_values = [trade["r_multiple"] for trade in trade_log]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    avg_hold = sum(trade["bars_held"] for trade in trade_log) / len(trade_log) if trade_log else 0.0
    return {
        "symbol": symbol,
        "execution_timeframe": execution_label,
        "exit_mode": exit_mode,
        "date_range": {"start": start, "end": end},
        "trades": len(trade_log),
        "win_rate": round((len(wins) / len(trade_log)) * 100, 2) if trade_log else 0.0,
        "avg_r": round(sum(r_values) / len(r_values), 3) if r_values else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
        "total_r": round(sum(r_values), 3),
        "avg_bars_held": round(avg_hold, 2),
        "scenario1_entries": scenario_counts["scenario1"],
        "scenario2_entries": scenario_counts["scenario2"],
    }


def main() -> None:
    load_dotenv(".env")
    ensure_dir(OUTPUT_DIR)

    results: list[dict[str, object]] = []
    for symbol in ASSETS:
        for execution_config in EXECUTION_CONFIGS:
            for exit_mode in EXIT_MODES:
                result = run_backtest(
                    symbol=symbol,
                    execution_granularity=execution_config["granularity"],
                    execution_label=execution_config["label"],
                    exit_mode=exit_mode["name"],
                )
                results.append(result)

    output_path = OUTPUT_DIR / "summary.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
