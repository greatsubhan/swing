"""Funded-account SIP stress test using static prop-firm guardrails."""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
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
STARTING_EQUITY = 100_000.0
MONTHLY_BUDGET = STARTING_EQUITY / 12.0
DAILY_FLOOR = 95_000.0
OVERALL_FLOOR = 90_000.0
LEVERAGES = (1.0, 2.0, 3.0)
STOP_PCTS = (0.10, 0.15, 0.20)
REPORT_DIR = Path("reports/secular_bull_sip")
JSON_PATH = REPORT_DIR / "funded_static_sip.json"
MD_PATH = REPORT_DIR / "FUNDED_STATIC_SIP.md"
CONFIG_PATH = Path("config/cwt_market_constraints.json")

FOCUS_SYMBOLS = ["XAU_USD", "XAG_USD", "NAS100_USD", "US30_USD", "BTC_USD"]

GROUP_LABELS = {
    "major_fx": "Major FX",
    "commodity_fx": "Commodity FX",
    "minor_cross_fx": "Minor & Cross FX",
    "indices": "Indices",
    "commodities": "Commodities",
    "crypto": "Crypto",
}

INDEX_CANONICAL = {
    "US500": "SPX500_USD",
    "SPX": "SPX500_USD",
    "SPX500_USD": "SPX500_USD",
    "US30": "US30_USD",
    "DJIA": "US30_USD",
    "US30_USD": "US30_USD",
    "US100": "NAS100_USD",
    "NDX": "NAS100_USD",
    "USTEC": "NAS100_USD",
    "NAS100_USD": "NAS100_USD",
    "UK100": "UK100_GBP",
    "FTSE": "UK100_GBP",
    "UK100_GBP": "UK100_GBP",
    "FR40": "FR40_EUR",
    "CAC": "FR40_EUR",
    "FR40_EUR": "FR40_EUR",
    "JP225": "JP225_USD",
    "NI225": "JP225_USD",
    "JP225_USD": "JP225_USD",
}

COMMODITY_CANONICAL = {
    "USOIL": "WTICO_USD",
    "WTICO_USD": "WTICO_USD",
    "UKOIL": "BCO_USD",
    "BCO_USD": "BCO_USD",
    "XAU_USD": "XAU_USD",
    "XAG_USD": "XAG_USD",
    "NATGAS": "NATGAS",
    "COPPER": "COPPER",
    "PLATINUM": "PLATINUM",
    "PALLADIUM": "PALLADIUM",
}

SYMBOL_LABELS = {
    "XAU_USD": "Gold",
    "XAG_USD": "Silver",
    "WTICO_USD": "WTI Crude",
    "BCO_USD": "Brent Crude",
    "SPX500_USD": "S&P 500",
    "US30_USD": "Dow Jones 30",
    "NAS100_USD": "Nasdaq 100",
    "UK100_GBP": "FTSE 100",
    "FR40_EUR": "France 40",
    "JP225_USD": "Nikkei 225",
    "BTC_USD": "Bitcoin",
}


@dataclass
class Tranche:
    entry_time: str
    entry_price: float
    stop_price: float
    units: float
    active: bool = True
    realized_pnl: float = 0.0
    stop_hit_time: str | None = None


@dataclass
class FundedSipResult:
    symbol: str
    label: str
    batch: str
    leverage: float
    stop_pct: float
    size_multiplier: float
    effective_monthly_notional: float
    months: int
    ending_equity: float
    net_pnl: float
    return_pct: float
    cagr: float | None
    max_drawdown_dollars: float
    max_drawdown_pct: float
    max_daily_loss_dollars: float
    stop_hit_count: int
    worst_12m_pnl: float | None
    worst_12m_start: str | None
    worst_12m_end: str | None
    breach: bool
    breach_reason: str | None
    breach_time: str | None
    verdict: str


def canonical_symbol(group_id: str, symbol: str) -> str:
    if group_id == "indices":
        return INDEX_CANONICAL.get(symbol, symbol)
    if group_id == "commodities":
        return COMMODITY_CANONICAL.get(symbol, symbol)
    return symbol


def load_group_symbols() -> dict[str, list[str]]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    groups: dict[str, list[str]] = {}
    for group in config["groups"]:
        group_id = group["group_id"]
        seen: set[str] = set()
        symbols: list[str] = []
        for raw_symbol in group["symbols"]:
            symbol = canonical_symbol(group_id, raw_symbol)
            if symbol in seen:
                continue
            seen.add(symbol)
            symbols.append(symbol)
        groups[group_id] = symbols
    groups["crypto"] = ["BTC_USD"]
    return groups


def label_for_symbol(symbol: str) -> str:
    return SYMBOL_LABELS.get(symbol, symbol.replace("_", "/"))


def _fetch_daily(symbol: str) -> pd.DataFrame:
    fetched = fetch_oanda_ohlcv(
        instrument=symbol,
        granularity="D",
        start=START_DATE,
        end=END_DATE,
        environment=os.getenv("OANDA_ENV", "practice"),
    )
    return fetched.df.copy().sort_index()


def _monthly_entry_mask(df: pd.DataFrame) -> pd.Series:
    periods = df.index.to_period("M")
    shifted = pd.Series(periods, index=df.index).shift(1)
    return pd.Series(periods, index=df.index) != shifted


def _years_between(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return max((end - start).days / 365.25, 1e-9)


def _verdict(result: FundedSipResult) -> str:
    if result.net_pnl > 20_000 and result.size_multiplier >= 0.75:
        return "Keep"
    if result.net_pnl > 5_000 and result.size_multiplier >= 0.35:
        return "Caution"
    return "Reject"


def simulate_combo(
    symbol: str,
    label: str,
    batch: str,
    daily_df: pd.DataFrame,
    *,
    leverage: float,
    stop_pct: float,
    size_multiplier: float,
    stop_on_breach: bool,
) -> FundedSipResult:
    df = daily_df.copy()
    if df.empty:
        raise RuntimeError(f"No daily candles returned for {symbol}")

    entry_mask = _monthly_entry_mask(df)
    tranches: list[Tranche] = []
    realized_pnl = 0.0
    previous_close_equity = STARTING_EQUITY
    peak_equity = STARTING_EQUITY
    max_drawdown_dollars = 0.0
    max_drawdown_pct = 0.0
    max_daily_loss_dollars = 0.0
    stop_hit_count = 0
    breach = False
    breach_reason: str | None = None
    breach_time: str | None = None
    equity_history: list[tuple[pd.Timestamp, float]] = []

    for idx, (timestamp, row) in enumerate(df.iterrows()):
        if bool(entry_mask.iloc[idx]):
            entry_price = float(row["open"])
            notional = MONTHLY_BUDGET * leverage * size_multiplier
            units = notional / entry_price if entry_price > 0 else 0.0
            tranches.append(
                Tranche(
                    entry_time=str(timestamp),
                    entry_price=entry_price,
                    stop_price=entry_price * (1.0 - stop_pct),
                    units=units,
                )
            )

        low_price = float(row["low"])
        close_price = float(row["close"])

        active_intraday_pnl = 0.0
        active_close_pnl = 0.0
        for tranche in tranches:
            if not tranche.active:
                continue
            if low_price <= tranche.stop_price:
                pnl = tranche.units * (tranche.stop_price - tranche.entry_price)
                tranche.active = False
                tranche.realized_pnl = pnl
                tranche.stop_hit_time = str(timestamp)
                realized_pnl += pnl
                stop_hit_count += 1
            else:
                active_intraday_pnl += tranche.units * (low_price - tranche.entry_price)
                active_close_pnl += tranche.units * (close_price - tranche.entry_price)

        intraday_equity = STARTING_EQUITY + realized_pnl + active_intraday_pnl
        close_equity = STARTING_EQUITY + realized_pnl + active_close_pnl

        peak_equity = max(peak_equity, close_equity)
        drawdown_dollars = peak_equity - intraday_equity
        drawdown_pct = drawdown_dollars / peak_equity if peak_equity > 0 else 0.0
        max_drawdown_dollars = max(max_drawdown_dollars, drawdown_dollars)
        max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

        daily_loss = previous_close_equity - intraday_equity
        max_daily_loss_dollars = max(max_daily_loss_dollars, daily_loss)
        previous_close_equity = close_equity

        equity_history.append((timestamp, close_equity))

        if intraday_equity < OVERALL_FLOOR:
            breach = True
            breach_reason = "overall_floor"
            breach_time = str(timestamp)
            if stop_on_breach:
                break
        elif intraday_equity < DAILY_FLOOR:
            breach = True
            breach_reason = "daily_floor"
            breach_time = str(timestamp)
            if stop_on_breach:
                break

    ending_equity = equity_history[-1][1] if equity_history else STARTING_EQUITY
    start_ts = df.index[0]
    end_ts = equity_history[-1][0] if equity_history else df.index[-1]
    years = _years_between(start_ts, end_ts)
    cagr = (ending_equity / STARTING_EQUITY) ** (1.0 / years) - 1.0 if ending_equity > 0 else None

    monthly_equity: list[tuple[pd.Timestamp, float]] = []
    last_period = None
    for timestamp, equity in equity_history:
        period = timestamp.to_period("M")
        if last_period is None or period != last_period:
            last_period = period
        if monthly_equity and monthly_equity[-1][0].to_period("M") == period:
            monthly_equity[-1] = (timestamp, equity)
        else:
            monthly_equity.append((timestamp, equity))

    worst_12m_pnl: float | None = None
    worst_12m_start: str | None = None
    worst_12m_end: str | None = None
    if len(monthly_equity) >= 12:
        for end_idx in range(11, len(monthly_equity)):
            start_idx = end_idx - 11
            pnl = monthly_equity[end_idx][1] - monthly_equity[start_idx][1]
            if worst_12m_pnl is None or pnl < worst_12m_pnl:
                worst_12m_pnl = pnl
                worst_12m_start = str(monthly_equity[start_idx][0])
                worst_12m_end = str(monthly_equity[end_idx][0])

    result = FundedSipResult(
        symbol=symbol,
        label=label,
        batch=batch,
        leverage=leverage,
        stop_pct=stop_pct,
        size_multiplier=round(size_multiplier, 4),
        effective_monthly_notional=round(MONTHLY_BUDGET * leverage * size_multiplier, 2),
        months=sum(1 for _ in monthly_equity),
        ending_equity=round(ending_equity, 2),
        net_pnl=round(ending_equity - STARTING_EQUITY, 2),
        return_pct=round((ending_equity - STARTING_EQUITY) / STARTING_EQUITY, 4),
        cagr=round(cagr, 4) if cagr is not None else None,
        max_drawdown_dollars=round(max_drawdown_dollars, 2),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        max_daily_loss_dollars=round(max_daily_loss_dollars, 2),
        stop_hit_count=stop_hit_count,
        worst_12m_pnl=round(worst_12m_pnl, 2) if worst_12m_pnl is not None else None,
        worst_12m_start=worst_12m_start,
        worst_12m_end=worst_12m_end,
        breach=breach,
        breach_reason=breach_reason,
        breach_time=breach_time,
        verdict="",
    )
    result.verdict = _verdict(result)
    return result


def find_safe_size(
    symbol: str,
    label: str,
    batch: str,
    daily_df: pd.DataFrame,
    *,
    leverage: float,
    stop_pct: float,
) -> FundedSipResult:
    probe = simulate_combo(
        symbol,
        label,
        batch,
        daily_df,
        leverage=leverage,
        stop_pct=stop_pct,
        size_multiplier=1.0,
        stop_on_breach=True,
    )
    if not probe.breach:
        return probe

    lo = 0.0
    hi = 1.0
    for _ in range(20):
        mid = (lo + hi) / 2.0
        result = simulate_combo(
            symbol,
            label,
            batch,
            daily_df,
            leverage=leverage,
            stop_pct=stop_pct,
            size_multiplier=mid,
            stop_on_breach=True,
        )
        if result.breach:
            hi = mid
        else:
            lo = mid

    safe_scale = lo
    return simulate_combo(
        symbol,
        label,
        batch,
        daily_df,
        leverage=leverage,
        stop_pct=stop_pct,
        size_multiplier=safe_scale,
        stop_on_breach=False,
    )


def summarize_group(results: list[FundedSipResult]) -> dict[str, float]:
    count = len(results)
    positive = sum(1 for item in results if item.net_pnl > 0)
    keeps = sum(1 for item in results if item.verdict == "Keep")
    cautions = sum(1 for item in results if item.verdict == "Caution")
    return {
        "tested": count,
        "positive": positive,
        "keep": keeps,
        "caution": cautions,
        "mean_size_multiplier": round(sum(item.size_multiplier for item in results) / count, 4) if count else 0.0,
        "mean_net_pnl": round(sum(item.net_pnl for item in results) / count, 2) if count else 0.0,
        "mean_return_pct": round(sum(item.return_pct for item in results) / count, 4) if count else 0.0,
        "mean_max_dd_pct": round(sum(item.max_drawdown_pct for item in results) / count, 4) if count else 0.0,
    }


def write_markdown(
    focus_rows: list[FundedSipResult],
    best_rows: list[FundedSipResult],
    group_rows: dict[str, list[FundedSipResult]],
    unavailable: dict[str, list[str]],
) -> None:
    lines: list[str] = []
    lines.append("# Secular Bull SIP Under Static Funded Rules")
    lines.append("")
    lines.append("## Funded Rules Applied")
    lines.append("")
    lines.append(f"- Starting equity: `${STARTING_EQUITY:,.0f}`")
    lines.append(f"- Static daily floor: `${DAILY_FLOOR:,.0f}`")
    lines.append(f"- Static overall floor: `${OVERALL_FLOOR:,.0f}`")
    lines.append("- Monthly SIP entries still occur on the first trading day of each month.")
    lines.append("- New position size is automatically reduced with a `size multiplier` so the account survives the funded floors.")
    lines.append("- This is a funded-account simulation, not an external-capital contribution model.")
    lines.append("")
    lines.append("## Focus Assets")
    lines.append("")
    lines.append("| Symbol | Lev | Stop | Size Mult | Eff. Monthly Notional $ | Ending Equity $ | Net PnL $ | Return % | CAGR | Max DD $ | Max DD % | Max Daily Loss $ | Stop Hits | Worst 12M PnL $ | Verdict |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in sorted(focus_rows, key=lambda item: (item.symbol, item.leverage, item.stop_pct)):
        lines.append(
            f"| `{result.symbol}` | {result.leverage:.0f}x | {int(result.stop_pct * 100)}% | {result.size_multiplier:.2f} | "
            f"{_fmt_money(result.effective_monthly_notional)} | {_fmt_money(result.ending_equity)} | {_fmt_money(result.net_pnl)} | "
            f"{_fmt_pct(result.return_pct)} | {_fmt_pct(result.cagr)} | {_fmt_money(result.max_drawdown_dollars)} | "
            f"{_fmt_pct(result.max_drawdown_pct)} | {_fmt_money(result.max_daily_loss_dollars)} | {result.stop_hit_count} | "
            f"{_fmt_money(result.worst_12m_pnl) if result.worst_12m_pnl is not None else 'n/a'} | {result.verdict} |"
        )
    lines.append("")
    lines.append("## Best Funded-Safe Variant Per Asset")
    lines.append("")
    lines.append("| Symbol | Batch | Best Lev | Stop | Size Mult | Eff. Monthly Notional $ | Ending Equity $ | Net PnL $ | Return % | CAGR | Max DD $ | Max DD % | Max Daily Loss $ | Stop Hits | Verdict |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in sorted(best_rows, key=lambda item: item.net_pnl, reverse=True):
        lines.append(
            f"| `{result.symbol}` | {GROUP_LABELS.get(result.batch, result.batch)} | {result.leverage:.0f}x | {int(result.stop_pct * 100)}% | "
            f"{result.size_multiplier:.2f} | {_fmt_money(result.effective_monthly_notional)} | {_fmt_money(result.ending_equity)} | "
            f"{_fmt_money(result.net_pnl)} | {_fmt_pct(result.return_pct)} | {_fmt_pct(result.cagr)} | "
            f"{_fmt_money(result.max_drawdown_dollars)} | {_fmt_pct(result.max_drawdown_pct)} | {_fmt_money(result.max_daily_loss_dollars)} | "
            f"{result.stop_hit_count} | {result.verdict} |"
        )
    lines.append("")
    lines.append("## Batch Summary")
    lines.append("")
    lines.append("| Batch | Tested | Positive | Keep | Caution | Mean Size Mult | Mean Net PnL $ | Mean Return % | Mean Max DD % |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for group_id, rows in group_rows.items():
        summary = summarize_group(rows)
        lines.append(
            f"| {GROUP_LABELS.get(group_id, group_id)} | {summary['tested']} | {summary['positive']} | {summary['keep']} | {summary['caution']} | "
            f"{summary['mean_size_multiplier']:.2f} | {_fmt_money(summary['mean_net_pnl'])} | {_fmt_pct(summary['mean_return_pct'])} | "
            f"{_fmt_pct(summary['mean_max_dd_pct'])} |"
        )
    lines.append("")
    if any(unavailable.values()):
        lines.append("## Unavailable Symbols")
        lines.append("")
        for group_id, symbols in unavailable.items():
            if symbols:
                lines.append(f"- {GROUP_LABELS.get(group_id, group_id)}: {', '.join(f'`{s}`' for s in symbols)}")
        lines.append("")
    lines.append("## Read")
    lines.append("")
    lines.append("- `Size Mult` is the largest fraction of the lecture-style monthly position size that survived the funded floors over the full sample.")
    lines.append("- `Eff. Monthly Notional` is `account/12 * leverage * size multiplier`.")
    lines.append("- Higher net PnL is not enough on its own; if the safe size collapses too far, the asset is less practical for a funded SIP lane.")
    lines.append("- This pass is the prop-style risk layer only. It still does not add correction-entry timing.")
    MD_PATH.write_text("\n".join(lines))


def main() -> None:
    _load_env(Path(".env"))
    groups = load_group_symbols()
    all_results: list[FundedSipResult] = []
    best_per_symbol: dict[str, FundedSipResult] = {}
    group_best_rows: dict[str, list[FundedSipResult]] = defaultdict(list)
    unavailable: dict[str, list[str]] = defaultdict(list)
    payload: dict[str, Any] = {
        "config": {
            "date_range": {"start": START_DATE, "end": END_DATE},
            "starting_equity": STARTING_EQUITY,
            "daily_floor": DAILY_FLOOR,
            "overall_floor": OVERALL_FLOOR,
            "monthly_budget_reference": MONTHLY_BUDGET,
            "leverages": list(LEVERAGES),
            "stop_pcts": list(STOP_PCTS),
        },
        "results": [],
        "best_per_symbol": {},
        "unavailable": {},
    }

    for group_id, symbols in groups.items():
        for symbol in symbols:
            label = label_for_symbol(symbol)
            try:
                daily_df = _fetch_daily(symbol)
            except Exception:
                unavailable[group_id].append(symbol)
                continue
            symbol_rows: list[FundedSipResult] = []
            for leverage in LEVERAGES:
                for stop_pct in STOP_PCTS:
                    result = find_safe_size(
                        symbol,
                        label,
                        group_id,
                        daily_df,
                        leverage=leverage,
                        stop_pct=stop_pct,
                    )
                    symbol_rows.append(result)
                    all_results.append(result)
                    payload["results"].append(asdict(result))
            best = max(
                symbol_rows,
                key=lambda item: (
                    {"Keep": 2, "Caution": 1, "Reject": 0}[item.verdict],
                    item.net_pnl,
                    item.size_multiplier,
                ),
            )
            best_per_symbol[symbol] = best
            group_best_rows[group_id].append(best)

        payload["unavailable"][group_id] = unavailable[group_id]

    payload["best_per_symbol"] = {symbol: asdict(result) for symbol, result in best_per_symbol.items()}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(payload, indent=2))

    focus_rows = [result for result in all_results if result.symbol in FOCUS_SYMBOLS]
    best_rows = list(best_per_symbol.values())
    write_markdown(focus_rows, best_rows, group_best_rows, unavailable)
    print(
        json.dumps(
            {
                "results_written": len(all_results),
                "best_assets_written": len(best_rows),
                "report": str(MD_PATH),
                "json": str(JSON_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
