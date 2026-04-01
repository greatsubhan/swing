"""CLI for running a quick Little RZY backtest."""
from __future__ import annotations

import argparse

from .workflows import make_synthetic_ohlcv, run_backtest, run_backtest_from_csv, save_backtest_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Little RZY backtest runner")
    parser.add_argument("--csv", type=str, default=None, help="Optional OHLCV CSV path")
    parser.add_argument("--timestamp-col", type=str, default="timestamp")
    parser.add_argument("--out", type=str, default="backtest_output")
    args = parser.parse_args()

    if args.csv:
        signals, trade_log, summary = run_backtest_from_csv(args.csv, args.timestamp_col)
    else:
        df = make_synthetic_ohlcv()
        signals, trade_log, summary = run_backtest(df)

    save_backtest_outputs(args.out, trade_log, summary)
    print(f"Signals: {len(signals)}")
    print(f"Trades: {summary.trades}, WinRate: {summary.win_rate:.2%}, AvgR: {summary.avg_r:.3f}")
    print(f"Outputs written to: {args.out}")


if __name__ == "__main__":
    main()
