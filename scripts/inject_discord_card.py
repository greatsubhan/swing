"""Inject Discord Import Pipeline card into dashboard INTEGRATIONS array."""
import sys

path = "bot-dashboard/index.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if "Discord Import Pipeline" in content:
    print("Already present - skipping injection")
    sys.exit(0)

old = 'actions:["TP-precision fix applied. Monitor post-fix runs; historical journals remain intact"]}]'

card_json = (
    ',{name:"Discord Import Pipeline",'
    'icon:"\\u{1F4E5}",'
    'status:"unknown",'
    'label:"READY (no data)",'
    'rows:['
    '{l:"Pipeline",v:"\\u2705 Implemented \\u2014 12/12 tests passing"},'
    '{l:"Modules",v:"discord_importer, parser, matcher"},'
    '{l:"Storage",v:"discord_import_journal.json per route"},'
    '{l:"Raw Archive",v:"discord_raw_archive.jsonl (JSONL)"},'
    '{l:"State File",v:"_discord_import_state.json"},'
    '{l:"Provenance",v:"native-journal vs discord-imported vs combined"},'
    '{l:"Status",v:"\\u26A0 No live data \\u2014 awaiting channel config"}'
    '],'
    'actions:['
    '"Set DISCORD_BOT_TOKEN env var",'
    '"Set DISCORD_IMPORT_CHANNEL_IDS",'
    '"Run: python scripts/run_discord_import.py --mode backfill"'
    ']'
    '}]'
)

if old in content:
    content = content.replace(old, card_json, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: Discord Import Pipeline card injected into dashboard")
else:
    # Try alternate pattern
    old2 = 'historical journals remain intact"]}]'
    if old2 in content:
        content = content.replace(old2, card_json, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("SUCCESS: Discord Import Pipeline card injected (alt pattern)")
    else:
        print("ERROR: Could not find insertion point")
        sys.exit(1)