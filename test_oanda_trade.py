"""Quick test script to send a small test trade on NAS100 via OANDA.
Usage: python test_oanda_trade.py

This script will:
1. Connect to OANDA practice API
2. Check account balance
3. Get current NAS100 price
4. Send a tiny market BUY order (1 unit) with SL and TP
5. Report the fill
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Load .env first
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

from signal_platform.oanda_execution import OandaClient, OandaConfig


def main():
    print("=" * 60)
    print("  OANDA TEST TRADE — NAS100 (Practice Account)")
    print("=" * 60)

    # Build config from env
    env = os.environ.get("OANDA_ENVIRONMENT") or os.environ.get("OANDA_ENV", "practice")
    config = OandaConfig(
        account_id=os.environ.get("OANDA_ACCOUNT_ID", ""),
        api_token=os.environ.get("OANDA_API_TOKEN", ""),
        environment=env,
    )

    if not config.account_id or not config.api_token:
        print("\nERROR: OANDA_ACCOUNT_ID or OANDA_API_TOKEN not found in .env")
        print("Please add these to your .env file:")
        print("  OANDA_ACCOUNT_ID=101-011-30754943-002")
        print("  OANDA_API_TOKEN=your-api-token-here")
        sys.exit(1)

    client = OandaClient(config)

    # Step 1: Test connection
    print(f"\n1. Testing connection to {config.environment} environment...")
    conn = client.test_connection()
    if not conn.get("ok"):
        print(f"   FAILED: {conn.get('error')}")
        sys.exit(1)
    print(f"   Connected! Account: {conn.get('account_id')}")
    print(f"   Balance: ${conn.get('balance')}  NAV: ${conn.get('nav')}")
    print(f"   Currency: {conn.get('currency')}")

    # Step 2: Get NAS100 price
    instrument = "NAS100_USD"
    print(f"\n2. Getting current {instrument} price...")
    price = client.get_current_price(instrument)
    if not price:
        # Try alternative instrument name
        instrument = "NAS100_USD"
        print(f"   Trying {instrument}...")
        price = client.get_current_price(instrument)

    if not price:
        print(f"   Could not get price for {instrument}")
        print("   Available instruments may differ. Checking account instruments...")
        # Try with a common forex pair as fallback
        print("   Falling back to EUR_USD for test trade...")
        instrument = "EUR_USD"
        price = client.get_current_price(instrument)

    if not price:
        print("   FAILED: Could not fetch any price data")
        sys.exit(1)

    print(f"   Instrument: {instrument}")
    print(f"   Bid: {price['bid']}")
    print(f"   Ask: {price['ask']}")
    print(f"   Mid: {price['mid']}")
    print(f"   Spread: {price['spread_pips']:.1f} pips")

    # Step 3: Calculate a tiny position
    # For NAS100 at ~20000, 1 unit = ~$20,000 notional
    # For EUR_USD at ~1.08, 100 units = ~$108 notional
    entry = price["mid"]
    if "NAS100" in instrument:
        units = 1  # Just 1 unit for NAS100
        stop_distance_points = 50  # 50 points SL
        tp_distance_points = 100  # 100 points TP
        sl = entry - stop_distance_points
        tp = entry + tp_distance_points
    else:
        units = 100  # 100 units for forex
        stop_distance_pips = 20  # 20 pips SL
        tp_distance_pips = 40  # 40 pips TP
        sl = entry - stop_distance_pips * 0.0001
        tp = entry + tp_distance_pips * 0.0001

    print(f"\n3. Order details:")
    print(f"   Side: BUY")
    print(f"   Units: {units}")
    print(f"   Entry (mid): {entry:.5f}")
    print(f"   Stop Loss: {sl:.5f}")
    print(f"   Take Profit: {tp:.5f}")

    # Step 4: Place the order
    print(f"\n4. Placing market order...")
    result = client.place_market_order(
        instrument=instrument,
        units=units,
        stop_loss_price=sl,
        take_profit_price=tp,
    )

    # Step 5: Report
    print(f"\n{'=' * 60}")
    if result.success:
        print("  ORDER FILLED SUCCESSFULLY!")
        print(f"  Order ID: {result.order_id}")
        print(f"  Fill Price: {result.fill_price}")
        print(f"  Fill Units: {result.fill_units}")
        print(f"  SL: {result.stop_loss}")
        print(f"  TP: {result.take_profit}")
    else:
        print("  ORDER FAILED!")
        print(f"  Error: {result.error_code}")
        print(f"  Message: {result.error_message}")
    print(f"{'=' * 60}")

    # Show updated account balance
    print("\n5. Updated account summary:")
    acct = client.get_account_summary()
    if acct:
        print(f"   Balance: ${acct.balance}")
        print(f"   NAV: ${acct.nav}")
        print(f"   Unrealized P/L: ${acct.unrealized_pl}")
        print(f"   Open Trades: {acct.open_trade_count}")

    # Show open positions
    print("\n6. Open positions:")
    positions = client.get_open_positions()
    if positions:
        for pos in positions:
            inst = pos.get("instrument", "?")
            long_units = pos.get("long", {}).get("units", "0")
            short_units = pos.get("short", {}).get("units", "0")
            pl = pos.get("unrealizedPL", "0")
            print(f"   {inst}: long={long_units} short={short_units} P/L=${pl}")
    else:
        print("   No open positions")

    print(f"\nExecution log: platform_output/execution_log.jsonl")
    print("Done!")


if __name__ == "__main__":
    main()