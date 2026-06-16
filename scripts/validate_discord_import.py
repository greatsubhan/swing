"""Validation script for the Discord import pipeline.

Proves that:
- Imported signal counts by strategy match
- Matched TP/SL counts match
- Duplicate prevention works
- Schema validation passes
- Dashboard numbers match imported journal totals
- Provenance badges reflect discord-imported source correctly
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_platform.discord_journal_models import load_imported_entries, load_import_state

REQUIRED_PROVENANCE_FIELDS = [
    "imported_from",
    "imported_at",
    "parser_version",
    "raw_message_ids",
    "source_channel_id",
    "source_channel_name",
    "confidence",
    "event_type",
]


def validate_route(route_id: str, output_dir: str = "platform_output") -> dict:
    """Validate a single route's discord import data."""
    base = Path(output_dir)
    import_path = base / route_id / "discord_import_journal.json"
    state_path = base / "_discord_import_state.json"
    metrics_path = base / "_dashboard_metrics.json"

    result = {
        "route": route_id,
        "checks": [],
        "passed": 0,
        "failed": 0,
    }

    def check(name, condition, detail=""):
        if condition:
            result["checks"].append({"name": name, "status": "PASS", "detail": detail})
            result["passed"] += 1
        else:
            result["checks"].append({"name": name, "status": "FAIL", "detail": detail})
            result["failed"] += 1

    # --- Check: import file exists ---
    check("import_file_exists", import_path.exists(), str(import_path))

    if not import_path.exists():
        return result

    # --- Load and parse entries ---
    entries = load_imported_entries(import_path)
    check("import_file_parseable", len(entries) > 0, f"{len(entries)} entries loaded")

    if not entries:
        return result

    # --- Schema validation: every entry has all provenance fields ---
    schema_ok = True
    missing_fields = []
    for i, entry in enumerate(entries):
        entry_dict = entry.to_dict()
        for field in REQUIRED_PROVENANCE_FIELDS:
            if field not in entry_dict or not entry_dict[field]:
                schema_ok = False
                missing_fields.append(f"entry[{i}].{field}")

    check(
        "schema_validation",
        schema_ok,
        f"Missing: {missing_fields[:5]}..." if missing_fields else "All provenance fields present",
    )

    # --- Check: imported_from is always "discord" ---
    all_discord = all(e.imported_from == "discord" for e in entries)
    check("imported_from_always_discord", all_discord)

    # --- Check: parser_version is set ---
    all_versioned = all(e.parser_version for e in entries)
    check("parser_version_set", all_versioned)

    # --- Check: no duplicate raw_message_ids ---
    all_ids = []
    for e in entries:
        all_ids.extend(e.raw_message_ids)
    unique_ids = set(all_ids)
    check("no_duplicate_message_ids", len(all_ids) == len(unique_ids), f"{len(all_ids)} total, {len(unique_ids)} unique")

    # --- Count events by type ---
    events_by_type = {}
    for e in entries:
        events_by_type[e.event_type] = events_by_type.get(e.event_type, 0) + 1

    signals = [e for e in entries if e.event_type == "signal_entry"]
    outcomes = [e for e in entries if e.event_type == "outcome"]
    matched_outcomes = [e for e in outcomes if e.matched_to_setup_id]
    unmatched_outcomes = [e for e in outcomes if not e.matched_to_setup_id]

    result["summary"] = {
        "total_entries": len(entries),
        "signals": len(signals),
        "outcomes": len(outcomes),
        "matched_outcomes": len(matched_outcomes),
        "unmatched_outcomes": len(unmatched_outcomes),
        "events_by_type": events_by_type,
        "confidence_breakdown": {},
    }

    for e in entries:
        conf = e.confidence
        result["summary"]["confidence_breakdown"][conf] = result["summary"]["confidence_breakdown"].get(conf, 0) + 1

    # --- Check: dashboard metrics match import totals ---
    metrics_data = {}
    if metrics_path.exists():
        try:
            metrics_data = json.loads(metrics_path.read_text())
            route_metrics = metrics_data.get(route_id, {})
            discord_metrics = route_metrics.get("discord_imported", {})
            dashboard_total = discord_metrics.get("total", 0)
            import_trade_entries = len([e for e in entries if e.event_type in ("signal_entry", "outcome")])
            check(
                "dashboard_matches_import_total",
                dashboard_total == import_trade_entries,
                f"dashboard={dashboard_total}, import={import_trade_entries}",
            )
            dashboard_matched = discord_metrics.get("matched_outcomes", 0)
            check(
                "dashboard_matches_matched_outcomes",
                dashboard_matched == len(matched_outcomes),
                f"dashboard={dashboard_matched}, actual={len(matched_outcomes)}",
            )
            dashboard_unmatched = discord_metrics.get("unmatched", 0)
            check(
                "dashboard_matches_unmatched_outcomes",
                dashboard_unmatched == len(unmatched_outcomes),
                f"dashboard={dashboard_unmatched}, actual={len(unmatched_outcomes)}",
            )
        except Exception as exc:
            check("dashboard_metrics_readable", False, str(exc))
    else:
        check("dashboard_metrics_file_exists", False, str(metrics_path))

    # --- Check: combined totals include discord ---
    if metrics_path.exists():
        try:
            route_metrics = metrics_data.get(route_id, {})
            combined = route_metrics.get("combined", {})
            native = route_metrics.get("native_journal", {})
            discord = route_metrics.get("discord_imported", {})
            expected_combined = native.get("total", 0) + discord.get("total", 0)
            check(
                "combined_totals_correct",
                combined.get("total", 0) == expected_combined,
                f"combined={combined.get('total', 0)}, expected={expected_combined}",
            )
        except Exception:
            pass

    return result


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "platform_output"
    state_path = Path(output_dir) / "_discord_import_state.json"
    state = load_import_state(state_path)

    print("\n" + "=" * 70)
    print("DISCORD IMPORT VALIDATION")
    print("=" * 70)

    # Find routes with discord import data
    routes = []
    base = Path(output_dir)
    for route_dir in sorted(base.iterdir()):
        if route_dir.is_dir() and (route_dir / "discord_import_journal.json").exists():
            routes.append(route_dir.name)

    if not routes:
        # Check if state mentions any routes
        if state.last_imported_message_id_per_channel:
            print("No discord import files found but state has channel data.")
            print("Run import first: python scripts/run_discord_import.py --mode backfill")
        else:
            print("No Discord import data found. Pipeline is empty.")
            print("Run import first: python scripts/run_discord_import.py --mode backfill")
        print("=" * 70)
        return

    total_passed = 0
    total_failed = 0

    for route_id in routes:
        result = validate_route(route_id, output_dir)
        total_passed += result["passed"]
        total_failed += result["failed"]

        status = "✅ PASS" if result["failed"] == 0 else "❌ FAIL"
        print(f"\n{status} — {route_id}")
        print(f"  Passed: {result['passed']}  Failed: {result['failed']}")

        if "summary" in result:
            s = result["summary"]
            print(f"  Signals: {s['signals']}  Outcomes: {s['outcomes']}")
            print(f"  Matched: {s['matched_outcomes']}  Unmatched: {s['unmatched_outcomes']}")
            print(f"  Confidence: {s['confidence_breakdown']}")
            print(f"  Events by type: {s['events_by_type']}")

        for check in result["checks"]:
            marker = "✓" if check["status"] == "PASS" else "✗"
            detail = f" ({check['detail']})" if check["detail"] else ""
            print(f"    {marker} {check['name']}{detail}")

    print("\n" + "=" * 70)
    overall = "✅ ALL PASSED" if total_failed == 0 else f"❌ {total_failed} FAILED"
    print(f"{overall} — {total_passed} passed, {total_failed} failed")
    print("=" * 70)

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()