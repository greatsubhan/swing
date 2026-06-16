import asyncio

import pandas as pd

from parabolic_exhaustion.config import DiscordConfig
from parabolic_exhaustion.discord_bot.formatter import AlertEvent
from parabolic_exhaustion.discord_bot.publisher import DiscordAlertPublisher, InMemoryAlertSink


def test_alert_deduplication_is_per_setup(monkeypatch, tmp_path) -> None:
    async def _run() -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.test/webhook")
        sink = InMemoryAlertSink()
        publisher = DiscordAlertPublisher(
            config=DiscordConfig(),
            transport=sink,
            log_path=tmp_path / "discord_alert_log.csv",
        )

        first = AlertEvent(
            symbol="XAU_USD",
            timestamp=pd.Timestamp("2026-01-30 14:33:00+00:00"),
            state="ENTRY_TRIGGERED",
            setup_id="XAU_USD-20260130",
            side="short",
            reason="first setup",
        )
        duplicate = AlertEvent(
            symbol="XAU_USD",
            timestamp=pd.Timestamp("2026-01-30 14:34:00+00:00"),
            state="ENTRY_TRIGGERED",
            setup_id="XAU_USD-20260130",
            side="short",
            reason="duplicate same setup",
        )
        second_setup = AlertEvent(
            symbol="XAU_USD",
            timestamp=pd.Timestamp("2026-01-31 14:33:00+00:00"),
            state="ENTRY_TRIGGERED",
            setup_id="XAU_USD-20260131",
            side="short",
            reason="new setup",
        )

        first_result = await publisher.publish(first)
        duplicate_result = await publisher.publish(duplicate)
        second_result = await publisher.publish(second_setup)

        assert first_result.delivered is True
        assert duplicate_result.deduplicated is True
        assert second_result.delivered is True
        assert len(sink.payloads) == 2
        assert (tmp_path / "discord_alert_log.csv").exists()

    asyncio.run(_run())
