"""Batch research runner for Little RZY."""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

from .config import EngineConfig
from .market_data import fetch_oanda_ohlcv, fetch_yahoo_ohlcv
from .profiles import apply_market_profile
from .workflows import run_backtest


def _read_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def _apply_config_overrides(base: EngineConfig, payload: dict[str, Any]) -> EngineConfig:
    costs = payload.get("costs", {})
    constraints = payload.get("constraints", {})
    htf = payload.get("htf_bias", {})
    indicator = payload.get("indicator", {})
    trend = payload.get("trend", {})
    structure = payload.get("structure", {})
    risk = payload.get("risk", {})
    execution = payload.get("execution", {})

    if indicator:
        base.indicator = replace(base.indicator, **indicator)
    if trend:
        base.trend = replace(base.trend, **trend)
    if structure:
        base.structure = replace(base.structure, **structure)
    if risk:
        base.risk = replace(base.risk, **risk)
    if execution:
        base.execution = replace(base.execution, **execution)

    base.risk.commission_per_trade = float(costs.get("commission_per_trade", base.risk.commission_per_trade))
    base.risk.spread_points = float(costs.get("spread_points", base.risk.spread_points))
    base.risk.slippage_points = float(costs.get("slippage_points", base.risk.slippage_points))

    base.portfolio.max_open_risk = constraints.get("max_open_risk", base.portfolio.max_open_risk)
    base.portfolio.max_trades_per_day = constraints.get("max_trades_per_day", base.portfolio.max_trades_per_day)
    base.portfolio.max_trades_per_symbol_per_day = constraints.get(
        "max_trades_per_symbol_per_day", base.portfolio.max_trades_per_symbol_per_day
    )
    base.portfolio.max_daily_drawdown = constraints.get("max_daily_drawdown", base.portfolio.max_daily_drawdown)
    base.portfolio.allow_partial_size = bool(constraints.get("allow_partial_size", base.portfolio.allow_partial_size))

    if htf:
        base.execution.use_htf_bias = bool(htf.get("enabled", False))
        base.execution.htf_granularity = str(htf.get("granularity", base.execution.htf_granularity))
        base.require_higher_timeframe_confirmation = base.execution.use_htf_bias

    return base


def _fetch_data(provider: str, symbol: str, start: str, end: str, granularity: str, interval: str, oanda_env: str):
    if provider == "yahoo":
        return fetch_yahoo_ohlcv(symbol=symbol, interval=interval, start=start, end=end)
    return fetch_oanda_ohlcv(
        instrument=symbol,
        granularity=granularity,
        start=start,
        end=end,
        environment=oanda_env,
        price="M",
    )


def run_research_config(config_path: str | Path) -> dict[str, Any]:
    payload = _read_config(config_path)
    out_dir = Path(payload.get("output_dir", "output/research/little_rzy"))
    out_dir.mkdir(parents=True, exist_ok=True)

    provider = str(payload.get("provider", "oanda"))
    granularity = str(payload.get("granularity", "H4"))
    timeframe = str(payload.get("timeframe", "4h"))
    higher_timeframe = str(payload.get("higher_timeframe", "1d"))
    interval = str(payload.get("interval", "1h"))
    use_market_profile = bool(payload.get("use_market_profile", True))
    symbols = list(payload.get("symbols", []))
    segments = list(payload.get("segments", []))
    oanda_env = str(payload.get("oanda_environment", "practice"))

    aggregate_rows: list[dict[str, Any]] = []

    for segment in segments:
        segment_name = str(segment["name"])
        segment_start = str(segment["start"])
        segment_end = str(segment["end"])
        segment_dir = out_dir / segment_name
        segment_dir.mkdir(parents=True, exist_ok=True)

        segment_rows: list[dict[str, Any]] = []
        for symbol in symbols:
            cfg = _apply_config_overrides(EngineConfig(), payload)
            fetched = _fetch_data(provider, symbol, segment_start, segment_end, granularity, interval, oanda_env)
            signals, trade_log, summary, diagnostics = run_backtest(
                fetched.df,
                symbol=fetched.symbol,
                asset_class=fetched.asset_class,
                timeframe=timeframe,
                higher_timeframe=cfg.execution.htf_granularity if cfg.execution.use_htf_bias else higher_timeframe,
                config=cfg,
                use_market_profile=use_market_profile,
            )
            effective_cfg = (
                apply_market_profile(cfg, symbol, timeframe=timeframe, variant="1h" if timeframe.lower() == "1h" else "4h")
                if use_market_profile
                else cfg
            )

            trade_csv_path = segment_dir / f"{symbol}_{timeframe}_trades.csv"
            trade_log.to_csv(trade_csv_path, index=False)

            row = {
                "segment": segment_name,
                "start": segment_start,
                "end": segment_end,
                "symbol": symbol,
                "timeframe": timeframe,
                "profile_name": effective_cfg.profile_name,
                "trades": summary.trades,
                "win_rate": summary.win_rate,
                "avg_r": summary.avg_r,
                "expectancy_r": summary.expectancy_r,
                "profit_factor": summary.profit_factor,
                "max_drawdown_r": summary.max_drawdown_r,
                "max_drawdown_currency": summary.max_drawdown_currency,
                "total_net_pnl": summary.total_net_pnl,
                "total_commission": summary.total_commission,
                "skipped_trades": summary.skipped_trades,
                "partial_size_trades": summary.partial_size_trades,
                "signals": len(signals),
                "trade_csv": str(trade_csv_path),
                "diagnostics": json.dumps(asdict(diagnostics)),
            }
            segment_rows.append(row)
            aggregate_rows.append(row)

        pd.DataFrame(segment_rows).to_csv(segment_dir / "segment_metrics.csv", index=False)

    aggregate_df = pd.DataFrame(aggregate_rows)
    if not aggregate_df.empty:
        aggregate_df.to_csv(out_dir / "aggregate_metrics.csv", index=False)
        grouped = (
            aggregate_df.groupby(["symbol", "timeframe"], dropna=False)
            .agg(
                segments=("segment", "count"),
                trades=("trades", "sum"),
                win_rate=("win_rate", "mean"),
                avg_r=("avg_r", "mean"),
                expectancy_r=("expectancy_r", "mean"),
                profit_factor=("profit_factor", "mean"),
                max_drawdown_r=("max_drawdown_r", "mean"),
                max_drawdown_currency=("max_drawdown_currency", "mean"),
                total_net_pnl=("total_net_pnl", "sum"),
                skipped_trades=("skipped_trades", "sum"),
            )
            .reset_index()
        )
        grouped.to_csv(out_dir / "aggregate_summary.csv", index=False)

    return {
        "config_path": str(config_path),
        "output_dir": str(out_dir),
        "segments": len(segments),
        "symbols": symbols,
        "rows": aggregate_rows,
    }
