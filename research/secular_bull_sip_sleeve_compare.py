"""Compare practical Secular Bull SIP sleeves across 2-year profile results."""
from __future__ import annotations

import json
from pathlib import Path


INPUT_JSON = Path("reports/secular_bull_sip/TWO_YEAR_PROFILE_SIP.json")
OUTPUT_JSON = Path("reports/secular_bull_sip/SLEEVE_COMPARE_2Y.json")
OUTPUT_MD = Path("reports/secular_bull_sip/SLEEVE_COMPARE_2Y.md")

SLEEVES = {
    "growth_core": {
        "label": "Growth Core",
        "symbols": ["XAU_USD", "XAG_USD", "BTC_USD"],
    },
    "balanced_core": {
        "label": "Balanced Core",
        "symbols": ["XAU_USD", "BTC_USD", "US30_USD"],
    },
    "full_classic": {
        "label": "Full Classic",
        "symbols": ["XAU_USD", "XAG_USD", "NAS100_USD", "US30_USD", "BTC_USD"],
    },
}


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    data = json.loads(INPUT_JSON.read_text())
    best_rows = data["best_asset_profile_mode_rows"]

    by_key: dict[tuple[str, str, str], dict] = {}
    for row in best_rows:
        by_key[(row["profile"], row["withdrawal_mode"], row["symbol"])] = row

    sleeve_rows: list[dict] = []
    for profile_key, profile in data["profiles"].items():
        for withdrawal_key, withdrawal in data["withdrawal_modes"].items():
            for sleeve_key, sleeve in SLEEVES.items():
                members = []
                missing = []
                for symbol in sleeve["symbols"]:
                    row = by_key.get((profile_key, withdrawal_key, symbol))
                    if row is None:
                        missing.append(symbol)
                    else:
                        members.append(row)
                if missing:
                    continue
                total_wealth = sum(member["total_wealth"] for member in members)
                ending_equity = sum(member["ending_equity"] for member in members)
                vault = sum(member["vault_withdrawn"] for member in members)
                mean_size = sum(member["size_multiplier"] for member in members) / len(members)
                keep_count = sum(1 for member in members if member["verdict"] == "Keep")
                caution_count = sum(1 for member in members if member["verdict"] == "Caution")
                mean_max_dd = sum(member["max_drawdown_pct"] for member in members) / len(members)
                max_daily_loss = max(member["max_daily_loss_dollars"] for member in members)
                btc_weight = next((member["total_wealth"] for member in members if member["symbol"] == "BTC_USD"), 0.0)
                sleeve_rows.append(
                    {
                        "profile": profile_key,
                        "profile_label": profile["label"],
                        "withdrawal_mode": withdrawal_key,
                        "withdrawal_label": withdrawal["label"],
                        "sleeve": sleeve_key,
                        "sleeve_label": sleeve["label"],
                        "symbols": sleeve["symbols"],
                        "total_wealth": round(total_wealth, 2),
                        "ending_equity": round(ending_equity, 2),
                        "vault_withdrawn": round(vault, 2),
                        "net_pnl": round(total_wealth - 100_000.0 * len(members), 2),
                        "mean_size_multiplier": round(mean_size, 4),
                        "keep_count": keep_count,
                        "caution_count": caution_count,
                        "mean_max_drawdown_pct": round(mean_max_dd, 4),
                        "max_member_daily_loss_dollars": round(max_daily_loss, 2),
                        "btc_share_of_wealth": round(btc_weight / total_wealth, 4) if total_wealth > 0 else 0.0,
                    }
                )

    growth_leaders = sorted(sleeve_rows, key=lambda row: row["total_wealth"], reverse=True)[:12]
    payout_leaders = sorted(
        sleeve_rows,
        key=lambda row: (
            row["vault_withdrawn"],
            -row["mean_max_drawdown_pct"],
            row["total_wealth"],
        ),
        reverse=True,
    )[:12]
    balanced_leaders = sorted(
        sleeve_rows,
        key=lambda row: (
            row["keep_count"],
            -row["mean_max_drawdown_pct"],
            row["total_wealth"],
            -row["btc_share_of_wealth"],
        ),
        reverse=True,
    )[:12]

    payload = {
        "sleeves": SLEEVES,
        "rows": sleeve_rows,
        "growth_leaders": growth_leaders,
        "payout_leaders": payout_leaders,
        "balanced_leaders": balanced_leaders,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2))

    lines: list[str] = []
    lines.append("# Two-Year SIP Sleeve Comparison")
    lines.append("")
    lines.append("## Sleeve Definitions")
    lines.append("")
    for sleeve in SLEEVES.values():
        lines.append(f"- **{sleeve['label']}**: " + ", ".join(f"`{symbol}`" for symbol in sleeve["symbols"]))
    lines.append("")

    def add_section(title: str, rows: list[dict]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Profile | Withdrawal | Sleeve | Total Wealth $ | End Equity $ | Vault $ | Net PnL $ | Mean Size Mult | Keep | Caution | Mean Max DD % | BTC Share |")
        lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in rows:
            lines.append(
                f"| {row['profile_label']} | {row['withdrawal_label']} | {row['sleeve_label']} | "
                f"{_fmt_money(row['total_wealth'])} | {_fmt_money(row['ending_equity'])} | {_fmt_money(row['vault_withdrawn'])} | "
                f"{_fmt_money(row['net_pnl'])} | {row['mean_size_multiplier']:.2f} | {row['keep_count']} | {row['caution_count']} | "
                f"{_fmt_pct(row['mean_max_drawdown_pct'])} | {_fmt_pct(row['btc_share_of_wealth'])} |"
            )
        lines.append("")

    add_section("Max Growth Leaders", growth_leaders)
    add_section("Payout-Friendly Leaders", payout_leaders)
    add_section("Balanced Leaders", balanced_leaders)

    lines.append("## Read")
    lines.append("")
    lines.append("- `Total Wealth` = ending account equity plus withdrawn profit held in the vault.")
    lines.append("- `BTC Share` is the fraction of total sleeve wealth coming from the Bitcoin sleeve.")
    lines.append("- `Balanced` ranking prefers more `Keep` rows, lower mean drawdown, and less dependence on BTC alone.")
    OUTPUT_MD.write_text("\n".join(lines))

    print(
        json.dumps(
            {
                "rows_written": len(sleeve_rows),
                "report": str(OUTPUT_MD),
                "json": str(OUTPUT_JSON),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
