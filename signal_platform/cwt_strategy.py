"""Strategy #4 adapter for CWT / Cambist with Trend."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import PlatformSignal, ScanResult
from .strategies import StrategyPlugin, StrategyScanRequest
from strategy_four_bot.scanner import fwm_config_from_extra, quality_layer_from_extra, run_live_cycle, save_scan_outputs
from strategy_four_bot.watchlists import resolve_watchlist


class CwtStrategy(StrategyPlugin):
    strategy_id = "strategy_four"
    strategy_name = "Cambist With Trend"
    default_watchlist = "core-mixed"

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        symbols = resolve_watchlist(request.watchlist)
        catch_up_since = (
            datetime.now(timezone.utc) - timedelta(hours=float(request.catch_up_hours))
            if request.catch_up_hours
            else None
        )
        quality_layer = quality_layer_from_extra(request.extra)
        fwm_config = fwm_config_from_extra(request.extra)
        rows, events, state = run_live_cycle(
            symbols=symbols,
            environment=request.environment,
            token=request.token,
            price=request.price,
            output_dir=request.output_dir,
            quality_layer=quality_layer,
            fwm_config=fwm_config,
            catch_up_since=catch_up_since,
        )
        save_scan_outputs(request.output_dir, rows, events, state)
        signals: list[PlatformSignal] = []
        current_setup_ids = {str(row["latest_signal"]["setup_id"]) for row in rows if row.get("latest_signal")}
        for latest in events:
            delivery_kind = "fresh" if str(latest["setup_id"]) in current_setup_ids else "catch_up"
            latest = {**latest, "delivery_kind": delivery_kind}
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
