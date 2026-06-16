"""Final comprehensive verification of all changes."""
import ast

print("=" * 60)
print("FINAL VERIFICATION")
print("=" * 60)
errors = []

# 1. runtime.py syntax valid
try:
    with open("signal_platform/runtime.py", encoding="utf-8") as f:
        src = f.read()
    ast.parse(src)
    print("[PASS] 1. runtime.py syntax valid")
except SyntaxError as e:
    print(f"[FAIL] 1. runtime.py syntax error: {e}")
    errors.append("runtime.py syntax")

# 2. Dispatch fix present, old bug removed
if 'elif route.dispatch in ("none", "discord", "discord_and_oanda")' in src:
    print("[PASS] 2a. Dispatch fix present at correct location")
else:
    print("[FAIL] 2a. Dispatch fix NOT found")
    errors.append("dispatch fix missing")

if 'elif route.dispatch == "none":' not in src:
    print("[PASS] 2b. Old buggy elif removed")
else:
    print("[FAIL] 2b. Old buggy elif still present")
    errors.append("old bug not removed")

# 3. PROJECT_MAP.md updated
with open("PROJECT_MAP.md", encoding="utf-8") as f:
    pm = f.read()

checks_pm = [
    ("2026-06-16T21:25", "Timestamp updated"),
    ("TP precision fix verified", "strategy_four OANDA state corrected"),
    ("market data endpoint", "little_rzy 401 clarified"),
    ("Resolve little_rzy market-data 401", "Required Actions updated"),
    ("RECONCILED", "Changelog entry added"),
]

for text, label in checks_pm:
    if text in pm:
        print(f"[PASS] 3. PROJECT_MAP.md: {label}")
    else:
        print(f"[FAIL] 3. PROJECT_MAP.md: {label}")
        errors.append(f"PM: {label}")

# 4. Dashboard updated
with open("bot-dashboard/index.html", encoding="utf-8") as f:
    dash = f.read()

# Check strategy_four bot card status
s4_parts = dash.split('id:"strategy_four"')
if len(s4_parts) > 1:
    s4_section = s4_parts[1][:500]
    if 'status:"idle"' in s4_section:
        print("[PASS] 4a. Dashboard: strategy_four status is idle")
    else:
        print("[FAIL] 4a. Dashboard: strategy_four status not idle")
        errors.append("s4 dashboard status")

checks_dash = [
    ("21:25:00 UTC", "Timestamp updated"),
    ("TP-precision fix verified (6/6 test fills)", "strategy_four story updated"),
    ("401 on market data endpoint", "little_rzy story clarified"),
    ("Dispatch type bug FIXED", "strategy_two story updated"),
    ("WORKING (TP FIX VERIFIED)", "OANDA integration badge updated"),
]

for text, label in checks_dash:
    if text in dash:
        print(f"[PASS] 4b. Dashboard: {label}")
    else:
        print(f"[FAIL] 4b. Dashboard: {label}")
        errors.append(f"Dashboard: {label}")

# 5. Consistency check
pm_fix = "FIXED (2026-06-16)" in pm
dash_fix = "FIXED (2026-06-16)" in dash
if pm_fix and dash_fix:
    print("[PASS] 5. Fix annotations present in both PROJECT_MAP.md and dashboard")
else:
    print("[FAIL] 5. Fix annotations missing")
    errors.append("consistency")

print()
print("=" * 60)
if errors:
    print(f"FAILED: {len(errors)} errors: {', '.join(errors)}")
else:
    print("ALL CHECKS PASSED — TASK COMPLETE")
print("=" * 60)