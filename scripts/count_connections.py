#!/usr/bin/env python3
"""Count connections in dashboard HTML and compare with PROJECT_MAP.md."""
import re
from pathlib import Path

html = Path("bot-dashboard/index.html").read_text(encoding="utf-8")

# Find all connections
conns = re.findall(r'\{from:"([^"]+)",to:"([^"]+)"', html)
print(f"HTML connection count: {len(conns)}")
for i, (f, t) in enumerate(conns, 1):
    print(f"  {i}. {f} -> {t}")

# Also count from PROJECT_MAP.md
pmap = Path("PROJECT_MAP.md").read_text(encoding="utf-8")
pmap_conns = re.findall(r'\| `([^`]+)` \| `([^`]+)` \|.*?\|.*?\| verified \|', pmap)
inferred_conns = re.findall(r'\| `([^`]+)` \| `([^`]+)` \|.*?\|.*?\| inferred \|', pmap)
print(f"\nPROJECT_MAP.md verified connections: {len(pmap_conns)}")
print(f"PROJECT_MAP.md inferred connections: {len(inferred_conns)}")
print(f"PROJECT_MAP.md total connections: {len(pmap_conns) + len(inferred_conns)}")