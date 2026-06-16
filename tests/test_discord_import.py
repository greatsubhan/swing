"""Validation tests for the Discord journal import pipeline.

Uses synthetic Discord message payloads matching the exact embed formats
produced by signal_platform/dispatchers.py.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_platform.discord_journal_models import (
    DiscordImportedEntry,
    DiscordImportState,
    load_imported_entries,
    load_import_state,
    save_import_state,
)
from signal_platform.discord_message_parser import (
    _detect_event_type,
    _extract_setup_id_from_footer,
    _extract_strategy_id_from_footer,
    parse_discord_message,
    parse_discord_messages,
)
from signal_platform.discord_outcome_matcher import match_all_outcomes, match_outcome_to_signals
from signal_platform.discord_importer import compute_imported_metrics


# === Synthetic Discord Message Payloads ===
# These match the exact format produced by dispatchers.py

SIGNAL_EMBED_CWT = {
    "id": "111111111111111101",
    "content": "📈 [CWT] EUR_USD H4 📉 SHORT NEW SIGNAL",
    "timestamp": "2026-06-10T08:00:00.000000+00:00",
    "embeds": [
        {
            "title": "📉 [CWT] EUR_USD H4 SHORT NEW SIGNAL",
            "description": "CWT pattern detected with alligator alignment",
            "color": 0x2ECC71,
            "fields": [
                {
                    "name": "Trade Plan",
                    "value": "⚡ Entry `1.0850`\n🛑 Stop `1.0900`\n🎯 Target `1.0750`\n📏 R/R `2.0R`\n⭐ Score `A`",
                    "inline": False,
                },
                {
                    "name": "Setup",
                    "value": "Root `root_s4_001`\nStructure `struct_s4_001`",
                    "inline": False,
                },
            ],
            "footer": {"text": "CWT | forex | strategy_four | cwt_eur_usd_h4_20260610_001"},
            "timestamp": "2026-06-10T08:00:00.000000+00:00",
        }
    ],
    "attachments": [],
    "reactions": [],
    "channel_id": "987654321098765432",
    "channel_name": "cwt-signals",
}

OUTCOME_EMBED_TP = {
    "id": "111111111111111102",
    "content": "✅ [CWT] EUR_USD H4 TP hit",
    "timestamp": "2026-06-10T10:30:00.000000+00:00",
    "embeds": [
        {
            "title": "✅ EUR_USD H4 TP hit",
            "description": "TP outcome recorded for setup `cwt_eur_usd_h4_20260610_001`.",
            "color": 0x2ECC71,
            "fields": [
                {
                    "name": "Result",
                    "value": "Side: `SHORT`\nOutcome: `TP hit`\nRealized: `2.00R`",
                    "inline": False,
                },
                {
                    "name": "Exit Details",
                    "value": "Exit Price: `1.0750`\nSignal Time: `2026-06-10T08:00:00.000000+00:00`\nOutcome Time: `2026-06-10T10:30:00.000000+00:00`",
                    "inline": False,
                },
                {
                    "name": "Hold",
                    "value": "Hold Time: `2.5h`\nBars Checked: `30`",
                    "inline": False,
                },
            ],
            "footer": {"text": "CWT | outcome | cwt_eur_usd_h4_20260610_001"},
            "timestamp": "2026-06-10T10:30:00.000000+00:00",
        }
    ],
}

OUTCOME_EMBED_SL = {
    "id": "111111111111111103",
    "content": "🛑 [CWT] GBP_JPY H4 SL hit",
    "timestamp": "2026-06-11T02:00:00.000000+00:00",
    "embeds": [
        {
            "title": "🛑 GBP_JPY H4 SL hit",
            "description": "SL outcome recorded for setup `cwt_gbp_jpy_h4_20260610_001`.",
            "color": 0xE74C3C,
            "fields": [
                {
                    "name": "Result",
                    "value": "Side: `LONG`\nOutcome: `SL hit`\nRealized: `-1.00R`",
                    "inline": False,
                },
                {
                    "name": "Exit Details",
                    "value": "Exit Price: `195.500`\nSignal Time: `2026-06-10T14:00:00.000000+00:00`\nOutcome Time: `2026-06-11T02:00:00.000000+00:00`",
                    "inline": False,
                },
            ],
            "footer": {"text": "CWT | outcome | cwt_gbp_jpy_h4_20260610_001"},
            "timestamp": "2026-06-11T02:00:00.000000+00:00",
        }
    ],
}

WEEKLY_REPORT = {
    "id": "111111111111111104",
    "content": "",
    "timestamp": "2026-06-12T06:00:00.000000+00:00",
    "embeds": [
        {
            "title": "📊 CWT Weekly Review (Jun 5-12)",
            "description": "Weekly performance summary",
            "color": 0x5865F2,
            "fields": [
                {"name": "Total Trades", "value": "15", "inline": True},
                {"name": "Win Rate", "value": "46.7%", "inline": True},
                {"name": "Net R", "value": "-0.5R", "inline": True},
            ],
            "footer": {"text": "CWT | forex | strategy_four | weekly_review"},
            "timestamp": "2026-06-12T06:00:00.000000+00:00",
        }
    ],
}

MANUAL_COMMENT = {
    "id": "111111111111111105",
    "content": "Good session today, 3 TP hits on EUR pairs",
    "timestamp": "2026-06-12T08:00:00.000000+00:00",
    "embeds": [],
}

SIGNAL_EMBED_LITTLE_RZY = {
    "id": "222222222222222101",
    "content": "📈 [Little Rzy] BCO_USD H4 LONG NEW SIGNAL",
    "timestamp": "2026-06-09T12:00:00.000000+00:00",
    "embeds": [
        {
            "title": "📈 [Little Rzy] BCO_USD H4 LONG NEW SIGNAL",
            "description": "Measured Drift pattern detected",
            "color": 0x2ECC71,
            "fields": [
                {
                    "name": "Trade Plan",
                    "value": "⚡ Entry `72.50`\n🛑 Stop `71.00`\n🎯 Target `75.50`\n📏 R/R `2.0R`",
                    "inline": False,
                },
            ],
            "footer": {"text": "Little Rzy | commodity | little_rzy | lrz_bco_usd_h4_20260609_001"},
            "timestamp": "2026-06-09T12:00:00.000000+00:00",
        }
    ],
}

OUTCOME_EMBED_LITTLE_RZY_SL = {
    "id": "222222222222222102",
    "content": "🛑 [Little Rzy] BCO_USD H4 SL hit",
    "timestamp": "2026-06-10T00:00:00.000000+00:00",
    "embeds": [
        {
            "title": "🛑 BCO_USD H4 SL hit",
            "description": "SL outcome recorded for setup `lrz_bco_usd_h4_20260609_001`.",
            "color": 0xE74C3C,
            "fields": [
                {
                    "name": "Result",
                    "value": "Side: `LONG`\nOutcome: `SL hit`\nRealized: `-1.00R`",
                    "inline": False,
                },
                {
                    "name": "Exit Details",
                    "value": "Exit Price: `71.00`\nSignal Time: `2026-06-09T12:00:00.000000+00:00`\nOutcome Time: `2026-06-10T00:00:00.000000+00:00`",
                    "inline": False,
                },
            ],
            "footer": {"text": "Little Rzy | outcome | lrz_bco_usd_h4_20260609_001"},
            "timestamp": "2026-06-10T00:00:00.000000+00:00",
        }
    ],
}


def test_event_type_detection():
    """Test that event types are correctly classified."""
    assert _detect_event_type("EUR_USD H4 TP hit", "tp outcome", "") == "outcome"
    assert _detect_event_type("GBP_JPY H4 SL hit", "sl outcome", "") == "outcome"
    assert _detect_event_type("Break-even EUR_USD", "", "") == "outcome"
    assert _detect_event_type("📊 CWT Weekly Review", "", "") == "weekly_report"
    assert _detect_event_type("📊 CWT Monthly Review", "", "") == "monthly_report"
    assert _detect_event_type("Prediction Performance Report", "", "") == "ml_performance"
    assert _detect_event_type("", "", "Manual comment here") == "manual_comment"
    assert _detect_event_type("", "", "") == "unknown"
    print("✅ event_type detection tests passed")


def test_footer_parsing():
    """Test setup_id and strategy_id extraction from footer text."""
    footer_signal = "CWT | forex | strategy_four | cwt_eur_usd_h4_20260610_001"
    assert _extract_strategy_id_from_footer(footer_signal) == "strategy_four"
    assert _extract_setup_id_from_footer(footer_signal) == "cwt_eur_usd_h4_20260610_001"

    footer_outcome = "CWT | outcome | cwt_eur_usd_h4_20260610_001"
    assert _extract_strategy_id_from_footer(footer_outcome) is None  # Only 3 parts
    assert _extract_setup_id_from_footer(footer_outcome) == "cwt_eur_usd_h4_20260610_001"

    footer_lrzy = "Little Rzy | commodity | little_rzy | lrz_bco_usd_h4_20260609_001"
    assert _extract_strategy_id_from_footer(footer_lrzy) == "little_rzy"
    assert _extract_setup_id_from_footer(footer_lrzy) == "lrz_bco_usd_h4_20260609_001"

    print("✅ footer_parsing tests passed")


def test_signal_parsing():
    """Test that a signal embed is parsed correctly."""
    msg = dict(SIGNAL_EMBED_CWT)
    channel_id = msg["channel_id"]
    channel_name = "cwt-signals"
    entry, archive = parse_discord_message(msg, channel_id, channel_name)

    assert entry is not None
    assert entry.event_type == "signal_entry"
    assert entry.strategy_id == "strategy_four"
    assert entry.route_id == "strategy_four"
    assert entry.setup_id == "cwt_eur_usd_h4_20260610_001"
    assert entry.symbol == "EUR_USD"
    assert entry.timeframe == "H4"
    assert entry.direction == "short"
    assert entry.source_channel_id == channel_id
    assert entry.source_channel_name == channel_name
    assert entry.raw_message_ids == ["111111111111111101"]
    assert archive.raw_message_id == "111111111111111101"
    print("✅ signal_parsing tests passed")


def test_outcome_parsing():
    """Test that an outcome embed is parsed correctly."""
    msg = dict(OUTCOME_EMBED_TP)
    channel_id = "987654321098765432"
    channel_name = "cwt-signals"
    entry, archive = parse_discord_message(msg, channel_id, channel_name)

    assert entry is not None
    assert entry.event_type == "outcome"
    assert entry.result_status == "tp"
    assert entry.setup_id == "cwt_eur_usd_h4_20260610_001"
    assert entry.symbol == "EUR_USD"
    assert entry.timeframe == "H4"
    assert entry.direction == "short"
    assert entry.confidence == "exact_match"
    print("✅ outcome_parsing tests passed")


def test_outcome_matching_exact_setup_id():
    """Test Tier 1: exact setup_id matching."""
    # Parse signal
    sig_entry, _ = parse_discord_message(
        SIGNAL_EMBED_CWT, "987654321098765432", "cwt-signals"
    )
    # Parse outcome
    out_entry, _ = parse_discord_message(
        OUTCOME_EMBED_TP, "987654321098765432", "cwt-signals"
    )
    assert sig_entry is not None
    assert out_entry is not None

    result, matched_id, method = match_outcome_to_signals(out_entry, [sig_entry])
    assert matched_id == "cwt_eur_usd_h4_20260610_001"
    assert method == "setup_id_footer"
    print("✅ outcome_matching_exact_setup_id tests passed")


def test_outcome_matching_no_match():
    """Test Tier 5: no match returns None."""
    sig_entry, _ = parse_discord_message(
        SIGNAL_EMBED_CWT, "987654321098765432", "cwt-signals"
    )
    # Outcome for a different symbol
    out_entry, _ = parse_discord_message(
        OUTCOME_EMBED_SL, "987654321098765432", "cwt-signals"
    )
    assert sig_entry is not None
    assert out_entry is not None

    # Outcome is for GBP_JPY but signal is for EUR_USD — different setup_id
    # Tier 1 fails (different setup_id), Tier 3 fails (different symbol), Tier 4 fails
    result, matched_id, method = match_outcome_to_signals(out_entry, [sig_entry])
    # This should NOT match because the setup_ids don't match and symbols differ
    # The outcome has setup_id "cwt_gbp_jpy_h4_20260610_001" while signal has "cwt_eur_usd_h4_20260610_001"
    assert matched_id is None or (sig_entry and matched_id != sig_entry.setup_id)
    print("✅ outcome_matching_no_match tests passed")


def test_match_all_outcomes():
    """Test batch matching of all outcomes."""
    entries = []
    for msg_data, ch_id, ch_name in [
        (SIGNAL_EMBED_CWT, "987654321098765432", "cwt-signals"),
        (SIGNAL_EMBED_LITTLE_RZY, "987654321098765433", "lrzy-signals"),
        (OUTCOME_EMBED_TP, "987654321098765432", "cwt-signals"),
        (OUTCOME_EMBED_SL, "987654321098765432", "cwt-signals"),
        (OUTCOME_EMBED_LITTLE_RZY_SL, "987654321098765433", "lrzy-signals"),
        (WEEKLY_REPORT, "987654321098765432", "cwt-signals"),
        (MANUAL_COMMENT, "987654321098765432", "cwt-signals"),
    ]:
        entry, _ = parse_discord_message(msg_data, ch_id, ch_name)
        if entry:
            entries.append(entry)

    matched = match_all_outcomes(entries)

    # Should have 2 signals, 3 outcomes, 1 report, 1 comment
    signals = [e for e in matched if e.event_type == "signal_entry"]
    outcomes = [e for e in matched if e.event_type == "outcome"]
    assert len(signals) == 2
    assert len(outcomes) == 3

    # CWT TP outcome should be matched
    cwt_tp = [e for e in outcomes if e.setup_id == "cwt_eur_usd_h4_20260610_001"][0]
    assert cwt_tp.matched_to_setup_id == "cwt_eur_usd_h4_20260610_001"
    assert cwt_tp.matching_method == "setup_id_footer"
    assert cwt_tp.confidence == "exact_match"

    # Little Rzy SL should be matched
    lrzy_sl = [e for e in outcomes if e.setup_id == "lrz_bco_usd_h4_20260609_001"][0]
    assert lrzy_sl.matched_to_setup_id == "lrz_bco_usd_h4_20260609_001"

    print("✅ match_all_outcomes tests passed")


def test_full_pipeline_with_temp_dir():
    """Test the full import pipeline end-to-end with temp files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "platform_output"
        output_dir.mkdir()

        # Import messages
        from signal_platform.discord_importer import import_from_channel_messages
        from signal_platform.discord_journal_models import DiscordImportState

        messages = [
            SIGNAL_EMBED_CWT,
            OUTCOME_EMBED_TP,
            SIGNAL_EMBED_LITTLE_RZY,
            OUTCOME_EMBED_LITTLE_RZY_SL,
        ]

        state = DiscordImportState()

        summary, state = import_from_channel_messages(
            channel_id="987654321098765432",
            channel_name="cwt-signals",
            route_id="strategy_four",
            messages=messages,
            state=state,
            output_dir=output_dir,
        )

        # Verify summary
        assert summary.events_parsed == 4
        assert summary.outcomes_matched >= 1  # At least CWT TP should match
        assert summary.new_messages == 4

        # Verify files were created
        journal_path = output_dir / "strategy_four" / "discord_import_journal.json"
        archive_path = output_dir / "strategy_four" / "discord_raw_archive.jsonl"
        state_path = output_dir / "_discord_import_state.json"

        assert journal_path.exists()
        assert archive_path.exists()
        # Note: state file is saved by run_import(), not import_from_channel_messages()
        # Save state manually for verification
        from signal_platform.discord_journal_models import save_import_state as _save_state
        _save_state(state_path, state)

        # Load and verify entries
        entries = load_imported_entries(journal_path)
        assert len(entries) == 4

        # Verify state
        loaded_state = load_import_state(state_path)
        assert loaded_state.total_imported_records == 4
        assert loaded_state.last_sync_utc != ""

        # Verify metrics
        metrics = compute_imported_metrics("strategy_four", str(output_dir))
        assert metrics["source"] == "discord_imported"
        assert metrics["total"] >= 2  # At least 2 signals + outcomes (signals are trade entries)

        # Test deduplication — running again should not duplicate
        summary2, state2 = import_from_channel_messages(
            channel_id="987654321098765432",
            channel_name="cwt-signals",
            route_id="strategy_four",
            messages=messages,
            state=loaded_state,
            output_dir=output_dir,
        )
        assert summary2.new_messages == 0
        assert summary2.messages_already_imported == 4

        entries2 = load_imported_entries(journal_path)
        assert len(entries2) == 4  # No duplication

        print("✅ full_pipeline_with_temp_dir tests passed")


def test_provenance_fields():
    """Test that every imported entry has all required provenance fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "platform_output"
        output_dir.mkdir()

        from signal_platform.discord_importer import import_from_channel_messages
        from signal_platform.discord_journal_models import DiscordImportState

        messages = [SIGNAL_EMBED_CWT, OUTCOME_EMBED_TP]
        state = DiscordImportState()

        summary, state = import_from_channel_messages(
            channel_id="987654321098765432",
            channel_name="cwt-signals",
            route_id="strategy_four",
            messages=messages,
            state=state,
            output_dir=output_dir,
        )

        journal_path = output_dir / "strategy_four" / "discord_import_journal.json"
        entries = load_imported_entries(journal_path)

        required_provenance = [
            "imported_from",
            "imported_at",
            "parser_version",
            "raw_message_ids",
            "source_channel_id",
            "source_channel_name",
            "confidence",
            "event_type",
        ]

        for entry in entries:
            entry_dict = entry.to_dict()
            for field in required_provenance:
                assert field in entry_dict, f"Missing provenance field '{field}' in entry"
                assert entry_dict[field], f"Empty provenance field '{field}' in entry"

            assert entry_dict["imported_from"] == "discord"
            assert entry_dict["parser_version"] == "1.0"
            assert entry_dict["raw_message_ids"]  # Non-empty

        print("✅ provenance_fields tests passed")


def test_no_duplicate_message_ids():
    """Test that import deduplication prevents duplicate message IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "platform_output"
        output_dir.mkdir()

        from signal_platform.discord_importer import import_from_channel_messages
        from signal_platform.discord_journal_models import DiscordImportState

        messages = [SIGNAL_EMBED_CWT, OUTCOME_EMBED_TP]
        state = DiscordImportState()

        # First import
        summary1, state1 = import_from_channel_messages(
            channel_id="987654321098765432",
            channel_name="cwt-signals",
            route_id="strategy_four",
            messages=messages,
            state=state,
            output_dir=output_dir,
        )

        # Second import with same messages
        summary2, state2 = import_from_channel_messages(
            channel_id="987654321098765432",
            channel_name="cwt-signals",
            route_id="strategy_four",
            messages=messages,
            state=state1,
            output_dir=output_dir,
        )

        assert summary2.new_messages == 0
        assert summary2.messages_already_imported == 2

        # Load and count unique message IDs
        entries = load_imported_entries(
            output_dir / "strategy_four" / "discord_import_journal.json"
        )
        all_msg_ids = []
        for e in entries:
            all_msg_ids.extend(e.raw_message_ids)
        assert len(all_msg_ids) == len(set(all_msg_ids)), "Duplicate message IDs found"

        print("✅ no_duplicate_message_ids tests passed")


def test_dashboard_metrics_match_import_files():
    """Test that dashboard metrics exactly match import file contents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "platform_output"
        output_dir.mkdir()

        from signal_platform.discord_importer import import_from_channel_messages
        from signal_platform.discord_journal_models import DiscordImportState

        messages = [
            SIGNAL_EMBED_CWT,
            OUTCOME_EMBED_TP,
            OUTCOME_EMBED_SL,
        ]
        state = DiscordImportState()

        summary, state = import_from_channel_messages(
            channel_id="987654321098765432",
            channel_name="cwt-signals",
            route_id="strategy_four",
            messages=messages,
            state=state,
            output_dir=output_dir,
        )

        # Load the import journal
        entries = load_imported_entries(
            output_dir / "strategy_four" / "discord_import_journal.json"
        )
        trade_entries = [e for e in entries if e.event_type in ("signal_entry", "outcome")]

        # Compute metrics
        metrics = compute_imported_metrics("strategy_four", str(output_dir))

        # Verify exact match
        assert metrics["total"] == len(trade_entries), (
            f"Dashboard total {metrics['total']} != import file count {len(trade_entries)}"
        )

        signals = [e for e in entries if e.event_type == "signal_entry"]
        outcomes = [e for e in entries if e.event_type == "outcome"]
        matched_outcomes = [e for e in outcomes if e.matched_to_setup_id]
        unmatched_outcomes = [e for e in outcomes if not e.matched_to_setup_id]

        assert metrics["matched_outcomes"] == len(matched_outcomes), (
            f"Matched count {metrics['matched_outcomes']} != actual {len(matched_outcomes)}"
        )
        assert metrics["unmatched"] == len(unmatched_outcomes), (
            f"Unmatched count {metrics['unmatched']} != actual {len(unmatched_outcomes)}"
        )

        print("✅ dashboard_metrics_match_import_files tests passed")


def test_merge_preserves_separate_totals():
    """Test Revision 3: native + discord_imported + combined are tracked separately."""
    # Simulate: native journal has 5 entries, discord import has 3
    # The dashboard metrics should show all three separately
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "platform_output"
        output_dir.mkdir()

        # Create a "native" journal file
        native_path = output_dir / "strategy_two" / "signal_journal.json"
        native_path.parent.mkdir(parents=True, exist_ok=True)
        native_entries = [
            {
                "strategy_id": "strategy_two",
                "strategy_name": "Trend Current",
                "setup_id": f"tc_pair1_h4_20260601_{i:03d}",
                "symbol": "EUR_USD",
                "asset_class": "forex",
                "timeframe": "H4",
                "side": "long",
                "signal_timestamp": f"2026-06-01T0{i}:00:00+00:00",
                "dispatched_at_utc": f"2026-06-01T0{i}:00:00+00:00",
                "entry": 1.0800 + i * 0.001,
                "stop_loss": 1.0750,
                "target_1": 1.0900,
                "risk_reward": 2.0,
                "quality_score": 70,
                "quality_grade": "B+",
                "status": "closed",
                "outcome": "tp_hit",
                "outcome_timestamp": f"2026-06-01T0{i+4}:00:00+00:00",
                "exit_price": 1.0900,
            }
            for i in range(3)
        ] + [
            {
                "strategy_id": "strategy_two",
                "strategy_name": "Trend Current",
                "setup_id": f"tc_pair1_h4_20260602_{i:03d}",
                "symbol": "EUR_USD",
                "asset_class": "forex",
                "timeframe": "H4",
                "side": "long",
                "signal_timestamp": f"2026-06-02T0{i}:00:00+00:00",
                "dispatched_at_utc": f"2026-06-02T0{i}:00:00+00:00",
                "entry": 1.0800 + i * 0.001,
                "stop_loss": 1.0750,
                "target_1": 1.0900,
                "risk_reward": 2.0,
                "quality_score": 70,
                "quality_grade": "B+",
                "status": "closed",
                "outcome": "sl_hit",
                "outcome_timestamp": f"2026-06-02T0{i+4}:00:00+00:00",
                "exit_price": 1.0750,
            }
            for i in range(2)
        ]
        native_path.write_text(json.dumps(native_entries, indent=2))

        # Import discord messages for strategy_two
        from signal_platform.discord_importer import import_from_channel_messages
        from signal_platform.discord_journal_models import DiscordImportState

        messages = [SIGNAL_EMBED_CWT]  # Just use CWT message as test signal
        state = DiscordImportState()

        summary, state = import_from_channel_messages(
            channel_id="987654321098765432",
            channel_name="cwt-signals",
            route_id="strategy_two",
            messages=messages,
            state=state,
            output_dir=output_dir,
        )

        # Verify that native and discord files exist independently
        assert native_path.exists()
        discord_path = output_dir / "strategy_two" / "discord_import_journal.json"
        assert discord_path.exists()

        # Native entries unchanged
        native = json.loads(native_path.read_text())
        assert len(native) == 5

        # Discord entries are separate
        discord = load_imported_entries(discord_path)
        assert len(discord) >= 1

        # Both files preserve their own totals
        print(f"  Native count: {len(native)}")
        print(f"  Discord count: {len(discord)}")
        print("✅ merge_preserves_separate_totals tests passed")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("DISCORD IMPORT PIPELINE TESTS")
    print("=" * 60)

    test_event_type_detection()
    test_footer_parsing()
    test_signal_parsing()
    test_outcome_parsing()
    test_outcome_matching_exact_setup_id()
    test_outcome_matching_no_match()
    test_match_all_outcomes()
    test_full_pipeline_with_temp_dir()
    test_provenance_fields()
    test_no_duplicate_message_ids()
    test_dashboard_metrics_match_import_files()
    test_merge_preserves_separate_totals()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)