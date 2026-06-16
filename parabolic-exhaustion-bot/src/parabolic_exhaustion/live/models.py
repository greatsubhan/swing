from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from parabolic_exhaustion.backtest.replay import PendingExecution, ReplayPosition
from parabolic_exhaustion.execution.state_machine import ReplayState


@dataclass
class SymbolLiveState:
    symbol: str
    current_state: ReplayState = ReplayState.NO_SETUP
    attempt_count: int = 0
    pending_entry: PendingExecution | None = None
    pending_add_index: int | None = None
    position: ReplayPosition | None = None
    sequence: int = 0
    entry_trade_id: int = 0
    bar_index: int = -1
    candidate: object | None = None
    intraday_1m: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    intraday_5m: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    seen_transition_keys: set[tuple[object, ...]] = field(default_factory=set)
    last_alert_status: str = "none"
    last_trade_snapshot: dict[str, object] | None = None
    last_bar_timestamp_1m: pd.Timestamp | None = None
    last_bar_timestamp_5m: pd.Timestamp | None = None
