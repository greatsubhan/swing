"""Parse Discord message embeds into DiscordImportedEntry records.

Understands the embed formats produced by dispatchers.py:
- Signal entries: discord_payload()
- Outcomes: outcome_payload()
- Reports: report_payload()
- Plain text messages
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .discord_journal_models import DiscordImportedEntry, RawMessageArchive

# --- Known strategy name → strategy_id mapping ---
STRATEGY_NAME_MAP: dict[str, str] = {
    "Little Rzy": "little_rzy",
    "Measured Drift": "little_rzy",
    "Little Rzy 1H": "little_rzy_1h",
    "Measured Drift (1H)": "little_rzy_1h",
    "Trend Current": "strategy_two",
    "CWT": "strategy_four",
    "Cambist With Trend": "strategy_four",
    "Secular Bull SIP": "strategy_five",
    "Secular Bull": "strategy_five",
}

# Reverse map: strategy_id → display name
STRATEGY_ID_TO_NAME: dict[str, str] = {
    "little_rzy": "Little Rzy",
    "little_rzy_1h": "Little Rzy 1H",
    "strategy_two": "Trend Current",
    "strategy_four": "CWT",
    "strategy_five": "Secular Bull SIP",
}

# Strategy-level matching windows (hours) — Revision 4
# These are used when setup_id is not available in outcome messages
MATCHING_WINDOW_HOURS: dict[str, float] = {
    "strategy_four": 2.0,       # M5 fast mean-reversion
    "little_rzy": 24.0,         # H4 day-trade holds
    "little_rzy_1h": 24.0,      # H1 day-trade holds
    "strategy_two": 48.0,       # H4 swing holds
    "strategy_five": 96.0,      # D multi-day holds
}
DEFAULT_MATCHING_WINDOW_HOURS = 48.0

# Outcome keywords from dispatchers.py outcome_payload
_OUTCOME_KEYWORDS = {
    "tp_hit": ["TP hit", "TP Hit", "tp_hit", "tp hit", "TP", "take profit hit"],
    "sl_hit": ["SL hit", "SL Hit", "sl_hit", "sl hit", "SL", "stop loss hit", "stopped out"],
    "break_even": ["Break-even", "breakeven", "break_even", "break even", "BE hit", "BE"],
    "partial": ["partial", "Partial", "partial close", "Partially closed"],
    "cancelled": ["cancelled", "canceled", "cancel", "Cancel"],
}

# Signal entry indicators
_ENTRY_SIGNAL_EMOJIS = {"📈", "📉", "📍"}
_ENTRY_EVENT_KEYWORDS = ["NEW SIGNAL", "REINFORCEMENT", "ADD", "MOVE STOP", "BASKET EXIT", "COOLDOWN", "SETUP"]

# Report keywords
_REPORT_KEYWORDS = ["Weekly Review", "Weekly Performance", "Monthly Review", "Monthly Performance", "Weekly Report", "Monthly Report"]
_ML_PERF_KEYWORDS = ["Prediction Performance", "ML Performance", "prediction accuracy", "ML Report"]


def _detect_event_type(embed_title: str | None, embed_description: str | None, content: str) -> str:
    """Classify the event type of a Discord message based on embed content.

    Returns one of: signal_entry, outcome, weekly_report, monthly_report,
    ml_performance, manual_comment, system_notification, unknown.
    """
    title = (embed_title or "").lower()
    desc = (embed_description or "").lower()
    text = (content or "").lower()
    combined = f"{title} {desc} {text}"

    # Check for outcome messages
    for outcome_key, keywords in _OUTCOME_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title or kw.lower() in combined:
                return "outcome"

    # Check for reports
    for kw in _REPORT_KEYWORDS:
        if kw.lower() in combined:
            if "monthly" in kw.lower():
                return "monthly_report"
            return "weekly_report"

    # Check for ML performance
    for kw in _ML_PERF_KEYWORDS:
        if kw.lower() in combined:
            return "ml_performance"

    # Check for signal entries (embed with trade fields)
    for kw in _ENTRY_EVENT_KEYWORDS:
        if kw.lower() in title:
            return "signal_entry"

    # If embed has trade-like fields (Entry, Stop, Target, Side), it's a signal
    trade_fields = ["entry", "stop", "target", "trade plan", "rr"]
    if title and any(tf in title for tf in trade_fields):
        return "signal_entry"

    # Embed with strategy name and symbol/timeframe pattern → likely signal
    strategy_pattern = re.search(r'\[.+?\]\s+\w+_\w+\s+\w+', title)
    if strategy_pattern:
        return "signal_entry"

    # Plain text without embeds → manual comment
    if not title and text:
        return "manual_comment"

    # Empty or unknown
    if not title and not desc and not text:
        return "unknown"

    return "unknown"


def _extract_strategy_id_from_footer(footer_text: str) -> str | None:
    """Extract strategy_id from embed footer text.

    Signal footer format: '{strategy_name} | {asset_class} | {strategy_id} | {setup_id}'
    Outcome footer format: '{strategy_name} | outcome | {setup_id}'
    """
    if not footer_text:
        return None
    parts = [p.strip() for p in footer_text.split("|")]
    # Signal footer has 4 parts; outcome footer has 3 parts with middle="outcome"
    if len(parts) >= 4:
        return parts[2]
    if len(parts) == 3 and parts[1].lower() == "outcome":
        # Outcome footer does not contain strategy_id
        return None
    if len(parts) >= 3:
        return parts[2]
    return None


def _extract_setup_id_from_footer(footer_text: str) -> str | None:
    """Extract setup_id from embed footer text."""
    if not footer_text:
        return None
    parts = [p.strip() for p in footer_text.split("|")]
    if len(parts) >= 4:
        # Fourth part is setup_id
        return parts[3]
    # Outcome footer: '{strategy_name} | outcome | {setup_id}'
    if len(parts) == 3 and parts[1].lower() == "outcome":
        return parts[2]
    return None


def _extract_asset_class_from_footer(footer_text: str) -> str | None:
    """Extract asset_class from embed footer text."""
    if not footer_text:
        return None
    parts = [p.strip() for p in footer_text.split("|")]
    if len(parts) >= 3:
        return parts[1]
    return None


def _extract_strategy_from_footer(footer_text: str) -> str | None:
    """Extract strategy name from embed footer text."""
    if not footer_text:
        return None
    parts = [p.strip() for p in footer_text.split("|")]
    if len(parts) >= 3:
        return parts[0]
    return None


def _parse_field_value(text: str, prefix: str) -> str | None:
    """Extract a value from a Discord field like '⚡ 1.0850'."""
    text = text.strip()
    if text.startswith(prefix):
        value = text[len(prefix):].strip()
        # Remove backtick wrapping
        value = value.strip("`").strip()
        return value if value and value != "n/a" else None
    return None


def _parse_inline_field(fields: list[dict], name_pattern: str) -> dict[str, str] | None:
    """Find a field by name pattern and parse its value into key-value pairs."""
    for field in fields:
        fname = field.get("name", "").lower()
        if name_pattern.lower() in fname:
            value = field.get("value", "")
            result = {}
            for line in value.split("\n"):
                line = line.strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().strip("`").strip()
                    v = v.strip().strip("`").strip()
                    if v and v != "n/a":
                        result[k] = v
                elif "`" in line:
                    parts = [p.strip("`").strip() for p in line.split() if p.strip("`").strip()]
                    for p in parts:
                        if p and p != "n/a":
                            result[p.split()[0] if p else "value"] = p
            return result if result else None
    return None


def _parse_signal_from_embed(
    embed: dict[str, Any],
    message_timestamp: str,
    channel_id: str,
    channel_name: str,
    message_id: str,
    message_content: str,
    reference: dict[str, Any] | None,
) -> DiscordImportedEntry | None:
    """Parse a signal entry embed into a DiscordImportedEntry."""
    title = embed.get("title", "")
    description = embed.get("description", "")
    fields = embed.get("fields", [])
    footer_data = embed.get("footer", {})
    footer_text = footer_data.get("text", "") if isinstance(footer_data, dict) else ""
    timestamp = embed.get("timestamp", message_timestamp)

    strategy_id = _extract_strategy_id_from_footer(footer_text)
    setup_id = _extract_setup_id_from_footer(footer_text)
    asset_class = _extract_asset_class_from_footer(footer_text)
    strategy_name = _extract_strategy_from_footer(footer_text)

    # Extract symbol and timeframe from title
    symbol = None
    timeframe = None
    direction = None

    # Title format: "📈 [CWT] EUR_USD H4 📉 SHORT NEW SIGNAL"
    # or: "📈 [CWT] EUR_USD H5M SHORT NEW SIGNAL"
    title_match = re.search(r'\[.+?\]\s+(\w+)\s+(\w+)', title)
    if title_match:
        symbol = title_match.group(1)
        timeframe = title_match.group(2)

    # Extract direction from title first (most reliable), then content
    title_upper = title.upper()
    content_upper = f"{title} {message_content}".upper()

    # Check title first for explicit SHORT/LONG words
    if "SHORT" in title_upper or "📉" in title or "LH/LL" in title_upper:
        direction = "short"
    elif "LONG" in title_upper or "📈" in title or "HH/HL" in title_upper:
        direction = "long"
    # Fall back to content text
    elif "SHORT" in content_upper or "📉" in message_content:
        direction = "short"
    elif "LONG" in content_upper or "📈" in message_content:
        direction = "long"
    elif "BUY" in content_upper:
        direction = "long"
    elif "SELL" in content_upper:
        direction = "short"

    # Extract trade parameters from fields
    entry = None
    stop_loss = None
    take_profit = []
    risk_reward = None

    for field in fields:
        fname = field.get("name", "").lower()
        fvalue = field.get("value", "").strip()

        if "trade plan" in fname or "trade" in fname or "setup" in fname:
            # Parse entry/stop/target from this field
            for line in fvalue.split("\n"):
                line_clean = line.strip().strip("`").strip()
                if "Entry" in line or "entry" in line:
                    val = _parse_field_value(line_clean, "⚡") or _parse_field_value(line_clean, "Entry")
                    if val:
                        try:
                            entry = float(val.replace(",", ""))
                        except ValueError:
                            pass
                elif "Stop" in line or "stop" in line:
                    val = _parse_field_value(line_clean, "🛑") or _parse_field_value(line_clean, "Stop")
                    if val:
                        try:
                            stop_loss = float(val.replace(",", ""))
                        except ValueError:
                            pass
                elif "Target" in line or "target" in line:
                    val = _parse_field_value(line_clean, "🎯") or _parse_field_value(line_clean, "Target")
                    if val:
                        try:
                            take_profit.append(float(val.replace(",", "")))
                        except ValueError:
                            pass

        if "rr" in fname or "risk" in fname:
            rr_match = re.search(r'(\d+\.?\d*)\s*R', fvalue)
            if rr_match:
                try:
                    risk_reward = float(rr_match.group(1))
                except ValueError:
                    pass

        # Also check for inline fields with "⚡ Entry `1.0850`" format
        if not entry:
            val = _parse_field_value(fvalue, "⚡")
            if val:
                try:
                    entry = float(val.replace(",", ""))
                except ValueError:
                    pass
        if not stop_loss:
            val = _parse_field_value(fvalue, "🛑")
            if val:
                try:
                    stop_loss = float(val.replace(",", ""))
                except ValueError:
                    pass
        if not take_profit:
            val = _parse_field_value(fvalue, "🎯")
            if val:
                try:
                    take_profit.append(float(val.replace(",", "")))
                except ValueError:
                    pass
        if not risk_reward:
            val = _parse_field_value(fvalue, "📏")
            if val:
                rr_match = re.search(r'(\d+\.?\d*)', val)
                if rr_match:
                    try:
                        risk_reward = float(rr_match.group(1))
                    except ValueError:
                        pass

    # Resolve strategy_id from name if not found in footer
    if not strategy_id and strategy_name:
        strategy_id = STRATEGY_NAME_MAP.get(strategy_name)

    return DiscordImportedEntry(
        imported_from="discord",
        parser_version="1.0",
        raw_message_ids=[message_id],
        source_channel_id=channel_id,
        source_channel_name=channel_name,
        confidence="exact_match" if setup_id else "medium",
        event_type="signal_entry",
        strategy_id=strategy_id,
        route_id=strategy_id,
        symbol=symbol,
        timeframe=timeframe,
        setup_id=setup_id,
        direction=direction,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit if take_profit else [],
        risk_reward=risk_reward,
        asset_class=asset_class,
        signal_timestamp=timestamp,
        result_status="open",
        matched_to_setup_id=setup_id,
        matching_method="setup_id_footer" if setup_id else None,
        raw_content=message_content,
        raw_embed_title=title,
        raw_footer=footer_text,
    )


def _parse_outcome_from_embed(
    embed: dict[str, Any],
    message_timestamp: str,
    channel_id: str,
    channel_name: str,
    message_id: str,
    message_content: str,
    reference: dict[str, Any] | None,
) -> DiscordImportedEntry | None:
    """Parse an outcome embed into a DiscordImportedEntry."""
    title = embed.get("title", "")
    description = embed.get("description", "")
    fields = embed.get("fields", [])
    footer_data = embed.get("footer", {})
    footer_text = footer_data.get("text", "") if isinstance(footer_data, dict) else ""
    timestamp = embed.get("timestamp", message_timestamp)

    strategy_id = _extract_strategy_id_from_footer(footer_text)
    setup_id = _extract_setup_id_from_footer(footer_text)
    strategy_name = _extract_strategy_from_footer(footer_text)

    # Determine outcome from title
    result_status = "unknown"
    for outcome_key, keywords in _OUTCOME_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title.lower() or kw.lower() in description.lower():
                if outcome_key == "tp_hit":
                    result_status = "tp"
                elif outcome_key == "sl_hit":
                    result_status = "sl"
                elif outcome_key == "break_even":
                    result_status = "sl"  # BE treated as closed neutral
                    result_status = "unknown"  # keep as unknown since no specific status
                else:
                    result_status = outcome_key
                break
        if result_status != "unknown":
            break

    # Extract symbol and timeframe from title
    symbol = None
    timeframe = None
    direction = None

    # Title format: "✅ EUR_USD H4 TP hit"
    title_parts = title.split()
    for i, part in enumerate(title_parts):
        clean = part.strip("✅🛑🟡📍")
        if "_" in clean and len(clean) > 3:
            symbol = clean
        elif re.match(r'^[HMHDW]\d*$', clean, re.IGNORECASE) or clean.upper() in ("D", "W", "MN"):
            timeframe = clean.upper()

    # Parse "Result" field
    for field in fields:
        fname = field.get("name", "").lower()
        fvalue = field.get("value", "").strip()

        if "result" in fname:
            for line in fvalue.split("\n"):
                line_clean = line.strip().strip("`").strip()
                if line_clean.lower().startswith("side:"):
                    side_str = line_clean.split(":", 1)[1].strip().strip("`").strip()
                    if side_str.upper() == "LONG":
                        direction = "long"
                    elif side_str.upper() == "SHORT":
                        direction = "short"
                elif line_clean.lower().startswith("outcome:"):
                    outcome_str = line_clean.split(":", 1)[1].strip().strip("`").strip()
                    if "tp" in outcome_str.lower():
                        result_status = "tp"
                    elif "sl" in outcome_str.lower():
                        result_status = "sl"
                    elif "break" in outcome_str.lower() or "be" in outcome_str.lower():
                        result_status = "sl"
                elif line_clean.lower().startswith("realized:"):
                    rr_str = line_clean.split(":", 1)[1].strip().strip("`").strip()
                    rr_match = re.search(r'([-\d.]+)\s*R', rr_str)
                    if rr_match:
                        try:
                            # For TP, preserve positive R; for SL, use -1.0
                            r_val = float(rr_match.group(1))
                            if result_status == "sl" and r_val > 0:
                                r_val = -1.0
                            if result_status == "tp" and r_val < 0:
                                r_val = 1.0
                        except ValueError:
                            pass

        if "exit" in fname or "price" in fname:
            for line in fvalue.split("\n"):
                line_clean = line.strip().strip("`").strip()
                if "exit price" in line_clean.lower() or "price" in line_clean.lower():
                    price_str = line_clean.split(":", 1)[-1].strip().strip("`").strip()
                    # Don't parse — leave as is

    # Resolve strategy_id
    if not strategy_id and strategy_name:
        strategy_id = STRATEGY_NAME_MAP.get(strategy_name)

    return DiscordImportedEntry(
        imported_from="discord",
        parser_version="1.0",
        raw_message_ids=[message_id],
        source_channel_id=channel_id,
        source_channel_name=channel_name,
        confidence="exact_match" if setup_id else "high" if symbol else "medium",
        event_type="outcome",
        strategy_id=strategy_id,
        route_id=strategy_id,
        symbol=symbol,
        timeframe=timeframe,
        setup_id=setup_id,
        direction=direction,
        result_status=result_status,
        result_timestamp=timestamp,
        matched_to_setup_id=setup_id,
        matching_method="setup_id_footer" if setup_id else None,
        raw_content=message_content,
        raw_embed_title=title,
        raw_footer=footer_text,
    )


def _parse_report_embed(
    embed: dict[str, Any],
    message_timestamp: str,
    channel_id: str,
    channel_name: str,
    message_id: str,
    message_content: str,
    event_type: str,
) -> DiscordImportedEntry | None:
    """Parse a report embed into a DiscordImportedEntry (event_type only, no trade data)."""
    title = embed.get("title", "")
    footer_data = embed.get("footer", {})
    footer_text = footer_data.get("text", "") if isinstance(footer_data, dict) else ""
    timestamp = embed.get("timestamp", message_timestamp)

    strategy_id = _extract_strategy_id_from_footer(footer_text)
    strategy_name = _extract_strategy_from_footer(footer_text)

    if not strategy_id and strategy_name:
        strategy_id = STRATEGY_NAME_MAP.get(strategy_name)

    return DiscordImportedEntry(
        imported_from="discord",
        parser_version="1.0",
        raw_message_ids=[message_id],
        source_channel_id=channel_id,
        source_channel_name=channel_name,
        confidence="unknown",
        event_type=event_type,
        strategy_id=strategy_id,
        route_id=strategy_id,
        signal_timestamp=timestamp,
        result_status="unknown",
        raw_content=message_content,
        raw_embed_title=title,
        raw_footer=footer_text,
    )


def parse_discord_message(
    message: dict[str, Any],
    channel_id: str,
    channel_name: str,
) -> tuple[DiscordImportedEntry | None, RawMessageArchive]:
    """Parse a single Discord message dict into a normalized entry and raw archive record.

    Args:
        message: Discord API message dict (from discord.py Message.to_dict())
        channel_id: Channel ID string
        channel_name: Channel name string

    Returns:
        Tuple of (DiscordImportedEntry | None, RawMessageArchive)
    """
    message_id = str(message.get("id", ""))
    content = message.get("content", "")
    embeds = message.get("embeds", [])
    timestamp = message.get("timestamp", "")
    attachments = [
        a.get("url", "") for a in message.get("attachments", []) if isinstance(a, dict)
    ]
    reactions = message.get("reactions", [])
    reference = message.get("message_reference") or message.get("messageReference")

    # Build raw archive record
    archive = RawMessageArchive(
        raw_message_id=message_id,
        channel_id=channel_id,
        channel_name=channel_name,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        message_timestamp=timestamp,
        raw_content=content,
        raw_embeds=embeds,
        raw_attachments=attachments,
        raw_reactions=[r for r in reactions if isinstance(r, dict)],
        raw_reference=reference,
    )

    # If no embeds, classify as manual comment
    if not embeds:
        entry = DiscordImportedEntry(
            imported_from="discord",
            parser_version="1.0",
            raw_message_ids=[message_id],
            source_channel_id=channel_id,
            source_channel_name=channel_name,
            confidence="unknown",
            event_type="manual_comment",
            signal_timestamp=timestamp,
            result_status="unknown",
            raw_content=content,
        )
        return entry, archive

    # Parse the first (primary) embed
    primary_embed = embeds[0] if embeds else {}
    embed_title = primary_embed.get("title", "")
    embed_description = primary_embed.get("description", "")

    event_type = _detect_event_type(embed_title, embed_description, content)

    # Route to appropriate parser
    if event_type == "signal_entry":
        entry = _parse_signal_from_embed(
            primary_embed, timestamp, channel_id, channel_name,
            message_id, content, reference,
        )
        return entry, archive

    if event_type == "outcome":
        entry = _parse_outcome_from_embed(
            primary_embed, timestamp, channel_id, channel_name,
            message_id, content, reference,
        )
        return entry, archive

    if event_type in ("weekly_report", "monthly_report", "ml_performance"):
        entry = _parse_report_embed(
            primary_embed, timestamp, channel_id, channel_name,
            message_id, content, event_type,
        )
        return entry, archive

    # Unknown or system notification
    entry = DiscordImportedEntry(
        imported_from="discord",
        parser_version="1.0",
        raw_message_ids=[message_id],
        source_channel_id=channel_id,
        source_channel_name=channel_name,
        confidence="unknown",
        event_type=event_type,
        signal_timestamp=timestamp,
        result_status="unknown",
        raw_content=content,
        raw_embed_title=embed_title,
        raw_footer=(primary_embed.get("footer", {}) or {}).get("text", ""),
    )
    return entry, archive


def parse_discord_messages(
    messages: list[dict[str, Any]],
    channel_id: str,
    channel_name: str,
) -> list[tuple[DiscordImportedEntry | None, RawMessageArchive]]:
    """Parse multiple Discord messages."""
    results = []
    for msg in messages:
        entry, archive = parse_discord_message(msg, channel_id, channel_name)
        results.append((entry, archive))
    return results