"""Config-driven signal platform runtime."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .dispatchers import (
    load_sent_setup_ids,
    new_signals_only,
    save_sent_setup_ids,
    send_discord_outcome,
    send_discord_report,
    send_discord_webhook,
)
from .journal import (
    append_new_signals,
    backfill_known_signals,
    build_stats_snapshot,
    journal_summary_data,
    load_journal,
    load_report_state,
    refresh_open_entries,
    report_period_keys,
    resolved_entries_since,
    save_journal,
    save_report_state,
    signal_with_stats,
)
from .models import PlatformSignal
from .registry import get_strategy
from .strategies import StrategyScanRequest


@dataclass
class StrategyRoute:
    strategy_id: str
    enabled: bool
    watchlist: str
    granularity: str
    higher_timeframe: str
    interval_minutes: int
    dispatch: str
    discord_webhook_url: str | None
    output_dir: str
    state_file: str
    journal_file: str
    report_state_file: str
    send_weekly_report: bool = True
    send_monthly_report: bool = True
    use_market_profile: bool = True


@dataclass
class PlatformConfig:
    oanda_environment: str
    oanda_price: str
    routes: list[StrategyRoute]


def _resolve_env_placeholders(value: object) -> object:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.getenv(env_name, "")
    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}
    return value


def load_platform_config(path: str | Path) -> PlatformConfig:
    payload = _resolve_env_placeholders(json.loads(Path(path).read_text()))
    routes = [
        StrategyRoute(
            strategy_id=str(route["strategy_id"]),
            enabled=bool(route.get("enabled", True)),
            watchlist=str(route["watchlist"]),
            granularity=str(route.get("granularity", "H4")),
            higher_timeframe=str(route.get("higher_timeframe", "1d")),
            interval_minutes=int(route.get("interval_minutes", 240)),
            dispatch=str(route.get("dispatch", "none")),
            discord_webhook_url=route.get("discord_webhook_url"),
            output_dir=str(route.get("output_dir", f"platform_output/{route['strategy_id']}")),
            state_file=str(route.get("state_file", f"platform_output/{route['strategy_id']}/sent_state.json")),
            journal_file=str(route.get("journal_file", f"platform_output/{route['strategy_id']}/signal_journal.json")),
            report_state_file=str(route.get("report_state_file", f"platform_output/{route['strategy_id']}/report_state.json")),
            send_weekly_report=bool(route.get("send_weekly_report", True)),
            send_monthly_report=bool(route.get("send_monthly_report", True)),
            use_market_profile=bool(route.get("use_market_profile", True)),
        )
        for route in payload.get("routes", [])
    ]
    return PlatformConfig(
        oanda_environment=str(payload.get("oanda_environment", "practice")),
        oanda_price=str(payload.get("oanda_price", "M")),
        routes=routes,
    )


def run_route(route: StrategyRoute, environment: str, price: str, token: str | None) -> dict[str, object]:
    strategy = get_strategy(route.strategy_id)
    managed_events = bool(getattr(strategy, "managed_events", False))
    output_dir = Path(route.output_dir)
    scan_request = StrategyScanRequest(
        watchlist=route.watchlist,
        granularity=route.granularity,
        higher_timeframe=route.higher_timeframe,
        environment=environment,
        token=token,
        price=price,
        output_dir=output_dir,
        use_market_profile=route.use_market_profile,
    )
    result = strategy.scan(scan_request)
    sent_setup_ids = load_sent_setup_ids(route.state_file)
    if managed_events:
        journal_entries = []
        recent_outcomes = []
        fresh_signals = new_signals_only(result.signals, sent_setup_ids)
        enriched_signals = fresh_signals
        latest_stats = None
    else:
        journal_entries = load_journal(route.journal_file)
        journal_entries = backfill_known_signals(journal_entries, result.signals, sent_setup_ids)
        journal_entries = refresh_open_entries(journal_entries, token=token, environment=environment, price=price)
        recent_outcomes = resolved_entries_since(
            journal_entries, datetime.now(timezone.utc) - timedelta(minutes=max(route.interval_minutes * 2, 15))
        )
        fresh_signals = new_signals_only(result.signals, sent_setup_ids)
        stats = build_stats_snapshot(journal_entries)
        enriched_signals = [signal_with_stats(signal, stats) for signal in fresh_signals]
        latest_stats = build_stats_snapshot(journal_entries)

    delivered: list[PlatformSignal] = []
    if route.dispatch == "discord":
        if not route.discord_webhook_url:
            raise ValueError(f"Route {route.strategy_id} uses discord dispatch but has no webhook URL.")
        for outcome in recent_outcomes:
            send_discord_outcome(route.discord_webhook_url, outcome, username=f"{strategy.strategy_name} Desk")
            outcome.outcome_notified = True
        for signal in enriched_signals:
            send_discord_webhook(route.discord_webhook_url, signal, username=f"{strategy.strategy_name} Desk")
            delivered.append(signal)
            sent_setup_ids.add(signal.setup_id)
        if not managed_events:
            report_state = load_report_state(route.report_state_file)
            now = datetime.now(timezone.utc)
            weekly_key, monthly_key = report_period_keys(now)
            if route.send_weekly_report and journal_entries and report_state.get("weekly") != weekly_key:
                weekly_summary = journal_summary_data(journal_entries, "Weekly", now - timedelta(days=7))
                send_discord_report(
                    route.discord_webhook_url,
                    weekly_summary,
                    username=f"{strategy.strategy_name} Review",
                    strategy_name=strategy.strategy_name,
                )
                report_state["weekly"] = weekly_key
            if route.send_monthly_report and journal_entries and report_state.get("monthly") != monthly_key:
                monthly_summary = journal_summary_data(journal_entries, "Monthly", now - timedelta(days=30))
                send_discord_report(
                    route.discord_webhook_url,
                    monthly_summary,
                    username=f"{strategy.strategy_name} Review",
                    strategy_name=strategy.strategy_name,
                )
                report_state["monthly"] = monthly_key
            save_report_state(route.report_state_file, report_state)
    elif route.dispatch == "none":
        pass
    else:
        raise ValueError(f"Unsupported dispatch type: {route.dispatch}")

    if not managed_events:
        journal_entries = append_new_signals(journal_entries, delivered)
        save_journal(route.journal_file, journal_entries)
    save_sent_setup_ids(route.state_file, sent_setup_ids)

    summary = {
        "strategy_id": route.strategy_id,
        "strategy_name": strategy.strategy_name,
        "watchlist": route.watchlist,
        "interval_minutes": route.interval_minutes,
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(result.rows),
        "signals_found": len(result.signals),
        "fresh_signals": len(fresh_signals),
        "delivered": len(delivered),
        "new_outcomes": len(recent_outcomes),
        "dispatch": route.dispatch,
        "output_dir": str(output_dir),
        "state_file": route.state_file,
        "journal_file": route.journal_file,
        "report_state_file": route.report_state_file,
        "stats_snapshot": latest_stats.to_dict() if latest_stats is not None else None,
        "managed_events": managed_events,
    }
    summary_path = output_dir / "platform_run_summary.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary


def run_platform_config(config_path: str | Path, token: str | None) -> list[dict[str, object]]:
    config = load_platform_config(config_path)
    results: list[dict[str, object]] = []
    for route in config.routes:
        if not route.enabled:
            continue
        results.append(run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token))
    return results


def serve_platform_config(
    config_path: str | Path,
    token: str | None,
    poll_seconds: int = 30,
    max_cycles: int | None = None,
    run_immediately: bool = True,
) -> list[dict[str, object]]:
    config = load_platform_config(config_path)
    last_run_at: dict[str, float] = {}
    results: list[dict[str, object]] = []
    cycle = 0

    while True:
        now = time.time()
        for route in config.routes:
            if not route.enabled:
                continue
            route_key = f"{route.strategy_id}:{route.watchlist}:{route.output_dir}"
            interval_seconds = max(60, route.interval_minutes * 60)
            previous = last_run_at.get(route_key)
            due = previous is None if run_immediately else previous is not None and (now - previous) >= interval_seconds
            if previous is not None and (now - previous) >= interval_seconds:
                due = True
            if previous is None and not run_immediately:
                last_run_at[route_key] = now
                continue
            if not due:
                continue
            summary = run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token)
            results.append(summary)
            last_run_at[route_key] = now
        cycle += 1
        if max_cycles is not None and cycle >= max_cycles:
            return results
        time.sleep(max(5, poll_seconds))
