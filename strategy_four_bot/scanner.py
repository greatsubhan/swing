"""Live scanner for CWT / Cambist with Trend."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from little_rzy_bot.market_data import fetch_oanda_ohlcv
from research.cwt_forex_backtest import (
    ADX_STRONG_TREND,
    ADX_TREND_THRESHOLD,
    BUFFER_ATR_FRACTION,
    alligator_awakening,
    alligator_sleeping,
    alligator_mouth_width,
    compute_bias_series,
    compute_mt5_zigzag,
    project_cambist_levels,
    scenario_one_long,
    scenario_one_short,
    scenario_two_long,
    scenario_two_short,
    with_indicators,
)
from signal_platform.journal import load_journal

from .watchlists import asset_class_for, minimum_timeframe_for

OANDA_CACHE_DIR = Path("research_data/cwt_live")
STATE_FILE_NAME = "ladder_state.json"
LADDER_SEQUENCE = [0.07, 0.20, 0.45, 1.00]
LOOKBACK_DAYS = 240
TIMEFRAME_TO_OANDA = {"5m": "M5", "15m": "M15", "30m": "M30", "1h": "H1", "4h": "H4"}
NOISE_LOOKBACK_BARS = 6

# Default bias timeframe — research shows H4/Daily far superior to H1 for
# Alligator-based strategies.  H1 is kept as a fallback for assets that
# require tighter execution.
DEFAULT_BIAS_TIMEFRAME = "H4"
BIAS_TIMEFRAME_TO_OANDA = {"1h": "H1", "4h": "H4", "D": "D"}


@dataclass(frozen=True)
class CwtRegimeConfig:
    """Controls whether regime-based filtering is applied.

    When enabled the scanner will:
    - Skip entries when the ADX on the bias timeframe is below `min_adx`
      (ranging market, Alligator historically underperforms).
    - Skip entries when the Alligator is sleeping on the execution timeframe
      (lines intertwined, no directional edge).
    - Flag entries that occur during an Alligator awakening (highest-probability
      window per research).
    """
    enabled: bool = True
    min_adx: float = ADX_TREND_THRESHOLD  # 20.0 — below this, markets are ranging
    strong_adx: float = ADX_STRONG_TREND  # 25.0 — above this, strong trend confirmed
    bias_timeframe: str = DEFAULT_BIAS_TIMEFRAME  # "H4" preferred per research


@dataclass(frozen=True)
class CwtQualityLayerConfig:
    require_followthrough: bool = False
    skip_high_noise: bool = False
    stop_scale: float = 1.0
    min_atr_multiple: float = 0.0


@dataclass(frozen=True)
class CwtFwmConfig:
    enabled_symbols: frozenset[str] = frozenset()
    swing_lookback_bars: int = 8
    order_valid_bars: int = 2


def quality_layer_from_extra(extra: dict[str, object] | None) -> CwtQualityLayerConfig:
    payload = (extra or {}).get("quality_layer", {})
    if not isinstance(payload, dict):
        return CwtQualityLayerConfig()
    return CwtQualityLayerConfig(
        require_followthrough=bool(payload.get("require_followthrough", False)),
        skip_high_noise=bool(payload.get("skip_high_noise", False)),
        stop_scale=float(payload.get("stop_scale", 1.0)),
        min_atr_multiple=float(payload.get("min_atr_multiple", 0.0)),
    )


def fwm_config_from_extra(extra: dict[str, object] | None) -> CwtFwmConfig:
    payload = (extra or {}).get("fwm_selective", {})
    if not isinstance(payload, dict):
        return CwtFwmConfig()
    enabled_symbols = payload.get("enabled_symbols", [])
    if not isinstance(enabled_symbols, list):
        enabled_symbols = []
    return CwtFwmConfig(
        enabled_symbols=frozenset(str(symbol) for symbol in enabled_symbols),
        swing_lookback_bars=int(payload.get("swing_lookback_bars", 8)),
        order_valid_bars=int(payload.get("order_valid_bars", 2)),
    )


def regime_config_from_extra(extra: dict[str, object] | None) -> CwtRegimeConfig:
    """Build a CwtRegimeConfig from the strategy's extra config block.

    Example config (in the platform route JSON):
        "regime": {
            "enabled": true,
            "min_adx": 20.0,
            "strong_adx": 25.0,
            "bias_timeframe": "H4"
        }
    """
    payload = (extra or {}).get("regime", {})
    if not isinstance(payload, dict):
        return CwtRegimeConfig()
    return CwtRegimeConfig(
        enabled=bool(payload.get("enabled", True)),
        min_adx=float(payload.get("min_adx", ADX_TREND_THRESHOLD)),
        strong_adx=float(payload.get("strong_adx", ADX_STRONG_TREND)),
        bias_timeframe=str(payload.get("bias_timeframe", DEFAULT_BIAS_TIMEFRAME)),
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _cache_path(symbol: str, granularity: str) -> Path:
    return OANDA_CACHE_DIR / symbol / f"{granularity}_live.csv"


def load_state(output_dir: str | Path) -> dict[str, object]:
    path = Path(output_dir) / STATE_FILE_NAME
    if not path.exists():
        return {"symbols": {}}
    return json.loads(path.read_text() or '{"symbols": {}}')


def save_state(output_dir: str | Path, state: dict[str, object]) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / STATE_FILE_NAME).write_text(json.dumps(state, indent=2))


def _history_start() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()


def _parse_event_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def load_history(symbol: str, granularity: str, environment: str, token: str | None, price: str) -> pd.DataFrame:
    cache_path = _cache_path(symbol, granularity)
    ensure_dir(cache_path.parent)
    cached: pd.DataFrame | None = None
    if cache_path.exists():
        try:
            cached = pd.read_csv(cache_path, parse_dates=["timestamp"])
            if cached is not None and not cached.empty:
                cached["timestamp"] = pd.to_datetime(cached["timestamp"], utc=True)
        except Exception:
            cached = None

    refresh_start = _history_start()
    if cached is not None and not cached.empty:
        latest_cached = pd.Timestamp(cached["timestamp"].max())
        refresh_start = (latest_cached - timedelta(days=5)).date().isoformat()

    fetched = fetch_oanda_ohlcv(
        instrument=symbol,
        granularity=granularity,
        start=refresh_start,
        end=None,
        price=price,
        token=token,
        environment=environment,
    )
    df = fetched.df
    if not df.empty and df.index.tz is None:
        df.index = pd.to_datetime(df.index, utc=True)
    if cached is not None and not cached.empty:
        merged = pd.concat([cached.set_index("timestamp"), df]).sort_index()
        merged = merged[~merged.index.duplicated(keep="last")]
        merged = merged.loc[merged.index >= pd.Timestamp(_history_start(), tz="UTC")]
        merged.reset_index().to_csv(cache_path, index=False)
        return merged

    df.reset_index().to_csv(cache_path, index=False)
    return df


def ladder_state_from_journal(journal_path: str | Path, symbol: str) -> dict[str, object]:
    entries = [
        entry
        for entry in load_journal(journal_path)
        if entry.symbol == symbol
        and bool(getattr(entry, "is_root_signal", True))
        and entry.status == "closed"
        and bool(entry.outcome)
    ]
    entries.sort(
        key=lambda entry: (
            _parse_event_timestamp(entry.outcome_timestamp or entry.signal_timestamp or entry.dispatched_at_utc),
            entry.setup_id,
        )
    )
    step_index = 0
    last_outcome = "none"
    last_setup_id = None
    for entry in entries:
        last_setup_id = entry.setup_id
        if entry.outcome == "tp_hit":
            step_index = 0
            last_outcome = "tp_hit"
        else:
            step_index = min(step_index + 1, len(LADDER_SEQUENCE) - 1)
            last_outcome = entry.outcome
    return {
        "step_index": step_index,
        "risk_pct": LADDER_SEQUENCE[step_index],
        "last_outcome": last_outcome,
        "last_setup_id": last_setup_id,
    }


def _quality(signal: dict[str, float], row: pd.Series) -> tuple[int, str]:
    score = 60 if signal["scenario"] == "scenario2" else 55
    if float(row["close"]) > float(row["lips"]) > float(row["teeth"]) > float(row["jaw"]):
        score += 12
    if float(row["close"]) < float(row["lips"]) < float(row["teeth"]) < float(row["jaw"]):
        score += 12
    if float(signal.get("atr", 0.0)) > 0:
        score += 8
    if float(row["atr14"]) > 0 and abs(float(row["close"]) - float(row["open"])) >= float(row["atr14"]) * 0.25:
        score += 6
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


def _recent_noise_metrics(frame: pd.DataFrame, idx: int) -> dict[str, object]:
    start = max(0, idx - NOISE_LOOKBACK_BARS)
    window = frame.iloc[start:idx]
    if len(window) < 3:
        return {"high_noise": False, "direction_flips": 0, "compression_atr": None}
    close_deltas = window["close"].diff().dropna()
    signs = [1 if value > 0 else -1 if value < 0 else 0 for value in close_deltas]
    flips = sum(1 for left, right in zip(signs, signs[1:]) if left != 0 and right != 0 and left != right)
    atr_value = float(window["atr14"].iloc[-1]) if pd.notna(window["atr14"].iloc[-1]) else None
    compression_atr = None
    if atr_value and atr_value > 0:
        compression_atr = float((window["high"].max() - window["low"].min()) / atr_value)
    high_noise = flips >= 3 and (compression_atr is None or compression_atr <= 2.25)
    return {
        "high_noise": high_noise,
        "direction_flips": flips,
        "compression_atr": round(compression_atr, 4) if compression_atr is not None else None,
    }


def _followthrough_passes(side: str, confirmation_bar: pd.Series, reference_entry: float) -> bool:
    close = float(confirmation_bar["close"])
    open_price = float(confirmation_bar["open"])
    if side == "long":
        return close > open_price and close > reference_entry
    return close < open_price and close < reference_entry


def _upper_half_close(row: pd.Series) -> bool:
    if float(row["high"]) <= float(row["low"]):
        return False
    return float(row["close"]) >= (float(row["high"]) + float(row["low"])) / 2.0


def _lower_half_close(row: pd.Series) -> bool:
    if float(row["high"]) <= float(row["low"]):
        return False
    return float(row["close"]) <= (float(row["high"]) + float(row["low"])) / 2.0


def _detect_fwm_candidate(frame: pd.DataFrame, idx: int, bias: int, swing_lookback_bars: int) -> dict[str, float | str] | None:
    if idx < max(1, swing_lookback_bars - 1):
        return None
    row = frame.iloc[idx]
    previous = frame.iloc[idx - 1]
    if pd.isna(row["atr14"]) or pd.isna(row["jaw"]) or pd.isna(row["teeth"]) or pd.isna(row["lips"]):
        return None

    recent = frame.iloc[idx - swing_lookback_bars + 1 : idx + 1]
    mouth_low = float(min(row["jaw"], row["teeth"], row["lips"]))
    mouth_high = float(max(row["jaw"], row["teeth"], row["lips"]))
    buffer = float(row["atr14"]) * BUFFER_ATR_FRACTION

    if bias == 1:
        is_recent_swing_low = float(row["low"]) <= float(recent["low"].min())
        is_outside_mouth = float(row["low"]) < mouth_low
        line_flattening = float(row["lips"]) >= float(previous["lips"])
        if is_recent_swing_low and is_outside_mouth and _upper_half_close(row) and line_flattening:
            trigger = float(row["high"]) + buffer
            stop = float(row["low"]) - buffer
            if stop < trigger:
                return {
                    "side": "long",
                    "trigger_price": trigger,
                    "stop_price": stop,
                    "target_price": trigger + (trigger - stop),
                    "initial_risk": trigger - stop,
                    "scenario": "fwm",
                }

    if bias == -1:
        is_recent_swing_high = float(row["high"]) >= float(recent["high"].max())
        is_outside_mouth = float(row["high"]) > mouth_high
        line_flattening = float(row["lips"]) <= float(previous["lips"])
        if is_recent_swing_high and is_outside_mouth and _lower_half_close(row) and line_flattening:
            trigger = float(row["low"]) - buffer
            stop = float(row["high"]) + buffer
            if stop > trigger:
                return {
                    "side": "short",
                    "trigger_price": trigger,
                    "stop_price": stop,
                    "target_price": trigger - (stop - trigger),
                    "initial_risk": stop - trigger,
                    "scenario": "fwm",
                }

    return None


def _apply_stop_rules(
    *,
    side: str,
    entry_price: float,
    base_stop: float,
    atr_value: float | None,
    quality_layer: CwtQualityLayerConfig,
) -> tuple[float, float]:
    risk_distance = abs(entry_price - base_stop) * max(quality_layer.stop_scale, 0.0)
    if atr_value is not None and atr_value > 0 and quality_layer.min_atr_multiple > 0:
        risk_distance = max(risk_distance, quality_layer.min_atr_multiple * atr_value)
    if side == "long":
        stop_price = entry_price - risk_distance
        target_1 = entry_price + risk_distance
    else:
        stop_price = entry_price + risk_distance
        target_1 = entry_price - risk_distance
    return stop_price, target_1


def scan_symbol(
    symbol: str,
    minimum_timeframe: str,
    environment: str,
    token: str | None,
    price: str,
    ladder_info: dict[str, object],
    quality_layer: CwtQualityLayerConfig | None = None,
    fwm_config: CwtFwmConfig | None = None,
    regime_config: CwtRegimeConfig | None = None,
    catch_up_since: datetime | None = None,
) -> dict[str, object]:
    quality_layer = quality_layer or CwtQualityLayerConfig()
    fwm_config = fwm_config or CwtFwmConfig()
    regime_config = regime_config or CwtRegimeConfig()
    execution_granularity = TIMEFRAME_TO_OANDA[minimum_timeframe]
    execution = with_indicators(load_history(symbol, execution_granularity, environment, token, price))

    # --- Bias timeframe: configurable, defaults to H4 per research ---
    bias_tf_label = regime_config.bias_timeframe  # "H4", "1h", etc.
    bias_tf_oanda = BIAS_TIMEFRAME_TO_OANDA.get(bias_tf_label, "H4")
    bias_frame = with_indicators(load_history(symbol, bias_tf_oanda, environment, token, price))

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

    # --- ADX from bias timeframe merged into execution for regime filtering ---
    adx_lookup = bias_frame[["adx14"]].sort_index().copy()
    adx_lookup["ts_key"] = pd.Index(adx_lookup.index).asi8
    execution = execution.sort_index().copy()
    if "ts_key" not in execution.columns:
        execution["timestamp"] = execution.index
        execution["ts_key"] = pd.Index(execution.index).asi8
    execution = pd.merge_asof(
        execution,
        adx_lookup[["ts_key", "adx14"]],
        on="ts_key",
        direction="backward",
        suffixes=("", "_bias"),
    )
    execution = execution.set_index("timestamp").drop(columns=["ts_key"]) if "timestamp" in execution.columns else execution.drop(columns=["ts_key"], errors="ignore")
    # Prefer the bias-timeframe ADX for regime decisions
    if "adx14_bias" in execution.columns:
        execution["adx14"] = execution["adx14_bias"].fillna(execution.get("adx14", 0))
        execution = execution.drop(columns=["adx14_bias"], errors="ignore")

    if len(execution) < 130:
        return {
            "symbol": symbol,
            "timeframe": minimum_timeframe,
            "asset_class": asset_class_for(symbol),
            "alert": None,
            "latest_signal": None,
            "recent_signals": [],
            "reason": "insufficient_history",
        }
    def signal_for_entry_index(entry_idx: int) -> tuple[dict[str, object] | None, str]:
        if entry_idx <= 0 or entry_idx >= len(execution):
            return None, "missing_entry_bar"
        setup_idx = entry_idx - 1
        row = execution.iloc[setup_idx]
        entry_bar = execution.iloc[entry_idx]
        bias = int(row["bias_signal"])
        active_blue = float(row["active_blue"]) if pd.notna(row["active_blue"]) else None
        active_red = float(row["active_red"]) if pd.notna(row["active_red"]) else None

        # --- Regime filter (research-backed) ---
        setup_bar_adx = float(row["adx14"]) if pd.notna(row.get("adx14")) else None
        setup_bar_sleeping = bool(row["alligator_sleeping"]) if "alligator_sleeping" in row.index else False
        setup_bar_mouth_width = float(row["mouth_width"]) if "mouth_width" in row.index else None
        is_awakening = alligator_awakening(setup_idx, execution) if regime_config.enabled else False

        if regime_config.enabled:
            if setup_bar_adx is not None and setup_bar_adx < regime_config.min_adx:
                return None, "regime_ranging_low_adx"
            if setup_bar_sleeping:
                return None, "alligator_sleeping"

        if symbol in fwm_config.enabled_symbols:
            for candidate_idx in range(max(1, entry_idx - fwm_config.order_valid_bars), entry_idx):
                candidate_row = execution.iloc[candidate_idx]
                candidate_bias = int(candidate_row["bias_signal"])
                candidate = _detect_fwm_candidate(execution, candidate_idx, candidate_bias, fwm_config.swing_lookback_bars)
                if candidate is None:
                    continue
                if entry_idx < candidate_idx + 1 or entry_idx > candidate_idx + fwm_config.order_valid_bars:
                    continue

                if str(candidate["side"]) == "long" and float(entry_bar["high"]) >= float(candidate["trigger_price"]):
                    entry_price = max(float(entry_bar["open"]), float(candidate["trigger_price"]))
                    stop_price = float(candidate["stop_price"])
                    if stop_price >= entry_price:
                        return None, "invalid_fwm_stop"
                    target_1 = float(candidate["target_price"])
                    quality_score = 80
                    quality_grade = "A" if quality_score >= 85 else "B"
                    stop_distance_pct = abs(stop_price - entry_price) / abs(entry_price) * 100.0 if entry_price else None
                    risk_pct = float(ladder_info["risk_pct"])
                    previous_outcome = str(ladder_info.get("last_outcome", "none"))
                    entry_time = execution.index[entry_idx]
                    setup_id = f"cwt-{symbol.lower()}-{minimum_timeframe}-fwm-long-{entry_time.strftime('%Y%m%d%H%M')}"
                    scenario_label = "First Wise Man"
                    reason_summary = (
                        "First Wise Man entry-lane long under H1 bias. "
                        "The signal bar made a local swing low outside the Alligator cluster, closed in its upper half, "
                        "and the trigger bar broke the signal high."
                    )
                    risk_display = f"{risk_pct:.2f}% (step {int(ladder_info['step_index']) + 1}/4)"
                    if previous_outcome != "none":
                        risk_display += f" after {previous_outcome.replace('_', ' ')}"
                    return {
                        "strategy_id": "strategy_four",
                        "symbol": symbol,
                        "asset_class": asset_class_for(symbol),
                        "timeframe": minimum_timeframe,
                        "signal_type": "long",
                        "timestamp": entry_time.isoformat(),
                        "setup_bar_time": execution.index[candidate_idx].isoformat(),
                        "setup_id": setup_id,
                        "reason_summary": reason_summary,
                        "quality_score": quality_score,
                        "quality_grade": quality_grade,
                        "risk_reward": 1.0,
                        "entry": round(entry_price, 6),
                        "stop_loss": round(stop_price, 6),
                        "target_1": round(target_1, 6),
                        "scenario": "fwm",
                        "scenario_label": scenario_label,
                        "bias_timeframe": "1h",
                        "execution_granularity": execution_granularity,
                        "risk_fraction": risk_pct / 100.0,
                        "risk_label": "Recommended Risk Step",
                        "risk_display": risk_display,
                        "ladder_sequence_pct": LADDER_SEQUENCE,
                        "ladder_step_index": int(ladder_info["step_index"]),
                        "previous_outcome": previous_outcome,
                        "previous_setup_id": ladder_info.get("last_setup_id"),
                        "stop_distance_pct": round(stop_distance_pct, 2) if stop_distance_pct is not None else None,
                        "event_type": "entry",
                        "signal_source": "fwm_selective",
                    }, "signal"

                if str(candidate["side"]) == "short" and float(entry_bar["low"]) <= float(candidate["trigger_price"]):
                    entry_price = min(float(entry_bar["open"]), float(candidate["trigger_price"]))
                    stop_price = float(candidate["stop_price"])
                    if stop_price <= entry_price:
                        return None, "invalid_fwm_stop"
                    target_1 = float(candidate["target_price"])
                    quality_score = 80
                    quality_grade = "A" if quality_score >= 85 else "B"
                    stop_distance_pct = abs(stop_price - entry_price) / abs(entry_price) * 100.0 if entry_price else None
                    risk_pct = float(ladder_info["risk_pct"])
                    previous_outcome = str(ladder_info.get("last_outcome", "none"))
                    entry_time = execution.index[entry_idx]
                    setup_id = f"cwt-{symbol.lower()}-{minimum_timeframe}-fwm-short-{entry_time.strftime('%Y%m%d%H%M')}"
                    scenario_label = "First Wise Man"
                    reason_summary = (
                        "First Wise Man entry-lane short under H1 bias. "
                        "The signal bar made a local swing high outside the Alligator cluster, closed in its lower half, "
                        "and the trigger bar broke the signal low."
                    )
                    risk_display = f"{risk_pct:.2f}% (step {int(ladder_info['step_index']) + 1}/4)"
                    if previous_outcome != "none":
                        risk_display += f" after {previous_outcome.replace('_', ' ')}"
                    return {
                        "strategy_id": "strategy_four",
                        "symbol": symbol,
                        "asset_class": asset_class_for(symbol),
                        "timeframe": minimum_timeframe,
                        "signal_type": "short",
                        "timestamp": entry_time.isoformat(),
                        "setup_bar_time": execution.index[candidate_idx].isoformat(),
                        "setup_id": setup_id,
                        "reason_summary": reason_summary,
                        "quality_score": quality_score,
                        "quality_grade": quality_grade,
                        "risk_reward": 1.0,
                        "entry": round(entry_price, 6),
                        "stop_loss": round(stop_price, 6),
                        "target_1": round(target_1, 6),
                        "scenario": "fwm",
                        "scenario_label": scenario_label,
                        "bias_timeframe": "1h",
                        "execution_granularity": execution_granularity,
                        "risk_fraction": risk_pct / 100.0,
                        "risk_label": "Recommended Risk Step",
                        "risk_display": risk_display,
                        "ladder_sequence_pct": LADDER_SEQUENCE,
                        "ladder_step_index": int(ladder_info["step_index"]),
                        "previous_outcome": previous_outcome,
                        "previous_setup_id": ladder_info.get("last_setup_id"),
                        "stop_distance_pct": round(stop_distance_pct, 2) if stop_distance_pct is not None else None,
                        "event_type": "entry",
                        "signal_source": "fwm_selective",
                    }, "signal"

        long_signal = scenario_one_long(execution, setup_idx, bias)
        short_signal = scenario_one_short(execution, setup_idx, bias)
        if long_signal is None and short_signal is None:
            long_signal = scenario_two_long(execution, setup_idx, bias, active_red)
            short_signal = scenario_two_short(execution, setup_idx, bias, active_blue)

        signal = long_signal if long_signal is not None else short_signal
        if signal is None:
            return None, "no_signal"

        next_bar = entry_bar
        setup_bar_time = execution.index[setup_idx]
        entry_time = execution.index[entry_idx]
        reference_entry = float(next_bar["open"])
        buffer = float(signal["atr"]) * BUFFER_ATR_FRACTION
        if signal is long_signal:
            side = "long"
            base_stop = float(signal["stop_anchor"] - buffer)
            if base_stop >= reference_entry:
                return None, "invalid_stop"
        else:
            side = "short"
            base_stop = float(signal["stop_anchor"] + buffer)
            if base_stop <= reference_entry:
                return None, "invalid_stop"

        if quality_layer.require_followthrough:
            if not _followthrough_passes(side, next_bar, reference_entry):
                return None, "missing_followthrough"
            entry_price = float(next_bar["close"])
            quality_notes = ["followthrough_confirmed"]
        else:
            entry_price = reference_entry
            quality_notes = []

        noise_metrics = _recent_noise_metrics(execution, entry_idx)
        if quality_layer.skip_high_noise and bool(noise_metrics["high_noise"]):
            return None, "high_noise_session"

        atr_value = float(next_bar["atr14"]) if pd.notna(next_bar["atr14"]) else float(signal.get("atr") or 0.0) or None
        stop_price, target_1 = _apply_stop_rules(
            side=side,
            entry_price=entry_price,
            base_stop=base_stop,
            atr_value=atr_value,
            quality_layer=quality_layer,
        )
        if side == "long" and stop_price >= entry_price:
            return None, "invalid_stop"
        if side == "short" and stop_price <= entry_price:
            return None, "invalid_stop"

        quality_score, quality_grade = _quality(signal, row)

        # --- Regime quality boost: strong ADX + wide mouth + awakening = A-grade ---
        if regime_config.enabled and setup_bar_adx is not None:
            if setup_bar_adx >= regime_config.strong_adx:
                quality_score = min(quality_score + 8, 95)
            if is_awakening:
                quality_score = min(quality_score + 5, 95)
            if setup_bar_mouth_width is not None and setup_bar_mouth_width > 0.10:
                quality_score = min(quality_score + 3, 95)
            if quality_score >= 85:
                quality_grade = "A"
            elif quality_score >= 75:
                quality_grade = "B"
            elif quality_score >= 65:
                quality_grade = "C"
            else:
                quality_grade = "D"

        stop_distance_pct = abs(stop_price - entry_price) / abs(entry_price) * 100.0 if entry_price else None
        risk_pct = float(ladder_info["risk_pct"])
        previous_outcome = str(ladder_info.get("last_outcome", "none"))
        setup_id = f"cwt-{symbol.lower()}-{minimum_timeframe}-{signal['scenario']}-{side}-{entry_time.strftime('%Y%m%d%H%M')}"
        scenario_label = signal["scenario"].replace("scenario", "Scenario ").title()

        # Build regime context string for the reason summary
        regime_context = ""
        if regime_config.enabled:
            adx_str = f"ADX {setup_bar_adx:.1f}" if setup_bar_adx is not None else "ADX n/a"
            regime_parts = [adx_str]
            if is_awakening:
                regime_parts.append("Alligator awakening")
            if setup_bar_mouth_width is not None:
                regime_parts.append(f"mouth {setup_bar_mouth_width:.3f}")
            regime_context = f" [{', '.join(regime_parts)}]"

        reason_summary = (
            f"{scenario_label} continuation in line with {bias_tf_label} bias.{regime_context} "
            f"Entry uses the {'confirmation bar close' if quality_layer.require_followthrough else 'next bar open after the completed setup candle'}, "
            f"stop sits beyond the structural invalidation, and target is fixed at 1R."
        )
        risk_display = f"{risk_pct:.2f}% (step {int(ladder_info['step_index']) + 1}/4)"
        if previous_outcome != "none":
            risk_display += f" after {previous_outcome.replace('_', ' ')}"

        return {
            "strategy_id": "strategy_four",
            "symbol": symbol,
            "asset_class": asset_class_for(symbol),
            "timeframe": minimum_timeframe,
            "signal_type": side,
            "timestamp": entry_time.isoformat(),
            "setup_bar_time": setup_bar_time.isoformat(),
            "setup_id": setup_id,
            "reason_summary": reason_summary,
            "quality_score": quality_score,
            "quality_grade": quality_grade,
            "risk_reward": 1.0,
            "entry": round(entry_price, 6),
            "stop_loss": round(stop_price, 6),
            "target_1": round(target_1, 6),
            "scenario": signal["scenario"],
            "scenario_label": scenario_label,
            "bias_timeframe": bias_tf_label,
            "execution_granularity": execution_granularity,
            "risk_fraction": risk_pct / 100.0,
            "risk_label": "Recommended Risk Step",
            "risk_display": risk_display,
            "ladder_sequence_pct": LADDER_SEQUENCE,
            "ladder_step_index": int(ladder_info["step_index"]),
            "previous_outcome": previous_outcome,
            "previous_setup_id": ladder_info.get("last_setup_id"),
            "stop_distance_pct": round(stop_distance_pct, 2) if stop_distance_pct is not None else None,
            "event_type": "entry",
            "quality_layer": {
                "require_followthrough": quality_layer.require_followthrough,
                "skip_high_noise": quality_layer.skip_high_noise,
                "stop_scale": quality_layer.stop_scale,
                "min_atr_multiple": quality_layer.min_atr_multiple,
            },
            "quality_filter_notes": quality_notes,
            "entry_basis": "confirmation_close" if quality_layer.require_followthrough else "next_bar_open",
            "direction_flips_pre_entry": noise_metrics["direction_flips"],
            "compression_atr_pre_entry": noise_metrics["compression_atr"],
            "high_noise_session": bool(noise_metrics["high_noise"]),
            # --- Regime metrics ---
            "adx": round(setup_bar_adx, 2) if setup_bar_adx is not None else None,
            "alligator_sleeping": setup_bar_sleeping,
            "alligator_mouth_width": round(setup_bar_mouth_width, 4) if setup_bar_mouth_width is not None else None,
            "alligator_awakening": is_awakening,
            "regime_filtered": regime_config.enabled,
            "regime_strong_trend": setup_bar_adx is not None and setup_bar_adx >= regime_config.strong_adx,
        }, "signal"

    latest_signal, latest_reason = signal_for_entry_index(len(execution) - 1)
    recent_signals: list[dict[str, object]] = []
    if catch_up_since is not None:
        catch_up_since_ts = pd.Timestamp(catch_up_since)
        if catch_up_since_ts.tzinfo is None:
            catch_up_since_ts = catch_up_since_ts.tz_localize("UTC")
        else:
            catch_up_since_ts = catch_up_since_ts.tz_convert("UTC")
        start_idx = max(1, int(execution.index.searchsorted(catch_up_since_ts)) - 2)
        seen_setup_ids: set[str] = set()
        if latest_signal is not None:
            seen_setup_ids.add(str(latest_signal["setup_id"]))
        for entry_idx in range(start_idx, len(execution)):
            signal_payload, reason = signal_for_entry_index(entry_idx)
            if signal_payload is None:
                continue
            entry_timestamp = pd.Timestamp(signal_payload["timestamp"])
            if entry_timestamp < catch_up_since_ts:
                continue
            setup_id = str(signal_payload["setup_id"])
            if setup_id in seen_setup_ids:
                continue
            recent_signals.append(signal_payload)
            seen_setup_ids.add(setup_id)

    if latest_signal is None:
        return {
            "symbol": symbol,
            "timeframe": minimum_timeframe,
            "asset_class": asset_class_for(symbol),
            "alert": None,
            "latest_signal": None,
            "recent_signals": recent_signals,
            "reason": latest_reason,
        }
    return {
        "symbol": symbol,
        "timeframe": minimum_timeframe,
        "asset_class": asset_class_for(symbol),
        "alert": (
            f"{symbol} {minimum_timeframe} {str(latest_signal['signal_type']).upper()} "
            f"{latest_signal['scenario']} | risk {latest_signal['risk_display']}"
        ),
        "latest_signal": latest_signal,
        "recent_signals": recent_signals,
        "reason": "signal",
    }


def save_scan_outputs(output_dir: str | Path, rows: list[dict[str, object]], signals: list[dict[str, object]], state: dict[str, object]) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scan_results.json").write_text(json.dumps(rows, indent=2))
    (out / "alerts.txt").write_text("\n".join(row["alert"] for row in rows if row.get("alert")))
    (out / "signals.json").write_text(json.dumps(signals, indent=2))
    save_state(out, state)


def run_live_cycle(
    symbols: list[str],
    environment: str,
    token: str | None,
    price: str,
    output_dir: str | Path,
    quality_layer: CwtQualityLayerConfig | None = None,
    fwm_config: CwtFwmConfig | None = None,
    regime_config: CwtRegimeConfig | None = None,
    catch_up_since: datetime | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    state = load_state(output_dir)
    journal_path = Path(output_dir) / "signal_journal.json"
    rows: list[dict[str, object]] = []
    signals: list[dict[str, object]] = []
    state_symbols: dict[str, object] = {}
    for symbol in symbols:
        minimum_timeframe = minimum_timeframe_for(symbol)
        ladder_info = ladder_state_from_journal(journal_path, symbol) if journal_path.exists() else {
            "step_index": 0,
            "risk_pct": LADDER_SEQUENCE[0],
            "last_outcome": "none",
            "last_setup_id": None,
        }
        state_symbols[symbol] = ladder_info
        row = scan_symbol(
            symbol,
            minimum_timeframe,
            environment,
            token,
            price,
            ladder_info,
            quality_layer=quality_layer,
            fwm_config=fwm_config,
            regime_config=regime_config,
            catch_up_since=catch_up_since,
        )
        rows.append(row)
        if row.get("latest_signal"):
            signals.append(row["latest_signal"])
        for recovered in row.get("recent_signals", []):
            signals.append(recovered)
    state["symbols"] = state_symbols
    return rows, signals, state
