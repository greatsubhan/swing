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
import traceback

import numpy as np

from .dispatchers import (
    load_sent_setup_ids,
    new_signals_only,
    save_sent_setup_ids,
    send_discord_outcome,
    send_discord_report,
    send_discord_text,
    send_discord_webhook,
)
from .journal import (
    append_new_signals,
    backfill_known_signals,
    build_stats_snapshot,
    enrich_ladder_fields,
    journal_summary_data,
    load_journal,
    load_report_state,
    pending_outcome_notifications,
    refresh_open_entries,
    report_period_keys,
    save_journal,
    save_ladder_ledger,
    save_report_state,
    signal_with_stats,
)
from .metrics import compute_strategy_metrics, performance_summary_text
from .ml_features import build_feature_vectors, vectors_to_numpy
from .ml_models import train_outcome_classifier, train_realized_r_regressor, save_model_metadata, save_model
from .signal_scoring import score_signal_with_ml
from .discord_predictions import format_signal_with_prediction, format_report_with_predictions
from .prediction_tracking import record_prediction, load_predictions, match_predictions_with_outcomes, evaluate_predictions, generate_prediction_report
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
    ladder_ledger_file: str | None = None
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
            ladder_ledger_file=route.get("ladder_ledger_file"),
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


def _post_reinforcement_alerts(route: StrategyRoute) -> bool:
    extra = route.extra or {}
    reinforcement = extra.get("signal_reinforcement", {})
    if not isinstance(reinforcement, dict):
        return True
    return bool(reinforcement.get("post_alerts", True))


def _outcome_price_mode(route: StrategyRoute) -> str:
    extra = route.extra or {}
    mode = extra.get("outcome_price_mode", "route_default")
    return str(mode or "route_default")


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


def _append_dispatch_failures(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_service_heartbeat(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _predictions_log_path(output_dir: Path) -> Path:
    return output_dir / "predictions.jsonl"


def _send_discord_signal_with_ml(
    route: StrategyRoute,
    strategy: Any,
    signal: PlatformSignal,
    model_dir: Path,
    predictions_path: Path,
) -> dict[str, object]:
    score = score_signal_with_ml(signal, model_dir)
    record_prediction(
        signal.setup_id,
        score.get("outcome_prediction") or {},
        score.get("realized_r_prediction") or {},
        predictions_path,
    )
    message = format_signal_with_prediction(signal, score)
    send_discord_text(route.discord_webhook_url, message, username=f"{strategy.strategy_name} Desk")
    return score


def _send_weekly_prediction_performance(
    route: StrategyRoute,
    strategy: Any,
    predictions_path: Path,
    journal_entries: list[Any],
) -> None:
    predictions = load_predictions(predictions_path)
    if not predictions:
        return
    matched = match_predictions_with_outcomes(predictions, journal_entries)
    evaluation = evaluate_predictions(matched)
    if evaluation.get("closed_trades", 0) <= 0:
        return
    report_text = generate_prediction_report(evaluation)
    formatted_text = format_report_with_predictions(report_text, evaluation)
    send_discord_text(route.discord_webhook_url, formatted_text, username=f"{strategy.strategy_name} Model Review")


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


def _record_route_failure(route: StrategyRoute, *, strategy_name: str, started_at: datetime, exc: Exception) -> dict[str, object]:
    output_dir = Path(route.output_dir)
    health_log_path = _resolved_route_path(output_dir, route.health_log_file, "route_cycle_log.csv")
    health_snapshot_path = _resolved_route_path(output_dir, route.health_snapshot_file, "health_snapshot.json")
    dispatch_failure_log_path = output_dir / "dispatch_failures.jsonl"
    finished_at = datetime.now(timezone.utc)
    error_text = f"{type(exc).__name__}: {exc}"
    trace_text = traceback.format_exc()
    summary = {
        "strategy_id": route.strategy_id,
        "strategy_name": strategy_name,
        "watchlist": route.watchlist,
        "interval_minutes": route.interval_minutes,
        "ran_at_utc": finished_at.isoformat(),
        "rows": 0,
        "signals_found": 0,
        "fresh_signals": 0,
        "delivered": 0,
        "pending_outcomes": 0,
        "outcomes_sent": 0,
        "dispatch_errors": [error_text],
        "dispatch": route.dispatch,
        "output_dir": str(output_dir),
        "state_file": route.state_file,
        "journal_file": route.journal_file,
        "report_state_file": route.report_state_file,
        "stats_snapshot": None,
        "managed_events": False,
        "quiet_reason": "route_error",
        "error": error_text,
        "traceback": trace_text,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "platform_run_summary.json").write_text(json.dumps(summary, indent=2))
    health_snapshot = {
        "strategy_id": route.strategy_id,
        "strategy_name": strategy_name,
        "watchlist": route.watchlist,
        "managed_events": False,
        "last_cycle_started_utc": started_at.isoformat(),
        "last_cycle_finished_utc": finished_at.isoformat(),
        "last_successful_market_refresh_utc": None,
        "last_successful_discord_post_utc": None,
        "signals_found": 0,
        "tradable_signals": 0,
        "reinforcement_signals": 0,
        "fresh_signals": 0,
        "recovered_entries_found": 0,
        "recovered_entries_sent": 0,
        "reinforcements_sent": 0,
        "pending_unnotified_outcomes_count": 0,
        "outcomes_sent": 0,
        "suppressed_duplicates": 0,
        "dispatch_error_count": 1,
        "dispatch_errors": [error_text],
        "quiet_reason": "route_error",
        "error": error_text,
    }
    health_log_row = {
        "route": route.strategy_id,
        "run_time_utc": finished_at.isoformat(),
        "rows_scanned": 0,
        "signals_found": 0,
        "tradable_signals": 0,
        "reinforcement_signals": 0,
        "fresh_signals": 0,
        "recovered_entries": 0,
        "reinforcements_sent": 0,
        "outcomes_pending": 0,
        "outcomes_sent": 0,
        "suppressed_duplicates": 0,
        "dispatch_errors": 1,
        "quiet_reason": "route_error",
        "error": error_text,
    }
    _append_health_log(health_log_path, health_log_row)
    _write_health_snapshot(health_snapshot_path, health_snapshot)
    _append_dispatch_failures(
        dispatch_failure_log_path,
        [
            {
                "timestamp_utc": finished_at.isoformat(),
                "route": route.strategy_id,
                "strategy_name": strategy_name,
                "stage": "route_failure",
                "error": error_text,
                "traceback": trace_text,
            }
        ],
    )
    return summary


def _train_route_ml_models(
    route: StrategyRoute,
    *,
    test_fraction: float = 0.2,
    min_closed_samples: int = 20,
) -> dict[str, object]:
    """Train ML models from journal entries if sufficient data exists.
    
    Args:
        route: Strategy route configuration
        test_fraction: Fraction of recent entries to use as test set
        min_closed_samples: Minimum closed trades required to train
    
    Returns:
        Dictionary with training results or error information
    """
    result = {
        "route_id": route.strategy_id,
        "status": "skipped",
        "reason": "no_journal",
        "models_trained": [],
    }
    
    # Load journal
    if not Path(route.journal_file).exists():
        return result
    
    try:
        entries = load_journal(route.journal_file)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"journal_load_error: {exc}"
        return result
    
    # Check for sufficient closed trades
    closed_count = sum(1 for e in entries if e.status == "closed" and e.realized_r() is not None)
    if closed_count < min_closed_samples:
        result["reason"] = f"insufficient_closed_trades: {closed_count} < {min_closed_samples}"
        return result
    
    # Build feature vectors
    try:
        from .ml_features import load_and_build_features
        train_vectors, test_vectors, feature_names = load_and_build_features(
            route.journal_file, test_fraction=test_fraction
        )
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"feature_extraction_error: {exc}"
        return result
    
    # Get labeled samples for training
    outcome_labels = [v for v in train_vectors if v.outcome_label is not None]
    test_outcome_labels = [v for v in test_vectors if v.outcome_label is not None]
    
    if len(outcome_labels) < min_closed_samples:
        result["reason"] = f"insufficient_train_samples: {len(outcome_labels)} < {min_closed_samples}"
        return result
    
    output_dir = Path(route.output_dir) / "ml_models"
    
    try:
        # Train outcome classifier
        X_train, y_train, _ = vectors_to_numpy(outcome_labels, feature_names)
        X_test, y_test, _ = vectors_to_numpy(test_outcome_labels, feature_names)
        
        if len(X_train) > 0 and len(X_test) > 0 and len(np.unique(y_train)) > 0:
            outcome_model, outcome_result = train_outcome_classifier(
                X_train, y_train, X_test, y_test,
                model_type="logistic",
                feature_names=feature_names,
            )
            save_model(outcome_model, output_dir / "outcome_classifier.pkl")
            save_model_metadata(outcome_result, output_dir / "outcome_classifier_metadata.json")
            result["models_trained"].append("outcome_classifier")
    except Exception as exc:
        result["outcome_classifier_error"] = str(exc)
    
    try:
        # Train realized R regressor
        realized_r_labels = [v for v in train_vectors if v.realized_r_label is not None]
        test_realized_r_labels = [v for v in test_vectors if v.realized_r_label is not None]
        
        if len(realized_r_labels) >= min_closed_samples // 2:
            X_train_r, _, y_train_r = vectors_to_numpy(realized_r_labels, feature_names)
            X_test_r, _, y_test_r = vectors_to_numpy(test_realized_r_labels, feature_names)
            
            if len(X_train_r) > 0 and len(X_test_r) > 0:
                realized_r_model, realized_r_result = train_realized_r_regressor(
                    X_train_r, y_train_r, X_test_r, y_test_r,
                    model_type="decision_tree",
                    feature_names=feature_names,
                )
                save_model(realized_r_model, output_dir / "realized_r_regressor.pkl")
                save_model_metadata(realized_r_result, output_dir / "realized_r_regressor_metadata.json")
                result["models_trained"].append("realized_r_regressor")
    except Exception as exc:
        result["realized_r_regressor_error"] = str(exc)
    
    if result["models_trained"]:
        result["status"] = "success"
        result["reason"] = None
        result["train_count"] = len(outcome_labels)
        result["test_count"] = len(test_outcome_labels)
        result["feature_count"] = len(feature_names)
    
    return result


def run_route(route: StrategyRoute, environment: str, price: str, token: str | None) -> dict[str, object]:
    strategy = get_strategy(route.strategy_id)
    managed_events = bool(getattr(strategy, "managed_events", False))
    output_dir = Path(route.output_dir)
    cycle_started_at = datetime.now(timezone.utc)
    health_log_path = _resolved_route_path(output_dir, route.health_log_file, "route_cycle_log.csv")
    health_snapshot_path = _resolved_route_path(output_dir, route.health_snapshot_file, "health_snapshot.json")
    dispatch_failure_log_path = output_dir / "dispatch_failures.jsonl"
    ladder_ledger_path = _resolved_route_path(output_dir, route.ladder_ledger_file, "ladder_ledger.json")
    dispatch_errors: list[str] = []
    dispatch_failure_rows: list[dict[str, object]] = []
    last_successful_discord_post_utc: str | None = None
    if not managed_events:
        journal_entries = load_journal(route.journal_file)
        journal_entries = enrich_ladder_fields(journal_entries)
        journal_entries = refresh_open_entries(
            journal_entries,
            token=token,
            environment=environment,
            price=price,
            outcome_price_mode=_outcome_price_mode(route),
        )
        save_journal(route.journal_file, journal_entries)
        save_ladder_ledger(ladder_ledger_path, journal_entries)
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
    dispatchable_signals = (
        effective_signals
        if _post_reinforcement_alerts(route)
        else [signal for signal in effective_signals if signal.is_tradable]
    )
    sent_setup_ids = load_sent_setup_ids(route.state_file)
    if managed_events:
        pending_outcomes = []
        outcomes_to_send = []
        unsent_signals = new_signals_only(dispatchable_signals, sent_setup_ids)
        fresh_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) != "catch_up"]
        recovered_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) == "catch_up"]
        recovered_signals = recovered_signals[: route.max_catch_up_entries_per_run]
        suppressed_duplicates = len(dispatchable_signals) - len(unsent_signals)
        enriched_fresh_signals = fresh_signals
        enriched_recovered_signals = recovered_signals
        latest_stats = None
        journal_metrics = None
    else:
        journal_entries = backfill_known_signals(journal_entries, tradable_signals, sent_setup_ids)
        pending_outcomes = pending_outcome_notifications(journal_entries)
        outcomes_to_send = pending_outcome_notifications(journal_entries, limit=route.max_backfill_outcomes_per_run)
        unsent_signals = new_signals_only(dispatchable_signals, sent_setup_ids)
        fresh_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) != "catch_up"]
        recovered_signals = [signal for signal in unsent_signals if _signal_delivery_kind(signal) == "catch_up"]
        recovered_signals = recovered_signals[: route.max_catch_up_entries_per_run]
        suppressed_duplicates = len(dispatchable_signals) - len(unsent_signals)
        stats = build_stats_snapshot(journal_entries)
        journal_metrics = compute_strategy_metrics(journal_entries)
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
                dispatch_failure_rows.append(
                    {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "route": route.strategy_id,
                        "strategy_name": strategy.strategy_name,
                        "stage": "outcome",
                        "setup_id": outcome.setup_id,
                        "error": str(exc),
                    }
                )
                continue
            outcome.outcome_notified = True
            outcomes_sent += 1
            last_successful_discord_post_utc = datetime.now(timezone.utc).isoformat()
        model_dir = Path(route.output_dir) / "ml_models"
        predictions_path = _predictions_log_path(output_dir)
        for signal in enriched_fresh_signals:
            try:
                _send_discord_signal_with_ml(route, strategy, signal, model_dir, predictions_path)
            except Exception as exc:
                dispatch_errors.append(f"signal:{signal.setup_id}:{exc}")
                dispatch_failure_rows.append(
                    {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "route": route.strategy_id,
                        "strategy_name": strategy.strategy_name,
                        "stage": "signal",
                        "setup_id": signal.setup_id,
                        "delivery_kind": _signal_delivery_kind(signal),
                        "error": str(exc),
                    }
                )
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
                _send_discord_signal_with_ml(route, strategy, signal, model_dir, predictions_path)
            except Exception as exc:
                dispatch_errors.append(f"signal:{signal.setup_id}:{exc}")
                dispatch_failure_rows.append(
                    {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "route": route.strategy_id,
                        "strategy_name": strategy.strategy_name,
                        "stage": "signal",
                        "setup_id": signal.setup_id,
                        "delivery_kind": _signal_delivery_kind(signal),
                        "error": str(exc),
                    }
                )
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
                try:
                    send_discord_report(
                        route.discord_webhook_url,
                        weekly_summary,
                        username=f"{strategy.strategy_name} Review",
                        strategy_name=strategy.strategy_name,
                    )
                    _send_weekly_prediction_performance(route, strategy, predictions_path, journal_entries)
                except Exception as exc:
                    dispatch_errors.append(f"report:weekly:{exc}")
                    dispatch_failure_rows.append(
                        {
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "route": route.strategy_id,
                            "strategy_name": strategy.strategy_name,
                            "stage": "weekly_report",
                            "error": str(exc),
                        }
                    )
                else:
                    report_state["weekly"] = weekly_key
            if route.send_monthly_report and journal_entries and report_state.get("monthly") != monthly_key:
                monthly_summary = journal_summary_data(journal_entries, "Monthly", now - timedelta(days=30))
                try:
                    send_discord_report(
                        route.discord_webhook_url,
                        monthly_summary,
                        username=f"{strategy.strategy_name} Review",
                        strategy_name=strategy.strategy_name,
                    )
                except Exception as exc:
                    dispatch_errors.append(f"report:monthly:{exc}")
                    dispatch_failure_rows.append(
                        {
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "route": route.strategy_id,
                            "strategy_name": strategy.strategy_name,
                            "stage": "monthly_report",
                            "error": str(exc),
                        }
                    )
                else:
                    report_state["monthly"] = monthly_key
            save_report_state(route.report_state_file, report_state)
    elif route.dispatch == "none":
        pass
    else:
        raise ValueError(f"Unsupported dispatch type: {route.dispatch}")

    if not managed_events:
        journal_entries = append_new_signals(journal_entries, delivered_tradable)
        save_journal(route.journal_file, journal_entries)
        save_ladder_ledger(ladder_ledger_path, journal_entries)
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
        "dispatchable_signals": len(dispatchable_signals),
        "reinforcement_alerts_suppressed": len(reinforcement_signals) if not _post_reinforcement_alerts(route) else 0,
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
        "ladder_ledger_file": str(ladder_ledger_path),
        "report_state_file": route.report_state_file,
        "stats_snapshot": latest_stats.to_dict() if latest_stats is not None else None,
        "metrics_snapshot": journal_metrics if not managed_events else None,
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
    if journal_metrics is not None:
        summary["performance_text"] = performance_summary_text(journal_metrics["summary"])
        # Include grouped metrics for deeper analysis
        summary["performance_by_scenario"] = journal_metrics.get("by_scenario", {})
        summary["performance_by_quality_grade"] = journal_metrics.get("by_quality_grade", {})
        summary["performance_by_asset_class"] = journal_metrics.get("by_asset_class", {})
        summary["performance_by_time_of_day"] = journal_metrics.get("by_time_of_day", {})
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
    
    # Add performance metrics to health snapshot if available
    if journal_metrics is not None and not managed_events:
        summary_metrics = journal_metrics.get("summary", {})
        health_snapshot["performance_metrics"] = {
            "win_rate": summary_metrics.get("win_rate", 0.0),
            "closed_count": summary_metrics.get("closed_count", 0),
            "expectancy_r": summary_metrics.get("expectancy_r", 0.0),
            "payoff_ratio": summary_metrics.get("payoff_ratio", 0.0),
            "total_realized_r": summary_metrics.get("total_realized_r", 0.0),
            "probability_of_ruin": summary_metrics.get("probability_of_ruin", 0.0),
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
    _append_dispatch_failures(dispatch_failure_log_path, dispatch_failure_rows)
    
    # Train ML models if not managed_events
    if not managed_events:
        try:
            ml_result = _train_route_ml_models(route)
            summary["ml_training"] = ml_result
        except Exception as exc:
            summary["ml_training"] = {
                "status": "error",
                "error": str(exc),
            }
    
    return summary


def run_platform_config(config_path: str | Path, token: str | None) -> list[dict[str, object]]:
    config = load_platform_config(config_path)
    results: list[dict[str, object]] = []
    for route in config.routes:
        if not route.enabled:
            continue
        started_at = datetime.now(timezone.utc)
        strategy_name = route.strategy_id
        try:
            strategy = get_strategy(route.strategy_id)
            strategy_name = strategy.strategy_name
            results.append(run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token))
        except Exception as exc:
            results.append(_record_route_failure(route, strategy_name=strategy_name, started_at=started_at, exc=exc))
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
    started_at = datetime.now(timezone.utc)
    strategy_name = route.strategy_id
    try:
        strategy = get_strategy(route.strategy_id)
        strategy_name = strategy.strategy_name
        return run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token)
    except Exception as exc:
        return _record_route_failure(route, strategy_name=strategy_name, started_at=started_at, exc=exc)


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
    heartbeat_path = Path("logs") / "signal_platform_heartbeat.json"

    while True:
        now = time.time()
        cycle_started_at = datetime.now(timezone.utc)
        heartbeat_payload = {
            "status": "running",
            "cycle": cycle + 1,
            "started_at_utc": cycle_started_at.isoformat(),
            "poll_seconds": poll_seconds,
            "enabled_routes": [route.strategy_id for route in config.routes if route.enabled],
            "routes_due": [],
        }
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
            heartbeat_payload["routes_due"].append(route.strategy_id)
            strategy_name = route.strategy_id
            try:
                strategy = get_strategy(route.strategy_id)
                strategy_name = strategy.strategy_name
                summary = run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token)
            except Exception as exc:
                summary = _record_route_failure(route, strategy_name=strategy_name, started_at=cycle_started_at, exc=exc)
            results.append(summary)
            last_run_at[route_key] = now
        heartbeat_payload["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        heartbeat_payload["results_recorded"] = len(results)
        _write_service_heartbeat(heartbeat_path, heartbeat_payload)
        cycle += 1
        if max_cycles is not None and cycle >= max_cycles:
            return results
        time.sleep(max(5, poll_seconds))
