"""Market- and timeframe-specific profile helpers for Little RZY."""
from __future__ import annotations

from dataclasses import replace

from .config import EngineConfig


ENERGY_SYMBOLS = {"WTICO_USD", "BCO_USD"}
INDICES_SYMBOLS = {"UK100_GBP", "NAS100_USD", "US30_USD", "SPX500_USD", "FR40_EUR", "JP225_USD"}


def _clone(cfg: EngineConfig, profile_name: str) -> EngineConfig:
    profiled = replace(cfg)
    profiled.profile_name = profile_name
    return profiled


def apply_market_profile(cfg: EngineConfig, symbol: str, timeframe: str = "4h", variant: str = "4h") -> EngineConfig:
    normalized = symbol.upper()
    tf = timeframe.lower()

    if variant == "1h":
        profiled = _clone(cfg, f"{normalized.lower()}_1h")
        profiled.structure = replace(
            cfg.structure,
            pullback_min_retrace=0.20,
            pullback_max_retrace=0.55,
            pullback_max_bars=8,
            max_setup_age_bars=4,
        )
        profiled.risk = replace(
            cfg.risk,
            min_rr=1.0,
            atr_stop_padding=0.12 if normalized in INDICES_SYMBOLS else 0.18,
        )
        profiled.execution = replace(
            cfg.execution,
            allowed_sessions=("london", "new_york", "london_new_york"),
            min_atr_to_spread_ratio=8.0,
            min_bar_range_to_spread_ratio=3.0,
            use_htf_bias=True,
            htf_granularity="H4",
        )
        profiled.require_higher_timeframe_confirmation = True
        profiled.strategy_name = "Little RZY 1H"
        return profiled

    if normalized in ENERGY_SYMBOLS:
        profiled = _clone(cfg, f"{normalized.lower()}_{tf}")
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
        profiled = _clone(cfg, f"{normalized.lower()}_{tf}")
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
        profiled = _clone(cfg, f"{normalized.lower()}_{tf}")
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
        profiled = _clone(cfg, f"{normalized.lower()}_{tf}")
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

    return _clone(cfg, f"{normalized.lower()}_{tf}")
