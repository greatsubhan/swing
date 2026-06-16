"""Discover Discord channel IDs from webhook URLs using the bot token.

This script:
1. Reads .env for DISCORD_BOT_TOKEN and all DISCORD_WEBHOOK_URL_* vars
2. Calls GET /webhooks/{id} with bot auth to find each webhook's channel_id
3. Prints the channel map needed for import
"""
import os
import json
import re
import sys
from pathlib import Path

# Load .env manually
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN not found in .env")
    sys.exit(1)

# Collect all webhook URLs
webhooks = {}
for key, val in os.environ.items():
    if key.startswith("DISCORD_WEBHOOK_URL_") and val.strip():
        name = key.replace("DISCORD_WEBHOOK_URL_", "").lower()
        webhooks[name] = val.strip()

if not webhooks:
    print("ERROR: No DISCORD_WEBHOOK_URL_* vars found in .env")
    sys.exit(1)

print(f"Found {len(webhooks)} webhook URLs:")
for name, url in webhooks.items():
    print(f"  {name}: {url[:60]}...")

# Map webhook names to strategy IDs
ROUTE_MAP = {
    "little_rzy": "little_rzy",
    "strategy_two": "strategy_two",
    "cwt": "strategy_four",
    "sip": "strategy_five",
}

# Use Discord API to look up channel IDs
import asyncio

async def discover_channels():
    try:
        import aiohttp
    except ImportError:
        print("ERROR: aiohttp not installed. Run: pip install aiohttp")
        return

    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "User-Agent": "SignalPlatformDiscovery/1.0",
    }

    channel_map = {}

    async with aiohttp.ClientSession() as session:
        for name, url in webhooks.items():
            # Extract webhook ID from URL
            # URL format: https://discord.com/api/webhooks/{id}/{token}
            match = re.search(r'/webhooks/(\d+)/', url)
            if not match:
                print(f"  WARNING: Could not extract webhook ID from {name}")
                continue

            webhook_id = match.group(1)
            api_url = f"https://discord.com/api/v10/webhooks/{webhook_id}"

            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    channel_id = data.get("channel_id", "")
                    guild_id = data.get("guild_id", "")
                    channel_name = data.get("channel", {}).get("name", "unknown") if isinstance(data.get("channel"), dict) else "unknown"

                    route_id = ROUTE_MAP.get(name, name)
                    channel_map[channel_id] = {
                        "route_id": route_id,
                        "channel_name": channel_name,
                        "webhook_name": name,
                        "guild_id": guild_id,
                    }
                    print(f"  {name} -> channel {channel_id} ({channel_name}) -> route {route_id}")
                elif resp.status == 401:
                    print(f"  ERROR: Unauthorized for {name} - bot token may be invalid")
                    error_text = await resp.text()
                    print(f"    Response: {error_text[:200]}")
                elif resp.status == 403:
                    print(f"  ERROR: Forbidden for {name} - bot needs 'manage_webhooks' or 'view_channel' permission")
                else:
                    error_text = await resp.text()
                    print(f"  ERROR: HTTP {resp.status} for {name}: {error_text[:200]}")

    return channel_map

channel_map = asyncio.run(discover_channels())

if channel_map:
    # Write channel map to env
    channel_ids = list(channel_map.keys())
    route_map_json = json.dumps({cid: info["route_id"] for cid, info in channel_map.items()})

    print(f"\n{'='*60}")
    print("CHANNEL DISCOVERY COMPLETE")
    print(f"{'='*60}")
    print(f"\nAdd these to your .env file:")
    print(f"DISCORD_IMPORT_CHANNEL_IDS={','.join(channel_ids)}")
    print(f'DISCORD_IMPORT_CHANNEL_MAP={route_map_json}')
    print(f"\nChannel details:")
    for cid, info in channel_map.items():
        print(f"  {cid}: {info['channel_name']} -> {info['route_id']}")
else:
    print("\nNo channels discovered. Check bot token and permissions.")