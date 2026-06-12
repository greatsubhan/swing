"""ML model training, validation, and evaluation for signal platform."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        roc_auc_score,
        mean_squared_error,
        mean_absolute_error,
    )
    from sklearn.preprocessing import StandardScaler
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class ClassificationMetrics:
    """Metrics for binary classification."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None = None
    support: int = 0


@dataclass
class RegressionMetrics:
    """Metrics for regression."""

    mse: float
    mae: float
    rmse: float
    support: int = 0


@dataclass
class ModelTrainResult:
    """Result of model training."""

    model_type: str
    feature_names: list[str]
    train_metrics: dict[str, Any]
    test_metrics: dict[str, Any]
    model_version: str = "1.0"


def train_outcome_classifier(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_type: str = "logistic",
    feature_names: list[str] | None = None,
) -> tuple[Any, ModelTrainResult]:
    """Train binary classification model for trade outcomes.
    
    Args:
        X_train: Training features (n_train, n_features)
        y_train: Training labels (n_train,) - 1 for win, 0 for loss
        X_test: Test features (n_test, n_features)
        y_test: Test labels (n_test,)
        model_type: "logistic" or "decision_tree"
        feature_names: Optional feature names for reporting
    
    Returns:
        (model, result)
    """
    if not SKLEARN_AVAILABLE:
        raise ImportError("scikit-learn is required for ML models")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    if model_type == "logistic":
        model = LogisticRegression(
            max_iter=1000,
            random_state=42,
            solver="lbfgs",
            class_weight="balanced",
        )
    elif model_type == "decision_tree":
        model = DecisionTreeClassifier(
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            class_weight="balanced",
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    model.fit(X_train_scaled, y_train)
    
    # Evaluate on train set
    y_train_pred = model.predict(X_train_scaled)
    train_metrics = {
        "accuracy": float(accuracy_score(y_train, y_train_pred)),
        "precision": float(precision_score(y_train, y_train_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_train, y_train_pred, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_train, y_train_pred, average="weighted", zero_division=0)),
        "support": len(y_train),
    }
    
    # Add ROC-AUC if binary classification
    if len(np.unique(y_train)) > 1:
        try:
            y_train_proba = model.predict_proba(X_train_scaled)[:, 1]
            train_metrics["roc_auc"] = float(roc_auc_score(y_train, y_train_proba))
        except Exception:
            pass
    
    # Evaluate on test set
    y_test_pred = model.predict(X_test_scaled)
    test_metrics = {
        "accuracy": float(accuracy_score(y_test, y_test_pred)),
        "precision": float(precision_score(y_test, y_test_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_test, y_test_pred, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_test, y_test_pred, average="weighted", zero_division=0)),
        "support": len(y_test),
    }
    
    # Add ROC-AUC if binary classification
    if len(np.unique(y_test)) > 1:
        try:
            y_test_proba = model.predict_proba(X_test_scaled)[:, 1]
            test_metrics["roc_auc"] = float(roc_auc_score(y_test, y_test_proba))
        except Exception:
            pass
    
    # Wrap model with scaler for inference
    class ScaledModel:
        def __init__(self, scaler, model):
            self.scaler = scaler
            self.model = model
        
        def predict(self, X):
            return self.model.predict(self.scaler.transform(X))
        
        def predict_proba(self, X):
            return self.model.predict_proba(self.scaler.transform(X))
    
    wrapped_model = ScaledModel(scaler, model)
    
    result = ModelTrainResult(
        model_type=model_type,
        feature_names=feature_names or [],
        train_metrics=train_metrics,
        test_metrics=test_metrics,
    )
    
    return wrapped_model, result


def train_realized_r_regressor(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_type: str = "decision_tree",
    feature_names: list[str] | None = None,
) -> tuple[Any, ModelTrainResult]:
    """Train regression model for realized R prediction.
    
    Args:
        X_train: Training features (n_train, n_features)
        y_train: Training labels (n_train,) - realized R values
        X_test: Test features (n_test, n_features)
        y_test: Test labels (n_test,)
        model_type: "decision_tree" (logistic regression doesn't apply)
        feature_names: Optional feature names for reporting
    
    Returns:
        (model, result)
    """
    if not SKLEARN_AVAILABLE:
        raise ImportError("scikit-learn is required for ML models")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    if model_type == "decision_tree":
        model = DecisionTreeRegressor(
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
        )
    else:
        raise ValueError(f"Unsupported model type for regression: {model_type}")
    
    model.fit(X_train_scaled, y_train)
    
    # Evaluate on train set
    y_train_pred = model.predict(X_train_scaled)
    train_metrics = {
        "mse": float(mean_squared_error(y_train, y_train_pred)),
        "mae": float(mean_absolute_error(y_train, y_train_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_train, y_train_pred))),
        "support": len(y_train),
    }
    
    # Evaluate on test set
    y_test_pred = model.predict(X_test_scaled)
    test_metrics = {
        "mse": float(mean_squared_error(y_test, y_test_pred)),
        "mae": float(mean_absolute_error(y_test, y_test_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_test_pred))),
        "support": len(y_test),
    }
    
    # Wrap model with scaler for inference
    class ScaledModel:
        def __init__(self, scaler, model):
            self.scaler = scaler
            self.model = model
        
        def predict(self, X):
            return self.model.predict(self.scaler.transform(X))
    
    wrapped_model = ScaledModel(scaler, model)
    
    result = ModelTrainResult(
        model_type=model_type,
        feature_names=feature_names or [],
        train_metrics=train_metrics,
        test_metrics=test_metrics,
    )
    
    return wrapped_model, result


def save_model_metadata(result: ModelTrainResult, path: Path) -> None:
    """Save model metadata to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_type": result.model_type,
        "feature_names": result.feature_names,
        "train_metrics": result.train_metrics,
        "test_metrics": result.test_metrics,
        "model_version": result.model_version,
    }
    path.write_text(json.dumps(payload, indent=2))


def load_model_metadata(path: Path) -> ModelTrainResult:
    """Load model metadata from JSON."""
    payload = json.loads(path.read_text())
    return ModelTrainResult(
        model_type=payload["model_type"],
        feature_names=payload["feature_names"],
        train_metrics=payload["train_metrics"],
        test_metrics=payload["test_metrics"],
        model_version=payload.get("model_version", "1.0"),
    )


def save_model(model: Any, path: Path) -> None:
    """Save model to disk using joblib."""
    if not SKLEARN_AVAILABLE:
        raise ImportError("scikit-learn is required for ML models")
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_model(path: Path) -> Any:
    """Load model from disk using joblib."""
    if not SKLEARN_AVAILABLE:
        raise ImportError("scikit-learn is required for ML models")
    return joblib.load(path)
