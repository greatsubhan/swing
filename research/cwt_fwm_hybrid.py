"""Research-only CWT + First Wise Man hybrid comparison.

This runner keeps the current production CWT logic intact and tests two
research overlays against the current benchmark:

1. Baseline CWT
2. CWT + FWM Gate
3. CWT + FWM Entry Lane

Phase 1 intentionally freezes:

- H1 bias
- minimum execution timeframe by symbol
- Scenario 1 + Scenario 2
- fixed 1:1 exit
- funded ladder 0.07 / 0.20 / 0.45 / 1.00
- funded guardrails

It only asks whether a strict, backtest-safe First Wise Man layer improves the
existing entry quality enough to matter.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.cwt_forex_backtest import (  # noqa: E402
    BUFFER_ATR_FRACTION,
    MAX_BARS_HELD,
    Position,
    compute_bias_series,
    compute_mt5_zigzag,
    load_oanda_history,
    project_cambist_levels,
    scenario_one_long,
    scenario_one_short,
    scenario_two_long,
    scenario_two_short,
    with_indicators,
)
from signal_platform.env import load_dotenv  # noqa: E402
from strategy_four_bot.watchlists import minimum_timeframe_for  # noqa: E402

START = "2023-01-01"
END = "2026-04-01"
OUTPUT_DIR = Path("reports/cwt_forex")
OUTPUT_JSON = OUTPUT_DIR / "FWM_HYBRID_RESEARCH.json"
OUTPUT_MD = OUTPUT_DIR / "FWM_HYBRID_RESEARCH.md"
NEXT_STEPS_MD = OUTPUT_DIR / "FWM_HYBRID_NEXT_STEPS.md"

SHORTLIST = [
    "NAS100_USD",
    "SPX500_USD",
    "UK100_GBP",
    "USD_JPY",
    "NZD_USD",
    "AUD_USD",
    "EUR_USD",
    "GBP_JPY",
]

STARTING_BALANCE = 100_000.0
ASSET_DAILY_CAP_DOLLARS = 1_000.0
PORTFOLIO_DAILY_CAP_DOLLARS = 5_000.0
OVERALL_BRAKE_EQUITY = 95_000.0
RISK_LADDER = [0.07, 0.20, 0.45, 1.00]

FWM_SWING_LOOKBACK_BARS = 8
FWM_GATE_LOOKBACK_BARS = 12
FWM_ORDER_VALID_BARS = 2


@dataclass
class PendingFwmOrder:
    symbol: str
    timeframe: str
    side: str
    signal_time: pd.Timestamp
    signal_index: int
    activate_index: int
    expire_index: int
    trigger_price: float
    stop_price: float
    target_price: float
    initial_risk: float
    bias_timeframe: str = "H1"
    source: str = "fwm"
    scenario: str = "fwm"


@dataclass
class ResearchPosition:
    symbol: str
    timeframe: str
    side: str
    source: str
    scenario: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    target_price: float
    initial_risk: float
    bars_held: int = 0


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def granularity_for_label(label: str) -> str:
    return {"5m": "M5", "15m": "M15"}[label]


def risk_pct_to_dollars(risk_pct: float) -> float:
    return STARTING_BALANCE * (risk_pct / 100.0)


def load_symbol_frame(symbol: str, timeframe_label: str) -> pd.DataFrame:
    execution = with_indicators(
        load_oanda_history(
            symbol,
            granularity_for_label(timeframe_label),
            start=START,
            end=END,
        )
    )
    bias_frame = with_indicators(load_oanda_history(symbol, "H1", start=START, end=END))
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
    return execution


def upper_half_close(row: pd.Series) -> bool:
    if float(row["high"]) <= float(row["low"]):
        return False
    return float(row["close"]) >= (float(row["high"]) + float(row["low"])) / 2.0


def lower_half_close(row: pd.Series) -> bool:
    if float(row["high"]) <= float(row["low"]):
        return False
    return float(row["close"]) <= (float(row["high"]) + float(row["low"])) / 2.0


def detect_fwm_candidate(frame: pd.DataFrame, idx: int, bias: int) -> dict[str, float | str] | None:
    if idx < max(1, FWM_SWING_LOOKBACK_BARS - 1):
        return None

    row = frame.iloc[idx]
    previous = frame.iloc[idx - 1]
    if pd.isna(row["atr14"]) or pd.isna(row["jaw"]) or pd.isna(row["teeth"]) or pd.isna(row["lips"]):
        return None

    recent = frame.iloc[idx - FWM_SWING_LOOKBACK_BARS + 1 : idx + 1]
    mouth_low = float(min(row["jaw"], row["teeth"], row["lips"]))
    mouth_high = float(max(row["jaw"], row["teeth"], row["lips"]))
    buffer = float(row["atr14"]) * BUFFER_ATR_FRACTION

    if bias == 1:
        is_recent_swing_low = float(row["low"]) <= float(recent["low"].min())
        is_outside_mouth = float(row["low"]) < mouth_low
        line_flattening = float(row["lips"]) >= float(previous["lips"])
        if is_recent_swing_low and is_outside_mouth and upper_half_close(row) and line_flattening:
            trigger = float(row["high"]) + buffer
            stop = float(row["low"]) - buffer
            if stop < trigger:
                return {
                    "side": "long",
                    "trigger_price": trigger,
                    "stop_price": stop,
                    "target_price": trigger + (trigger - stop),
                    "initial_risk": trigger - stop,
                    "source": "fwm",
                    "scenario": "fwm",
                }

    if bias == -1:
        is_recent_swing_high = float(row["high"]) >= float(recent["high"].max())
        is_outside_mouth = float(row["high"]) > mouth_high
        line_flattening = float(row["lips"]) <= float(previous["lips"])
        if is_recent_swing_high and is_outside_mouth and lower_half_close(row) and line_flattening:
            trigger = float(row["low"]) - buffer
            stop = float(row["high"]) + buffer
            if stop > trigger:
                return {
                    "side": "short",
                    "trigger_price": trigger,
                    "stop_price": stop,
                    "target_price": trigger - (stop - trigger),
                    "initial_risk": stop - trigger,
                    "source": "fwm",
                    "scenario": "fwm",
                }

    return None


def build_pending_fwm_order(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    idx: int,
    candidate: dict[str, float | str],
) -> PendingFwmOrder | None:
    trigger_price = float(candidate["trigger_price"])
    stop_price = float(candidate["stop_price"])
    initial_risk = float(candidate["initial_risk"])
    if initial_risk <= 0:
        return None
    return PendingFwmOrder(
        symbol=symbol,
        timeframe=timeframe,
        side=str(candidate["side"]),
        signal_time=frame.index[idx],
        signal_index=idx,
        activate_index=idx + 1,
        expire_index=idx + FWM_ORDER_VALID_BARS,
        trigger_price=trigger_price,
        stop_price=stop_price,
        target_price=float(candidate["target_price"]),
        initial_risk=initial_risk,
    )


def build_baseline_signal(frame: pd.DataFrame, idx: int) -> dict[str, float | str] | None:
    row = frame.iloc[idx]
    if pd.isna(row["atr14"]) or pd.isna(row["jaw"]):
        return None

    bias = int(row["bias_signal"])
    active_blue = float(row["active_blue"]) if pd.notna(row["active_blue"]) else None
    active_red = float(row["active_red"]) if pd.notna(row["active_red"]) else None

    long_signal = scenario_one_long(frame, idx, bias)
    short_signal = scenario_one_short(frame, idx, bias)
    if long_signal is None and short_signal is None:
        long_signal = scenario_two_long(frame, idx, bias, active_red)
        short_signal = scenario_two_short(frame, idx, bias, active_blue)

    signal = long_signal if long_signal is not None else short_signal
    if signal is None:
        return None

    next_bar = frame.iloc[idx + 1]
    entry_time = frame.index[idx + 1]
    entry_price = float(next_bar["open"])
    buffer = float(signal["atr"]) * BUFFER_ATR_FRACTION

    if signal is long_signal:
        side = "long"
        stop_price = float(signal["stop_anchor"]) - buffer
        if stop_price >= entry_price:
            return None
        initial_risk = entry_price - stop_price
        target_price = entry_price + initial_risk
    else:
        side = "short"
        stop_price = float(signal["stop_anchor"]) + buffer
        if stop_price <= entry_price:
            return None
        initial_risk = stop_price - entry_price
        target_price = entry_price - initial_risk

    if initial_risk <= 0:
        return None

    return {
        "symbol": "",
        "timeframe": "",
        "side": side,
        "source": "baseline",
        "scenario": str(signal["scenario"]),
        "entry_time": entry_time,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "initial_risk": initial_risk,
    }


def open_research_position(
    symbol: str,
    timeframe: str,
    signal: dict[str, object],
) -> ResearchPosition:
    return ResearchPosition(
        symbol=symbol,
        timeframe=timeframe,
        side=str(signal["side"]),
        source=str(signal["source"]),
        scenario=str(signal["scenario"]),
        entry_time=pd.Timestamp(signal["entry_time"]),
        entry_price=float(signal["entry_price"]),
        stop_price=float(signal["stop_price"]),
        target_price=float(signal["target_price"]),
        initial_risk=float(signal["initial_risk"]),
    )


def maybe_trigger_fwm_order(
    pending_order: PendingFwmOrder | None,
    frame: pd.DataFrame,
    idx: int,
) -> tuple[PendingFwmOrder | None, ResearchPosition | None]:
    if pending_order is None:
        return None, None
    if idx < pending_order.activate_index:
        return pending_order, None
    if idx > pending_order.expire_index:
        return None, None

    row = frame.iloc[idx]
    bar_time = frame.index[idx]
    if pending_order.side == "long" and float(row["high"]) >= pending_order.trigger_price:
        entry_price = max(float(row["open"]), pending_order.trigger_price)
        if pending_order.stop_price >= entry_price:
            return None, None
        return (
            None,
            ResearchPosition(
                symbol=pending_order.symbol,
                timeframe=pending_order.timeframe,
                side="long",
                source="fwm",
                scenario="fwm",
                entry_time=bar_time,
                entry_price=entry_price,
                stop_price=pending_order.stop_price,
                target_price=entry_price + (entry_price - pending_order.stop_price),
                initial_risk=entry_price - pending_order.stop_price,
            ),
        )

    if pending_order.side == "short" and float(row["low"]) <= pending_order.trigger_price:
        entry_price = min(float(row["open"]), pending_order.trigger_price)
        if pending_order.stop_price <= entry_price:
            return None, None
        return (
            None,
            ResearchPosition(
                symbol=pending_order.symbol,
                timeframe=pending_order.timeframe,
                side="short",
                source="fwm",
                scenario="fwm",
                entry_time=bar_time,
                entry_price=entry_price,
                stop_price=pending_order.stop_price,
                target_price=entry_price - (pending_order.stop_price - entry_price),
                initial_risk=pending_order.stop_price - entry_price,
            ),
        )

    return pending_order, None


def close_position_if_needed(
    frame: pd.DataFrame,
    idx: int,
    position: ResearchPosition,
) -> dict[str, object] | None:
    row = frame.iloc[idx]
    position.bars_held += 1

    exit_price: float | None = None
    reason: str | None = None
    bias = int(row["bias_signal"])

    if position.side == "long":
        if float(row["low"]) <= position.stop_price:
            exit_price = position.stop_price
            reason = "stop"
        elif float(row["high"]) >= position.target_price:
            exit_price = position.target_price
            reason = "target"
        elif bias == -1:
            exit_price = float(row["close"])
            reason = "bias_flip"
    else:
        if float(row["high"]) >= position.stop_price:
            exit_price = position.stop_price
            reason = "stop"
        elif float(row["low"]) <= position.target_price:
            exit_price = position.target_price
            reason = "target"
        elif bias == 1:
            exit_price = float(row["close"])
            reason = "bias_flip"

    if exit_price is None and position.bars_held >= MAX_BARS_HELD:
        exit_price = float(row["close"])
        reason = "timeout"

    if exit_price is None or reason is None:
        return None

    if position.side == "long":
        r_multiple = (exit_price - position.entry_price) / position.initial_risk
    else:
        r_multiple = (position.entry_price - exit_price) / position.initial_risk

    return {
        "symbol": position.symbol,
        "timeframe": position.timeframe,
        "side": position.side,
        "source": position.source,
        "scenario": position.scenario,
        "entry_time": position.entry_time.isoformat(),
        "exit_time": frame.index[idx].isoformat(),
        "entry_price": round(position.entry_price, 6),
        "exit_price": round(exit_price, 6),
        "bars_held": position.bars_held,
        "hold_minutes": hold_minutes(position.timeframe, position.bars_held),
        "r_multiple": round(float(r_multiple), 6),
        "reason": reason,
    }


def hold_minutes(timeframe: str, bars_held: int) -> int:
    multiplier = {"5m": 5, "15m": 15}[timeframe]
    return multiplier * bars_held


def generate_trades_for_mode(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    mode: str,
    selective_fwm_symbols: set[str] | None = None,
) -> list[dict[str, object]]:
    effective_mode = mode
    if mode == "fwm_selective":
        enabled = symbol in (selective_fwm_symbols or set())
        effective_mode = "fwm_entry_lane" if enabled else "baseline"

    position: ResearchPosition | None = None
    pending_order: PendingFwmOrder | None = None
    trade_log: list[dict[str, object]] = []
    last_fwm_idx_by_side: dict[str, int | None] = {"long": None, "short": None}

    for idx in range(120, len(frame) - 1):
        row = frame.iloc[idx]
        if pd.isna(row["atr14"]) or pd.isna(row["jaw"]):
            continue

        if position is not None:
            closed_trade = close_position_if_needed(frame, idx, position)
            if closed_trade is not None:
                trade_log.append(closed_trade)
                position = None
                pending_order = None
                continue

        if position is not None:
            continue

        pending_order, triggered_position = maybe_trigger_fwm_order(pending_order, frame, idx)
        if triggered_position is not None:
            position = triggered_position
            continue

        bias = int(row["bias_signal"])
        candidate = detect_fwm_candidate(frame, idx, bias)
        if candidate is not None:
            last_fwm_idx_by_side[str(candidate["side"])] = idx
            opposite = "short" if str(candidate["side"]) == "long" else "long"
            last_fwm_idx_by_side[opposite] = None
            if effective_mode == "fwm_entry_lane":
                pending_order = build_pending_fwm_order(symbol, timeframe, frame, idx, candidate)

        baseline_signal = build_baseline_signal(frame, idx)
        if baseline_signal is not None:
            signal_side = str(baseline_signal["side"])
            gate_side = signal_side
            gate_idx = last_fwm_idx_by_side[gate_side]
            gate_is_open = gate_idx is not None and (idx - gate_idx) <= FWM_GATE_LOOKBACK_BARS

            if effective_mode == "fwm_gate" and not gate_is_open:
                baseline_signal = None
            elif baseline_signal is not None:
                baseline_signal["symbol"] = symbol
                baseline_signal["timeframe"] = timeframe

        if baseline_signal is not None:
            pending_order = None
            position = open_research_position(symbol, timeframe, baseline_signal)

    if position is not None:
        final_bar = frame.iloc[-1]
        final_price = float(final_bar["close"])
        if position.side == "long":
            r_multiple = (final_price - position.entry_price) / position.initial_risk
        else:
            r_multiple = (position.entry_price - final_price) / position.initial_risk
        trade_log.append(
            {
                "symbol": position.symbol,
                "timeframe": position.timeframe,
                "side": position.side,
                "source": position.source,
                "scenario": position.scenario,
                "entry_time": position.entry_time.isoformat(),
                "exit_time": frame.index[-1].isoformat(),
                "entry_price": round(position.entry_price, 6),
                "exit_price": round(final_price, 6),
                "bars_held": position.bars_held,
                "hold_minutes": hold_minutes(position.timeframe, position.bars_held),
                "r_multiple": round(float(r_multiple), 6),
                "reason": "final_bar",
            }
        )

    return trade_log


def replay_funded_portfolio(raw_trades: list[dict[str, object]]) -> dict[str, object]:
    equity = STARTING_BALANCE
    peak_equity = STARTING_BALANCE
    max_drawdown = 0.0
    ladder_index_by_symbol: dict[str, int] = defaultdict(int)
    daily_asset_risk: dict[str, float] = defaultdict(float)
    daily_portfolio_risk = 0.0
    current_day: str | None = None

    processed = 0
    skipped_asset = 0
    skipped_portfolio = 0
    skipped_brake = 0
    taken_trades: list[dict[str, object]] = []
    risk_step_counts: Counter[float] = Counter()
    scenario_mix: Counter[str] = Counter()
    source_mix: Counter[str] = Counter()
    per_symbol: dict[str, dict[str, float | int]] = {
        symbol: {
            "taken": 0,
            "wins": 0,
            "losses": 0,
            "net_pnl_dollars": 0.0,
            "net_pct": 0.0,
            "skipped_asset_cap": 0,
            "skipped_portfolio_cap": 0,
            "skipped_overall_brake": 0,
        }
        for symbol in SHORTLIST
    }

    trades = sorted(raw_trades, key=lambda trade: trade["entry_time"])
    for trade in trades:
        symbol = str(trade["symbol"])
        entry_day = str(trade["entry_time"])[:10]
        if current_day != entry_day:
            current_day = entry_day
            daily_asset_risk = defaultdict(float)
            daily_portfolio_risk = 0.0

        risk_pct = RISK_LADDER[min(ladder_index_by_symbol[symbol], len(RISK_LADDER) - 1)]
        risk_dollars = risk_pct_to_dollars(risk_pct)

        if equity < OVERALL_BRAKE_EQUITY:
            skipped_brake += 1
            per_symbol[symbol]["skipped_overall_brake"] += 1
            continue
        if daily_asset_risk[symbol] + risk_dollars > ASSET_DAILY_CAP_DOLLARS:
            skipped_asset += 1
            per_symbol[symbol]["skipped_asset_cap"] += 1
            continue
        if daily_portfolio_risk + risk_dollars > PORTFOLIO_DAILY_CAP_DOLLARS:
            skipped_portfolio += 1
            per_symbol[symbol]["skipped_portfolio_cap"] += 1
            continue

        daily_asset_risk[symbol] += risk_dollars
        daily_portfolio_risk += risk_dollars
        risk_step_counts[risk_pct] += 1
        scenario_mix[str(trade["scenario"])] += 1
        source_mix[str(trade["source"])] += 1

        r_multiple = float(trade["r_multiple"])
        pnl_dollars = risk_dollars * r_multiple
        equity += pnl_dollars
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, peak_equity - equity)
        processed += 1

        if pnl_dollars > 0:
            ladder_index_by_symbol[symbol] = 0
            per_symbol[symbol]["wins"] += 1
        else:
            ladder_index_by_symbol[symbol] = min(ladder_index_by_symbol[symbol] + 1, len(RISK_LADDER) - 1)
            per_symbol[symbol]["losses"] += 1

        per_symbol[symbol]["taken"] += 1
        per_symbol[symbol]["net_pnl_dollars"] += pnl_dollars
        per_symbol[symbol]["net_pct"] += (pnl_dollars / STARTING_BALANCE) * 100.0

        taken_trades.append(
            {
                **trade,
                "risk_pct": risk_pct,
                "risk_dollars": round(risk_dollars, 2),
                "pnl_dollars": round(pnl_dollars, 2),
                "equity_after": round(equity, 2),
            }
        )

    wins = [trade for trade in taken_trades if float(trade["pnl_dollars"]) > 0]
    losses = [trade for trade in taken_trades if float(trade["pnl_dollars"]) < 0]
    profit_factor = None
    if losses:
        profit_factor = round(
            sum(float(trade["pnl_dollars"]) for trade in wins)
            / abs(sum(float(trade["pnl_dollars"]) for trade in losses)),
            2,
        )

    avg_hold = round(mean(float(trade["hold_minutes"]) for trade in taken_trades), 2) if taken_trades else 0.0
    return {
        "portfolio_summary": {
            "ending_balance": round(equity, 2),
            "net_pnl_dollars": round(equity - STARTING_BALANCE, 2),
            "return_pct": round(((equity / STARTING_BALANCE) - 1) * 100.0, 2),
            "trades_taken": processed,
            "trades_skipped_asset_cap": skipped_asset,
            "trades_skipped_portfolio_cap": skipped_portfolio,
            "trades_skipped_overall_brake": skipped_brake,
            "win_rate": round((len(wins) / processed) * 100.0, 2) if processed else 0.0,
            "profit_factor": profit_factor,
            "max_drawdown_dollars": round(max_drawdown, 2),
            "average_hold_minutes": avg_hold,
            "risk_step_counts": {str(step): count for step, count in sorted(risk_step_counts.items())},
            "scenario_mix": dict(sorted(scenario_mix.items())),
            "source_mix": dict(sorted(source_mix.items())),
        },
        "per_symbol_summary": {
            symbol: {
                **stats,
                "net_pnl_dollars": round(float(stats["net_pnl_dollars"]), 2),
                "net_pct": round(float(stats["net_pct"]), 2),
                "win_rate": round((int(stats["wins"]) / int(stats["taken"])) * 100.0, 2) if int(stats["taken"]) else 0.0,
            }
            for symbol, stats in per_symbol.items()
        },
        "taken_trades_sample": taken_trades[:40],
    }


def summarize_mode(raw_trades: list[dict[str, object]], funded: dict[str, object]) -> dict[str, object]:
    r_values = [float(trade["r_multiple"]) for trade in raw_trades]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    raw_profit_factor = None
    if losses:
        raw_profit_factor = round(sum(wins) / abs(sum(losses)), 2)

    scenario_mix = Counter(str(trade["scenario"]) for trade in raw_trades)
    source_mix = Counter(str(trade["source"]) for trade in raw_trades)
    hold_average = round(mean(float(trade["hold_minutes"]) for trade in raw_trades), 2) if raw_trades else 0.0

    return {
        "raw_trade_summary": {
            "trades": len(raw_trades),
            "win_rate": round((len(wins) / len(raw_trades)) * 100.0, 2) if raw_trades else 0.0,
            "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
            "profit_factor": raw_profit_factor,
            "average_hold_minutes": hold_average,
            "scenario_mix": dict(sorted(scenario_mix.items())),
            "source_mix": dict(sorted(source_mix.items())),
        },
        **funded,
    }


def evaluate_verdict(mode_name: str, baseline: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    base_summary = baseline["portfolio_summary"]
    candidate_summary = candidate["portfolio_summary"]
    baseline_symbols = baseline["per_symbol_summary"]
    candidate_symbols = candidate["per_symbol_summary"]

    base_pf = float(base_summary["profit_factor"] or 0.0)
    candidate_pf = float(candidate_summary["profit_factor"] or 0.0)
    base_return = float(base_summary["return_pct"])
    candidate_return = float(candidate_summary["return_pct"])
    base_dd = float(base_summary["max_drawdown_dollars"])
    candidate_dd = float(candidate_summary["max_drawdown_dollars"])
    base_trades = int(base_summary["trades_taken"])
    candidate_trades = int(candidate_summary["trades_taken"])

    improved_symbols = sum(
        1
        for symbol in SHORTLIST
        if float(candidate_symbols[symbol]["net_pnl_dollars"]) > float(baseline_symbols[symbol]["net_pnl_dollars"])
    )
    positive_symbols = sum(
        1 for symbol in SHORTLIST if float(candidate_symbols[symbol]["net_pnl_dollars"]) > 0
    )

    pf_improved_meaningfully = candidate_pf >= base_pf + 0.03
    return_improved_without_pf_damage = candidate_return >= base_return + 5.0 and candidate_pf >= base_pf - 0.01
    drawdown_ok = candidate_dd <= base_dd * 1.10
    trades_ok = candidate_trades >= int(base_trades * 0.75)
    breadth_ok = improved_symbols >= 3 and positive_symbols >= 6

    keep = (pf_improved_meaningfully or return_improved_without_pf_damage) and drawdown_ok and trades_ok and breadth_ok

    return {
        "mode": mode_name,
        "verdict": "keep" if keep else "discard",
        "checks": {
            "pf_improved_meaningfully": pf_improved_meaningfully,
            "return_improved_without_pf_damage": return_improved_without_pf_damage,
            "drawdown_ok": drawdown_ok,
            "trades_ok": trades_ok,
            "breadth_ok": breadth_ok,
        },
        "assumptions": {
            "pf_improvement_threshold": "+0.03",
            "return_upgrade_without_pf_damage": "+5.0 return points with profit factor no worse than -0.01",
            "max_drawdown_tolerance": "+10%",
            "trade_count_floor": "75% of baseline",
            "breadth_requirement": ">=3 symbols improve and >=6 stay positive",
        },
        "comparison": {
            "baseline_profit_factor": base_pf,
            "candidate_profit_factor": candidate_pf,
            "baseline_return_pct": base_return,
            "candidate_return_pct": candidate_return,
            "baseline_max_drawdown_dollars": base_dd,
            "candidate_max_drawdown_dollars": candidate_dd,
            "baseline_trades_taken": base_trades,
            "candidate_trades_taken": candidate_trades,
            "improved_symbols": improved_symbols,
            "positive_symbols": positive_symbols,
        },
    }


def format_currency(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"${float(value):,.2f}"


def format_pct(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}%"


def build_markdown_report(result: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# CWT FWM Hybrid Research")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- Research-only comparison. Live `strategy_four` was left untouched.")
    lines.append("- Baseline frozen to current CWT benchmark style:")
    lines.append("  - `H1` bias")
    lines.append("  - minimum timeframe by symbol")
    lines.append("  - `Scenario 1 + Scenario 2`")
    lines.append("  - fixed `1:1` exit")
    lines.append("  - ZigZag/Cambist `12 / 5 / 3`")
    lines.append("  - ladder `0.07 / 0.20 / 0.45 / 1.00`")
    lines.append("  - funded caps `$1,000 / $5,000 / $95,000 brake`")
    lines.append("")
    lines.append("## FWM Assumptions")
    lines.append("")
    lines.append(f"- swing lookback: `{FWM_SWING_LOOKBACK_BARS}` bars")
    lines.append(f"- gate lookback: `{FWM_GATE_LOOKBACK_BARS}` bars")
    lines.append(f"- stop-order validity: `{FWM_ORDER_VALID_BARS}` bars")
    lines.append("- long FWM candidate: lowest low in lookback, close in upper half, low below Alligator cluster, lips flattening/up")
    lines.append("- short FWM candidate: highest high in lookback, close in lower half, high above Alligator cluster, lips flattening/down")
    lines.append("- no AO, no fractal breakout lane, no pyramiding, no Williams trailing exits")
    lines.append("")
    lines.append("## Portfolio Comparison")
    lines.append("")
    lines.append("| Mode | Trades Taken | Win Rate | PF | Ending Balance | Net PnL | Return | Max DD | Avg Hold | Skipped by Caps |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for mode_name, mode_result in result["modes"].items():
        summary = mode_result["portfolio_summary"]
        skipped = (
            int(summary["trades_skipped_asset_cap"])
            + int(summary["trades_skipped_portfolio_cap"])
            + int(summary["trades_skipped_overall_brake"])
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    mode_name,
                    str(summary["trades_taken"]),
                    format_pct(summary["win_rate"]),
                    str(summary["profit_factor"]),
                    format_currency(summary["ending_balance"]),
                    format_currency(summary["net_pnl_dollars"]),
                    format_pct(summary["return_pct"]),
                    format_currency(summary["max_drawdown_dollars"]),
                    f"{float(summary['average_hold_minutes']):.2f}m",
                    str(skipped),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    baseline = result["modes"]["baseline"]["portfolio_summary"]
    lines.append(
        f"Baseline reference on the 8-symbol shortlist finished at {format_currency(baseline['ending_balance'])}, "
        f"{format_pct(baseline['return_pct'])} return, PF `{baseline['profit_factor']}`, and "
        f"max drawdown {format_currency(baseline['max_drawdown_dollars'])}."
    )
    lines.append("")
    for verdict in result["verdicts"]:
        lines.append(f"### {verdict['mode']}")
        lines.append("")
        lines.append(f"- verdict: `{verdict['verdict']}`")
        comparison = verdict["comparison"]
        lines.append(
            f"- PF `{comparison['baseline_profit_factor']}` -> `{comparison['candidate_profit_factor']}`"
        )
        lines.append(
            f"- return `{comparison['baseline_return_pct']}%` -> `{comparison['candidate_return_pct']}%`"
        )
        lines.append(
            f"- max DD `{comparison['baseline_max_drawdown_dollars']}` -> `{comparison['candidate_max_drawdown_dollars']}`"
        )
        lines.append(
            f"- trades `{comparison['baseline_trades_taken']}` -> `{comparison['candidate_trades_taken']}`"
        )
        lines.append(
            f"- improving symbols: `{comparison['improved_symbols']}` / `{len(SHORTLIST)}`"
        )
        failed_checks = [name for name, ok in verdict["checks"].items() if not ok]
        if failed_checks:
            lines.append(f"- why it failed: `{', '.join(failed_checks)}`")
        else:
            lines.append("- why it passed: all phase-1 acceptance checks cleared")
        lines.append("")

    lines.append("## Scenario Mix")
    lines.append("")
    for mode_name, mode_result in result["modes"].items():
        raw = mode_result["raw_trade_summary"]
        funded = mode_result["portfolio_summary"]
        lines.append(f"### {mode_name}")
        lines.append("")
        lines.append(f"- raw scenario mix: `{raw['scenario_mix']}`")
        lines.append(f"- funded scenario mix: `{funded['scenario_mix']}`")
        lines.append(f"- funded source mix: `{funded['source_mix']}`")
        lines.append("")

    lines.append("## Per-Symbol Contribution")
    lines.append("")
    for mode_name, mode_result in result["modes"].items():
        lines.append(f"### {mode_name}")
        lines.append("")
        lines.append("| Symbol | Timeframe | Net PnL | Win Rate | Trades Taken |")
        lines.append("|---|---|---:|---:|---:|")
        per_symbol = mode_result["per_symbol_summary"]
        for symbol in SHORTLIST:
            stats = per_symbol[symbol]
            lines.append(
                f"| `{symbol}` | `{result['timeframes'][symbol]}` | {format_currency(stats['net_pnl_dollars'])} | "
                f"{format_pct(stats['win_rate'])} | {int(stats['taken'])} |"
            )
        lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    kept_modes = [verdict["mode"] for verdict in result["verdicts"] if verdict["verdict"] == "keep"]
    if kept_modes:
        lines.append(
            f"Phase 1 found a viable FWM hybrid path in: `{', '.join(kept_modes)}`. "
            "Only after that should phase 2 even consider fractal confirmation."
        )
    else:
        lines.append(
            "Phase 1 did not produce a clear upgrade over current CWT on the locked benchmark. "
            "Recommendation: keep current CWT unchanged and do not proceed to AO / full Three Wise Men stacking yet."
        )
    lines.append("")
    return "\n".join(lines)


def build_next_steps_report(result: dict[str, object], selective_symbols: list[str]) -> str:
    lines: list[str] = []
    lines.append("# CWT FWM Hybrid Next Steps")
    lines.append("")
    lines.append("## Locked Decisions")
    lines.append("")
    lines.append("- Discard `FWM Gate`.")
    lines.append("- Keep `FWM Entry Lane` as the only Bill Williams hybrid candidate worth carrying forward.")
    lines.append("- Do not touch live `strategy_four` yet.")
    lines.append("- Treat the next step as a narrower research profile, not a live rollout.")
    lines.append("")
    lines.append("## First-Pass Symbol Read")
    lines.append("")
    lines.append("| Symbol | Baseline Net PnL | FWM Entry Lane Net PnL | Delta | Decision |")
    lines.append("|---|---:|---:|---:|---|")
    baseline_symbols = result["modes"]["baseline"]["per_symbol_summary"]
    entry_symbols = result["modes"]["fwm_entry_lane"]["per_symbol_summary"]
    for symbol in SHORTLIST:
        base_pnl = float(baseline_symbols[symbol]["net_pnl_dollars"])
        entry_pnl = float(entry_symbols[symbol]["net_pnl_dollars"])
        delta = entry_pnl - base_pnl
        decision = "Enable FWM lane" if symbol in selective_symbols else "Keep baseline only"
        lines.append(
            f"| `{symbol}` | {format_currency(base_pnl)} | {format_currency(entry_pnl)} | "
            f"{format_currency(delta)} | {decision} |"
        )
    lines.append("")
    lines.append("## Applied Step")
    lines.append("")
    lines.append("I applied the next research step immediately by building a `fwm_selective` mode:")
    lines.append("")
    for symbol in selective_symbols:
        lines.append(f"- `FWM enabled`: `{symbol}`")
    for symbol in SHORTLIST:
        if symbol not in selective_symbols:
            lines.append(f"- `Baseline only`: `{symbol}`")
    lines.append("")
    selective = result["modes"]["fwm_selective"]["portfolio_summary"]
    baseline = result["modes"]["baseline"]["portfolio_summary"]
    lines.append("## Selective Mode Result")
    lines.append("")
    lines.append("| Mode | Ending Balance | Net PnL | Return | PF | Max DD | Trades Taken |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    lines.append(
        f"| baseline | {format_currency(baseline['ending_balance'])} | {format_currency(baseline['net_pnl_dollars'])} | "
        f"{format_pct(baseline['return_pct'])} | {baseline['profit_factor']} | {format_currency(baseline['max_drawdown_dollars'])} | {baseline['trades_taken']} |"
    )
    lines.append(
        f"| fwm_selective | {format_currency(selective['ending_balance'])} | {format_currency(selective['net_pnl_dollars'])} | "
        f"{format_pct(selective['return_pct'])} | {selective['profit_factor']} | {format_currency(selective['max_drawdown_dollars'])} | {selective['trades_taken']} |"
    )
    lines.append("")
    lines.append("## Recommended Sequence")
    lines.append("")
    lines.append("1. Keep current live CWT unchanged.")
    lines.append("2. Treat `fwm_selective` as the new research benchmark challenger, not `fwm_gate`.")
    lines.append("3. Run a second-pass sensitivity study on `fwm_selective` only:")
    lines.append("   - `FWM swing lookback`: test `6 / 8 / 10`")
    lines.append("   - `FWM order validity`: test `1 / 2 / 3` bars")
    lines.append("   - `FWM gate window`: do not advance unless needed later")
    lines.append("4. Only if `fwm_selective` stays stronger after sensitivity testing should phase 2 consider fractal confirmation.")
    lines.append("5. Keep AO / Second Wise Man / pyramiding out until after that.")
    lines.append("")
    lines.append("## Practical Recommendation")
    lines.append("")
    lines.append(
        "The clean next research lane is not a global Bill Williams conversion. "
        "It is a selective hybrid: baseline CWT everywhere, with FWM entry-lane enabled only on the six symbols that improved."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    load_dotenv(".env")
    ensure_dir(OUTPUT_DIR)

    frames: dict[str, pd.DataFrame] = {}
    timeframes: dict[str, str] = {}
    for symbol in SHORTLIST:
        timeframe = minimum_timeframe_for(symbol)
        timeframes[symbol] = timeframe
        frames[symbol] = load_symbol_frame(symbol, timeframe)

    mode_results: dict[str, dict[str, object]] = {}
    for mode in ["baseline", "fwm_gate", "fwm_entry_lane"]:
        raw_trades: list[dict[str, object]] = []
        for symbol in SHORTLIST:
            raw_trades.extend(generate_trades_for_mode(symbol, timeframes[symbol], frames[symbol], mode))
        funded = replay_funded_portfolio(raw_trades)
        mode_results[mode] = summarize_mode(raw_trades, funded)

    selective_symbols = [
        symbol
        for symbol in SHORTLIST
        if float(mode_results["fwm_entry_lane"]["per_symbol_summary"][symbol]["net_pnl_dollars"])
        > float(mode_results["baseline"]["per_symbol_summary"][symbol]["net_pnl_dollars"])
    ]

    selective_raw_trades: list[dict[str, object]] = []
    for symbol in SHORTLIST:
        selective_raw_trades.extend(
            generate_trades_for_mode(
                symbol,
                timeframes[symbol],
                frames[symbol],
                "fwm_selective",
                selective_fwm_symbols=set(selective_symbols),
            )
        )
    mode_results["fwm_selective"] = summarize_mode(
        selective_raw_trades,
        replay_funded_portfolio(selective_raw_trades),
    )

    verdicts = [
        evaluate_verdict("fwm_gate", mode_results["baseline"], mode_results["fwm_gate"]),
        evaluate_verdict("fwm_entry_lane", mode_results["baseline"], mode_results["fwm_entry_lane"]),
        evaluate_verdict("fwm_selective", mode_results["baseline"], mode_results["fwm_selective"]),
    ]

    result = {
        "config": {
            "start": START,
            "end": END,
            "shortlist": SHORTLIST,
            "timeframes": timeframes,
            "risk_ladder_pct": RISK_LADDER,
            "asset_daily_cap_dollars": ASSET_DAILY_CAP_DOLLARS,
            "portfolio_daily_cap_dollars": PORTFOLIO_DAILY_CAP_DOLLARS,
            "overall_brake_equity": OVERALL_BRAKE_EQUITY,
            "fwm_swing_lookback_bars": FWM_SWING_LOOKBACK_BARS,
            "fwm_gate_lookback_bars": FWM_GATE_LOOKBACK_BARS,
            "fwm_order_valid_bars": FWM_ORDER_VALID_BARS,
        },
        "timeframes": timeframes,
        "selective_fwm_symbols": selective_symbols,
        "modes": mode_results,
        "verdicts": verdicts,
    }

    OUTPUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown_report(result), encoding="utf-8")
    NEXT_STEPS_MD.write_text(build_next_steps_report(result, selective_symbols), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
