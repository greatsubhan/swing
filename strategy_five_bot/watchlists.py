"""Watchlists for the Secular Bull SIP board."""
from __future__ import annotations

WATCHLISTS: dict[str, list[str]] = {
    "full-classic": [
        "XAU_USD",
        "XAG_USD",
        "NAS100_USD",
        "US30_USD",
        "BTC_USD",
    ],
    "balanced-core": [
        "XAU_USD",
        "BTC_USD",
        "US30_USD",
    ],
    "growth-core": [
        "XAU_USD",
        "XAG_USD",
        "BTC_USD",
    ],
}

ASSET_CLASS_BY_SYMBOL: dict[str, str] = {
    "XAU_USD": "metal",
    "XAG_USD": "metal",
    "NAS100_USD": "index",
    "US30_USD": "index",
    "BTC_USD": "crypto",
}

SLEEVE_LABELS: dict[str, str] = {
    "full-classic": "Full Classic",
    "balanced-core": "Balanced Core",
    "growth-core": "Growth Core",
}


def resolve_watchlist(name: str) -> list[str]:
    key = name.lower()
    if key not in WATCHLISTS:
        available = ", ".join(sorted(WATCHLISTS))
        raise ValueError(f"Unknown SIP watchlist '{name}'. Available: {available}")
    return WATCHLISTS[key]


def watchlist_label(name: str) -> str:
    return SLEEVE_LABELS.get(name.lower(), name)


def asset_class_for(symbol: str) -> str:
    return ASSET_CLASS_BY_SYMBOL.get(symbol.upper(), "other")

