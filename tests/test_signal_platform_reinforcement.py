from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from signal_platform.models import JournalEntry, PlatformSignal, ReinforcementConfig, ScanResult, SignalStructure
from signal_platform.reinforcement import apply_signal_reinforcement
from signal_platform.runtime import StrategyRoute, run_route


def _signal(setup_id: str, timestamp: str, *, side: str = "long", quality_score: int = 75) -> PlatformSignal:
    return PlatformSignal(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side=side,
        timestamp=timestamp,
        setup_id=setup_id,
        summary="Scenario 2 continuation under H1 bias.",
        alert_text="alert",
        quality_score=quality_score,
        quality_grade="B",
        risk_reward=1.0,
        entry=1.101,
        stop_loss=1.1,
        target_1=1.102,
        raw_signal={"event_type": "entry", "delivery_kind": "fresh", "bias_timeframe": "H1"},
    )


def _closed_root_entry(setup_id: str) -> JournalEntry:
    return JournalEntry(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        setup_id=setup_id,
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="long",
        signal_timestamp="2026-04-15T00:00:00+00:00",
        dispatched_at_utc="2026-04-15T00:01:00+00:00",
        entry=1.101,
        stop_loss=1.1,
        target_1=1.102,
        risk_reward=1.0,
        quality_score=75,
        quality_grade="B",
        status="closed",
        outcome="tp_hit",
        outcome_timestamp="2026-04-15T00:20:00+00:00",
        exit_price=1.102,
        outcome_notified=True,
    )


def test_apply_signal_reinforcement_turns_duplicate_into_reinforcement() -> None:
    config = ReinforcementConfig(enabled=True)
    result = apply_signal_reinforcement(
        signals=[
            _signal("root-1", "2026-04-15T00:00:00+00:00", quality_score=75),
            _signal("dup-1", "2026-04-15T00:05:00+00:00", quality_score=82),
        ],
        journal_entries=[],
        existing_structures={},
        config=config,
    )

    assert len(result.tradable_signals) == 1
    assert len(result.reinforcement_signals) == 1
    root = result.tradable_signals[0]
    reinforcement = result.reinforcement_signals[0]
    assert root.setup_id == "root-1"
    assert reinforcement.is_tradable is False
    assert reinforcement.root_signal_id == "root-1"
    assert reinforcement.structure_id == root.structure_id
    assert reinforcement.reinforcement_count == 1
    assert reinforcement.strength_score == 66


def test_apply_signal_reinforcement_allows_new_structure_after_root_closes() -> None:
    config = ReinforcementConfig(enabled=True)
    existing_structure = SignalStructure(
        structure_id="strategy_four:EUR_USD:5m:long:root-1",
        strategy_id="strategy_four",
        symbol="EUR_USD",
        timeframe="5m",
        side="long",
        start_timestamp="2026-04-15T00:00:00+00:00",
        last_update_timestamp="2026-04-15T00:00:00+00:00",
        status="active",
        root_signal_id="root-1",
        reinforcement_count=0,
        strength_score=50,
        best_quality_score=75,
        current_status="active",
        entry=1.101,
        stop_loss=1.1,
        target_1=1.102,
        last_signal_timestamp="2026-04-15T00:00:00+00:00",
    )

    result = apply_signal_reinforcement(
        signals=[_signal("next-1", "2026-04-15T01:00:00+00:00", quality_score=77)],
        journal_entries=[_closed_root_entry("root-1")],
        existing_structures={existing_structure.structure_id: existing_structure},
        config=config,
    )

    assert len(result.tradable_signals) == 1
    assert len(result.reinforcement_signals) == 0
    assert result.tradable_signals[0].setup_id == "next-1"
    assert result.tradable_signals[0].root_signal_id == "next-1"


@dataclass
class _FakeStrategy:
    strategy_id: str = "strategy_four"
    strategy_name: str = "Cambist With Trend"
    default_watchlist: str = "core-mixed"
    managed_events: bool = False
    result: ScanResult | None = None

    def scan(self, request):  # noqa: ANN001
        assert self.result is not None
        return self.result


def test_run_route_journals_only_root_signal_when_reinforcement_enabled(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "strategy_four"
    fake_strategy = _FakeStrategy(
        result=ScanResult(
            strategy_id="strategy_four",
            strategy_name="Cambist With Trend",
            watchlist="core-mixed",
            signals=[
                _signal("root-1", "2026-04-15T00:00:00+00:00", quality_score=75),
                _signal("dup-1", "2026-04-15T00:05:00+00:00", quality_score=84),
            ],
            rows=[{"symbol": "EUR_USD"}],
        )
    )

    sent_signals: list[str] = []
    monkeypatch.setattr("signal_platform.runtime.get_strategy", lambda _strategy_id: fake_strategy)
    monkeypatch.setattr("signal_platform.runtime.refresh_open_entries", lambda entries, **_: entries)
    monkeypatch.setattr("signal_platform.runtime.send_discord_outcome", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("signal_platform.runtime.send_discord_webhook", lambda _url, signal, username=None: sent_signals.append(signal.setup_id))
    monkeypatch.setattr("signal_platform.runtime.send_discord_report", lambda *_args, **_kwargs: None)

    route = StrategyRoute(
        strategy_id="strategy_four",
        enabled=True,
        watchlist="core-mixed",
        granularity="M5",
        higher_timeframe="H1",
        interval_minutes=5,
        dispatch="discord",
        discord_webhook_url="https://example.test/webhook",
        output_dir=str(output_dir),
        state_file=str(output_dir / "sent_state.json"),
        journal_file=str(output_dir / "signal_journal.json"),
        report_state_file=str(output_dir / "report_state.json"),
        reinforcement_state_file=str(output_dir / "reinforcement_state.json"),
        reinforcement_log_file=str(output_dir / "reinforcement_decisions.jsonl"),
        extra={"signal_reinforcement": {"enabled": True}},
    )

    summary = run_route(route, environment="practice", price="M", token="token")

    journal_text = Path(route.journal_file).read_text(encoding="utf-8")
    assert sent_signals == ["root-1", "dup-1"]
    assert journal_text.count('"setup_id"') == 1
    assert '"setup_id": "root-1"' in journal_text
    assert summary["delivered_tradable"] == 1
    assert summary["delivered_reinforcement"] == 1
