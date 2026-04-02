"""Curated watchlists for live signal scanning."""
from __future__ import annotations


WATCHLISTS = {
    "primary-4h": [
        "WTICO_USD",
        "BCO_USD",
        "XAG_USD",
        "UK100_GBP",
        "NAS100_USD",
        "XAU_USD",
    ],
    "energy-4h": [
        "WTICO_USD",
        "BCO_USD",
    ],
    "metals-4h": [
        "XAG_USD",
        "XAU_USD",
    ],
    "indices-4h": [
        "UK100_GBP",
        "NAS100_USD",
    ],
}


def resolve_watchlist(name: str) -> list[str]:
    key = name.lower()
    if key not in WATCHLISTS:
        raise ValueError(f"Unknown watchlist: {name}")
    return WATCHLISTS[key]
