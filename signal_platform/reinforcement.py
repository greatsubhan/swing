"""Structure-aware signal reinforcement handling.

This module converts duplicate same-structure signals into reinforcement
events while keeping the first valid setup as the only tradable signal.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import JournalEntry, PlatformSignal, ReinforcementConfig, SignalStructure


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reinforcement_config_from_route_extra(extra: dict[str, Any] | None) -> ReinforcementConfig:
    """Build a reinforcement config from route extras."""
    payload = (extra or {}).get("signal_reinforcement", {})
    if not isinstance(payload, dict):
        return ReinforcementConfig()
    return ReinforcementConfig(
        enabled=bool(payload.get("enabled", False)),
        state_file=payload.get("state_file"),
        decision_log_file=payload.get("decision_log_file"),
        base_strength_score=int(payload.get("base_strength_score", 50)),
        max_strength_score=int(payload.get("max_strength_score", 100)),
        quality_improvement_points=int(payload.get("quality_improvement_points", 5)),
        continuation_points=int(payload.get("continuation_points", 5)),
        structure_holds_points=int(payload.get("structure_holds_points", 3)),
        htf_alignment_points=int(payload.get("htf_alignment_points", 3)),
        enable_r_scaling=bool(payload.get("enable_r_scaling", False)),
        r_scale_per_reinforcement=float(payload.get("r_scale_per_reinforcement", 0.25)),
        max_effective_r_exposure=float(payload.get("max_effective_r_exposure", 2.0)),
    )


def load_structure_state(path: str | Path) -> dict[str, SignalStructure]:
    state_path = Path(path)
    if not state_path.exists():
        return {}
    payload = json.loads(state_path.read_text(encoding="utf-8") or "{}")
    structures = payload.get("structures", payload)
    if not isinstance(structures, dict):
        return {}
    return {
        structure_id: SignalStructure(**structure_payload)
        for structure_id, structure_payload in structures.items()
    }


def save_structure_state(path: str | Path, structures: dict[str, SignalStructure]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"updated_at_utc": _utc_now_iso(), "structures": {key: value.to_dict() for key, value in structures.items()}}, indent=2),
        encoding="utf-8",
    )


def append_reinforcement_decisions(path: str | Path, decisions: list[dict[str, Any]]) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision) + "\n")


@dataclass
class ReinforcementProcessingResult:
    tradable_signals: list[PlatformSignal]
    reinforcement_signals: list[PlatformSignal]
    all_signals: list[PlatformSignal]
    structures: dict[str, SignalStructure]
    decisions: list[dict[str, Any]]


def _structure_key(symbol: str, timeframe: str, side: str) -> str:
    return f"{symbol}|{timeframe}|{side}"


def _find_active_structure(
    structures: dict[str, SignalStructure],
    *,
    symbol: str,
    timeframe: str,
    side: str,
) -> SignalStructure | None:
    active = [
        structure
        for structure in structures.values()
        if structure.symbol == symbol
        and structure.timeframe == timeframe
        and structure.side == side
        and structure.status == "active"
    ]
    if not active:
        return None
    active.sort(key=lambda structure: (_parse_timestamp(structure.last_signal_timestamp), structure.structure_id), reverse=True)
    return active[0]


def _sync_structure_statuses(
    structures: dict[str, SignalStructure],
    journal_entries: list[JournalEntry],
) -> None:
    journal_by_setup_id = {entry.setup_id: entry for entry in journal_entries}
    for structure in structures.values():
        root_entry = journal_by_setup_id.get(structure.root_signal_id)
        if root_entry is None:
            continue
        if root_entry.status != "closed":
            continue
        structure.last_update_timestamp = root_entry.outcome_timestamp or root_entry.last_update_timestamp or structure.last_update_timestamp
        structure.current_status = "closed" if root_entry.outcome == "tp_hit" else "invalidated"
        structure.status = "closed" if root_entry.outcome == "tp_hit" else "invalidated"


def _has_htf_alignment(signal: PlatformSignal) -> bool:
    raw = signal.raw_signal or {}
    if "htf_alignment" in raw:
        return bool(raw["htf_alignment"])
    if raw.get("bias_timeframe"):
        return True
    return False


def _build_root_summary(signal: PlatformSignal) -> str:
    return (
        f"{signal.summary} This is the primary tradable signal for the current structure."
    )


def _build_reinforcement_summary(signal: PlatformSignal, structure: SignalStructure) -> str:
    return (
        f"Structure still holds for {signal.symbol} {signal.timeframe.upper()} {signal.side.upper()}. "
        f"Strength is now {structure.strength_score}/100 after {structure.reinforcement_count} reinforcement"
        f"{'' if structure.reinforcement_count == 1 else 's'}. No new trade; reinforcement only."
    )


def _build_structure(
    signal: PlatformSignal,
    config: ReinforcementConfig,
) -> SignalStructure:
    structure_id = f"{signal.strategy_id}:{signal.symbol}:{signal.timeframe}:{signal.side}:{signal.setup_id}"
    return SignalStructure(
        structure_id=structure_id,
        strategy_id=signal.strategy_id,
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        side=signal.side,
        start_timestamp=signal.timestamp,
        last_update_timestamp=signal.timestamp,
        status="active",
        root_signal_id=signal.setup_id,
        reinforcement_count=0,
        strength_score=config.base_strength_score,
        best_quality_score=signal.quality_score,
        current_status="active",
        entry=signal.entry,
        stop_loss=signal.stop_loss,
        target_1=signal.target_1,
        last_signal_timestamp=signal.timestamp,
        last_signal_id=signal.setup_id,
        htf_alignment_active=_has_htf_alignment(signal),
        effective_r_exposure=1.0,
    )


def _annotate_root_signal(signal: PlatformSignal, structure: SignalStructure) -> PlatformSignal:
    raw_signal = {
        **signal.raw_signal,
        "event_type": "entry",
        "structure_id": structure.structure_id,
        "root_signal_id": structure.root_signal_id,
        "reinforcement_count": 0,
        "strength_score": structure.strength_score,
        "structure_status": structure.status,
        "reinforcement_reason": "first_valid_signal_in_structure",
        "is_tradable": True,
    }
    return replace(
        signal,
        summary=_build_root_summary(signal),
        alert_text=_build_root_summary(signal),
        is_tradable=True,
        structure_id=structure.structure_id,
        root_signal_id=structure.root_signal_id,
        reinforcement_count=0,
        strength_score=structure.strength_score,
        raw_signal=raw_signal,
    )


def _apply_strength_update(
    structure: SignalStructure,
    signal: PlatformSignal,
    config: ReinforcementConfig,
) -> tuple[SignalStructure, list[str]]:
    reasons: list[str] = []
    score_delta = 0
    if signal.quality_score is not None and (
        structure.best_quality_score is None or signal.quality_score > structure.best_quality_score
    ):
        score_delta += config.quality_improvement_points
        reasons.append("quality_score_improved")
        structure.best_quality_score = signal.quality_score
    score_delta += config.continuation_points
    reasons.append("continuation_confirmed")
    score_delta += config.structure_holds_points
    reasons.append("structure_holds")
    if _has_htf_alignment(signal):
        score_delta += config.htf_alignment_points
        reasons.append("htf_alignment_maintained")
        structure.htf_alignment_active = True
    structure.reinforcement_count += 1
    structure.last_update_timestamp = signal.timestamp
    structure.last_signal_timestamp = signal.timestamp
    structure.last_signal_id = signal.setup_id
    structure.strength_score = min(config.max_strength_score, structure.strength_score + score_delta)
    if config.enable_r_scaling:
        effective_r = 1.0 + (structure.reinforcement_count * config.r_scale_per_reinforcement)
        structure.effective_r_exposure = min(config.max_effective_r_exposure, effective_r)
    return structure, reasons


def _annotate_reinforcement_signal(
    signal: PlatformSignal,
    structure: SignalStructure,
    reasons: list[str],
    config: ReinforcementConfig,
) -> PlatformSignal:
    raw_signal = {
        **signal.raw_signal,
        "event_type": "reinforcement",
        "structure_id": structure.structure_id,
        "root_signal_id": structure.root_signal_id,
        "reinforcement_count": structure.reinforcement_count,
        "strength_score": structure.strength_score,
        "structure_status": structure.status,
        "reinforcement_reason": "same_active_structure",
        "reinforcement_components": reasons,
        "is_tradable": False,
        "effective_r_exposure": structure.effective_r_exposure if config.enable_r_scaling else 1.0,
        "r_scaling_enabled": config.enable_r_scaling,
    }
    return replace(
        signal,
        summary=_build_reinforcement_summary(signal, structure),
        alert_text=_build_reinforcement_summary(signal, structure),
        is_tradable=False,
        structure_id=structure.structure_id,
        root_signal_id=structure.root_signal_id,
        reinforcement_count=structure.reinforcement_count,
        strength_score=structure.strength_score,
        raw_signal=raw_signal,
    )


def apply_signal_reinforcement(
    *,
    signals: list[PlatformSignal],
    journal_entries: list[JournalEntry],
    existing_structures: dict[str, SignalStructure],
    config: ReinforcementConfig,
) -> ReinforcementProcessingResult:
    """Convert duplicate same-structure signals into reinforcement events.

    The underlying signal list is processed in chronological order. The first
    valid signal for a structure remains tradable; subsequent same-side signals
    while that structure is active become non-tradable reinforcement updates.
    """
    if not config.enabled:
        return ReinforcementProcessingResult(
            tradable_signals=signals,
            reinforcement_signals=[],
            all_signals=signals,
            structures=existing_structures,
            decisions=[],
        )

    structures = dict(existing_structures)
    _sync_structure_statuses(structures, journal_entries)

    tradable: list[PlatformSignal] = []
    reinforcements: list[PlatformSignal] = []
    decisions: list[dict[str, Any]] = []

    ordered_signals = sorted(signals, key=lambda signal: (_parse_timestamp(signal.timestamp), signal.setup_id))

    for signal in ordered_signals:
        if str(signal.raw_signal.get("event_type", "entry")).lower() != "entry":
            tradable.append(signal)
            decisions.append(
                {
                    "timestamp": signal.timestamp,
                    "signal_id": signal.setup_id,
                    "symbol": signal.symbol,
                    "timeframe": signal.timeframe,
                    "side": signal.side,
                    "classification": "passthrough",
                    "reason": "non_entry_event",
                }
            )
            continue

        active_same = _find_active_structure(
            structures,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            side=signal.side,
        )

        if active_same is not None:
            if active_same.root_signal_id == signal.setup_id:
                root_signal = _annotate_root_signal(signal, active_same)
                tradable.append(root_signal)
                decisions.append(
                    {
                        "timestamp": signal.timestamp,
                        "signal_id": signal.setup_id,
                        "symbol": signal.symbol,
                        "timeframe": signal.timeframe,
                        "side": signal.side,
                        "classification": "root_signal",
                        "structure_id": active_same.structure_id,
                        "root_signal_id": active_same.root_signal_id,
                        "strength_score": active_same.strength_score,
                        "reason": "existing_root_signal_replayed",
                    }
                )
                continue
            updated_structure, reasons = _apply_strength_update(active_same, signal, config)
            structures[updated_structure.structure_id] = updated_structure
            reinforcement_signal = _annotate_reinforcement_signal(signal, updated_structure, reasons, config)
            reinforcements.append(reinforcement_signal)
            decisions.append(
                {
                    "timestamp": signal.timestamp,
                    "signal_id": signal.setup_id,
                    "symbol": signal.symbol,
                    "timeframe": signal.timeframe,
                    "side": signal.side,
                    "classification": "reinforcement",
                    "structure_id": updated_structure.structure_id,
                    "root_signal_id": updated_structure.root_signal_id,
                    "reinforcement_count": updated_structure.reinforcement_count,
                    "strength_score": updated_structure.strength_score,
                    "reason": "active_structure_continues",
                    "components": reasons,
                }
            )
            continue

        opposite_side = "short" if signal.side.lower() == "long" else "long"
        active_opposite = _find_active_structure(
            structures,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            side=opposite_side,
        )
        if active_opposite is not None:
            active_opposite.status = "invalidated"
            active_opposite.current_status = "invalidated"
            active_opposite.last_update_timestamp = signal.timestamp
            structures[active_opposite.structure_id] = active_opposite

        structure = _build_structure(signal, config)
        structures[structure.structure_id] = structure
        root_signal = _annotate_root_signal(signal, structure)
        tradable.append(root_signal)
        decisions.append(
            {
                "timestamp": signal.timestamp,
                "signal_id": signal.setup_id,
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "side": signal.side,
                "classification": "root_signal",
                "structure_id": structure.structure_id,
                "root_signal_id": structure.root_signal_id,
                "strength_score": structure.strength_score,
                "reason": "first_valid_signal_in_structure",
            }
        )

    all_signals = sorted([*tradable, *reinforcements], key=lambda signal: (_parse_timestamp(signal.timestamp), signal.setup_id))
    return ReinforcementProcessingResult(
        tradable_signals=tradable,
        reinforcement_signals=reinforcements,
        all_signals=all_signals,
        structures=structures,
        decisions=decisions,
    )
