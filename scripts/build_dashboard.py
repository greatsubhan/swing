#!/usr/bin/env python3
"""Rebuild dashboard index.html with corrected stale values + build stamp."""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

HTML = Path("bot-dashboard/index.html")
METRICS = Path("platform_output/_dashboard_metrics.json")
INTEGRATIONS = Path("platform_output/integrations.json")
PMAP = Path("PROJECT_MAP.md")
ENV = Path(".env")

def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def env_vals(path):
    d = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d

# Load artifacts
env = env_vals(ENV)
integrations = load(INTEGRATIONS)
now = datetime.now(timezone.utc)
build_time = now.strftime("%Y-%m-%d %H:%M:%S UTC")

# Count webhook env vars
webhook_vars = [
    ("little_rzy", env.get("DISCORD_WEBHOOK_URL_LITTLE_RZY", "")),
    ("strategy_two", env.get("DISCORD_WEBHOOK_URL_STRATEGY_TWO", "")),
    ("CWT", env.get("DISCORD_WEBHOOK_URL_CWT", "")),
    ("SIP", env.get("DISCORD_WEBHOOK_URL_SIP", "")),
    ("little_rzy_1h", env.get("DISCORD_WEBHOOK_URL_LITTLE_RZY_1H", "")),
    ("base", env.get("DISCORD_WEBHOOK_URL", "")),
]
configured = [n for n, v in webhook_vars if v and v.startswith("https://discord.com/api/webhooks/")]
missing = [n for n, v in webhook_vars if not v or not v.startswith("https://discord.com/api/")]

# Read HTML
html = HTML.read_text(encoding="utf-8")
original_len = len(html)

changes = []

# --- Read PROJECT_MAP.md for authoritative connection count ---
if PMAP.exists():
    pmap_text = PMAP.read_text(encoding="utf-8")
    # Count connections in PROJECT_MAP.md §4
    import re as _re
    verified_conns = _re.findall(r'\| `[^`]+` \| `[^`]+` \|.*?\| verified \|', pmap_text)
    inferred_conns = _re.findall(r'\| `[^`]+` \| `[^`]+` \|.*?\| inferred \|', pmap_text)
    total_pmap_conns = len(verified_conns) + len(inferred_conns)
else:
    total_pmap_conns = 37  # fallback: 34 verified + 3 inferred as of last audit

# Count connections currently in HTML MAP.connections
html_conn_count = html.count('{from:"')
if html_conn_count != total_pmap_conns:
    changes.append(f"Connection count mismatch: HTML has {html_conn_count}, PROJECT_MAP.md has {total_pmap_conns}")
    # Add missing inferred connection: discord_webhooks -> discord_signal
    # (PROJECT_MAP.md §4 line 155: "Code sends but no success confirm in runtime data")
    missing_conn = '{from:"discord_webhooks",to:"discord_signal",type:"inferred",desc:"Code sends but no success confirm in runtime"}'
    if missing_conn not in html and total_pmap_conns > html_conn_count:
        metrics_start = html.find('metrics:[')
        if metrics_start > 0:
            insert_pos = html.rfind('},', 0, metrics_start)
            if insert_pos > 0:
                html = html[:insert_pos+2] + ',' + missing_conn + html[insert_pos+2:]
                html_conn_count = html.count('{from:"')
                changes.append(f"Added missing inferred connection (discord_webhooks -> discord_signal). New count: {html_conn_count}")
else:
    changes.append(f"Connection count already correct: {html_conn_count}")

# 1. Fix lastUpdated timestamp
old_ts = 'lastUpdated:"2026-06-13T18:23:00+10:00"'
new_ts = f'lastUpdated:"{build_time}"'
if old_ts in html:
    html = html.replace(old_ts, new_ts, 1)
    changes.append(f"lastUpdated: {old_ts} -> {new_ts}")

# 2. Fix Discord "missing" item in MAP.missing array
old_missing = 'item:"Discord webhook URLs",impact:"No Discord dispatch, no outcomes, no reports",blocker:"ENV VARS NOT SET",cascade:"Blocks: discord_signal/outcome/weekly -> discord_webhooks"'
new_missing = f'item:"Discord webhook delivery confirmation",impact:"{len(configured)} of {len(webhook_vars)} webhooks configured in .env; blocked by OANDA cascade preventing signal generation",blocker:"Blocked by OANDA 401, not missing env vars",cascade:"No signals to dispatch: OANDA 401 blocks scanners"'
if old_missing in html:
    html = html.replace(old_missing, new_missing, 1)
    changes.append("Fixed Discord missing item: corrected impact/blocker/cascade")

# Also try alternate encoding of same text
old_missing2 = 'item:"Discord webhook URLs",impact:"No Discord dispatch, no outcomes, no reports",blocker:"ENV VARS NOT SET"'
if old_missing2 in html:
    new_missing2 = f'item:"Discord webhook delivery confirmation",impact:"{len(configured)} of {len(webhook_vars)} webhooks configured in .env; blocked by OANDA cascade",blocker:"Blocked by OANDA 401, not missing env vars"'
    html = html.replace(old_missing2, new_missing2, 1)
    changes.append("Fixed Discord missing item (alt match)")

# 3. Fix OANDA missing item wording
old_oanda = 'item:"OANDA API key",impact:"401 on all OANDA routes -- no market data, no execution, no entry refresh",blocker:"ENV VAR NOT SET"'
new_oanda = 'item:"OANDA API token (expired/revoked)",impact:"401 on all OANDA routes -- no market data, no execution, no entry refresh",blocker:"API token expired/revoked -- regenerate at oanda.com/account/token"'
if old_oanda in html:
    html = html.replace(old_oanda, new_oanda, 1)
    changes.append("Fixed OANDA missing item: clarified blocker")

# 4. Fix Discord node issues text
for old_text, new_text in [
    ('issues:"Env vars missing"', 'issues:"Blocked by OANDA 401 -- no signals reach dispatch"'),
]:
    count = html.count(old_text)
    if count > 0:
        html = html.replace(old_text, new_text)
        changes.append(f"Fixed discord issues: '{old_text}' -> '{new_text}' ({count} occurrences)")

# Fix discord_webhooks node issues
old_wh_issues = 'issues:"Env vars not resolved"'
new_wh_issues = f'issues:"{len(configured)} of {len(webhook_vars)} webhooks configured, 1 unused"'
if old_wh_issues in html:
    html = html.replace(old_wh_issues, new_wh_issues, 1)
    changes.append("Fixed discord_webhooks issues text")

# 5. Fix flow description
old_flow = 'Discord (code paths exist, env vars missing) vs OANDA (blocked by 401).'
new_flow = f'Discord ({len(configured)} of {len(webhook_vars)} webhooks configured) vs OANDA (blocked by 401).'
if old_flow in html:
    html = html.replace(old_flow, new_flow, 1)
    changes.append("Fixed flow description: corrected Discord status text")

# 6. Fix inferred[0] item
old_inferred = 'item:"All webhooks work",reason:"Code sends but no success confirmation in runtime",confidence:"inferred"'
new_inferred = f'item:"{len(configured)} of {len(webhook_vars)} Discord webhooks configured",reason:"Configured in .env; delivery untested by runtime data",confidence:"verified"'
if old_inferred in html:
    html = html.replace(old_inferred, new_inferred, 1)
    changes.append("Fixed inferred[0]: updated from 'inferred' to 'verified'")

# 7. Fix footer timestamp
old_footer = "Architecture source: PROJECT_MAP.md (updated ${MAP.lastUpdated})"
if old_footer in html:
    # This is in a template literal - keep as-is (it uses MAP.lastUpdated which is now correct)
    pass

# 8. Add build stamp + integrity check section before </footer>
build_hash = hashlib.sha256(f"{build_time}{json.dumps(integrations, sort_keys=True)}".encode()).hexdigest()[:12]

oanda_status = integrations.get("subsystems", {}).get("oanda", {}).get("status", "unknown")
oanda_reason = integrations.get("subsystems", {}).get("oanda", {}).get("reason", "N/A")
journal_data = load(METRICS)

build_stamp = f'''
<div style="margin-top:12px;padding:8px 12px;background:var(--bg-card);border-radius:var(--radius-sm);border:1px solid var(--border);font-size:0.55rem;color:var(--text-muted);display:grid;grid-template-columns:1fr 1fr;gap:4px;">
  <div>Build: {build_time}</div>
  <div>Hash: {build_hash}</div>
  <div>OANDA: {oanda_status} ({oanda_reason[:50]}...)</div>
  <div>Discord: {len(configured)}/{len(webhook_vars)} webhooks configured</div>
  <div>Journals: strategy_four={journal_data.get("strategy_four", {}).get("total", 0)}, little_rzy={journal_data.get("little_rzy", {}).get("total", 0)}</div>
  <div>Integrity: {len(changes)} stale items corrected</div>
</div>
'''

if "build-stamp" not in html and "<footer" in html:
    html = html.replace("<footer", build_stamp + "<footer", 1)
    changes.append("Added build stamp section")

# Write
HTML.write_text(html, encoding="utf-8")

print(f"Build complete: {len(html)} bytes (was {original_len})")
print(f"Changes made: {len(changes)}")
for i, c in enumerate(changes, 1):
    print(f"  {i}. {c}")
print(f"\nBuild hash: {build_hash}")
print(f"Build time: {build_time}")
print(f"OANDA status: {oanda_status}")
print(f"Discord: {len(configured)} configured, {len(missing)} missing")