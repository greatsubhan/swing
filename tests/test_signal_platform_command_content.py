from __future__ import annotations

import json

from signal_platform.command_content import (
    build_boards_text,
    build_help_text,
    build_ladder_text,
    build_recent_text,
    build_status_text,
    build_strategy_text,
    parse_command_message,
    resolve_strategy_card,
)


def test_parse_command_message_supports_plain_prefixed_and_alias_forms() -> None:
    assert parse_command_message("strategy cwt") == ("strategy", "cwt")
    assert parse_command_message("!status") == ("status", None)
    assert parse_command_message("health cwt") == ("status", "cwt")
    assert parse_command_message("/help") == ("help", None)
    assert parse_command_message("scan trend") == ("scan", "trend")
    assert parse_command_message("boards") == ("boards", None)
    assert parse_command_message("commands") == ("help", None)
    assert parse_command_message("recent sip") == ("recent", "sip")
    assert parse_command_message("ladder nas100") == ("ladder", "nas100")
    assert parse_command_message("random chat") == (None, None)


def test_resolve_strategy_card_aliases() -> None:
    assert resolve_strategy_card("cwt").strategy_id == "strategy_four"
    assert resolve_strategy_card("trend").strategy_id == "strategy_two"
    assert resolve_strategy_card("sip").strategy_id == "strategy_five"


def test_build_strategy_text_overview_and_specific() -> None:
    overview = build_strategy_text()
    assert "Live Boards" in overview
    assert "Cambist With Trend" in overview

    detail = build_strategy_text("cwt")
    assert "M5/M15 execution with H1 bias" in detail
    assert "How to use it" in detail


def test_build_help_and_boards_text() -> None:
    help_text = build_help_text()
    assert "Command Guide" in help_text
    assert "recent" in help_text
    assert "scan" in help_text

    boards_text = build_boards_text()
    assert "Live Boards" in boards_text
    assert "Measured Drift" in boards_text
    assert "Secular Bull SIP" in boards_text


def test_build_status_and_recent_text(tmp_path) -> None:
    config_path = tmp_path / "platform.json"
    cwt_dir = tmp_path / "platform_output" / "strategy_four"
    cwt_dir.mkdir(parents=True, exist_ok=True)
    (cwt_dir / "health_snapshot.json").write_text(
        json.dumps(
            {
                "dispatch_error_count": 0,
                "last_successful_market_refresh_utc": "2026-04-14T00:00:00+00:00",
                "last_successful_discord_post_utc": "2026-04-14T00:05:00+00:00",
                "fresh_signals": 1,
                "recovered_entries_found": 2,
                "recovered_entries_sent": 1,
                "pending_unnotified_outcomes_count": 0,
                "quiet_reason": "active",
            }
        ),
        encoding="utf-8",
    )
    (cwt_dir / "ladder_ledger.json").write_text(
        json.dumps(
            {
                "updated_at_utc": "2026-04-14T00:10:00+00:00",
                "symbol_count": 1,
                "symbols": {
                    "NAS100_USD": {
                        "current_state": {
                            "last_setup_id": "setup-1",
                            "status": "closed",
                            "outcome": "tp_hit",
                            "ladder_step": 0,
                            "risk_pct": 0.07,
                            "updated_at": "2026-04-14T00:10:00+00:00",
                        },
                        "events": [
                            {
                                "setup_id": "setup-1",
                                "ladder_step_at_entry": 2,
                                "ladder_risk_pct_at_entry": 0.45,
                                "ladder_previous_outcome": "sl_hit",
                                "ladder_previous_setup_id": "setup-0",
                                "ladder_transition_note": "reset_after_tp",
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (cwt_dir / "signal_journal.json").write_text(
        json.dumps(
            [
                {
                    "strategy_id": "strategy_four",
                    "strategy_name": "Cambist With Trend",
                    "setup_id": "setup-1",
                    "symbol": "EUR_USD",
                    "asset_class": "forex",
                    "timeframe": "5m",
                    "side": "short",
                    "signal_timestamp": "2026-04-14T00:00:00+00:00",
                    "dispatched_at_utc": "2026-04-14T00:01:00+00:00",
                    "entry": 1.1,
                    "stop_loss": 1.2,
                    "target_1": 1.0,
                    "risk_reward": 1.0,
                    "quality_score": 8,
                    "quality_grade": "A",
                    "status": "closed",
                    "outcome": "tp_hit",
                    "outcome_timestamp": "2026-04-14T01:00:00+00:00",
                    "exit_price": 1.0,
                    "outcome_notified": True,
                    "last_checked_utc": "2026-04-14T01:05:00+00:00",
                    "bars_checked": 12,
                    "raw_signal": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "oanda_environment": "practice",
                "oanda_price": "M",
                "routes": [
                    {
                        "strategy_id": "strategy_four",
                        "enabled": True,
                        "watchlist": "core-mixed",
                        "granularity": "M5",
                        "higher_timeframe": "H1",
                        "interval_minutes": 5,
                        "dispatch": "discord",
                        "discord_webhook_url": "https://example.test/webhook",
                        "output_dir": str(cwt_dir),
                        "state_file": str(cwt_dir / "sent_state.json"),
                        "journal_file": str(cwt_dir / "signal_journal.json"),
                        "report_state_file": str(cwt_dir / "report_state.json"),
                        "health_snapshot_file": str(cwt_dir / "health_snapshot.json"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    status_text = build_status_text(config_path)
    assert "Board Status" in status_text
    assert "Cambist With Trend" in status_text
    assert "fresh=1" in status_text
    assert "last_post=" in status_text

    recent_text = build_recent_text(config_path)
    assert "Recent Activity" in recent_text
    assert "Latest signal" in recent_text
    assert "Latest outcome" in recent_text

    ladder_text = build_ladder_text(config_path, "nas100")
    assert "Ladder | NAS100_USD" in ladder_text
    assert "step=0" in ladder_text
    assert "reset_after_tp" in ladder_text

    status_ladder_text = build_status_text(config_path, "cwt ladder nas100")
    assert "Ladder | NAS100_USD" in status_ladder_text
