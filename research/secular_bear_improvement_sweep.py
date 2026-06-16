"""Tune funded-account risk settings for the secular-bear strategy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.secular_bear_account_sim import OUTPUT_DIR, ensure_dir, simulate
from research.secular_bear_oanda_matrix import ASSETS
from signal_platform.env import load_dotenv

RISK_FRACTIONS = (0.01, 0.0075, 0.005, 0.0025)
INTERVALS = ("4h", "1d")


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for risk_fraction in RISK_FRACTIONS:
        for interval in INTERVALS:
            bucket = [row for row in rows if row["risk_fraction"] == risk_fraction and row["execution_interval"] == interval]
            survivors = [row for row in bucket if row["within_overall_limit"] and row["within_daily_limit"]]
            summary.append(
                {
                    "risk_fraction": risk_fraction,
                    "execution_interval": interval,
                    "symbols_tested": len(bucket),
                    "survivors": len(survivors),
                    "positive_survivors": len([row for row in survivors if row["net_pnl"] > 0]),
                    "mean_return_pct": round(sum(row["return_pct"] for row in bucket) / len(bucket), 2) if bucket else 0.0,
                    "mean_avg_r": round(sum(row["avg_r"] for row in bucket) / len(bucket), 3) if bucket else 0.0,
                    "mean_profit_factor": round(
                        sum(row["profit_factor"] for row in bucket if row["profit_factor"] is not None)
                        / len([row for row in bucket if row["profit_factor"] is not None]),
                        2,
                    )
                    if [row for row in bucket if row["profit_factor"] is not None]
                    else None,
                    "best_symbol": max(bucket, key=lambda row: row["net_pnl"])["symbol"] if bucket else None,
                    "best_symbol_return_pct": max(bucket, key=lambda row: row["net_pnl"])["return_pct"] if bucket else None,
                }
            )
    return summary


def main() -> None:
    load_dotenv(".env")
    ensure_dir(OUTPUT_DIR)

    rows: list[dict[str, object]] = []
    for asset in ASSETS:
        symbol = asset["symbol"]
        for interval in INTERVALS:
            for risk_fraction in RISK_FRACTIONS:
                result = simulate(symbol, interval, regime="alligator", risk_fraction=risk_fraction, kill_on_limits=False)
                result["category"] = asset["category"]
                rows.append(result)

    payload = {"runs": rows, "summary": summarize(rows)}
    output_path = OUTPUT_DIR / "improvement_sweep.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
