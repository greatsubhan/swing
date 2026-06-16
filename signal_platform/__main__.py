"""CLI entrypoint for the multi-strategy signal platform."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .discord_command_bot import run_discord_command_bot_sync
from .dispatchers import send_discord_webhook
from .env import load_dotenv
from .models import PlatformSignal
from .registry import get_strategy, list_strategies
from .runtime import run_configured_route, run_platform_config, serve_platform_config
from .strategies import StrategyScanRequest


def _default_test_webhook(strategy_id: str) -> str | None:
    normalized = strategy_id.lower()
    if normalized == "little_rzy":
        return os.getenv("DISCORD_WEBHOOK_URL_LITTLE_RZY") or os.getenv("DISCORD_WEBHOOK_URL")
    if normalized == "little_rzy_1h":
        return os.getenv("DISCORD_WEBHOOK_URL_LITTLE_RZY_1H") or os.getenv("DISCORD_WEBHOOK_URL_LITTLE_RZY") or os.getenv("DISCORD_WEBHOOK_URL")
    if normalized == "strategy_two":
        return os.getenv("DISCORD_WEBHOOK_URL_STRATEGY_TWO") or os.getenv("DISCORD_WEBHOOK_URL")
    if normalized == "strategy_four":
        return os.getenv("DISCORD_WEBHOOK_URL_CWT") or os.getenv("DISCORD_WEBHOOK_URL")
    if normalized == "strategy_five":
        return os.getenv("DISCORD_WEBHOOK_URL_SIP") or os.getenv("DISCORD_WEBHOOK_URL")
    return os.getenv("DISCORD_WEBHOOK_URL")


def _test_signal_defaults(strategy_id: str) -> dict[str, object]:
    normalized = strategy_id.lower()
    if normalized == "strategy_four":
        return {
            "symbol": "EUR_USD",
            "timeframe": "5m",
            "side": "short",
            "summary": (
                "CWT preview: Scenario 2 continuation with H1 bias aligned. "
                "Execution is on M5 or M15 only, never 4h."
            ),
            "raw_signal": {
                "scenario": "scenario2",
                "scenario_label": "Scenario 2",
                "bias_timeframe": "H1",
                "risk_label": "Recommended Risk Step",
                "risk_display": "0.07% (step 1/4)",
                "risk_fraction": 0.0007,
                "event_type": "entry",
                "stop_distance_pct": 0.03,
            },
            "quality_score": 74,
            "quality_grade": "C",
            "risk_reward": 1.0,
            "entry": 1.15188,
            "stop_loss": 1.15221,
            "target_1": 1.15155,
        }
    if normalized == "little_rzy_1h":
        return {
            "symbol": "NAS100_USD",
            "timeframe": "1h",
            "side": "long",
            "summary": (
                "Measured Drift 1H preview: lower-timeframe continuation setup with H4 bias, "
                "session filter, and volatility gating."
            ),
            "raw_signal": {
                "event_type": "entry",
                "scenario": "Measured Move 1H",
                "scenario_label": "Measured Move 1H",
                "bias_timeframe": "H4",
                "session": "london_new_york",
                "volatility_regime": "normal",
                "risk_label": "Setup Risk Guide",
                "risk_display": "User-sized",
                "stop_distance_pct": 0.9,
            },
            "quality_score": 81,
            "quality_grade": "B",
            "risk_reward": 1.4,
            "entry": 20125.0,
            "stop_loss": 19980.0,
            "target_1": 20328.0,
        }
    if normalized == "strategy_two":
        return {
            "symbol": "ETH_USD",
            "timeframe": "4h",
            "side": "short",
            "summary": (
                "Trend Current preview: 4h continuation basket aligned with the 1d trend, "
                "using structured invalidation and basket-style management."
            ),
            "raw_signal": {
                "event_type": "entry",
                "scenario": "Trend Pullback",
                "scenario_label": "Trend Pullback",
                "bias_timeframe": "1D",
                "risk_label": "Max Open Basket Risk",
                "risk_display": "1.00%",
                "risk_fraction": 0.01,
                "stop_distance_pct": 2.4,
            },
            "quality_score": 82,
            "quality_grade": "B",
            "risk_reward": 2.2,
            "entry": 2650.0,
            "stop_loss": 2715.0,
            "target_1": 2507.0,
        }
    if normalized == "strategy_five":
        return {
            "symbol": "Full Classic",
            "timeframe": "1mo",
            "side": "long",
            "summary": (
                "Secular Bull SIP preview: monthly sleeve allocation board using a Full Classic "
                "macro sleeve and payout-aware review logic."
            ),
            "raw_signal": {
                "event_type": "sip_allocation",
                "sleeve_label": "Full Classic",
                "allocation_month": "2026-04",
                "profile_label": "FTMO Swing style",
                "payout_label": "Skim 50% of month-end profit above $100k",
                "account_size": 100000.0,
                "monthly_budget_per_asset": 8333.33,
                "total_sleeve_budget": 25000.00,
                "active_legs": [
                    {"symbol": "XAU_USD", "price_reference": 3228.00, "monthly_budget": 8333.33, "reference_units": 2.5810},
                    {"symbol": "NAS100_USD", "price_reference": 19850.00, "monthly_budget": 8333.33, "reference_units": 0.4198},
                    {"symbol": "BTC_USD", "price_reference": 69400.00, "monthly_budget": 8333.33, "reference_units": 0.1201},
                ],
                "skipped_legs": [
                    {"symbol": "XAG_USD", "trend_label": "filter blocked"},
                    {"symbol": "US30_USD", "trend_label": "filter blocked"},
                ],
                "reference_research": {
                    "profile_label": "FTMO Swing",
                    "withdrawal_label": "Skim 50% of month-end profit above $100k",
                    "sleeve_label": "Full Classic",
                },
            },
            "quality_score": 80,
            "quality_grade": "B",
            "risk_reward": 1.0,
            "entry": 1.0,
            "stop_loss": 0.5,
            "target_1": 2.0,
        }
    return {
        "symbol": "WTICO_USD",
        "timeframe": "4h",
        "side": "long",
        "summary": (
            "Measured Drift preview: 4h measured-move continuation setup with the hybrid stop model "
            "and market-profile tuning."
        ),
        "raw_signal": {
            "event_type": "entry",
            "scenario": "Measured Move",
            "scenario_label": "Measured Move",
            "bias_timeframe": "1D",
            "risk_label": "Setup Risk Guide",
            "risk_display": "User-sized",
            "event_type": "entry",
            "stop_distance_pct": 1.6,
        },
        "quality_score": 88,
        "quality_grade": "A",
        "risk_reward": 2.4,
        "entry": 100.0,
        "stop_loss": 98.5,
        "target_1": 103.6,
    }


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
    scan_parser.add_argument("--log-signals", action="store_true")
    scan_parser.add_argument("--log-filtered-setups", action="store_true")
    scan_parser.add_argument("--signal-log-file", default=None)
    scan_parser.add_argument("--filtered-log-file", default=None)

    scan_route_parser = subparsers.add_parser(
        "scan-route",
        help="Run one configured Discord bot route once, including dispatch and state updates",
    )
    scan_route_parser.add_argument("--config", required=True, help="Path to JSON config file")
    scan_route_parser.add_argument("--strategy", required=True, help="Configured strategy route id")
    scan_route_parser.add_argument("--oanda-token", default=None)
    scan_route_parser.add_argument("--watchlist", default=None, help="Optional watchlist override")
    scan_route_parser.add_argument("--granularity", default=None, help="Optional timeframe override")
    scan_route_parser.add_argument("--higher-timeframe", default=None, help="Optional higher timeframe override")
    scan_route_parser.add_argument("--out", default=None, help="Optional output directory override")
    scan_route_parser.add_argument("--dispatch", choices=["discord", "none"], default=None)
    scan_route_parser.add_argument("--catch-up-hours", type=float, default=None, help="Optional recent-entry recovery window override")

    run_parser = subparsers.add_parser("run-config", help="Run all enabled configured strategy routes")
    run_parser.add_argument("--config", required=True, help="Path to JSON config file")
    run_parser.add_argument("--oanda-token", default=None)

    serve_parser = subparsers.add_parser("serve", help="Run enabled routes repeatedly on their configured intervals")
    serve_parser.add_argument("--config", required=True, help="Path to JSON config file")
    serve_parser.add_argument("--oanda-token", default=None)
    serve_parser.add_argument("--poll-seconds", type=int, default=30, help="How often to wake up and check route schedules")
    serve_parser.add_argument("--max-cycles", type=int, default=None, help="Optional limit for test runs")
    serve_parser.add_argument("--no-run-immediately", action="store_true", help="Wait a full interval before first run")

    command_bot_parser = subparsers.add_parser("command-bot", help="Run the lightweight Discord command bot")
    command_bot_parser.add_argument("--config", default="config/platform.example.json", help="Path to platform config file")
    command_bot_parser.add_argument("--bot-token", default=None, help="Discord bot token; defaults to DISCORD_BOT_TOKEN")

    test_parser = subparsers.add_parser("test-discord", help="Send a sample Discord webhook message")
    test_parser.add_argument("--webhook-url", default=None, help="Discord webhook URL; defaults to DISCORD_WEBHOOK_URL_LITTLE_RZY or DISCORD_WEBHOOK_URL")
    test_parser.add_argument("--strategy", default="little_rzy")
    test_parser.add_argument("--symbol", default=None)
    test_parser.add_argument("--timeframe", default=None)
    test_parser.add_argument("--side", choices=["long", "short"], default=None)

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
            strategy_id=args.strategy,
            watchlist=args.watchlist or strategy.default_watchlist,
            granularity=args.granularity,
            higher_timeframe=args.higher_timeframe,
            environment=args.oanda_env,
            token=args.oanda_token,
            price=args.oanda_price,
            output_dir=Path(args.out),
            use_market_profile=not args.disable_auto_profile,
            log_signals=args.log_signals,
            log_filtered_setups=args.log_filtered_setups,
            signal_log_file=args.signal_log_file,
            filtered_log_file=args.filtered_log_file,
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

    if args.command == "scan-route":
        summary = run_configured_route(
            args.config,
            strategy_id=args.strategy,
            token=args.oanda_token,
            watchlist=args.watchlist,
            granularity=args.granularity,
            higher_timeframe=args.higher_timeframe,
            output_dir=args.out,
            dispatch=args.dispatch,
            catch_up_hours=args.catch_up_hours,
        )
        print(json.dumps(summary, indent=2))
        return

    if args.command == "run-config":
        results = run_platform_config(args.config, token=args.oanda_token)
        print(json.dumps(results, indent=2))
        return

    if args.command == "command-bot":
        run_discord_command_bot_sync(token=args.bot_token, config_path=args.config)
        return

    if args.command == "test-discord":
        webhook_url = args.webhook_url or _default_test_webhook(args.strategy)
        if not webhook_url:
            raise SystemExit("No Discord webhook URL provided. Pass --webhook-url or set the strategy webhook in .env.")
        strategy = get_strategy(args.strategy)
        defaults = _test_signal_defaults(args.strategy)
        signal = PlatformSignal(
            strategy_id=args.strategy,
            strategy_name=strategy.strategy_name,
            symbol=str(args.symbol or defaults["symbol"]),
            asset_class="test",
            timeframe=str(args.timeframe or defaults["timeframe"]),
            side=str(args.side or defaults["side"]),
            timestamp="2026-04-03T00:00:00+00:00",
            setup_id="platform-test-message",
            summary=str(defaults["summary"]),
            alert_text="Test Discord alert",
            quality_score=int(defaults["quality_score"]),
            quality_grade=str(defaults["quality_grade"]),
            risk_reward=float(defaults["risk_reward"]),
            entry=float(defaults["entry"]),
            stop_loss=float(defaults["stop_loss"]),
            target_1=float(defaults["target_1"]),
            raw_signal=dict(defaults["raw_signal"]),
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
