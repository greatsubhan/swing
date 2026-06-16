"""Standalone crypto-only monthly SIP baseline report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.secular_bull_sip_baseline import (
    MONTHLY_CONTRIBUTION,
    STARTING_CAPITAL,
    START_DATE,
    END_DATE,
    SipResult,
    _fmt_money,
    _fmt_pct,
    _load_env,
    simulate_symbol,
)


OUTPUT_DIR = Path("reports/secular_bull_sip")
OUTPUT_JSON = OUTPUT_DIR / "crypto_monthly_sip.json"
OUTPUT_MD = OUTPUT_DIR / "CRYPTO_MONTHLY_SIP.md"

CRYPTO_ASSETS: dict[str, str] = {
    "BTC_USD": "Bitcoin",
    "ETH_USD": "Ethereum",
    "LTC_USD": "Litecoin",
    "BCH_USD": "Bitcoin Cash",
}


def write_markdown(results: list[SipResult]) -> None:
    lines: list[str] = []
    lines.append("# Secular Bull SIP Crypto Slice")
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
    best = max(results, key=lambda item: item.xirr or -999)
    lowest_dd = min(results, key=lambda item: item.max_drawdown_pct)
    lines.append("## Quick Read")
    lines.append("")
    lines.append(
        f"- Best money-weighted return: `{best.symbol}` with XIRR `{_fmt_pct(best.xirr)}` "
        f"and net PnL `${_fmt_money(best.net_pnl)}`."
    )
    lines.append(
        f"- Lowest drawdown: `{lowest_dd.symbol}` with max DD `{_fmt_pct(lowest_dd.max_drawdown_pct)}`."
    )
    lines.append("- Crypto remains the highest-volatility sleeve in this SIP baseline, so the upside and pain should be read together.")
    OUTPUT_MD.write_text("\n".join(lines))


def main() -> None:
    _load_env(Path(".env"))
    results = [simulate_symbol(symbol, label) for symbol, label in CRYPTO_ASSETS.items()]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps([result.__dict__ for result in results], indent=2))
    write_markdown(results)
    print(json.dumps([result.__dict__ for result in results], indent=2))


if __name__ == "__main__":
    main()
