"""Watchlists for strategy #2."""
from __future__ import annotations

WATCHLISTS: dict[str, list[str]] = {
    "core-4h": [
        "USD_CHF",
        "ETH_USD",
        "AUD_CHF",
        "LTC_USD",
        "EUR_GBP",
        "EUR_USD",
        "XAG_USD",
        "USD_CAD",
    ],
    "bench-4h": [
        "GBP_USD",
        "BCO_USD",
        "WTICO_USD",
        "BTC_USD",
        "XAU_USD",
    ],
    "broad-4h": [
        "USD_CHF",
        "ETH_USD",
        "AUD_CHF",
        "LTC_USD",
        "EUR_GBP",
        "EUR_USD",
        "XAG_USD",
        "USD_CAD",
        "GBP_USD",
        "BCO_USD",
        "WTICO_USD",
        "BTC_USD",
        "XAU_USD",
    ],
}

ASSET_CLASS_BY_SYMBOL: dict[str, str] = {
    "USD_CHF": "forex",
    "ETH_USD": "crypto",
    "AUD_CHF": "forex",
    "LTC_USD": "crypto",
    "EUR_GBP": "forex",
    "EUR_USD": "forex",
    "XAG_USD": "metal",
    "USD_CAD": "forex",
    "GBP_USD": "forex",
    "BCO_USD": "energy",
    "WTICO_USD": "energy",
    "BTC_USD": "crypto",
    "XAU_USD": "metal",
}


def resolve_watchlist(name: str) -> list[str]:
    key = name.lower()
    if key not in WATCHLISTS:
        available = ", ".join(sorted(WATCHLISTS))
        raise ValueError(f"Unknown strategy #2 watchlist '{name}'. Available: {available}")
    return WATCHLISTS[key]


def asset_class_for(symbol: str) -> str:
    return ASSET_CLASS_BY_SYMBOL.get(symbol.upper(), "other")

