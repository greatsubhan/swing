"""Config-driven signal platform runtime."""
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import replace
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
    pending_outcome_notifications,
    refresh_open_entries,
    report_period_keys,
    save_journal,
    save_report_state,
    signal_with_stats,
)
from .models import PlatformSignal
from .reinforcement import (
    append_reinforcement_decisions,
    apply_signal_reinforcement,
    load_structure_state,
    reinforcement_config_from_route_extra,
    save_structure_state,
)
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
    log_signals: bool = False
    log_filtered_setups: bool = False
    signal_log_file: str | None = None
    filtered_log_file: str | None = None
    catch_up_hours: float = 3.0
    max_backfill_outcomes_per_run: int = 100
    max_catch_up_entries_per_run: int = 50
    health_log_file: str | None = None
    health_snapshot_file: str | None = None
    reinforcement_state_file: str | None = None
    reinforcement_log_file: str | None = None
    extra: dict | None = None


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
            log_signals=bool(route.get("log_signals", False)),
            log_filtered_setups=bool(route.get("log_filtered_setups", False)),
            signal_log_file=route.get("signal_log_file"),
            filtered_log_file=route.get("filtered_log_file"),
            catch_up_hours=float(route.get("catch_up_hours", 3.0)),
            max_backfill_outcomes_per_run=int(route.get("max_backfill_outcomes_per_run", 100)),
            max_catch_up_entries_per_run=int(route.get("max_catch_up_entries_per_run", 50)),
            health_log_file=route.get("health_log_file"),
            health_snapshot_file=route.get("health_snapshot_file"),
            reinforcement_state_file=route.get("reinforcement_state_file"),
            reinforcement_log_file=route.get("reinforcement_log_file"),
            extra=route.get("extra"),
        )
        for route in payload.get("routes", [])
    ]
    return PlatformConfig(
        oanda_environment=str(payload.get("oanda_environment", "practice")),
        oanda_price=str(payload.get("oanda_price", "M")),
        routes=routes,
    )


def _signal_delivery_kind(signal: PlatformSignal) -> str:
    return str(signal.raw_signal.get("delivery_kind", "fresh")).lower()


def _resolved_route_path(output_dir: Path, configured_path: str | None, filename: str) -> Path:
    return Path(configured_path) if configured_path else output_dir / filename


def _append_health_log(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    fieldnames = list(row.keys())
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _write_health_snapshot(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _derive_quiet_reason(rows: list[dict[str, object]], suppressed_duplicates: int) -> str | None:
    if suppressed_duplicates > 0:
        return "duplicate_suppression"
    reasons: dict[str, int] = {}
    for row in rows:
        reason = row.get("reason") or row.get("note") or row.get("error")
        if not reason:
            continue
        reasons[str(reason)] = reasons.get(str(reason), 0) + 1
    if not reasons:
        return "no_signal"
    return sorted(reasons.items(), key=lambda item: (-item[1], item[0]))[0][0]


def run_route(route: StrategyRoute, environment: str, price: str, token: str | None) -> dict[str, object]:
    strategy = get_strategy(route.strategy_id)
    managed_events = bool(getattr(strategy, "managed_events", False))
    output_dir = Path(route.output_dir)
    cycle_started_at = datetime.now(timezone.utc)
    health_log_path = _resolved_route_path(output_dir, route.health_log_file, "route_cycle_log.csv")
    health_snapshot_path = _resolved_route_path(output_dir, route.health_snapshot_file, "health_snapshot.json")
    dispatch_errors: list[str] = []
    last_successful_discord_post_utc: str | None = None
    if not managed_events:
        journal_entries = load_journal(route.journal_file)
        journal_entries = refresh_open_entries(journal_entries, token=token, environment=environment, price=price)
        save_journal(route.journal_file, journal_entries)
    else:
        journal_entries = []
    reinforcement_config = reinforcement_config_from_route_extra(route.extra)
    reinforcement_state_path = _resolved_route_path(output_dir, route.reinforcement_state_file, "reinforcement_state.json")
    reinforcement_log_path = _resolved_route_path(output_dir, route.reinforcement_log_file, "reinforcement_decisions.jsonl")
    existing_structures = load_structure_state(reinforcement_state_path) if reinforcement_config.enabled and not managed_events else {}
    scan_request = StrategyScanRequest(
        strategy_id=route.strategy_id,
        watchlist=route.watchlist,
        granularity=route.granularity,
        higher_timeframe=route.higher_timeframe,
        environment=environment,
        token=token,
        price=price,
        output_dir=output_dir,
        use_market_profile=route.use_market_profile,
        log_signals=route.log_signals,
        log_filtered_setups=route.log_filtered_setups,
        signal_log_file=route.signal_log_file,
        filtered_log_file=route.filtered_log_file,
        catch_up_hours=route.catch_up_hours if not managed_events else None,
        extra=route.extra,
    )
    result = strategy.scan(scan_request)
    reinforcement_result = apply_signal_reinforcement(
        signals=result.signals,
        journal_entries=journal_entries,
        existing_structures=existing_structures,
        config=reinforcement_config,
    )
    if reinforcement_config.enabled and not managed_events:
        save_structure_state(reinforcement_state_path, reinforcement_result.structures)
        append_reinforcement_decisions(reinforcement_log_path, reinforcement_result.decisions)
    effective_signals = reinforcement_result.all_signals
    tradable_signals = reinforcement_result.tradable_signals
    reinforcement_signals = reinforcement_result.reinforcement_signals
    sent_setup_ids = load_sent_setup_ids(route.state_file)
    if managed_events:
        pending_outcomes = []
        outcomes_to_send = []
        unsent_signals = new_signals_only(effective_signals, sent_setup_ids)
        fresh_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) != "catch_up"]
        recovered_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) == "catch_up"]
        recovered_signals = recovered_signals[: route.max_catch_up_entries_per_run]
        suppressed_duplicates = len(effective_signals) - len(unsent_signals)
        enriched_fresh_signals = fresh_signals
        enriched_recovered_signals = recovered_signals
        latest_stats = None
    else:
        journal_entries = backfill_known_signals(journal_entries, tradable_signals, sent_setup_ids)
        pending_outcomes = pending_outcome_notifications(journal_entries)
        outcomes_to_send = pending_outcome_notifications(journal_entries, limit=route.max_backfill_outcomes_per_run)
        unsent_signals = new_signals_only(effective_signals, sent_setup_ids)
        fresh_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) != "catch_up"]
        recovered_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) == "catch_up"]
        recovered_signals = recovered_signals[: route.max_catch_up_entries_per_run]
        suppressed_duplicates = len(effective_signals) - len(unsent_signals)
        stats = build_stats_snapshot(journal_entries)
        enriched_fresh_signals = [signal_with_stats(signal, stats) for signal in fresh_signals]
        enriched_recovered_signals = [signal_with_stats(signal, stats) for signal in recovered_signals]
        latest_stats = build_stats_snapshot(journal_entries)

    delivered: list[PlatformSignal] = []
    recovered_delivered: list[PlatformSignal] = []
    delivered_tradable: list[PlatformSignal] = []
    delivered_reinforcement: list[PlatformSignal] = []
    recovered_delivered_reinforcement: list[PlatformSignal] = []
    outcomes_sent = 0
    if route.dispatch == "discord":
        if not route.discord_webhook_url:
            raise ValueError(f"Route {route.strategy_id} uses discord dispatch but has no webhook URL.")
        for outcome in outcomes_to_send:
            try:
                send_discord_outcome(route.discord_webhook_url, outcome, username=f"{strategy.strategy_name} Desk")
            except Exception as exc:
                dispatch_errors.append(f"outcome:{outcome.setup_id}:{exc}")
                continue
            outcome.outcome_notified = True
            outcomes_sent += 1
            last_successful_discord_post_utc = datetime.now(timezone.utc).isoformat()
        for signal in enriched_fresh_signals:
            try:
                send_discord_webhook(route.discord_webhook_url, signal, username=f"{strategy.strategy_name} Desk")
            except Exception as exc:
                dispatch_errors.append(f"signal:{signal.setup_id}:{exc}")
                continue
            delivered.append(signal)
            if signal.is_tradable:
                delivered_tradable.append(signal)
            else:
                delivered_reinforcement.append(signal)
            sent_setup_ids.add(signal.setup_id)
            last_successful_discord_post_utc = datetime.now(timezone.utc).isoformat()
        for signal in enriched_recovered_signals:
            try:
                send_discord_webhook(route.discord_webhook_url, signal, username=f"{strategy.strategy_name} Desk")
            except Exception as exc:
                dispatch_errors.append(f"signal:{signal.setup_id}:{exc}")
                continue
            delivered.append(signal)
            recovered_delivered.append(signal)
            if signal.is_tradable:
                delivered_tradable.append(signal)
            else:
                delivered_reinforcement.append(signal)
                recovered_delivered_reinforcement.append(signal)
            sent_setup_ids.add(signal.setup_id)
            last_successful_discord_post_utc = datetime.now(timezone.utc).isoformat()
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
        journal_entries = append_new_signals(journal_entries, delivered_tradable)
        save_journal(route.journal_file, journal_entries)
    save_sent_setup_ids(route.state_file, sent_setup_ids)

    summary = {
        "strategy_id": route.strategy_id,
        "strategy_name": strategy.strategy_name,
        "watchlist": route.watchlist,
        "interval_minutes": route.interval_minutes,
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(result.rows),
        "signals_found": len(effective_signals),
        "tradable_signals": len(tradable_signals),
        "reinforcement_signals": len(reinforcement_signals),
        "fresh_signals": len(fresh_signals),
        "recovered_entries_found": len(recovered_signals),
        "delivered": len(delivered),
        "delivered_tradable": len(delivered_tradable),
        "delivered_reinforcement": len(delivered_reinforcement),
        "recovered_delivered": len(recovered_delivered),
        "recovered_reinforcement_delivered": len(recovered_delivered_reinforcement),
        "pending_outcomes": len(pending_outcomes),
        "outcomes_sent": outcomes_sent,
        "suppressed_duplicates": suppressed_duplicates,
        "dispatch_errors": dispatch_errors,
        "catch_up_hours": route.catch_up_hours if not managed_events else None,
        "dispatch": route.dispatch,
        "output_dir": str(output_dir),
        "state_file": route.state_file,
        "journal_file": route.journal_file,
        "report_state_file": route.report_state_file,
        "stats_snapshot": latest_stats.to_dict() if latest_stats is not None else None,
        "managed_events": managed_events,
        "reinforcement_enabled": reinforcement_config.enabled,
    }
    summary_path = output_dir / "platform_run_summary.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    quiet_reason = None
    if len(effective_signals) == 0:
        quiet_reason = _derive_quiet_reason(result.rows, suppressed_duplicates)
    elif len(fresh_signals) == 0 and len(recovered_signals) == 0:
        quiet_reason = "duplicate_suppression"
    summary["quiet_reason"] = quiet_reason
    summary_path.write_text(json.dumps(summary, indent=2))
    health_snapshot = {
        "strategy_id": route.strategy_id,
        "strategy_name": strategy.strategy_name,
        "watchlist": route.watchlist,
        "managed_events": managed_events,
        "last_cycle_started_utc": cycle_started_at.isoformat(),
        "last_cycle_finished_utc": datetime.now(timezone.utc).isoformat(),
        "last_successful_market_refresh_utc": cycle_started_at.isoformat(),
        "last_successful_discord_post_utc": last_successful_discord_post_utc,
        "signals_found": len(effective_signals),
        "tradable_signals": len(tradable_signals),
        "reinforcement_signals": len(reinforcement_signals),
        "fresh_signals": len(fresh_signals),
        "recovered_entries_found": len(recovered_signals),
        "recovered_entries_sent": len(recovered_delivered),
        "reinforcements_sent": len(delivered_reinforcement),
        "pending_unnotified_outcomes_count": len(pending_outcome_notifications(journal_entries)) if not managed_events else 0,
        "outcomes_sent": outcomes_sent,
        "suppressed_duplicates": suppressed_duplicates,
        "dispatch_error_count": len(dispatch_errors),
        "dispatch_errors": dispatch_errors,
        "quiet_reason": quiet_reason,
    }
    health_log_row = {
        "route": route.strategy_id,
        "run_time_utc": health_snapshot["last_cycle_finished_utc"],
        "rows_scanned": len(result.rows),
        "signals_found": len(effective_signals),
        "tradable_signals": len(tradable_signals),
        "reinforcement_signals": len(reinforcement_signals),
        "fresh_signals": len(fresh_signals),
        "recovered_entries": len(recovered_signals),
        "reinforcements_sent": len(delivered_reinforcement),
        "outcomes_pending": len(pending_outcomes),
        "outcomes_sent": outcomes_sent,
        "suppressed_duplicates": suppressed_duplicates,
        "dispatch_errors": len(dispatch_errors),
        "quiet_reason": quiet_reason or "",
    }
    _append_health_log(health_log_path, health_log_row)
    _write_health_snapshot(health_snapshot_path, health_snapshot)
    return summary


def run_platform_config(config_path: str | Path, token: str | None) -> list[dict[str, object]]:
    config = load_platform_config(config_path)
    results: list[dict[str, object]] = []
    for route in config.routes:
        if not route.enabled:
            continue
        results.append(run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token))
    return results


def run_configured_route(
    config_path: str | Path,
    *,
    strategy_id: str,
    token: str | None,
    watchlist: str | None = None,
    granularity: str | None = None,
    higher_timeframe: str | None = None,
    output_dir: str | None = None,
    dispatch: str | None = None,
    catch_up_hours: float | None = None,
) -> dict[str, object]:
    config = load_platform_config(config_path)
    matched_route = next((route for route in config.routes if route.strategy_id == strategy_id), None)
    if matched_route is None:
        available = ", ".join(sorted(route.strategy_id for route in config.routes))
        raise KeyError(f"Unknown strategy route {strategy_id!r}. Available: {available}")

    route = replace(
        matched_route,
        enabled=True,
        watchlist=watchlist or matched_route.watchlist,
        granularity=granularity or matched_route.granularity,
        higher_timeframe=higher_timeframe or matched_route.higher_timeframe,
        output_dir=output_dir or matched_route.output_dir,
        dispatch=dispatch or matched_route.dispatch,
        catch_up_hours=matched_route.catch_up_hours if catch_up_hours is None else catch_up_hours,
    )
    return run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token)


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
