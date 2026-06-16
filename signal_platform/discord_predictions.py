"""Enhanced Discord integration with ML predictions."""
from __future__ import annotations

from typing import Any

from .signal_scoring import create_signal_score_summary
from .models import PlatformSignal


def format_signal_with_prediction(
    signal: PlatformSignal,
    score: dict[str, Any],
) -> str:
    """Format signal notification with ML prediction.
    
    Args:
        signal: The platform signal
        score: Score dict from signal_scoring module
    
    Returns:
        Formatted message for Discord
    """
    lines = []
    
    # Signal header
    lines.append(f"📊 **{signal.symbol}** | {signal.quality_grade or 'N/A'}")
    
    # Signal details
    lines.append(f"Entry: {signal.entry:.5f} | SL: {signal.stop_loss:.5f} | TP: {signal.target_1:.5f}")
    
    # Risk/Reward
    if signal.risk_reward is not None:
        lines.append(f"Risk/Reward: {signal.risk_reward:.2f}:1")
    
    # ML Predictions if available
    if score.get("score_computed"):
        lines.append("\n**🤖 ML Predictions:**")
        
        # Outcome prediction
        outcome_pred = score.get("outcome_prediction", {})
        if outcome_pred.get("available"):
            pred_text = outcome_pred.get("prediction_text", "unknown")
            conf = outcome_pred.get("confidence", 0.5)
            emoji = "✅" if pred_text == "win" else "❌"
            lines.append(f"{emoji} Outcome: **{pred_text.upper()}** ({conf:.1%} confidence)")
        
        # Realized R prediction
        realized_r_pred = score.get("realized_r_prediction", {})
        if realized_r_pred.get("available"):
            expected_r = realized_r_pred.get("prediction_rounded", 0.0)
            lines.append(f"💰 Expected R: **{expected_r:+.2f}R**")
        
        # Overall confidence
        lines.append(f"📈 ML Confidence: {score.get('ml_confidence', 0.5):.1%}")
    
    return "\n".join(lines)


def format_signal_batch_summary(
    signals: list[PlatformSignal],
    scores: list[dict[str, Any]],
) -> str:
    """Format summary of multiple signals with predictions.
    
    Args:
        signals: List of signals
        scores: List of corresponding scores
    
    Returns:
        Formatted batch summary for Discord
    """
    lines = []
    
    # Summary header
    lines.append(f"📈 **SIGNAL BATCH** - {len(signals)} signal(s)")
    
    # Compute summary statistics
    summary = create_signal_score_summary(scores)
    
    if summary.get("models_computed", 0) > 0:
        lines.append(f"\n**ML Analysis:**")
        lines.append(f"Models computed: {summary['models_computed']}/{summary['total_signals']}")
        lines.append(f"Avg confidence: {summary['avg_confidence']:.1%}")
        
        if "predicted_win_ratio" in summary:
            win_ratio = summary["predicted_win_ratio"] * 100
            lines.append(f"Predicted win ratio: {win_ratio:.0f}%")
        
        if "avg_expected_r" in summary:
            lines.append(f"Avg expected R: {summary['avg_expected_r']:+.2f}R")
    
    # Individual signals (brief)
    lines.append(f"\n**Signals:**")
    for signal, score in zip(signals, scores):
        status = "🤖" if score.get("score_computed") else "⚠️"
        outcome_pred = score.get("outcome_prediction", {})
        outcome_emoji = "✅" if outcome_pred.get("prediction_text") == "win" else "❌"
        lines.append(f"{status} {signal.symbol} {outcome_emoji}")
    
    return "\n".join(lines)


def format_report_with_predictions(
    report_text: str,
    prediction_summary: dict[str, Any] | None = None,
) -> str:
    """Enhance a report with prediction performance summary.
    
    Args:
        report_text: Original report text
        prediction_summary: Prediction evaluation summary
    
    Returns:
        Enhanced report with predictions
    """
    if prediction_summary is None or not prediction_summary.get("closed_trades", 0):
        return report_text
    
    # Add prediction section
    lines = [report_text]
    lines.append("\n" + "=" * 40)
    lines.append("🤖 **ML MODEL PERFORMANCE**")
    lines.append("=" * 40)
    
    outcome = prediction_summary.get("outcome_prediction", {})
    if outcome.get("evaluated", 0) > 0:
        acc = outcome["accuracy"] * 100
        lines.append(f"Outcome Classifier Accuracy: {acc:.1f}%")
        lines.append(f"  - Correct: {outcome['correct']}/{outcome['evaluated']}")
    
    realized_r = prediction_summary.get("realized_r_prediction", {})
    if realized_r.get("evaluated", 0) > 0:
        mae = realized_r["mean_absolute_error"]
        lines.append(f"Realized R MAE: {mae:.3f}R")
    
    return "\n".join(lines)


def create_prediction_confidence_badge(confidence: float) -> str:
    """Create a visual confidence badge for Discord.
    
    Args:
        confidence: Confidence value (0-1)
    
    Returns:
        Formatted badge string
    """
    if confidence >= 0.9:
        return "🟢🟢🟢 Very High"
    elif confidence >= 0.7:
        return "🟢🟢 High"
    elif confidence >= 0.6:
        return "🟡🟡 Medium"
    elif confidence >= 0.5:
        return "🟡 Low"
    else:
        return "🔴 Very Low"
