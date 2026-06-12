"""Bar-by-bar signal generation engine."""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import pandas as pd

from .config import EngineConfig
from .data_models import BollingerContext, Signal, StructureInfo, TrendlinePoint
from .filters import primary_session
from .indicators import adx, atr, bollinger, ema
from .pivots import detect_pivot_highs, detect_pivot_lows
from .scoring import grade, score_setup
from .structure_detection import detect_candidate
from .trendline import line_from_points, line_value
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

    def _compute_trend_states(self, df: pd.DataFrame) -> pd.Series:
        ph = detect_pivot_highs(df, self.config.pivots.left_bars, self.config.pivots.right_bars)
        pl = detect_pivot_lows(df, self.config.pivots.left_bars, self.config.pivots.right_bars)
        states: List[str] = []

        for i in range(len(df)):
            row = df.iloc[i]
            ph_i = [p for p in ph if p[0] <= i - self.config.pivots.right_bars]
            pl_i = [p for p in pl if p[0] <= i - self.config.pivots.right_bars]
            states.append(
                detect_trend_state(
                    row,
                    ph_i,
                    pl_i,
                    self.config.trend.min_hhhl_count,
                    self.config.trend.min_ma_slope,
                    self.config.trend.min_adx,
                )
            )

        return pd.Series(states, index=df.index, dtype="object")

    def _resample_ohlcv(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        freq_map = {
            "5m": "5min",
            "m5": "5min",
            "15m": "15min",
            "m15": "15min",
            "30m": "30min",
            "m30": "30min",
            "1h": "1h",
            "h1": "1h",
            "4h": "4h",
            "h4": "4h",
            "1d": "1D",
            "d": "1D",
            "1w": "1W",
            "w": "1W",
        }
        rule = freq_map.get(timeframe.lower())
        if rule is None:
            raise ValueError(f"Unsupported higher timeframe: {timeframe}")

        return (
            df.resample(rule, label="right", closed="right")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

    def _build_higher_timeframe_states(self, df: pd.DataFrame, higher_timeframe: str) -> pd.Series:
        htf_ohlcv = self._resample_ohlcv(df[["open", "high", "low", "close", "volume"]], higher_timeframe)
        if htf_ohlcv.empty:
            return pd.Series(["sideways"] * len(df), index=df.index, dtype="object")

        htf_featured = self.prepare_features(htf_ohlcv)
        htf_states = self._compute_trend_states(htf_featured).shift(1)
        return htf_states.reindex(df.index, method="ffill").fillna("sideways")

    def _has_rejection_candle(self, df: pd.DataFrame, trigger_index: int, candidate) -> bool:
        if trigger_index <= 0:
            return False

        rejection_index = trigger_index - 1
        rejection_bar = df.iloc[rejection_index]
        slope, intercept = line_from_points(
            (candidate.trendline_start_index, candidate.trendline_start_price),
            (candidate.trendline_end_index, candidate.trendline_end_price),
        )
        trendline_at_rejection = line_value(slope, intercept, rejection_index)
        tolerance = candidate.trendline_tolerance

        if candidate.side == "short":
            touched = float(rejection_bar["high"]) >= trendline_at_rejection - tolerance
            rejected = float(rejection_bar["close"]) < float(rejection_bar["open"]) and float(rejection_bar["close"]) < trendline_at_rejection
            return touched and rejected

        touched = float(rejection_bar["low"]) <= trendline_at_rejection + tolerance
        rejected = float(rejection_bar["close"]) > float(rejection_bar["open"]) and float(rejection_bar["close"]) > trendline_at_rejection
        return touched and rejected

    def run(self, df: pd.DataFrame, symbol: str, asset_class: str, timeframe: str, higher_timeframe: str) -> List[Signal]:
        df = self.prepare_features(df)
        trend_states = self._compute_trend_states(df)
        htf_states = (
            self._build_higher_timeframe_states(df, higher_timeframe)
            if higher_timeframe
            else pd.Series(["sideways"] * len(df), index=df.index, dtype="object")
        )
        ph = detect_pivot_highs(df, self.config.pivots.left_bars, self.config.pivots.right_bars)
        pl = detect_pivot_lows(df, self.config.pivots.left_bars, self.config.pivots.right_bars)
        signals: List[Signal] = []
        used_setups: set[Tuple[int, str]] = set()
        maturity_counter: Dict[str, int] = {"long": 0, "short": 0}
        active_trend_run: str | None = None

        for i in range(max(self.config.indicator.bb_length, self.config.indicator.atr_length), len(df)):
            row = df.iloc[i]
            ph_i = [p for p in ph if p[0] <= i - self.config.pivots.right_bars]
            pl_i = [p for p in pl if p[0] <= i - self.config.pivots.right_bars]
            trend_state = str(trend_states.iloc[i])
            higher_trend_state = str(htf_states.iloc[i]) if self.config.require_higher_timeframe_confirmation else trend_state

            if trend_state != active_trend_run:
                maturity_counter = {"long": 0, "short": 0}
                active_trend_run = None if trend_state == "sideways" else trend_state

            if self.config.require_higher_timeframe_confirmation:
                if trend_state == "sideways" or higher_trend_state == "sideways" or trend_state != higher_trend_state:
                    continue

            candidate = detect_candidate(df, i, trend_state, ph_i, pl_i, self.config)
            if not candidate:
                continue
            key = (candidate.anchor_index, candidate.side)
            if key in used_setups:
                logger.debug("Duplicate setup skipped at index=%s side=%s", i, candidate.side)
                continue

            next_maturity = maturity_counter[candidate.side] + 1
            if next_maturity > self.config.trend.max_trend_maturity:
                logger.debug("Candidate at index=%s skipped due to maturity=%s", i, next_maturity)
                continue

            if self.config.require_rejection_candle and not self._has_rejection_candle(df, i, candidate):
                logger.debug("Candidate at index=%s skipped due to missing rejection candle", i)
                continue

            entry_hit = row["low"] <= candidate.entry_trigger if candidate.side == "short" else row["high"] >= candidate.entry_trigger
            if not entry_hit:
                logger.debug("Candidate at index=%s not triggered", i)
                continue

            if candidate.side == "short":
                bb_bias = 1.0 if row["high"] >= row["bb_upper"] else 0.75 if row["high"] >= row["bb_mid"] else 0.35
            else:
                bb_bias = 1.0 if row["low"] <= row["bb_lower"] else 0.75 if row["low"] <= row["bb_mid"] else 0.35
            maturity_counter[candidate.side] = next_maturity
            trend_maturity = next_maturity
            q_score = score_setup(trend_state, candidate.risk_reward, trend_maturity, bb_bias, self.config)

            structure = StructureInfo(
                impulse_start_index=candidate.impulse_start,
                impulse_end_index=candidate.impulse_end,
                pullback_start_index=candidate.pullback_start,
                pullback_end_index=candidate.pullback_end,
                anchor_low=float(df["low"].iloc[candidate.anchor_index]) if candidate.side == "short" else None,
                anchor_high=float(df["high"].iloc[candidate.anchor_index]) if candidate.side == "long" else None,
                trendline_points=[
                    TrendlinePoint(index=candidate.trendline_start_index, price=candidate.trendline_start_price),
                    TrendlinePoint(index=candidate.trendline_end_index, price=candidate.trendline_end_price),
                ],
                trendline_tolerance=candidate.trendline_tolerance,
                measured_distance=candidate.measured_distance,
                projected_target=candidate.target,
            )
            boll_ctx = BollingerContext(
                bb_length=self.config.indicator.bb_length,
                bb_stddev=self.config.indicator.bb_stddev,
                price_vs_mid="below" if row["close"] < row["bb_mid"] else "above",
                pullback_band_location="near_upper_band" if candidate.side == "short" else "near_lower_band",
                extension_state="moderately_stretched" if abs(row["close"] - row["bb_mid"]) > row["atr"] else "normal",
            )
            atr_at_entry = float(row["atr"])
            bar_range_at_entry = float(row["high"] - row["low"])
            rolling_atr = df["atr"].iloc[max(0, i - 19) : i + 1].median()
            volatility_regime = "normal"
            if rolling_atr and not pd.isna(rolling_atr):
                if atr_at_entry < rolling_atr * 0.8:
                    volatility_regime = "compressed"
                elif atr_at_entry > rolling_atr * 1.2:
                    volatility_regime = "expanded"
            structure_tag = (
                "bullish_hh_hl_continuation"
                if candidate.side == "long"
                else "bearish_ll_lh_continuation"
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
                invalidation_level=candidate.invalidation_level,
                risk_reward=round(candidate.risk_reward, 2),
                structure=structure,
                bollinger_context=boll_ctx,
                quality_score=q_score,
                quality_grade=grade(q_score),
                trend_maturity=trend_maturity,
                alerts=["fresh_trend_structure", "pullback_rejected_at_trendline", "good_bb_context"],
                reason_summary=f"{trend_state.title()} trend. {candidate.validity_reason} with measured move target.",
                setup_id=f"{symbol}-{timeframe}-{candidate.side}-{candidate.anchor_index}",
                profile_name=self.config.profile_name,
                atr_at_entry=atr_at_entry,
                bar_range_at_entry=bar_range_at_entry,
                retrace_pct=round(candidate.retrace_pct, 4),
                impulse_atr_multiple=round(candidate.impulse_atr_multiple, 4),
                volatility_regime=volatility_regime,
                session=primary_session(str(df.index[i])),
                structure_tag=structure_tag,
                higher_timeframe_bias=higher_trend_state,
            )
            signals.append(signal)
            used_setups.add(key)
        return signals
