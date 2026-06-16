#!/usr/bin/env python3
"""Fix JS syntax error in connections and clean up build stamps."""
import re
from pathlib import Path

html_path = Path("bot-dashboard/index.html")
html = html_path.read_text(encoding="utf-8")

# 1. Fix the corrupted connections area: double comma + missing brace
# Pattern: },,{from:"discord_webhooks" ... "runtime"}{from:"oanda_order" ... 401"}
old_bad = '},,{from:"discord_webhooks",to:"discord_signal",type:"inferred",desc:"Code sends but no success confirm in runtime"}{from:"oanda_order",to:"journal_lr",type:"inferred",desc:"Code path exists but blocked by 401"}'
new_good = '},{from:"discord_webhooks",to:"discord_signal",type:"inferred",desc:"Code sends but no success confirm in runtime"},{from:"oanda_order",to:"journal_lr",type:"inferred",desc:"Code path exists but blocked by 401"}'

if old_bad in html:
    html = html.replace(old_bad, new_good, 1)
    print("1. Fixed double comma + missing brace in connections")
else:
    print("1. Connections already OK (pattern not found)")

# 2. Remove the /*37*/ comment from connections (not valid JS)
html = html.replace('connections:[/*37*/', 'connections:[', 1)
print("2. Removed /*37*/ comment from connections")

# 3. Fix OANDA missing item: em dash vs double hyphen
old_oanda = 'item:"OANDA API key",impact:"401 on all OANDA routes \u2014 no market data, no execution, no entry refresh",blocker:"ENV VAR NOT SET"'
new_oanda = 'item:"OANDA API token (expired/revoked)",impact:"401 on all OANDA routes \u2014 no market data, no execution, no entry refresh",blocker:"API token expired/revoked \u2014 regenerate at oanda.com/account/token"'

if old_oanda in html:
    html = html.replace(old_oanda, new_oanda, 1)
    print("3. Fixed OANDA missing item text (em dash)")
else:
    print("3. OANDA item already OK or not found")

# 4. Remove duplicate build stamps - keep only the last one
# Find all build stamp divs
stamp_pattern = re.compile(
    r'<div style="margin-top:12px;padding:8px 12px;background:var\(--bg-card\).*?</div>\n*</div>\n*</div>',
    re.DOTALL
)
stamps = list(stamp_pattern.finditer(html))
if len(stamps) > 1:
    # Remove all but the last stamp
    for stamp in stamps[:-1]:
        html = html[:stamp.start()] + html[stamp.end():]
    print(f"4. Removed {len(stamps)-1} duplicate build stamps, kept latest")
elif len(stamps) == 1:
    print("4. Only 1 build stamp present")
else:
    print("4. No build stamps found")

# Verify connection count
conn_count = html.count('{from:"')
print(f"\nFinal connection count: {conn_count}")

# Verify no double commas in connections area
conns_start = html.find('connections:[')
metrics_start = html.find('metrics:[')
if conns_start > 0 and metrics_start > conns_start:
    conn_section = html[conns_start:metrics_start]
    if ',,' in conn_section:
        print("WARNING: Still has double comma in connections!")
    else:
        print("No double commas in connections section ✓")

html_path.write_text(html, encoding="utf-8")
print(f"\nWrote {len(html)} bytes to {html_path}")