"""Strategy #2 adapter for the multi-strategy platform."""
from __future__ import annotations

from .models import PlatformSignal, ScanResult
from .strategies import StrategyPlugin, StrategyScanRequest
from strategy_two_bot.scanner import save_scan_outputs, scan_oanda_symbols
from strategy_two_bot.watchlists import resolve_watchlist


class TrendCurrentStrategy(StrategyPlugin):
    strategy_id = "strategy_two"
    strategy_name = "Trend Current"
    default_watchlist = "core-4h"

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        symbols = resolve_watchlist(request.watchlist)
        rows = scan_oanda_symbols(
            symbols=symbols,
            granularity=request.granularity,
            higher_timeframe=request.higher_timeframe,
            environment=request.environment,
            token=request.token,
            price=request.price,
        )
        save_scan_outputs(request.output_dir, rows)
        signals: list[PlatformSignal] = []
        for row in rows:
            latest = row.get("latest_signal")
            if not latest:
                continue
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
                    alert_text=str(row.get("alert") or ""),
                    quality_score=int(latest["quality_score"]),
                    quality_grade=str(latest["quality_grade"]),
                    risk_reward=float(latest["risk_reward"]),
                    entry=float(latest["entry"]),
                    stop_loss=float(latest["stop_loss"]),
                    target_1=float(latest["target_1"]),
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
