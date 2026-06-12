"""Monthly managed-events scanner for the Secular Bull SIP board."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from little_rzy_bot.market_data import fetch_oanda_ohlcv

from .watchlists import asset_class_for, watchlist_label

LOOKBACK_DAYS = 500
ACCOUNT_SIZE = 100000.0
MONTHLY_BUDGET = ACCOUNT_SIZE / 12.0
DEFAULT_PROFILE = "FTMO Swing style"
DEFAULT_PAYOUT_MODE = "Skim 50% of month-end profit above $100k"
REFERENCE_PROFILE_LABEL = "FTMO Swing"
REFERENCE_WITHDRAWAL_LABEL = "Skim 50% of month-end profit above $100k"
ALLOCATION_GRACE_DAYS = 7
REVIEW_GRACE_DAYS = 7
RESEARCH_REPORT = Path("reports/secular_bull_sip/SLEEVE_COMPARE_2Y.json")
STATE_FILE_NAME = "sip_state.json"


def _history_start() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()


def _state_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / STATE_FILE_NAME


def load_state(output_dir: str | Path) -> dict[str, object]:
    path = _state_path(output_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text() or "{}")


def save_state(output_dir: str | Path, state: dict[str, object]) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _state_path(output).write_text(json.dumps(state, indent=2))


def load_history(symbol: str, environment: str, token: str | None, price: str) -> pd.DataFrame:
    fetched = fetch_oanda_ohlcv(
        instrument=symbol,
        granularity="D",
        start=_history_start(),
        end=None,
        price=price,
        token=token,
        environment=environment,
    )
    return fetched.df.sort_index()


def _first_trading_day(df: pd.DataFrame, year: int, month: int) -> pd.Timestamp | None:
    period_rows = df[(df.index.year == year) & (df.index.month == month)]
    if period_rows.empty:
        return None
    return period_rows.index[0]


def _previous_month(anchor: pd.Timestamp) -> tuple[int, int]:
    if anchor.month == 1:
        return anchor.year - 1, 12
    return anchor.year, anchor.month - 1


def _monthly_return_stats(df: pd.DataFrame, year: int, month: int) -> dict[str, float | str] | None:
    rows = df[(df.index.year == year) & (df.index.month == month)]
    if rows.empty:
        return None
    first_row = rows.iloc[0]
    last_row = rows.iloc[-1]
    month_open = float(first_row["open"])
    month_close = float(last_row["close"])
    pct = ((month_close / month_open) - 1.0) * 100.0 if month_open else 0.0
    return {
        "month_open": month_open,
        "month_close": month_close,
        "month_return_pct": pct,
        "bars": int(len(rows)),
        "start": rows.index[0].isoformat(),
        "end": rows.index[-1].isoformat(),
    }


def _trend_snapshot(df: pd.DataFrame, anchor: pd.Timestamp) -> dict[str, object]:
    cutoff = df[df.index <= anchor]
    if cutoff.empty:
        return {
            "trend_ok": False,
            "label": "insufficient history",
        }
    monthly_close = cutoff["close"].resample("ME").last().dropna()
    if len(monthly_close) < 24:
        return {
            "trend_ok": False,
            "label": "insufficient history",
        }
    ema12 = monthly_close.ewm(span=12, adjust=False).mean()
    ema24 = monthly_close.ewm(span=24, adjust=False).mean()
    latest_close = float(monthly_close.iloc[-1])
    latest_ema12 = float(ema12.iloc[-1])
    latest_ema24 = float(ema24.iloc[-1])
    prev_ema12 = float(ema12.iloc[-2]) if len(ema12) >= 2 else latest_ema12
    trend_ok = latest_close > latest_ema12 > latest_ema24 and latest_ema12 >= prev_ema12
    label = "bullish" if trend_ok else "filter blocked"
    return {
        "trend_ok": bool(trend_ok),
        "label": label,
        "close": round(latest_close, 6),
        "ema12": round(latest_ema12, 6),
        "ema24": round(latest_ema24, 6),
        "ema12_rising": bool(latest_ema12 >= prev_ema12),
        "month": monthly_close.index[-1].strftime("%Y-%m"),
    }


def _reference_row(watchlist: str) -> dict[str, object] | None:
    if not RESEARCH_REPORT.exists():
        return None
    payload = json.loads(RESEARCH_REPORT.read_text())
    rows = payload.get("rows", [])
    sleeve_key = watchlist.replace("-", "_")
    for row in rows:
        if (
            row.get("profile_label") == REFERENCE_PROFILE_LABEL
            and row.get("withdrawal_label") == REFERENCE_WITHDRAWAL_LABEL
            and row.get("sleeve") == sleeve_key
        ):
            return row
    return None


def _latest_shared_date(history: dict[str, pd.DataFrame]) -> pd.Timestamp:
    latest_dates = [df.index[-1] for df in history.values() if not df.empty]
    return min(latest_dates)


def _allocation_due(latest: pd.Timestamp, first_trading_day: pd.Timestamp | None) -> bool:
    if first_trading_day is None:
        return False
    return 0 <= (latest.date() - first_trading_day.date()).days <= ALLOCATION_GRACE_DAYS


def _review_due(latest: pd.Timestamp, first_trading_day: pd.Timestamp | None) -> bool:
    if first_trading_day is None:
        return False
    return 0 <= (latest.date() - first_trading_day.date()).days <= REVIEW_GRACE_DAYS


def _allocation_event(
    watchlist: str,
    symbols: list[str],
    history: dict[str, pd.DataFrame],
    latest: pd.Timestamp,
    reference: dict[str, object] | None,
) -> dict[str, object]:
    active_legs: list[dict[str, object]] = []
    skipped_legs: list[dict[str, object]] = []
    trend_anchor_year, trend_anchor_month = _previous_month(latest)
    for symbol in symbols:
        latest_row = history[symbol].loc[:latest].iloc[-1]
        price_reference = float(latest_row["close"])
        reference_units = (MONTHLY_BUDGET / price_reference) if price_reference else 0.0
        trend_month_rows = history[symbol][
            (history[symbol].index.year == trend_anchor_year) & (history[symbol].index.month == trend_anchor_month)
        ]
        trend_anchor = trend_month_rows.index[-1] if not trend_month_rows.empty else history[symbol].loc[:latest].index[-1]
        trend = _trend_snapshot(history[symbol], trend_anchor)
        leg = {
            "symbol": symbol,
            "asset_class": asset_class_for(symbol),
            "price_reference": round(price_reference, 6),
            "reference_units": round(reference_units, 6),
            "monthly_budget": round(MONTHLY_BUDGET, 2),
            "trend_label": str(trend["label"]),
            "trend_month": str(trend.get("month", "n/a")),
            "trend_close": trend.get("close"),
            "trend_ema12": trend.get("ema12"),
            "trend_ema24": trend.get("ema24"),
        }
        if bool(trend["trend_ok"]):
            active_legs.append(leg)
        else:
            skipped_legs.append(leg)

    allocation_month = f"{latest.year}-{latest.month:02d}"
    sleeve_label = watchlist_label(watchlist)
    reference_text = None
    if reference:
        reference_text = (
            f"Research reference: {reference['profile_label']} / {reference['withdrawal_label']} / "
            f"{reference['sleeve_label']} produced ${reference['total_wealth']:,.2f} total wealth "
            f"with {reference['mean_max_drawdown_pct'] * 100:.2f}% mean max drawdown."
        )
    if active_legs:
        summary = (
            f"Monthly SIP allocation for the {sleeve_label} basket. "
            f"Only add to assets whose long-term monthly trend is still with us. "
            f"Use the fixed monthly budget per active asset and treat the size math as guidance, "
            f"not broker-exact lot sizing."
        )
    else:
        summary = (
            f"Monthly SIP review for the {sleeve_label} basket. "
            f"No fresh adds this month because none of the sleeve assets passed the long-term trend filter."
        )
    if reference_text:
        summary = f"{summary} {reference_text}"
    return {
        "strategy_id": "strategy_five",
        "symbol": sleeve_label,
        "asset_class": "portfolio",
        "timeframe": "1mo",
        "signal_type": "long",
        "timestamp": latest.isoformat(),
        "setup_id": f"sip-{watchlist}-{allocation_month}-allocation",
        "reason_summary": summary,
        "quality_score": None,
        "quality_grade": None,
        "risk_reward": None,
        "entry": None,
        "stop_loss": None,
        "target_1": None,
        "event_type": "sip_allocation",
        "allocation_month": allocation_month,
        "sleeve_label": sleeve_label,
        "profile_label": DEFAULT_PROFILE,
        "payout_label": DEFAULT_PAYOUT_MODE,
        "account_size": ACCOUNT_SIZE,
        "monthly_budget_per_asset": round(MONTHLY_BUDGET, 2),
        "total_sleeve_budget": round(MONTHLY_BUDGET * len(active_legs), 2),
        "active_legs": active_legs,
        "skipped_legs": skipped_legs,
        "active_count": len(active_legs),
        "skipped_count": len(skipped_legs),
        "reference_research": reference,
    }


def _review_event(
    watchlist: str,
    symbols: list[str],
    history: dict[str, pd.DataFrame],
    latest: pd.Timestamp,
    reference: dict[str, object] | None,
) -> dict[str, object] | None:
    review_year, review_month = _previous_month(latest)
    asset_rows: list[dict[str, object]] = []
    for symbol in symbols:
        stats = _monthly_return_stats(history[symbol], review_year, review_month)
        if not stats:
            continue
        asset_rows.append(
            {
                "symbol": symbol,
                "asset_class": asset_class_for(symbol),
                **stats,
            }
        )
    if not asset_rows:
        return None

    sleeve_label = watchlist_label(watchlist)
    avg_return = sum(float(row["month_return_pct"]) for row in asset_rows) / len(asset_rows)
    best_row = max(asset_rows, key=lambda row: float(row["month_return_pct"]))
    worst_row = min(asset_rows, key=lambda row: float(row["month_return_pct"]))
    review_month_label = f"{review_year}-{review_month:02d}"
    summary = (
        f"Month-end SIP review for the {sleeve_label} basket. "
        f"The equal-weight basket return was {avg_return:.2f}% for {review_month_label}, "
        f"with {best_row['symbol']} strongest and {worst_row['symbol']} weakest."
    )
    if reference:
        summary = (
            f"{summary} Research anchor: {reference['profile_label']} / {reference['withdrawal_label']} "
            f"/ {reference['sleeve_label']}."
        )
    return {
        "strategy_id": "strategy_five",
        "symbol": sleeve_label,
        "asset_class": "portfolio",
        "timeframe": "1mo",
        "signal_type": "long",
        "timestamp": latest.isoformat(),
        "setup_id": f"sip-{watchlist}-{review_month_label}-review",
        "reason_summary": summary,
        "quality_score": None,
        "quality_grade": None,
        "risk_reward": None,
        "entry": None,
        "stop_loss": None,
        "target_1": None,
        "event_type": "sip_review",
        "review_month": review_month_label,
        "sleeve_label": sleeve_label,
        "profile_label": DEFAULT_PROFILE,
        "payout_label": DEFAULT_PAYOUT_MODE,
        "sleeve_return_pct": round(avg_return, 2),
        "best_asset": best_row["symbol"],
        "best_asset_return_pct": round(float(best_row["month_return_pct"]), 2),
        "worst_asset": worst_row["symbol"],
        "worst_asset_return_pct": round(float(worst_row["month_return_pct"]), 2),
        "assets": asset_rows,
        "reference_research": reference,
    }


def save_scan_outputs(
    output_dir: str | Path,
    rows: list[dict[str, object]],
    signals: list[dict[str, object]],
    state: dict[str, object],
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scan_results.json").write_text(json.dumps(rows, indent=2))
    (out / "signals.json").write_text(json.dumps(signals, indent=2))
    save_state(out, state)


def run_live_cycle(
    symbols: list[str],
    watchlist: str,
    environment: str,
    token: str | None,
    price: str,
    output_dir: str | Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    history = {symbol: load_history(symbol, environment, token, price) for symbol in symbols}
    latest = _latest_shared_date(history)
    first_current = _first_trading_day(next(iter(history.values())), latest.year, latest.month)
    reference = _reference_row(watchlist)

    rows: list[dict[str, object]] = []
    signals: list[dict[str, object]] = []

    if _allocation_due(latest, first_current):
        signals.append(_allocation_event(watchlist, symbols, history, latest, reference))
    if _review_due(latest, first_current):
        review_signal = _review_event(watchlist, symbols, history, latest, reference)
        if review_signal is not None:
            signals.append(review_signal)

    for symbol in symbols:
        latest_row = history[symbol].loc[:latest].iloc[-1]
        prev_year, prev_month = _previous_month(latest)
        month_stats = _monthly_return_stats(history[symbol], prev_year, prev_month)
        trend_month_rows = history[symbol][
            (history[symbol].index.year == prev_year) & (history[symbol].index.month == prev_month)
        ]
        trend_anchor = trend_month_rows.index[-1] if not trend_month_rows.empty else history[symbol].loc[:latest].index[-1]
        trend = _trend_snapshot(history[symbol], trend_anchor)
        rows.append(
            {
                "symbol": symbol,
                "asset_class": asset_class_for(symbol),
                "latest_timestamp": latest.isoformat(),
                "latest_close": round(float(latest_row["close"]), 6),
                "monthly_budget": round(MONTHLY_BUDGET, 2),
                "reference_units": round(MONTHLY_BUDGET / float(latest_row["close"]), 6),
                "last_closed_month": f"{prev_year}-{prev_month:02d}",
                "last_closed_month_return_pct": round(float(month_stats["month_return_pct"]), 2) if month_stats else None,
                "trend_ok": bool(trend["trend_ok"]),
                "trend_label": str(trend["label"]),
            }
        )

    state = {
        "watchlist": watchlist,
        "watchlist_label": watchlist_label(watchlist),
        "latest_shared_timestamp": latest.isoformat(),
        "allocation_month": f"{latest.year}-{latest.month:02d}",
        "profile_label": DEFAULT_PROFILE,
        "payout_label": DEFAULT_PAYOUT_MODE,
        "symbols": symbols,
        "reference_research": reference,
    }
    return rows, signals, state
