from __future__ import annotations

import json
from pathlib import Path

from signal_platform.runtime import run_configured_route


def test_run_configured_route_uses_configured_dispatch_path(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "platform.json"
    config_path.write_text(
        json.dumps(
            {
                "oanda_environment": "practice",
                "oanda_price": "M",
                "routes": [
                    {
                        "strategy_id": "strategy_two",
                        "enabled": False,
                        "watchlist": "core-4h",
                        "granularity": "H4",
                        "higher_timeframe": "1d",
                        "interval_minutes": 240,
                        "dispatch": "discord",
                        "discord_webhook_url": "https://example.test/webhook",
                        "output_dir": "platform_output/strategy_two",
                        "state_file": "platform_output/strategy_two/sent_state.json",
                        "journal_file": "platform_output/strategy_two/signal_journal.json",
                        "report_state_file": "platform_output/strategy_two/report_state.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_route(route, environment: str, price: str, token: str | None):
        captured["route"] = route
        captured["environment"] = environment
        captured["price"] = price
        captured["token"] = token
        return {"strategy_id": route.strategy_id, "output_dir": route.output_dir}

    monkeypatch.setattr("signal_platform.runtime.run_route", fake_run_route)

    summary = run_configured_route(
        config_path,
        strategy_id="strategy_two",
        token="token-123",
        output_dir="platform_output/strategy_two_scan",
    )

    route = captured["route"]
    assert route.enabled is True
    assert route.strategy_id == "strategy_two"
    assert route.dispatch == "discord"
    assert route.output_dir == "platform_output/strategy_two_scan"
    assert captured["environment"] == "practice"
    assert captured["price"] == "M"
    assert captured["token"] == "token-123"
    assert summary["strategy_id"] == "strategy_two"
