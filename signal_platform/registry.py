"""Strategy registry."""
from __future__ import annotations

from .little_rzy_strategy import LittleRzyStrategy
from .strategies import StrategyPlugin


_STRATEGIES: dict[str, StrategyPlugin] = {
    "little_rzy": LittleRzyStrategy(),
}


def get_strategy(strategy_id: str) -> StrategyPlugin:
    key = strategy_id.lower()
    if key not in _STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_id}")
    return _STRATEGIES[key]


def list_strategies() -> list[StrategyPlugin]:
    return list(_STRATEGIES.values())
