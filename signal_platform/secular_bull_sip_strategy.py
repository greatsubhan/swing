"""Strategy #5 adapter for the Secular Bull SIP monthly board."""
from __future__ import annotations

from .models import PlatformSignal, ScanResult
from .strategies import StrategyPlugin, StrategyScanRequest
from strategy_five_bot.scanner import run_live_cycle, save_scan_outputs
from strategy_five_bot.watchlists import resolve_watchlist


class SecularBullSipStrategy(StrategyPlugin):
    strategy_id = "strategy_five"
    strategy_name = "Secular Bull SIP"
    default_watchlist = "full-classic"
    managed_events = True

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        symbols = resolve_watchlist(request.watchlist)
        rows, events, state = run_live_cycle(
            symbols=symbols,
            watchlist=request.watchlist,
            environment=request.environment,
            token=request.token,
            price=request.price,
            output_dir=request.output_dir,
        )
        save_scan_outputs(request.output_dir, rows, events, state)
        signals: list[PlatformSignal] = []
        for latest in events:
            signals.append(
                PlatformSignal(
                    strategy_id=self.strategy_id,
                    strategy_name=self.strategy_name,
                    symbol=str(latest["symbol"]),
                    asset_class=str(latest["asset_class"]),
                    timeframe=str(latest["timeframe"]),
                    side=str(latest["signal_type"]),
                    timestamp=str(latest["timestamp"]),
                    setup_id=str(latest["setup_id"]),
                    summary=str(latest["reason_summary"]),
                    alert_text=str(latest["reason_summary"]),
                    quality_score=None,
                    quality_grade=None,
                    risk_reward=None,
                    entry=None,
                    stop_loss=None,
                    target_1=None,
                    raw_signal=latest,
                )
            )
        return ScanResult(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            watchlist=request.watchlist,
            signals=signals,
            rows=rows,
        )
