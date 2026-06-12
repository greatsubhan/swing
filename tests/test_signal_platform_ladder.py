from __future__ import annotations

import json
from pathlib import Path

from signal_platform.journal import append_new_signals, refresh_open_entries, save_ladder_ledger
from signal_platform.models import JournalEntry, PlatformSignal


def test_append_new_signals_persists_ladder_snapshot() -> None:
    signal = PlatformSignal(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="long",
        timestamp="2026-04-17T00:00:00+00:00",
        setup_id="setup-1",
        summary="Test",
        alert_text="Test",
        risk_reward=1.0,
        entry=1.1,
        stop_loss=1.0,
        target_1=1.2,
        raw_signal={
            "ladder_sequence_pct": [0.07, 0.2, 0.45, 1.0],
            "ladder_step_index": 1,
            "risk_fraction": 0.002,
            "risk_display": "0.20% (step 2/4) after sl hit",
            "previous_outcome": "sl_hit",
            "previous_setup_id": "prev-1",
        },
    )

    entries = append_new_signals([], [signal])

    assert len(entries) == 1
    entry = entries[0]
    assert entry.ladder_step_at_entry == 1
    assert entry.ladder_risk_pct_at_entry == 0.2
    assert entry.ladder_risk_display_at_entry == "0.20% (step 2/4) after sl hit"
    assert entry.ladder_previous_outcome == "sl_hit"
    assert entry.ladder_previous_setup_id == "prev-1"


def test_refresh_open_entries_updates_next_ladder_after_sl(monkeypatch) -> None:
    entry = JournalEntry(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        setup_id="setup-1",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="long",
        signal_timestamp="2026-04-17T00:00:00+00:00",
        dispatched_at_utc="2026-04-17T00:01:00+00:00",
        entry=1.1,
        stop_loss=1.0,
        target_1=1.2,
        risk_reward=1.0,
        quality_score=80,
        quality_grade="B",
        status="open",
        ladder_sequence_pct=[0.07, 0.2, 0.45, 1.0],
        ladder_step_at_entry=1,
        ladder_risk_pct_at_entry=0.2,
        ladder_risk_display_at_entry="0.20% (step 2/4)",
    )

    monkeypatch.setattr(
        "signal_platform.journal._find_outcome",
        lambda *_args, **_kwargs: ("sl_hit", "2026-04-17T00:10:00+00:00", 1.0, 1),
    )

    refreshed = refresh_open_entries([entry], token="token", environment="practice", price="M")

    assert refreshed[0].ladder_step_after_outcome == 2
    assert refreshed[0].ladder_next_risk_pct == 0.45
    assert refreshed[0].ladder_transition_note == "advance_after_sl"


def test_save_ladder_ledger_writes_reviewable_symbol_history(tmp_path: Path) -> None:
    entry = JournalEntry(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        setup_id="setup-1",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="long",
        signal_timestamp="2026-04-17T00:00:00+00:00",
        dispatched_at_utc="2026-04-17T00:01:00+00:00",
        entry=1.1,
        stop_loss=1.0,
        target_1=1.2,
        risk_reward=1.0,
        quality_score=80,
        quality_grade="B",
        status="closed",
        outcome="tp_hit",
        outcome_timestamp="2026-04-17T00:10:00+00:00",
        ladder_sequence_pct=[0.07, 0.2, 0.45, 1.0],
        ladder_step_at_entry=2,
        ladder_risk_pct_at_entry=0.45,
        ladder_risk_display_at_entry="0.45% (step 3/4)",
        ladder_step_after_outcome=0,
        ladder_next_risk_pct=0.07,
        ladder_transition_note="reset_after_tp",
    )

    ledger_path = tmp_path / "ladder_ledger.json"
    save_ladder_ledger(ledger_path, [entry])
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert payload["symbol_count"] == 1
    assert payload["symbols"]["EUR_USD"]["current_state"]["ladder_step"] == 0
    assert payload["symbols"]["EUR_USD"]["events"][0]["ladder_transition_note"] == "reset_after_tp"
