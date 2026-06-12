"""Compare the current CWT benchmark with Trend Current and Measured Drift.

This is a high-level benchmark comparison, not a perfectly apples-to-apples
portfolio simulation. The report is explicit about the scope differences.
"""
from __future__ import annotations

import json
from pathlib import Path

OUTPUT_DIR = Path("reports/cwt_forex")


def load_json(path: Path):
    return json.loads(path.read_text())


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    cwt = load_json(OUTPUT_DIR / "funded_ladder_sim_alt_0.07_0.20_0.45_1.00.json")
    trend_current_rows = load_json(Path("reports/secular_bear_static_funded/static_funded_results.json"))
    measured_drift = load_json(Path("reports/measured_drift_static_funded/static_funded_results.json"))

    trend_current_focus = [
        row for row in trend_current_rows
        if row["execution_interval"] == "4h"
        and row["symbol"] in {"USD_CHF", "ETH_USD", "AUD_CHF", "LTC_USD", "EUR_GBP", "EUR_USD", "XAG_USD", "USD_CAD"}
    ]

    measured_assets = measured_drift["assets"]

    report = {
        "cwt_benchmark": {
            "label": "CWT funded ladder benchmark",
            "date_range": "2025-01-01 to 2026-04-01",
            "scope_note": "portfolio simulation across four symbols with daily risk caps",
            "ending_balance": cwt["portfolio_summary"]["ending_balance"],
            "net_pnl_dollars": cwt["portfolio_summary"]["net_pnl_dollars"],
            "return_pct": cwt["portfolio_summary"]["return_pct"],
            "trades_taken": cwt["portfolio_summary"]["trades_taken"],
            "win_rate": cwt["portfolio_summary"]["win_rate"],
            "profit_factor": cwt["portfolio_summary"]["profit_factor"],
            "max_drawdown_dollars": cwt["portfolio_summary"]["max_drawdown_dollars"],
        },
        "trend_current_benchmark": {
            "label": "Trend Current benchmark basket",
            "date_range": "2020-01-01 to 2026-04-01",
            "scope_note": "per-asset static-funded simulations on the keep-list basket, not one rotating account",
            "assets_count": len(trend_current_focus),
            "mean_return_pct": round(average([row["return_pct"] for row in trend_current_focus]), 2),
            "mean_win_rate": round(average([row["win_rate"] for row in trend_current_focus]), 2),
            "mean_avg_r": round(average([row["avg_r"] for row in trend_current_focus]), 3),
            "mean_profit_factor": round(average([row["profit_factor"] for row in trend_current_focus if row["profit_factor"] is not None]), 2),
            "mean_reward_risk_ratio": round(average([row["reward_risk_ratio"] for row in trend_current_focus if row["reward_risk_ratio"] is not None]), 3),
            "mean_max_drawdown_dollars": round(average([row["max_drawdown_dollars"] for row in trend_current_focus]), 2),
        },
        "measured_drift_benchmark": {
            "label": "Measured Drift benchmark basket",
            "date_range": f"{measured_drift['period_start']} to {measured_drift['period_end_exclusive']}",
            "scope_note": "per-asset static-funded simulations on the production basket, not one rotating account",
            "assets_count": len(measured_assets),
            "mean_return_pct": round(average([row["return_pct"] for row in measured_assets]), 2),
            "mean_win_rate": round(average([row["win_rate"] for row in measured_assets]), 2),
            "mean_avg_r": round(average([row["avg_r"] for row in measured_assets]), 3),
            "mean_profit_factor": round(average([row["profit_factor"] for row in measured_assets if row["profit_factor"] is not None]), 2),
            "mean_reward_risk_ratio": round(average([row["reward_risk_ratio"] for row in measured_assets if row["reward_risk_ratio"] is not None]), 3),
            "mean_max_drawdown_dollars": round(average([row["max_drawdown_dollars"] for row in measured_assets]), 2),
        },
        "notes": [
            "CWT is the only result here that is currently modeled as one combined portfolio with daily caps.",
            "Trend Current and Measured Drift benchmark files are per-asset funded-style simulations, not one rotating portfolio.",
            "The comparison is useful for scale and quality, but not perfectly apples-to-apples.",
        ],
    }

    out_path = OUTPUT_DIR / "BENCHMARK_COMPARISON.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
