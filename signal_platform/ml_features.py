"""ML feature extraction and dataset building for signal platform journals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np

from .journal import load_journal
from .metrics import _parse_datetime, _time_of_day_bucket
from .models import JournalEntry


@dataclass
class FeatureVector:
    """A single feature vector with label."""

    setup_id: str
    signal_timestamp: str
    features: dict[str, float | int | str]
    outcome_label: int | None
    realized_r_label: float | None
    asset_class: str | None
    scenario: str | None


def _extract_raw_signal_features(raw_signal: dict[str, Any]) -> dict[str, float | int]:
    """Extract numeric features from raw_signal dict."""
    features: dict[str, float | int] = {}
    
    # Common numeric fields that might appear in raw_signal
    numeric_keys = [
        "level_distance",
        "fwm_score",
        "confirmation_strength",
        "trend_alignment",
        "structure_confluence",
        "pips_to_entry",
        "risk_pips",
        "reward_pips",
    ]
    
    for key in numeric_keys:
        value = raw_signal.get(key)
        if value is not None:
            try:
                features[f"raw_signal_{key}"] = float(value)
            except (ValueError, TypeError):
                pass
    
    return features


def _extract_time_features(signal_timestamp: str | None) -> dict[str, str | int]:
    """Extract time-based features from signal timestamp."""
    features: dict[str, str | int] = {}
    
    dt = _parse_datetime(signal_timestamp)
    if dt is None:
        return {"time_of_day": "unknown", "day_of_week": -1, "hour": -1}
    
    features["time_of_day"] = _time_of_day_bucket(dt)
    features["day_of_week"] = dt.weekday()
    features["hour"] = dt.hour
    
    return features


def _compute_previous_outcome(
    current_idx: int,
    entries: list[JournalEntry],
    lookback_count: int = 5,
) -> dict[str, int | float]:
    """Compute aggregate outcome from previous N trades."""
    features: dict[str, int | float] = {}
    
    if current_idx < 1:
        features["prev_win_ratio"] = 0.0
        features["prev_avg_r"] = 0.0
        features["prev_trades_count"] = 0
        return features
    
    # Look back at previous entries
    start_idx = max(0, current_idx - lookback_count)
    prev_entries = entries[start_idx:current_idx]
    
    closed = [e for e in prev_entries if e.status == "closed"]
    if not closed:
        features["prev_win_ratio"] = 0.0
        features["prev_avg_r"] = 0.0
        features["prev_trades_count"] = 0
        return features
    
    realized_r_values = [e.realized_r() for e in closed if e.realized_r() is not None]
    wins = [r for r in realized_r_values if r > 0]
    
    features["prev_win_ratio"] = len(wins) / len(closed) if closed else 0.0
    features["prev_avg_r"] = sum(realized_r_values) / len(realized_r_values) if realized_r_values else 0.0
    features["prev_trades_count"] = len(closed)
    
    return features


def build_feature_vectors(
    entries: list[JournalEntry],
    test_fraction: float = 0.2,
) -> tuple[list[FeatureVector], list[FeatureVector]]:
    """Build feature vectors from journal entries with time-based train/test split.
    
    Args:
        entries: Journal entries sorted by signal_timestamp
        test_fraction: Fraction of most recent entries to use as test set
    
    Returns:
        (train_vectors, test_vectors)
    """
    vectors: list[FeatureVector] = []
    
    for idx, entry in enumerate(entries):
        # Extract features
        raw_signal_features = _extract_raw_signal_features(entry.raw_signal or {})
        time_features = _extract_time_features(entry.signal_timestamp)
        previous_features = _compute_previous_outcome(idx, entries, lookback_count=5)
        
        features = {
            "quality_score": entry.quality_score or 0.0,
            "quality_grade": entry.quality_grade or "unknown",
            **raw_signal_features,
            **time_features,
            **previous_features,
        }
        
        # Determine labels
        outcome_label = None
        realized_r_label = None
        
        if entry.status == "closed":
            realized_r = entry.realized_r()
            if realized_r is not None:
                # Binary outcome: 1 for win, 0 for loss
                outcome_label = 1 if realized_r > 0 else 0
                realized_r_label = realized_r
        
        vector = FeatureVector(
            setup_id=entry.setup_id,
            signal_timestamp=entry.signal_timestamp or "",
            features=features,
            outcome_label=outcome_label,
            realized_r_label=realized_r_label,
            asset_class=entry.asset_class,
            scenario=str(entry.raw_signal.get("scenario", "unknown")) if entry.raw_signal else "unknown",
        )
        vectors.append(vector)
    
    # Time-based train/test split
    split_idx = int(len(vectors) * (1 - test_fraction))
    train_vectors = vectors[:split_idx]
    test_vectors = vectors[split_idx:]
    
    return train_vectors, test_vectors


def vectors_to_numpy(
    vectors: list[FeatureVector],
    feature_names: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
    """Convert feature vectors to numpy arrays.
    
    Args:
        vectors: List of FeatureVector objects
        feature_names: Optional list of feature names to extract (in order).
                      If None, all features are used (order may vary).
    
    Returns:
        (X, y_outcome, y_realized_r) where X is (n_samples, n_features),
        y_outcome is binary labels, y_realized_r is continuous labels.
        y_outcome and y_realized_r are None if no labeled samples exist.
    """
    if not vectors:
        return np.array([]), None, None
    
    # Determine feature names if not provided
    if feature_names is None:
        # Collect all unique feature names
        feature_set = set()
        for vec in vectors:
            feature_set.update(vec.features.keys())
        feature_names = sorted(feature_set)
    
    # Build feature matrix
    X_list = []
    y_outcome_list = []
    y_realized_r_list = []
    labeled_indices = []
    
    for idx, vec in enumerate(vectors):
        # Extract features in order
        row = []
        for fname in feature_names:
            value = vec.features.get(fname)
            # Convert categorical to numeric if needed
            if isinstance(value, str):
                # Simple encoding: hash for now (can improve)
                value = hash(value) % 1000 / 1000.0
            row.append(float(value) if value is not None else 0.0)
        
        X_list.append(row)
        
        if vec.outcome_label is not None:
            y_outcome_list.append(vec.outcome_label)
            labeled_indices.append(idx)
        
        if vec.realized_r_label is not None and idx not in [i for i in labeled_indices if vec.outcome_label is None]:
            y_realized_r_list.append(vec.realized_r_label)
    
    X = np.array(X_list, dtype=np.float64)
    y_outcome = np.array(y_outcome_list, dtype=np.int32) if y_outcome_list else None
    y_realized_r = np.array(y_realized_r_list, dtype=np.float64) if y_realized_r_list else None
    
    return X, y_outcome, y_realized_r


def load_and_build_features(
    journal_path: str | Path,
    test_fraction: float = 0.2,
) -> tuple[list[FeatureVector], list[FeatureVector], list[str]]:
    """Load journal and build feature vectors with feature names.
    
    Returns:
        (train_vectors, test_vectors, feature_names)
    """
    from pathlib import Path
    
    entries = load_journal(journal_path)
    train_vectors, test_vectors = build_feature_vectors(entries, test_fraction=test_fraction)
    
    # Determine feature names from all vectors
    feature_set = set()
    for vec in train_vectors + test_vectors:
        feature_set.update(vec.features.keys())
    feature_names = sorted(feature_set)
    
    return train_vectors, test_vectors, feature_names
