from pathlib import Path

from parabolic_exhaustion.config import (
    load_assets_config,
    load_backtest_config,
    load_strategy_config,
)


def test_load_strategy_config() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_strategy_config(root / "config" / "strategy.yaml")

    assert config.provider == "oanda"
    assert config.market_scope == "multi_asset"
    assert config.session_scope == "london_new_york"
    assert config.filters.extension.mode == "atr_multiple"
    assert config.signal_timeframe == "1m"
    assert config.kill_zones.london.enabled is True
    assert config.kill_zones.new_york.enabled is True
    assert config.kill_zones.overlap.enabled is True
    assert "NAS100_PARABOLIC_PAPER" in config.paper_profiles
    profile = config.paper_profiles["NAS100_PARABOLIC_PAPER"]
    assert profile.markets == ["NAS100_USD"]
    assert profile.parameter_set_id == "idx_ps07_baseline_on"
    assert profile.discord_channel_name == "nas100-parabolic-paper"


def test_load_assets_and_backtest_configs() -> None:
    root = Path(__file__).resolve().parents[2]
    assets = load_assets_config(root / "config" / "assets.yaml")
    backtest = load_backtest_config(root / "config" / "backtest.yaml")

    assert assets.selection_mode == "scanner"
    assert len(assets.instruments) == 7
    assert backtest.parameter_grid.signal_timeframes == ["1m", "5m"]
    assert backtest.replay.use_kill_zones_for_entry is True
