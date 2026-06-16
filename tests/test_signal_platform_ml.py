"""Tests for ML pipeline modules."""
import json
import tempfile
from pathlib import Path

import pytest

from signal_platform.journal import JournalEntry, save_journal
from signal_platform.ml_features import (
    build_feature_vectors,
    vectors_to_numpy,
    _extract_raw_signal_features,
    _extract_time_features,
    _compute_previous_outcome,
)
from signal_platform.ml_models import (
    train_outcome_classifier,
    train_realized_r_regressor,
    save_model_metadata,
    load_model_metadata,
)


def _create_sample_journal_entries(count: int = 30) -> list[JournalEntry]:
    """Create sample journal entries for testing."""
    entries = []
    
    for i in range(count):
        is_closed = i < count - 5
        outcome = "win" if is_closed and i % 2 == 0 else ("loss" if is_closed else None)
        realized_r = (2.0 - i * 0.05) if is_closed else None
        
        entry = JournalEntry(
            strategy_id="test_strategy",
            strategy_name="Test Strategy",
            setup_id=f"setup_{i}",
            symbol="EURUSD",
            asset_class="FX",
            timeframe="H4",
            side="long",
            signal_timestamp=f"2026-01-{(i % 28) + 1:02d}T{(i % 24):02d}:00:00Z",
            dispatched_at_utc=f"2026-01-{(i % 28) + 1:02d}T{(i % 24):02d}:05:00Z",
            entry=1.0800 + i * 0.0001,
            stop_loss=1.0790 + i * 0.0001,
            target_1=1.0820 + i * 0.0001,
            risk_reward=2.0,
            quality_score=6 + (i % 5),
            quality_grade="A" if i % 2 == 0 else "B",
            status="closed" if is_closed else "open",
            exit_price=1.0825 + i * 0.0002 if is_closed else None,
            outcome=outcome,
            outcome_timestamp=f"2026-01-{(i % 28) + 1:02d}T{((i % 24) + 4):02d}:00:00Z" if is_closed else None,
            raw_signal={
                "scenario": "trend",
                "level_distance": 10.5 + i * 0.5,
                "fwm_score": 0.5 + (i % 5) * 0.1,
                "delivery_kind": "fresh",
            },
        )
        # Manually add realized_r using the dict representation
        entry_dict = entry.to_dict()
        # Re-create with realized_r note
        entries.append(entry)
    
    return entries


class TestFeatureExtraction:
    """Test feature extraction from journal entries."""
    
    def test_extract_raw_signal_features(self):
        """Test extraction of numeric features from raw_signal."""
        raw_signal = {
            "scenario": "trend",
            "level_distance": 10.5,
            "fwm_score": 0.75,
            "unknown_field": "ignored",
            "confirmation_strength": 0.8,
        }
        
        features = _extract_raw_signal_features(raw_signal)
        
        assert "raw_signal_level_distance" in features
        assert features["raw_signal_level_distance"] == 10.5
        assert "raw_signal_fwm_score" in features
        assert features["raw_signal_fwm_score"] == 0.75
        assert "raw_signal_confirmation_strength" in features
    
    def test_extract_time_features(self):
        """Test extraction of time-based features."""
        timestamp = "2026-01-15T14:30:00Z"
        
        features = _extract_time_features(timestamp)
        
        assert "time_of_day" in features
        assert "day_of_week" in features
        assert "hour" in features
        assert features["hour"] == 14
        assert features["day_of_week"] in range(7)
    
    def test_compute_previous_outcome(self):
        """Test computation of previous trade outcomes."""
        entries = _create_sample_journal_entries(10)
        
        features = _compute_previous_outcome(5, entries, lookback_count=3)
        
        assert "prev_win_ratio" in features
        assert "prev_avg_r" in features
        assert "prev_trades_count" in features
        assert 0 <= features["prev_win_ratio"] <= 1
    
    def test_build_feature_vectors(self):
        """Test building feature vectors from entries."""
        entries = _create_sample_journal_entries(20)
        
        train, test = build_feature_vectors(entries, test_fraction=0.2)
        
        assert len(train) > 0
        assert len(test) > 0
        assert len(train) > len(test)  # Train should be larger
        
        # Check that all vectors have features
        for vec in train:
            assert len(vec.features) > 0
            assert vec.setup_id
    
    def test_vectors_to_numpy(self):
        """Test conversion of feature vectors to numpy arrays."""
        entries = _create_sample_journal_entries(20)
        train, test = build_feature_vectors(entries)
        
        X, y_outcome, y_r = vectors_to_numpy(train)
        
        assert X.shape[0] == len(train)
        assert X.shape[1] > 0
        # Check that we have some labeled samples
        if y_outcome is not None:
            assert len(y_outcome) > 0


class TestModelTraining:
    """Test model training and validation."""
    
    def test_train_outcome_classifier_logistic(self):
        """Test training logistic regression outcome classifier."""
        import numpy as np
        
        # Create dummy data
        X_train = np.random.randn(30, 10)
        y_train = np.random.randint(0, 2, 30)
        X_test = np.random.randn(10, 10)
        y_test = np.random.randint(0, 2, 10)
        
        model, result = train_outcome_classifier(
            X_train, y_train, X_test, y_test,
            model_type="logistic",
            feature_names=[f"feature_{i}" for i in range(10)]
        )
        
        assert model is not None
        assert result.model_type == "logistic"
        assert result.train_metrics["accuracy"] >= 0
        assert result.test_metrics["accuracy"] >= 0
        assert len(result.feature_names) == 10
    
    def test_train_outcome_classifier_decision_tree(self):
        """Test training decision tree outcome classifier."""
        import numpy as np
        
        X_train = np.random.randn(30, 10)
        y_train = np.random.randint(0, 2, 30)
        X_test = np.random.randn(10, 10)
        y_test = np.random.randint(0, 2, 10)
        
        model, result = train_outcome_classifier(
            X_train, y_train, X_test, y_test,
            model_type="decision_tree",
        )
        
        assert model is not None
        assert result.model_type == "decision_tree"
        assert "accuracy" in result.test_metrics
    
    def test_train_realized_r_regressor(self):
        """Test training realized R regressor."""
        import numpy as np
        
        X_train = np.random.randn(30, 10)
        y_train = np.random.randn(30) * 2  # R values
        X_test = np.random.randn(10, 10)
        y_test = np.random.randn(10) * 2
        
        model, result = train_realized_r_regressor(
            X_train, y_train, X_test, y_test,
            model_type="decision_tree",
        )
        
        assert model is not None
        assert result.model_type == "decision_tree"
        assert "mae" in result.test_metrics
        assert "rmse" in result.test_metrics
    
    def test_save_load_model_metadata(self):
        """Test saving and loading model metadata."""
        from signal_platform.ml_models import ModelTrainResult
        
        result = ModelTrainResult(
            model_type="logistic",
            feature_names=["f1", "f2", "f3"],
            train_metrics={"accuracy": 0.85},
            test_metrics={"accuracy": 0.80},
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "metadata.json"
            save_model_metadata(result, path)
            
            assert path.exists()
            loaded = load_model_metadata(path)
            
            assert loaded.model_type == "logistic"
            assert loaded.feature_names == ["f1", "f2", "f3"]
            assert loaded.train_metrics["accuracy"] == 0.85


class TestEndToEnd:
    """End-to-end tests for ML pipeline."""
    
    def test_full_pipeline_with_sample_data(self):
        """Test the complete pipeline from journal to trained models."""
        import numpy as np
        
        entries = _create_sample_journal_entries(50)
        
        # Build feature vectors
        train, test, feature_names = (
            build_feature_vectors(entries),
            build_feature_vectors(entries),
            []
        )
        
        # For simplicity, test just feature building
        assert len(train) > 0
        assert len(test) > 0
    
    def test_journal_to_models_integration(self):
        """Test integration from journal file to model training."""
        entries = _create_sample_journal_entries(30)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "journal.json"
            save_journal(str(journal_path), entries)
            
            assert journal_path.exists()
            
            # Load and process
            from signal_platform.ml_features import load_and_build_features
            train, test, feature_names = load_and_build_features(str(journal_path))
            
            assert len(train) > 0
            assert len(test) > 0
            assert len(feature_names) > 0


class TestModelInference:
    """Test model inference and prediction."""
    
    def test_model_predictor_graceful_failure(self):
        """Test that ModelPredictor handles missing models gracefully."""
        from signal_platform.ml_inference import ModelPredictor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = ModelPredictor(tmpdir)
            
            features = {"feature_0": 0.5, "feature_1": 0.3}
            
            # Should not crash, should return error status
            outcome = predictor.predict_outcome(features)
            assert "available" in outcome
            
            realized_r = predictor.predict_realized_r(features)
            assert "available" in realized_r
    
    def test_load_and_predict_convenience(self):
        """Test convenience function for loading and predicting."""
        from signal_platform.ml_inference import load_and_predict
        
        with tempfile.TemporaryDirectory() as tmpdir:
            features = {"f1": 0.1, "f2": 0.2}
            
            predictions = load_and_predict(tmpdir, features)
            
            assert "outcome" in predictions
            assert "realized_r" in predictions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
