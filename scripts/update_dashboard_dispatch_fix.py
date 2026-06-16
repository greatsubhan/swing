"""Update dashboard to reflect dispatch type bug fix."""
import re

path = "bot-dashboard/index.html"
with open(path, encoding="utf-8") as f:
    content = f.read()

# 1. Update lastUpdated timestamp
content = content.replace(
    'lastUpdated:"2026-06-16 16:50:00 UTC"',
    'lastUpdated:"2026-06-16 19:22:00 UTC"'
)

# 2. Update strategy_two story and last_cycle
content = content.replace(
    'last_cycle:"2026-06-13T06:57:01+00:00"},story:"Journal empty \\u2014 no signals dispatched yet."',
    'last_cycle:"2026-06-16T05:45:22+00:00"},story:"Dispatch type bug FIXED (2026-06-16). Journal empty \\u2014 no qualifying setups."'
)

# 3. Update strategy_five story
content = content.replace(
    'story:"Monthly allocation board. No journal file yet."',
    'story:"Dispatch type bug FIXED (2026-06-16). OANDA 401 on market data remains. No journal file yet."'
)

# 4. Update footer build timestamp
content = content.replace(
    'Build: 2026-06-16 16:50:00 UTC',
    'Build: 2026-06-16 19:22:00 UTC'
)

content = content.replace(
    'Build: 2026-06-16 16:50 UTC',
    'Build: 2026-06-16 19:22 UTC'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

# Verify changes
with open(path, encoding="utf-8") as f:
    updated = f.read()

checks = [
    ("19:22:00 UTC" in updated, "Timestamp updated"),
    ("Dispatch type bug FIXED" in updated, "Strategy_two story updated"),
    ("OANDA 401 on market data remains" in updated, "Strategy_five story updated"),
]

for ok, label in checks:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}")

print("\n=== Dashboard update complete ===")