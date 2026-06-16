"""Data models for Discord journal import pipeline."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class DiscordImportedEntry:
    """A normalized trade event record imported from Discord message history."""

    # --- Provenance (always preserved) ---
    imported_from: str = "discord"
    imported_at: str = ""  # ISO timestamp of import
    parser_version: str = "1.0"
    raw_message_ids: list[str] = field(default_factory=list)
    source_channel_id: str = ""
    source_channel_name: str = ""
    confidence: str = "unknown"  # exact_match | high | medium | low | unknown

    # --- Event Classification ---
    event_type: str = "unknown"  # signal_entry | outcome | weekly_report | monthly_report | ml_performance | manual_comment | system_notification | unknown

    # --- Strategy/Signal Identification ---
    strategy_id: str | None = None
    route_id: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    setup_id: str | None = None
    direction: str | None = None  # long | short

    # --- Trade Parameters ---
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: list[float] = field(default_factory=list)
    risk_reward: float | None = None
    asset_class: str | None = None

    # --- Timing ---
    signal_timestamp: str | None = None
    result_timestamp: str | None = None

    # --- Outcome ---
    result_status: str = "unknown"  # open | tp | sl | partial | cancelled | unknown
    realized_r: float | None = None
    exit_price: float | None = None

    # --- Matching ---
    matched_to_setup_id: str | None = None
    matching_method: str | None = None  # setup_id_footer | symbol+timeframe+side+proximity | reply_thread | none

    # --- Raw Parsing Artifacts ---
    raw_content: str = ""
    raw_embed_title: str | None = None
    raw_footer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RawMessageArchive:
    """Raw Discord message payload preserved for reprocessing."""

    raw_message_id: str = ""
    channel_id: str = ""
    channel_name: str = ""
    fetched_at_utc: str = ""
    message_timestamp: str = ""
    raw_content: str = ""
    raw_embeds: list[dict[str, Any]] = field(default_factory=list)
    raw_attachments: list[str] = field(default_factory=list)
    raw_reactions: list[dict[str, Any]] = field(default_factory=list)
    raw_reference: dict[str, Any] | None = None
    parser_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscordImportState:
    """State tracking for incremental sync."""

    last_sync_utc: str = ""
    last_imported_message_id_per_channel: dict[str, str] = field(default_factory=dict)
    imported_message_ids: list[str] = field(default_factory=list)
    total_imported_records: int = 0
    total_matched_outcomes: int = 0
    total_unmatched_outcomes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DiscordImportState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DiscordImportSummary:
    """Summary of a single import run."""

    started_at_utc: str = ""
    finished_at_utc: str = ""
    route: str = ""
    messages_fetched: int = 0
    messages_already_imported: int = 0
    new_messages: int = 0
    events_parsed: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    outcomes_matched: int = 0
    outcomes_unmatched: int = 0
    confidence_breakdown: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MergedRouteMetrics:
    """Merged metrics for a route showing native + discord-imported + combined."""

    native_journal: dict[str, Any] = field(default_factory=dict)
    discord_imported: dict[str, Any] = field(default_factory=dict)
    combined: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "native_journal": self.native_journal,
            "discord_imported": self.discord_imported,
            "combined": self.combined,
            "runtime": self.runtime,
        }


def save_import_state(path: str | Path, state: DiscordImportState) -> None:
    """Save import state to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state.to_dict(), indent=2))


def load_import_state(path: str | Path) -> DiscordImportState:
    """Load import state from disk, or return empty state."""
    p = Path(path)
    if not p.exists():
        return DiscordImportState()
    try:
        return DiscordImportState.from_dict(json.loads(p.read_text() or "{}"))
    except (json.JSONDecodeError, Exception):
        return DiscordImportState()


def save_imported_entries(path: str | Path, entries: list[DiscordImportedEntry]) -> None:
    """Save normalized imported entries to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([e.to_dict() for e in entries], indent=2))


def load_imported_entries(path: str | Path) -> list[DiscordImportedEntry]:
    """Load normalized imported entries from a JSON file."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text() or "[]")
    except (json.JSONDecodeError, Exception):
        return []
    if not isinstance(data, list):
        return []
    entries = []
    for item in data:
        if not isinstance(item, dict):
            continue
        allowed = {f.name for f in DiscordImportedEntry.__dataclass_fields__.values()}
        normalized = {k: v for k, v in item.items() if k in allowed}
        entries.append(DiscordImportedEntry(**normalized))
    return entries


def append_raw_archive(path: str | Path, records: list[RawMessageArchive]) -> None:
    """Append raw message records to the archive (JSONL format)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record.to_dict(), separators=(",", ":")) + "\n")


def load_raw_archive_ids(path: str | Path) -> set[str]:
    """Load all message IDs already in the archive (for deduplication)."""
    p = Path(path)
    if not p.exists():
        return set()
    ids: set[str] = set()
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    mid = record.get("raw_message_id", "")
                    if mid:
                        ids.add(mid)
                except (json.JSONDecodeError, KeyError):
                    continue
    except (OSError, IOError):
        pass
    return ids