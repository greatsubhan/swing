"""Import signal journal files and produce structured metrics for the dashboard.

Produces triple-view metrics per route:
- native_journal: from signal_journal.json (runtime-generated)
- discord_imported: from discord_import_journal.json (Discord-imported)
- combined: merged totals with explicit provenance
"""
import json
import sys
from pathlib import Path
from statistics import mean
from datetime import datetime, timezone


def compute_metrics(entries, source_label="native_journal"):
    """Compute dashboard metrics from JournalEntry list."""
    total = len(entries)
    closed = [e for e in entries if e.get("status") == "closed"]
    open_entries = [e for e in entries if e.get("status") == "open"]
    pending = [e for e in entries if e.get("status") not in ("closed", "open")]
    
    tp = sum(1 for e in closed if e.get("outcome") == "tp_hit")
    sl = sum(1 for e in closed if e.get("outcome") == "sl_hit")
    be = sum(1 for e in closed if e.get("outcome") in ("break_even", "breakeven"))
    
    def realized_r(e):
        if e.get("status") != "closed":
            return None
        outcome = e.get("outcome")
        rr = e.get("risk_reward")
        if outcome == "tp_hit":
            return rr if rr else 0.0
        if outcome == "sl_hit":
            return -1.0
        if outcome in ("break_even", "breakeven"):
            return 0.0
        return None
    
    r_vals_raw = [realized_r(e) for e in closed]
    r_vals: list[float] = [r for r in r_vals_raw if r is not None]
    net_r = sum(r_vals) if r_vals else 0.0
    avg_r = mean(r_vals) if r_vals else 0.0
    win_rate = tp / len(closed) if closed else 0.0
    
    wins = [r for r in r_vals if r > 0.0]
    losses = [r for r in r_vals if r < 0.0]
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")
    
    symbols = sorted(set(e.get("symbol") for e in entries if e.get("symbol")))
    sides = {}
    for e in entries:
        s = e.get("side", e.get("direction", "unknown"))
        sides[s] = sides.get(s, 0) + 1
    
    latest = max([e.get("signal_timestamp", "") for e in entries]) if entries else ""
    
    return {
        "total": total,
        "closed": len(closed),
        "open": len(open_entries),
        "pending": len(pending),
        "tp": tp,
        "sl": sl,
        "be": be,
        "win_rate": round(win_rate * 100, 1),
        "net_r": round(net_r, 2),
        "avg_r": round(avg_r, 3),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else None,
        "symbols": symbols,
        "sides": sides,
        "latest_timestamp": latest,
    }


def compute_discord_imported_metrics(route_id, output_dir):
    """Compute metrics from discord_import_journal.json for a route."""
    import_path = Path(output_dir) / route_id / "discord_import_journal.json"
    if not import_path.exists():
        return {
            "source": "discord_imported",
            "total": 0, "closed": 0, "open": 0,
            "tp": 0, "sl": 0, "be": 0,
            "win_rate": 0.0, "net_r": 0.0, "avg_r": 0.0,
            "profit_factor": None, "symbols": [],
            "unmatched": 0, "matched_outcomes": 0,
            "file": str(import_path), "last_sync_utc": "",
        }

    try:
        data = json.loads(import_path.read_text() or "[]")
    except (json.JSONDecodeError, Exception):
        return {"source": "discord_imported", "total": 0, "error": "corrupt"}

    if not isinstance(data, list):
        return {"source": "discord_imported", "total": 0, "error": "not_a_list"}

    # Filter to trade-relevant entries
    trade_entries = [e for e in data if e.get("event_type") in ("signal_entry", "outcome")]
    signals = [e for e in data if e.get("event_type") == "signal_entry"]
    outcomes = [e for e in data if e.get("event_type") == "outcome"]

    # Closed = matched outcomes with known result
    closed = [e for e in outcomes
              if e.get("matched_to_setup_id") and e.get("result_status") in ("tp", "sl")]
    open_sigs = [e for e in signals if e.get("result_status") == "open"]

    tp = sum(1 for e in closed if e.get("result_status") == "tp")
    sl = sum(1 for e in closed if e.get("result_status") == "sl")

    # Realized R
    r_vals = []
    for e in closed:
        rr = e.get("realized_r")
        if rr is not None:
            r_vals.append(rr)
        elif e.get("result_status") == "tp":
            r_vals.append(e.get("risk_reward", 1.0) or 1.0)
        elif e.get("result_status") == "sl":
            r_vals.append(-1.0)

    net_r = sum(r_vals) if r_vals else 0.0
    avg_r = mean(r_vals) if r_vals else 0.0
    win_rate = (tp / len(closed) * 100) if closed else 0.0

    wins = [r for r in r_vals if r > 0]
    losses = [r for r in r_vals if r < 0]
    pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None

    symbols = sorted(set(e.get("symbol") for e in data if e.get("symbol")))
    matched_count = sum(1 for e in outcomes if e.get("matched_to_setup_id"))
    unmatched_count = sum(1 for e in outcomes if not e.get("matched_to_setup_id"))

    # Get last sync from state file
    state_path = Path(output_dir) / "_discord_import_state.json"
    last_sync = ""
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text() or "{}")
            last_sync = state.get("last_sync_utc", "")
        except Exception:
            pass

    return {
        "source": "discord_imported",
        "total": len(trade_entries),
        "closed": len(closed),
        "open": len(open_sigs),
        "tp": tp,
        "sl": sl,
        "be": 0,
        "win_rate": round(win_rate, 1),
        "net_r": round(net_r, 2),
        "avg_r": round(avg_r, 3),
        "profit_factor": round(pf, 2) if pf is not None else None,
        "symbols": symbols,
        "unmatched": unmatched_count,
        "matched_outcomes": matched_count,
        "file": str(import_path),
        "last_sync_utc": last_sync,
    }


def merge_native_and_discord(native_metrics, discord_metrics):
    """Produce combined metrics from native and discord-imported sources.

    Combined totals are set union (deduplicated), not sum.
    """
    native_total = native_metrics.get("total", 0)
    discord_total = discord_metrics.get("total", 0)

    # For combined: use the larger of the two for total (they may overlap)
    # Since native and discord are stored in separate files with no overlap,
    # combined total = native + discord
    combined_total = native_total + discord_total

    native_closed = native_metrics.get("closed", 0)
    discord_closed = discord_metrics.get("closed", 0)
    combined_closed = native_closed + discord_closed

    native_tp = native_metrics.get("tp", 0)
    discord_tp = discord_metrics.get("tp", 0)
    combined_tp = native_tp + discord_tp

    native_sl = native_metrics.get("sl", 0)
    discord_sl = discord_metrics.get("sl", 0)
    combined_sl = native_sl + discord_sl

    native_open = native_metrics.get("open", 0)
    discord_open = discord_metrics.get("open", 0)
    combined_open = native_open + discord_open

    native_net_r = native_metrics.get("net_r", 0.0)
    discord_net_r = discord_metrics.get("net_r", 0.0)
    combined_net_r = round(native_net_r + discord_net_r, 2)

    combined_wr = round((combined_tp / combined_closed * 100) if combined_closed else 0.0, 1)

    # Profit factor: combine wins and losses
    native_avg_r = native_metrics.get("avg_r", 0.0)
    native_wins_sum = native_closed * native_avg_r * (native_metrics.get("win_rate", 0) / 100) if native_closed else 0
    # Simplified: just compute from net_r and closed counts
    combined_pf = None
    if combined_tp > 0 and combined_sl > 0:
        combined_pf = round(combined_tp / combined_sl, 2)

    # Merge symbol lists
    combined_symbols = sorted(set(
        native_metrics.get("symbols", []) + discord_metrics.get("symbols", [])
    ))

    return {
        "source": "combined",
        "total": combined_total,
        "closed": combined_closed,
        "open": combined_open,
        "tp": combined_tp,
        "sl": combined_sl,
        "be": native_metrics.get("be", 0) + discord_metrics.get("be", 0),
        "win_rate": combined_wr,
        "net_r": combined_net_r,
        "avg_r": round(combined_net_r / combined_closed, 3) if combined_closed else 0.0,
        "profit_factor": combined_pf,
        "symbols": combined_symbols,
        "native_count": native_total,
        "discord_imported_count": discord_total,
    }


def main():
    base = Path("platform_output")
    routes = {
        "strategy_four": base / "strategy_four/signal_journal.json",
        "little_rzy": base / "little_rzy/signal_journal.json",
        "strategy_two": base / "strategy_two/signal_journal.json",
        "strategy_five": base / "strategy_five/signal_journal.json",
    }
    
    output = {}
    
    for name, path in routes.items():
        route_output = {}
        
        # --- Native journal metrics ---
        if path.exists():
            try:
                entries = json.loads(path.read_text())
            except (json.JSONDecodeError, Exception):
                route_output["native_journal"] = {"error": "corrupt_journal", "total": 0, "source": "native_journal"}
                entries = []
            if not isinstance(entries, list):
                route_output["native_journal"] = {"error": "not_a_list", "total": 0, "source": "native_journal"}
                entries = []

            if "native_journal" not in route_output:
                native_m = compute_metrics(entries, "native_journal")
                native_m["source"] = "native_journal"
                native_m["journal_file"] = str(path)
                route_output["native_journal"] = native_m
        else:
            route_output["native_journal"] = {
                "total": 0, "source": "native_journal",
                "error": "file_not_found", "journal_file": str(path),
            }
        
        # --- Discord-imported metrics ---
        discord_m = compute_discord_imported_metrics(name, str(base))
        route_output["discord_imported"] = discord_m
        
        # --- Combined metrics ---
        native_m = route_output.get("native_journal", {})
        route_output["combined"] = merge_native_and_discord(
            native_m if "error" not in native_m else {"total": 0, "closed": 0, "tp": 0, "sl": 0, "be": 0, "net_r": 0.0, "win_rate": 0.0, "symbols": [], "avg_r": 0.0},
            discord_m,
        )
        
        output[name] = route_output
    
    # Read health snapshots for runtime status
    for route_name in ["strategy_four", "little_rzy", "strategy_two", "strategy_five"]:
        health_path = base / route_name / "health_snapshot.json"
        if health_path.exists():
            try:
                health = json.loads(health_path.read_text())
                output[route_name]["runtime"] = {
                    "status": "error" if health.get("dispatch_error_count", 0) > 0 else "idle",
                    "dispatch_errors": health.get("dispatch_error_count", 0),
                    "last_cycle": health.get("last_cycle_finished_utc", ""),
                    "signals_found": health.get("signals_found", 0),
                    "error_message": health.get("error") or (health.get("dispatch_errors", [])[:1] or [None])[0],
                }
            except Exception:
                pass
    
    # Read integration status if available
    integrations_path = base / "integrations.json"
    if integrations_path.exists():
        try:
            integrations = json.loads(integrations_path.read_text())
            output["_integrations"] = {
                "overall": integrations.get("overall", "unknown"),
                "checked_at_utc": integrations.get("checked_at_utc", ""),
                "oanda": integrations.get("subsystems", {}).get("oanda", {}),
                "discord": integrations.get("subsystems", {}).get("discord", {}),
                "action_items": integrations.get("action_items", []),
            }
        except Exception:
            output["_integrations"] = {"overall": "error", "checked_at_utc": "", "action_items": ["Run python integration_check.py to diagnose"]}

    # --- Discord import summary ---
    state_path = base / "_discord_import_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text() or "{}")
            output["_discord_import"] = {
                "last_sync_utc": state.get("last_sync_utc", ""),
                "total_imported_records": state.get("total_imported_records", 0),
                "total_matched_outcomes": state.get("total_matched_outcomes", 0),
                "total_unmatched_outcomes": state.get("total_unmatched_outcomes", 0),
                "channels": state.get("last_imported_message_id_per_channel", {}),
            }
        except Exception:
            pass

    # Write output
    (base / "_dashboard_metrics.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()