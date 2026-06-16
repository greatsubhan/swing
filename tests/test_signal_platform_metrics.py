from datetime import timezone

from signal_platform.models import JournalEntry
from signal_platform.metrics import compute_strategy_metrics, performance_summary_text


def _closed_entry(setup_id: str, outcome: str, realized_r: float) -> JournalEntry:
    return JournalEntry(
        strategy_id="strategy_four",
        strategy_name="Cambist With Trend",
        setup_id=setup_id,
        symbol="EUR_USD",
        asset_class="forex",
        timeframe="5m",
        side="long",
        signal_timestamp="2026-01-01T00:00:00+00:00",
        dispatched_at_utc="2026-01-01T00:00:00+00:00",
        entry=1.0,
        stop_loss=0.9,
        target_1=1.1,
        risk_reward=1.0,
        quality_score=80,
        quality_grade="B",
        status="closed",
        is_root_signal=True,
        outcome=outcome,
        outcome_timestamp="2026-01-01T01:00:00+00:00",
        exit_price=1.1 if outcome == "tp_hit" else 0.9,
        raw_signal={"scenario": "scenario1"},
    )


def test_compute_strategy_metrics_summary() -> None:
    entries = [
        _closed_entry("s1", "tp_hit", 1.0),
        _closed_entry("s2", "sl_hit", -1.0),
        _closed_entry("s3", "sl_hit", -1.0),
        _closed_entry("s4", "tp_hit", 1.0),
    ]
    metrics = compute_strategy_metrics(entries)
    summary = metrics["summary"]

    assert summary["closed_count"] == 4
    assert summary["win_rate"] == 0.5
    assert summary["payoff_ratio"] == 1.0
    assert abs(summary["expectancy_r"] - 0.0) < 1e-9
    assert summary["total_realized_r"] == 0.0
    assert "by_scenario" in metrics
    assert metrics["by_scenario"]["scenario1"]["closed_count"] == 4


def test_performance_summary_text() -> None:
    entries = [
        _closed_entry("s1", "tp_hit", 1.0),
        _closed_entry("s2", "sl_hit", -1.0),
    ]
    metrics = compute_strategy_metrics(entries)
    text = performance_summary_text(metrics["summary"])
    assert "Closed signals: 2" in text
    assert "Win rate 50.0%" in text
