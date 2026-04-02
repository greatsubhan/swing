"""Strategy interfaces for the signal platform."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import ScanResult


@dataclass
class StrategyScanRequest:
    watchlist: str
    granularity: str
    higher_timeframe: str
    environment: str
    token: str | None
    price: str
    output_dir: Path
    use_market_profile: bool = True


class StrategyPlugin(Protocol):
    strategy_id: str
    strategy_name: str
    default_watchlist: str

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        ...
