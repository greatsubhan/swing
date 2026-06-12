"""Leveraged monthly SIP stress test for the Secular Bull strategy."""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from little_rzy_bot.market_data import fetch_oanda_ohlcv
from research.secular_bull_sip_baseline import _fmt_money, _fmt_pct, _load_env


START_DATE = "2020-01-01"
END_DATE = "2026-04-01"
STARTING_CAPITAL = 100_000.0
MONTHLY_CONTRIBUTION = STARTING_CAPITAL / 12.0
LEVERAGES = (1.0, 2.0, 3.0)
STOP_PCTS = (0.10, 0.15, 0.20)
REPORT_DIR = Path("reports/secular_bull_sip")
JSON_PATH = REPORT_DIR / "leveraged_monthly_sip.json"
MD_PATH = REPORT_DIR / "LEVERAGED_MONTHLY_SIP.md"
ANALOG_JSON = REPORT_DIR / "regime_analogs.json"

ASSETS: dict[str, str] = {
    "XAU_USD": "Gold",
    "NAS100_USD": "Nasdaq 100",
    "US30_USD": "Dow Jones 30",
    "BTC_USD": "Bitcoin",
    "ETH_USD": "Ethereum",
}


@dataclass
class Tranche:
    entry_time: str
    entry_price: float
    stop_price: float | None
    units: float
    contribution: float
    leverage: float
    active: bool = True
    stop_hit_time: str | None = None
    stop_value: float | None = None
    current_value: float = 0.0


@dataclass
class LeveragedSipResult:
    symbol: str
    label: str
    window_name: str
    start_bar: str
    end_bar: str
    months: int
    leverage: float
    stop_pct: float | None
    total_contributed: float
    ending_value: float
    net_pnl: float
    moic: float
    annualized_return: float | None
    xirr: float | None
    max_drawdown_dollars: float
    max_drawdown_pct: float
    positive_month_pct: float
    best_month_return: float
    worst_month_return: float
    worst_12m_net_pnl: float | None
    worst_12m_start: str | None
    worst_12m_end: str | None
    stop_hit_count: int
    capital_efficiency: float


def _xnpv(rate: float, cashflows: list[tuple[float, float]]) -> float:
    total = 0.0
    for years_from_start, amount in cashflows:
        total += amount / ((1.0 + rate) ** years_from_start)
    return total


def _xirr(cashflows: list[tuple[float, float]]) -> float | None:
    has_negative = any(amount < 0 for _, amount in cashflows)
    has_positive = any(amount > 0 for _, amount in cashflows)
    if not (has_negative and has_positive):
        return None

    low = -0.9999
    high = 10.0
    low_npv = _xnpv(low, cashflows)
    high_npv = _xnpv(high, cashflows)

    while low_npv * high_npv > 0 and high < 1_000:
        high *= 2.0
        high_npv = _xnpv(high, cashflows)

    if low_npv * high_npv > 0:
        return None

    for _ in range(200):
        mid = (low + high) / 2.0
        mid_npv = _xnpv(mid, cashflows)
        if abs(mid_npv) < 1e-7:
            return mid
        if low_npv * mid_npv <= 0:
            high = mid
            high_npv = mid_npv
        else:
            low = mid
            low_npv = mid_npv
    return (low + high) / 2.0


def _fetch_monthly(symbol: str) -> pd.DataFrame:
    fetched = fetch_oanda_ohlcv(
        instrument=symbol,
        granularity="M",
        start=START_DATE,
        end=END_DATE,
        environment=os.getenv("OANDA_ENV", "practice"),
    )
    return fetched.df.copy().sort_index()


def _slice_frame(df: pd.DataFrame, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    frame = df.copy()
    if start is not None:
        frame = frame[frame.index >= pd.Timestamp(start)]
    if end is not None:
        frame = frame[frame.index <= pd.Timestamp(end)]
    return frame


def simulate_window(
    symbol: str,
    label: str,
    monthly_df: pd.DataFrame,
    *,
    window_name: str,
    leverage: float,
    stop_pct: float | None,
    start: str | None = None,
    end: str | None = None,
) -> LeveragedSipResult:
    df = _slice_frame(monthly_df, start=start, end=end)
    if df.empty:
        raise RuntimeError(f"No monthly candles returned for {symbol} in window {window_name}")

    tranches: list[Tranche] = []
    monthly_returns: list[float] = []
    equity_history: list[tuple[pd.Timestamp, float]] = []
    contribution_history: list[tuple[pd.Timestamp, float]] = []
    total_contributed = 0.0
    peak_equity = 0.0
    max_drawdown_dollars = 0.0
    max_drawdown_pct = 0.0
    stop_hit_count = 0
    previous_equity = 0.0
    first_ts = df.index[0]
    cashflows: list[tuple[float, float]] = []

    for timestamp, row in df.iterrows():
        contribution = MONTHLY_CONTRIBUTION
        entry_price = float(row["open"])
        low_price = float(row["low"])
        close_price = float(row["close"])
        units = (contribution * leverage) / entry_price
        stop_price = entry_price * (1.0 - stop_pct) if stop_pct is not None else None
        tranche = Tranche(
            entry_time=str(timestamp),
            entry_price=entry_price,
            stop_price=stop_price,
            units=units,
            contribution=contribution,
            leverage=leverage,
        )
        tranches.append(tranche)
        total_contributed += contribution

        years_from_start = (timestamp - first_ts).days / 365.25
        cashflows.append((years_from_start, -contribution))

        for active_tranche in tranches:
            if active_tranche.active and active_tranche.stop_price is not None and low_price <= active_tranche.stop_price:
                stop_value = active_tranche.contribution + active_tranche.units * (
                    active_tranche.stop_price - active_tranche.entry_price
                )
                active_tranche.active = False
                active_tranche.stop_hit_time = str(timestamp)
                active_tranche.stop_value = stop_value
                active_tranche.current_value = stop_value
                stop_hit_count += 1
            elif active_tranche.active:
                active_tranche.current_value = active_tranche.contribution + active_tranche.units * (
                    close_price - active_tranche.entry_price
                )
            elif active_tranche.stop_value is not None:
                active_tranche.current_value = active_tranche.stop_value

        end_equity = sum(item.current_value for item in tranches)
        equity_before_move = previous_equity + contribution
        month_return = (end_equity / equity_before_move - 1.0) if equity_before_move > 0 else 0.0
        monthly_returns.append(month_return)
        equity_history.append((timestamp, end_equity))
        contribution_history.append((timestamp, total_contributed))

        peak_equity = max(peak_equity, end_equity)
        drawdown_dollars = peak_equity - end_equity
        drawdown_pct = drawdown_dollars / peak_equity if peak_equity > 0 else 0.0
        max_drawdown_dollars = max(max_drawdown_dollars, drawdown_dollars)
        max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)
        previous_equity = end_equity

    ending_value = previous_equity
    final_ts = df.index[-1]
    final_years = (final_ts - first_ts).days / 365.25
    cashflows.append((final_years, ending_value))

    total_growth = math.prod(1.0 + value for value in monthly_returns)
    annualized_return = total_growth ** (12.0 / len(monthly_returns)) - 1.0 if monthly_returns else None
    xirr = _xirr(cashflows)

    worst_12m_net_pnl: float | None = None
    worst_12m_start: str | None = None
    worst_12m_end: str | None = None
    if len(equity_history) >= 12:
        equity_snapshots = [(first_ts - pd.Timedelta(days=31), 0.0)] + equity_history
        contribution_snapshots = [(first_ts - pd.Timedelta(days=31), 0.0)] + contribution_history
        for end_idx in range(12, len(equity_snapshots)):
            start_idx = end_idx - 12
            pnl = (
                equity_snapshots[end_idx][1]
                - equity_snapshots[start_idx][1]
                - (contribution_snapshots[end_idx][1] - contribution_snapshots[start_idx][1])
            )
            if worst_12m_net_pnl is None or pnl < worst_12m_net_pnl:
                worst_12m_net_pnl = pnl
                worst_12m_start = str(equity_snapshots[start_idx + 1][0])
                worst_12m_end = str(equity_snapshots[end_idx][0])

    return LeveragedSipResult(
        symbol=symbol,
        label=label,
        window_name=window_name,
        start_bar=str(first_ts),
        end_bar=str(final_ts),
        months=len(df),
        leverage=leverage,
        stop_pct=stop_pct,
        total_contributed=round(total_contributed, 2),
        ending_value=round(ending_value, 2),
        net_pnl=round(ending_value - total_contributed, 2),
        moic=round(ending_value / total_contributed, 4),
        annualized_return=round(annualized_return, 4) if annualized_return is not None else None,
        xirr=round(xirr, 4) if xirr is not None else None,
        max_drawdown_dollars=round(max_drawdown_dollars, 2),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        positive_month_pct=round(sum(1 for value in monthly_returns if value > 0) / len(monthly_returns), 4),
        best_month_return=round(max(monthly_returns), 4),
        worst_month_return=round(min(monthly_returns), 4),
        worst_12m_net_pnl=round(worst_12m_net_pnl, 2) if worst_12m_net_pnl is not None else None,
        worst_12m_start=worst_12m_start,
        worst_12m_end=worst_12m_end,
        stop_hit_count=stop_hit_count,
        capital_efficiency=round((ending_value - total_contributed) / total_contributed, 4),
    )


def _load_windows() -> list[dict[str, str]]:
    if not ANALOG_JSON.exists():
        raise RuntimeError("Missing regime_analogs.json. Run the analogue study first.")
    payload = json.loads(ANALOG_JSON.read_text())
    windows = [
        {
            "name": "current_regime",
            "label": "Current Regime",
            "start": payload["current_regime"]["start"],
            "end": payload["current_regime"]["end"],
        }
    ]
    for analog in payload["analogs"]:
        windows.append(
            {
                "name": f"analog_{analog['rank']}",
                "label": f"Analog {analog['rank']}" if not analog.get("label") else f"Analog {analog['rank']} ({analog['label']})",
                "start": analog["match_start"],
                "end": analog["match_end"],
            }
        )
    return windows


def _verdict(full_sample: LeveragedSipResult, stress_results: list[LeveragedSipResult], baseline_result: LeveragedSipResult) -> str:
    positive_windows = sum(1 for result in stress_results if result.net_pnl > 0)
    worst_window_pnl = min(result.net_pnl for result in stress_results)
    worst_window_dd = max(result.max_drawdown_pct for result in stress_results)
    efficiency_delta = full_sample.capital_efficiency - baseline_result.capital_efficiency
    stop_hits_per_year = full_sample.stop_hit_count / max(full_sample.months / 12.0, 1e-9)

    if (
        efficiency_delta > 0.10
        and positive_windows >= 3
        and worst_window_pnl > -10_000
        and worst_window_dd <= 0.35
        and stop_hits_per_year <= 4.0
    ):
        return "Keep"
    if (
        efficiency_delta > 0.0
        and positive_windows >= 2
        and worst_window_dd <= 0.50
        and stop_hits_per_year <= 8.0
    ):
        return "Caution"
    return "Reject"


def _result_key(result: LeveragedSipResult) -> str:
    stop_text = "none" if result.stop_pct is None else f"{int(result.stop_pct * 100)}"
    return f"{result.symbol}|{result.window_name}|{result.leverage:.1f}|{stop_text}"


def _combo_key(symbol: str, window_name: str, leverage: float, stop_pct: float | None) -> str:
    stop_text = "none" if stop_pct is None else f"{int(stop_pct * 100)}"
    return f"{symbol}|{window_name}|{leverage:.1f}|{stop_text}"


def _comparison_row(
    full_sample: LeveragedSipResult,
    baseline_result: LeveragedSipResult,
    stress_results: list[LeveragedSipResult],
) -> dict[str, Any]:
    worst_stress_pnl = min(result.net_pnl for result in stress_results)
    worst_stress_dd = max(result.max_drawdown_pct for result in stress_results)
    return {
        "symbol": full_sample.symbol,
        "label": full_sample.label,
        "leverage": full_sample.leverage,
        "stop_pct": full_sample.stop_pct,
        "ending_value": full_sample.ending_value,
        "net_pnl": full_sample.net_pnl,
        "moic": full_sample.moic,
        "annualized_return": full_sample.annualized_return,
        "xirr": full_sample.xirr,
        "max_drawdown_dollars": full_sample.max_drawdown_dollars,
        "max_drawdown_pct": full_sample.max_drawdown_pct,
        "stop_hit_count": full_sample.stop_hit_count,
        "worst_12m_net_pnl": full_sample.worst_12m_net_pnl,
        "capital_efficiency": full_sample.capital_efficiency,
        "baseline_net_pnl": baseline_result.net_pnl,
        "baseline_xirr": baseline_result.xirr,
        "baseline_capital_efficiency": baseline_result.capital_efficiency,
        "capital_efficiency_delta": round(full_sample.capital_efficiency - baseline_result.capital_efficiency, 4),
        "capital_efficiency_ratio": round(
            full_sample.capital_efficiency / baseline_result.capital_efficiency, 4
        )
        if baseline_result.capital_efficiency not in (0.0, -0.0)
        else None,
        "stress_positive_windows": sum(1 for result in stress_results if result.net_pnl > 0),
        "worst_stress_net_pnl": worst_stress_pnl,
        "worst_stress_max_dd_pct": round(worst_stress_dd, 4),
        "verdict": _verdict(full_sample, stress_results, baseline_result),
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Secular Bull SIP Leveraged Monthly Stress Test")
    lines.append("")
    lines.append("## Test Setup")
    lines.append("")
    lines.append(f"- Date range: `{START_DATE}` to `{END_DATE}`")
    lines.append(f"- Starting capital reference: `${STARTING_CAPITAL:,.0f}`")
    lines.append(f"- Monthly contribution per asset test: `${MONTHLY_CONTRIBUTION:,.2f}`")
    lines.append("- Base model: long-only monthly accumulation with tranches held across future months.")
    lines.append("- Leveraged variants tested: `1x`, `2x`, `3x`")
    lines.append("- Protective stop variants tested: `10%`, `15%`, `20%` below each tranche entry.")
    lines.append("- One asset per simulation, no rotation, no correction filter.")
    lines.append("- Stress windows: current regime plus Analog 1, Analog 2, and Analog 3.")
    lines.append("")
    lines.append("## Full-Sample Comparison")
    lines.append("")
    lines.append("| Asset | Lev | Stop | Ending $ | Net PnL $ | MOIC | Ann. Return | XIRR | Max DD $ | Max DD % | Stop Hits | Worst 12M PnL $ | Baseline PnL $ | Cap Eff | Delta vs Base | Verdict |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in sorted(payload["full_sample_comparison"], key=lambda item: (item["verdict"], item["net_pnl"]), reverse=True):
        lines.append(
            f"| `{row['symbol']}` | {row['leverage']:.0f}x | {int(row['stop_pct'] * 100)}% | "
            f"{_fmt_money(row['ending_value'])} | {_fmt_money(row['net_pnl'])} | {row['moic']:.2f} | "
            f"{_fmt_pct(row['annualized_return'])} | {_fmt_pct(row['xirr'])} | "
            f"{_fmt_money(row['max_drawdown_dollars'])} | {_fmt_pct(row['max_drawdown_pct'])} | {row['stop_hit_count']} | "
            f"{_fmt_money(row['worst_12m_net_pnl']) if row['worst_12m_net_pnl'] is not None else 'n/a'} | "
            f"{_fmt_money(row['baseline_net_pnl'])} | {_fmt_pct(row['capital_efficiency'])} | "
            f"{_fmt_pct(row['capital_efficiency_delta'])} | {row['verdict']} |"
        )
    lines.append("")

    for window_name, window_payload in payload["stress_windows"].items():
        lines.append(f"## {window_payload['label']}")
        lines.append("")
        lines.append("| Asset | Lev | Stop | Net PnL $ | Max DD % | Stop Hits | Baseline PnL $ | Delta vs Base | Verdict |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for row in sorted(window_payload["comparison"], key=lambda item: item["net_pnl"], reverse=True):
            lines.append(
                f"| `{row['symbol']}` | {row['leverage']:.0f}x | {int(row['stop_pct'] * 100)}% | "
                f"{_fmt_money(row['net_pnl'])} | {_fmt_pct(row['max_drawdown_pct'])} | {row['stop_hit_count']} | "
                f"{_fmt_money(row['baseline_net_pnl'])} | {_fmt_pct(row['capital_efficiency_delta'])} | {row['verdict']} |"
            )
        lines.append("")

    lines.append("## Read")
    lines.append("")
    lines.append("- `Cap Eff` is net PnL divided by total contributed capital.")
    lines.append("- `Delta vs Base` is the leveraged capital-efficiency improvement over the unleveraged monthly SIP baseline on the same asset and window.")
    lines.append("- `Verdict` is skeptical by design: it only turns `Keep` when leverage improves capital efficiency and stays reasonably controlled across the stress windows.")
    lines.append("- This report intentionally stops before correction-entry SIP or any bot/product work.")
    MD_PATH.write_text("\n".join(lines))


def main() -> None:
    _load_env(Path(".env"))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    windows = _load_windows()
    monthly_data = {symbol: _fetch_monthly(symbol) for symbol in ASSETS}

    baseline_full_sample: dict[str, LeveragedSipResult] = {}
    full_sample_results: list[LeveragedSipResult] = []
    stress_results: dict[str, list[LeveragedSipResult]] = {window["name"]: [] for window in windows}
    baseline_stress: dict[str, dict[str, LeveragedSipResult]] = {window["name"]: {} for window in windows}

    for symbol, label in ASSETS.items():
        frame = monthly_data[symbol]
        baseline_full = simulate_window(
            symbol,
            label,
            frame,
            window_name="full_sample",
            leverage=1.0,
            stop_pct=None,
        )
        baseline_full_sample[symbol] = baseline_full

        for window in windows:
            baseline_stress[window["name"]][symbol] = simulate_window(
                symbol,
                label,
                frame,
                window_name=window["name"],
                leverage=1.0,
                stop_pct=None,
                start=window["start"],
                end=window["end"],
            )

        for leverage in LEVERAGES:
            for stop_pct in STOP_PCTS:
                result = simulate_window(
                    symbol,
                    label,
                    frame,
                    window_name="full_sample",
                    leverage=leverage,
                    stop_pct=stop_pct,
                )
                full_sample_results.append(result)
                for window in windows:
                    stress_results[window["name"]].append(
                        simulate_window(
                            symbol,
                            label,
                            frame,
                            window_name=window["name"],
                            leverage=leverage,
                            stop_pct=stop_pct,
                            start=window["start"],
                            end=window["end"],
                        )
                    )

    stress_lookup = {_result_key(result): result for results in stress_results.values() for result in results}
    full_sample_comparison: list[dict[str, Any]] = []
    for result in full_sample_results:
        matching_stress = [
            stress_lookup[_combo_key(result.symbol, window["name"], result.leverage, result.stop_pct)]
            for window in windows
        ]
        full_sample_comparison.append(_comparison_row(result, baseline_full_sample[result.symbol], matching_stress))

    stress_window_payloads: dict[str, Any] = {}
    for window in windows:
        comparison_rows: list[dict[str, Any]] = []
        for result in stress_results[window["name"]]:
            comparison_rows.append(
                _comparison_row(result, baseline_stress[window["name"]][result.symbol], [result])
            )
        stress_window_payloads[window["name"]] = {
            "label": window["label"],
            "start": window["start"],
            "end": window["end"],
            "comparison": comparison_rows,
        }

    payload = {
        "config": {
            "date_range": {"start": START_DATE, "end": END_DATE},
            "starting_capital_reference": STARTING_CAPITAL,
            "monthly_contribution": MONTHLY_CONTRIBUTION,
            "leverages": list(LEVERAGES),
            "stop_pcts": list(STOP_PCTS),
        },
        "baseline_reference": {
            "full_sample": {symbol: asdict(result) for symbol, result in baseline_full_sample.items()},
            "stress_windows": {
                window_name: {symbol: asdict(result) for symbol, result in results.items()}
                for window_name, results in baseline_stress.items()
            },
        },
        "full_sample_results": [asdict(result) for result in full_sample_results],
        "full_sample_comparison": full_sample_comparison,
        "stress_windows": stress_window_payloads,
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2))
    write_markdown(payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
