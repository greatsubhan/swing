"""Find historical analogs for the current Secular Bull SIP regime."""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from little_rzy_bot.market_data import fetch_oanda_ohlcv
from research.secular_bull_sip_baseline import _fmt_money, _fmt_pct, _load_env


START_DATE = "2020-01-01"
END_DATE = "2026-04-01"
WINDOW_MONTHS = 12
MONTHLY_CONTRIBUTION = 100_000.0 / 12.0
OUTPUT_DIR = Path("reports/secular_bull_sip")
OUTPUT_JSON = OUTPUT_DIR / "regime_analogs.json"
OUTPUT_MD = OUTPUT_DIR / "REGIME_ANALOGS.md"
MANUAL_ANALOGS = [
    {
        "label": "US-Iran crisis / early 2020 geopolitical shock",
        "match_start": "2020-01-31 22:00:00+00:00",
        "match_end": "2020-12-31 22:00:00+00:00",
        "follow_start": "2021-01-31 22:00:00+00:00",
        "follow_end": "2021-12-31 22:00:00+00:00",
    }
]

ASSETS: dict[str, str] = {
    "XAU_USD": "Gold",
    "NAS100_USD": "Nasdaq 100",
    "US30_USD": "Dow Jones 30",
    "BTC_USD": "Bitcoin",
    "ETH_USD": "Ethereum",
}


@dataclass
class WindowResult:
    period_start: str
    period_end: str
    months: int
    total_contributed: float
    ending_value: float
    net_pnl: float
    max_drawdown_pct: float


def _fetch_monthly(symbol: str) -> pd.DataFrame:
    fetched = fetch_oanda_ohlcv(
        instrument=symbol,
        granularity="M",
        start=START_DATE,
        end=END_DATE,
        environment=os.getenv("OANDA_ENV", "practice"),
    )
    df = fetched.df.copy().sort_index()
    frame = pd.DataFrame(index=df.index)
    frame["open"] = df["open"].astype(float)
    frame["close"] = df["close"].astype(float)
    frame["ret"] = frame["close"].pct_change()
    return frame


def _common_index(monthly_data: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    common = None
    for frame in monthly_data.values():
        idx = frame.index
        common = idx if common is None else common.intersection(idx)
    if common is None:
        raise RuntimeError("No common monthly index found.")
    return common.sort_values()


def _feature_vector(monthly_data: dict[str, pd.DataFrame], index_slice: pd.DatetimeIndex) -> list[float]:
    values: list[float] = []
    for symbol in ASSETS:
        series = monthly_data[symbol].loc[index_slice, "ret"].fillna(0.0)
        values.extend(float(v) for v in series.tolist())
    return values


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _simulate_window(monthly_data: dict[str, pd.DataFrame], index_slice: pd.DatetimeIndex) -> dict[str, WindowResult]:
    results: dict[str, WindowResult] = {}
    for symbol, label in ASSETS.items():
        frame = monthly_data[symbol].loc[index_slice]
        units = 0.0
        total_contributed = 0.0
        peak_value = 0.0
        max_dd_pct = 0.0
        ending_value = 0.0
        for _, row in frame.iterrows():
            units += MONTHLY_CONTRIBUTION / float(row["open"])
            total_contributed += MONTHLY_CONTRIBUTION
            ending_value = units * float(row["close"])
            peak_value = max(peak_value, ending_value)
            dd_pct = (peak_value - ending_value) / peak_value if peak_value > 0 else 0.0
            max_dd_pct = max(max_dd_pct, dd_pct)
        results[symbol] = WindowResult(
            period_start=str(index_slice[0]),
            period_end=str(index_slice[-1]),
            months=len(index_slice),
            total_contributed=round(total_contributed, 2),
            ending_value=round(ending_value, 2),
            net_pnl=round(ending_value - total_contributed, 2),
            max_drawdown_pct=round(max_dd_pct, 4),
        )
    return results


def _basket_summary(window_results: dict[str, WindowResult]) -> dict[str, float]:
    items = list(window_results.values())
    return {
        "mean_ending_value": round(sum(item.ending_value for item in items) / len(items), 2),
        "mean_net_pnl": round(sum(item.net_pnl for item in items) / len(items), 2),
        "mean_max_drawdown_pct": round(sum(item.max_drawdown_pct for item in items) / len(items), 4),
    }


def _pick_analog_windows(index: pd.DatetimeIndex, monthly_data: dict[str, pd.DataFrame]) -> dict[str, object]:
    current_slice = index[-WINDOW_MONTHS:]
    current_vector = _feature_vector(monthly_data, current_slice)

    candidates: list[dict[str, object]] = []
    max_start = len(index) - (2 * WINDOW_MONTHS)
    for start in range(1, max_start + 1):
        candidate_slice = index[start : start + WINDOW_MONTHS]
        if len(candidate_slice) < WINDOW_MONTHS:
            continue
        following_slice = index[start + WINDOW_MONTHS : start + (2 * WINDOW_MONTHS)]
        if len(following_slice) < WINDOW_MONTHS:
            continue
        vector = _feature_vector(monthly_data, candidate_slice)
        candidates.append(
            {
                "distance": round(_distance(current_vector, vector), 6),
                "candidate_slice": candidate_slice,
                "following_slice": following_slice,
            }
        )

    candidates.sort(key=lambda item: float(item["distance"]))
    selected: list[dict[str, object]] = []
    used_ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for item in candidates:
        start_ts = item["candidate_slice"][0]
        end_ts = item["candidate_slice"][-1]
        overlaps = any(not (end_ts < used_start or start_ts > used_end) for used_start, used_end in used_ranges)
        if overlaps:
            continue
        selected.append(item)
        used_ranges.append((start_ts, end_ts))
        if len(selected) == 2:
            break

    return {
        "current_slice": current_slice,
        "selected": selected,
    }


def _slice_from_bounds(index: pd.DatetimeIndex, start: str, end: str) -> pd.DatetimeIndex:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    selected = index[(index >= start_ts) & (index <= end_ts)]
    if selected.empty:
        raise RuntimeError(f"No data between {start} and {end}")
    return selected


def write_markdown(payload: dict[str, object]) -> None:
    lines: list[str] = []
    lines.append("# Secular Bull SIP Regime Analogs")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("- Regime definition: last 12 completed monthly bars across the core Secular Bull assets.")
    lines.append("- Similarity method: Euclidean distance across concatenated monthly return vectors for Gold, Nasdaq, Dow, Bitcoin, and Ethereum.")
    lines.append("- Analogs selected: the two closest non-overlapping historical 12-month windows with a full following 12-month window available.")
    lines.append("- SIP model inside each window: long-only, no leverage, no stop, monthly contribution `$8,333.33` per asset.")
    lines.append("")
    current = payload["current_regime"]
    lines.append("## Current Regime")
    lines.append("")
    lines.append(f"- Current comparison window: `{current['start']}` to `{current['end']}`")
    lines.append(f"- Basket mean ending value over that 12-month SIP slice: `${_fmt_money(current['summary']['mean_ending_value'])}`")
    lines.append(f"- Basket mean net PnL: `${_fmt_money(current['summary']['mean_net_pnl'])}`")
    lines.append(f"- Basket mean max drawdown: `{_fmt_pct(current['summary']['mean_max_drawdown_pct'])}`")
    lines.append("")
    for analog in payload["analogs"]:
        lines.append(f"## Analog {analog['rank']}")
        lines.append("")
        if analog.get("label"):
            lines.append(f"- Label: `{analog['label']}`")
        if analog.get("distance") is not None:
            lines.append(f"- Similarity distance: `{analog['distance']}`")
        lines.append(f"- Matching window: `{analog['match_start']}` to `{analog['match_end']}`")
        lines.append(f"- Following window: `{analog['follow_start']}` to `{analog['follow_end']}`")
        lines.append("")
        lines.append("### Matching Window")
        lines.append("")
        lines.append("| Asset | Ending Value $ | Net PnL $ | Max DD % |")
        lines.append("|---|---:|---:|---:|")
        for symbol, result in analog["match_results"].items():
            lines.append(
                f"| `{symbol}` | {_fmt_money(result['ending_value'])} | {_fmt_money(result['net_pnl'])} | {_fmt_pct(result['max_drawdown_pct'])} |"
            )
        lines.append("")
        lines.append(
            f"- Basket mean net PnL: `${_fmt_money(analog['match_summary']['mean_net_pnl'])}` "
            f"with mean max DD `{_fmt_pct(analog['match_summary']['mean_max_drawdown_pct'])}`"
        )
        lines.append("")
        lines.append("### Following 12 Months")
        lines.append("")
        lines.append("| Asset | Ending Value $ | Net PnL $ | Max DD % |")
        lines.append("|---|---:|---:|---:|")
        for symbol, result in analog["follow_results"].items():
            lines.append(
                f"| `{symbol}` | {_fmt_money(result['ending_value'])} | {_fmt_money(result['net_pnl'])} | {_fmt_pct(result['max_drawdown_pct'])} |"
            )
        lines.append("")
        lines.append(
            f"- Basket mean net PnL: `${_fmt_money(analog['follow_summary']['mean_net_pnl'])}` "
            f"with mean max DD `{_fmt_pct(analog['follow_summary']['mean_max_drawdown_pct'])}`"
        )
        lines.append("")
    lines.append("## Read")
    lines.append("")
    lines.append("- Pure monthly SIP should be judged by how well it survives messy windows without requiring timing skill.")
    lines.append("- If the analog matching windows and the following windows remain broadly positive on the core assets, that supports staying systematic during noisy periods.")
    lines.append("- If leveraged versions are tested later, these same analog windows will be the right place to stress-test them.")
    OUTPUT_MD.write_text("\n".join(lines))


def main() -> None:
    _load_env(Path(".env"))
    monthly_data = {symbol: _fetch_monthly(symbol) for symbol in ASSETS}
    common_index = _common_index(monthly_data)
    analog_info = _pick_analog_windows(common_index, monthly_data)

    current_slice = analog_info["current_slice"]
    current_results = _simulate_window(monthly_data, current_slice)
    payload: dict[str, object] = {
        "config": {
            "date_range": {"start": START_DATE, "end": END_DATE},
            "window_months": WINDOW_MONTHS,
            "monthly_contribution": MONTHLY_CONTRIBUTION,
        },
        "current_regime": {
            "start": str(current_slice[0]),
            "end": str(current_slice[-1]),
            "results": {symbol: asdict(result) for symbol, result in current_results.items()},
            "summary": _basket_summary(current_results),
        },
        "analogs": [],
    }

    for rank, item in enumerate(analog_info["selected"], start=1):
        match_slice = item["candidate_slice"]
        follow_slice = item["following_slice"]
        match_results = _simulate_window(monthly_data, match_slice)
        follow_results = _simulate_window(monthly_data, follow_slice)
        payload["analogs"].append(
            {
                "rank": rank,
                "label": None,
                "distance": item["distance"],
                "match_start": str(match_slice[0]),
                "match_end": str(match_slice[-1]),
                "follow_start": str(follow_slice[0]),
                "follow_end": str(follow_slice[-1]),
                "match_results": {symbol: asdict(result) for symbol, result in match_results.items()},
                "follow_results": {symbol: asdict(result) for symbol, result in follow_results.items()},
                "match_summary": _basket_summary(match_results),
                "follow_summary": _basket_summary(follow_results),
            }
        )

    next_rank = len(payload["analogs"]) + 1
    for manual in MANUAL_ANALOGS:
        match_slice = _slice_from_bounds(common_index, manual["match_start"], manual["match_end"])
        follow_slice = _slice_from_bounds(common_index, manual["follow_start"], manual["follow_end"])
        match_results = _simulate_window(monthly_data, match_slice)
        follow_results = _simulate_window(monthly_data, follow_slice)
        payload["analogs"].append(
            {
                "rank": next_rank,
                "label": manual["label"],
                "distance": None,
                "match_start": str(match_slice[0]),
                "match_end": str(match_slice[-1]),
                "follow_start": str(follow_slice[0]),
                "follow_end": str(follow_slice[-1]),
                "match_results": {symbol: asdict(result) for symbol, result in match_results.items()},
                "follow_results": {symbol: asdict(result) for symbol, result in follow_results.items()},
                "match_summary": _basket_summary(match_results),
                "follow_summary": _basket_summary(follow_results),
            }
        )
        next_rank += 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2))
    write_markdown(payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
