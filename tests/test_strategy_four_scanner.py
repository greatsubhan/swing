from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from strategy_four_bot import scanner as cwt_scanner
from strategy_four_bot.scanner import CwtFwmConfig, CwtQualityLayerConfig, ladder_state_from_journal, scan_symbol


def test_ladder_state_uses_trade_timeline_and_root_signals_only(tmp_path: Path) -> None:
    journal_path = tmp_path / "signal_journal.json"
    journal_path.write_text(
        json.dumps(
            [
                {
                    "strategy_id": "strategy_four",
                    "strategy_name": "Cambist With Trend",
                    "setup_id": "late-dispatched-sl",
                    "symbol": "EUR_USD",
                    "asset_class": "forex",
                    "timeframe": "5m",
                    "side": "long",
                    "signal_timestamp": "2026-04-17T10:00:00+00:00",
                    "dispatched_at_utc": "2026-04-17T12:00:00+00:00",
                    "entry": 1.1,
                    "stop_loss": 1.0,
                    "target_1": 1.2,
                    "risk_reward": 1.0,
                    "quality_score": 80,
                    "quality_grade": "B",
                    "status": "closed",
                    "is_root_signal": True,
                    "outcome": "sl_hit",
                    "outcome_timestamp": "2026-04-17T10:30:00+00:00",
                    "raw_signal": {"risk_fraction": 0.0007},
                },
                {
                    "strategy_id": "strategy_four",
                    "strategy_name": "Cambist With Trend",
                    "setup_id": "earlier-dispatched-tp",
                    "symbol": "EUR_USD",
                    "asset_class": "forex",
                    "timeframe": "5m",
                    "side": "long",
                    "signal_timestamp": "2026-04-17T11:00:00+00:00",
                    "dispatched_at_utc": "2026-04-17T11:15:00+00:00",
                    "entry": 1.1,
                    "stop_loss": 1.0,
                    "target_1": 1.2,
                    "risk_reward": 1.0,
                    "quality_score": 82,
                    "quality_grade": "B",
                    "status": "closed",
                    "is_root_signal": True,
                    "outcome": "tp_hit",
                    "outcome_timestamp": "2026-04-17T11:10:00+00:00",
                    "raw_signal": {"risk_fraction": 0.0020},
                },
                {
                    "strategy_id": "strategy_four",
                    "strategy_name": "Cambist With Trend",
                    "setup_id": "reinforcement-should-not-count",
                    "symbol": "EUR_USD",
                    "asset_class": "forex",
                    "timeframe": "5m",
                    "side": "long",
                    "signal_timestamp": "2026-04-17T11:05:00+00:00",
                    "dispatched_at_utc": "2026-04-17T11:05:30+00:00",
                    "entry": 1.1,
                    "stop_loss": 1.0,
                    "target_1": 1.2,
                    "risk_reward": 1.0,
                    "quality_score": 85,
                    "quality_grade": "A",
                    "status": "closed",
                    "is_root_signal": False,
                    "outcome": "sl_hit",
                    "outcome_timestamp": "2026-04-17T11:07:00+00:00",
                    "raw_signal": {"risk_fraction": 0.0045},
                },
            ]
        ),
        encoding="utf-8",
    )

    ladder = ladder_state_from_journal(journal_path, "EUR_USD")

    assert ladder["last_setup_id"] == "earlier-dispatched-tp"
    assert ladder["last_outcome"] == "tp_hit"
    assert ladder["step_index"] == 0
    assert ladder["risk_pct"] == 0.07


def _base_frame() -> pd.DataFrame:
    start = datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc)
    index = [start + timedelta(minutes=5 * i) for i in range(140)]
    rows = []
    for i in range(140):
        base = 100.0 + (i * 0.01)
        rows.append(
            {
                "open": base,
                "high": base + 0.3,
                "low": base - 0.3,
                "close": base + 0.05,
                "atr14": 1.0,
                "lips": base - 0.05,
                "teeth": base - 0.10,
                "jaw": base - 0.15,
            }
        )
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(index))
    frame.index.name = "timestamp"
    return frame


def test_scan_symbol_applies_followthrough_confirmation_close_and_quality_stop(monkeypatch) -> None:
    frame = _base_frame()
    frame.iloc[-1, frame.columns.get_loc("open")] = 101.0
    frame.iloc[-1, frame.columns.get_loc("close")] = 102.0
    frame.iloc[-1, frame.columns.get_loc("high")] = 102.2
    frame.iloc[-1, frame.columns.get_loc("low")] = 100.9

    monkeypatch.setattr(cwt_scanner, "load_history", lambda *args, **kwargs: frame.copy())
    monkeypatch.setattr(cwt_scanner, "with_indicators", lambda df: df.copy())
    monkeypatch.setattr(cwt_scanner, "compute_mt5_zigzag", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(
        cwt_scanner,
        "project_cambist_levels",
        lambda execution, *_args, **_kwargs: pd.DataFrame(
            {"active_blue": [0.0] * len(execution), "active_red": [0.0] * len(execution)},
            index=execution.index,
        ),
    )
    monkeypatch.setattr(cwt_scanner, "compute_bias_series", lambda bias_frame: pd.Series([1] * len(bias_frame), index=bias_frame.index))

    def _scenario_one_long(execution, idx, bias):  # noqa: ANN001
        if idx == len(execution) - 2:
            return {"scenario": "scenario1", "atr": 1.0, "stop_anchor": 100.0}
        return None

    monkeypatch.setattr(cwt_scanner, "scenario_one_long", _scenario_one_long)
    monkeypatch.setattr(cwt_scanner, "scenario_one_short", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_long", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_short", lambda *_args, **_kwargs: None)

    result = scan_symbol(
        "EUR_USD",
        "5m",
        "practice",
        "token",
        "M",
        {"step_index": 0, "risk_pct": 0.07, "last_outcome": "none", "last_setup_id": None},
        quality_layer=CwtQualityLayerConfig(require_followthrough=True, skip_high_noise=True, stop_scale=1.1, min_atr_multiple=0.35),
    )

    signal = result["latest_signal"]
    assert signal is not None
    assert signal["entry_basis"] == "confirmation_close"
    assert signal["entry"] == 102.0
    assert signal["quality_layer"]["require_followthrough"] is True
    assert "followthrough_confirmed" in signal["quality_filter_notes"]
    assert signal["stop_loss"] < signal["entry"]
    assert round(signal["target_1"] - signal["entry"], 6) == round(signal["entry"] - signal["stop_loss"], 6)


def test_scan_symbol_skips_high_noise_when_quality_layer_enabled(monkeypatch) -> None:
    frame = _base_frame()

    monkeypatch.setattr(cwt_scanner, "load_history", lambda *args, **kwargs: frame.copy())
    monkeypatch.setattr(cwt_scanner, "with_indicators", lambda df: df.copy())
    monkeypatch.setattr(cwt_scanner, "compute_mt5_zigzag", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(
        cwt_scanner,
        "project_cambist_levels",
        lambda execution, *_args, **_kwargs: pd.DataFrame(
            {"active_blue": [0.0] * len(execution), "active_red": [0.0] * len(execution)},
            index=execution.index,
        ),
    )
    monkeypatch.setattr(cwt_scanner, "compute_bias_series", lambda bias_frame: pd.Series([1] * len(bias_frame), index=bias_frame.index))
    monkeypatch.setattr(cwt_scanner, "_recent_noise_metrics", lambda *_args, **_kwargs: {"high_noise": True, "direction_flips": 4, "compression_atr": 1.8})

    def _scenario_one_long(execution, idx, bias):  # noqa: ANN001
        if idx == len(execution) - 2:
            return {"scenario": "scenario1", "atr": 1.0, "stop_anchor": 100.0}
        return None

    monkeypatch.setattr(cwt_scanner, "scenario_one_long", _scenario_one_long)
    monkeypatch.setattr(cwt_scanner, "scenario_one_short", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_long", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_short", lambda *_args, **_kwargs: None)

    result = scan_symbol(
        "EUR_USD",
        "5m",
        "practice",
        "token",
        "M",
        {"step_index": 0, "risk_pct": 0.07, "last_outcome": "none", "last_setup_id": None},
        quality_layer=CwtQualityLayerConfig(skip_high_noise=True),
    )

    assert result["latest_signal"] is None
    assert result["reason"] == "high_noise_session"


def test_scan_symbol_emits_fwm_signal_for_selected_symbol(monkeypatch) -> None:
    frame = _base_frame()
    frame.iloc[-1, frame.columns.get_loc("open")] = 100.5
    frame.iloc[-1, frame.columns.get_loc("high")] = 101.5
    frame.iloc[-1, frame.columns.get_loc("low")] = 100.2
    frame.iloc[-1, frame.columns.get_loc("close")] = 101.2

    monkeypatch.setattr(cwt_scanner, "load_history", lambda *args, **kwargs: frame.copy())
    monkeypatch.setattr(cwt_scanner, "with_indicators", lambda df: df.copy())
    monkeypatch.setattr(cwt_scanner, "compute_mt5_zigzag", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(
        cwt_scanner,
        "project_cambist_levels",
        lambda execution, *_args, **_kwargs: pd.DataFrame(
            {"active_blue": [0.0] * len(execution), "active_red": [0.0] * len(execution)},
            index=execution.index,
        ),
    )
    monkeypatch.setattr(cwt_scanner, "compute_bias_series", lambda bias_frame: pd.Series([1] * len(bias_frame), index=bias_frame.index))
    monkeypatch.setattr(cwt_scanner, "scenario_one_long", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_one_short", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_long", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_short", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cwt_scanner,
        "_detect_fwm_candidate",
        lambda frame, idx, bias, swing_lookback_bars: {
            "side": "long",
            "trigger_price": 101.0,
            "stop_price": 99.5,
            "target_price": 102.5,
            "initial_risk": 1.5,
            "scenario": "fwm",
        }
        if idx == len(frame) - 2
        else None,
    )

    result = scan_symbol(
        "EUR_USD",
        "5m",
        "practice",
        "token",
        "M",
        {"step_index": 0, "risk_pct": 0.07, "last_outcome": "none", "last_setup_id": None},
        quality_layer=CwtQualityLayerConfig(skip_high_noise=False),
        fwm_config=CwtFwmConfig(enabled_symbols=frozenset({"EUR_USD"}), swing_lookback_bars=8, order_valid_bars=2),
    )

    signal = result["latest_signal"]
    assert signal is not None
    assert signal["scenario"] == "fwm"
    assert signal["signal_source"] == "fwm_selective"
    assert signal["signal_type"] == "long"


def test_scan_symbol_keeps_unselected_symbol_on_baseline_only(monkeypatch) -> None:
    frame = _base_frame()

    monkeypatch.setattr(cwt_scanner, "load_history", lambda *args, **kwargs: frame.copy())
    monkeypatch.setattr(cwt_scanner, "with_indicators", lambda df: df.copy())
    monkeypatch.setattr(cwt_scanner, "compute_mt5_zigzag", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(
        cwt_scanner,
        "project_cambist_levels",
        lambda execution, *_args, **_kwargs: pd.DataFrame(
            {"active_blue": [0.0] * len(execution), "active_red": [0.0] * len(execution)},
            index=execution.index,
        ),
    )
    monkeypatch.setattr(cwt_scanner, "compute_bias_series", lambda bias_frame: pd.Series([1] * len(bias_frame), index=bias_frame.index))
    monkeypatch.setattr(cwt_scanner, "scenario_one_long", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_one_short", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_long", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cwt_scanner, "scenario_two_short", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cwt_scanner,
        "_detect_fwm_candidate",
        lambda *_args, **_kwargs: {"side": "long", "trigger_price": 101.0, "stop_price": 99.5, "target_price": 102.5, "initial_risk": 1.5, "scenario": "fwm"},
    )

    result = scan_symbol(
        "NAS100_USD",
        "5m",
        "practice",
        "token",
        "M",
        {"step_index": 0, "risk_pct": 0.07, "last_outcome": "none", "last_setup_id": None},
        fwm_config=CwtFwmConfig(enabled_symbols=frozenset({"EUR_USD"}), swing_lookback_bars=8, order_valid_bars=2),
    )

    assert result["latest_signal"] is None
    assert result["reason"] == "no_signal"
