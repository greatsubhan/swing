import asyncio

import pandas as pd

from parabolic_exhaustion.config import BacktestConfig, DiscordConfig, StrategyConfig
from parabolic_exhaustion.discord_bot.publisher import DiscordAlertPublisher, InMemoryAlertSink
from parabolic_exhaustion.live.engine import LiveSignalEngine


def test_live_pipeline_emits_expected_alert_sequence(tmp_path, monkeypatch) -> None:
    async def _run() -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.test/webhook")
        strategy = StrategyConfig()
        strategy.sessions["new_york"].end_time = "09:37"
        strategy.risk.partial_take_r = 1.0

        backtest = BacktestConfig()
        backtest.target_r = 2.0
        backtest.force_exit_minutes_before_close = 0
        sink = InMemoryAlertSink()
        publisher = DiscordAlertPublisher(
            config=DiscordConfig(),
            transport=sink,
            log_path=tmp_path / "discord_alert_log.csv",
        )
        engine = LiveSignalEngine(
            strategy_config=strategy,
            backtest_config=backtest,
            discord_config=DiscordConfig(),
            publisher=publisher,
            output_dir=tmp_path,
            profile_name="NAS100_PARABOLIC_PAPER",
            parameter_set_id="idx_ps07_baseline_on",
            forward_test_log_path=tmp_path / "forward_test_log_parabolic.csv",
        )
        engine.refresh_daily_candidates(_build_daily_bars())

        bars_5m = _build_5m_context()
        for _, row in bars_5m.iterrows():
            payload = row.copy()
            payload["timeframe"] = "5m"
            await engine.process_bar(payload)

        bars_1m = _build_happy_path_1m()
        for _, row in bars_1m.iterrows():
            payload = row.copy()
            payload["timeframe"] = "1m"
            await engine.process_bar(payload)

        contents = "\n".join(payload["content"] for payload in sink.payloads)
        assert "EXHAUSTION_WATCH" in contents
        assert "ENTRY_TRIGGERED" in contents
        assert "PARTIAL_TAKEN" in contents
        assert "BREAK_EVEN_PROTECTED" in contents
        assert "EXITED" in contents
        assert (tmp_path / "live_state_transitions.csv").exists()
        assert (tmp_path / "discord_alert_log.csv").exists()
        forward_log = pd.read_csv(tmp_path / "forward_test_log_parabolic.csv")
        assert {"EXHAUSTION_WATCH", "ENTRY_TRIGGERED", "PARTIAL_TAKEN", "BREAK_EVEN_PROTECTED", "EXITED"}.issubset(
            set(forward_log["state"])
        )
        assert set(forward_log["parameter_set_id"]) == {"idx_ps07_baseline_on"}
        assert forward_log["realized_result_R"].notna().any()

    asyncio.run(_run())


def _build_daily_bars() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01", periods=30, freq="D")
    closes = [100, 101, 102, 103, 104, 104, 104, 105, 106, 108, 110, 113, 116, 120, 123, 126, 129, 133, 138, 143, 148, 150, 152, 154, 156, 158, 160, 162, 165, 168]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": closes,
            "high": [price + 1.5 for price in closes],
            "low": [price - 1.0 for price in closes],
            "close": closes,
            "volume": [1000 + (idx * 50) for idx in range(len(timestamps))],
            "asset_class": ["metal"] * len(timestamps),
        }
    )


def _build_happy_path_1m() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-30 14:30:00+00:00", periods=8, freq="min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": [168.0, 168.8, 168.4, 167.6, 167.3, 166.8, 166.4, 166.5],
            "high": [169.0, 169.4, 168.8, 168.1, 167.4, 167.5, 166.8, 166.7],
            "low": [167.8, 168.2, 167.5, 167.0, 166.1, 166.2, 166.0, 166.2],
            "close": [168.8, 168.4, 167.7, 167.4, 166.4, 166.5, 166.3, 166.4],
            "volume": [100, 110, 160, 200, 180, 220, 210, 150],
        }
    )


def _build_5m_context() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2026-01-30 14:30:00+00:00",
            "2026-01-30 14:35:00+00:00",
        ]
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD", "XAU_USD"],
            "open": [168.0, 166.8],
            "high": [169.4, 167.1],
            "low": [167.5, 165.8],
            "close": [167.7, 165.9],
            "volume": [750, 760],
        }
    )
