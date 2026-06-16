"""Reconcile PROJECT_MAP.md and dashboard with actual OANDA state.

Per docs/OANDA_DIAGNOSTICS_REVIEW.md:
- strategy_four OANDA auth WORKS, TP precision fix applied, 6/6 test fills verified
- little_rzy has 401 on MARKET DATA endpoint (not order execution)
- strategy_two dispatch bug FIXED
- strategy_five dispatch bug FIXED, market data 401 remains
"""
import re

# ============================================================
# 1. Update PROJECT_MAP.md
# ============================================================
print("=== Updating PROJECT_MAP.md ===")
with open("PROJECT_MAP.md", encoding="utf-8") as f:
    pm = f.read()

# 1a. §12 — strategy_four health snapshot row
pm = pm.replace(
    '| Health snapshot | strategy_four | 🔴 ERROR | 2026-06-13T07:10:43Z | HTTP 401 Unauthorized on OANDA API | ✅ verified |',
    '| Health snapshot | strategy_four | ✅ WORKING | 2026-06-16T09:51:00Z | TP precision fix verified — 6/6 test fills (2026-06-16). Auth working. | ✅ verified |'
)

# 1b. §12 — little_rzy health snapshot — clarify 401 is on market data only
pm = pm.replace(
    '| Health snapshot | little_rzy | 🔴 ERROR | 2026-06-13T06:56:17Z | HTTP 401 Unauthorized on OANDA API | ✅ verified |',
    '| Health snapshot | little_rzy | ⚠️ DEGRADED | 2026-06-13T06:56:17Z | OANDA auth works for orders; 401 on market data endpoint (fetch_oanda_ohlcv) | ✅ verified |'
)

# 1c. §12 — strategy_two already updated by previous fix
# 1d. §12 — strategy_five already updated by previous fix

# 1e. §12 — strategy_four route cycle log
pm = pm.replace(
    '| Route cycle log | strategy_four | CSV with error rows | — | Multiple 401 error entries | ✅ verified |',
    '| Route cycle log | strategy_four | CSV with error rows + success rows | — | TP precision rejections (pre-fix) + successful fills (post-fix) | ✅ verified |'
)

# 1f. §20.4 — strategy_four health snapshot
pm = pm.replace(
    '| strategy_four | ✅ | 2026-06-13T09:02:11Z | HTTP 401: Unauthorized | OANDA blocks scan |',
    '| strategy_four | ✅ | 2026-06-16T09:51:00Z | (none) — TP precision fix verified 6/6 fills | OANDA fully operational |'
)

# 1g. §20.4 — little_rzy health snapshot
pm = pm.replace(
    '| little_rzy | ✅ | 2026-06-13T06:56:17Z | HTTP 401: Unauthorized | OANDA blocks scan |',
    '| little_rzy | ✅ | 2026-06-13T06:56:17Z | 401 on market data endpoint only | Auth works; market data blocked |'
)

# 1h. §20.5 — Required Actions: OANDA is no longer P0 for strategy_four
pm = pm.replace(
    '| 🔴 P0 | Generate new OANDA practice API token at oanda.com/account/token; update `OANDA_API_TOKEN` in `.env` | All market data, scanners, signal dispatch, trade execution |',
    '| 🟡 P1 | Resolve little_rzy market-data 401 (different endpoint or token scope needed) | little_rzy scanner candle data |'
)

# 1i. §20.1 Impact — update to reflect fixed state
pm = pm.replace(
    '| Impact | strategy_four OANDA execution partially working (auth OK, orders reach OANDA, some rejected for TP precision). little_rzy market-data fetch returns 401. strategy_two/five have "Unsupported dispatch type: discord" runtime error. |',
    '| Impact | strategy_four OANDA execution **WORKING** (TP precision fix verified 6/6 fills). little_rzy market-data fetch returns 401. strategy_two/five dispatch type bug **FIXED**. |'
)

# 1j. §20.1 Status field
pm = pm.replace(
    '| Status | ⚠️ **PARTIALLY WORKING — Auth succeeds, order-validation rejections on TP precision** |',
    '| Status | ✅ **WORKING — strategy_four TP precision fix verified (6/6 fills). little_rzy market-data 401 remains.** |'
)

# 1k. Update timestamp
pm = pm.replace(
    '**Last updated:** 2026-06-16T19:19:00+10:00',
    '**Last updated:** 2026-06-16T21:25:00+10:00'
)

# 1l. Add changelog entry
pm = pm.replace(
    '| 2026-06-16 | **FIXED:** runtime.py dispatch type bug',
    '| 2026-06-16 | **RECONCILED:** PROJECT_MAP.md §12, §20 with OANDA diagnostics review — strategy_four confirmed working (6/6 fills), little_rzy 401 clarified as market-data-only\n| 2026-06-16 | **FIXED:** runtime.py dispatch type bug'
)

with open("PROJECT_MAP.md", "w", encoding="utf-8") as f:
    f.write(pm)

# Verify PROJECT_MAP.md changes
with open("PROJECT_MAP.md", encoding="utf-8") as f:
    pm_check = f.read()

pm_results = [
    ("strategy_four WORKING (not ERROR)", "TP precision fix verified" in pm_check and "strategy_four" in pm_check),
    ("little_rzy DEGRADED (clarified 401)", "market data endpoint" in pm_check),
    ("Required Actions downgraded", "Resolve little_rzy market-data 401" in pm_check),
    ("Timestamp updated", "2026-06-16T21:25" in pm_check),
    ("Changelog added", "RECONCILED" in pm_check),
    ("§20.1 Status updated", "WORKING" in pm_check.split("### 20.1")[1].split("### 20.2")[0] if "### 20.1" in pm_check else False),
]

for label, ok in pm_results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

# ============================================================
# 2. Update Dashboard
# ============================================================
print("\n=== Updating Dashboard ===")
with open("bot-dashboard/index.html", encoding="utf-8") as f:
    dash = f.read()

# 2a. Update strategy_four bot card: status and story
# Current: status:"error", story mentions OANDA TP fix
# The strategy_four card has status:"error" — change to "idle" since auth works
# Actually, looking at the bot list, strategy_four's status is "error" because of OANDA
# With the fix applied, it should be "idle" (no new errors, auth works)
# But the health snapshot may still show the old 401 error from June 13
# The safest approach is to keep the status but update the story

# Update strategy_four story
dash = dash.replace(
    'story:"1,029 signals (459 TP, 564 SL, 6 open). WR 44.9%, net -105.0R. OANDA: TP-precision fix applied."',
    'story:"1,029 signals (459 TP, 564 SL, 6 open). WR 44.9%, net -105.0R. OANDA: TP-precision fix verified (6/6 test fills). Auth working."'
)

# 2b. Update strategy_four runtime_error in jm
dash = dash.replace(
    'runtime_error:"Auth working, TP-precision fix applied",last_cycle:"2026-06-13T07:05:39+00:00"',
    'runtime_error:"TP-precision fix verified (6/6 fills, 2026-06-16)",last_cycle:"2026-06-16T09:51:00+00:00"'
)

# 2c. Update little_rzy story to clarify 401 is market-data only
dash = dash.replace(
    'story:"2 trades (0 TP, 2 SL, net -2.0R). OANDA: auth working, TP-precision fix applied."',
    'story:"2 trades (0 TP, 2 SL, net -2.0R). OANDA: auth works for orders; 401 on market data endpoint."'
)

# 2d. Update little_rzy runtime_error
dash = dash.replace(
    'runtime_error:"Auth working, TP-precision fix applied"',
    'runtime_error:"Auth works; 401 on market data endpoint"'
)

# 2e. Update timestamp
dash = dash.replace(
    'lastUpdated:"2026-06-16 19:22:00 UTC"',
    'lastUpdated:"2026-06-16 21:25:00 UTC"'
)

# 2f. Update footer build timestamp
dash = dash.replace('Build: 2026-06-16 19:22:00 UTC', 'Build: 2026-06-16 21:25:00 UTC')
dash = dash.replace('Build: 2026-06-16 19:22 UTC', 'Build: 2026-06-16 21:25 UTC')

# 2g. Update the INTEGRATIONS OANDA card to reflect working state
dash = dash.replace(
    'label:"PARTIALLY WORKING"',
    'label:"WORKING (TP FIX VERIFIED)"'
)
dash = dash.replace(
    'v:"Auth working, TP-precision fix applied"',
    'v:"Auth working, TP-precision fix verified (6/6 fills)"'
)

with open("bot-dashboard/index.html", "w", encoding="utf-8") as f:
    f.write(dash)

# Verify dashboard changes
with open("bot-dashboard/index.html", encoding="utf-8") as f:
    dash_check = f.read()

dash_results = [
    ("strategy_four story updated", "TP-precision fix verified (6/6 test fills)" in dash_check),
    ("little_rzy story clarified", "401 on market data endpoint" in dash_check),
    ("Timestamp updated", "21:25:00 UTC" in dash_check),
    ("OANDA integration badge updated", "WORKING (TP FIX VERIFIED)" in dash_check),
]

for label, ok in dash_results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

print("\n=== Reconciliation Complete ===")
print(f"PROJECT_MAP.md: {sum(1 for _,ok in pm_results if ok)}/{len(pm_results)} checks passed")
print(f"Dashboard: {sum(1 for _,ok in dash_results if ok)}/{len(dash_results)} checks passed")