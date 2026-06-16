"""Strategy #2 adapter for the multi-strategy platform."""
from __future__ import annotations

from .models import PlatformSignal, ScanResult
from .strategies import StrategyPlugin, StrategyScanRequest
from strategy_two_bot.scanner import run_live_cycle, save_scan_outputs
from strategy_two_bot.watchlists import resolve_watchlist


class TrendCurrentStrategy(StrategyPlugin):
    strategy_id = "strategy_two"
    strategy_name = "Trend Current"
    default_watchlist = "core-4h"
    managed_events = True

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        symbols = resolve_watchlist(request.watchlist)
        rows, events, state = run_live_cycle(
            symbols=symbols,
            granularity=request.granularity,
            higher_timeframe=request.higher_timeframe,
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
                    quality_score=int(latest["quality_score"]) if latest.get("quality_score") is not None else None,
                    quality_grade=str(latest["quality_grade"]) if latest.get("quality_grade") is not None else None,
                    risk_reward=float(latest["risk_reward"]) if latest.get("risk_reward") is not None else None,
                    entry=float(latest["entry"]) if latest.get("entry") is not None else None,
                    stop_loss=float(latest["stop_loss"]) if latest.get("stop_loss") is not None else None,
                    target_1=float(latest["target_1"]) if latest.get("target_1") is not None else None,
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
