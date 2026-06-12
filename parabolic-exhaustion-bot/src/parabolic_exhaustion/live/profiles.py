from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from parabolic_exhaustion.config import (
    BacktestConfig,
    DiscordConfig,
    PaperProfileConfig,
    StrategyConfig,
    load_backtest_config,
    load_discord_config,
    load_strategy_config,
)
from parabolic_exhaustion.discord_bot.publisher import DiscordAlertPublisher
from parabolic_exhaustion.live.engine import LiveSignalEngine


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class LiveProfileRuntime:
    name: str
    profile: PaperProfileConfig
    strategy_config: StrategyConfig
    backtest_config: BacktestConfig
    discord_config: DiscordConfig
    output_dir: Path
    forward_test_log_path: Path


def load_live_profile(
    profile_name: str,
    *,
    project_root: Path = PROJECT_ROOT,
) -> LiveProfileRuntime:
    strategy_config = load_strategy_config(project_root / "config" / "strategy.yaml")
    backtest_config = load_backtest_config(project_root / "config" / "backtest.yaml")
    discord_config = load_discord_config(project_root / "config" / "discord.yaml")

    if profile_name not in strategy_config.paper_profiles:
        available = ", ".join(sorted(strategy_config.paper_profiles))
        raise KeyError(f"Unknown paper profile {profile_name!r}. Available: {available}")

    profile = strategy_config.paper_profiles[profile_name]
    strategy_variant = strategy_config.model_copy(deep=True)
    strategy_variant.market_scope = "multi_asset"
    discord_variant = discord_config.model_copy(deep=True)
    discord_variant.webhook_env_var = profile.discord_webhook_env_var
    discord_variant.channel_name = profile.discord_channel_name

    output_dir = project_root / "output" / profile.output_subdir
    forward_test_log_path = output_dir / profile.forward_test_log_filename
    return LiveProfileRuntime(
        name=profile_name,
        profile=profile,
        strategy_config=strategy_variant,
        backtest_config=backtest_config,
        discord_config=discord_variant,
        output_dir=output_dir,
        forward_test_log_path=forward_test_log_path,
    )


def build_live_engine_for_profile(
    profile_name: str,
    *,
    project_root: Path = PROJECT_ROOT,
    publisher: DiscordAlertPublisher | None = None,
) -> tuple[LiveProfileRuntime, LiveSignalEngine, DiscordAlertPublisher]:
    runtime = load_live_profile(profile_name, project_root=project_root)
    alert_publisher = publisher or DiscordAlertPublisher(
        config=runtime.discord_config,
        log_path=runtime.output_dir / "discord_alert_log.csv",
    )
    engine = LiveSignalEngine(
        strategy_config=runtime.strategy_config,
        backtest_config=runtime.backtest_config,
        discord_config=runtime.discord_config,
        publisher=alert_publisher,
        output_dir=runtime.output_dir,
        profile_name=runtime.name,
        parameter_set_id=runtime.profile.parameter_set_id,
        forward_test_log_path=runtime.forward_test_log_path,
        session_timezone=runtime.profile.session_timezone,
    )
    return runtime, engine, alert_publisher
