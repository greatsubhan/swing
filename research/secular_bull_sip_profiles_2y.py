"""Two-year SIP research with swing-friendly prop-firm profiles and payout overlay."""
from __future__ import annotations

import json
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
INITIAL_BALANCE = 100_000.0
MONTHLY_BUDGET = INITIAL_BALANCE / 12.0
WINDOW_MONTHS = 24
WINDOW_STEP_MONTHS = 12
LEVERAGES = (1.0, 2.0, 3.0)
STOP_PCTS = (0.10, 0.15, 0.20)
REPORT_DIR = Path("reports/secular_bull_sip")
JSON_PATH = REPORT_DIR / "TWO_YEAR_PROFILE_SIP.json"
MD_PATH = REPORT_DIR / "TWO_YEAR_PROFILE_SIP.md"

ASSETS = {
    "XAU_USD": "Gold",
    "XAG_USD": "Silver",
    "NAS100_USD": "Nasdaq 100",
    "US30_USD": "Dow Jones 30",
    "BTC_USD": "Bitcoin",
}

PROFILES = {
    "ftmo_swing": {
        "label": "FTMO Swing",
        "daily_mode": "start_balance",
        "daily_loss_pct": 0.05,
        "overall_mode": "static",
        "overall_loss_pct": 0.10,
        "weekend_holding": True,
        "sources": [
            "https://ftmo.com/en/trading-objectives/",
            "https://ftmo.com/en/faq/ftmo-swing-account-type/",
        ],
    },
    "the5ers_high_stakes": {
        "label": "The5ers High Stakes",
        "daily_mode": "max_balance_equity",
        "daily_loss_pct": 0.05,
        "overall_mode": "static",
        "overall_loss_pct": 0.10,
        "weekend_holding": True,
        "sources": [
            "https://help.the5ers.com/what-is-the-maximum-loss-and-the-maximum-daily-loss-in-the-high-stakes-program/",
            "https://help.the5ers.com/do-i-have-to-close-my-positions-overnight/",
        ],
    },
    "fundednext_stellar_instant": {
        "label": "FundedNext Stellar Instant",
        "daily_mode": "none",
        "daily_loss_pct": 0.0,
        "overall_mode": "trailing_capped_initial",
        "overall_loss_pct": 0.06,
        "weekend_holding": True,
        "sources": [
            "https://help.fundednext.com/en/articles/11641163-what-are-the-daily-loss-limit-and-the-maximum-loss-limit-for-the-stellar-instant-accounts",
            "https://help.fundednext.com/en/articles/11641232-are-there-restrictions-for-overnight-or-weekend-trading",
        ],
    },
}

WITHDRAWAL_MODES = {
    "none": {"label": "No Withdrawal"},
    "skim_quarter_above_base": {"label": "Skim 25% of month-end profit above $100k"},
    "skim_half_above_base": {"label": "Skim 50% of month-end profit above $100k"},
    "skim_three_quarters_above_base": {"label": "Skim 75% of month-end profit above $100k"},
}


@dataclass
class Tranche:
    entry_price: float
    stop_price: float
    units: float
    active: bool = True


@dataclass
class ProfileWindowResult:
    symbol: str
    label: str
    profile: str
    withdrawal_mode: str
    window_name: str
    window_start: str
    window_end: str
    leverage: float
    stop_pct: float
    size_multiplier: float
    effective_monthly_notional: float
    ending_equity: float
    vault_withdrawn: float
    total_wealth: float
    net_pnl: float
    return_pct: float
    max_drawdown_dollars: float
    max_drawdown_pct: float
    max_daily_loss_dollars: float
    payout_count: int
    stop_hit_count: int
    breach: bool
    breach_reason: str | None
    verdict: str


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
    periods = pd.Series(df.index.to_period("M"), index=df.index)
    return periods != periods.shift(1)


def _build_windows(index: pd.DatetimeIndex) -> list[dict[str, str]]:
    windows: list[dict[str, str]] = []
    unique_months = pd.PeriodIndex(index.to_period("M").unique()).sort_values()
    for start_idx in range(0, max(len(unique_months) - WINDOW_MONTHS + 1, 0), WINDOW_STEP_MONTHS):
        window_months = unique_months[start_idx : start_idx + WINDOW_MONTHS]
        if len(window_months) < WINDOW_MONTHS:
            continue
        start_period = window_months[0]
        end_period = window_months[-1]
        start_ts = index[index.to_period("M") == start_period][0]
        end_ts = index[index.to_period("M") == end_period][-1]
        windows.append(
            {
                "name": f"{start_period.start_time.date()}_to_{end_period.end_time.date()}",
                "start": str(start_ts),
                "end": str(end_ts),
            }
        )
    return windows


def _slice_df(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))].copy()


def _daily_floor(
    profile: dict[str, Any],
    *,
    day_start_balance: float,
    day_start_equity: float,
) -> float | None:
    mode = profile["daily_mode"]
    loss = profile["daily_loss_pct"] * INITIAL_BALANCE
    if mode == "none":
        return None
    if mode == "start_balance":
        return day_start_balance - loss
    if mode == "max_balance_equity":
        return max(day_start_balance, day_start_equity) - loss
    raise ValueError(f"Unknown daily mode: {mode}")


def _overall_floor(profile: dict[str, Any], high_watermark: float) -> float:
    loss = profile["overall_loss_pct"] * INITIAL_BALANCE
    mode = profile["overall_mode"]
    if mode == "static":
        return INITIAL_BALANCE - loss
    if mode == "trailing_capped_initial":
        return min(INITIAL_BALANCE, high_watermark - loss)
    raise ValueError(f"Unknown overall mode: {mode}")


def _apply_withdrawal(mode: str, equity: float) -> tuple[float, float]:
    if mode == "none" or equity <= INITIAL_BALANCE:
        return equity, 0.0
    excess = equity - INITIAL_BALANCE
    if mode == "skim_quarter_above_base":
        ratio = 0.25
    elif mode == "skim_half_above_base":
        ratio = 0.50
    elif mode == "skim_three_quarters_above_base":
        ratio = 0.75
    else:
        raise ValueError(f"Unknown withdrawal mode: {mode}")
    withdrawn = excess * ratio
    return equity - withdrawn, withdrawn


def _verdict(result: ProfileWindowResult) -> str:
    if result.breach:
        return "Reject"
    if result.total_wealth > 140_000 and result.size_multiplier >= 0.50:
        return "Keep"
    if result.total_wealth > 115_000 and result.size_multiplier >= 0.25:
        return "Caution"
    return "Reject"


def simulate_window(
    symbol: str,
    label: str,
    df: pd.DataFrame,
    *,
    profile_key: str,
    profile: dict[str, Any],
    withdrawal_mode: str,
    window_name: str,
    start: str,
    end: str,
    leverage: float,
    stop_pct: float,
    size_multiplier: float,
    stop_on_breach: bool,
) -> ProfileWindowResult:
    frame = _slice_df(df, start, end)
    if frame.empty:
        raise RuntimeError(f"No data for {symbol} in {window_name}")

    entry_mask = _monthly_entry_mask(frame)
    tranches: list[Tranche] = []
    realized_pnl = 0.0
    withdrawn_total = 0.0
    payout_count = 0
    stop_hit_count = 0
    peak_equity = INITIAL_BALANCE
    max_drawdown_dollars = 0.0
    max_drawdown_pct = 0.0
    max_daily_loss_dollars = 0.0
    breach = False
    breach_reason: str | None = None

    current_day = None
    day_start_balance = INITIAL_BALANCE
    day_start_equity = INITIAL_BALANCE
    trailing_high = INITIAL_BALANCE

    for idx, (timestamp, row) in enumerate(frame.iterrows()):
        close_price = float(row["close"])
        active_close_pnl_open = sum(
            tranche.units * (close_price - tranche.entry_price) for tranche in tranches if tranche.active
        )
        day_balance = INITIAL_BALANCE + realized_pnl - withdrawn_total
        opening_equity = day_balance + active_close_pnl_open

        if current_day != timestamp.date():
            current_day = timestamp.date()
            day_start_balance = day_balance
            day_start_equity = opening_equity

        if bool(entry_mask.iloc[idx]):
            entry_price = float(row["open"])
            notional = MONTHLY_BUDGET * leverage * size_multiplier
            units = notional / entry_price if entry_price > 0 else 0.0
            tranches.append(
                Tranche(
                    entry_price=entry_price,
                    stop_price=entry_price * (1.0 - stop_pct),
                    units=units,
                )
            )

        low_price = float(row["low"])
        active_intraday_pnl = 0.0
        active_close_pnl = 0.0
        for tranche in tranches:
            if not tranche.active:
                continue
            if low_price <= tranche.stop_price:
                realized_pnl += tranche.units * (tranche.stop_price - tranche.entry_price)
                tranche.active = False
                stop_hit_count += 1
            else:
                active_intraday_pnl += tranche.units * (low_price - tranche.entry_price)
                active_close_pnl += tranche.units * (close_price - tranche.entry_price)

        balance = INITIAL_BALANCE + realized_pnl - withdrawn_total
        intraday_equity = balance + active_intraday_pnl
        close_equity = balance + active_close_pnl

        trailing_high = max(trailing_high, close_equity)
        overall_floor = _overall_floor(profile, trailing_high)
        daily_floor = _daily_floor(profile, day_start_balance=day_start_balance, day_start_equity=day_start_equity)

        peak_equity = max(peak_equity, close_equity)
        dd_dollars = peak_equity - intraday_equity
        dd_pct = dd_dollars / peak_equity if peak_equity > 0 else 0.0
        max_drawdown_dollars = max(max_drawdown_dollars, dd_dollars)
        max_drawdown_pct = max(max_drawdown_pct, dd_pct)

        daily_loss = day_start_equity - intraday_equity
        max_daily_loss_dollars = max(max_daily_loss_dollars, daily_loss)

        breached = False
        if intraday_equity < overall_floor:
            breach = True
            breach_reason = "overall_floor"
            breached = True
        elif daily_floor is not None and intraday_equity < daily_floor:
            breach = True
            breach_reason = "daily_floor"
            breached = True

        if breached and stop_on_breach:
            break

        if bool(entry_mask.iloc[idx]):
            adjusted_close_equity, withdrawn = _apply_withdrawal(withdrawal_mode, close_equity)
            if withdrawn > 0:
                withdrawn_total += withdrawn
                payout_count += 1
                close_equity = adjusted_close_equity

    ending_equity = close_equity if "close_equity" in locals() else INITIAL_BALANCE
    total_wealth = ending_equity + withdrawn_total
    result = ProfileWindowResult(
        symbol=symbol,
        label=label,
        profile=profile_key,
        withdrawal_mode=withdrawal_mode,
        window_name=window_name,
        window_start=start,
        window_end=end,
        leverage=leverage,
        stop_pct=stop_pct,
        size_multiplier=round(size_multiplier, 4),
        effective_monthly_notional=round(MONTHLY_BUDGET * leverage * size_multiplier, 2),
        ending_equity=round(ending_equity, 2),
        vault_withdrawn=round(withdrawn_total, 2),
        total_wealth=round(total_wealth, 2),
        net_pnl=round(total_wealth - INITIAL_BALANCE, 2),
        return_pct=round((total_wealth - INITIAL_BALANCE) / INITIAL_BALANCE, 4),
        max_drawdown_dollars=round(max_drawdown_dollars, 2),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        max_daily_loss_dollars=round(max_daily_loss_dollars, 2),
        payout_count=payout_count,
        stop_hit_count=stop_hit_count,
        breach=breach,
        breach_reason=breach_reason,
        verdict="",
    )
    result.verdict = _verdict(result)
    return result


def find_safe_result(
    symbol: str,
    label: str,
    df: pd.DataFrame,
    *,
    profile_key: str,
    profile: dict[str, Any],
    withdrawal_mode: str,
    window_name: str,
    start: str,
    end: str,
    leverage: float,
    stop_pct: float,
) -> ProfileWindowResult:
    probe = simulate_window(
        symbol,
        label,
        df,
        profile_key=profile_key,
        profile=profile,
        withdrawal_mode=withdrawal_mode,
        window_name=window_name,
        start=start,
        end=end,
        leverage=leverage,
        stop_pct=stop_pct,
        size_multiplier=1.0,
        stop_on_breach=True,
    )
    if not probe.breach:
        return probe

    lo = 0.0
    hi = 1.0
    for _ in range(12):
        mid = (lo + hi) / 2.0
        trial = simulate_window(
            symbol,
            label,
            df,
            profile_key=profile_key,
            profile=profile,
            withdrawal_mode=withdrawal_mode,
            window_name=window_name,
            start=start,
            end=end,
            leverage=leverage,
            stop_pct=stop_pct,
            size_multiplier=mid,
            stop_on_breach=True,
        )
        if trial.breach:
            hi = mid
        else:
            lo = mid

    return simulate_window(
        symbol,
        label,
        df,
        profile_key=profile_key,
        profile=profile,
        withdrawal_mode=withdrawal_mode,
        window_name=window_name,
        start=start,
        end=end,
        leverage=leverage,
        stop_pct=stop_pct,
        size_multiplier=lo,
        stop_on_breach=False,
    )


def write_markdown(payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Two-Year SIP Profile Study")
    lines.append("")
    lines.append("## Setup")
    lines.append("")
    lines.append("- Assets: Gold, Silver, Nasdaq 100, Dow Jones 30, Bitcoin")
    lines.append("- Window length: 24 months")
    lines.append("- Step between windows: 12 months")
    lines.append("- SIP entries: first trading day of each month")
    lines.append("- Tested leverage: `1x`, `2x`, `3x`")
    lines.append("- Tested stops: `10%`, `15%`, `20%`")
    lines.append("- Withdrawal overlays:")
    lines.append("  - `none`")
    lines.append("  - `skim_half_above_base`")
    lines.append("")
    lines.append("## Firm Profiles")
    lines.append("")
    for key, profile in PROFILES.items():
        lines.append(f"### {profile['label']}")
        lines.append("")
        lines.append(f"- Daily rule mode: `{profile['daily_mode']}`")
        lines.append(f"- Daily loss: `{profile['daily_loss_pct'] * 100:.0f}%`")
        lines.append(f"- Overall rule mode: `{profile['overall_mode']}`")
        lines.append(f"- Overall loss: `{profile['overall_loss_pct'] * 100:.0f}%`")
        lines.append(f"- Weekend holding assumed allowed: `{profile['weekend_holding']}`")
        lines.append("- Sources:")
        for source in profile["sources"]:
            lines.append(f"  - [{source}]({source})")
        lines.append("")

    lines.append("## Best Result Per Asset / Profile / Withdrawal Mode")
    lines.append("")
    lines.append("| Profile | Withdrawal | Asset | Best Window | Lev | Stop | Size Mult | End Equity $ | Vault $ | Total Wealth $ | Net PnL $ | Return % | Max DD % | Max Daily Loss $ | Payouts | Verdict |")
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in payload["best_asset_profile_mode_rows"]:
        lines.append(
            f"| {row['profile_label']} | {row['withdrawal_label']} | `{row['symbol']}` | `{row['window_name']}` | "
            f"{row['leverage']:.0f}x | {int(row['stop_pct'] * 100)}% | {row['size_multiplier']:.2f} | "
            f"{_fmt_money(row['ending_equity'])} | {_fmt_money(row['vault_withdrawn'])} | {_fmt_money(row['total_wealth'])} | "
            f"{_fmt_money(row['net_pnl'])} | {_fmt_pct(row['return_pct'])} | {_fmt_pct(row['max_drawdown_pct'])} | "
            f"{_fmt_money(row['max_daily_loss_dollars'])} | {row['payout_count']} | {row['verdict']} |"
        )
    lines.append("")

    lines.append("## Multi-Account Sleeve Summary")
    lines.append("")
    lines.append("| Profile | Withdrawal | Window | Total Wealth $ | End Equity $ | Vault $ | Mean Size Mult | Keep Count | Caution Count |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|")
    for row in payload["sleeve_rows"]:
        lines.append(
            f"| {row['profile_label']} | {row['withdrawal_label']} | `{row['window_name']}` | {_fmt_money(row['total_wealth'])} | "
            f"{_fmt_money(row['ending_equity'])} | {_fmt_money(row['vault_withdrawn'])} | {row['mean_size_multiplier']:.2f} | "
            f"{row['keep_count']} | {row['caution_count']} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `Vault` is withdrawn profit under the payout overlay. It represents money skimmed out of the account, not unrealized open equity.")
    lines.append("- The payout overlay is a research approximation. It does not assume a specific challenge fee or exact payout schedule.")
    lines.append("- FundedNext Stellar Instant uses a trailing max-loss rule in the profile model; because SIP is mostly open-equity driven, this remains an approximation rather than a broker-exact recreation.")
    MD_PATH.write_text("\n".join(lines))


def main() -> None:
    _load_env(Path(".env"))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    data = {symbol: _fetch_daily(symbol) for symbol in ASSETS}
    common_index = None
    for frame in data.values():
        common_index = frame.index if common_index is None else common_index.intersection(frame.index)
    if common_index is None:
        raise RuntimeError("No common index available")
    windows = _build_windows(common_index.sort_values())

    results: list[ProfileWindowResult] = []
    by_profile_mode_asset: dict[tuple[str, str, str], list[ProfileWindowResult]] = {}
    by_profile_mode_window: dict[tuple[str, str, str], list[ProfileWindowResult]] = {}

    for profile_key, profile in PROFILES.items():
        for withdrawal_mode in WITHDRAWAL_MODES:
            for window in windows:
                for symbol, label in ASSETS.items():
                    frame = data[symbol]
                    symbol_results: list[ProfileWindowResult] = []
                    for leverage in LEVERAGES:
                        for stop_pct in STOP_PCTS:
                            result = find_safe_result(
                                symbol,
                                label,
                                frame,
                                profile_key=profile_key,
                                profile=profile,
                                withdrawal_mode=withdrawal_mode,
                                window_name=window["name"],
                                start=window["start"],
                                end=window["end"],
                                leverage=leverage,
                                stop_pct=stop_pct,
                            )
                            results.append(result)
                            symbol_results.append(result)
                    best_symbol_result = max(
                        symbol_results,
                        key=lambda item: (
                            {"Keep": 2, "Caution": 1, "Reject": 0}[item.verdict],
                            item.total_wealth,
                            item.size_multiplier,
                        ),
                    )
                    by_profile_mode_asset.setdefault((profile_key, withdrawal_mode, symbol), []).append(best_symbol_result)
                    by_profile_mode_window.setdefault((profile_key, withdrawal_mode, window["name"]), []).append(best_symbol_result)

    best_asset_profile_mode_rows: list[dict[str, Any]] = []
    for (profile_key, withdrawal_mode, symbol), rows in by_profile_mode_asset.items():
        best = max(
            rows,
            key=lambda item: (
                {"Keep": 2, "Caution": 1, "Reject": 0}[item.verdict],
                item.total_wealth,
                item.size_multiplier,
            ),
        )
        row = asdict(best)
        row["profile_label"] = PROFILES[profile_key]["label"]
        row["withdrawal_label"] = WITHDRAWAL_MODES[withdrawal_mode]["label"]
        best_asset_profile_mode_rows.append(row)

    sleeve_rows: list[dict[str, Any]] = []
    for (profile_key, withdrawal_mode, window_name), rows in by_profile_mode_window.items():
        sleeve_rows.append(
            {
                "profile": profile_key,
                "profile_label": PROFILES[profile_key]["label"],
                "withdrawal_mode": withdrawal_mode,
                "withdrawal_label": WITHDRAWAL_MODES[withdrawal_mode]["label"],
                "window_name": window_name,
                "ending_equity": round(sum(item.ending_equity for item in rows), 2),
                "vault_withdrawn": round(sum(item.vault_withdrawn for item in rows), 2),
                "total_wealth": round(sum(item.total_wealth for item in rows), 2),
                "mean_size_multiplier": round(sum(item.size_multiplier for item in rows) / len(rows), 4),
                "keep_count": sum(1 for item in rows if item.verdict == "Keep"),
                "caution_count": sum(1 for item in rows if item.verdict == "Caution"),
            }
        )

    payload = {
        "config": {
            "date_range": {"start": START_DATE, "end": END_DATE},
            "initial_balance": INITIAL_BALANCE,
            "monthly_budget": MONTHLY_BUDGET,
            "window_months": WINDOW_MONTHS,
            "window_step_months": WINDOW_STEP_MONTHS,
            "leverages": list(LEVERAGES),
            "stop_pcts": list(STOP_PCTS),
        },
        "profiles": PROFILES,
        "withdrawal_modes": WITHDRAWAL_MODES,
        "windows": windows,
        "results": [asdict(result) for result in results],
        "best_asset_profile_mode_rows": best_asset_profile_mode_rows,
        "sleeve_rows": sleeve_rows,
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2))
    write_markdown(payload)
    print(
        json.dumps(
            {
                "windows": len(windows),
                "results_written": len(results),
                "report": str(MD_PATH),
                "json": str(JSON_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
