"""Real-time signal scoring with ML model predictions."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .ml_features import FeatureVector, _extract_raw_signal_features, _extract_time_features
from .ml_inference import ModelPredictor
from .models import PlatformSignal


def score_signal_with_ml(
    signal: PlatformSignal,
    model_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Score a signal with ML model predictions.
    
    Args:
        signal: The platform signal to score
        model_dir: Optional directory containing trained models
    
    Returns:
        Dictionary with score, predictions, and metadata
    """
    score = {
        "setup_id": signal.setup_id,
        "symbol": signal.symbol,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "outcome_prediction": None,
        "realized_r_prediction": None,
        "ml_confidence": 0.5,
        "score_computed": False,
    }
    
    # If no model directory provided, just return empty score
    if model_dir is None:
        return score
    
    # Try to load models and make predictions
    try:
        predictor = _load_model_predictor(model_dir)
        
        # Check if any models are available
        if predictor.outcome_model is None and predictor.realized_r_model is None:
            return score
        
        # Extract features from signal
        features = _extract_features_from_signal(signal)
        
        # Get predictions
        outcome_pred = predictor.predict_outcome(features)
        realized_r_pred = predictor.predict_realized_r(features)
        
        score["outcome_prediction"] = outcome_pred
        score["realized_r_prediction"] = realized_r_pred
        
        # Compute overall confidence
        if outcome_pred.get("available") and "confidence" in outcome_pred:
            score["ml_confidence"] = outcome_pred["confidence"]
        
        score["score_computed"] = True
        
    except Exception as exc:
        score["error"] = str(exc)
    
    return score


@lru_cache(maxsize=8)
def _load_model_predictor(model_dir: Path | str) -> ModelPredictor:
    return ModelPredictor(model_dir)


def _extract_features_from_signal(signal: PlatformSignal) -> dict[str, float | int | str]:
    """Extract ML features from a PlatformSignal."""
    features = {}
    
    # Quality features
    features["quality_score"] = signal.quality_score or 0.0
    features["quality_grade"] = signal.quality_grade or "unknown"
    
    # Raw signal features
    raw_signal_features = _extract_raw_signal_features(signal.raw_signal or {})
    features.update(raw_signal_features)
    
    # Time features - use 'timestamp' field from PlatformSignal
    time_features = _extract_time_features(signal.timestamp)
    features.update(time_features)
    
    # Asset class
    features["asset_class"] = signal.asset_class or "unknown"
    
    # Scenario
    scenario = str(signal.raw_signal.get("scenario", "unknown")) if signal.raw_signal else "unknown"
    features["scenario"] = scenario
    
    return features


def filter_signals_by_model_confidence(
    signals: list[PlatformSignal],
    model_dir: Path | str,
    min_confidence: float = 0.6,
) -> tuple[list[PlatformSignal], list[dict[str, Any]]]:
    """Filter signals by ML model confidence threshold.
    
    Args:
        signals: List of signals to filter
        model_dir: Directory containing trained models
        min_confidence: Minimum confidence threshold (0-1)
    
    Returns:
        (filtered_signals, scores_for_all)
    """
    scores = []
    filtered = []
    
    for signal in signals:
        score = score_signal_with_ml(signal, model_dir)
        scores.append(score)
        
        confidence = score.get("ml_confidence", 0.5)
        if confidence >= min_confidence:
            filtered.append(signal)
    
    return filtered, scores


def rank_signals_by_expected_r(
    signals: list[PlatformSignal],
    model_dir: Path | str,
) -> tuple[list[tuple[PlatformSignal, float]], list[dict[str, Any]]]:
    """Rank signals by expected realized R prediction.
    
    Args:
        signals: List of signals to rank
        model_dir: Directory containing trained models
    
    Returns:
        (ranked_signals_with_r, scores_for_all) where ranked list is sorted descending by R
    """
    scores = []
    ranked = []
    
    for signal in signals:
        score = score_signal_with_ml(signal, model_dir)
        scores.append(score)
        
        realized_r_pred = score.get("realized_r_prediction") or {}
        expected_r = realized_r_pred.get("prediction", 0.0) if realized_r_pred.get("available") else 0.0
        
        ranked.append((signal, float(expected_r)))
    
    # Sort by expected R descending
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    return ranked, scores


def create_signal_score_summary(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Create summary statistics from signal scores.
    
    Args:
        scores: List of signal scores
    
    Returns:
        Summary dictionary with statistics
    """
    if not scores:
        return {}
    
    computed = [s for s in scores if s.get("score_computed")]
    if not computed:
        return {"total_signals": len(scores), "models_computed": 0}
    
    outcome_preds = []
    realized_r_preds = []
    confidences = []
    
    for score in computed:
        confidences.append(score.get("ml_confidence", 0.5))
        
        outcome_pred = score.get("outcome_prediction", {})
        if outcome_pred.get("available"):
            outcome_preds.append(outcome_pred.get("prediction", 0))
        
        realized_r_pred = score.get("realized_r_prediction", {})
        if realized_r_pred.get("available"):
            realized_r_preds.append(realized_r_pred.get("prediction", 0.0))
    
    summary = {
        "total_signals": len(scores),
        "models_computed": len(computed),
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.5,
        "min_confidence": min(confidences) if confidences else 0.5,
        "max_confidence": max(confidences) if confidences else 0.5,
    }
    
    if outcome_preds:
        win_count = sum(1 for p in outcome_preds if p == 1)
        summary["predicted_win_ratio"] = win_count / len(outcome_preds)
        summary["predicted_win_count"] = win_count
    
    if realized_r_preds:
        summary["avg_expected_r"] = sum(realized_r_preds) / len(realized_r_preds)
        summary["median_expected_r"] = sorted(realized_r_preds)[len(realized_r_preds) // 2]
        summary["max_expected_r"] = max(realized_r_preds)
        summary["min_expected_r"] = min(realized_r_preds)
    
    return summary
