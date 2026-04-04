"""CLI entrypoint for the multi-strategy signal platform."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .dispatchers import send_discord_webhook
from .env import load_dotenv
from .models import PlatformSignal
from .registry import get_strategy, list_strategies
from .runtime import run_platform_config, serve_platform_config
from .strategies import StrategyScanRequest


def _default_test_webhook(strategy_id: str) -> str | None:
    normalized = strategy_id.lower()
    if normalized == "little_rzy":
        return os.getenv("DISCORD_WEBHOOK_URL_LITTLE_RZY") or os.getenv("DISCORD_WEBHOOK_URL")
    if normalized == "strategy_two":
        return os.getenv("DISCORD_WEBHOOK_URL_STRATEGY_TWO") or os.getenv("DISCORD_WEBHOOK_URL")
    return os.getenv("DISCORD_WEBHOOK_URL")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-strategy signal platform")
    parser.add_argument("--env-file", default=".env", help="Optional .env file to load before running commands")
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

    serve_parser = subparsers.add_parser("serve", help="Run enabled routes repeatedly on their configured intervals")
    serve_parser.add_argument("--config", required=True, help="Path to JSON config file")
    serve_parser.add_argument("--oanda-token", default=None)
    serve_parser.add_argument("--poll-seconds", type=int, default=30, help="How often to wake up and check route schedules")
    serve_parser.add_argument("--max-cycles", type=int, default=None, help="Optional limit for test runs")
    serve_parser.add_argument("--no-run-immediately", action="store_true", help="Wait a full interval before first run")

    test_parser = subparsers.add_parser("test-discord", help="Send a sample Discord webhook message")
    test_parser.add_argument("--webhook-url", default=None, help="Discord webhook URL; defaults to DISCORD_WEBHOOK_URL_LITTLE_RZY or DISCORD_WEBHOOK_URL")
    test_parser.add_argument("--strategy", default="little_rzy")
    test_parser.add_argument("--symbol", default="WTICO_USD")
    test_parser.add_argument("--timeframe", default="4h")
    test_parser.add_argument("--side", choices=["long", "short"], default="long")

    args = parser.parse_args()
    load_dotenv(args.env_file)

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

    if args.command == "run-config":
        results = run_platform_config(args.config, token=args.oanda_token)
        print(json.dumps(results, indent=2))
        return

    if args.command == "test-discord":
        webhook_url = args.webhook_url or _default_test_webhook(args.strategy)
        if not webhook_url:
            raise SystemExit("No Discord webhook URL provided. Pass --webhook-url or set the strategy webhook in .env.")
        strategy = get_strategy(args.strategy)
        signal = PlatformSignal(
            strategy_id=args.strategy,
            strategy_name=strategy.strategy_name,
            symbol=args.symbol,
            asset_class="test",
            timeframe=args.timeframe,
            side=args.side,
            timestamp="2026-04-03T00:00:00+00:00",
            setup_id="platform-test-message",
            summary="This is a test alert from the multi-strategy signal platform.",
            alert_text="Test Discord alert",
            quality_score=88,
            quality_grade="A",
            risk_reward=2.4,
            entry=100.0,
            stop_loss=98.5,
            target_1=103.6,
        )
        send_discord_webhook(webhook_url, signal, username=f"{strategy.strategy_name} Preview")
        print(json.dumps({"status": "ok", "message": "Discord test alert sent."}, indent=2))
        return

    results = serve_platform_config(
        args.config,
        token=args.oanda_token,
        poll_seconds=args.poll_seconds,
        max_cycles=args.max_cycles,
        run_immediately=not args.no_run_immediately,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
