"""Live signal scanning helpers."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .alerts import concise_alert
from .config import EngineConfig
from .filters import filter_signals
from .market_data import fetch_oanda_ohlcv
from .profiles import apply_market_profile
from .signal_engine import SignalEngine


def infer_asset_class(symbol: str) -> str:
    upper = symbol.upper()
    if upper in {"WTICO_USD", "BCO_USD"}:
        return "energy"
    if upper in {"XAU_USD", "XAG_USD"}:
        return "metals"
    if upper in {"UK100_GBP", "NAS100_USD", "US30_USD", "SPX500_USD", "FR40_EUR", "JP225_USD"}:
        return "indices"
    if "_" in upper:
        return "forex"
    return "unknown"


def _append_signal_log(path: str | Path | None, rows: list[dict]) -> None:
    if not path or not rows:
        return
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def scan_oanda_symbols(
    symbols: Iterable[str],
    granularity: str = "H4",
    higher_timeframe: str = "1d",
    environment: str = "practice",
    token: str | None = None,
    price: str = "M",
    use_market_profile: bool = True,
    base_config: EngineConfig | None = None,
    variant: str = "4h",
    log_signals: bool = False,
    log_filtered_setups: bool = False,
    signal_log_file: str | Path | None = None,
    filtered_log_file: str | Path | None = None,
    catch_up_since: datetime | None = None,
) -> list[dict]:
    results: list[dict] = []
    timeframe_label = {"H4": "4h", "H1": "1h", "M15": "15m", "M5": "5m"}.get(granularity, granularity.lower())
    signal_log_rows: list[dict] = []
    filtered_log_rows: list[dict] = []

    for symbol in symbols:
        fetched = fetch_oanda_ohlcv(
            instrument=symbol,
            granularity=granularity,
            start=None,
            end=None,
            price=price,
            token=token,
            environment=environment,
        )
        cfg = replace(base_config) if base_config is not None else EngineConfig()
        if use_market_profile:
            cfg = apply_market_profile(cfg, symbol, timeframe=timeframe_label, variant=variant)
        if cfg.execution.use_htf_bias and cfg.execution.htf_granularity:
            effective_higher_timeframe = cfg.execution.htf_granularity
        else:
            effective_higher_timeframe = higher_timeframe

        engine = SignalEngine(cfg)
        signals = engine.run(
            fetched.df,
            symbol=symbol,
            asset_class=infer_asset_class(symbol),
            timeframe=timeframe_label,
            higher_timeframe=effective_higher_timeframe,
        )
        passed_signals, filtered_signals = filter_signals(signals, cfg)

        latest_bar_timestamp = fetched.df.index[-1].isoformat() if not fetched.df.empty else None
        current_bar_signals = [signal for signal in passed_signals if signal.timestamp == latest_bar_timestamp]
        recent_signals = []
        if catch_up_since is not None:
            for signal in passed_signals:
                signal_timestamp = datetime.fromisoformat(str(signal.timestamp).replace("Z", "+00:00"))
                if signal_timestamp >= catch_up_since:
                    recent_signals.append(signal)
        latest_signal = current_bar_signals[-1] if current_bar_signals else None
        results.append(
            {
                "symbol": symbol,
                "signal_count": len(passed_signals),
                "filtered_signal_count": len(filtered_signals),
                "current_bar_signal_count": len(current_bar_signals),
                "latest_signal": latest_signal.to_dict() if latest_signal else None,
                "recent_signals": [signal.to_dict() for signal in recent_signals],
                "alert": concise_alert(latest_signal) if latest_signal else None,
                "filtered_setups": [
                    {
                        "setup_id": signal.setup_id,
                        "timestamp": signal.timestamp,
                        "reasons": reasons,
                    }
                    for signal, reasons in filtered_signals
                ],
            }
        )

        if log_signals:
            for signal in passed_signals:
                signal_log_rows.append(
                    {
                        "strategy": cfg.strategy_name,
                        "profile_name": signal.profile_name,
                        "symbol": signal.symbol,
                        "timeframe": signal.timeframe,
                        "direction": signal.signal_type,
                        "timestamp": signal.timestamp,
                        "setup_id": signal.setup_id,
                        "entry": signal.entry,
                        "stop_loss": signal.stop_loss,
                        "target_1": signal.target_1,
                        "risk_reward": signal.risk_reward,
                        "atr": signal.atr_at_entry,
                        "retrace_pct": signal.retrace_pct,
                        "impulse_atr_multiple": signal.impulse_atr_multiple,
                        "session": signal.session,
                        "volatility_regime": signal.volatility_regime,
                        "structure_tag": signal.structure_tag,
                        "higher_timeframe_bias": signal.higher_timeframe_bias,
                    }
                )

        if log_filtered_setups:
            for signal, reasons in filtered_signals:
                filtered_log_rows.append(
                    {
                        "strategy": cfg.strategy_name,
                        "profile_name": signal.profile_name,
                        "symbol": signal.symbol,
                        "timeframe": signal.timeframe,
                        "direction": signal.signal_type,
                        "timestamp": signal.timestamp,
                        "setup_id": signal.setup_id,
                        "reason": "|".join(reasons),
                        "entry": signal.entry,
                        "stop_loss": signal.stop_loss,
                        "target_1": signal.target_1,
                        "risk_reward": signal.risk_reward,
                        "atr": signal.atr_at_entry,
                        "session": signal.session,
                        "volatility_regime": signal.volatility_regime,
                    }
                )

    _append_signal_log(signal_log_file, signal_log_rows)
    _append_signal_log(filtered_log_file, filtered_log_rows)
    return results


def save_scan_outputs(output_dir: str | Path, results: list[dict]) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scan_results.json").write_text(json.dumps(results, indent=2))
    alerts = [row["alert"] for row in results if row["alert"]]
    (out / "alerts.txt").write_text("\n".join(alerts))
