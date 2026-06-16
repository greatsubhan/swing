"""Strategy interfaces for the signal platform."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .models import ScanResult


@dataclass
class StrategyScanRequest:
    strategy_id: str
    watchlist: str
    granularity: str
    higher_timeframe: str
    environment: str
    token: str | None
    price: str
    output_dir: Path
    use_market_profile: bool = True
    log_signals: bool = False
    log_filtered_setups: bool = False
    signal_log_file: str | None = None
    filtered_log_file: str | None = None
    catch_up_hours: float | None = None
    extra: dict[str, Any] | None = None


class StrategyPlugin(Protocol):
    strategy_id: str
    strategy_name: str
    default_watchlist: str

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        ...
