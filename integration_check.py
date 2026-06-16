"""Integration health check — run this to diagnose OANDA, Discord, journal, and runtime status.

Produces platform_output/integrations.json as a structured report for the dashboard.

Usage: python integration_check.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Load .env first
sys.path.insert(0, str(Path(__file__).parent))
from signal_platform.env import load_dotenv

load_dotenv(Path(".env"))


def check_oanda() -> dict:
    """Test OANDA connection and classify failure mode."""
    from signal_platform.oanda_execution import OandaConfig, OandaClient

    token = os.environ.get("OANDA_API_TOKEN", "")
    account_id = os.environ.get("OANDA_ACCOUNT_ID", "")
    env = os.environ.get("OANDA_ENV", "practice")

    if not token or token in ("", "replace_me"):
        return {"status": "blocked", "reason": "OANDA_API_TOKEN missing or placeholder", "category": "missing_credential"}
    if not account_id or account_id in ("", "replace_me"):
        return {"status": "blocked", "reason": "OANDA_ACCOUNT_ID missing or placeholder", "category": "missing_credential"}

    config = OandaConfig(account_id=account_id, api_token=token, environment=env)
    client = OandaClient(config)
    result = client.test_connection()

    if result.get("ok"):
        return {
            "status": "healthy",
            "reason": f"Connected to account {result.get('account_id')}, balance={result.get('balance')}",
            "account_id": result.get("account_id"),
            "balance": result.get("balance"),
            "nav": result.get("nav"),
            "currency": result.get("currency"),
            "category": "connected",
        }

    error = result.get("error", "")
    if "401" in error or "Unauthorized" in error:
        return {"status": "broken", "reason": error, "category": "auth_failure",
                "diagnosis": "API token is expired, revoked, or doesn't match this account. Generate a new token at oanda.com/account/token",
                "token_prefix": token[:8] + "..." if len(token) > 8 else "(empty)",
                "account_id": account_id, "environment": env}
    if "Missing" in error:
        return {"status": "blocked", "reason": error, "category": "missing_credential"}
    if "Connection failed" in error:
        return {"status": "broken", "reason": error, "category": "network_failure"}

    return {"status": "broken", "reason": error, "category": "unknown"}


def check_discord_webhook(env_var_name: str, label: str) -> dict:
    """Validate a Discord webhook URL."""
    url = os.environ.get(env_var_name, "")
    if not url or url == "replace_me":
        return {"status": "missing", "label": label, "url": "(not set)", "category": "env_var_missing"}
    if not url.startswith("https://discord.com/api/webhooks/"):
        return {"status": "invalid", "label": label, "url": url[:40] + "...", "category": "bad_url_format"}

    # Test with a lightweight request
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "integration-check/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 400:
                return {"status": "healthy", "label": label, "url": url[:60] + "...", "category": "connected"}
            return {"status": "broken", "label": label, "url": url[:60] + "...", "category": "http_error", "reason": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "broken", "label": label, "url": url[:60] + "...", "category": "webhook_not_found", "reason": "404 — webhook deleted or invalid"}
        if exc.code == 401 or exc.code == 403:
            return {"status": "broken", "label": label, "url": url[:60] + "...", "category": "auth_error", "reason": f"HTTP {exc.code}"}
        return {"status": "unknown", "label": label, "url": url[:60] + "...", "category": "http_error", "reason": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"status": "unknown", "label": label, "url": url[:60] + "...", "category": "network_error", "reason": str(exc)[:200]}


def check_journals() -> dict:
    """Check completeness of journal files for all routes."""
    routes = {
        "strategy_four": {"file": "platform_output/strategy_four/signal_journal.json", "expected": True},
        "little_rzy": {"file": "platform_output/little_rzy/signal_journal.json", "expected": True},
        "strategy_two": {"file": "platform_output/strategy_two/signal_journal.json", "expected": True},
        "strategy_five": {"file": "platform_output/strategy_five/signal_journal.json", "expected": False},
        "little_rzy_1h": {"file": "platform_output/little_rzy_1h/signal_journal.json", "expected": False},
    }
    result = {}
    for route, info in routes.items():
        p = Path(info["file"])
        if not p.exists():
            result[route] = {"exists": False, "entries": 0, "valid_json": False,
                             "status": "missing" if info["expected"] else "expected_missing"}
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            count = len(data) if isinstance(data, list) else 0
            result[route] = {"exists": True, "entries": count, "valid_json": True, "status": "ok"}
        except Exception as exc:
            result[route] = {"exists": True, "entries": 0, "valid_json": False, "status": "corrupt", "error": str(exc)[:200]}
    return result


def check_health_snapshots() -> dict:
    """Read all health snapshots for integration status."""
    routes = ["strategy_four", "little_rzy", "strategy_two", "strategy_five"]
    result = {}
    for route in routes:
        p = Path(f"platform_output/{route}/health_snapshot.json")
        if not p.exists():
            result[route] = {"exists": False, "status": "missing"}
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            errors = data.get("dispatch_errors", [])
            error_str = errors[0] if errors else None
            result[route] = {
                "exists": True,
                "status": "error" if data.get("dispatch_error_count", 0) > 0 else "ok",
                "last_cycle": data.get("last_cycle_finished_utc"),
                "signals_found": data.get("signals_found", 0),
                "error": error_str or data.get("error"),
                "quiet_reason": data.get("quiet_reason"),
            }
        except Exception as exc:
            result[route] = {"exists": True, "status": "corrupt", "error": str(exc)[:200]}
    return result


def main():
    """Run all checks and write integrations.json."""
    print("=" * 60)
    print("  Integration Health Check")
    print("=" * 60)

    report = {"checked_at_utc": "", "overall": "unknown", "subsystems": {}}

    # OANDA
    oanda = check_oanda()
    report["subsystems"]["oanda"] = oanda
    oanda_icon = "✅" if oanda["status"] == "healthy" else "❌" if oanda["status"] == "broken" else "⚠️"
    print(f"\n{oanda_icon} OANDA: {oanda['status']} — {oanda['reason']}")

    # Discord webhooks
    webhooks = {
        "discord_little_rzy": ("DISCORD_WEBHOOK_URL_LITTLE_RZY", "Little Rzy"),
        "discord_strategy_two": ("DISCORD_WEBHOOK_URL_STRATEGY_TWO", "Strategy Two"),
        "discord_cwt": ("DISCORD_WEBHOOK_URL_CWT", "CWT (Strategy Four)"),
        "discord_sip": ("DISCORD_WEBHOOK_URL_SIP", "Secular Bull SIP"),
        "discord_little_rzy_1h": ("DISCORD_WEBHOOK_URL_LITTLE_RZY_1H", "Little Rzy 1H (disabled)"),
        "discord_base": ("DISCORD_WEBHOOK_URL", "Base Discord Webhook"),
    }
    discord_results = {}
    for key, (env_var, label) in webhooks.items():
        wh = check_discord_webhook(env_var, label)
        discord_results[key] = wh
        wh_icon = "✅" if wh["status"] == "healthy" else "❌" if wh["status"] in ("broken", "missing") else "❓"
        print(f"  {wh_icon} {label}: {wh['status']} — {wh.get('reason', wh['category'])}")
    report["subsystems"]["discord"] = discord_results

    # Journals
    journals = check_journals()
    report["subsystems"]["journals"] = journals
    print(f"\n📓 Journals:")
    for route, info in journals.items():
        j_icon = "✅" if info["status"] == "ok" else "❌" if info["status"] in ("missing", "corrupt") else "⚠️"
        print(f"  {j_icon} {route}: {info['status']} ({info['entries']} entries)")

    # Health snapshots
    snapshots = check_health_snapshots()
    report["subsystems"]["health_snapshots"] = snapshots
    print(f"\n💓 Health Snapshots:")
    for route, info in snapshots.items():
        s_icon = "✅" if info.get("status") == "ok" else "❌" if info.get("status") == "error" else "⚠️"
        print(f"  {s_icon} {route}: {info.get('status', 'missing')} — {info.get('error') or info.get('last_cycle', 'no data')}")

    # Overall status
    statuses = [oanda["status"]]
    statuses.extend(wh["status"] for wh in discord_results.values())
    if "broken" in statuses:
        report["overall"] = "degraded"
    elif "missing" in statuses or "unknown" in statuses:
        report["overall"] = "partial"
    else:
        report["overall"] = "healthy"

    print(f"\n{'=' * 60}")
    print(f"  Overall: {report['overall'].upper()}")
    print(f"{'=' * 60}")

    # Action items
    actions = []
    if oanda["category"] == "auth_failure":
        actions.append("OANDA: Generate new API token at oanda.com/account/token and update OANDA_API_TOKEN in .env")
    if oanda["category"] == "missing_credential":
        actions.append("OANDA: Fill in OANDA_API_TOKEN and OANDA_ACCOUNT_ID in .env")
    missing_webhooks = [k for k, v in discord_results.items() if v["status"] == "missing" and "disabled" not in k]
    if missing_webhooks:
        actions.append(f"Discord: Set missing webhook env vars: {', '.join(missing_webhooks)}")
    broken_webhooks = [k for k, v in discord_results.items() if v["status"] == "broken"]
    if broken_webhooks:
        actions.append(f"Discord: Fix broken webhooks: {', '.join(broken_webhooks)}")

    report["action_items"] = actions
    if actions:
        print("\n📋 Action Items:")
        for a in actions:
            print(f"  • {a}")

    # Write report
    from datetime import datetime, timezone
    report["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    output_path = Path("platform_output/integrations.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n✅ Report written to {output_path}")

    return 0 if report["overall"] == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())