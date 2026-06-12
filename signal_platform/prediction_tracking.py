"""Track and evaluate ML model prediction performance."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .journal import JournalEntry


def record_prediction(
    setup_id: str,
    outcome_prediction: dict[str, Any],
    realized_r_prediction: dict[str, Any],
    path: Path | str,
) -> None:
    """Record a model prediction for later evaluation.
    
    Args:
        setup_id: Signal setup ID
        outcome_prediction: Outcome prediction dict from model
        realized_r_prediction: Realized R prediction dict from model
        path: Path to predictions log file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    record = {
        "setup_id": setup_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "outcome_prediction": outcome_prediction,
        "realized_r_prediction": realized_r_prediction,
    }
    
    # Append to JSONL file
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def load_predictions(path: Path | str) -> list[dict[str, Any]]:
    """Load recorded predictions from JSONL file.
    
    Args:
        path: Path to predictions log file
    
    Returns:
        List of prediction records
    """
    path = Path(path)
    if not path.exists():
        return []
    
    predictions = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    predictions.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    
    return predictions


def match_predictions_with_outcomes(
    predictions: list[dict[str, Any]],
    entries: list[JournalEntry],
) -> list[dict[str, Any]]:
    """Match recorded predictions with actual journal outcomes.
    
    Args:
        predictions: List of prediction records
        entries: List of journal entries with outcomes
    
    Returns:
        List of matched prediction/outcome pairs
    """
    entry_by_setup = {e.setup_id: e for e in entries}
    matched = []
    
    for pred in predictions:
        setup_id = pred.get("setup_id")
        entry = entry_by_setup.get(setup_id)
        
        if entry is None:
            continue
        
        match = {
            "setup_id": setup_id,
            "prediction_timestamp": pred.get("timestamp_utc"),
            "outcome_prediction": pred.get("outcome_prediction"),
            "realized_r_prediction": pred.get("realized_r_prediction"),
            "actual_outcome": entry.outcome,
            "actual_realized_r": entry.realized_r(),
            "journal_entry_status": entry.status,
        }
        matched.append(match)
    
    return matched


def evaluate_predictions(matched: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate model prediction performance.
    
    Args:
        matched: List of matched prediction/outcome pairs
    
    Returns:
        Evaluation metrics
    """
    if not matched:
        return {
            "total_predictions": 0,
            "evaluated_count": 0,
        }
    
    # Filter to closed trades
    closed = [m for m in matched if m.get("actual_realized_r") is not None]
    
    if not closed:
        return {
            "total_predictions": len(matched),
            "evaluated_count": 0,
        }
    
    # Outcome prediction evaluation
    outcome_correct = 0
    outcome_evaluated = 0
    outcome_preds_made = 0
    outcome_pred_dist = {"predicted_wins": 0, "predicted_losses": 0}
    
    for match in closed:
        outcome_pred = match.get("outcome_prediction") or {}
        if not outcome_pred.get("available"):
            continue
        
        outcome_evaluated += 1
        outcome_preds_made += 1
        
        predicted = outcome_pred.get("prediction")
        actual = 1 if match.get("actual_realized_r", 0) > 0 else 0
        
        if predicted == actual:
            outcome_correct += 1
        
        if predicted == 1:
            outcome_pred_dist["predicted_wins"] += 1
        else:
            outcome_pred_dist["predicted_losses"] += 1
    
    # Realized R prediction evaluation
    realized_r_errors = []
    realized_r_evaluated = 0
    
    for match in closed:
        realized_r_pred = match.get("realized_r_prediction") or {}
        if not realized_r_pred.get("available"):
            continue
        
        realized_r_evaluated += 1
        
        predicted_r = realized_r_pred.get("prediction", 0.0)
        actual_r = match.get("actual_realized_r", 0.0)
        
        error = abs(predicted_r - actual_r)
        realized_r_errors.append(error)
    
    evaluation = {
        "total_predictions": len(matched),
        "closed_trades": len(closed),
        "outcome_prediction": {
            "evaluated": outcome_evaluated,
            "accuracy": outcome_correct / outcome_evaluated if outcome_evaluated > 0 else 0.0,
            "correct": outcome_correct,
            "distribution": outcome_pred_dist,
        },
        "realized_r_prediction": {
            "evaluated": realized_r_evaluated,
            "mean_absolute_error": sum(realized_r_errors) / len(realized_r_errors) if realized_r_errors else 0.0,
            "max_error": max(realized_r_errors) if realized_r_errors else 0.0,
            "min_error": min(realized_r_errors) if realized_r_errors else 0.0,
        },
    }
    
    return evaluation


def generate_prediction_report(
    evaluation: dict[str, Any],
) -> str:
    """Generate human-readable prediction performance report.
    
    Args:
        evaluation: Evaluation metrics dict
    
    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=== MODEL PREDICTION PERFORMANCE ===")
    lines.append(f"Total predictions: {evaluation.get('total_predictions', 0)}")
    lines.append(f"Closed trades matched: {evaluation.get('closed_trades', 0)}")
    
    # Outcome prediction report
    outcome = evaluation.get("outcome_prediction", {})
    if outcome.get("evaluated", 0) > 0:
        acc = outcome["accuracy"] * 100
        lines.append(f"\nOutcome Classifier:")
        lines.append(f"  Accuracy: {acc:.1f}% ({outcome['correct']}/{outcome['evaluated']})")
        dist = outcome.get("distribution", {})
        lines.append(f"  Predicted wins: {dist.get('predicted_wins', 0)}")
        lines.append(f"  Predicted losses: {dist.get('predicted_losses', 0)}")
    
    # Realized R prediction report
    realized_r = evaluation.get("realized_r_prediction", {})
    if realized_r.get("evaluated", 0) > 0:
        mae = realized_r["mean_absolute_error"]
        lines.append(f"\nRealized R Regressor:")
        lines.append(f"  Mean Absolute Error: {mae:.3f}R")
        lines.append(f"  Max Error: {realized_r['max_error']:.3f}R")
        lines.append(f"  Min Error: {realized_r['min_error']:.3f}R")
    
    return "\n".join(lines)
