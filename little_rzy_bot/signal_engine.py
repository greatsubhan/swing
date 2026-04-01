"""Bar-by-bar signal generation engine."""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import pandas as pd

from .config import EngineConfig
from .data_models import BollingerContext, Signal, StructureInfo, TrendlinePoint
from .indicators import adx, atr, bollinger, ema
from .pivots import detect_pivot_highs, detect_pivot_lows
from .scoring import grade, score_setup
from .structure_detection import detect_candidate
from .trend_detection import detect_trend_state

logger = logging.getLogger(__name__)


class SignalEngine:
    def __init__(self, config: EngineConfig):
        self.config = config

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["atr"] = atr(out, self.config.indicator.atr_length)
        out[["bb_mid", "bb_upper", "bb_lower"]] = bollinger(
            out, self.config.indicator.bb_length, self.config.indicator.bb_stddev
        )
        out["ema_fast"] = ema(out, self.config.indicator.ema_fast)
        out["ema_slow"] = ema(out, self.config.indicator.ema_slow)
        out["ema_slow_slope"] = out["ema_slow"].diff()
        out["adx"] = adx(out, self.config.indicator.adx_length)
        return out

    def run(self, df: pd.DataFrame, symbol: str, asset_class: str, timeframe: str, higher_timeframe: str) -> List[Signal]:
        df = self.prepare_features(df)
        ph = detect_pivot_highs(df, self.config.pivots.left_bars, self.config.pivots.right_bars)
        pl = detect_pivot_lows(df, self.config.pivots.left_bars, self.config.pivots.right_bars)
        signals: List[Signal] = []
        used_setups: set[Tuple[int, str]] = set()
        maturity_counter: Dict[str, int] = {"long": 0, "short": 0}

        for i in range(max(self.config.indicator.bb_length, self.config.indicator.atr_length), len(df)):
            row = df.iloc[i]
            ph_i = [p for p in ph if p[0] <= i - self.config.pivots.right_bars]
            pl_i = [p for p in pl if p[0] <= i - self.config.pivots.right_bars]
            trend_state = detect_trend_state(
                row,
                ph_i,
                pl_i,
                self.config.trend.min_hhhl_count,
                self.config.trend.min_ma_slope,
                self.config.trend.min_adx,
            )
            candidate = detect_candidate(df, i, trend_state, ph_i, pl_i, self.config)
            if not candidate:
                continue
            key = (candidate.anchor_index, candidate.side)
            if key in used_setups:
                logger.debug("Duplicate setup skipped at index=%s side=%s", i, candidate.side)
                continue

            entry_hit = row["low"] <= candidate.entry_trigger if candidate.side == "short" else row["high"] >= candidate.entry_trigger
            if not entry_hit:
                logger.debug("Candidate at index=%s not triggered", i)
                continue

            bb_bias = 1.0 if (candidate.side == "short" and row["close"] >= row["bb_mid"]) or (candidate.side == "long" and row["close"] <= row["bb_mid"]) else 0.4
            maturity_counter[candidate.side] += 1
            trend_maturity = maturity_counter[candidate.side]
            q_score = score_setup(trend_state, candidate.risk_reward, trend_maturity, bb_bias, self.config)

            structure = StructureInfo(
                impulse_start_index=candidate.impulse_start,
                impulse_end_index=candidate.impulse_end,
                pullback_start_index=candidate.pullback_start,
                pullback_end_index=candidate.pullback_end,
                anchor_low=float(df["low"].iloc[candidate.anchor_index]) if candidate.side == "short" else None,
                anchor_high=float(df["high"].iloc[candidate.anchor_index]) if candidate.side == "long" else None,
                trendline_points=[TrendlinePoint(index=candidate.pullback_start, price=float(df["high"].iloc[candidate.pullback_start] if candidate.side == "short" else df["low"].iloc[candidate.pullback_start])), TrendlinePoint(index=i, price=float(row["high"] if candidate.side == "short" else row["low"]))],
                measured_distance=abs(candidate.entry_trigger - candidate.target),
                projected_target=candidate.target,
            )
            boll_ctx = BollingerContext(
                bb_length=self.config.indicator.bb_length,
                bb_stddev=self.config.indicator.bb_stddev,
                price_vs_mid="below" if row["close"] < row["bb_mid"] else "above",
                pullback_band_location="near_upper_band" if candidate.side == "short" else "near_lower_band",
                extension_state="moderately_stretched" if abs(row["close"] - row["bb_mid"]) > row["atr"] else "normal",
            )
            signal = Signal(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                higher_timeframe=higher_timeframe,
                signal_type=candidate.side,
                strategy=self.config.strategy_name,
                trend_state=trend_state,
                setup_status="triggered",
                timestamp=str(df.index[i]),
                entry=candidate.entry_trigger,
                stop_loss=candidate.stop,
                target_1=candidate.target,
                target_2=None,
                invalidation_level=candidate.stop,
                risk_reward=round(candidate.risk_reward, 2),
                structure=structure,
                bollinger_context=boll_ctx,
                quality_score=q_score,
                quality_grade=grade(q_score),
                trend_maturity=trend_maturity,
                alerts=["fresh_trend_structure", "pullback_rejected_at_trendline", "good_bb_context"],
                reason_summary=f"{trend_state.title()} trend. Valid {candidate.side} Little RZY with measured move target.",
                setup_id=f"{symbol}-{timeframe}-{candidate.side}-{candidate.anchor_index}",
            )
            signals.append(signal)
            used_setups.add(key)
        return signals
