"""CLI entrypoint for the multi-strategy signal platform."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import get_strategy, list_strategies
from .runtime import run_platform_config
from .strategies import StrategyScanRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-strategy signal platform")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-strategies", help="List registered strategies")
    list_parser.set_defaults(command="list-strategies")

    scan_parser = subparsers.add_parser("scan", help="Scan one strategy once")
    scan_parser.add_argument("--strategy", required=True, help="Registered strategy id")
    scan_parser.add_argument("--watchlist", default=None, help="Strategy watchlist name")
    scan_parser.add_argument("--granularity", default="H4")
    scan_parser.add_argument("--higher-timeframe", default="1d")
    scan_parser.add_argument("--oanda-env", choices=["practice", "live"], default="practice")
    scan_parser.add_argument("--oanda-price", choices=["M", "B", "A"], default="M")
    scan_parser.add_argument("--oanda-token", default=None)
    scan_parser.add_argument("--out", default="platform_output")
    scan_parser.add_argument("--disable-auto-profile", action="store_true")

    run_parser = subparsers.add_parser("run-config", help="Run all enabled configured strategy routes")
    run_parser.add_argument("--config", required=True, help="Path to JSON config file")
    run_parser.add_argument("--oanda-token", default=None)

    args = parser.parse_args()

    if args.command == "list-strategies":
        rows = [
            {
                "strategy_id": strategy.strategy_id,
                "strategy_name": strategy.strategy_name,
                "default_watchlist": strategy.default_watchlist,
            }
            for strategy in list_strategies()
        ]
        print(json.dumps(rows, indent=2))
        return

    if args.command == "scan":
        strategy = get_strategy(args.strategy)
        request = StrategyScanRequest(
            watchlist=args.watchlist or strategy.default_watchlist,
            granularity=args.granularity,
            higher_timeframe=args.higher_timeframe,
            environment=args.oanda_env,
            token=args.oanda_token,
            price=args.oanda_price,
            output_dir=Path(args.out),
            use_market_profile=not args.disable_auto_profile,
        )
        result = strategy.scan(request)
        summary = {
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.strategy_name,
            "watchlist": request.watchlist,
            "rows": len(result.rows),
            "signals_found": len(result.signals),
            "alerts_found": sum(1 for row in result.rows if row.get("alert")),
            "output_dir": args.out,
        }
        print(json.dumps(summary, indent=2))
        return

    results = run_platform_config(args.config, token=args.oanda_token)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
