"""Baseline monthly SIP backtest for the Secular Bull strategy."""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from little_rzy_bot.market_data import fetch_oanda_ohlcv


START_DATE = "2020-01-01"
END_DATE = "2026-04-01"
STARTING_CAPITAL = 100_000.0
MONTHLY_CONTRIBUTION = STARTING_CAPITAL / 12.0
REPORT_DIR = Path("reports/secular_bull_sip")
JSON_PATH = REPORT_DIR / "baseline_monthly_sip.json"
MD_PATH = REPORT_DIR / "BASELINE_MONTHLY_SIP.md"

ASSETS: dict[str, str] = {
    "XAU_USD": "Gold",
    "NAS100_USD": "Nasdaq 100",
    "US30_USD": "Dow Jones 30",
    "BTC_USD": "Bitcoin",
    "ETH_USD": "Ethereum",
}


@dataclass
class SipResult:
    symbol: str
    label: str
    start_bar: str
    end_bar: str
    months: int
    total_contributed: float
    ending_value: float
    net_pnl: float
    moic: float
    twr_annualized: float | None
    xirr: float | None
    max_drawdown_dollars: float
    max_drawdown_pct: float
    positive_month_pct: float
    best_month_return: float
    worst_month_return: float
    best_year_return: float | None
    worst_year_return: float | None


def _load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _xnpv(rate: float, cashflows: Iterable[tuple[float, float]]) -> float:
    total = 0.0
    for years_from_start, amount in cashflows:
        total += amount / ((1.0 + rate) ** years_from_start)
    return total


def _xirr(year_amount_pairs: list[tuple[float, float]]) -> float | None:
    has_negative = any(amount < 0 for _, amount in year_amount_pairs)
    has_positive = any(amount > 0 for _, amount in year_amount_pairs)
    if not (has_negative and has_positive):
        return None

    low = -0.9999
    high = 10.0
    low_npv = _xnpv(low, year_amount_pairs)
    high_npv = _xnpv(high, year_amount_pairs)

    while low_npv * high_npv > 0 and high < 1_000:
        high *= 2.0
        high_npv = _xnpv(high, year_amount_pairs)

    if low_npv * high_npv > 0:
        return None

    for _ in range(200):
        mid = (low + high) / 2.0
        mid_npv = _xnpv(mid, year_amount_pairs)
        if abs(mid_npv) < 1e-7:
            return mid
        if low_npv * mid_npv <= 0:
            high = mid
            high_npv = mid_npv
        else:
            low = mid
            low_npv = mid_npv
    return (low + high) / 2.0


def _fetch_monthly(symbol: str):
    fetched = fetch_oanda_ohlcv(
        instrument=symbol,
        granularity="M",
        start=START_DATE,
        end=END_DATE,
        environment=os.getenv("OANDA_ENV", "practice"),
    )
    return fetched.df.copy().sort_index()


def simulate_symbol(symbol: str, label: str) -> SipResult:
    df = _fetch_monthly(symbol)
    if df.empty:
        raise RuntimeError(f"No monthly candles returned for {symbol}")

    units = 0.0
    total_contributed = 0.0
    peak_equity = 0.0
    max_drawdown_dollars = 0.0
    max_drawdown_pct = 0.0
    monthly_returns: list[float] = []
    annual_returns: dict[int, list[float]] = {}
    cashflows: list[tuple[float, float]] = []

    first_ts = df.index[0]
    previous_equity = 0.0

    for timestamp, row in df.iterrows():
        contribution = MONTHLY_CONTRIBUTION
        units_bought = contribution / float(row["open"])
        units += units_bought
        total_contributed += contribution

        equity_before_move = previous_equity + contribution
        end_equity = units * float(row["close"])
        month_return = (end_equity / equity_before_move - 1.0) if equity_before_move > 0 else 0.0
        monthly_returns.append(month_return)
        annual_returns.setdefault(timestamp.year, []).append(month_return)

        peak_equity = max(peak_equity, end_equity)
        drawdown_dollars = peak_equity - end_equity
        drawdown_pct = drawdown_dollars / peak_equity if peak_equity > 0 else 0.0
        max_drawdown_dollars = max(max_drawdown_dollars, drawdown_dollars)
        max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

        years_from_start = (timestamp - first_ts).days / 365.25
        cashflows.append((years_from_start, -contribution))
        previous_equity = end_equity

    ending_value = previous_equity
    final_ts = df.index[-1]
    final_years = (final_ts - first_ts).days / 365.25
    cashflows.append((final_years, ending_value))

    total_growth = math.prod(1.0 + value for value in monthly_returns)
    twr_annualized = total_growth ** (12.0 / len(monthly_returns)) - 1.0 if monthly_returns else None
    annual_compound_returns = {
        year: math.prod(1.0 + value for value in values) - 1.0 for year, values in annual_returns.items()
    }
    xirr = _xirr(cashflows)

    return SipResult(
        symbol=symbol,
        label=label,
        start_bar=str(first_ts),
        end_bar=str(final_ts),
        months=len(df),
        total_contributed=round(total_contributed, 2),
        ending_value=round(ending_value, 2),
        net_pnl=round(ending_value - total_contributed, 2),
        moic=round(ending_value / total_contributed, 4),
        twr_annualized=round(twr_annualized, 4) if twr_annualized is not None else None,
        xirr=round(xirr, 4) if xirr is not None else None,
        max_drawdown_dollars=round(max_drawdown_dollars, 2),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        positive_month_pct=round(sum(1 for value in monthly_returns if value > 0) / len(monthly_returns), 4),
        best_month_return=round(max(monthly_returns), 4),
        worst_month_return=round(min(monthly_returns), 4),
        best_year_return=round(max(annual_compound_returns.values()), 4) if annual_compound_returns else None,
        worst_year_return=round(min(annual_compound_returns.values()), 4) if annual_compound_returns else None,
    )


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def write_markdown(results: list[SipResult]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Secular Bull SIP Baseline")
    lines.append("")
    lines.append("## Test Setup")
    lines.append("")
    lines.append(f"- Date range: `{START_DATE}` to `{END_DATE}`")
    lines.append(f"- Starting capital reference: `${STARTING_CAPITAL:,.0f}`")
    lines.append(f"- Monthly contribution per asset test: `${MONTHLY_CONTRIBUTION:,.2f}`")
    lines.append("- Variant: pure monthly SIP baseline")
    lines.append("- Long-only")
    lines.append("- No leverage")
    lines.append("- No stop loss")
    lines.append("- One asset per simulation")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Month | Worst Month | Best Year | Worst Year |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in sorted(results, key=lambda item: item.net_pnl, reverse=True):
        lines.append(
            "| "
            f"`{result.symbol}` | {result.label} | {result.months} | {_fmt_money(result.total_contributed)} | "
            f"{_fmt_money(result.ending_value)} | {_fmt_money(result.net_pnl)} | {result.moic:.2f} | "
            f"{_fmt_pct(result.twr_annualized)} | {_fmt_pct(result.xirr)} | {_fmt_money(result.max_drawdown_dollars)} | "
            f"{_fmt_pct(result.max_drawdown_pct)} | {_fmt_pct(result.positive_month_pct)} | "
            f"{_fmt_pct(result.best_month_return)} | {_fmt_pct(result.worst_month_return)} | "
            f"{_fmt_pct(result.best_year_return)} | {_fmt_pct(result.worst_year_return)} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `TWR Ann.` is the annualized time-weighted return across monthly contributions.")
    lines.append("- `XIRR` is the money-weighted annualized return using monthly contributions and final liquidation value.")
    lines.append("- `MOIC` = ending value divided by total contributed capital.")
    lines.append("- This is the pure baseline only. Leveraged and correction-filter variants still need their own passes.")
    MD_PATH.write_text("\n".join(lines))


def main() -> None:
    _load_env(Path(".env"))
    results = [simulate_symbol(symbol, label) for symbol, label in ASSETS.items()]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps([asdict(result) for result in results], indent=2))
    write_markdown(results)
    print(json.dumps([asdict(result) for result in results], indent=2))


if __name__ == "__main__":
    main()
