from __future__ import annotations

from pathlib import Path

from parabolic_exhaustion.backtest.historical_validation import PROJECT_ROOT
from parabolic_exhaustion.backtest.historical_validation_flow import run_flow_historical_validation
from parabolic_exhaustion.config import load_assets_config, load_backtest_config, load_strategy_config


FLOW_OPEN_OUTPUT_ROOT = PROJECT_ROOT / "output" / "flow_validation_open"
FLOW_OPEN_PERFORMANCE_PATH = PROJECT_ROOT / "performance_matrix_flow_open.csv"


def main() -> None:
    strategy_config = load_strategy_config(PROJECT_ROOT / "config" / "strategy.yaml")
    backtest_config = load_backtest_config(PROJECT_ROOT / "config" / "backtest.yaml")
    assets_config = load_assets_config(PROJECT_ROOT / "config" / "assets.yaml")
    performance_matrix = run_flow_historical_validation(
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        assets_config=assets_config,
        parameter_config_attr="flow_open_validation_parameter_sets",
        output_root=FLOW_OPEN_OUTPUT_ROOT,
        performance_matrix_path=FLOW_OPEN_PERFORMANCE_PATH,
        output_suffix="flow_open",
    )
    print(f"Wrote {len(performance_matrix)} Strategy B opening-window rows to {FLOW_OPEN_PERFORMANCE_PATH}")


if __name__ == "__main__":
    main()
