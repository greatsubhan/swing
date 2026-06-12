"""Watchlists for the CWT strategy."""
from __future__ import annotations

WATCHLISTS: dict[str, list[str]] = {
    "core-mixed": [
        "NAS100_USD",
        "SPX500_USD",
        "UK100_GBP",
        "USD_JPY",
        "NZD_USD",
        "AUD_USD",
        "EUR_USD",
        "GBP_JPY",
    ],
    "watch-mixed": [
        "FR40_EUR",
        "GBP_USD",
        "US30_USD",
        "USD_CHF",
        "GBP_NZD",
        "NZD_JPY",
        "XAG_USD",
        "BCO_USD",
    ],
    "broad-mixed": [
        "NAS100_USD",
        "SPX500_USD",
        "UK100_GBP",
        "USD_JPY",
        "NZD_USD",
        "AUD_USD",
        "EUR_USD",
        "GBP_JPY",
        "FR40_EUR",
        "GBP_USD",
        "US30_USD",
        "USD_CHF",
        "GBP_NZD",
        "NZD_JPY",
        "XAG_USD",
        "BCO_USD",
    ],
}

MINIMUM_TIMEFRAME_BY_SYMBOL: dict[str, str] = {
    "NAS100_USD": "5m",
    "SPX500_USD": "5m",
    "UK100_GBP": "5m",
    "USD_JPY": "5m",
    "NZD_USD": "5m",
    "AUD_USD": "5m",
    "EUR_USD": "5m",
    "GBP_JPY": "15m",
    "FR40_EUR": "5m",
    "GBP_USD": "5m",
    "US30_USD": "5m",
    "USD_CHF": "5m",
    "GBP_NZD": "15m",
    "NZD_JPY": "15m",
    "XAG_USD": "15m",
    "BCO_USD": "15m",
}

ASSET_CLASS_BY_SYMBOL: dict[str, str] = {
    "NAS100_USD": "index",
    "SPX500_USD": "index",
    "UK100_GBP": "index",
    "USD_JPY": "forex",
    "NZD_USD": "forex",
    "AUD_USD": "forex",
    "EUR_USD": "forex",
    "GBP_JPY": "forex_cross",
    "FR40_EUR": "index",
    "GBP_USD": "forex",
    "US30_USD": "index",
    "USD_CHF": "forex",
    "GBP_NZD": "forex_cross",
    "NZD_JPY": "forex_cross",
    "XAG_USD": "metal",
    "BCO_USD": "energy",
}


def resolve_watchlist(name: str) -> list[str]:
    key = name.lower()
    if key not in WATCHLISTS:
        available = ", ".join(sorted(WATCHLISTS))
        raise ValueError(f"Unknown CWT watchlist '{name}'. Available: {available}")
    return WATCHLISTS[key]


def minimum_timeframe_for(symbol: str) -> str:
    return MINIMUM_TIMEFRAME_BY_SYMBOL.get(symbol.upper(), "5m")


def asset_class_for(symbol: str) -> str:
    return ASSET_CLASS_BY_SYMBOL.get(symbol.upper(), "other")
