from __future__ import annotations

import numpy as np
import pandas as pd

from parabolic_exhaustion.config import ExtensionMode, StrategyConfig
from parabolic_exhaustion.features.daily import engineer_daily_features


EXTENSION_COLUMNS: dict[ExtensionMode, str] = {
    "atr_multiple": "extension_from_base_atr",
    "points": "extension_from_base_points",
    "pct_from_base": "extension_from_base_pct",
    "distance_from_sma20_pct": "distance_from_sma20_pct",
}


def scan_daily_candidates(
    daily_bars_or_features: pd.DataFrame,
    strategy_config: StrategyConfig,
) -> pd.DataFrame:
    """Identify late-stage daily candidates and assign a ranking score."""

    if "extension_from_base_pct" not in daily_bars_or_features.columns:
        data = engineer_daily_features(daily_bars_or_features)
    else:
        data = daily_bars_or_features.copy()

    extension_column = EXTENSION_COLUMNS[strategy_config.filters.extension.mode]
    thresholds = data["symbol"].map(strategy_config.filters.extension.per_symbol_overrides).fillna(
        strategy_config.filters.extension.min_value
    )

    extension_values = data[extension_column].fillna(0.0)
    extension_ok = extension_values >= thresholds
    volume_ok = data["rolling_volume_rank_60d"].fillna(0.0) >= strategy_config.filters.volume_rank_min
    parabolic_ok = data["parabolic_slope_score"].fillna(0.0) >= strategy_config.filters.min_parabolic_slope_score
    near_high_pct = (
        ((data["highest_close_20d"] - data["close"]).clip(lower=0.0) / data["highest_close_20d"].replace(0.0, np.nan))
        .fillna(0.0)
        * 100.0
    )
    near_high_ok = near_high_pct <= strategy_config.filters.near_high_threshold_pct

    data["extension_metric_name"] = extension_column
    data["extension_metric_value"] = extension_values
    data["extension_threshold_value"] = thresholds
    data["daily_candidate"] = extension_ok & volume_ok & parabolic_ok & near_high_ok
    data["parabolic_exhaustion_score"] = _score_candidates(data, strategy_config).round(2)
    data["candidate_reason"] = _build_reason_text(
        data,
        extension_ok=extension_ok,
        volume_ok=volume_ok,
        parabolic_ok=parabolic_ok,
        near_high_ok=near_high_ok,
    )
    data["candidate_rank"] = (
        data.groupby("timestamp")["parabolic_exhaustion_score"].rank(ascending=False, method="dense")
    )
    return data


def _score_candidates(data: pd.DataFrame, strategy_config: StrategyConfig) -> pd.Series:
    tolerance = max(strategy_config.filters.round_number_tolerance_pct, 0.01)
    thresholds = data["extension_threshold_value"].replace(0.0, np.nan)
    extension_component = ((data["extension_metric_value"] / thresholds) / 2.0).clip(0.0, 1.0)
    acceleration_component = (data["parabolic_slope_score"].fillna(0.0) / 100.0).clip(0.0, 1.0)
    volume_component = data["rolling_volume_rank_60d"].fillna(0.0).clip(0.0, 1.0)
    round_component = (1.0 - (data["round_number_proximity"].fillna(tolerance) / tolerance)).clip(0.0, 1.0)
    intraday_structure_component = _optional_component(
        data,
        ["lower_high_flag", "lower_low_flag"],
    )
    vwap_component = _optional_component(
        data,
        ["vwap_cross_down_flag", "vwap_reclaim_fail_flag"],
    )

    score = (
        extension_component * 25.0
        + acceleration_component * 20.0
        + volume_component * 15.0
        + round_component * 5.0
        + intraday_structure_component * 15.0
        + vwap_component * 20.0
    )
    return score.clip(0.0, 100.0)


def _optional_component(data: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not all(column in data.columns for column in columns):
        return pd.Series(np.zeros(len(data)), index=data.index, dtype=float)
    values = sum(data[column].fillna(False).astype(float) for column in columns)
    return (values / len(columns)).clip(0.0, 1.0)


def _build_reason_text(
    data: pd.DataFrame,
    *,
    extension_ok: pd.Series,
    volume_ok: pd.Series,
    parabolic_ok: pd.Series,
    near_high_ok: pd.Series,
) -> pd.Series:
    reasons: list[str] = []
    for index, row in data.iterrows():
        row_reasons: list[str] = []
        if extension_ok.iloc[index]:
            row_reasons.append(
                f"{row['extension_metric_name']} {row['extension_metric_value']:.2f} >= {row['extension_threshold_value']:.2f}"
            )
        if volume_ok.iloc[index]:
            row_reasons.append(f"volume rank {row['rolling_volume_rank_60d']:.2f}")
        if parabolic_ok.iloc[index]:
            row_reasons.append(f"parabolic slope {row['parabolic_slope_score']:.1f}")
        if near_high_ok.iloc[index]:
            row_reasons.append("holding near 20-day highs")
        reasons.append("; ".join(row_reasons))
    return pd.Series(reasons, index=data.index)
