"""Update OANDA wording in dashboard to reflect evidence-based status."""
import re

path = "bot-dashboard/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = [
    ("OANDA 401 error.", "OANDA: auth working, TP-precision fix applied."),
    ("OANDA 401.\"", "OANDA: TP-precision fix applied.\""),
    ("OANDA API 401 Unauthorized", "Auth working, TP-precision fix applied"),
    ("OANDA 401 blocks scanning", "OANDA: auth working, TP fix applied"),
    ("OANDA 401 blocks live cycle", "OANDA: auth working, TP fix applied"),
    ("OANDA 401 -- no signals reach dispatch", "Auth working, TP fix applied"),
    ("OANDA 401 blocks live scanners and new dispatch", "TP-precision fix applied. Monitor post-fix runs"),
    ('OANDA: broken (HTTP Error 401: Unauthorized...)', 'OANDA: Auth working, TP-precision fix applied'),
    ('status:"broken",label:"BROKEN"', 'status:"partial",label:"PARTIALLY WORKING"'),
    ('{l:"Status",v:"HTTP 401"}', '{l:"Status",v:"Auth working, TP-precision fix applied"}'),
    ('{l:"Root Cause",v:"Token expired/revoked"}', '{l:"Root Cause",v:"_format_price() used 2 decimals; OANDA requires 1"}'),
    ('⛔ Blocked by HTTP 401', '⚠ Partially blocked (strategy_four works, little_rzy 401)'),
    ('⛔ Connection test (401)', '✅ Connection test (auth OK)'),
    ('⛔ Account query', '✅ Account query (auth OK)'),
    ('⛔ execute_signal()', '⚠ execute_signal() (TP-precision fix applied)'),
    ('Blocked by 401', 'Partially blocked (strategy_four works; little_rzy market-data 401)'),
    ('2 routes, 401 errors', '2 routes, TP-precision rejections + market-data 401'),
    ('401 errors', 'TP-precision rejections + market-data 401 on some routes'),
]

for old, new in replacements:
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        print(f"  Replaced {count}x: '{old[:50]}...' -> '{new[:50]}...'")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nDone. File updated: {path}")