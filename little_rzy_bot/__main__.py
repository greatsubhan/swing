"""CLI for running Little RZY backtests, research batches, and live scans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import EngineConfig
from .market_data import fetch_oanda_ohlcv, fetch_yahoo_ohlcv, save_ohlcv_csv
from signal_platform.env import load_dotenv
from .scanner import save_scan_outputs, scan_oanda_symbols
from .watchlists import resolve_watchlist
from .workflows import make_synthetic_ohlcv, run_backtest, run_backtest_from_csv, save_backtest_outputs
from .research import run_research_config


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Little RZY backtest runner")
    parser.add_argument("--scan", action="store_true", help="Scan live OANDA watchlist symbols and emit latest signals")
    parser.add_argument("--watchlist", type=str, default="primary-4h", help="Named watchlist for scan mode")
    parser.add_argument("--csv", type=str, default=None, help="Optional OHLCV CSV path")
    parser.add_argument("--timestamp-col", type=str, default="timestamp")
    parser.add_argument("--out", type=str, default="backtest_output")
    parser.add_argument("--provider", choices=["yahoo", "oanda"], default=None, help="Optional market data provider to fetch from before backtesting")
    parser.add_argument("--symbol", type=str, default=None, help="Yahoo ticker or OANDA instrument")
    parser.add_argument("--start", type=str, default=None, help="Start datetime/date, e.g. 2024-01-01 or 2024-01-01T00:00:00Z")
    parser.add_argument("--end", type=str, default=None, help="End datetime/date, e.g. 2024-12-31 or 2024-12-31T00:00:00Z")
    parser.add_argument("--period", type=str, default="1y", help="Yahoo-only period when start/end are omitted")
    parser.add_argument("--interval", type=str, default="1d", help="Yahoo interval, e.g. 1d, 1h, 15m")
    parser.add_argument("--granularity", type=str, default="H1", help="OANDA granularity, e.g. M15, H1, H4, D")
    parser.add_argument("--oanda-price", choices=["M", "B", "A"], default="M", help="OANDA candle price type: mid, bid, or ask")
    parser.add_argument("--oanda-env", choices=["practice", "live"], default="practice")
    parser.add_argument("--oanda-token", type=str, default=None, help="Optional OANDA token override; otherwise uses OANDA_API_TOKEN")
    parser.add_argument("--save-csv", type=str, default=None, help="Optional path to persist fetched OHLCV before backtesting")
    parser.add_argument("--asset-class", type=str, default=None, help="Override asset class used in signals")
    parser.add_argument("--timeframe", type=str, default=None, help="Override timeframe label used in signals")
    parser.add_argument("--higher-timeframe", type=str, default="1d", help="Higher timeframe label used in signals")
    parser.add_argument("--disable-auto-profile", action="store_true", help="Disable built-in market-specific tuning profiles")
    parser.add_argument("--commission-per-trade", type=float, default=0.0, help="Fixed currency commission per round trip")
    parser.add_argument("--spread-points", type=float, default=0.0, help="Spread in raw price points")
    parser.add_argument("--slippage-points", type=float, default=0.0, help="Adverse slippage in raw price points per fill")
    parser.add_argument("--max-open-risk", type=float, default=None, help="Max simultaneous open risk across trades, measured in R")
    parser.add_argument("--max-trades-per-day", type=int, default=None, help="Max accepted trades per calendar day")
    parser.add_argument("--max-trades-per-symbol-per-day", type=int, default=None, help="Max accepted trades per symbol per calendar day")
    parser.add_argument("--max-daily-drawdown", type=float, default=None, help="Stop taking new trades after this realized daily drawdown in R")
    parser.add_argument("--export-trades-csv", type=str, default=None, help="Optional path to write the enriched per-trade CSV")
    parser.add_argument("--use-htf-bias", action="store_true", help="Require higher-timeframe bias alignment for the test run")
    parser.add_argument("--htf-granularity", type=str, default=None, help="Override higher-timeframe granularity when HTF bias is enabled")
    return parser


def _apply_cli_overrides(cfg: EngineConfig, args: argparse.Namespace) -> EngineConfig:
    cfg.risk.commission_per_trade = args.commission_per_trade
    cfg.risk.spread_points = args.spread_points
    cfg.risk.slippage_points = args.slippage_points
    cfg.portfolio.max_open_risk = args.max_open_risk
    cfg.portfolio.max_trades_per_day = args.max_trades_per_day
    cfg.portfolio.max_trades_per_symbol_per_day = args.max_trades_per_symbol_per_day
    cfg.portfolio.max_daily_drawdown = args.max_daily_drawdown
    if args.use_htf_bias:
        cfg.execution.use_htf_bias = True
        cfg.execution.htf_granularity = args.htf_granularity or args.higher_timeframe
        cfg.require_higher_timeframe_confirmation = True
    return cfg


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    load_dotenv(".env")
    if argv[:1] == ["research"]:
        parser = argparse.ArgumentParser(description="Little RZY research runner")
        parser.add_argument("research")
        parser.add_argument("--config", required=True, help="Path to a research JSON config")
        args = parser.parse_args(argv)
        results = run_research_config(args.config)
        print(json.dumps(results, indent=2))
        return

    parser = _build_legacy_parser()
    args = parser.parse_args(argv)

    fetched_csv_path = None

    try:
        cfg = _apply_cli_overrides(EngineConfig(), args)
        if args.scan:
            symbols = resolve_watchlist(args.watchlist)
            results = scan_oanda_symbols(
                symbols=symbols,
                granularity=args.granularity,
                higher_timeframe=args.htf_granularity or args.higher_timeframe,
                environment=args.oanda_env,
                token=args.oanda_token,
                price=args.oanda_price,
                use_market_profile=not args.disable_auto_profile,
                base_config=cfg,
            )
            save_scan_outputs(args.out, results)
            print(f"Scanned {len(symbols)} symbols from watchlist: {args.watchlist}")
            print(f"Alerts generated: {sum(1 for row in results if row['alert'])}")
            print(f"Outputs written to: {args.out}")
            return
        if args.provider:
            if not args.symbol:
                raise SystemExit("--symbol is required when --provider is used.")

            if args.provider == "yahoo":
                fetched = fetch_yahoo_ohlcv(
                    symbol=args.symbol,
                    interval=args.interval,
                    start=args.start,
                    end=args.end,
                    period=args.period,
                )
            else:
                fetched = fetch_oanda_ohlcv(
                    instrument=args.symbol,
                    granularity=args.granularity,
                    start=args.start,
                    end=args.end,
                    price=args.oanda_price,
                    token=args.oanda_token,
                    environment=args.oanda_env,
                )

            csv_path = args.save_csv or str(Path(args.out) / "fetched_ohlcv.csv")
            fetched_csv_path = save_ohlcv_csv(fetched.df, csv_path)
            signals, trade_log, summary, diagnostics = run_backtest(
                fetched.df,
                symbol=fetched.symbol,
                asset_class=args.asset_class or fetched.asset_class,
                timeframe=args.timeframe or fetched.timeframe,
                higher_timeframe=args.htf_granularity or args.higher_timeframe,
                config=cfg,
                use_market_profile=not args.disable_auto_profile,
            )
        elif args.csv:
            signals, trade_log, summary, diagnostics = run_backtest_from_csv(args.csv, args.timestamp_col)
        else:
            df = make_synthetic_ohlcv()
            signals, trade_log, summary, diagnostics = run_backtest(
                df,
                config=cfg,
                higher_timeframe=args.htf_granularity or args.higher_timeframe,
                use_market_profile=not args.disable_auto_profile,
            )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    save_backtest_outputs(
        args.out,
        trade_log,
        summary,
        diagnostics=diagnostics,
        signals=signals,
        export_trades_csv=args.export_trades_csv,
    )
    if fetched_csv_path:
        print(f"Fetched OHLCV saved to: {fetched_csv_path}")
    print(f"Signals: {len(signals)}")
    print(f"Trades: {summary.trades}, WinRate: {summary.win_rate:.2%}, AvgR: {summary.avg_r:.3f}")
    print(f"Outputs written to: {args.out}")


if __name__ == "__main__":
    main()
