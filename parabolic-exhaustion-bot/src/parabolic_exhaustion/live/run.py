from __future__ import annotations

import argparse
import asyncio
import os

import pandas as pd

from parabolic_exhaustion.backtest.historical_validation import load_symbol_data
from parabolic_exhaustion.config import load_assets_config
from parabolic_exhaustion.live.env import load_env_file
from parabolic_exhaustion.live.oanda import OandaLiveDataProvider
from parabolic_exhaustion.live.profiles import PROJECT_ROOT, build_live_engine_for_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a live paper-alert profile.")
    parser.add_argument("--profile", required=True, help="Profile name from config/strategy.yaml")
    parser.add_argument("--provider", choices=["oanda"], default="oanda", help="Live data provider")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional .env file to load before starting the live runner.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Optional cap on processed bar events for smoke testing.",
    )
    return parser


async def _run(profile_name: str, provider_name: str, max_events: int | None) -> None:
    runtime, engine, _publisher = build_live_engine_for_profile(profile_name, project_root=PROJECT_ROOT)
    assets_config = load_assets_config(PROJECT_ROOT / "config" / "assets.yaml")
    asset_class_by_symbol = {instrument.symbol: instrument.asset_class for instrument in assets_config.instruments}
    symbols = runtime.profile.markets
    daily_frames = [
        load_symbol_data(symbol, asset_class=asset_class_by_symbol[symbol]).daily_bars
        for symbol in symbols
    ]
    daily_bars = daily_frames[0] if len(daily_frames) == 1 else pd.concat(daily_frames, ignore_index=True)

    if provider_name != "oanda":
        raise ValueError(f"Unsupported live provider: {provider_name}")
    if not os.getenv("OANDA_API_TOKEN"):
        raise EnvironmentError("OANDA_API_TOKEN is required for the OANDA live provider.")

    provider = OandaLiveDataProvider()
    await engine.run(
        live_provider=provider,
        daily_bars=daily_bars,
        symbols=symbols,
        timeframes=("1m", "5m"),
        max_events=max_events,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    load_env_file(args.env_file)
    asyncio.run(_run(args.profile, args.provider, args.max_events))


if __name__ == "__main__":
    main()
