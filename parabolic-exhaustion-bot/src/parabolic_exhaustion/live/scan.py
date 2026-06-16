from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd

from parabolic_exhaustion.live.env import load_env_file
from parabolic_exhaustion.live.oanda import OandaLiveDataProvider
from parabolic_exhaustion.live.profiles import PROJECT_ROOT, build_live_engine_for_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a one-shot live scan for a parabolic paper profile.")
    parser.add_argument("--profile", required=True, help="Profile name from config/strategy.yaml")
    parser.add_argument("--provider", choices=["oanda"], default="oanda", help="Live data provider")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional .env file to load before starting the scan.",
    )
    parser.add_argument("--daily-count", type=int, default=160, help="Number of recent daily bars to fetch.")
    parser.add_argument("--intraday-1m-count", type=int, default=240, help="Number of recent 1m bars to fetch.")
    parser.add_argument("--intraday-5m-count", type=int, default=96, help="Number of recent 5m bars to fetch.")
    return parser


async def run_one_shot_scan(
    *,
    profile_name: str,
    provider_name: str,
    env_file: str | Path | None,
    project_root: Path = PROJECT_ROOT,
    daily_count: int = 160,
    intraday_1m_count: int = 240,
    intraday_5m_count: int = 96,
    provider: Any | None = None,
) -> dict[str, object]:
    load_env_file(env_file)
    runtime, engine, _publisher = build_live_engine_for_profile(profile_name, project_root=project_root)

    if provider_name != "oanda":
        raise ValueError(f"Unsupported live provider: {provider_name}")
    live_provider = provider or OandaLiveDataProvider()
    try:
        symbols = runtime.profile.markets
        daily_frames = []
        for symbol in symbols:
            daily_frame = await live_provider.get_recent_bars(symbol, "1d", count=daily_count)
            if not daily_frame.empty:
                daily_frames.append(daily_frame.drop(columns=["timeframe"], errors="ignore"))
        daily_bars = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
        candidates = engine.refresh_daily_candidates(daily_bars) if not daily_bars.empty else pd.DataFrame()

        summary_rows: list[dict[str, object]] = []
        total_alerts = 0
        for symbol in symbols:
            bars_5m = await live_provider.get_recent_bars(symbol, "5m", count=intraday_5m_count)
            bars_1m = await live_provider.get_recent_bars(symbol, "1m", count=intraday_1m_count)

            for _, row in bars_5m.iterrows():
                await engine.process_bar_with_options(row, publish_alerts=False, persist_outputs=False)

            if not bars_1m.empty:
                for _, row in bars_1m.iloc[:-1].iterrows():
                    await engine.process_bar_with_options(row, publish_alerts=False, persist_outputs=False)
                alert_results = await engine.process_bar_with_options(
                    bars_1m.iloc[-1],
                    publish_alerts=True,
                    persist_outputs=True,
                )
            else:
                alert_results = []

            state = engine.symbol_states.get(symbol)
            total_alerts += sum(1 for result in alert_results if result.delivered)
            candidate_row = (
                candidates.loc[candidates["symbol"] == symbol].sort_values("timestamp").tail(1)
                if not candidates.empty
                else pd.DataFrame()
            )
            summary_rows.append(
                {
                    "symbol": symbol,
                    "candidate_active": not candidate_row.empty,
                    "candidate_timestamp": candidate_row["timestamp"].iloc[0] if not candidate_row.empty else None,
                    "current_state": getattr(getattr(state, "current_state", None), "name", "NO_SETUP"),
                    "alerts_delivered": sum(1 for result in alert_results if result.delivered),
                    "alerts_suppressed": sum(1 for result in alert_results if result.deduplicated),
                    "last_bar_timestamp_1m": getattr(state, "last_bar_timestamp_1m", None),
                    "last_bar_timestamp_5m": getattr(state, "last_bar_timestamp_5m", None),
                    "forward_test_log_path": str(runtime.forward_test_log_path),
                }
            )

        summary = {
            "profile": runtime.name,
            "strategy_type": runtime.profile.strategy_type,
            "provider": provider_name,
            "symbols": symbols,
            "rows": summary_rows,
            "total_alerts_delivered": total_alerts,
            "output_dir": str(runtime.output_dir),
        }
        summary_path = runtime.output_dir / "scan_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(_json_ready(summary), indent=2), encoding="utf-8")
        return summary
    finally:
        client = getattr(live_provider, "client", None)
        if provider is None and client is not None:
            await client.aclose()


def _json_ready(value: object) -> object:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    summary = asyncio.run(
        run_one_shot_scan(
            profile_name=args.profile,
            provider_name=args.provider,
            env_file=args.env_file,
            daily_count=args.daily_count,
            intraday_1m_count=args.intraday_1m_count,
            intraday_5m_count=args.intraday_5m_count,
        )
    )
    print(json.dumps(_json_ready(summary), indent=2))


if __name__ == "__main__":
    main()
