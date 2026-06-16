"""Seed integrations.json based on the integration audit findings."""
import json
from pathlib import Path
from datetime import datetime, timezone

report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "overall": "degraded",
    "subsystems": {
        "oanda": {
            "status": "broken",
            "reason": "HTTP Error 401: Unauthorized",
            "category": "auth_failure",
            "diagnosis": "API token is expired, revoked, or doesn't match this account. Generate a new token at oanda.com/account/token",
            "account_id": "101-011-30754943-003",
            "environment": "practice"
        },
        "discord": {
            "discord_little_rzy": {
                "status": "healthy",
                "label": "Little Rzy",
                "category": "configured"
            },
            "discord_strategy_two": {
                "status": "healthy",
                "label": "Strategy Two",
                "category": "configured"
            },
            "discord_cwt": {
                "status": "healthy",
                "label": "CWT (Strategy Four)",
                "category": "configured"
            },
            "discord_sip": {
                "status": "healthy",
                "label": "Secular Bull SIP",
                "category": "configured"
            },
            "discord_little_rzy_1h": {
                "status": "missing",
                "label": "Little Rzy 1H (disabled)",
                "category": "route_disabled"
            },
            "discord_base": {
                "status": "missing",
                "label": "Base Discord Webhook",
                "category": "env_var_missing"
            }
        },
        "journals": {
            "strategy_four": {"exists": True, "entries": 1029, "valid_json": True, "status": "ok"},
            "little_rzy": {"exists": True, "entries": 2, "valid_json": True, "status": "ok"},
            "strategy_two": {"exists": True, "entries": 0, "valid_json": True, "status": "ok"},
            "strategy_five": {"exists": False, "entries": 0, "valid_json": False, "status": "missing"},
            "little_rzy_1h": {"exists": False, "entries": 0, "valid_json": False, "status": "expected_missing"}
        },
        "health_snapshots": {
            "strategy_four": {"exists": True, "status": "error", "last_cycle": "2026-06-13T09:02:11.150366+00:00", "signals_found": 0, "error": "HTTPError: HTTP Error 401: Unauthorized"},
            "little_rzy": {"exists": True, "status": "error", "last_cycle": "2026-06-13T06:56:17.724578+00:00", "signals_found": 0, "error": "HTTPError: HTTP Error 401: Unauthorized"},
            "strategy_two": {"exists": True, "status": "ok", "last_cycle": "2026-06-12T08:55:22+00:00", "signals_found": 0},
            "strategy_five": {"exists": True, "status": "ok", "last_cycle": "2026-06-12T10:55:48+00:00", "signals_found": 0}
        }
    },
    "action_items": [
        "OANDA: Generate new API token at oanda.com/account/token and update OANDA_API_TOKEN in .env",
        "Discord: Confirm webhook URLs are reachable (run python integration_check.py)",
        "strategy_five: No journal file yet (D1 low-frequency strategy — may need days to produce first signal)"
    ]
}

output_path = Path("platform_output/integrations.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, indent=2))
print(f"Wrote {output_path} ({len(json.dumps(report))} bytes)")