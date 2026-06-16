"""Position sizing calculations for automated trade execution.

Provides risk-based position sizing that calculates how many units to trade
based on account equity, risk percentage, and stop-loss distance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Pip values per unit for common OANDA instrument types
# Major pairs: 1 pip = 0.0001, JPY pairs: 1 pip = 0.01
PIP_PIP_VALUES = {
    "JPY": 0.01,
    "default": 0.0001,
}


def _pip_value_for_symbol(symbol: str) -> float:
    """Return the pip value (price increment) for a given OANDA symbol."""
    upper = symbol.upper()
    if "JPY" in upper:
        return PIP_PIP_VALUES["JPY"]
    return PIP_PIP_VALUES["default"]


@dataclass
class PositionSizeResult:
    """Result of a position size calculation."""
    units: int
    risk_amount: float
    stop_distance: float
    stop_distance_pips: float
    notional_value: float
    approved: bool
    rejection_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "units": self.units,
            "risk_amount": round(self.risk_amount, 2),
            "stop_distance": round(self.stop_distance, 5),
            "stop_distance_pips": round(self.stop_distance_pips, 1),
            "notional_value": round(self.notional_value, 2),
            "approved": self.approved,
            "rejection_reason": self.rejection_reason,
        }


def calculate_position_size(
    account_equity: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    instrument: str,
    max_units: int | None = None,
    price_mode: str = "M",
) -> PositionSizeResult:
    """Calculate position size based on fixed fractional risk.

    This uses a "risk 1% (or X%) of equity" approach where the stop-loss
    distance determines how large the position can be while keeping the
    maximum loss within the risk budget.

    Args:
        account_equity: Current account equity in account currency.
        risk_per_trade_pct: Percentage of equity to risk per trade (e.g. 1.0 = 1%).
        entry_price: Expected entry price.
        stop_loss_price: Stop-loss price level.
        instrument: OANDA instrument symbol (e.g. "EUR_USD").
        max_units: Optional maximum units allowed per trade.
        price_mode: OANDA price mode ("M"=mid, "B"=bid, "A"=ask).

    Returns:
        PositionSizeResult with approved=True if the trade passes all checks.
    """
    if account_equity <= 0:
        return PositionSizeResult(
            units=0, risk_amount=0, stop_distance=0, stop_distance_pips=0,
            notional_value=0, approved=False,
            rejection_reason="Account equity is zero or negative",
        )

    if risk_per_trade_pct <= 0:
        return PositionSizeResult(
            units=0, risk_amount=0, stop_distance=0, stop_distance_pips=0,
            notional_value=0, approved=False,
            rejection_reason="Risk per trade percentage must be positive",
        )

    risk_amount = account_equity * (risk_per_trade_pct / 100.0)
    stop_distance = abs(entry_price - stop_loss_price)

    if stop_distance == 0:
        return PositionSizeResult(
            units=0, risk_amount=risk_amount, stop_distance=0, stop_distance_pips=0,
            notional_value=0, approved=False,
            rejection_reason="Stop distance is zero — cannot size position",
        )

    pip_val = _pip_value_for_symbol(instrument)
    stop_distance_pips = stop_distance / pip_val

    # Units = risk_amount / stop_distance
    # For OANDA v20: units are positive for BUY, negative for SELL
    units = int(risk_amount / stop_distance)

    if units == 0:
        return PositionSizeResult(
            units=0, risk_amount=risk_amount, stop_distance=stop_distance,
            stop_distance_pips=stop_distance_pips,
            notional_value=0, approved=False,
            rejection_reason=f"Calculated units is 0 — stop too wide ({stop_distance_pips:.1f} pips) for risk budget",
        )

    # Apply maximum units cap
    if max_units is not None:
        if abs(units) > abs(max_units):
            logger.info(
                "Position size capped from %d to %d units (max_units=%d)",
                units, max_units, max_units,
            )
            units = max_units

    notional_value = abs(units) * entry_price

    return PositionSizeResult(
        units=units,
        risk_amount=risk_amount,
        stop_distance=stop_distance,
        stop_distance_pips=stop_distance_pips,
        notional_value=notional_value,
        approved=True,
    )


def calculate_position_size_with_atr(
    account_equity: float,
    risk_per_trade_pct: float,
    entry_price: float,
    atr_value: float,
    atr_stop_multiplier: float,
    instrument: str,
    side: str = "BUY",
    max_units: int | None = None,
) -> PositionSizeResult:
    """Calculate position size using ATR-based stop distance.

    This is an alternative sizing method that uses volatility (ATR) to
    determine the stop distance rather than a fixed structure level.

    Args:
        account_equity: Current account equity.
        risk_per_trade_pct: Risk percentage per trade.
        entry_price: Expected entry price.
        atr_value: Current ATR value.
        atr_stop_multiplier: How many ATR multiples for the stop.
        instrument: OANDA instrument symbol.
        side: "BUY" or "SELL".
        max_units: Optional maximum units cap.

    Returns:
        PositionSizeResult with sizing and approval status.
    """
    stop_distance = atr_value * atr_stop_multiplier

    if side.upper() == "BUY":
        stop_loss_price = entry_price - stop_distance
    else:
        stop_loss_price = entry_price + stop_distance

    return calculate_position_size(
        account_equity=account_equity,
        risk_per_trade_pct=risk_per_trade_pct,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        instrument=instrument,
        max_units=max_units,
    )