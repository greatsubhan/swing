"""CWT stop-loss forensics and intervention analysis.

This script builds a decision-ready report package for `strategy_four` by:

- normalizing closed trade history from the operational journal and replay files
- splitting each source into raw and root-only lenses
- loading cached market bars to measure what happened after each SL hit
- testing a fixed matrix of alternative stop/entry/filter interventions
- exporting a Markdown report, row-level CSV, and summary JSON
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.cwt_forex_backtest import with_indicators

JOURNAL_PATH = ROOT / "platform_output" / "strategy_four" / "signal_journal.json"
REPLAY_PATH = ROOT / "reports" / "cwt_since_inception" / "replay_signals.csv"
OP_SUMMARY_PATH = ROOT / "reports" / "cwt_operational" / "CWT_OPERATIONAL_SUMMARY.json"
FIRST_SIGNAL_SUMMARY_PATH = ROOT / "reports" / "cwt_operational" / "CWT_FIRST_SIGNAL_ONLY_SUMMARY.json"
REPLAY_SUMMARY_PATH = ROOT / "reports" / "cwt_since_inception" / "replay_summary.json"

OUTPUT_DIR = ROOT / "reports" / "cwt_sl_forensics"
REPORT_PATH = OUTPUT_DIR / "CWT_SL_FORENSICS_REPORT.md"
CSV_PATH = OUTPUT_DIR / "cwt_sl_forensics_rows.csv"
JSON_PATH = OUTPUT_DIR / "cwt_sl_forensics_summary.json"

LADDER_SEQUENCE = [0.07, 0.20, 0.45, 1.00]
REPETITION_WINDOW_BARS = 12
TIMEFRAME_MINUTES = {"5m": 5, "15m": 15}
TIMEFRAME_TO_LIVE_FILE = {"5m": "M5_live.csv", "15m": "M15_live.csv"}
TIMEFRAME_TO_ARCHIVE_FILE = {"5m": "M5_2025-01-01_2026-04-01.csv", "15m": "M15_2025-01-01_2026-04-01.csv"}
FOLLOWTHROUGH_WINDOW_BARS = 1
NOISE_LOOKBACK_BARS = 6
POST_STOP_WINDOW_BARS = 96


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    label: str
    stop_scale: float = 1.0
    use_symbol_point_floor: bool = False
    min_atr_multiple: float | None = None
    delay_bars: int = 0
    require_followthrough: bool = False
    skip_small_stop_atr: float | None = None
    skip_duplicate_cluster: bool = False
    skip_high_noise: bool = False


VARIANTS: list[VariantSpec] = [
    VariantSpec("baseline", "Baseline"),
    VariantSpec("fixed_widen_10", "Widen stop +10%", stop_scale=1.10),
    VariantSpec("fixed_widen_20", "Widen stop +20%", stop_scale=1.20),
    VariantSpec("fixed_widen_30", "Widen stop +30%", stop_scale=1.30),
    VariantSpec("symbol_point_floor", "Apply symbol point floor", use_symbol_point_floor=True),
    VariantSpec("atr_floor_025", "Apply 0.25 ATR floor", min_atr_multiple=0.25),
    VariantSpec("atr_floor_035", "Apply 0.35 ATR floor", min_atr_multiple=0.35),
    VariantSpec("atr_floor_050", "Apply 0.50 ATR floor", min_atr_multiple=0.50),
    VariantSpec("delay_1bar", "Delay entry by 1 bar", delay_bars=1),
    VariantSpec("followthrough_1bar", "Require one-bar follow-through", require_followthrough=True),
    VariantSpec("skip_small_stop_atr", "Skip too-small stops", skip_small_stop_atr=0.20),
    VariantSpec("skip_duplicate_cluster", "Skip duplicate clusters", skip_duplicate_cluster=True),
    VariantSpec("skip_high_noise", "Skip high-noise sessions", skip_high_noise=True),
]


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cooldown_window(entry: dict[str, Any]) -> timedelta:
    timeframe = str(entry.get("timeframe", "5m")).lower()
    minutes = TIMEFRAME_MINUTES.get(timeframe, 5)
    return timedelta(minutes=minutes * REPETITION_WINDOW_BARS)


def _load_operational_entries() -> list[dict[str, Any]]:
    payload = _load_json(JOURNAL_PATH) or []
    entries: list[dict[str, Any]] = []
    for row in payload:
        raw_signal = row.get("raw_signal") or {}
        entries.append(
            {
                "source_section": "operational_journal",
                "setup_id": str(row.get("setup_id")),
                "symbol": str(row.get("symbol")),
                "asset_class": str(row.get("asset_class", "")),
                "timeframe": str(row.get("timeframe")),
                "side": str(row.get("side")),
                "signal_timestamp": str(row.get("signal_timestamp")),
                "setup_bar_time": str(raw_signal.get("setup_bar_time") or row.get("signal_timestamp")),
                "scenario": str(raw_signal.get("scenario", "")) or None,
                "entry": float(row.get("entry") or 0.0),
                "stop_loss": float(row.get("stop_loss") or 0.0),
                "target_1": float(row.get("target_1") or 0.0),
                "status": str(row.get("status")),
                "outcome": str(row.get("outcome", "")) or None,
                "outcome_timestamp": str(row.get("outcome_timestamp", "")) or None,
                "exit_price": _to_float(row.get("exit_price")),
                "bars_checked": int(row.get("bars_checked") or 0),
                "quality_score": _to_float(row.get("quality_score")),
                "quality_grade": str(row.get("quality_grade", "")) or None,
                "risk_reward": _to_float(row.get("risk_reward")) or 1.0,
                "risk_fraction": _to_float(raw_signal.get("risk_fraction")),
                "is_root_signal": bool(row.get("is_root_signal", True)),
                "raw_signal": raw_signal,
            }
        )
    return entries


def _load_replay_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with REPLAY_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            entries.append(
                {
                    "source_section": "since_inception_replay",
                    "setup_id": str(row.get("setup_id")),
                    "symbol": str(row.get("symbol")),
                    "asset_class": str(row.get("asset_class", "")),
                    "timeframe": str(row.get("timeframe")),
                    "side": str(row.get("signal_type")),
                    "signal_timestamp": str(row.get("timestamp")),
                    "setup_bar_time": str(row.get("setup_bar_time") or row.get("timestamp")),
                    "scenario": str(row.get("scenario", "")) or None,
                    "entry": float(row.get("entry") or 0.0),
                    "stop_loss": float(row.get("stop_loss") or 0.0),
                    "target_1": float(row.get("target_1") or 0.0),
                    "status": str(row.get("status")),
                    "outcome": str(row.get("outcome", "")) or None,
                    "outcome_timestamp": str(row.get("outcome_timestamp", "")) or None,
                    "exit_price": _to_float(row.get("exit_price")),
                    "bars_checked": int(row.get("bars_checked") or 0),
                    "quality_score": None,
                    "quality_grade": None,
                    "risk_reward": _to_float(row.get("realized_r")) if row.get("outcome") == "tp_hit" else 1.0,
                    "risk_fraction": None,
                    "is_root_signal": True,
                    "raw_signal": {},
                }
            )
    return entries


def _select_first_signals(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    selected: list[dict[str, Any]] = []
    suppressed_reasons: dict[str, str] = {}
    last_selected_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    ordered = sorted(
        [entry for entry in entries if bool(entry.get("is_root_signal", True))],
        key=lambda entry: (_parse_timestamp(entry.get("signal_timestamp")), str(entry.get("setup_id", ""))),
    )
    for entry in ordered:
        key = (str(entry.get("symbol")), str(entry.get("timeframe")), str(entry.get("side")))
        previous = last_selected_by_key.get(key)
        if previous is not None:
            previous_signal_time = _parse_timestamp(previous.get("signal_timestamp"))
            current_signal_time = _parse_timestamp(entry.get("signal_timestamp"))
            time_gap = current_signal_time - previous_signal_time
            if previous.get("status") != "closed":
                suppressed_reasons[str(entry.get("setup_id"))] = "same_direction_active_trade"
                continue
            if previous.get("outcome") == "tp_hit" and time_gap <= _cooldown_window(entry):
                suppressed_reasons[str(entry.get("setup_id"))] = "same_direction_post_tp_cluster"
                continue
        selected.append(entry)
        last_selected_by_key[key] = entry
    return selected, suppressed_reasons


def _reconstruct_ladder(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[str(entry["symbol"])].append(entry)

    ladder_by_setup: dict[str, dict[str, Any]] = {}
    for symbol, symbol_entries in grouped.items():
        step_index = 0
        previous_outcome = "none"
        previous_setup_id = None
        for entry in sorted(symbol_entries, key=lambda row: (_parse_timestamp(row["signal_timestamp"]), row["setup_id"])):
            ladder_by_setup[entry["setup_id"]] = {
                "ladder_step_at_entry": step_index,
                "ladder_risk_pct_at_entry": LADDER_SEQUENCE[step_index],
                "ladder_previous_outcome": previous_outcome,
                "ladder_previous_setup_id": previous_setup_id,
            }
            if entry.get("status") == "closed":
                if entry.get("outcome") == "tp_hit":
                    step_index = 0
                    previous_outcome = "tp_hit"
                elif entry.get("outcome") == "sl_hit":
                    step_index = min(step_index + 1, len(LADDER_SEQUENCE) - 1)
                    previous_outcome = "sl_hit"
                else:
                    previous_outcome = str(entry.get("outcome") or "other")
                previous_setup_id = entry["setup_id"]
    return ladder_by_setup


def _load_bar_history(symbol: str, timeframe: str, cache: dict[tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
    key = (symbol, timeframe)
    if key in cache:
        return cache[key]

    live_path = ROOT / "research_data" / "cwt_live" / symbol / TIMEFRAME_TO_LIVE_FILE[timeframe]
    archive_path = ROOT / "research_data" / "cwt_oanda" / symbol / TIMEFRAME_TO_ARCHIVE_FILE[timeframe]
    parts: list[pd.DataFrame] = []
    for path in [archive_path, live_path]:
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        parts.append(df)

    if not parts:
        raise FileNotFoundError(f"No cached bars found for {symbol} {timeframe}")

    combined = pd.concat(parts, ignore_index=True).sort_values("timestamp")
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.set_index("timestamp")
    enriched = with_indicators(combined)
    cache[key] = enriched
    return enriched


def _entry_index(frame: pd.DataFrame, timestamp: str) -> int | None:
    ts = _parse_timestamp(timestamp)
    if frame.empty:
        return None
    position = frame.index.searchsorted(ts, side="left")
    if position >= len(frame):
        return None
    return int(position)


def _stop_distance_points(entry: dict[str, Any]) -> float:
    return abs(float(entry["entry"]) - float(entry["stop_loss"]))


def _recent_noise_metrics(frame: pd.DataFrame, idx: int) -> dict[str, Any]:
    start = max(0, idx - NOISE_LOOKBACK_BARS)
    window = frame.iloc[start:idx]
    if len(window) < 3:
        return {"high_noise": False, "direction_flips": 0, "wickiness": None, "compression_atr": None}

    close_deltas = window["close"].diff().dropna()
    signs = [1 if value > 0 else -1 if value < 0 else 0 for value in close_deltas]
    flips = sum(1 for left, right in zip(signs, signs[1:]) if left != 0 and right != 0 and left != right)
    atr_value = float(window["atr14"].iloc[-1]) if pd.notna(window["atr14"].iloc[-1]) else math.nan
    bar_ranges = (window["high"] - window["low"]).astype(float)
    bodies = (window["close"] - window["open"]).abs().astype(float)
    wickiness = float((bar_ranges - bodies).clip(lower=0.0).mean()) if len(window) else math.nan
    compression_atr = float((window["high"].max() - window["low"].min()) / atr_value) if atr_value and not math.isnan(atr_value) else math.nan
    high_noise = flips >= 3 and (math.isnan(compression_atr) or compression_atr <= 2.25)
    return {
        "high_noise": high_noise,
        "direction_flips": flips,
        "wickiness": wickiness if not math.isnan(wickiness) else None,
        "compression_atr": compression_atr if not math.isnan(compression_atr) else None,
    }


def _followthrough_passes(side: str, bar: pd.Series, entry_price: float) -> bool:
    close = float(bar["close"])
    open_price = float(bar["open"])
    if side == "long":
        return close > open_price and close > entry_price
    return close < open_price and close < entry_price


def _simulate_outcome(
    side: str,
    frame: pd.DataFrame,
    entry_idx: int,
    stop_price: float,
    target_price: float,
) -> tuple[str | None, int | None, str | None, float | None]:
    bars_checked = 0
    for idx in range(entry_idx + 1, len(frame)):
        row = frame.iloc[idx]
        bars_checked += 1
        high = float(row["high"])
        low = float(row["low"])
        timestamp = frame.index[idx].isoformat()
        if side == "long":
            if low <= stop_price and high >= target_price:
                return "sl_hit", bars_checked, timestamp, stop_price
            if low <= stop_price:
                return "sl_hit", bars_checked, timestamp, stop_price
            if high >= target_price:
                return "tp_hit", bars_checked, timestamp, target_price
        else:
            if high >= stop_price and low <= target_price:
                return "sl_hit", bars_checked, timestamp, stop_price
            if high >= stop_price:
                return "sl_hit", bars_checked, timestamp, stop_price
            if low <= target_price:
                return "tp_hit", bars_checked, timestamp, target_price
    return None, None, None, None


def _simulate_variant(
    trade: dict[str, Any],
    frame: pd.DataFrame,
    variant: VariantSpec,
    symbol_point_floors: dict[str, float],
) -> dict[str, Any]:
    entry_idx = trade.get("_entry_index")
    if entry_idx is None:
        return {"status": "skipped", "skip_reason": "missing_entry_bar"}
    if variant.skip_duplicate_cluster and trade.get("duplicate_cluster_exposure"):
        return {"status": "skipped", "skip_reason": "duplicate_cluster"}
    if variant.skip_high_noise and trade.get("high_noise_session"):
        return {"status": "skipped", "skip_reason": "high_noise_session"}

    delayed_idx = int(entry_idx) + int(variant.delay_bars)
    if delayed_idx >= len(frame):
        return {"status": "skipped", "skip_reason": "missing_delayed_entry"}

    delayed_row = frame.iloc[delayed_idx]
    entry_price = float(delayed_row["open"])
    target_price = float(trade["target_1"])
    side = str(trade["side"])
    if (side == "long" and entry_price >= target_price) or (side == "short" and entry_price <= target_price):
        return {"status": "skipped", "skip_reason": "target_already_passed"}
    if variant.require_followthrough and not _followthrough_passes(side, delayed_row, entry_price):
        return {"status": "skipped", "skip_reason": "missing_followthrough"}

    base_stop = float(trade["stop_loss"])
    base_risk = abs(entry_price - base_stop)
    atr_value = float(delayed_row["atr14"]) if pd.notna(delayed_row["atr14"]) else math.nan
    risk_distance = base_risk * float(variant.stop_scale)
    if variant.use_symbol_point_floor:
        risk_distance = max(risk_distance, float(symbol_point_floors.get(str(trade["symbol"]), base_risk)))
    if variant.min_atr_multiple is not None and not math.isnan(atr_value):
        risk_distance = max(risk_distance, float(variant.min_atr_multiple) * atr_value)
    if variant.skip_small_stop_atr is not None and not math.isnan(atr_value):
        if atr_value <= 0 or (risk_distance / atr_value) < float(variant.skip_small_stop_atr):
            return {"status": "skipped", "skip_reason": "stop_below_atr_threshold"}

    stop_price = entry_price - risk_distance if side == "long" else entry_price + risk_distance
    outcome, bars_checked, outcome_timestamp, exit_price = _simulate_outcome(
        side=side,
        frame=frame,
        entry_idx=delayed_idx,
        stop_price=stop_price,
        target_price=target_price,
    )
    if outcome is None:
        return {
            "status": "open",
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "risk_distance": risk_distance,
            "bars_checked": None,
            "realized_r": 0.0,
        }

    reward_distance = abs(target_price - entry_price)
    realized_r = -1.0 if outcome == "sl_hit" else (reward_distance / risk_distance if risk_distance else 0.0)
    return {
        "status": "closed",
        "outcome": outcome,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "risk_distance": risk_distance,
        "bars_checked": bars_checked,
        "outcome_timestamp": outcome_timestamp,
        "exit_price": exit_price,
        "realized_r": realized_r,
    }


def _post_stop_metrics(trade: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    stop_timestamp = trade.get("outcome_timestamp")
    if not stop_timestamp:
        return {
            "mfe_after_sl_points": None,
            "mfe_after_sl_r": None,
            "mae_after_sl_points": None,
            "mae_after_sl_r": None,
            "bars_to_recovery": None,
            "bars_to_tp_if_survived": None,
            "would_reach_tp_if_survived": False,
            "stop_overshoot_points": None,
            "stop_overshoot_r": None,
        }

    stop_idx = _entry_index(frame, stop_timestamp)
    if stop_idx is None:
        return {
            "mfe_after_sl_points": None,
            "mfe_after_sl_r": None,
            "mae_after_sl_points": None,
            "mae_after_sl_r": None,
            "bars_to_recovery": None,
            "bars_to_tp_if_survived": None,
            "would_reach_tp_if_survived": False,
            "stop_overshoot_points": None,
            "stop_overshoot_r": None,
        }

    future = frame.iloc[stop_idx + 1 : stop_idx + 1 + POST_STOP_WINDOW_BARS]
    if future.empty:
        return {
            "mfe_after_sl_points": 0.0,
            "mfe_after_sl_r": 0.0,
            "mae_after_sl_points": 0.0,
            "mae_after_sl_r": 0.0,
            "bars_to_recovery": None,
            "bars_to_tp_if_survived": None,
            "would_reach_tp_if_survived": False,
            "stop_overshoot_points": 0.0,
            "stop_overshoot_r": 0.0,
        }

    entry = float(trade["entry"])
    stop = float(trade["stop_loss"])
    target = float(trade["target_1"])
    risk = abs(entry - stop) or math.nan
    side = str(trade["side"])
    stop_row = frame.iloc[stop_idx]
    if side == "long":
        stop_overshoot = max(0.0, stop - float(stop_row["low"]))
        mfe_points = float(future["high"].max()) - entry
        mae_points = entry - float(future["low"].min())
        recovery_hits = future["high"] >= entry
        target_hits = future["high"] >= target
    else:
        stop_overshoot = max(0.0, float(stop_row["high"]) - stop)
        mfe_points = entry - float(future["low"].min())
        mae_points = float(future["high"].max()) - entry
        recovery_hits = future["low"] <= entry
        target_hits = future["low"] <= target

    bars_to_recovery = None
    if recovery_hits.any():
        first = recovery_hits[recovery_hits].index[0]
        bars_to_recovery = int(future.index.get_loc(first) + 1)
    bars_to_tp = None
    if target_hits.any():
        first = target_hits[target_hits].index[0]
        bars_to_tp = int(future.index.get_loc(first) + 1)

    return {
        "mfe_after_sl_points": round(mfe_points, 6),
        "mfe_after_sl_r": round(mfe_points / risk, 4) if risk and not math.isnan(risk) else None,
        "mae_after_sl_points": round(mae_points, 6),
        "mae_after_sl_r": round(mae_points / risk, 4) if risk and not math.isnan(risk) else None,
        "bars_to_recovery": bars_to_recovery,
        "bars_to_tp_if_survived": bars_to_tp,
        "would_reach_tp_if_survived": bool(target_hits.any()),
        "stop_overshoot_points": round(stop_overshoot, 6),
        "stop_overshoot_r": round(stop_overshoot / risk, 4) if risk and not math.isnan(risk) else None,
    }


def _primary_reason(trade: dict[str, Any]) -> tuple[str, list[str]]:
    flags: list[str] = []
    if trade.get("duplicate_cluster_exposure"):
        flags.append("duplicate_cluster_exposure")
    if trade.get("high_noise_session"):
        flags.append("high_noise_session")

    if trade.get("variant_fixed_widen_10_outcome") == "tp_hit" and trade.get("would_reach_tp_if_survived"):
        return "stop_too_tight", flags
    if trade.get("variant_atr_floor_025_outcome") == "tp_hit" and trade.get("would_reach_tp_if_survived"):
        return "stop_too_tight", flags
    if trade.get("variant_delay_1bar_outcome") == "tp_hit":
        return "entry_too_early", flags
    if trade.get("duplicate_cluster_exposure"):
        return "duplicate_cluster_exposure", flags
    if trade.get("high_noise_session"):
        return "high_noise_session", flags
    if trade.get("would_reach_tp_if_survived") and (trade.get("stop_overshoot_r") or 0.0) > 0.25:
        return "structure_invalidated_before_reversal", flags
    if (trade.get("mfe_after_sl_r") or 0.0) > 0.5:
        return "insufficient_reward_after_survival", flags
    return "continuation_failed_cleanly", flags


def _recommended_action(trade: dict[str, Any]) -> str:
    ordered = [
        ("delay_1bar", "Delay entry by 1 bar"),
        ("followthrough_1bar", "Require one-bar follow-through"),
        ("skip_small_stop_atr", "Skip too-small stop"),
        ("skip_high_noise", "Skip high-noise session"),
        ("skip_duplicate_cluster", "Skip duplicate cluster"),
        ("atr_floor_025", "Apply 0.25 ATR floor"),
        ("fixed_widen_10", "Widen stop +10%"),
        ("symbol_point_floor", "Apply symbol point floor"),
    ]
    for variant_id, label in ordered:
        if trade.get(f"variant_{variant_id}_outcome") == "tp_hit":
            return label
        if trade.get(f"variant_{variant_id}_status") == "skipped":
            return label
    return "Keep baseline"


def _build_views() -> list[dict[str, Any]]:
    sources = {
        "operational_journal": _load_operational_entries(),
        "since_inception_replay": _load_replay_entries(),
    }
    all_rows: list[dict[str, Any]] = []
    for source_section, entries in sources.items():
        selected, suppressed = _select_first_signals(entries)
        for trade_lens, lens_entries in [("raw", entries), ("root_only", selected)]:
            ladder = _reconstruct_ladder(lens_entries)
            selected_ids = {entry["setup_id"] for entry in selected}
            for entry in lens_entries:
                row = dict(entry)
                row["trade_lens"] = trade_lens
                row["selected_in_root_only"] = entry["setup_id"] in selected_ids
                row["suppressed_reason"] = suppressed.get(entry["setup_id"])
                row["duplicate_cluster_exposure"] = row["suppressed_reason"] in {
                    "same_direction_active_trade",
                    "same_direction_post_tp_cluster",
                }
                row.update(ladder.get(entry["setup_id"], {}))
                all_rows.append(row)
    return all_rows


def _symbol_point_floors(entries: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for entry in entries:
        if entry.get("status") != "closed":
            continue
        grouped[str(entry["symbol"])].append(_stop_distance_points(entry))
    floors: dict[str, float] = {}
    for symbol, distances in grouped.items():
        floors[symbol] = float(pd.Series(distances).quantile(0.25))
    return floors


def _realized_r(outcome: str | None, risk_reward: float | None) -> float:
    if outcome == "tp_hit":
        return float(risk_reward or 1.0)
    if outcome == "sl_hit":
        return -1.0
    return 0.0


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value - peak)
    return max_drawdown


def _variant_metrics(entries: list[dict[str, Any]], variant_id: str, use_variant: bool) -> dict[str, Any]:
    ordered = sorted(entries, key=lambda row: (_parse_timestamp(row["signal_timestamp"]), row["setup_id"]))
    trades = 0
    wins = 0
    gross_profit_r = 0.0
    gross_loss_r = 0.0
    total_r = 0.0
    step_index = 0
    equity = 100_000.0
    equity_curve = [0.0]
    resets = 0
    advances = 0

    for entry in ordered:
        if use_variant:
            status = entry.get(f"variant_{variant_id}_status")
            outcome = entry.get(f"variant_{variant_id}_outcome")
            realized_r = float(entry.get(f"variant_{variant_id}_realized_r") or 0.0)
            bars = entry.get(f"variant_{variant_id}_bars_checked")
        else:
            status = "closed"
            outcome = entry.get("outcome")
            realized_r = _realized_r(outcome, entry.get("risk_reward"))
            bars = entry.get("bars_checked")

        if status == "skipped":
            continue
        if status != "closed":
            continue
        trades += 1
        total_r += realized_r
        if realized_r > 0:
            wins += 1
            gross_profit_r += realized_r
        elif realized_r < 0:
            gross_loss_r += abs(realized_r)
        risk_fraction = LADDER_SEQUENCE[step_index] / 100.0
        equity += equity * risk_fraction * realized_r
        equity_curve.append(equity - 100_000.0)
        if outcome == "tp_hit":
            resets += 1
            step_index = 0
        elif outcome == "sl_hit":
            advances += 1
            step_index = min(step_index + 1, len(LADDER_SEQUENCE) - 1)

    profit_factor = gross_profit_r / gross_loss_r if gross_loss_r else None
    return {
        "trades": trades,
        "wins": wins,
        "win_rate": (wins / trades) if trades else 0.0,
        "profit_factor": profit_factor,
        "total_r": total_r,
        "avg_r": (total_r / trades) if trades else 0.0,
        "ending_equity": equity,
        "max_drawdown_r": _max_drawdown(equity_curve) / 100_000.0,
        "ladder_resets": resets,
        "ladder_advances": advances,
    }


def _build_reconciliation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"current_counts": {}, "saved_summaries": {}, "notes": []}
    for section, lens in [("operational_journal", "raw"), ("operational_journal", "root_only"), ("since_inception_replay", "raw")]:
        subset = [row for row in rows if row["source_section"] == section and row["trade_lens"] == lens and row.get("status") == "closed"]
        result["current_counts"][f"{section}:{lens}"] = {
            "closed": len(subset),
            "tp_hits": sum(1 for row in subset if row.get("outcome") == "tp_hit"),
            "sl_hits": sum(1 for row in subset if row.get("outcome") == "sl_hit"),
        }

    operational_summary = _load_json(OP_SUMMARY_PATH) or {}
    first_signal_summary = _load_json(FIRST_SIGNAL_SUMMARY_PATH) or {}
    replay_summary = _load_json(REPLAY_SUMMARY_PATH) or {}
    result["saved_summaries"]["operational_summary"] = operational_summary.get("performance") or {}
    result["saved_summaries"]["first_signal_summary"] = (first_signal_summary.get("headline") or {})
    result["saved_summaries"]["replay_summary"] = replay_summary

    live_raw = result["current_counts"]["operational_journal:raw"]
    saved_raw = operational_summary.get("performance") or {}
    if saved_raw:
        sl_delta = int(live_raw["sl_hits"]) - int(saved_raw.get("sl_hits", 0) or 0)
        if sl_delta != 0:
            result["notes"].append(
                f"Operational summary markdown/json is stale versus the current journal: SL delta {sl_delta:+d}."
            )
    live_root = result["current_counts"].get("operational_journal:root_only", {})
    saved_root = first_signal_summary.get("headline") or {}
    if saved_root:
        tp_delta = int(live_root.get("tp_hits", 0)) - int(saved_root.get("tp_hits", 0) or 0)
        sl_delta = int(live_root.get("sl_hits", 0)) - int(saved_root.get("sl_hits", 0) or 0)
        if tp_delta != 0 or sl_delta != 0:
            result["notes"].append(
                "First-signal-only summary is behind the current journal state: "
                f"TP delta {tp_delta:+d}, SL delta {sl_delta:+d}."
            )
    return result


def build_analysis() -> dict[str, Any]:
    rows = _build_views()
    closed_rows = [row for row in rows if row.get("status") == "closed"]
    symbol_point_floors = _symbol_point_floors(closed_rows)

    bar_cache: dict[tuple[str, str], pd.DataFrame] = {}
    sl_rows: list[dict[str, Any]] = []
    by_view_metrics: dict[str, Any] = {}
    per_symbol: dict[str, dict[str, Any]] = defaultdict(lambda: {"sl_hits": 0, "reasons": Counter(), "saved_by": Counter()})

    for row in rows:
        if row.get("status") != "closed":
            continue
        frame = _load_bar_history(str(row["symbol"]), str(row["timeframe"]), bar_cache)
        entry_idx = _entry_index(frame, str(row["signal_timestamp"]))
        row["_entry_index"] = entry_idx
        atr_value = None
        high_noise = False
        noise_metrics = {"direction_flips": 0, "wickiness": None, "compression_atr": None}
        if entry_idx is not None:
            entry_bar = frame.iloc[entry_idx]
            atr_value = float(entry_bar["atr14"]) if pd.notna(entry_bar["atr14"]) else None
            noise_metrics = _recent_noise_metrics(frame, entry_idx)
            high_noise = bool(noise_metrics["high_noise"])
        row["stop_distance_points"] = round(_stop_distance_points(row), 6)
        row["stop_distance_pct"] = round((row["stop_distance_points"] / abs(float(row["entry"])) * 100.0), 4) if row["entry"] else None
        row["stop_distance_atr"] = round(row["stop_distance_points"] / atr_value, 4) if atr_value else None
        row["high_noise_session"] = high_noise
        row["direction_flips_pre_entry"] = noise_metrics["direction_flips"]
        row["wickiness_pre_entry"] = noise_metrics["wickiness"]
        row["compression_atr_pre_entry"] = noise_metrics["compression_atr"]

        if row.get("outcome") == "sl_hit":
            post_stop = _post_stop_metrics(row, frame)
            row.update(post_stop)

        for variant in VARIANTS:
            variant_result = _simulate_variant(row, frame, variant, symbol_point_floors)
            row[f"variant_{variant.variant_id}_status"] = variant_result.get("status")
            row[f"variant_{variant.variant_id}_outcome"] = variant_result.get("outcome")
            row[f"variant_{variant.variant_id}_realized_r"] = variant_result.get("realized_r")
            row[f"variant_{variant.variant_id}_bars_checked"] = variant_result.get("bars_checked")
            row[f"variant_{variant.variant_id}_skip_reason"] = variant_result.get("skip_reason")

        if row.get("outcome") == "sl_hit":
            reason, flags = _primary_reason(row)
            row["primary_reason"] = reason
            row["secondary_flags"] = flags
            row["recommended_action"] = _recommended_action(row)
            row["notes"] = (
                f"Scenario {row.get('scenario') or 'unknown'}; "
                f"overshoot_r={row.get('stop_overshoot_r')}; "
                f"mfe_after_sl_r={row.get('mfe_after_sl_r')}"
            )
            sl_rows.append(row)
            key = f"{row['source_section']}:{row['trade_lens']}"
            per_symbol[str(row["symbol"])]["sl_hits"] += 1
            per_symbol[str(row["symbol"])]["reasons"][reason] += 1
            if row.get("recommended_action") and row["recommended_action"] != "Keep baseline":
                per_symbol[str(row["symbol"])]["saved_by"][row["recommended_action"]] += 1

    for section in ["operational_journal", "since_inception_replay"]:
        for lens in ["raw", "root_only"]:
            subset = [
                row
                for row in rows
                if row["source_section"] == section and row["trade_lens"] == lens and row.get("status") == "closed"
            ]
            if not subset:
                continue
            metrics = {"baseline": _variant_metrics(subset, "baseline", use_variant=False)}
            for variant in VARIANTS[1:]:
                metrics[variant.variant_id] = _variant_metrics(subset, variant.variant_id, use_variant=True)
            by_view_metrics[f"{section}:{lens}"] = metrics

    leaderboard: list[dict[str, Any]] = []
    for view_key, metrics in by_view_metrics.items():
        baseline = metrics["baseline"]
        for variant in VARIANTS[1:]:
            current = metrics[variant.variant_id]
            leaderboard.append(
                {
                    "view": view_key,
                    "variant_id": variant.variant_id,
                    "label": variant.label,
                    "trade_delta": current["trades"] - baseline["trades"],
                    "win_rate_delta": round((current["win_rate"] - baseline["win_rate"]) * 100.0, 2),
                    "profit_factor_delta": (
                        round((current["profit_factor"] or 0.0) - (baseline["profit_factor"] or 0.0), 4)
                        if current["profit_factor"] is not None or baseline["profit_factor"] is not None
                        else None
                    ),
                    "total_r_delta": round(current["total_r"] - baseline["total_r"], 4),
                    "drawdown_delta_r": round(current["max_drawdown_r"] - baseline["max_drawdown_r"], 4),
                    "ending_equity_delta": round(current["ending_equity"] - baseline["ending_equity"], 2),
                    "ladder_reset_delta": current["ladder_resets"] - baseline["ladder_resets"],
                    "ladder_advance_delta": current["ladder_advances"] - baseline["ladder_advances"],
                }
            )
    leaderboard.sort(key=lambda row: (row["total_r_delta"], row["profit_factor_delta"] or -999), reverse=True)

    top_cases = sorted(
        [
            row
            for row in sl_rows
            if row.get("would_reach_tp_if_survived") and (row.get("stop_overshoot_r") or 999.0) <= 0.20
        ],
        key=lambda row: (row.get("stop_overshoot_r") or 999.0, -(row.get("mfe_after_sl_r") or 0.0)),
    )[:15]

    sl_breakdown_rows: list[dict[str, Any]] = []
    grouped_breakdown: dict[tuple[str, str, str, str, int | None], list[dict[str, Any]]] = defaultdict(list)
    for row in sl_rows:
        key = (
            str(row["source_section"]),
            str(row["trade_lens"]),
            str(row["symbol"]),
            str(row["timeframe"]),
            row.get("ladder_step_at_entry"),
        )
        grouped_breakdown[key].append(row)
    for (source_section, trade_lens, symbol, timeframe, ladder_step), items in sorted(grouped_breakdown.items()):
        sl_breakdown_rows.append(
            {
                "source_section": source_section,
                "trade_lens": trade_lens,
                "symbol": symbol,
                "timeframe": timeframe,
                "ladder_step": ladder_step,
                "sl_hits": len(items),
                "top_reason": Counter(item["primary_reason"] for item in items).most_common(1)[0][0],
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "assumptions": {
            "strategy_id": "strategy_four",
            "trade_lenses": ["raw", "root_only"],
            "repetition_window_bars": REPETITION_WINDOW_BARS,
            "post_stop_window_bars": POST_STOP_WINDOW_BARS,
            "symbol_point_floor_method": "25th percentile of closed-trade stop distances per symbol",
            "high_noise_rule": ">=3 close-direction flips over the last 6 bars and compressed range <= 2.25 ATR",
        },
        "reconciliation": _build_reconciliation(rows),
        "summary_counts": {
            "total_rows": len(rows),
            "closed_rows": len(closed_rows),
            "sl_rows": len(sl_rows),
            "by_view": {
                view: {
                    "trades": metrics["baseline"]["trades"],
                    "sl_hits": sum(
                        1
                        for row in rows
                        if f"{row['source_section']}:{row['trade_lens']}" == view and row.get("outcome") == "sl_hit"
                    ),
                }
                for view, metrics in by_view_metrics.items()
            },
        },
        "symbol_point_floors": symbol_point_floors,
        "by_view_metrics": by_view_metrics,
        "intervention_leaderboard": leaderboard,
        "per_symbol_breakdown": {
            symbol: {
                "sl_hits": payload["sl_hits"],
                "reasons": dict(payload["reasons"]),
                "saved_by": dict(payload["saved_by"]),
            }
            for symbol, payload in sorted(per_symbol.items())
        },
        "sl_breakdown_rows": sl_breakdown_rows,
        "top_small_overshoot_cases": [
            {
                "source_section": row["source_section"],
                "trade_lens": row["trade_lens"],
                "setup_id": row["setup_id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "side": row["side"],
                "signal_timestamp": row["signal_timestamp"],
                "stop_overshoot_r": row.get("stop_overshoot_r"),
                "mfe_after_sl_r": row.get("mfe_after_sl_r"),
                "recommended_action": row.get("recommended_action"),
            }
            for row in top_cases
        ],
        "sl_rows": sl_rows,
    }


def _write_csv(sl_rows: list[dict[str, Any]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_section",
        "trade_lens",
        "setup_id",
        "symbol",
        "timeframe",
        "side",
        "entry_timestamp",
        "stop_timestamp",
        "ladder_step",
        "ladder_risk_pct",
        "scenario",
        "quality_score",
        "stop_distance_points",
        "stop_distance_pct",
        "stop_distance_atr",
        "primary_reason",
        "secondary_flags",
        "duplicate_cluster_exposure",
        "high_noise_session",
        "mfe_after_sl_points",
        "mfe_after_sl_r",
        "mae_after_sl_points",
        "mae_after_sl_r",
        "bars_to_recovery",
        "bars_to_tp_if_survived",
        "would_reach_tp_if_survived",
        "stop_overshoot_points",
        "stop_overshoot_r",
        "would_survive_fixed_widen_10",
        "would_survive_fixed_widen_20",
        "would_survive_atr_floor_025",
        "would_survive_1bar_delay",
        "would_reach_tp_fixed_widen_10",
        "would_reach_tp_atr_floor_025",
        "recommended_action",
        "notes",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in sl_rows:
            writer.writerow(
                {
                    "source_section": row["source_section"],
                    "trade_lens": row["trade_lens"],
                    "setup_id": row["setup_id"],
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "side": row["side"],
                    "entry_timestamp": row["signal_timestamp"],
                    "stop_timestamp": row.get("outcome_timestamp"),
                    "ladder_step": row.get("ladder_step_at_entry"),
                    "ladder_risk_pct": row.get("ladder_risk_pct_at_entry"),
                    "scenario": row.get("scenario"),
                    "quality_score": row.get("quality_score"),
                    "stop_distance_points": row.get("stop_distance_points"),
                    "stop_distance_pct": row.get("stop_distance_pct"),
                    "stop_distance_atr": row.get("stop_distance_atr"),
                    "primary_reason": row.get("primary_reason"),
                    "secondary_flags": "|".join(row.get("secondary_flags", [])),
                    "duplicate_cluster_exposure": row.get("duplicate_cluster_exposure"),
                    "high_noise_session": row.get("high_noise_session"),
                    "mfe_after_sl_points": row.get("mfe_after_sl_points"),
                    "mfe_after_sl_r": row.get("mfe_after_sl_r"),
                    "mae_after_sl_points": row.get("mae_after_sl_points"),
                    "mae_after_sl_r": row.get("mae_after_sl_r"),
                    "bars_to_recovery": row.get("bars_to_recovery"),
                    "bars_to_tp_if_survived": row.get("bars_to_tp_if_survived"),
                    "would_reach_tp_if_survived": row.get("would_reach_tp_if_survived"),
                    "stop_overshoot_points": row.get("stop_overshoot_points"),
                    "stop_overshoot_r": row.get("stop_overshoot_r"),
                    "would_survive_fixed_widen_10": row.get("variant_fixed_widen_10_outcome") != "sl_hit",
                    "would_survive_fixed_widen_20": row.get("variant_fixed_widen_20_outcome") != "sl_hit",
                    "would_survive_atr_floor_025": row.get("variant_atr_floor_025_outcome") != "sl_hit",
                    "would_survive_1bar_delay": row.get("variant_delay_1bar_outcome") != "sl_hit",
                    "would_reach_tp_fixed_widen_10": row.get("variant_fixed_widen_10_outcome") == "tp_hit",
                    "would_reach_tp_atr_floor_025": row.get("variant_atr_floor_025_outcome") == "tp_hit",
                    "recommended_action": row.get("recommended_action"),
                    "notes": row.get("notes"),
                }
            )


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# CWT SL Forensics Report",
        "",
        "## Headline Findings",
        "",
    ]
    for note in summary["reconciliation"].get("notes", []):
        lines.append(f"- {note}")
    lines.extend(
        [
            f"- Total analyzed SL rows: `{summary['summary_counts']['sl_rows']}`",
            f"- Views covered: `{', '.join(summary['summary_counts']['by_view'])}`",
            "",
            "## SL Counts By Source / Lens",
            "",
            "| View | Trades | SL Hits |",
            "|---|---:|---:|",
        ]
    )
    for view, payload in sorted(summary["summary_counts"]["by_view"].items()):
        lines.append(f"| `{view}` | `{payload['trades']}` | `{payload['sl_hits']}` |")

    reason_counts = Counter(row["primary_reason"] for row in summary["sl_rows"])
    lines.extend(
        [
            "",
            "## Top Recurring SL Reasons",
            "",
            "| Reason | Count |",
            "|---|---:|",
        ]
    )
    for reason, count in reason_counts.most_common():
        lines.append(f"| `{reason}` | `{count}` |")

    lines.extend(
        [
            "",
            "## SL Breakdown By Symbol / TF / Ladder Step",
            "",
            "| Source | Lens | Symbol | TF | Ladder Step | SL Hits | Top Reason |",
            "|---|---|---|---|---:|---:|---|",
        ]
    )
    for row in sorted(summary["sl_breakdown_rows"], key=lambda item: (-item["sl_hits"], item["source_section"], item["symbol"]))[:20]:
        lines.append(
            f"| `{row['source_section']}` | `{row['trade_lens']}` | `{row['symbol']}` | `{row['timeframe']}` | "
            f"`{row['ladder_step']}` | `{row['sl_hits']}` | `{row['top_reason']}` |"
        )

    saved_vs_bad = {
        "saved_by_fixed_widen_10": sum(1 for row in summary["sl_rows"] if row.get("variant_fixed_widen_10_outcome") == "tp_hit"),
        "saved_by_atr_floor_025": sum(1 for row in summary["sl_rows"] if row.get("variant_atr_floor_025_outcome") == "tp_hit"),
        "still_bad_after_fixed_widen_30": sum(1 for row in summary["sl_rows"] if row.get("variant_fixed_widen_30_outcome") == "sl_hit"),
        "still_bad_after_delay_1bar": sum(1 for row in summary["sl_rows"] if row.get("variant_delay_1bar_outcome") == "sl_hit"),
    }
    lines.extend(
        [
            "",
            "## Saved vs Still Bad",
            "",
            f"- Saved by `+10%` stop widening and still reaches TP: `{saved_vs_bad['saved_by_fixed_widen_10']}`",
            f"- Saved by `0.25 ATR` floor and still reaches TP: `{saved_vs_bad['saved_by_atr_floor_025']}`",
            f"- Still SL after `+30%` widening: `{saved_vs_bad['still_bad_after_fixed_widen_30']}`",
            f"- Still SL after `1-bar` delayed entry: `{saved_vs_bad['still_bad_after_delay_1bar']}`",
            "",
            "## Intervention Leaderboard",
            "",
            "| View | Variant | Total R Delta | Profit Factor Delta | Trade Delta | Drawdown Delta R |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in summary["intervention_leaderboard"][:16]:
        profit_factor_delta = "n/a" if row["profit_factor_delta"] is None else f"{row['profit_factor_delta']:+.4f}"
        lines.append(
            f"| `{row['view']}` | `{row['variant_id']}` | `{row['total_r_delta']:+.4f}` | "
            f"`{profit_factor_delta}` | `{row['trade_delta']:+d}` | `{row['drawdown_delta_r']:+.4f}` |"
        )

    lines.extend(
        [
            "",
            "## Small Overshoot Cases That Recovered",
            "",
            "| Source | Lens | Symbol | Setup | Overshoot R | MFE After SL R | Recommended Action |",
            "|---|---|---|---|---:|---:|---|",
        ]
    )
    for row in summary["top_small_overshoot_cases"][:12]:
        lines.append(
            f"| `{row['source_section']}` | `{row['trade_lens']}` | `{row['symbol']}` | `{row['setup_id']}` | "
            f"`{row['stop_overshoot_r']}` | `{row['mfe_after_sl_r']}` | `{row['recommended_action']}` |"
        )

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
        ]
    )
    recommended_actions = Counter(row["recommended_action"] for row in summary["sl_rows"])
    for action, count in recommended_actions.most_common(8):
        lines.append(f"- `{action}`: `{count}` SL cases")
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(summary["sl_rows"])
    json_payload = {
        key: value for key, value in summary.items() if key != "sl_rows"
    }
    JSON_PATH.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_render_markdown(summary), encoding="utf-8")


def main() -> None:
    summary = build_analysis()
    write_outputs(summary)
    print(json.dumps({"report": str(REPORT_PATH), "csv": str(CSV_PATH), "json": str(JSON_PATH)}, indent=2))


if __name__ == "__main__":
    main()
