#!/usr/bin/env python3
"""Quick verification of dashboard HTML corrections."""
import re
from pathlib import Path

html = Path("bot-dashboard/index.html").read_text(encoding="utf-8")

# Count connections in HTML
html_conn_count = html.count('{from:"')

# Count connections in PROJECT_MAP.md
import re as _re
pmap_text = Path("PROJECT_MAP.md").read_text(encoding="utf-8")
verified_pmap = _re.findall(r'\| `[^`]+` \| `[^`]+` \|.*?\| verified \|', pmap_text)
inferred_pmap = _re.findall(r'\| `[^`]+` \| `[^`]+` \|.*?\| inferred \|', pmap_text)
total_pmap = len(verified_pmap) + len(inferred_pmap)

checks = {
    "1. lastUpdated": bool(re.search(r'lastUpdated:"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)"', html)),
    "2. Connection count (matches PROJECT_MAP.md)": html_conn_count == total_pmap,
    "3. Connection count (actual)": f"{html_conn_count} vs {total_pmap}",
    "4. NO 'ENV VARS NOT SET'": "ENV VARS NOT SET" not in html,
    "5. Has 'Blocked by OANDA 401'": "Blocked by OANDA 401" in html,
    "6. NO 'env vars missing' in flow": "env vars missing" not in html,
    "7. Build stamp present": "Build:" in html,
    "8. OANDA 'expired/revoked'": "expired/revoked" in html,
    "9. Inferred[0] verified": 'confidence:"verified"' in html,
}

all_ok = True
for name, val in checks.items():
    status = "OK" if val else "FAIL"
    # Don't mark the displayed count as a failure
    if not val and "actual" not in name:
        all_ok = False
    print(f"  {status}: {name} = {val}")

print(f"\n  ALL CRITICAL CHECKS: {'PASS' if all_ok else 'FAIL'}")
