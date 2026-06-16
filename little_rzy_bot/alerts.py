"""Alert message formatting."""
from .data_models import Signal


def concise_alert(signal: Signal) -> str:
    return (
        f"{signal.symbol} {signal.timeframe.upper()} {signal.signal_type.upper()} - "
        f"Little RZY continuation setup triggered. Entry {signal.entry:.4f}, "
        f"stop {signal.stop_loss:.4f}, target {signal.target_1:.4f}, "
        f"RR {signal.risk_reward:.2f}, score {signal.quality_score}/{signal.quality_grade}, "
        f"session {signal.session or 'n/a'}, profile {signal.profile_name or 'baseline'}."
    )
