import asyncio

import pandas as pd

from parabolic_exhaustion.config import BacktestConfig, DiscordConfig, PaperProfileConfig, StrategyConfig
from parabolic_exhaustion.discord_bot.publisher import DiscordAlertPublisher, InMemoryAlertSink
from parabolic_exhaustion.live.engine import LiveSignalEngine
from parabolic_exhaustion.live.profiles import LiveProfileRuntime
from parabolic_exhaustion.live.scan import run_one_shot_scan


class FakeRecentBarsProvider:
    async def get_recent_bars(self, symbol: str, timeframe: str, *, count: int) -> pd.DataFrame:
        if timeframe == "1d":
            return pd.DataFrame(columns=["timestamp", "symbol", "open", "high", "low", "close", "volume", "timeframe"])
        timestamps = pd.to_datetime(
            [
                "2026-01-30 14:30:00+00:00",
                "2026-01-30 14:31:00+00:00",
            ]
            if timeframe == "1m"
            else [
                "2026-01-30 14:30:00+00:00",
                "2026-01-30 14:35:00+00:00",
            ]
        )
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "symbol": [symbol] * len(timestamps),
                "open": [20000.0] * len(timestamps),
                "high": [20010.0] * len(timestamps),
                "low": [19990.0] * len(timestamps),
                "close": [20005.0] * len(timestamps),
                "volume": [100.0] * len(timestamps),
                "timeframe": [timeframe] * len(timestamps),
            }
        )


def test_run_one_shot_scan_writes_summary_without_replaying_history(tmp_path, monkeypatch) -> None:
    async def _run() -> None:
        strategy = StrategyConfig()
        backtest = BacktestConfig()
        discord = DiscordConfig(enabled=False)
        profile = PaperProfileConfig(markets=["NAS100_USD"])
        runtime = LiveProfileRuntime(
            name="NAS100_PARABOLIC_PAPER",
            profile=profile,
            strategy_config=strategy,
            backtest_config=backtest,
            discord_config=discord,
            output_dir=tmp_path,
            forward_test_log_path=tmp_path / "forward_test_log_parabolic.csv",
        )
        publisher = DiscordAlertPublisher(
            config=discord,
            transport=InMemoryAlertSink(),
            log_path=tmp_path / "discord_alert_log.csv",
        )
        engine = LiveSignalEngine(
            strategy_config=strategy,
            backtest_config=backtest,
            discord_config=discord,
            publisher=publisher,
            output_dir=tmp_path,
            profile_name=runtime.name,
            parameter_set_id=profile.parameter_set_id,
            forward_test_log_path=runtime.forward_test_log_path,
        )

        monkeypatch.setattr(
            "parabolic_exhaustion.live.scan.build_live_engine_for_profile",
            lambda profile_name, project_root: (runtime, engine, publisher),
        )

        summary = await run_one_shot_scan(
            profile_name="NAS100_PARABOLIC_PAPER",
            provider_name="oanda",
            env_file=None,
            project_root=tmp_path,
            provider=FakeRecentBarsProvider(),
        )

        assert summary["profile"] == "NAS100_PARABOLIC_PAPER"
        assert summary["total_alerts_delivered"] == 0
        assert summary["rows"][0]["symbol"] == "NAS100_USD"
        assert summary["rows"][0]["candidate_active"] is False
        assert (tmp_path / "scan_summary.json").exists()

    asyncio.run(_run())
