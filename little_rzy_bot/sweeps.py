"""Parameter sweep utilities."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
from typing import Iterable, List

import pandas as pd

from .config import EngineConfig
from .signal_engine import SignalEngine
from .backtest_adapter import simulate_signals, to_trade_log_df
from .reporting import summarize


def run_simple_sweep(
    df: pd.DataFrame,
    base_cfg: EngineConfig,
    impulse_atr_values: Iterable[float],
    min_rr_values: Iterable[float],
    symbol: str,
    asset_class: str,
    timeframe: str,
    higher_timeframe: str,
) -> List[dict]:
    rows: List[dict] = []
    for imp, rr in product(impulse_atr_values, min_rr_values):
        cfg = replace(base_cfg)
        cfg.structure = replace(base_cfg.structure, min_impulse_atr=imp)
        cfg.risk = replace(base_cfg.risk, min_rr=rr)
        engine = SignalEngine(cfg)
        signals = engine.run(df, symbol, asset_class, timeframe, higher_timeframe)
        trades = to_trade_log_df(simulate_signals(df, signals, cfg))
        summary = summarize(trades)
        rows.append(
            {
                "min_impulse_atr": imp,
                "min_rr": rr,
                "trades": summary.trades,
                "win_rate": summary.win_rate,
                "expectancy_r": summary.expectancy_r,
                "profit_factor": summary.profit_factor,
            }
        )
    return rows
