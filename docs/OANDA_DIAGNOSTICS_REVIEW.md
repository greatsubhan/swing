# OANDA Integration Diagnostics Review
**Generated:** 2026-06-16T17:50:00+10:00
**Status:** Active — partial fix applied, pending additional instrumentation

---

## Executive Summary

The previous diagnosis of "OANDA 401 error" is **inaccurate** for the CWT strategy_four route. Evidence from `platform_output/execution_log.jsonl` proves OANDA authentication **is working** for order execution on that route. The actual root cause of failed orders is a **take-profit price precision bug** in `_format_price()`.

---

## Confirmed Evidence (from `execution_log.jsonl`)

| Timestamp (UTC) | Instrument | Units | Result | Detail |
|---|---|---|---|---|
| 2026-06-12T16:06:35 | NAS100_USD | 1 | **FILLED** | order_id=19, price=29456.4 |
| 2026-06-12T16:42:39 | NAS100_USD | 1 | **REJECTED** | TP price too precise |
| 2026-06-12T16:43:27 | NAS100_USD | 1 | **FILLED** | order_id=7, price=29589.2 |
| 2026-06-12T17:27:08 | NAS100_USD | 1 | **REJECTED** | TP price too precise |
| 2026-06-14T14:25:05 | UK100_GBP | 10 | **REJECTED** | TP price too precise |

**Fill rate for logged orders:** 2/5 (40%)
**All rejections:** same root cause — `"The Take Profit on fill specified contains a price with more precision than is allowed by the Order's instrument"`

---

## Root Cause Matrix

### Layer 1: OANDA Authentication & Market Data
| Route | Error | Evidence | Status |
|---|---|---|---|
| `strategy_four` (CWT) | — | execution_log shows successful fills | **Auth working** |
| `little_rzy` (Measured Drift) | `HTTPError 401` | dispatch_failures.jsonl (June 12-13) | **Auth failing for market data fetch** |
| `strategy_five` (Secular Bull SIP) | `HTTPError 401` | dispatch_failures.jsonl (June 13) | **Auth failing for market data fetch** |

### Layer 2: Order Validation
| Instrument | Error | Frequency | Fix |
|---|---|---|---|
| NAS100_USD | TP precision | 2/4 orders | Change index precision from 2 to 1 decimal |
| UK100_GBP | TP precision | 1/1 orders | Change index precision from 2 to 1 decimal |

### Layer 3: Dispatch & Reporting
| Route | Error | Frequency | Status |
|---|---|---|---|
| `strategy_two` (Trend Current) | `ValueError: Unsupported dispatch type: discord` | Every cycle since June 13 | **Broken — cannot send signals** |
| `strategy_five` (Secular Bull SIP) | `ValueError: Unsupported dispatch type: discord` | Every cycle since June 13 | **Broken — cannot send signals** |
| `strategy_four` (CWT) | Discord weekly/monthly webhook: `{"embeds": ["0"]}` | Every 5 min since April | **Report loop broken** |

---

## The Two User-Observed Rejected Orders

**2026-06-13 03:27 AM** and **2026-06-16 09:51 AM** — these are NOT present in `execution_log.jsonl`. This means either:

1. The orders were never submitted via `place_market_order()` (pre-flight rejection, duplicate suppression, or circuit breaker)
2. The execution log was not written (logging failure)
3. The orders were submitted by a different code path (not the platform runtime)

**Current instrument resolution from `config/platform.example.json`:**
- `strategy_four` uses `core-mixed` watchlist: `["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "NAS100_USD", "US30_USD", "SPX500_USD", "UK100_GBP", "USD_CHF", "EUR_JPY"]`
- OANDA account: `101-004-31460905-001` (practice environment `https://api-fxpractice.oanda.com`)
- Dispatch: `discord_and_oanda`

---

## Fix Applied

### Fix 1: TP Price Precision Bug (oanda_execution.py)
**Before:** `_format_price()` used 2 decimal places for all indices
**After:** Uses 1 decimal place for major indices (NAS100, UK100, SPX500, US30, DJ30, DAX, DE30, AU200)

OANDA's instrument specifications for these indices require 1 decimal place. The previous 2-decimal format caused OANDA to reject orders with "more precision than is allowed."

---

## Applied Fixes

1. ✅ **TP price precision bug fixed** — `_format_price()` in `oanda_execution.py` corrected for index instruments (1 decimal) and JP225 (0 decimals)
2. ✅ **Structured OANDA diagnostics logging** — `runtime.py` now writes `oanda_diagnostics.jsonl` per run with full order details including raw_response, error_code, account_id, and environment
3. ✅ **PROJECT_MAP.md updated** — Evidence-based per-route OANDA diagnostics table added in §20.1
4. ✅ **Dashboard wording updated** — All "OANDA 401" / "API broken" narrative replaced with evidence-based messaging

## Remaining Follow-Up (Not Yet Implemented)

1. **Resolve `ValueError: Unsupported dispatch type: discord`** — strategy_two and strategy_five cannot send any signals
2. **Fix Discord weekly/monthly report webhook** — strategy_four report retry loop is consuming resources
3. **Investigate why execution_log.jsonl has no entries for June 13 or June 16** — the user-confirmed rejected orders on those dates are not in the log; need pre-flight rejection logging
4. **Resolve 401 on little_rzy market data** — different token or endpoint needed for `https://api-fxpractice.oanda.com/v3/instruments/{inst}/candles`

---

## Diagnostic Artifacts

| File | Purpose | Current Size |
|---|---|---|
| `platform_output/execution_log.jsonl` | Order execution results | 5 entries |
| `platform_output/{route}/oanda_diagnostics.jsonl` | **NEW:** Full OANDA order diagnostics per run | Created on next run |
| `platform_output/{route}/dispatch_failures.jsonl` | Route-level failures | 11.9 MB (strategy_four) |
| `platform_output/{route}/platform_run_summary.json` | Per-run summary | Available per route |
| `platform_output/{route}/route_cycle_log.csv` | Cycle timing | Per route |

---

*Next: Review when each route last sent an OANDA order, check execution_log for gaps around 2026-06-13 03:27 and 2026-06-16 09:51.*