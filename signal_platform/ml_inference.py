"""Model inference and prediction for signal platform ML pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .ml_models import load_model, load_model_metadata
from .ml_features import FeatureVector


class ModelPredictor:
    """Load and use trained models for inference."""
    
    def __init__(self, model_dir: Path | str):
        """Initialize predictor from model directory.
        
        Args:
            model_dir: Directory containing model files (*.pkl) and metadata (*.json)
        """
        self.model_dir = Path(model_dir)
        self.outcome_model = None
        self.outcome_metadata = None
        self.realized_r_model = None
        self.realized_r_metadata = None
        
        # Load outcome model if available
        outcome_model_path = self.model_dir / "outcome_classifier.pkl"
        outcome_meta_path = self.model_dir / "outcome_classifier_metadata.json"
        if outcome_model_path.exists() and outcome_meta_path.exists():
            try:
                self.outcome_model = load_model(outcome_model_path)
                self.outcome_metadata = load_model_metadata(outcome_meta_path)
            except Exception as exc:
                print(f"Warning: Failed to load outcome model: {exc}")
        
        # Load realized R model if available
        realized_r_model_path = self.model_dir / "realized_r_regressor.pkl"
        realized_r_meta_path = self.model_dir / "realized_r_regressor_metadata.json"
        if realized_r_model_path.exists() and realized_r_meta_path.exists():
            try:
                self.realized_r_model = load_model(realized_r_model_path)
                self.realized_r_metadata = load_model_metadata(realized_r_meta_path)
            except Exception as exc:
                print(f"Warning: Failed to load realized R model: {exc}")
    
    def predict_outcome(self, features: dict[str, float | int | str]) -> dict[str, float]:
        """Predict trade outcome (win/loss) for feature vector.
        
        Args:
            features: Feature dict from FeatureVector.features
        
        Returns:
            Dict with prediction and confidence
        """
        if self.outcome_model is None or self.outcome_metadata is None:
            return {
                "available": False,
                "error": "outcome_model_not_loaded",
            }
        
        try:
            # Extract features in order
            feature_names = self.outcome_metadata.feature_names
            X = np.array([[
                float(features.get(fname, 0.0)) if isinstance(features.get(fname), (int, float, str))
                else 0.0
                for fname in feature_names
            ]])
            
            prediction = self.outcome_model.predict(X)[0]
            
            # Get confidence if available
            confidence = 0.5
            if hasattr(self.outcome_model, 'predict_proba'):
                try:
                    proba = self.outcome_model.predict_proba(X)[0]
                    confidence = float(proba[int(prediction)])
                except Exception:
                    pass
            
            return {
                "available": True,
                "prediction": int(prediction),
                "prediction_text": "win" if prediction == 1 else "loss",
                "confidence": float(confidence),
            }
        except Exception as exc:
            return {
                "available": True,
                "error": str(exc),
            }
    
    def predict_realized_r(self, features: dict[str, float | int | str]) -> dict[str, float]:
        """Predict realized R for feature vector.
        
        Args:
            features: Feature dict from FeatureVector.features
        
        Returns:
            Dict with prediction and confidence interval
        """
        if self.realized_r_model is None or self.realized_r_metadata is None:
            return {
                "available": False,
                "error": "realized_r_model_not_loaded",
            }
        
        try:
            # Extract features in order
            feature_names = self.realized_r_metadata.feature_names
            X = np.array([[
                float(features.get(fname, 0.0)) if isinstance(features.get(fname), (int, float, str))
                else 0.0
                for fname in feature_names
            ]])
            
            prediction = self.realized_r_model.predict(X)[0]
            
            return {
                "available": True,
                "prediction": float(prediction),
                "prediction_rounded": round(float(prediction), 2),
            }
        except Exception as exc:
            return {
                "available": True,
                "error": str(exc),
            }
    
    def predict_both(self, features: dict[str, float | int | str]) -> dict[str, Any]:
        """Predict both outcome and realized R.
        
        Args:
            features: Feature dict from FeatureVector.features
        
        Returns:
            Dict with both predictions
        """
        return {
            "outcome": self.predict_outcome(features),
            "realized_r": self.predict_realized_r(features),
        }


def load_and_predict(model_dir: Path | str, features: dict[str, float | int | str]) -> dict[str, Any]:
    """Convenience function to load models and make predictions.
    
    Args:
        model_dir: Directory containing models
        features: Feature dict
    
    Returns:
        Predictions dict
    """
    predictor = ModelPredictor(model_dir)
    return predictor.predict_both(features)
