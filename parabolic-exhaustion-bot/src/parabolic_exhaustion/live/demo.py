from __future__ import annotations

import argparse
import asyncio

import pandas as pd

from parabolic_exhaustion.discord_bot.formatter import AlertEvent
from parabolic_exhaustion.live.env import load_env_file
from parabolic_exhaustion.live.profiles import PROJECT_ROOT, build_live_engine_for_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send a demo Discord alert for a live paper profile.")
    parser.add_argument("--profile", required=True, help="Profile name from config/strategy.yaml")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional .env file to load before publishing the demo alert.",
    )
    parser.add_argument(
        "--state",
        default="ENTRY_TRIGGERED",
        help="Alert state label to use for the synthetic demo event.",
    )
    return parser


async def _run(profile_name: str, env_file: str | None, state: str) -> None:
    load_env_file(env_file)
    runtime, _engine, publisher = build_live_engine_for_profile(profile_name, project_root=PROJECT_ROOT)
    timestamp = pd.Timestamp.now(tz="UTC")
    event = AlertEvent(
        symbol=runtime.profile.markets[0],
        timestamp=timestamp,
        state=state,
        setup_id=f"demo-{timestamp.strftime('%Y%m%d%H%M%S')}",
        side="short",
        reason="Demo signal from the NAS100 parabolic paper-forward pipeline.",
        entry_price=20350.0,
        stop_price=20410.0,
        first_target_price=20280.0,
        kill_zone_name="new_york",
        alert_priority="normal",
    )
    result = await publisher.publish(event)
    if not result.delivered:
        raise RuntimeError(f"Demo alert was not delivered: {result.message}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args.profile, args.env_file, args.state))


if __name__ == "__main__":
    main()
