from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from signal_platform.models import JournalEntry, PlatformSignal, ScanResult
from signal_platform.runtime import StrategyRoute, run_route


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


def _sample_signal(setup_id: str, *, delivery_kind: str = "fresh") -> PlatformSignal:
    return PlatformSignal(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="long",
        timestamp="2026-04-14T00:00:00+00:00",
        setup_id=setup_id,
        summary="Test setup",
        alert_text="Test setup",
        quality_score=80,
        quality_grade="B",
        risk_reward=1.0,
        entry=1.1,
        stop_loss=1.0,
        target_1=1.2,
        raw_signal={"delivery_kind": delivery_kind, "event_type": "entry"},
    )


def test_run_route_recovers_unnotified_outcomes(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "strategy_four"
    journal_path = output_dir / "signal_journal.json"
    entry = JournalEntry(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        setup_id="closed-1",
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="short",
        signal_timestamp="2026-04-10T00:00:00+00:00",
        dispatched_at_utc="2026-04-10T00:01:00+00:00",
        entry=1.1,
        stop_loss=1.2,
        target_1=1.0,
        risk_reward=1.0,
        quality_score=75,
        quality_grade="B",
        status="closed",
        outcome="tp_hit",
        outcome_timestamp="2026-04-10T03:00:00+00:00",
        exit_price=1.0,
        outcome_notified=False,
    )

    fake_strategy = _FakeStrategy(
        result=ScanResult(
            strategy_id="strategy_four",
            strategy_name="Cambist With Trend",
            watchlist="core-mixed",
            signals=[],
            rows=[],
        )
    )

    sent_outcomes: list[str] = []
    monkeypatch.setattr("signal_platform.runtime.get_strategy", lambda _strategy_id: fake_strategy)
    monkeypatch.setattr("signal_platform.runtime.refresh_open_entries", lambda entries, **_: entries)
    monkeypatch.setattr("signal_platform.runtime.send_discord_outcome", lambda _url, e, username=None: sent_outcomes.append(e.setup_id))
    monkeypatch.setattr("signal_platform.runtime.send_discord_webhook", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("signal_platform.runtime.send_discord_report", lambda *_args, **_kwargs: None)

    from signal_platform.journal import save_journal

    save_journal(journal_path, [entry])

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
        journal_file=str(journal_path),
        report_state_file=str(output_dir / "report_state.json"),
    )

    summary = run_route(route, environment="practice", price="M", token="token")

    assert sent_outcomes == ["closed-1"]
    assert summary["outcomes_sent"] == 1
    saved = Path(journal_path).read_text(encoding="utf-8")
    assert '"outcome_notified": true' in saved


def test_run_route_dispatches_fresh_and_recovered_entries(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "strategy_four"
    fake_strategy = _FakeStrategy(
        result=ScanResult(
            strategy_id="strategy_four",
            strategy_name="Cambist With Trend",
            watchlist="core-mixed",
            signals=[
                _sample_signal("fresh-1", delivery_kind="fresh"),
                _sample_signal("recovered-1", delivery_kind="catch_up"),
                _sample_signal("duplicate-1", delivery_kind="catch_up"),
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

    state_file = output_dir / "sent_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text('{"sent_setup_ids": ["duplicate-1"]}', encoding="utf-8")

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
        state_file=str(state_file),
        journal_file=str(output_dir / "signal_journal.json"),
        report_state_file=str(output_dir / "report_state.json"),
    )

    summary = run_route(route, environment="practice", price="M", token="token")

    assert sent_signals == ["fresh-1", "recovered-1"]
    assert summary["fresh_signals"] == 1
    assert summary["recovered_entries_found"] == 1
    assert summary["recovered_delivered"] == 1
    assert summary["suppressed_duplicates"] == 1


def test_cwt_load_history_refreshes_stale_cache(tmp_path, monkeypatch) -> None:
    from strategy_four_bot import scanner as cwt_scanner

    monkeypatch.setattr(cwt_scanner, "OANDA_CACHE_DIR", tmp_path)

    cache_dir = tmp_path / "EUR_USD"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "M5_live.csv"
    cached = pd.DataFrame(
        {
            "timestamp": ["2026-04-10T00:00:00+00:00"],
            "open": [1.1],
            "high": [1.2],
            "low": [1.0],
            "close": [1.15],
        }
    )
    cached.to_csv(cache_path, index=False)

    fresh_index = pd.DatetimeIndex(
        [
            datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 10, 0, 5, tzinfo=timezone.utc),
        ]
    )
    fresh_df = pd.DataFrame(
        {
            "open": [1.1, 1.15],
            "high": [1.2, 1.25],
            "low": [1.0, 1.1],
            "close": [1.15, 1.2],
        },
        index=fresh_index,
    )

    class _Fetched:
        def __init__(self, df: pd.DataFrame) -> None:
            self.df = df

    monkeypatch.setattr(
        cwt_scanner,
        "fetch_oanda_ohlcv",
        lambda **_kwargs: _Fetched(fresh_df),
    )

    merged = cwt_scanner.load_history("EUR_USD", "M5", "practice", "token", "M")

    assert len(merged) == 2
    assert merged.index.max() == fresh_index.max()
    saved = pd.read_csv(cache_path)
    assert len(saved) == 2
