"""Performance metrics and reporting for signal platform journals."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Callable

from .journal import load_journal
from .models import JournalEntry

TIME_OF_DAY_BUCKETS = [
    (0, 5, "overnight"),
    (6, 11, "morning"),
    (12, 17, "afternoon"),
    (18, 23, "evening"),
]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _time_of_day_bucket(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    hour = dt.hour
    for start, end, label in TIME_OF_DAY_BUCKETS:
        if start <= hour <= end:
            return label
    return "unknown"


def confidence_interval_proportion(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if trials <= 0:
        return 0.0, 0.0
    p = successes / trials
    z2 = z * z
    denom = 1 + z2 / trials
    centre = p + z2 / (2 * trials)
    margin = z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials))
    lower = max(0.0, (centre - margin) / denom)
    upper = min(1.0, (centre + margin) / denom)
    return lower, upper


def probability_of_ruin_approx(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    risk_fraction: float = 0.01,
    bankroll_fraction: float = 0.5,
) -> float:
    if win_rate <= 0 or risk_fraction <= 0 or bankroll_fraction <= 0:
        return 1.0
    loss_rate = 1.0 - win_rate
    if avg_loss >= 0 or avg_win <= 0:
        return 1.0
    payoff_ratio = avg_win / abs(avg_loss) if avg_loss != 0 else float("inf")
    edge = win_rate * payoff_ratio - loss_rate
    if edge <= 0:
        return 1.0
    q_over_pb = loss_rate / (win_rate * payoff_ratio)
    if q_over_pb >= 1.0:
        return 1.0
    exponent = bankroll_fraction / risk_fraction
    return min(1.0, max(0.0, q_over_pb ** exponent))


def _build_summary(entries: list[JournalEntry]) -> dict[str, object]:
    closed = [entry for entry in entries if entry.status == "closed"]
    realized = [entry.realized_r() for entry in closed if entry.realized_r() is not None]
    total_closed = len(realized)
    wins = [value for value in realized if value > 0]
    losses = [value for value in realized if value < 0]
    win_rate = len(wins) / total_closed if total_closed else 0.0
    avg_win = mean(wins) if wins else 0.0
    avg_loss = mean(losses) if losses else 0.0
    payoff_ratio = (avg_win / abs(avg_loss)) if losses else float("inf")
    expectancy = mean(realized) if realized else 0.0
    lower, upper = confidence_interval_proportion(len(wins), total_closed)
    return {
        "signal_count": len(entries),
        "closed_count": total_closed,
        "open_count": len([entry for entry in entries if entry.status == "open"]),
        "win_rate": win_rate,
        "win_rate_ci_lower": lower,
        "win_rate_ci_upper": upper,
        "avg_win_r": avg_win,
        "avg_loss_r": avg_loss,
        "payoff_ratio": payoff_ratio,
        "expectancy_r": expectancy,
        "total_realized_r": sum(realized) if realized else 0.0,
        "r_distribution": {
            "median": float(sorted(realized)[len(realized) // 2]) if realized else 0.0,
            "min": min(realized) if realized else 0.0,
            "max": max(realized) if realized else 0.0,
        },
        "probability_of_ruin": probability_of_ruin_approx(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            risk_fraction=0.01,
            bankroll_fraction=0.5,
        ),
    }


def compute_grouped_metrics(
    entries: list[JournalEntry],
    group_func: Callable[[JournalEntry], str],
) -> dict[str, dict[str, object]]:
    groups: dict[str, list[JournalEntry]] = defaultdict(list)
    for entry in entries:
        groups[group_func(entry)].append(entry)
    return {group: _build_summary(group_entries) for group, group_entries in groups.items()}


def compute_strategy_metrics(entries: list[JournalEntry]) -> dict[str, object]:
    summary = _build_summary(entries)
    return {
        "summary": summary,
        "by_scenario": compute_grouped_metrics(entries, lambda entry: str(entry.raw_signal.get("scenario", "unknown"))),
        "by_quality_grade": compute_grouped_metrics(entries, lambda entry: str(entry.quality_grade or "unknown")),
        "by_asset_class": compute_grouped_metrics(entries, lambda entry: str(entry.asset_class or "unknown")),
        "by_time_of_day": compute_grouped_metrics(
            entries,
            lambda entry: _time_of_day_bucket(_parse_datetime(entry.signal_timestamp)),
        ),
    }


def performance_summary_text(summary: dict[str, object]) -> str:
    win_rate = summary["win_rate"] * 100
    lower = summary["win_rate_ci_lower"] * 100
    upper = summary["win_rate_ci_upper"] * 100
    return (
        f"Closed signals: {summary['closed_count']}. "
        f"Win rate {win_rate:.1f}% (95% CI {lower:.1f}%–{upper:.1f}%). "
        f"Payoff ratio {summary['payoff_ratio']:.2f}. "
        f"Expectancy {summary['expectancy_r']:.3f}R. "
        f"Total realized {summary['total_realized_r']:.2f}R. "
        f"Approx. ruin risk {summary['probability_of_ruin']:.2%}."
    )


def load_metrics_from_journal(path: str | Path) -> dict[str, object]:
    entries = load_journal(path)
    return compute_strategy_metrics(entries)
