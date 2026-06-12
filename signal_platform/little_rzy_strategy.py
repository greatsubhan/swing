"""Measured Drift adapter for the multi-strategy platform."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import PlatformSignal, ScanResult
from .strategies import StrategyPlugin, StrategyScanRequest
from little_rzy_bot.config import EngineConfig
from little_rzy_bot.scanner import save_scan_outputs, scan_oanda_symbols
from little_rzy_bot.watchlists import resolve_watchlist


class LittleRzyStrategy(StrategyPlugin):
    strategy_id = "little_rzy"
    strategy_name = "Measured Drift"
    default_watchlist = "primary-4h"

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        symbols = resolve_watchlist(request.watchlist)
        catch_up_since = (
            datetime.now(timezone.utc) - timedelta(hours=float(request.catch_up_hours))
            if request.catch_up_hours
            else None
        )
        rows = scan_oanda_symbols(
            symbols=symbols,
            granularity=request.granularity,
            higher_timeframe=request.higher_timeframe,
            environment=request.environment,
            token=request.token,
            price=request.price,
            use_market_profile=request.use_market_profile,
            base_config=EngineConfig(),
            variant="4h",
            log_signals=request.log_signals,
            log_filtered_setups=request.log_filtered_setups,
            signal_log_file=request.signal_log_file,
            filtered_log_file=request.filtered_log_file,
            catch_up_since=catch_up_since,
        )
        save_scan_outputs(request.output_dir, rows)
        signals: list[PlatformSignal] = []
        seen_setup_ids: set[str] = set()
        for row in rows:
            latest = row.get("latest_signal")
            if not latest:
                latest = None
            if latest:
                latest = {**latest, "delivery_kind": "fresh"}
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
                seen_setup_ids.add(str(latest["setup_id"]))
            for recent in row.get("recent_signals", []):
                setup_id = str(recent["setup_id"])
                if setup_id in seen_setup_ids:
                    continue
                recent = {**recent, "delivery_kind": "catch_up"}
                signals.append(
                    PlatformSignal(
                        strategy_id=self.strategy_id,
                        strategy_name=self.strategy_name,
                        symbol=str(recent["symbol"]),
                        asset_class=str(recent["asset_class"]),
                        timeframe=str(recent["timeframe"]),
                        side=str(recent["signal_type"]),
                        timestamp=str(recent["timestamp"]),
                        setup_id=setup_id,
                        summary=str(recent["reason_summary"]),
                        alert_text=str(recent["reason_summary"]),
                        quality_score=int(recent["quality_score"]),
                        quality_grade=str(recent["quality_grade"]),
                        risk_reward=float(recent["risk_reward"]),
                        entry=float(recent["entry"]),
                        stop_loss=float(recent["stop_loss"]),
                        target_1=float(recent["target_1"]),
                        raw_signal=recent,
                    )
                )
                seen_setup_ids.add(setup_id)
        return ScanResult(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            watchlist=request.watchlist,
            signals=signals,
            rows=rows,
        )


class LittleRzy1HStrategy(StrategyPlugin):
    strategy_id = "little_rzy_1h"
    strategy_name = "Measured Drift 1H"
    default_watchlist = "research-1h"

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        symbols = resolve_watchlist(request.watchlist)
        cfg = EngineConfig()
        cfg.execution.use_htf_bias = True
        cfg.execution.htf_granularity = request.higher_timeframe or "H4"
        cfg.require_higher_timeframe_confirmation = True
        catch_up_since = (
            datetime.now(timezone.utc) - timedelta(hours=float(request.catch_up_hours))
            if request.catch_up_hours
            else None
        )
        rows = scan_oanda_symbols(
            symbols=symbols,
            granularity=request.granularity,
            higher_timeframe=request.higher_timeframe,
            environment=request.environment,
            token=request.token,
            price=request.price,
            use_market_profile=request.use_market_profile,
            base_config=cfg,
            variant="1h",
            log_signals=request.log_signals,
            log_filtered_setups=request.log_filtered_setups,
            signal_log_file=request.signal_log_file,
            filtered_log_file=request.filtered_log_file,
            catch_up_since=catch_up_since,
        )
        save_scan_outputs(request.output_dir, rows)
        signals: list[PlatformSignal] = []
        seen_setup_ids: set[str] = set()
        for row in rows:
            latest = row.get("latest_signal")
            if latest:
                latest = {**latest, "delivery_kind": "fresh"}
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
                seen_setup_ids.add(str(latest["setup_id"]))
            for recent in row.get("recent_signals", []):
                setup_id = str(recent["setup_id"])
                if setup_id in seen_setup_ids:
                    continue
                recent = {**recent, "delivery_kind": "catch_up"}
                signals.append(
                    PlatformSignal(
                        strategy_id=self.strategy_id,
                        strategy_name=self.strategy_name,
                        symbol=str(recent["symbol"]),
                        asset_class=str(recent["asset_class"]),
                        timeframe=str(recent["timeframe"]),
                        side=str(recent["signal_type"]),
                        timestamp=str(recent["timestamp"]),
                        setup_id=setup_id,
                        summary=str(recent["reason_summary"]),
                        alert_text=str(recent["reason_summary"]),
                        quality_score=int(recent["quality_score"]),
                        quality_grade=str(recent["quality_grade"]),
                        risk_reward=float(recent["risk_reward"]),
                        entry=float(recent["entry"]),
                        stop_loss=float(recent["stop_loss"]),
                        target_1=float(recent["target_1"]),
                        raw_signal=recent,
                    )
                )
                seen_setup_ids.add(setup_id)
        return ScanResult(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            watchlist=request.watchlist,
            signals=signals,
            rows=rows,
        )
