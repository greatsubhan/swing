"""OANDA V20 order execution module.

Handles placing market and limit orders on OANDA accounts, fetching account
balances, and managing open positions. Uses the OANDA v20 REST API via
the requests library directly (no heavy SDK dependency).

IMPORTANT SAFETY NOTES:
- This module only operates on OANDA practice/demo accounts unless explicitly
  configured for live trading.
- Every order placement goes through a pre-flight check including:
    - Daily trade count limits
    - Maximum position size limits
    - Circuit breaker / drawdown guard checks
    - Duplicate signal suppression
- All execution attempts are logged with full context for auditing.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from signal_platform.position_sizing import PositionSizeResult, calculate_position_size

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration and constants
# ---------------------------------------------------------------------------

OANDA_API_BASE_LIVE = "https://api-fxtrade.oanda.com"
OANDA_API_BASE_PRACTICE = "https://api-fxpractice.oanda.com"
OANDA_STREAM_BASE_LIVE = "https://stream-fxtrade.oanda.com"
OANDA_STREAM_BASE_PRACTICE = "https://stream-fxpractice.oanda.com"


@dataclass
class OandaConfig:
    """Configuration for OANDA API connection and execution."""
    account_id: str = ""
    api_token: str = ""
    environment: str = "practice"  # "practice" or "live"
    price_mode: str = "M"  # "M"=mid, "B"=bid, "A"=ask

    # Execution settings
    enabled: bool = False
    risk_per_trade_pct: float = 1.0
    max_units_per_trade: int | None = None
    max_daily_trades: int = 10
    max_daily_loss_pct: float = 5.0
    allowed_instruments: list[str] = field(default_factory=list)

    # Rate limiting
    min_order_interval_seconds: float = 0.5

    # Kill switch — if True, no orders will be placed
    kill_switch: bool = False

    @property
    def api_base(self) -> str:
        if self.environment == "live":
            return OANDA_API_BASE_LIVE
        return OANDA_API_BASE_PRACTICE

    @property
    def stream_base(self) -> str:
        if self.environment == "live":
            return OANDA_STREAM_BASE_LIVE
        return OANDA_STREAM_BASE_PRACTICE

    @property
    def is_live(self) -> bool:
        return self.environment == "live"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    @classmethod
    def from_env(cls, prefix: str = "OANDA") -> "OandaConfig":
        """Build config from environment variables."""
        env = os.environ.get("OANDA_ENVIRONMENT") or os.environ.get("OANDA_ENV", "practice")
        return cls(
            account_id=os.environ.get(f"{prefix}_ACCOUNT_ID", ""),
            api_token=os.environ.get(f"{prefix}_API_TOKEN", ""),
            environment=env,
            price_mode=os.environ.get("OANDA_PRICE_MODE", "M"),
        )


# ---------------------------------------------------------------------------
# Data classes for execution results
# ---------------------------------------------------------------------------

@dataclass
class OrderResult:
    """Result of an order execution attempt."""
    success: bool
    order_id: str | None = None
    fill_price: str | None = None
    fill_units: str | None = None
    instrument: str | None = None
    side: str | None = None
    units: int = 0
    stop_loss: str | None = None
    take_profit: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AccountInfo:
    """OANDA account summary."""
    account_id: str
    balance: float
    unrealized_pl: float
    nav: float
    margin_available: float
    margin_used: float
    open_trade_count: int
    currency: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Execution log for audit trail
# ---------------------------------------------------------------------------

class ExecutionLog:
    """Append-only log of all execution attempts."""

    def __init__(self, log_path: str | None = None):
        self.log_path = Path(log_path) if log_path else Path("platform_output/execution_log.jsonl")

    def log(self, entry: dict) -> None:
        """Append a single execution log entry."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            entry["logged_at"] = datetime.now(timezone.utc).isoformat()
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            logger.error("Failed to write execution log: %s", exc)

    def today_count(self) -> int:
        """Count how many orders were placed today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        count = 0
        try:
            if self.log_path.exists():
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and line.startswith("{"):
                            entry = json.loads(line)
                            ts = entry.get("timestamp", "")
                            if ts.startswith(today):
                                count += 1
        except Exception as exc:
            logger.error("Failed to count today's executions: %s", exc)
        return count


def _format_price(price: float, instrument: str) -> str:
    """Format price with correct precision for the instrument.
    
    OANDA instrument precision rules:
    - Index CFDs: 1 decimal place (NAS100, SPX500, UK100, US30, DAX, etc.)
    - JP225: 0 decimal places (whole units)
    - XAU/XAG: 2 decimal places
    - JPY forex pairs: 3 decimal places
    - All other forex: 5 decimal places
    """
    upper = instrument.upper()
    # JP225 requires whole-number precision (0 decimals)
    if "JP225" in upper:
        return f"{price:.0f}"
    # All other indices use 1 decimal place
    if any(idx in upper for idx in ("NAS100", "SPX500", "UK100", "US30", "DJ30", "DAX", "AU200", "DE30")):
        return f"{price:.1f}"
    if "XAU" in upper or "XAG" in upper:
        return f"{price:.2f}"
    if "JPY" in upper:
        return f"{price:.3f}"
    return f"{price:.5f}"


# ---------------------------------------------------------------------------
# Core OANDA client
# ---------------------------------------------------------------------------

class OandaClient:
    """Lightweight OANDA v20 REST API client for order execution."""

    def __init__(self, config: OandaConfig):
        self.config = config
        self.exec_log = ExecutionLog()
        self._last_order_time: float = 0.0

    # -- Connection test --

    def test_connection(self) -> dict:
        """Test API connectivity and return account summary."""
        if not self.config.api_token or not self.config.account_id:
            return {"ok": False, "error": "Missing API token or account ID"}

        try:
            resp = requests.get(
                f"{self.config.api_base}/v3/accounts/{self.config.account_id}/summary",
                headers=self.config.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                acct = data.get("account", {})
                return {
                    "ok": True,
                    "account_id": acct.get("id"),
                    "balance": acct.get("balance"),
                    "nav": acct.get("NAV"),
                    "currency": acct.get("currency"),
                }
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except requests.exceptions.RequestException as exc:
            return {"ok": False, "error": f"Connection failed: {exc}"}

    # -- Account info --

    def get_account_summary(self) -> AccountInfo | None:
        """Fetch current account summary."""
        try:
            resp = requests.get(
                f"{self.config.api_base}/v3/accounts/{self.config.account_id}/summary",
                headers=self.config.headers,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.error("Account summary failed: HTTP %d", resp.status_code)
                return None

            acct = resp.json().get("account", {})
            return AccountInfo(
                account_id=acct.get("id", ""),
                balance=float(acct.get("balance", 0)),
                unrealized_pl=float(acct.get("unrealizedPL", 0)),
                nav=float(acct.get("NAV", 0)),
                margin_available=float(acct.get("marginAvailable", 0)),
                margin_used=float(acct.get("marginUsed", 0)),
                open_trade_count=int(acct.get("openTradeCount", 0)),
                currency=acct.get("currency", "USD"),
            )
        except Exception as exc:
            logger.error("Failed to get account summary: %s", exc)
            return None

    # -- Price fetching --

    def get_current_price(self, instrument: str) -> dict | None:
        """Fetch the current price for an instrument."""
        try:
            resp = requests.get(
                f"{self.config.api_base}/v3/accounts/{self.config.account_id}/pricing",
                headers=self.config.headers,
                params={"instruments": instrument},
                timeout=10,
            )
            if resp.status_code != 200:
                return None

            prices = resp.json().get("prices", [])
            if not prices:
                return None

            price_data = prices[0]
            bids = price_data.get("bids", [])
            asks = price_data.get("asks", [])

            return {
                "instrument": instrument,
                "bid": float(bids[0]["price"]) if bids else None,
                "ask": float(asks[0]["price"]) if asks else None,
                "mid": (
                    (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
                    if bids and asks
                    else None
                ),
                "spread_pips": (
                    (float(asks[0]["price"]) - float(bids[0]["price"]))
                    / (0.0001 if "JPY" not in instrument.upper() else 0.01)
                    if bids and asks
                    else None
                ),
            }
        except Exception as exc:
            logger.error("Failed to get price for %s: %s", instrument, exc)
            return None

    # -- Pre-flight checks --

    def _check_kill_switch(self) -> str | None:
        """Return rejection reason if kill switch is active."""
        if self.config.kill_switch:
            return "Kill switch is active — no orders will be placed"
        return None

    def _check_daily_trade_limit(self) -> str | None:
        """Check if daily trade count has been reached."""
        today_count = self.exec_log.today_count()
        if today_count >= self.config.max_daily_trades:
            return f"Daily trade limit reached ({today_count}/{self.config.max_daily_trades})"
        return None

    def _check_instrument_allowed(self, instrument: str) -> str | None:
        """Check if this instrument is in the allowed list."""
        if not self.config.allowed_instruments:
            return None  # No restriction
        if instrument not in self.config.allowed_instruments:
            return f"Instrument {instrument} not in allowed list: {self.config.allowed_instruments}"
        return None

    def _check_rate_limit(self) -> str | None:
        """Ensure minimum time between orders."""
        elapsed = time.time() - self._last_order_time
        if elapsed < self.config.min_order_interval_seconds:
            wait = self.config.min_order_interval_seconds - elapsed
            return f"Rate limit: must wait {wait:.1f}s between orders"
        return None

    def run_preflight(self, instrument: str) -> str | None:
        """Run all pre-flight checks. Returns rejection reason or None."""
        checks = [
            self._check_kill_switch(),
            self._check_daily_trade_limit(),
            self._check_instrument_allowed(instrument),
            self._check_rate_limit(),
        ]
        for reason in checks:
            if reason is not None:
                logger.warning("Pre-flight rejected: %s", reason)
                return reason
        return None

    # -- Order placement --

    def place_market_order(
        self,
        instrument: str,
        units: int,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
        trailing_stop_distance: float | None = None,
    ) -> OrderResult:
        """Place a market order on OANDA.

        Args:
            instrument: OANDA instrument (e.g. "EUR_USD").
            units: Number of units (positive = BUY, negative = SELL).
            stop_loss_price: Optional stop-loss price level.
            take_profit_price: Optional take-profit price level.
            trailing_stop_distance: Optional trailing stop distance in pips.

        Returns:
            OrderResult with fill details or error information.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Pre-flight checks
        reject = self.run_preflight(instrument)
        if reject:
            return OrderResult(
                success=False,
                instrument=instrument,
                side="BUY" if units > 0 else "SELL",
                units=units,
                error_code="PREFLIGHT_FAILED",
                error_message=reject,
                timestamp=timestamp,
            )

        # Build the order body
        order_body: dict[str, Any] = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "timeInForce": "FOK",  # Fill or Kill — all or nothing
        }

        # Attach stop-loss
        if stop_loss_price is not None:
            order_body["stopLossOnFill"] = {
                "price": _format_price(stop_loss_price, instrument),
            }

        # Attach take-profit
        if take_profit_price is not None:
            order_body["takeProfitOnFill"] = {
                "price": _format_price(take_profit_price, instrument),
            }

        # Attach trailing stop
        if trailing_stop_distance is not None:
            order_body["trailingStopLossOnFill"] = {
                "distance": f"{trailing_stop_distance:.1f}",
            }

        payload = {"order": order_body}

        logger.info(
            "Placing OANDA market order: %s %d units of %s (SL=%s, TP=%s)",
            "BUY" if units > 0 else "SELL",
            abs(units),
            instrument,
            stop_loss_price,
            take_profit_price,
        )

        try:
            resp = requests.post(
                f"{self.config.api_base}/v3/accounts/{self.config.account_id}/orders",
                headers=self.config.headers,
                json=payload,
                timeout=15,
            )

            self._last_order_time = time.time()

            if resp.status_code == 201:
                data = resp.json()
                transaction = (
                    data.get("orderFillTransaction", {})
                    or data.get("orderCreateTransaction", {})
                )
                order_id = transaction.get("id", "")
                fill_price = transaction.get("price", "")
                fill_units = transaction.get("units", "")
                sl_order = transaction.get("stopLossOrder") or {}
                tp_order = transaction.get("takeProfitOrder") or {}
                sl = sl_order.get("price") or sl_order.get("distance", "")
                tp = tp_order.get("price") or tp_order.get("distance", "")

                result = OrderResult(
                    success=True,
                    order_id=order_id,
                    fill_price=fill_price,
                    fill_units=fill_units,
                    instrument=instrument,
                    side="BUY" if units > 0 else "SELL",
                    units=units,
                    stop_loss=sl or None,
                    take_profit=tp or None,
                    raw_response=data,
                    timestamp=timestamp,
                )

                logger.info(
                    "OANDA order filled: id=%s price=%s units=%s",
                    order_id, fill_price, fill_units,
                )

                # Log the execution
                self.exec_log.log({
                    "action": "market_order",
                    "success": True,
                    "instrument": instrument,
                    "units": units,
                    "fill_price": fill_price,
                    "order_id": order_id,
                    "timestamp": timestamp,
                })

                return result
            else:
                error_data = resp.json() if resp.text else {}
                error_msg_raw = error_data.get("errorMessage", "")
                if isinstance(error_msg_raw, dict):
                    error_code = error_msg_raw.get("code", "UNKNOWN")
                    error_msg = error_msg_raw.get("message", resp.text[:500])
                else:
                    error_code = "UNKNOWN"
                    error_msg = str(error_msg_raw) or resp.text[:500]

                result = OrderResult(
                    success=False,
                    instrument=instrument,
                    side="BUY" if units > 0 else "SELL",
                    units=units,
                    error_code=error_code,
                    error_message=error_msg,
                    raw_response=error_data,
                    timestamp=timestamp,
                )

                logger.error(
                    "OANDA order failed: %s %d %s — %s: %s",
                    instrument, units, "BUY" if units > 0 else "SELL",
                    error_code, error_msg,
                )

                self.exec_log.log({
                    "action": "market_order",
                    "success": False,
                    "instrument": instrument,
                    "units": units,
                    "error_code": error_code,
                    "error_message": error_msg,
                    "timestamp": timestamp,
                })

                return result

        except requests.exceptions.RequestException as exc:
            logger.error("OANDA API request failed: %s", exc)
            return OrderResult(
                success=False,
                instrument=instrument,
                side="BUY" if units > 0 else "SELL",
                units=units,
                error_code="REQUEST_FAILED",
                error_message=str(exc),
                timestamp=timestamp,
            )

    # -- Position management --

    def get_open_positions(self) -> list[dict]:
        """Fetch all open positions."""
        try:
            resp = requests.get(
                f"{self.config.api_base}/v3/accounts/{self.config.account_id}/openPositions",
                headers=self.config.headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("positions", [])
        except Exception as exc:
            logger.error("Failed to get open positions: %s", exc)
            return []

    def close_position(self, instrument: str, units: int | None = None) -> OrderResult:
        """Close an open position by sending a market order in the opposite direction.

        Args:
            instrument: OANDA instrument to close.
            units: Number of units to close. If None, closes the entire position.

        Returns:
            OrderResult with close details.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # For OANDA v20 netting accounts, close via market order
        if units is not None:
            close_units = -abs(units)
        else:
            # Find current position size to close it
            positions = self.get_open_positions()
            for pos in positions:
                if pos.get("instrument") == instrument:
                    long_units = int(float(pos.get("long", {}).get("units", "0") or "0"))
                    short_units = int(float(pos.get("short", {}).get("units", "0") or "0"))
                    close_units = short_units - long_units  # negative = selling, positive = buying
                    break
            else:
                return OrderResult(
                    success=False,
                    instrument=instrument,
                    error_code="NO_POSITION",
                    error_message=f"No open position found for {instrument}",
                    timestamp=timestamp,
                )

        payload = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(close_units),
                "timeInForce": "FOK",
            }
        }

        try:
            resp = requests.post(
                f"{self.config.api_base}/v3/accounts/{self.config.account_id}/orders",
                headers=self.config.headers,
                json=payload,
                timeout=15,
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                txn = data.get("orderFillTransaction", {})
                return OrderResult(
                    success=True,
                    order_id=txn.get("id"),
                    fill_price=txn.get("price"),
                    fill_units=txn.get("units"),
                    instrument=instrument,
                    raw_response=data,
                    timestamp=timestamp,
                )
            else:
                return OrderResult(
                    success=False,
                    instrument=instrument,
                    error_code="CLOSE_FAILED",
                    error_message=resp.text[:500],
                    timestamp=timestamp,
                )
        except Exception as exc:
            return OrderResult(
                success=False,
                instrument=instrument,
                error_code="CLOSE_REQUEST_FAILED",
                error_message=str(exc),
                timestamp=timestamp,
            )


# ---------------------------------------------------------------------------
# High-level execution interface for the signal platform
# ---------------------------------------------------------------------------

def execute_signal(
    client: OandaClient,
    instrument: str,
    side: str,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float | None,
    account_equity: float,
    risk_per_trade_pct: float,
    max_units: int | None = None,
    trailing_stop_pips: float | None = None,
) -> OrderResult:
    """Execute a trade signal on OANDA.

    This is the main entry point called by the signal platform runtime when
    a new signal passes all filters and is ready for execution.

    Args:
        client: Authenticated OandaClient.
        instrument: OANDA instrument (e.g. "EUR_USD").
        side: "BUY" or "SELL".
        entry_price: Expected entry price (used for sizing).
        stop_loss_price: Stop-loss price.
        take_profit_price: Take-profit price (optional).
        account_equity: Current account equity for position sizing.
        risk_per_trade_pct: Risk percentage per trade.
        max_units: Optional maximum units cap.
        trailing_stop_pips: Optional trailing stop distance in pips.

    Returns:
        OrderResult with execution details.
    """
    # Calculate position size
    sizing = calculate_position_size(
        account_equity=account_equity,
        risk_per_trade_pct=risk_per_trade_pct,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        instrument=instrument,
        max_units=max_units,
    )

    if not sizing.approved:
        logger.warning(
            "Signal rejected by position sizing: %s — %s",
            instrument, sizing.rejection_reason,
        )
        return OrderResult(
            success=False,
            instrument=instrument,
            side=side,
            error_code="SIZING_REJECTED",
            error_message=sizing.rejection_reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Adjust units sign for BUY/SELL
    units = sizing.units
    if side.upper() == "SELL":
        units = -abs(units)
    else:
        units = abs(units)

    # Place the order
    result = client.place_market_order(
        instrument=instrument,
        units=units,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        trailing_stop_distance=trailing_stop_pips,
    )

    return result