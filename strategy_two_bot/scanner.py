"""Stateful live scanner for Trend Current (strategy #2)."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from little_rzy_bot.market_data import fetch_oanda_ohlcv

from .watchlists import asset_class_for

OANDA_CACHE_DIR = Path("research_data/oanda")
STATE_FILE_NAME = "basket_state.json"
BASKET_RISK_FRACTION = 0.01
COOLDOWN_HOURS = 1

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


@dataclass
class BasketTranche:
    tranche_id: str
    entry_time: str
    entry_price: float
    stop_price: float
    initial_stop_price: float
    initial_risk_per_unit: float
    risk_fraction: float
    bars_held: int = 0
    moved_to_breakeven: bool = False

    def open_risk_fraction(self) -> float:
        if self.stop_price <= self.entry_price:
            return 0.0
        return self.risk_fraction * ((self.stop_price - self.entry_price) / self.initial_risk_per_unit)

    def pnl_fraction(self, price: float) -> float:
        r_multiple = (self.entry_price - price) / self.initial_risk_per_unit
        return self.risk_fraction * r_multiple


@dataclass
class BasketState:
    active_symbol: str | None = None
    active_asset_class: str | None = None
    timeframe: str = "4h"
    last_processed_bar: str | None = None
    basket_opened_at: str | None = None
    cooldowns: dict[str, str] = field(default_factory=dict)
    tranches: list[BasketTranche] = field(default_factory=list)


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


def _state_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / STATE_FILE_NAME


def load_state(output_dir: str | Path) -> BasketState:
    path = _state_path(output_dir)
    if not path.exists():
        return BasketState()
    payload = json.loads(path.read_text() or "{}")
    tranches = [BasketTranche(**tranche) for tranche in payload.get("tranches", [])]
    return BasketState(
        active_symbol=payload.get("active_symbol"),
        active_asset_class=payload.get("active_asset_class"),
        timeframe=payload.get("timeframe", "4h"),
        last_processed_bar=payload.get("last_processed_bar"),
        basket_opened_at=payload.get("basket_opened_at"),
        cooldowns={str(k): str(v) for k, v in payload.get("cooldowns", {}).items()},
        tranches=tranches,
    )


def save_state(output_dir: str | Path, state: BasketState) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = _state_path(out)
    payload = {
        "active_symbol": state.active_symbol,
        "active_asset_class": state.active_asset_class,
        "timeframe": state.timeframe,
        "last_processed_bar": state.last_processed_bar,
        "basket_opened_at": state.basket_opened_at,
        "cooldowns": state.cooldowns,
        "tranches": [asdict(tranche) for tranche in state.tranches],
    }
    path.write_text(json.dumps(payload, indent=2))


def _load_history(symbol: str, granularity: str, environment: str, token: str | None, price: str) -> pd.DataFrame:
    cache_dir = OANDA_CACHE_DIR / symbol
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{granularity}_live.csv"
    if cache_path.exists():
        try:
            cached = pd.read_csv(cache_path, parse_dates=["timestamp"])
            if not cached.empty:
                return cached.set_index("timestamp")
        except Exception:
            pass

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            fetched = fetch_oanda_ohlcv(symbol, granularity, token=token, environment=environment, price=price)
            df = fetched.df
            df.reset_index().to_csv(cache_path, index=False)
            return df
        except Exception as exc:
            last_error = exc
            time.sleep(2 + attempt * 2)
    if cache_path.exists():
        cached = pd.read_csv(cache_path, parse_dates=["timestamp"])
        if not cached.empty:
            return cached.set_index("timestamp")
    raise RuntimeError(f"Failed fetching {symbol} {granularity}") from last_error


def _parse_ts(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    return pd.Timestamp(value)


def _remaining_risk_fraction(tranches: list[BasketTranche]) -> float:
    remaining = BASKET_RISK_FRACTION - sum(tranche.open_risk_fraction() for tranche in tranches)
    return max(0.0, remaining)


def _basket_positive(tranches: list[BasketTranche], current_price: float) -> bool:
    return sum(tranche.pnl_fraction(current_price) for tranche in tranches) > 0


def _event_signal(
    symbol: str,
    asset_class: str,
    timeframe: str,
    timestamp: str,
    setup_id: str,
    summary: str,
    side: str,
    event_type: str,
    entry: float | None = None,
    stop_loss: float | None = None,
    target_1: float | None = None,
    risk_reward: float | None = None,
    quality_score: int | None = None,
    quality_grade: str | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        "symbol": symbol,
        "asset_class": asset_class,
        "timeframe": timeframe,
        "signal_type": side,
        "timestamp": timestamp,
        "setup_id": setup_id,
        "reason_summary": summary,
        "quality_score": quality_score,
        "quality_grade": quality_grade,
        "risk_reward": risk_reward,
        "entry": entry,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "event_type": event_type,
    }
    if extra:
        payload.update(extra)
    return payload


def _row_template(symbol: str, timeframe: str, trend_timeframe: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "asset_class": asset_class_for(symbol),
        "timeframe": timeframe,
        "trend_timeframe": trend_timeframe,
        "alert": "",
        "latest_signal": None,
    }


def _process_active_basket(
    state: BasketState,
    execution: pd.DataFrame,
    trend_view: pd.DataFrame,
    row: dict[str, object],
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    idx = len(execution) - 1
    bar = execution.iloc[idx]
    bar_time = execution.index[idx]
    bar_time_iso = bar_time.isoformat()
    state.last_processed_bar = bar_time_iso
    trend_slice = trend_view[trend_view.index <= bar_time]
    trend_ok = len(trend_slice) >= 220 and regime_bearish(trend_slice, len(trend_slice) - 1)
    trend_break = not trend_ok

    for tranche in state.tranches:
        tranche.bars_held += 1

    current_close = float(bar["close"])
    current_high = float(bar["high"])
    current_low = float(bar["low"])

    for tranche in state.tranches:
        if not tranche.moved_to_breakeven and current_close <= tranche.entry_price - tranche.initial_risk_per_unit:
            tranche.stop_price = tranche.entry_price
            tranche.moved_to_breakeven = True
            events.append(
                _event_signal(
                    symbol=state.active_symbol or "",
                    asset_class=state.active_asset_class or "other",
                    timeframe=state.timeframe,
                    timestamp=bar_time_iso,
                    setup_id=f"strategy_two:move_stop:{tranche.tranche_id}:{bar_time_iso}",
                    summary=(
                        f"Tranche from {tranche.entry_time} reached +1R. Stop is now moved to breakeven at "
                        f"{tranche.entry_price:.5f}, freeing basket risk for a later add."
                    ),
                    side="short",
                    event_type="move_stop",
                    stop_loss=tranche.entry_price,
                    extra={
                        "tranche_id": tranche.tranche_id,
                        "bars_held": tranche.bars_held,
                        "current_close": round(current_close, 6),
                    },
                )
            )

    stop_triggered = any(current_high >= tranche.stop_price for tranche in state.tranches)
    if state.tranches and (stop_triggered or trend_break):
        reason = "stop" if stop_triggered else "trend_break"
        tranche_results: list[str] = []
        total_r = 0.0
        for tranche in state.tranches:
            exit_price = current_close
            r_multiple = (tranche.entry_price - exit_price) / tranche.initial_risk_per_unit
            total_r += r_multiple * (tranche.risk_fraction / BASKET_RISK_FRACTION)
            tranche_results.append(
                f"{tranche.tranche_id}: {r_multiple:.2f}R from {tranche.entry_price:.5f} to {exit_price:.5f}"
            )
        summary = (
            f"Basket exit on {state.active_symbol}. Reason: {reason.replace('_', ' ')}. "
            f"Estimated basket result: {total_r:.2f}R. Tranches: {'; '.join(tranche_results)}"
        )
        events.append(
            _event_signal(
                symbol=state.active_symbol or "",
                asset_class=state.active_asset_class or "other",
                timeframe=state.timeframe,
                timestamp=bar_time_iso,
                setup_id=f"strategy_two:basket_exit:{state.active_symbol}:{bar_time_iso}",
                summary=summary,
                side="short",
                event_type="basket_exit",
                entry=current_close,
                extra={
                    "exit_reason": reason,
                    "tranche_count": len(state.tranches),
                    "basket_result_r": round(total_r, 3),
                    "current_close": round(current_close, 6),
                },
            )
        )
        if reason == "stop" and state.active_symbol:
            cooldown_until = (bar_time + pd.Timedelta(hours=COOLDOWN_HOURS)).isoformat()
            state.cooldowns[state.active_symbol] = cooldown_until
            events.append(
                _event_signal(
                    symbol=state.active_symbol,
                    asset_class=state.active_asset_class or "other",
                    timeframe=state.timeframe,
                    timestamp=bar_time_iso,
                    setup_id=f"strategy_two:cooldown:{state.active_symbol}:{bar_time_iso}",
                    summary=(
                        f"Cooldown started for {state.active_symbol} after a stop-driven basket exit. "
                        f"No new idea on this symbol before {cooldown_until}."
                    ),
                    side="short",
                    event_type="cooldown",
                    extra={"cooldown_until": cooldown_until},
                )
            )
        state.active_symbol = None
        state.active_asset_class = None
        state.basket_opened_at = None
        state.tranches = []
        row["latest_signal"] = events[-1]
        row["alert"] = str(events[-1]["reason_summary"])
        return events

    signal = pullback_signal(execution, idx) if trend_ok else None
    if signal and _basket_positive(state.tranches, current_close):
        remaining_risk = _remaining_risk_fraction(state.tranches)
        if remaining_risk > 0:
            stop_price = float(signal["swing_high"] + signal["atr"])
            risk_per_unit = stop_price - current_close
            if risk_per_unit > 0:
                tranche_id = f"{state.active_symbol}-{len(state.tranches) + 1}-{bar_time.strftime('%Y%m%d%H%M')}"
                tranche = BasketTranche(
                    tranche_id=tranche_id,
                    entry_time=bar_time_iso,
                    entry_price=current_close,
                    stop_price=stop_price,
                    initial_stop_price=stop_price,
                    initial_risk_per_unit=risk_per_unit,
                    risk_fraction=remaining_risk,
                )
                state.tranches.append(tranche)
                score, grade = _quality(signal, bar)
                target_1 = current_close - (risk_per_unit * 2.0)
                summary = (
                    f"Add confirmed on {state.active_symbol}. Existing basket stayed in profit, risk was freed by prior "
                    f"breakeven moves, and a fresh 4h pullback rejected the Alligator zone."
                )
                event = _event_signal(
                    symbol=state.active_symbol or "",
                    asset_class=state.active_asset_class or "other",
                    timeframe=state.timeframe,
                    timestamp=bar_time_iso,
                    setup_id=f"strategy_two:add:{tranche_id}",
                    summary=summary,
                    side="short",
                    event_type="add",
                    entry=current_close,
                    stop_loss=stop_price,
                    target_1=target_1,
                    risk_reward=2.0,
                    quality_score=score,
                    quality_grade=grade,
                    extra={
                        "tranche_id": tranche_id,
                        "risk_fraction": round(remaining_risk, 5),
                        "open_basket_risk_fraction": round(sum(t.open_risk_fraction() for t in state.tranches), 5),
                    },
                )
                events.append(event)
                row["latest_signal"] = event
                row["alert"] = (
                    f"{state.active_symbol} ADD 4H SHORT | entry {current_close:.6f} | stop {stop_price:.6f} | "
                    f"tp1 {target_1:.6f} | tranche risk {remaining_risk*100:.2f}%"
                )
    return events


def _select_best_candidate(candidates: list[tuple[dict[str, object], dict[str, float], pd.Series, pd.Timestamp]]) -> tuple[dict[str, object], dict[str, float], pd.Series, pd.Timestamp] | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (_quality(item[1], item[2])[0], item[1]["pullback_size"]), reverse=True)[0]


def run_live_cycle(
    symbols: list[str],
    granularity: str,
    higher_timeframe: str,
    environment: str,
    token: str | None,
    price: str,
    output_dir: str | Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], BasketState]:
    state = load_state(output_dir)
    exec_code = _granularity_code(granularity)
    trend_code = _granularity_code(higher_timeframe)
    timeframe = _timeframe_label(granularity)
    trend_timeframe = _timeframe_label(higher_timeframe)
    rows: list[dict[str, object]] = []
    events: list[dict[str, object]] = []

    if state.active_symbol:
        active_symbols = [state.active_symbol]
    else:
        active_symbols = list(symbols)

    candidates: list[tuple[dict[str, object], dict[str, float], pd.Series, pd.Timestamp]] = []

    for symbol in active_symbols:
        row = _row_template(symbol, timeframe, trend_timeframe)
        try:
            execution = with_indicators(_load_history(symbol, exec_code, environment=environment, token=token, price=price))
            trend_view = with_indicators(_load_history(symbol, trend_code, environment=environment, token=token, price=price))
        except Exception as exc:
            row["error"] = str(exc)
            rows.append(row)
            continue

        if len(execution) < 220 or len(trend_view) < 220:
            row["error"] = "Not enough history"
            rows.append(row)
            continue

        idx = len(execution) - 1
        bar = execution.iloc[idx]
        bar_time = execution.index[idx]
        bar_time_iso = bar_time.isoformat()

        if state.active_symbol == symbol:
            row["active_basket"] = True
            if state.last_processed_bar == bar_time_iso:
                row["note"] = "Latest bar already processed"
                rows.append(row)
                continue
            active_events = _process_active_basket(state, execution, trend_view, row)
            events.extend(active_events)
            rows.append(row)
            continue

        cooldown_until = _parse_ts(state.cooldowns.get(symbol))
        if cooldown_until is not None and bar_time < cooldown_until:
            row["note"] = f"Cooldown until {cooldown_until.isoformat()}"
            rows.append(row)
            continue

        trend_slice = trend_view[trend_view.index <= bar_time]
        if len(trend_slice) < 220 or not regime_bearish(trend_slice, len(trend_slice) - 1):
            rows.append(row)
            continue

        signal = pullback_signal(execution, idx)
        if not signal:
            rows.append(row)
            continue

        score, grade = _quality(signal, bar)
        stop_price = float(signal["swing_high"] + signal["atr"])
        entry_price = float(bar["close"])
        risk_per_unit = stop_price - entry_price
        if risk_per_unit <= 0:
            rows.append(row)
            continue
        target_1 = entry_price - (risk_per_unit * 2.0)
        preview = _event_signal(
            symbol=symbol,
            asset_class=asset_class_for(symbol),
            timeframe=timeframe,
            timestamp=bar_time_iso,
            setup_id=f"strategy_two:entry:{symbol}:{bar_time_iso}",
            summary=(
                f"Daily Alligator trend remains bearish and the latest {timeframe} pullback rejected the "
                f"Alligator zone. Entry models continuation lower with a structure stop above the swing high plus ATR."
            ),
            side="short",
            event_type="entry",
            entry=entry_price,
            stop_loss=stop_price,
            target_1=target_1,
            risk_reward=2.0,
            quality_score=score,
            quality_grade=grade,
            extra={
                "risk_fraction": round(BASKET_RISK_FRACTION, 5),
                "pullback_size": signal["pullback_size"],
                "zone_low": signal["zone_low"],
                "zone_high": signal["zone_high"],
            },
        )
        row["latest_signal"] = preview
        row["alert"] = (
            f"{symbol} 4H SHORT | entry {entry_price:.6f} | stop {stop_price:.6f} | "
            f"tp1 {target_1:.6f} | score {score}/{grade}"
        )
        rows.append(row)
        candidates.append((row, signal, bar, bar_time))

    if not state.active_symbol:
        best = _select_best_candidate(candidates)
        if best is not None:
            row, signal, bar, bar_time = best
            entry_price = float(bar["close"])
            stop_price = float(signal["swing_high"] + signal["atr"])
            risk_per_unit = stop_price - entry_price
            score, grade = _quality(signal, bar)
            target_1 = entry_price - (risk_per_unit * 2.0)
            tranche_id = f"{row['symbol']}-1-{bar_time.strftime('%Y%m%d%H%M')}"
            state.active_symbol = str(row["symbol"])
            state.active_asset_class = str(row["asset_class"])
            state.timeframe = timeframe
            state.basket_opened_at = bar_time.isoformat()
            state.last_processed_bar = bar_time.isoformat()
            state.tranches = [
                BasketTranche(
                    tranche_id=tranche_id,
                    entry_time=bar_time.isoformat(),
                    entry_price=entry_price,
                    stop_price=stop_price,
                    initial_stop_price=stop_price,
                    initial_risk_per_unit=risk_per_unit,
                    risk_fraction=BASKET_RISK_FRACTION,
                )
            ]
            entry_event = _event_signal(
                symbol=str(row["symbol"]),
                asset_class=str(row["asset_class"]),
                timeframe=timeframe,
                timestamp=bar_time.isoformat(),
                setup_id=f"strategy_two:entry:{tranche_id}",
                summary=(
                    f"Trend Current opened a new basket on {row['symbol']}. This is the first tranche under the 1% "
                    f"idea-risk cap, using the locked Alligator trend + pullback continuation model."
                ),
                side="short",
                event_type="entry",
                entry=entry_price,
                stop_loss=stop_price,
                target_1=target_1,
                risk_reward=2.0,
                quality_score=score,
                quality_grade=grade,
                extra={
                    "tranche_id": tranche_id,
                    "risk_fraction": round(BASKET_RISK_FRACTION, 5),
                    "pullback_size": signal["pullback_size"],
                    "zone_low": signal["zone_low"],
                    "zone_high": signal["zone_high"],
                },
            )
            events.append(entry_event)
            row["latest_signal"] = entry_event

    save_state(output_dir, state)
    return rows, events, state


def save_scan_outputs(output_dir: str | Path, rows: list[dict[str, object]], events: list[dict[str, object]], state: BasketState) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scan_results.json").write_text(json.dumps(rows, indent=2))
    alerts = [str(event["reason_summary"]) for event in events]
    (out / "alerts.txt").write_text("\n".join(alerts))
    (out / "basket_state.json").write_text(
        json.dumps(
            {
                "active_symbol": state.active_symbol,
                "active_asset_class": state.active_asset_class,
                "timeframe": state.timeframe,
                "last_processed_bar": state.last_processed_bar,
                "basket_opened_at": state.basket_opened_at,
                "cooldowns": state.cooldowns,
                "tranches": [asdict(tranche) for tranche in state.tranches],
            },
            indent=2,
        )
    )
