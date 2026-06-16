from __future__ import annotations

import unittest

import pandas as pd

from little_rzy_bot.backtest_adapter import simulate_signals
from little_rzy_bot.config import EngineConfig
from little_rzy_bot.data_models import BollingerContext, Signal, StructureInfo, TrendlinePoint
from little_rzy_bot.filters import filter_signal


def make_signal(timestamp: str, setup_id: str = "s1") -> Signal:
    structure = StructureInfo(
        impulse_start_index=0,
        impulse_end_index=1,
        pullback_start_index=2,
        pullback_end_index=3,
        anchor_low=None,
        anchor_high=100.0,
        trendline_points=[TrendlinePoint(index=1, price=95.0), TrendlinePoint(index=3, price=97.0)],
        trendline_tolerance=0.1,
        measured_distance=10.0,
        projected_target=110.0,
    )
    bollinger = BollingerContext(
        bb_length=20,
        bb_stddev=2.0,
        price_vs_mid="above",
        pullback_band_location="near_lower_band",
        extension_state="normal",
    )
    return Signal(
        symbol="TEST",
        asset_class="test",
        timeframe="1h",
        higher_timeframe="4h",
        signal_type="long",
        strategy="Little RZY",
        trend_state="bullish",
        setup_status="triggered",
        timestamp=timestamp,
        entry=100.0,
        stop_loss=90.0,
        target_1=110.0,
        target_2=None,
        invalidation_level=95.0,
        risk_reward=1.0,
        structure=structure,
        bollinger_context=bollinger,
        quality_score=80,
        quality_grade="B",
        trend_maturity=1,
        alerts=[],
        reason_summary="test",
        setup_id=setup_id,
        profile_name="baseline",
        atr_at_entry=10.0,
        bar_range_at_entry=12.0,
        retrace_pct=0.4,
        impulse_atr_multiple=2.0,
        volatility_regime="normal",
        session="london",
        structure_tag="bullish_hh_hl_continuation",
        higher_timeframe_bias="bullish",
    )


class LittleRzyHardeningTests(unittest.TestCase):
    def test_costs_reduce_net_pnl_and_r(self) -> None:
        df = pd.DataFrame(
            [
                {"open": 100, "high": 101, "low": 99, "close": 100},
                {"open": 100, "high": 100.5, "low": 99.5, "close": 100.2},
                {"open": 100.2, "high": 111, "low": 100, "close": 110.5},
            ],
            index=pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"]
            ),
        )
        cfg = EngineConfig()
        cfg.risk.spread_points = 2.0
        cfg.risk.slippage_points = 0.0
        cfg.risk.commission_per_trade = 1.0

        trades, _ = simulate_signals(df, [make_signal("2026-01-01 00:00:00+00:00")], cfg)
        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertAlmostEqual(trade.entry_price, 101.0, places=6)
        self.assertAlmostEqual(trade.exit_price, 109.0, places=6)
        self.assertAlmostEqual(trade.gross_pnl, 8.0, places=6)
        self.assertAlmostEqual(trade.net_pnl, 7.0, places=6)
        self.assertAlmostEqual(trade.pnl_r, 7.0 / 11.0, places=4)

    def test_max_open_risk_can_partially_size_second_trade(self) -> None:
        df = pd.DataFrame(
            [
                {"open": 100, "high": 101, "low": 99, "close": 100},
                {"open": 100, "high": 101, "low": 99, "close": 100},
                {"open": 100, "high": 101, "low": 99, "close": 100},
                {"open": 100, "high": 112, "low": 99, "close": 111},
                {"open": 111, "high": 112, "low": 110, "close": 111},
            ],
            index=pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T01:00:00Z",
                    "2026-01-01T02:00:00Z",
                    "2026-01-01T03:00:00Z",
                    "2026-01-01T04:00:00Z",
                ]
            ),
        )
        cfg = EngineConfig()
        cfg.portfolio.max_open_risk = 1.5
        cfg.portfolio.allow_partial_size = True

        signal_a = make_signal("2026-01-01 00:00:00+00:00", "a")
        signal_b = make_signal("2026-01-01 01:00:00+00:00", "b")
        trades, diagnostics = simulate_signals(df, [signal_a, signal_b], cfg)
        self.assertEqual(len(trades), 2)
        self.assertAlmostEqual(trades[0].size_fraction, 1.0, places=4)
        self.assertAlmostEqual(trades[1].size_fraction, 0.5, places=4)
        self.assertEqual(diagnostics.partial_size_trades, 1)

    def test_session_and_volatility_filters(self) -> None:
        cfg = EngineConfig()
        cfg.execution.allowed_sessions = ("london",)
        cfg.execution.min_atr_to_spread_ratio = 5.0
        cfg.risk.spread_points = 2.0

        signal = make_signal("2026-01-01T01:00:00+00:00", "f1")
        signal.session = "asia"
        signal.atr_at_entry = 5.0
        reasons = filter_signal(signal, cfg)
        self.assertIn("session", reasons)
        self.assertIn("volatility_atr", reasons)


if __name__ == "__main__":
    unittest.main()
