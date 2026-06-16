"""Machine-readable market universe for the advanced engulfing strategy."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "advanced_engulfing_market_constraints.json"

SPECIAL_ALIASES = {
    "US500": "SPX500_USD",
    "SPX": "SPX500_USD",
    "SPX500USD": "SPX500_USD",
    "US30": "US30_USD",
    "DJIA": "US30_USD",
    "US30USD": "US30_USD",
    "US100": "NAS100_USD",
    "NDX": "NAS100_USD",
    "USTEC": "NAS100_USD",
    "NAS100USD": "NAS100_USD",
    "UK100": "UK100_GBP",
    "FTSE": "UK100_GBP",
    "UK100GBP": "UK100_GBP",
    "FR40": "FR40_EUR",
    "CAC": "FR40_EUR",
    "FR40EUR": "FR40_EUR",
    "JP225": "JP225_USD",
    "NI225": "JP225_USD",
    "JP225USD": "JP225_USD",
    "XAUUSD": "XAU_USD",
    "XAGUSD": "XAG_USD",
    "USOIL": "WTICO_USD",
    "WTICOUSD": "WTICO_USD",
    "UKOIL": "BCO_USD",
    "BCOUSD": "BCO_USD",
    "BTCUSD": "BTC_USD",
    "ETHUSD": "ETH_USD",
    "LTCUSD": "LTC_USD",
    "BITCOINCASHUSD": "BCH_USD",
    "BITCOINCASHUSD": "BCH_USD",
    "BCHUSD": "BCH_USD",
}


def load_constraints() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def normalize_symbol(symbol: str) -> str:
    raw = str(symbol).strip().upper()
    collapsed = raw.replace("/", "").replace("_", "").replace("-", "").replace(" ", "")
    if collapsed in SPECIAL_ALIASES:
        return SPECIAL_ALIASES[collapsed]

    normalized = raw.replace("/", "_").replace("-", "_").replace(" ", "_")
    normalized = "_".join(part for part in normalized.split("_") if part)
    if normalized in SPECIAL_ALIASES:
        return SPECIAL_ALIASES[normalized]
    return normalized


def build_universe() -> list[dict[str, object]]:
    config = load_constraints()
    constraints = dict(config["symbol_constraints"])
    seen: set[str] = set()
    universe: list[dict[str, object]] = []

    for group in config["groups"]:
        group_id = str(group["group_id"])
        minimum_timeframe = str(group["minimum_timeframe"])
        for raw_symbol in group["symbols"]:
            symbol = normalize_symbol(str(raw_symbol))
            if symbol in seen:
                continue
            seen.add(symbol)
            universe.append(
                {
                    "symbol": symbol,
                    "group_id": group_id,
                    "minimum_timeframe": str(constraints.get(symbol, minimum_timeframe)),
                }
            )

    return universe


def filter_universe(symbols: list[str] | None = None, groups: list[str] | None = None) -> list[dict[str, object]]:
    requested_symbols = {normalize_symbol(item) for item in (symbols or [])}
    requested_groups = {item.strip().lower() for item in (groups or [])}
    rows = build_universe()
    if requested_groups:
        rows = [row for row in rows if str(row["group_id"]).lower() in requested_groups]
    if requested_symbols:
        rows = [row for row in rows if str(row["symbol"]) in requested_symbols]
    return rows
