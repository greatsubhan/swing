import pandas as pd

from parabolic_exhaustion.discord_bot.formatter import AlertEvent, format_discord_message


def test_discord_formatter_includes_required_fields() -> None:
    event = AlertEvent(
        symbol="XAU_USD",
        timestamp=pd.Timestamp("2026-01-30 14:33:00+00:00"),
        state="ENTRY_TRIGGERED",
        setup_id="XAU_USD-20260130",
        side="short",
        reason="VWAP rejection after parabolic extension",
        entry_price=167.6,
        stop_price=168.1,
        first_target_price=166.2,
        kill_zone_name="new_york_kill_zone",
        alert_priority="high",
    )

    payload = format_discord_message(event)

    assert "XAU_USD" in payload["content"]
    assert "ENTRY_TRIGGERED" in payload["content"]
    assert "short" in payload["content"]
    assert "VWAP rejection after parabolic extension" in payload["content"]
    assert "Kill Zone: new_york_kill_zone" in payload["content"]
