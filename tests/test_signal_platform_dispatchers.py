from __future__ import annotations

from signal_platform.dispatchers import discord_payload, outcome_payload, report_payload
from signal_platform.models import JournalEntry, PlatformSignal


def test_discord_payload_formats_tactical_signal_cleanly() -> None:
    signal = PlatformSignal(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="short",
        timestamp="2026-04-14T00:00:00+00:00",
        setup_id="cwt-1",
        summary="Scenario 2 short continuation under H1 bias.",
        alert_text="alert",
        quality_score=8,
        quality_grade="A",
        risk_reward=1.0,
        entry=1.15188,
        stop_loss=1.15221,
        target_1=1.15155,
        raw_signal={
            "event_type": "entry",
            "scenario_label": "Scenario 2",
            "bias_timeframe": "H1",
            "risk_label": "Recommended Risk Step",
            "risk_display": "0.07% (step 1/4)",
            "basket_id": "basket-1",
            "tranche_id": "tranche-1",
            "stats_snapshot": {
                "total_signals": 10,
                "tp_hits": 4,
                "sl_hits": 3,
                "open_signals": 3,
                "total_realized_r": 1.25,
            },
        },
    )

    payload = discord_payload(signal)

    assert "Cambist With Trend" in payload["content"]
    embed = payload["embeds"][0]
    assert "EUR_USD" in embed["title"]
    field_names = {field["name"] for field in embed["fields"]}
    assert "Entry" in field_names
    assert "Stop" in field_names
    assert "Live Record" in field_names


def test_discord_payload_formats_reinforcement_update_cleanly() -> None:
    signal = PlatformSignal(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        symbol="AUD_USD",
        asset_class="forex",
        timeframe="5m",
        side="long",
        timestamp="2026-04-15T01:00:00+00:00",
        setup_id="cwt-2",
        summary="Structure still holds. Strength is now 66/100 after 1 reinforcement. No new trade.",
        alert_text="alert",
        quality_score=84,
        quality_grade="A",
        risk_reward=1.0,
        entry=0.651,
        stop_loss=0.6495,
        target_1=0.6525,
        is_tradable=False,
        structure_id="strategy_four:AUD_USD:5m:long:root-1",
        root_signal_id="root-1",
        reinforcement_count=1,
        strength_score=66,
        raw_signal={
            "event_type": "reinforcement",
            "root_signal_id": "root-1",
            "structure_id": "strategy_four:AUD_USD:5m:long:root-1",
            "reinforcement_components": [
                "quality_score_improved",
                "continuation_confirmed",
                "structure_holds",
                "htf_alignment_maintained",
            ],
            "r_scaling_enabled": False,
        },
    )

    payload = discord_payload(signal)

    embed = payload["embeds"][0]
    field_names = {field["name"] for field in embed["fields"]}
    assert "Reference Signal" in field_names
    assert "Strength" in field_names
    assert "Trade Action" in field_names
    assert "No new trade" in next(field["value"] for field in embed["fields"] if field["name"] == "Trade Action")


def test_outcome_payload_supports_break_even_wording() -> None:
    entry = JournalEntry(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        setup_id="cwt-1",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="short",
        signal_timestamp="2026-04-14T00:00:00+00:00",
        dispatched_at_utc="2026-04-14T00:01:00+00:00",
        entry=1.15188,
        stop_loss=1.15221,
        target_1=1.15155,
        risk_reward=1.0,
        quality_score=8,
        quality_grade="A",
        status="closed",
        outcome="break_even",
        outcome_timestamp="2026-04-14T01:00:00+00:00",
        exit_price=1.15188,
        bars_checked=8,
    )

    payload = outcome_payload(entry)
    assert "Break-even" in payload["content"]
    embed = payload["embeds"][0]
    assert embed["fields"][3]["value"] == "0.00R"


def test_report_payload_uses_clean_lists() -> None:
    payload = report_payload(
        {
            "period_label": "Weekly 2026-W15",
            "signals_sent": 4,
            "tp_hits": 2,
            "sl_hits": 1,
            "open_count": 1,
            "total_realized_r": 1.5,
            "avg_closed_r_text": "0.50R",
            "avg_hold_text": "8.0h",
            "tp_list": ["EUR_USD (1.00R)"],
            "sl_list": ["GBP_USD (-1.00R)"],
            "open_list": ["XAU_USD"],
        }
    )
    embed = payload["embeds"][0]
    assert "Weekly" in embed["title"]
    assert "EUR_USD" in embed["fields"][7]["value"]
