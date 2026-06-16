"""End-to-end backtest workflows for Little RZY."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .backtest_adapter import simulate_signals, to_trade_log_df
from .config import EngineConfig
from .data_interface import load_ohlcv_csv
from .filters import filter_signals
from .profiles import apply_market_profile
from .reporting import summarize
from .signal_engine import SignalEngine


def make_synthetic_ohlcv(rows: int = 800, seed: int = 7) -> pd.DataFrame:
    """Generate deterministic synthetic OHLCV for smoke-testing the pipeline."""
    rng = np.random.default_rng(seed)
    dt = pd.date_range("2023-01-01", periods=rows, freq="4h")
    trend = np.linspace(0, 45, rows)
    cyc = 4 * np.sin(np.arange(rows) / 14.0)
    noise = rng.normal(0, 1.2, rows).cumsum() * 0.12
    close = 100 + trend + cyc + noise
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + np.abs(rng.normal(0.5, 0.35, rows))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.5, 0.35, rows))
    volume = rng.integers(900, 2200, rows)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dt,
    )


def run_backtest(
    df: pd.DataFrame,
    symbol: str = "SYNTH",
    asset_class: str = "synthetic",
    timeframe: str = "4h",
    higher_timeframe: str = "1d",
    config: Optional[EngineConfig] = None,
    use_market_profile: bool = True,
):
    """Run full signal->trade->summary pipeline and return artifacts."""
    cfg = config or EngineConfig()
    if use_market_profile:
        variant = "1h" if timeframe.lower() == "1h" else "4h"
        cfg = apply_market_profile(cfg, symbol, timeframe=timeframe, variant=variant)
    engine = SignalEngine(cfg)
    signals = engine.run(df, symbol, asset_class, timeframe, higher_timeframe)
    signals, filtered_signals = filter_signals(signals, cfg)
    trades, diagnostics = simulate_signals(df, signals, cfg)
    diagnostics.skipped_filters = len(filtered_signals)
    trade_log = to_trade_log_df(trades)
    summary = summarize(trade_log, diagnostics)
    return signals, trade_log, summary, diagnostics


def run_backtest_from_csv(csv_path: str | Path, timestamp_col: str = "timestamp"):
    df = load_ohlcv_csv(csv_path, timestamp_col=timestamp_col)
    return run_backtest(df)


def save_backtest_outputs(
    output_dir: str | Path,
    trade_log: pd.DataFrame,
    summary,
    diagnostics=None,
    signals=None,
    export_trades_csv: str | Path | None = None,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    trade_log.to_csv(out / "trade_log.csv", index=False)
    if export_trades_csv:
        export_path = Path(export_trades_csv)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        trade_log.to_csv(export_path, index=False)
    pd.DataFrame([asdict(summary)]).to_json(out / "summary.json", orient="records", indent=2)
    if diagnostics is not None:
        (out / "diagnostics.json").write_text(json.dumps(asdict(diagnostics), indent=2))
    if signals is not None:
        (out / "signals.json").write_text(json.dumps([signal.to_dict() for signal in signals], indent=2))
