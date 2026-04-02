"""Config-driven signal platform runtime."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .dispatchers import load_sent_setup_ids, new_signals_only, save_sent_setup_ids, send_discord_webhook
from .models import PlatformSignal
from .registry import get_strategy
from .strategies import StrategyScanRequest


@dataclass
class StrategyRoute:
    strategy_id: str
    enabled: bool
    watchlist: str
    granularity: str
    higher_timeframe: str
    dispatch: str
    discord_webhook_url: str | None
    output_dir: str
    state_file: str
    use_market_profile: bool = True


@dataclass
class PlatformConfig:
    oanda_environment: str
    oanda_price: str
    routes: list[StrategyRoute]


def _resolve_env_placeholders(value: object) -> object:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.getenv(env_name, "")
    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}
    return value


def load_platform_config(path: str | Path) -> PlatformConfig:
    payload = _resolve_env_placeholders(json.loads(Path(path).read_text()))
    routes = [
        StrategyRoute(
            strategy_id=str(route["strategy_id"]),
            enabled=bool(route.get("enabled", True)),
            watchlist=str(route["watchlist"]),
            granularity=str(route.get("granularity", "H4")),
            higher_timeframe=str(route.get("higher_timeframe", "1d")),
            dispatch=str(route.get("dispatch", "none")),
            discord_webhook_url=route.get("discord_webhook_url"),
            output_dir=str(route.get("output_dir", f"platform_output/{route['strategy_id']}")),
            state_file=str(route.get("state_file", f"platform_output/{route['strategy_id']}/sent_state.json")),
            use_market_profile=bool(route.get("use_market_profile", True)),
        )
        for route in payload.get("routes", [])
    ]
    return PlatformConfig(
        oanda_environment=str(payload.get("oanda_environment", "practice")),
        oanda_price=str(payload.get("oanda_price", "M")),
        routes=routes,
    )


def run_route(route: StrategyRoute, environment: str, price: str, token: str | None) -> dict[str, object]:
    strategy = get_strategy(route.strategy_id)
    output_dir = Path(route.output_dir)
    scan_request = StrategyScanRequest(
        watchlist=route.watchlist,
        granularity=route.granularity,
        higher_timeframe=route.higher_timeframe,
        environment=environment,
        token=token,
        price=price,
        output_dir=output_dir,
        use_market_profile=route.use_market_profile,
    )
    result = strategy.scan(scan_request)
    sent_setup_ids = load_sent_setup_ids(route.state_file)
    fresh_signals = new_signals_only(result.signals, sent_setup_ids)

    delivered: list[PlatformSignal] = []
    if route.dispatch == "discord":
        if not route.discord_webhook_url:
            raise ValueError(f"Route {route.strategy_id} uses discord dispatch but has no webhook URL.")
        for signal in fresh_signals:
            send_discord_webhook(route.discord_webhook_url, signal, username=f"{strategy.strategy_name} Bot")
            delivered.append(signal)
            sent_setup_ids.add(signal.setup_id)
        save_sent_setup_ids(route.state_file, sent_setup_ids)

    summary = {
        "strategy_id": route.strategy_id,
        "strategy_name": strategy.strategy_name,
        "watchlist": route.watchlist,
        "rows": len(result.rows),
        "signals_found": len(result.signals),
        "fresh_signals": len(fresh_signals),
        "delivered": len(delivered),
        "dispatch": route.dispatch,
        "output_dir": str(output_dir),
        "state_file": route.state_file,
    }
    summary_path = output_dir / "platform_run_summary.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary


def run_platform_config(config_path: str | Path, token: str | None) -> list[dict[str, object]]:
    config = load_platform_config(config_path)
    results: list[dict[str, object]] = []
    for route in config.routes:
        if not route.enabled:
            continue
        results.append(run_route(route, environment=config.oanda_environment, price=config.oanda_price, token=token))
    return results
