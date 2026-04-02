"""Market-specific profile helpers."""
from __future__ import annotations

from dataclasses import replace

from .config import EngineConfig


ENERGY_SYMBOLS = {"WTICO_USD", "BCO_USD"}
INDICES_SYMBOLS = {"UK100_GBP", "NAS100_USD"}


def apply_market_profile(cfg: EngineConfig, symbol: str) -> EngineConfig:
    normalized = symbol.upper()

    if normalized in ENERGY_SYMBOLS:
        profiled = replace(cfg)
        profiled.structure = replace(
            cfg.structure,
            pullback_min_retrace=0.25,
            pullback_max_retrace=0.65,
        )
        profiled.risk = replace(
            cfg.risk,
            min_rr=1.0,
            atr_stop_padding=0.15,
        )
        return profiled

    if normalized == "XAG_USD":
        profiled = replace(cfg)
        profiled.structure = replace(
            cfg.structure,
            pullback_min_retrace=0.20,
            pullback_max_retrace=0.60,
            max_setup_age_bars=8,
        )
        profiled.risk = replace(
            cfg.risk,
            atr_stop_padding=0.15,
        )
        return profiled

    if normalized == "XAU_USD":
        profiled = replace(cfg)
        profiled.structure = replace(
            cfg.structure,
            pullback_min_retrace=0.20,
            pullback_max_retrace=0.60,
            max_setup_age_bars=8,
        )
        profiled.risk = replace(
            cfg.risk,
            atr_stop_padding=0.25,
        )
        return profiled

    if normalized in INDICES_SYMBOLS:
        profiled = replace(cfg)
        profiled.structure = replace(
            cfg.structure,
            pullback_min_retrace=0.25,
            pullback_max_retrace=0.65,
        )
        profiled.risk = replace(
            cfg.risk,
            min_rr=1.0,
            atr_stop_padding=0.05,
        )
        return profiled

    return cfg
