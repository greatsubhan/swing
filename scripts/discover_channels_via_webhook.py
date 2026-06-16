"""Discover channel IDs by querying webhooks with their own tokens."""
import os
import re
import json
import asyncio
import sys
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

import aiohttp

ROUTE_MAP = {
    "little_rzy": "little_rzy",
    "strategy_two": "strategy_two",
    "cwt": "strategy_four",
    "sip": "strategy_five",
}

async def main():
    webhooks = {}
    for key, val in os.environ.items():
        if key.startswith("DISCORD_WEBHOOK_URL_") and val.strip():
            name = key.replace("DISCORD_WEBHOOK_URL_", "").lower()
            webhooks[name] = val.strip()

    print(f"Found {len(webhooks)} webhooks")

    channel_map = {}
    async with aiohttp.ClientSession() as session:
        for name, url in webhooks.items():
            m = re.search(r'/webhooks/(\d+)/(\S+)', url)
            if not m:
                print(f"  SKIP {name}: can't parse URL")
                continue
            wid, wt = m.groups()
            # Use webhook's own token — no bot auth needed
            api = f"https://discord.com/api/v10/webhooks/{wid}/{wt}"
            async with session.get(api) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cid = data.get("channel_id", "")
                    ch = data.get("channel")
                    gn = ch.get("name", "?") if isinstance(ch, dict) else "?"
                    route_id = ROUTE_MAP.get(name, name)
                    channel_map[cid] = {
                        "route_id": route_id,
                        "channel_name": gn,
                        "webhook_name": name,
                    }
                    print(f"  OK {name} -> channel {cid} ({gn}) -> {route_id}")
                else:
                    text = await resp.text()
                    print(f"  ERR {name}: HTTP {resp.status}: {text[:100]}")

    if channel_map:
        ids = list(channel_map.keys())
        route_map_json = json.dumps({cid: info["route_id"] for cid, info in channel_map.items()})
        print(f"\nChannel IDs: {','.join(ids)}")
        print(f"Route map: {route_map_json}")
        # Write to env file
        env_content = env_path.read_text()
        if "DISCORD_IMPORT_CHANNEL_IDS" not in env_content:
            env_content += f"\nDISCORD_IMPORT_CHANNEL_IDS={','.join(ids)}\n"
            env_content += f'DISCORD_IMPORT_CHANNEL_MAP={route_map_json}\n'
            env_path.write_text(env_content)
            print(f"\nAppended to {env_path}")
    else:
        print("No channels discovered")

asyncio.run(main())