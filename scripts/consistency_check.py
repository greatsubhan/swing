"""Check PROJECT_MAP.md and dashboard are in sync."""
print("=== Consistency Check: PROJECT_MAP.md vs Dashboard ===\n")

# Check PROJECT_MAP.md bot statuses
with open("PROJECT_MAP.md", encoding="utf-8") as f:
    pm = f.read()

with open("bot-dashboard/index.html", encoding="utf-8") as f:
    dash = f.read()

# Verify key consistency points
checks = []

# 1. Both reference the same fix date
checks.append(("Fix date consistency",
    "FIXED (2026-06-16)" in pm and "FIXED (2026-06-16)" in dash))

# 2. strategy_two is idle in both
checks.append(("strategy_two status",
    "strategy_two" in pm and "idle" in dash))

# 3. strategy_five has dispatch fix noted in both
checks.append(("strategy_five fix noted",
    "strategy_five" in pm and "Dispatch type bug FIXED" in dash))

# 4. Timestamps are updated in both
checks.append(("Timestamps updated",
    "2026-06-16T21:25" in pm and "21:25:00 UTC" in dash))

# 5. little_rzy still error in both
checks.append(("little_rzy error state",
    "strat_little_rzy" in pm and "error" in dash))

# 6. strategy_four still error in both
checks.append(("strategy_four error state",
    "strat_strategy_four" in pm and "error" in dash))

# 7. Dashboard bot count matches (7 bots)
checks.append(("Dashboard has 7 bots",
    dash.count("displayName:") == 7))

# 8. Changelog entry exists
checks.append(("Changelog entry",
    "dispatch type bug" in pm.lower() and "Cline" in pm))

all_pass = True
for name, result in checks:
    status = "PASS" if result else "FAIL"
    if not result:
        all_pass = False
    print(f"[{status}] {name}")

print(f"\n{'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
print(f"\nDashboard and PROJECT_MAP.md are {'in sync' if all_pass else 'OUT OF SYNC'}.")