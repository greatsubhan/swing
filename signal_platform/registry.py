"""Strategy registry."""
from __future__ import annotations

from .cwt_strategy import CwtStrategy
from .little_rzy_strategy import LittleRzy1HStrategy, LittleRzyStrategy
from .secular_bull_sip_strategy import SecularBullSipStrategy
from .strategies import StrategyPlugin
from .trend_current_strategy import TrendCurrentStrategy


_STRATEGIES: dict[str, StrategyPlugin] = {
    "little_rzy": LittleRzyStrategy(),
    "little_rzy_1h": LittleRzy1HStrategy(),
    "strategy_two": TrendCurrentStrategy(),
    "strategy_four": CwtStrategy(),
    "strategy_five": SecularBullSipStrategy(),
}


def get_strategy(strategy_id: str) -> StrategyPlugin:
    key = strategy_id.lower()
    if key not in _STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_id}")
    return _STRATEGIES[key]


def list_strategies() -> list[StrategyPlugin]:
    return list(_STRATEGIES.values())
