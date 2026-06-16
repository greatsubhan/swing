from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReplayState(str, Enum):
    NO_SETUP = "NO_SETUP"
    DAILY_CANDIDATE = "DAILY_CANDIDATE"
    EXHAUSTION_WATCH = "EXHAUSTION_WATCH"
    VWAP_LOST = "VWAP_LOST"
    VWAP_RETEST_PENDING = "VWAP_RETEST_PENDING"
    ENTRY_TRIGGERED = "ENTRY_TRIGGERED"
    PARTIAL_TAKEN = "PARTIAL_TAKEN"
    BREAK_EVEN_PROTECTED = "BREAK_EVEN_PROTECTED"
    ADD_TRIGGERED = "ADD_TRIGGERED"
    EXITED = "EXITED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class StateTransition:
    previous_state: ReplayState
    new_state: ReplayState
    reason: str
