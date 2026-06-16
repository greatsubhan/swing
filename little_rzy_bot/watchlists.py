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
    "research-4h-expanded": [
        "WTICO_USD",
        "BCO_USD",
        "XAG_USD",
        "XAU_USD",
        "UK100_GBP",
        "NAS100_USD",
        "US30_USD",
        "SPX500_USD",
        "FR40_EUR",
        "JP225_USD",
        "ESPIX_EUR",
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "AUD_USD",
        "AUD_CHF",
        "USD_CAD",
        "USD_CHF",
        "NZD_USD",
        "EUR_GBP",
        "EUR_JPY",
        "GBP_JPY",
        "BTC_USD",
        "ETH_USD",
        "LTC_USD",
        "BCH_USD",
    ],
    "indices-4h": [
        "UK100_GBP",
        "NAS100_USD",
    ],
    "research-1h": [
        "NAS100_USD",
        "EUR_USD",
    ],
    "indices-1h": [
        "NAS100_USD",
    ],
    "forex-1h": [
        "EUR_USD",
    ],
}


def resolve_watchlist(name: str) -> list[str]:
    key = name.lower()
    if key not in WATCHLISTS:
        raise ValueError(f"Unknown watchlist: {name}")
    return WATCHLISTS[key]
