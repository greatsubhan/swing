"""Tests for signal scoring, prediction tracking, and Discord integration."""
import json
import tempfile
from pathlib import Path

import pytest

from signal_platform.journal import JournalEntry, save_journal
from signal_platform.models import PlatformSignal
from signal_platform.signal_scoring import (
    score_signal_with_ml,
    filter_signals_by_model_confidence,
    rank_signals_by_expected_r,
    create_signal_score_summary,
)
from signal_platform.prediction_tracking import (
    record_prediction,
    load_predictions,
    match_predictions_with_outcomes,
    evaluate_predictions,
    generate_prediction_report,
)
from signal_platform.discord_predictions import (
    format_signal_with_prediction,
    format_signal_batch_summary,
    format_report_with_predictions,
    create_prediction_confidence_badge,
)


def _create_sample_signal() -> PlatformSignal:
    """Create a sample platform signal for testing."""
    return PlatformSignal(
        strategy_id="test_strategy",
        strategy_name="Test Strategy",
        setup_id="test_setup_001",
        symbol="EURUSD",
        asset_class="FX",
        timeframe="H4",
        side="long",
        timestamp="2026-01-15T14:30:00Z",
        summary="Test signal",
        alert_text="Test alert",
        quality_score=8,
        quality_grade="A",
        entry=1.0800,
        stop_loss=1.0790,
        target_1=1.0820,
        risk_reward=2.0,
        raw_signal={
            "scenario": "trend",
            "level_distance": 10.5,
            "fwm_score": 0.75,
            "delivery_kind": "fresh",
        },
        is_tradable=True,
    )


def _create_sample_journal_entry() -> JournalEntry:
    """Create a sample journal entry."""
    return JournalEntry(
        strategy_id="test_strategy",
        strategy_name="Test Strategy",
        setup_id="test_setup_001",
        symbol="EURUSD",
        asset_class="FX",
        timeframe="H4",
        side="long",
        signal_timestamp="2026-01-15T14:30:00Z",
        dispatched_at_utc="2026-01-15T14:35:00Z",
        entry=1.0800,
        stop_loss=1.0790,
        target_1=1.0820,
        risk_reward=2.0,
        quality_score=8,
        quality_grade="A",
        status="closed",
        exit_price=1.0825,
        outcome="win",
        outcome_timestamp="2026-01-15T18:30:00Z",
        raw_signal={
            "scenario": "trend",
            "level_distance": 10.5,
            "fwm_score": 0.75,
        },
    )


class TestSignalScoring:
    """Test signal scoring functionality."""
    
    def test_score_signal_without_models(self):
        """Test scoring signal with no models available."""
        signal = _create_sample_signal()
        
        score = score_signal_with_ml(signal, model_dir=None)
        
        assert score["setup_id"] == signal.setup_id
        assert score["score_computed"] is False
    
    def test_score_signal_with_missing_models(self):
        """Test scoring signal when model directory has no models."""
        signal = _create_sample_signal()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            score = score_signal_with_ml(signal, model_dir=tmpdir)
            
            assert score["setup_id"] == signal.setup_id
            assert score["score_computed"] is False
    
    def test_filter_signals_by_confidence(self):
        """Test filtering signals by confidence threshold."""
        signals = [_create_sample_signal() for _ in range(3)]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filtered, scores = filter_signals_by_model_confidence(
                signals, tmpdir, min_confidence=0.6
            )
            
            assert len(scores) == 3
            assert isinstance(filtered, list)
    
    def test_rank_signals_by_expected_r(self):
        """Test ranking signals by expected R."""
        signals = [_create_sample_signal() for _ in range(3)]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ranked, scores = rank_signals_by_expected_r(signals, tmpdir)
            
            assert len(ranked) == 3
            assert len(scores) == 3
            # Check that tuples contain (signal, R_value)
            for signal, r_value in ranked:
                assert isinstance(signal, PlatformSignal)
                assert isinstance(r_value, float)
    
    def test_create_signal_score_summary(self):
        """Test creating summary from scores."""
        scores = [
            {"score_computed": False},
            {"score_computed": False},
        ]
        
        summary = create_signal_score_summary(scores)
        
        assert summary["total_signals"] == 2
        assert summary["models_computed"] == 0


class TestPredictionTracking:
    """Test prediction tracking functionality."""
    
    def test_record_and_load_predictions(self):
        """Test recording and loading predictions."""
        prediction = {
            "available": True,
            "prediction": 1,
            "prediction_text": "win",
            "confidence": 0.85,
        }
        
        realized_r = {
            "available": True,
            "prediction": 1.5,
            "prediction_rounded": 1.50,
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pred_path = Path(tmpdir) / "predictions.jsonl"
            
            record_prediction("setup_001", prediction, realized_r, pred_path)
            
            loaded = load_predictions(pred_path)
            
            assert len(loaded) == 1
            assert loaded[0]["setup_id"] == "setup_001"
            assert loaded[0]["outcome_prediction"] == prediction
    
    def test_match_predictions_with_outcomes(self):
        """Test matching predictions with journal outcomes."""
        prediction = {
            "setup_id": "test_setup_001",
            "timestamp_utc": "2026-01-15T14:35:00Z",
            "outcome_prediction": {"available": True, "prediction": 1},
            "realized_r_prediction": {"available": True, "prediction": 1.5},
        }
        
        entry = _create_sample_journal_entry()
        
        matched = match_predictions_with_outcomes([prediction], [entry])
        
        assert len(matched) == 1
        assert matched[0]["setup_id"] == "test_setup_001"
        assert matched[0]["actual_outcome"] == "win"
    
    def test_evaluate_predictions(self):
        """Test prediction evaluation."""
        matched = [
            {
                "setup_id": "s001",
                "actual_realized_r": 1.5,
                "outcome_prediction": {"available": True, "prediction": 1},
            }
        ]
        
        evaluation = evaluate_predictions(matched)
        
        assert evaluation["total_predictions"] == 1
        assert "outcome_prediction" in evaluation
    
    def test_generate_prediction_report(self):
        """Test report generation."""
        evaluation = {
            "total_predictions": 10,
            "closed_trades": 8,
            "outcome_prediction": {
                "evaluated": 8,
                "accuracy": 0.75,
                "correct": 6,
            },
        }
        
        report = generate_prediction_report(evaluation)
        
        assert "MODEL PREDICTION PERFORMANCE" in report
        assert "Accuracy" in report


class TestDiscordPredictions:
    """Test Discord formatting with predictions."""
    
    def test_format_signal_with_prediction(self):
        """Test formatting signal with prediction."""
        signal = _create_sample_signal()
        score = {
            "score_computed": False,
            "ml_confidence": 0.5,
        }
        
        formatted = format_signal_with_prediction(signal, score)
        
        assert "EURUSD" in formatted
        assert signal.quality_grade in formatted
    
    def test_format_signal_batch_summary(self):
        """Test formatting batch summary."""
        signals = [_create_sample_signal() for _ in range(2)]
        scores = [
            {"score_computed": False, "ml_confidence": 0.5},
            {"score_computed": False, "ml_confidence": 0.6},
        ]
        
        formatted = format_signal_batch_summary(signals, scores)
        
        assert "SIGNAL BATCH" in formatted
        assert "2 signal" in formatted
    
    def test_format_report_with_predictions(self):
        """Test enhancing report with predictions."""
        report = "Test Report"
        prediction_summary = {
            "closed_trades": 5,
            "outcome_prediction": {
                "evaluated": 5,
                "accuracy": 0.8,
                "correct": 4,
            },
        }
        
        enhanced = format_report_with_predictions(report, prediction_summary)
        
        assert "Test Report" in enhanced
        assert "ML MODEL PERFORMANCE" in enhanced
        assert "80" in enhanced  # 80% accuracy
    
    def test_create_confidence_badge(self):
        """Test confidence badge creation."""
        # Test various confidence levels
        badge_high = create_prediction_confidence_badge(0.95)
        assert "Very High" in badge_high
        
        badge_medium = create_prediction_confidence_badge(0.65)
        assert "Medium" in badge_medium
        
        badge_low = create_prediction_confidence_badge(0.45)
        assert "Very Low" in badge_low


class TestIntegration:
    """Integration tests for all three modules."""
    
    def test_end_to_end_prediction_workflow(self):
        """Test complete workflow from scoring to tracking to reporting."""
        signal = _create_sample_signal()
        entry = _create_sample_journal_entry()
        
        # Score signal
        with tempfile.TemporaryDirectory() as tmpdir:
            score = score_signal_with_ml(signal, tmpdir)
            
            # Record prediction
            pred_path = Path(tmpdir) / "predictions.jsonl"
            record_prediction(
                signal.setup_id,
                score.get("outcome_prediction", {}),
                score.get("realized_r_prediction", {}),
                pred_path,
            )
            
            # Load and match
            predictions = load_predictions(pred_path)
            matched = match_predictions_with_outcomes(predictions, [entry])
            
            # Should have a match
            assert len(matched) > 0
            
            # Evaluate
            evaluation = evaluate_predictions(matched)
            assert evaluation["total_predictions"] > 0
            
            # Format for Discord
            formatted = format_signal_with_prediction(signal, score)
            assert signal.symbol in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
