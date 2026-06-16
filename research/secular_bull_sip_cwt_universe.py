"""Monthly SIP baseline run across the broader CWT universe."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
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


CONFIG_PATH = Path("config/cwt_market_constraints.json")
OUTPUT_DIR = Path("reports/secular_bull_sip")
OUTPUT_JSON = OUTPUT_DIR / "cwt_universe_monthly_sip.json"
OUTPUT_MD = OUTPUT_DIR / "CWT_UNIVERSE_MONTHLY_SIP.md"

GROUP_LABELS = {
    "major_fx": "Major FX",
    "commodity_fx": "Commodity FX",
    "minor_cross_fx": "Minor & Cross FX",
    "indices": "Indices",
    "commodities": "Commodities",
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
}


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
    return groups


def label_for_symbol(symbol: str) -> str:
    return SYMBOL_LABELS.get(symbol, symbol.replace("_", "/"))


def summarize_group(results: list[SipResult]) -> dict[str, float]:
    count = len(results)
    return {
        "tested": count,
        "mean_ending_value": round(sum(item.ending_value for item in results) / count, 2) if count else 0.0,
        "mean_net_pnl": round(sum(item.net_pnl for item in results) / count, 2) if count else 0.0,
        "mean_twr_ann": round(sum(item.twr_annualized or 0.0 for item in results) / count, 4) if count else 0.0,
        "mean_xirr": round(sum(item.xirr or 0.0 for item in results) / count, 4) if count else 0.0,
        "mean_max_dd_pct": round(sum(item.max_drawdown_pct for item in results) / count, 4) if count else 0.0,
    }


def write_markdown(group_results: dict[str, list[SipResult]], unavailable: dict[str, list[str]]) -> None:
    lines: list[str] = []
    lines.append("# Secular Bull SIP Baseline Across CWT Universe")
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
    lines.append("- Universe source: CWT market batches")
    lines.append("")
    lines.append("## Batch Summary")
    lines.append("")
    lines.append("| Batch | Tested | Mean Ending Value $ | Mean Net PnL $ | Mean TWR Ann. | Mean XIRR | Mean Max DD % |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for group_id, results in group_results.items():
        summary = summarize_group(results)
        lines.append(
            f"| {GROUP_LABELS.get(group_id, group_id)} | {summary['tested']} | "
            f"{_fmt_money(summary['mean_ending_value'])} | {_fmt_money(summary['mean_net_pnl'])} | "
            f"{_fmt_pct(summary['mean_twr_ann'])} | {_fmt_pct(summary['mean_xirr'])} | "
            f"{_fmt_pct(summary['mean_max_dd_pct'])} |"
        )
    lines.append("")
    lines.append("## Detailed Results")
    lines.append("")
    for group_id, results in group_results.items():
        lines.append(f"### {GROUP_LABELS.get(group_id, group_id)}")
        lines.append("")
        lines.append("| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Year | Worst Year |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for result in sorted(results, key=lambda item: item.net_pnl, reverse=True):
            lines.append(
                "| "
                f"`{result.symbol}` | {result.label} | {result.months} | {_fmt_money(result.total_contributed)} | "
                f"{_fmt_money(result.ending_value)} | {_fmt_money(result.net_pnl)} | {result.moic:.2f} | "
                f"{_fmt_pct(result.twr_annualized)} | {_fmt_pct(result.xirr)} | {_fmt_money(result.max_drawdown_dollars)} | "
                f"{_fmt_pct(result.max_drawdown_pct)} | {_fmt_pct(result.positive_month_pct)} | "
                f"{_fmt_pct(result.best_year_return)} | {_fmt_pct(result.worst_year_return)} |"
            )
        lines.append("")
        top = sorted(results, key=lambda item: item.net_pnl, reverse=True)[:3]
        bottom = sorted(results, key=lambda item: item.net_pnl)[:3]
        lines.append("Top performers:")
        for item in top:
            lines.append(
                f"- `{item.symbol}`: ending value `${_fmt_money(item.ending_value)}`, "
                f"net PnL `${_fmt_money(item.net_pnl)}`, XIRR `{_fmt_pct(item.xirr)}`, "
                f"max DD `{_fmt_pct(item.max_drawdown_pct)}`"
            )
        lines.append("Weakest performers:")
        for item in bottom:
            lines.append(
                f"- `{item.symbol}`: ending value `${_fmt_money(item.ending_value)}`, "
                f"net PnL `${_fmt_money(item.net_pnl)}`, XIRR `{_fmt_pct(item.xirr)}`, "
                f"max DD `{_fmt_pct(item.max_drawdown_pct)}`"
            )
        lines.append("")
    if any(unavailable.values()):
        lines.append("## Unavailable Symbols")
        lines.append("")
        for group_id, symbols in unavailable.items():
            if not symbols:
                continue
            lines.append(f"- {GROUP_LABELS.get(group_id, group_id)}: {', '.join(f'`{symbol}`' for symbol in symbols)}")
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This report uses the same pure monthly SIP baseline as the initial five-asset lecture pass.")
    lines.append("- A positive result here does not mean the asset belongs in the final secular-bull universe; it only shows how blind monthly accumulation behaved on this feed.")
    lines.append("- Leveraged and correction-filter versions still need separate testing.")
    OUTPUT_MD.write_text("\n".join(lines))


def main() -> None:
    _load_env(Path(".env"))
    groups = load_group_symbols()
    group_results: dict[str, list[SipResult]] = defaultdict(list)
    unavailable: dict[str, list[str]] = defaultdict(list)
    payload: dict[str, object] = {"config": {
        "date_range": {"start": START_DATE, "end": END_DATE},
        "starting_capital_reference": STARTING_CAPITAL,
        "monthly_contribution": MONTHLY_CONTRIBUTION,
        "variant": "pure_monthly_sip_baseline",
    }, "groups": {}, "unavailable": {}}

    for group_id, symbols in groups.items():
        payload["groups"][group_id] = []
        for symbol in symbols:
            try:
                result = simulate_symbol(symbol, label_for_symbol(symbol))
            except Exception:
                unavailable[group_id].append(symbol)
                continue
            group_results[group_id].append(result)
            payload["groups"][group_id].append(result.__dict__)
        payload["unavailable"][group_id] = unavailable[group_id]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2))
    write_markdown(group_results, unavailable)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
