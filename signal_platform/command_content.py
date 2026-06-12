"""Thoughtful strategy/help/status content for the Discord command bot."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .journal import load_journal
from .runtime import StrategyRoute, load_platform_config


@dataclass(frozen=True)
class StrategyCard:
    strategy_id: str
    title: str
    aliases: tuple[str, ...]
    cadence: str
    summary: str
    usage: str
    watch_for: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class CommandField:
    name: str
    value: str
    inline: bool = False


@dataclass(frozen=True)
class CommandCard:
    title: str
    description: str
    fields: tuple[CommandField, ...] = ()
    color: int = 0x5865F2


_STRATEGY_CARDS: tuple[StrategyCard, ...] = (
    StrategyCard(
        strategy_id="little_rzy",
        title="Measured Drift",
        aliases=("measured", "drift", "little_rzy", "little rzy", "rzy"),
        cadence="4h tactical signals",
        summary="Trend-following continuation setups built around structure, measured move logic, and controlled invalidation.",
        usage="Wait for a full 4h setup card, use the posted entry / stop / target plan, and size it to your own account rules.",
        watch_for="Selective swing setups rather than a high-frequency feed.",
        bullets=(
            "Best when clean structure and measured move logic line up together.",
            "Weekly and monthly reviews track realized outcomes so the board stays accountable.",
            "Quiet periods are normal because it waits for higher-quality 4h continuation structure.",
        ),
    ),
    StrategyCard(
        strategy_id="strategy_two",
        title="Trend Current",
        aliases=("trend", "trend_current", "strategy_two", "current"),
        cadence="4h managed baskets",
        summary="A stateful continuation strategy that builds a position as one coordinated basket, not as isolated random trades.",
        usage="Treat basket alerts, adds, stop moves, and exits as one idea being managed over time.",
        watch_for="Lower alert frequency, but richer lifecycle updates when a basket is active.",
        bullets=(
            "Basket-level risk matters more here than single-trade noise.",
            "New basket, add, stop move, and basket exit all belong to the same managed position.",
            "This board is intentionally patient because it waits for trend plus pullback alignment.",
        ),
    ),
    StrategyCard(
        strategy_id="strategy_four",
        title="Cambist With Trend",
        aliases=("cwt", "cambist", "strategy_four", "with trend"),
        cadence="M5/M15 execution with H1 bias",
        summary="Lower-timeframe continuation entries filtered by H1 bias, Alligator structure, and Cambist/ZigZag-style confirmation.",
        usage="Use it as a continuation plan: follow the posted side, respect the stop, and note the recommended ladder step in the card.",
        watch_for="More tactical flow than the 4h boards, but still selective when the trend filter is working properly.",
        bullets=(
            "Execution is on 5m or 15m depending on the asset, never on 4h.",
            "Recent missed setups can now be recovered after short downtime windows.",
            "Outcome follow-ups post even if the runner was briefly down or late.",
        ),
    ),
    StrategyCard(
        strategy_id="strategy_five",
        title="Secular Bull SIP",
        aliases=("sip", "secular", "bull", "strategy_five"),
        cadence="Monthly allocation board",
        summary="A long-only macro basket for Gold, Silver, Nasdaq, US30, and Bitcoin, with trend-filtered monthly adds.",
        usage="Think of it as an allocation board, not a fast signal bot. Follow the monthly budget math and only add the assets marked active.",
        watch_for="Monthly allocation and review events, not frequent TP / SL trade alerts.",
        bullets=(
            "Current live mode only adds when the long-term trend is with us.",
            "The board communicates planned adds, skipped assets, and month-end review updates.",
            "Followers still manage their own broker execution and sizing.",
        ),
    ),
)


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().replace("-", " ").replace("_", " ").split())


def _format_timestamp(timestamp: str | None) -> str:
    if not timestamp:
        return "n/a"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return timestamp
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _strategy_title(strategy_id: str) -> str:
    for card in _STRATEGY_CARDS:
        if card.strategy_id == strategy_id:
            return card.title
    return strategy_id


def _route_snapshot_path(route: StrategyRoute) -> Path:
    return Path(route.health_snapshot_file) if route.health_snapshot_file else Path(route.output_dir) / "health_snapshot.json"


def _route_summary_path(route: StrategyRoute) -> Path:
    return Path(route.output_dir) / "platform_run_summary.json"


def _route_signals_path(route: StrategyRoute) -> Path:
    return Path(route.output_dir) / "signals.json"


def _route_ladder_path(route: StrategyRoute) -> Path:
    return Path(route.ladder_ledger_file) if route.ladder_ledger_file else Path(route.output_dir) / "ladder_ledger.json"


def available_strategy_titles() -> list[str]:
    return [card.title for card in _STRATEGY_CARDS]


def resolve_strategy_card(query: str | None) -> StrategyCard | None:
    if not query:
        return None
    normalized = _normalize(query)
    for card in _STRATEGY_CARDS:
        if normalized == _normalize(card.strategy_id):
            return card
        if normalized == _normalize(card.title):
            return card
        if any(normalized == _normalize(alias) for alias in card.aliases):
            return card
    return None


def _status_emoji(dispatch_errors: int, last_refresh: str | None, quiet_reason: str | None) -> str:
    if dispatch_errors > 0:
        return "🔴"
    if not last_refresh:
        return "🟡"
    if quiet_reason in {"no_signal", "duplicate_suppression"}:
        return "🟢"
    return "🟢"


def _route_status_data(config_path: str | Path) -> list[dict[str, object]]:
    config = load_platform_config(config_path)
    rows: list[dict[str, object]] = []
    for route in config.routes:
        if not route.enabled:
            continue
        snapshot_path = _route_snapshot_path(route)
        payload: dict[str, object] = {}
        if snapshot_path.exists():
            payload = json.loads(snapshot_path.read_text() or "{}")
        summary_path = _route_summary_path(route)
        if summary_path.exists():
            payload.setdefault("summary", json.loads(summary_path.read_text() or "{}"))
        quiet_reason = str(payload.get("quiet_reason") or "active")
        dispatch_errors = int(payload.get("dispatch_error_count", 0))
        last_refresh = payload.get("last_successful_market_refresh_utc")
        last_discord = payload.get("last_successful_discord_post_utc")
        emoji = _status_emoji(dispatch_errors, str(last_refresh) if last_refresh else None, quiet_reason)
        rows.append(
            {
                "route": route,
                "strategy_id": route.strategy_id,
                "title": _strategy_title(route.strategy_id),
                "emoji": emoji,
                "quiet_reason": quiet_reason,
                "last_refresh": _format_timestamp(str(last_refresh) if last_refresh else None),
                "last_discord": _format_timestamp(str(last_discord) if last_discord else None),
                "fresh_signals": int(payload.get("fresh_signals", 0)),
                "recovered_entries_found": int(payload.get("recovered_entries_found", 0)),
                "recovered_entries_sent": int(payload.get("recovered_entries_sent", 0)),
                "pending_outcomes": int(payload.get("pending_unnotified_outcomes_count", 0)),
                "outcomes_sent": int(payload.get("outcomes_sent", 0)),
                "suppressed_duplicates": int(payload.get("suppressed_duplicates", 0)),
                "dispatch_errors": dispatch_errors,
                "managed_events": bool(payload.get("managed_events", False)),
            }
        )
    return rows


def _recent_tactical_activity(route: StrategyRoute) -> tuple[str, str]:
    entries = load_journal(route.journal_file)
    if not entries:
        return ("No recorded trade activity yet.", "No signal journal entries found for this board.")
    latest_signal = max(entries, key=lambda entry: entry.dispatched_at_utc)
    latest_closed = [entry for entry in entries if entry.status == "closed" and entry.outcome_timestamp]
    if latest_closed:
        latest_outcome = max(latest_closed, key=lambda entry: entry.outcome_timestamp or "")
        outcome_text = (
            f"Latest outcome: {latest_outcome.symbol} {latest_outcome.timeframe.upper()} "
            f"{(latest_outcome.outcome or 'closed').replace('_', ' ')} at {_format_timestamp(latest_outcome.outcome_timestamp)}."
        )
    else:
        outcome_text = "No closed outcomes recorded yet."
    latest_signal_text = (
        f"Latest signal: {latest_signal.symbol} {latest_signal.timeframe.upper()} "
        f"{latest_signal.side.upper()} at {_format_timestamp(latest_signal.dispatched_at_utc)}."
    )
    return latest_signal_text, outcome_text


def _recent_managed_activity(route: StrategyRoute) -> tuple[str, str]:
    signals_path = _route_signals_path(route)
    if not signals_path.exists():
        return ("No managed events recorded yet.", "No signals.json file found for this board.")
    payload = json.loads(signals_path.read_text() or "[]")
    if not payload:
        return ("No managed events recorded yet.", "signals.json exists but is empty.")
    latest_event = max(payload, key=lambda item: str(item.get("timestamp", "")))
    summary = str(latest_event.get("summary") or "Managed event recorded.")
    event_type = str(latest_event.get("raw_signal", {}).get("event_type", "event")).replace("_", " ")
    return (
        f"Latest event: {event_type.title()} at {_format_timestamp(str(latest_event.get('timestamp', '')))}.",
        summary,
    )


def _recent_route_data(config_path: str | Path, query: str | None = None) -> list[dict[str, str]]:
    config = load_platform_config(config_path)
    if query:
        target = resolve_strategy_card(query)
        target_id = target.strategy_id if target else _normalize(query).replace(" ", "_")
        routes = [route for route in config.routes if route.enabled and route.strategy_id == target_id]
    else:
        routes = [route for route in config.routes if route.enabled]
    rows: list[dict[str, str]] = []
    for route in routes:
        summary_text, outcome_text = (
            _recent_managed_activity(route)
            if route.strategy_id == "strategy_five"
            else _recent_tactical_activity(route)
        )
        rows.append(
            {
                "strategy_id": route.strategy_id,
                "title": _strategy_title(route.strategy_id),
                "summary": summary_text,
                "detail": outcome_text,
            }
        )
    return rows


def command_examples() -> tuple[str, ...]:
    return (
        "`boards`",
        "`strategy cwt`",
        "`status`",
        "`status trend`",
        "`status cwt ladder`",
        "`ladder nas100`",
        "`scan`",
        "`scan cwt`",
        "`recent`",
        "`recent measured`",
    )


def build_help_card() -> CommandCard:
    return CommandCard(
        title="Command Guide",
        description="Here are the commands that make the Discord assistant genuinely useful day to day.",
        fields=(
            CommandField("Explore", "`boards` shows every live board and what it is for."),
            CommandField("Understand", "`strategy <board>` explains how one board works and how to use it."),
            CommandField("Check health", "`status` or `status <board>` shows whether a board is healthy, quiet, or behind."),
            CommandField("Check ladder", "`status cwt ladder` gives the CWT ladder snapshot, and `ladder <symbol>` jumps straight to one symbol."),
            CommandField("Check now", "`scan` or `scan <board>` runs a silent one-shot scan without firing live trade alerts."),
            CommandField("See the latest", "`recent` or `recent <board>` shows the latest signal or managed event, plus the latest outcome when available."),
            CommandField("Quick examples", " • ".join(command_examples()), inline=False),
        ),
    )


def build_boards_card() -> CommandCard:
    fields = tuple(
        CommandField(
            card.title,
            f"{card.cadence}\n{card.summary}",
            inline=False,
        )
        for card in _STRATEGY_CARDS
    )
    return CommandCard(
        title="Live Boards",
        description="Each board has a different job. This gives you the fast map before you dive into one of them.",
        fields=fields,
    )


def build_strategy_card_response(query: str | None = None) -> CommandCard:
    card = resolve_strategy_card(query)
    if card is None and query:
        names = ", ".join(available_strategy_titles())
        return CommandCard(
            title="Strategy Not Found",
            description=f"I couldn't match `{query}` to a known strategy. Try one of: {names}.",
            color=0xE67E22,
        )
    if card is None:
        return build_boards_card()
    return CommandCard(
        title=card.title,
        description=card.summary,
        fields=(
            CommandField("Cadence", card.cadence, inline=True),
            CommandField("How to use it", card.usage, inline=False),
            CommandField("What to expect", card.watch_for, inline=False),
            CommandField("Key notes", "\n".join(f"• {bullet}" for bullet in card.bullets), inline=False),
        ),
    )


def _resolve_symbol_lookup(payload: dict[str, object], query: str | None) -> tuple[str | None, dict[str, object] | None]:
    symbols = payload.get("symbols", {})
    if not isinstance(symbols, dict) or not symbols:
        return None, None
    if not query:
        first_symbol = next(iter(symbols.keys()))
        return str(first_symbol), symbols[first_symbol]

    normalized_query = _normalize(query).replace(" ", "").replace("_", "")
    for symbol, symbol_payload in symbols.items():
        symbol_key = _normalize(str(symbol)).replace(" ", "").replace("_", "")
        if normalized_query == symbol_key or normalized_query in symbol_key:
            return str(symbol), symbol_payload
    return None, None


def build_ladder_card(config_path: str | Path, query: str | None = None) -> CommandCard:
    config = load_platform_config(config_path)
    route = next((route for route in config.routes if route.enabled and route.strategy_id == "strategy_four"), None)
    if route is None:
        return CommandCard(
            title="Ladder Not Available",
            description="CWT is not enabled in the current platform config.",
            color=0xE67E22,
        )

    ladder_path = _route_ladder_path(route)
    if not ladder_path.exists():
        return CommandCard(
            title="Ladder Not Available",
            description="The CWT ladder ledger has not been written yet.",
            color=0xE67E22,
        )

    payload = json.loads(ladder_path.read_text() or "{}")
    symbol, symbol_payload = _resolve_symbol_lookup(payload, query)
    if symbol is None or symbol_payload is None:
        requested = query or "that symbol"
        return CommandCard(
            title="Ladder Symbol Not Found",
            description=f"I couldn't match `{requested}` to a tracked CWT symbol.",
            color=0xE67E22,
        )

    current_state = symbol_payload.get("current_state") or {}
    events = symbol_payload.get("events") or []
    latest_event = events[-1] if events else {}
    return CommandCard(
        title=f"Ladder | {symbol}",
        description=(
            f"CWT ladder snapshot. Updated at "
            f"{_format_timestamp(str(current_state.get('updated_at')) if current_state.get('updated_at') else None)}."
        ),
        fields=(
            CommandField(
                "Current",
                (
                    f"step={current_state.get('ladder_step', 'n/a')} | "
                    f"risk={current_state.get('risk_pct', 'n/a')}% | "
                    f"outcome={current_state.get('outcome', 'n/a')}"
                ),
                inline=False,
            ),
            CommandField(
                "Latest Signal",
                (
                    f"{latest_event.get('setup_id', 'n/a')}\n"
                    f"entry_step={latest_event.get('ladder_step_at_entry', 'n/a')} | "
                    f"entry_risk={latest_event.get('ladder_risk_pct_at_entry', 'n/a')}%\n"
                    f"transition={latest_event.get('ladder_transition_note', 'n/a')}"
                ),
                inline=False,
            ),
            CommandField(
                "Previous Reference",
                (
                    f"previous_outcome={latest_event.get('ladder_previous_outcome', 'n/a')}\n"
                    f"previous_setup={latest_event.get('ladder_previous_setup_id', 'n/a')}"
                ),
                inline=False,
            ),
        ),
    )


def build_status_card(config_path: str | Path, query: str | None = None) -> CommandCard:
    if query:
        query_parts = _normalize(query).split()
        if "ladder" in query_parts:
            remaining = [part for part in query_parts if part != "ladder" and part != "cwt"]
            ladder_query = " ".join(remaining) if remaining else None
            return build_ladder_card(config_path, ladder_query)
    rows = _route_status_data(config_path)
    if query:
        card = resolve_strategy_card(query)
        strategy_id = card.strategy_id if card is not None else _normalize(query).replace(" ", "_")
        match = next((row for row in rows if row["strategy_id"] == strategy_id), None)
        if match is None:
            return CommandCard(
                title="Status Not Found",
                description=f"I couldn't find a live route for `{query}`.",
                color=0xE67E22,
            )
        return CommandCard(
            title=f"{match['emoji']} {match['title']}",
            description=f"Latest board health for `{match['strategy_id']}`.",
            fields=(
                CommandField(
                    "State",
                    "Active" if str(match["quiet_reason"]) in {"active", "None", "none", "null"} else str(match["quiet_reason"]).replace("_", " "),
                    inline=True,
                ),
                CommandField("Fresh signals", str(match["fresh_signals"]), inline=True),
                CommandField("Recovered entries sent", str(match["recovered_entries_sent"]), inline=True),
                CommandField("Pending outcomes", str(match["pending_outcomes"]), inline=True),
                CommandField("Last market refresh", str(match["last_refresh"]), inline=True),
                CommandField("Last Discord post", str(match["last_discord"]), inline=True),
                CommandField("Suppressed duplicates", str(match["suppressed_duplicates"]), inline=True),
                CommandField("Dispatch errors", str(match["dispatch_errors"]), inline=True),
            ),
            color=0x2ECC71 if match["dispatch_errors"] == 0 else 0xE74C3C,
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fields = tuple(
        CommandField(
            f"{row['emoji']} {row['title']}",
                (
                    f"fresh={row['fresh_signals']} | recovered_sent={row['recovered_entries_sent']} | "
                    f"pending_outcomes={row['pending_outcomes']} | dispatch_errors={row['dispatch_errors']}\n"
                    f"state={('active' if str(row['quiet_reason']) in {'active', 'None', 'none', 'null'} else str(row['quiet_reason']).replace('_', ' '))}\n"
                    f"last_refresh={row['last_refresh']}\n"
                    f"last_post={row['last_discord']}"
                ),
                inline=False,
            )
            for row in rows
    )
    return CommandCard(
        title="Board Status",
        description=f"Live health snapshot at {timestamp}. Quiet boards can still be healthy.",
        fields=fields,
    )


def build_recent_card(config_path: str | Path, query: str | None = None) -> CommandCard:
    rows = _recent_route_data(config_path, query)
    if query and not rows:
        return CommandCard(
            title="Recent Activity Not Found",
            description=f"I couldn't find a live route for `{query}`.",
            color=0xE67E22,
        )
    fields = tuple(
        CommandField(
            row["title"],
            f"{row['summary']}\n{row['detail']}",
            inline=False,
        )
        for row in rows
    )
    return CommandCard(
        title="Recent Activity",
        description="This is the latest recorded activity on each board, including outcomes where they exist.",
        fields=fields or (CommandField("Recent activity", "No activity recorded yet.", inline=False),),
    )


def build_scan_card(summaries: list[dict[str, object]], query: str | None = None) -> CommandCard:
    fields = []
    for summary in summaries:
        route_title = _strategy_title(str(summary["strategy_id"]))
        fields.append(
            CommandField(
                route_title,
                (
                    f"signals={summary['signals_found']} | fresh={summary['fresh_signals']} | "
                    f"recovered={summary['recovered_entries_found']} | outcomes={summary['outcomes_sent']}\n"
                    f"quiet_reason={summary.get('quiet_reason') or 'active'}"
                ),
                inline=False,
            )
        )
    target = f" for `{query}`" if query else ""
    return CommandCard(
        title="Scan Complete",
        description=f"Silent one-shot scan finished{target}. No live alerts were dispatched from this command.",
        fields=tuple(fields) or (CommandField("Result", "No enabled routes were scanned.", inline=False),),
    )


def _card_to_text(card: CommandCard) -> str:
    lines = [f"**{card.title}**", card.description]
    for field in card.fields:
        lines.append(f"{field.name}: {field.value}")
    return "\n".join(lines)


def build_help_text() -> str:
    return _card_to_text(build_help_card())


def build_boards_text() -> str:
    return _card_to_text(build_boards_card())


def build_strategy_text(query: str | None = None) -> str:
    return _card_to_text(build_strategy_card_response(query))


def build_status_text(config_path: str | Path, query: str | None = None) -> str:
    return _card_to_text(build_status_card(config_path, query))


def build_recent_text(config_path: str | Path, query: str | None = None) -> str:
    return _card_to_text(build_recent_card(config_path, query))


def build_ladder_text(config_path: str | Path, query: str | None = None) -> str:
    return _card_to_text(build_ladder_card(config_path, query))


def parse_command_message(content: str) -> tuple[str | None, str | None]:
    raw = content.strip()
    if not raw:
        return None, None
    lowered = raw.lower()
    prefixes = ("!", "/", ".")
    for prefix in prefixes:
        if lowered.startswith(prefix):
            raw = raw[len(prefix):].strip()
            lowered = raw.lower()
            break
    parts = raw.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else None
    aliases = {
        "commands": "help",
        "board": "boards",
        "health": "status",
    }
    command = aliases.get(command, command)
    if command in {"strategy", "help", "status", "scan", "boards", "recent", "ladder"}:
        return command, argument
    return None, None
