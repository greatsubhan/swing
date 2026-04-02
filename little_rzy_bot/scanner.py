"""Live signal scanning helpers."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .alerts import concise_alert
from .config import EngineConfig
from .market_data import fetch_oanda_ohlcv
from .profiles import apply_market_profile
from .signal_engine import SignalEngine


def infer_asset_class(symbol: str) -> str:
    upper = symbol.upper()
    if upper in {"WTICO_USD", "BCO_USD"}:
        return "energy"
    if upper in {"XAU_USD", "XAG_USD"}:
        return "metals"
    if upper in {"UK100_GBP", "NAS100_USD", "US30_USD", "SPX500_USD", "FR40_EUR", "JP225_USD"}:
        return "indices"
    if "_" in upper:
        return "forex"
    return "unknown"


def scan_oanda_symbols(
    symbols: Iterable[str],
    granularity: str = "H4",
    higher_timeframe: str = "1d",
    environment: str = "practice",
    token: str | None = None,
    price: str = "M",
    use_market_profile: bool = True,
) -> list[dict]:
    results: list[dict] = []
    timeframe_label = "4h" if granularity == "H4" else granularity.lower()

    for symbol in symbols:
        fetched = fetch_oanda_ohlcv(
            instrument=symbol,
            granularity=granularity,
            start=None,
            end=None,
            price=price,
            token=token,
            environment=environment,
        )
        cfg = EngineConfig()
        if use_market_profile:
            cfg = apply_market_profile(cfg, symbol)
        engine = SignalEngine(cfg)
        signals = engine.run(
            fetched.df,
            symbol=symbol,
            asset_class=infer_asset_class(symbol),
            timeframe=timeframe_label,
            higher_timeframe=higher_timeframe,
        )
        latest_signal = signals[-1] if signals else None
        results.append(
            {
                "symbol": symbol,
                "signal_count": len(signals),
                "latest_signal": latest_signal.to_dict() if latest_signal else None,
                "alert": concise_alert(latest_signal) if latest_signal else None,
            }
        )

    return results


def save_scan_outputs(output_dir: str | Path, results: list[dict]) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scan_results.json").write_text(json.dumps(results, indent=2))
    alerts = [row["alert"] for row in results if row["alert"]]
    (out / "alerts.txt").write_text("\n".join(alerts))
