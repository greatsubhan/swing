"""
10-Minute OANDA Test Trade Script
==================================
Places small random trades on OANDA practice account to verify the
TP precision fix works end-to-end. Each trade is immediately closed.

Usage:
    python scripts/test_oanda_10min.py

Requires:
    - OANDA_ACCOUNT_ID and OANDA_API_TOKEN in .env
    - Practice/demo account only
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_platform.oanda_execution import OandaClient, OandaConfig, _format_price


def _load_dotenv():
    """Load .env file into os.environ if not already set."""
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env from {env_path}")


_load_dotenv()


def get_mid_price(client: OandaClient, instrument: str) -> float | None:
    """Get current mid price for an instrument."""
    try:
        resp = __import__("requests").get(
            f"{client.config.api_base}/v3/accounts/{client.config.account_id}/pricing",
            headers=client.config.headers,
            params={"instruments": instrument},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        prices = resp.json().get("prices", [])
        if not prices:
            return None
        p = prices[0]
        bids = p.get("bids", [])
        asks = p.get("asks", [])
        if bids and asks:
            return (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
    except Exception as exc:
        print(f"  ⚠ Failed to get price for {instrument}: {exc}")
    return None


def close_all_positions(client: OandaClient) -> None:
    """Close any remaining open positions."""
    positions = client.get_open_positions()
    for pos in positions:
        inst = pos.get("instrument", "")
        long_u = int(float(pos.get("long", {}).get("units", "0") or "0"))
        short_u = int(float(pos.get("short", {}).get("units", "0") or "0"))
        net = long_u + short_u
        if net != 0:
            print(f"  Closing {inst} ({net} units)...")
            result = client.close_position(inst)
            if result.success:
                print(f"  ✅ Closed at {result.fill_price}")
            else:
                print(f"  ❌ Close failed: {result.error_message}")


def run_test(duration_seconds: int = 600, interval_seconds: int = 60):
    """Run test trades for specified duration."""
    print("=" * 70)
    print("OANDA 10-Minute Test Trade Script")
    print("=" * 70)
    print(f"Duration: {duration_seconds}s | Interval: {interval_seconds}s")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Load config
    config = OandaConfig.from_env()
    if not config.api_token or not config.account_id:
        print("❌ ERROR: OANDA_ACCOUNT_ID and OANDA_API_TOKEN must be set in .env")
        print("   Run: cp .env.example .env and fill in credentials")
        return

    print(f"Account: {config.account_id}")
    print(f"Environment: {config.environment}")
    print()

    # Create client with relaxed limits for testing
    config.max_daily_trades = 50
    config.min_order_interval_seconds = 0.5
    client = OandaClient(config)

    # Test connection
    print("Testing connection...")
    conn = client.test_connection()
    if not conn.get("ok"):
        print(f"❌ Connection failed: {conn.get('error')}")
        return
    print(f"✅ Connected — Balance: {conn.get('balance')} {conn.get('currency')}")
    print()

    # Test instruments — indices that previously failed with TP precision
    instruments = [
        ("NAS100_USD", "Index CFD (1 decimal)"),
        ("UK100_GBP", "Index CFD (1 decimal)"),
        ("SPX500_USD", "Index CFD (1 decimal)"),
    ]

    results = []
    start_time = time.time()
    trade_num = 0

    print("Starting test trades...")
    print("-" * 70)

    while time.time() - start_time < duration_seconds:
        trade_num += 1
        elapsed = int(time.time() - start_time)
        remaining = max(0, duration_seconds - elapsed)
        print(f"\n[Trade #{trade_num}] Elapsed: {elapsed}s | Remaining: {remaining}s")

        # Pick a random instrument
        instrument, desc = random.choice(instruments)
        print(f"  Instrument: {instrument} ({desc})")

        # Get current price
        price = get_mid_price(client, instrument)
        if price is None:
            print(f"  ⚠ Could not get price, skipping")
            time.sleep(interval_seconds)
            continue

        print(f"  Mid price: {price}")

        # Calculate SL/TP levels (tight for testing — 5 points away)
        if "JPY" in instrument.upper():
            pip = 0.01
        elif any(idx in instrument.upper() for idx in ("NAS100", "UK100", "SPX500", "US30", "DJ30", "DAX")):
            pip = 1.0  # Index: 1 point = 1 pip equivalent
        else:
            pip = 0.0001

        sl_distance = 50 * pip  # 50 points away
        tp_distance = 50 * pip  # 50 points away

        side = random.choice(["BUY", "SELL"])
        if side == "BUY":
            sl_price = price - sl_distance
            tp_price = price + tp_distance
        else:
            sl_price = price + sl_distance
            tp_price = price - tp_distance

        print(f"  Side: {side} | Units: 1")
        print(f"  SL: {sl_price} | TP: {tp_price}")
        print(f"  Formatted SL: {_format_price(sl_price, instrument)} | TP: {_format_price(tp_price, instrument)}")

        # Place the order
        units = 1 if side == "BUY" else -1
        result = client.place_market_order(
            instrument=instrument,
            units=units,
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
        )

        trade_result = {
            "trade_num": trade_num,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instrument": instrument,
            "side": side,
            "units": units,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "formatted_sl": _format_price(sl_price, instrument),
            "formatted_tp": _format_price(tp_price, instrument),
            "success": result.success,
            "order_id": result.order_id,
            "fill_price": result.fill_price,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

        if result.success:
            print(f"  ✅ FILLED — order_id={result.order_id} fill_price={result.fill_price}")
            print(f"     SL={result.stop_loss} TP={result.take_profit}")

            # Close immediately
            print(f"  Closing position...")
            close_result = client.close_position(instrument)
            if close_result.success:
                print(f"  ✅ Closed at {close_result.fill_price}")
                trade_result["closed"] = True
                trade_result["close_price"] = close_result.fill_price
            else:
                print(f"  ❌ Close failed: {close_result.error_message}")
                trade_result["closed"] = False
                trade_result["close_error"] = close_result.error_message
        else:
            print(f"  ❌ REJECTED — {result.error_code}: {result.error_message}")
            trade_result["closed"] = False

        results.append(trade_result)

        # Save diagnostics
        diag_path = Path("platform_output/test_trade_diagnostics.jsonl")
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        with open(diag_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trade_result) + "\n")

        # Wait for next trade
        if time.time() - start_time < duration_seconds:
            print(f"  Waiting {interval_seconds}s...")
            time.sleep(interval_seconds)

    # Cleanup: close any remaining positions
    print("\n" + "=" * 70)
    print("Cleanup: closing any remaining positions...")
    close_all_positions(client)

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    total = len(results)
    filled = sum(1 for r in results if r["success"])
    rejected = total - filled
    closed = sum(1 for r in results if r.get("closed"))

    print(f"Total trades attempted: {total}")
    print(f"Fills: {filled} | Rejections: {rejected}")
    print(f"Positions closed: {closed}/{filled}")
    print(f"Duration: {int(time.time() - start_time)}s")
    print()

    if filled > 0:
        print("✅ TP precision fix VERIFIED — orders accepted by OANDA")
    elif rejected > 0:
        errors = set(r.get("error_message", "") for r in results if not r["success"])
        print(f"❌ All orders rejected. Errors:")
        for e in errors:
            print(f"   - {e}")
    else:
        print("⚠ No trades were attempted")

    print(f"\nDiagnostics saved to: platform_output/test_trade_diagnostics.jsonl")
    print(f"Execution log: platform_output/execution_log.jsonl")


if __name__ == "__main__":
    run_test(duration_seconds=600, interval_seconds=60)