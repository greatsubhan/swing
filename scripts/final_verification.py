"""Final verification of all fixes."""
import ast
import json

print("=" * 60)
print("FINAL VERIFICATION OF ALL FIXES")
print("=" * 60)

# 1. Verify runtime.py syntax
print("\n--- 1. runtime.py Syntax Check ---")
try:
    with open("signal_platform/runtime.py", encoding="utf-8") as f:
        source = f.read()
    ast.parse(source)
    print("[PASS] runtime.py parses correctly")
except SyntaxError as e:
    print(f"[FAIL] Syntax error: {e}")

# 2. Verify dispatch fix
print("\n--- 2. Dispatch Type Fix ---")
lines = source.splitlines()
fix_found = False
old_bug_gone = True
for i, line in enumerate(lines, 1):
    if 'elif route.dispatch in ("none", "discord", "discord_and_oanda")' in line:
        fix_found = True
        print(f"[PASS] Fix found at line {i}")
    if line.strip() == 'elif route.dispatch == "none":':
        old_bug_gone = False
        print(f"[FAIL] Old buggy line still at line {i}")

if fix_found and old_bug_gone:
    print("[PASS] Dispatch fix verified — old bug removed")
else:
    if not fix_found:
        print("[FAIL] Fix NOT found")

# 3. Verify PROJECT_MAP.md updates
print("\n--- 3. PROJECT_MAP.md Updates ---")
with open("PROJECT_MAP.md", encoding="utf-8") as f:
    pm = f.read()

pm_checks = [
    ("2026-06-16T19:19" in pm, "Timestamp updated"),
    ("FIXED (2026-06-16)" in pm, "Fix noted in health snapshots"),
    ("FIXED (2026-06-16)" in pm and "strategy_two" in pm, "strategy_two fix documented"),
    ("2026-06-16" in pm and "dispatch type bug" in pm.lower(), "Changelog entry added"),
    ("FIXED (2026-06-16)" in pm and "strategy_five" in pm, "strategy_five fix documented"),
]

for ok, label in pm_checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")

# 4. Verify dashboard updates
print("\n--- 4. Dashboard Updates ---")
with open("bot-dashboard/index.html", encoding="utf-8") as f:
    dash = f.read()

dash_checks = [
    ("19:22:00 UTC" in dash, "Timestamp updated"),
    ("Dispatch type bug FIXED" in dash, "Strategy_two story updated"),
    ("OANDA 401 on market data remains" in dash, "Strategy_five story updated"),
]

for ok, label in dash_checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")

# 5. Verify no new broken patterns
print("\n--- 5. Integrity Checks ---")
# Check that the dashboard MAP still has all 7 bots
bot_count = dash.count('"id":') + dash.count("id:\"")
print(f"[INFO] Dashboard bot/node entries found: ~{bot_count} (expected ~46+)")

# Check runtime.py has all expected dispatch types handled
dispatch_handled = all(
    dtype in source
    for dtype in ['"discord"', '"discord_and_oanda"', '"none"']
)
print(f"[{'PASS' if dispatch_handled else 'FAIL'}] All dispatch types present in runtime.py")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)

print("\nSUMMARY OF CHANGES:")
print("  1. FIXED: runtime.py line 857 — dispatch type elif condition")
print("     Before: elif route.dispatch == \"none\":")
print("     After:  elif route.dispatch in (\"none\", \"discord\", \"discord_and_oanda\"):")
print("  2. UPDATED: PROJECT_MAP.md — timestamps, health snapshots, cascade, changelog")
print("  3. UPDATED: bot-dashboard/index.html — timestamps, bot stories")
print("")
print("BOTS AFFECTED:")
print("  strategy_two:  ERROR (ValueError) → IDLE (dispatch fixed)")
print("  strategy_five: ERROR (ValueError) → DEGRADED (dispatch fixed, OANDA 401 remains)")
print("")
print("UNFIXED (requires user action):")
print("  little_rzy: OANDA 401 on market data — regenerate API token")
print("  strategy_four: OANDA 401 on market data — regenerate API token")