"""Lightweight inbound Discord bot for strategy/help/status/recent/scan commands."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .command_content import (
    CommandCard,
    build_boards_card,
    build_help_card,
    build_ladder_card,
    build_recent_card,
    build_scan_card,
    build_status_card,
    build_strategy_card_response,
    parse_command_message,
)
from .runtime import load_platform_config, run_configured_route


async def run_discord_command_bot(*, token: str, config_path: str | Path) -> None:
    try:
        import discord  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError(
            "discord.py is not installed. Run `pip install -r requirements.txt` before starting the command bot."
        ) from exc

    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True

    client = discord.Client(intents=intents)
    resolved_config = str(config_path)
    scan_lock = asyncio.Lock()

    async def _send_card(channel, card: CommandCard) -> None:  # noqa: ANN001
        embed = discord.Embed(
            title=card.title,
            description=card.description,
            color=card.color,
        )
        for field in card.fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)
        await channel.send(embed=embed)

    def _resolve_route_id(argument: str | None) -> str | None:
        from .command_content import resolve_strategy_card  # local import to keep startup light

        if not argument:
            return None
        card = resolve_strategy_card(argument)
        if card is not None:
            return card.strategy_id
        normalized = argument.strip().lower().replace("-", "_").replace(" ", "_")
        return normalized or None

    def _scan_all_routes() -> CommandCard:
        config = load_platform_config(resolved_config)
        summaries: list[dict[str, object]] = []
        for route in config.routes:
            if not route.enabled:
                continue
            summary = run_configured_route(
                resolved_config,
                strategy_id=route.strategy_id,
                token=os.getenv("OANDA_API_TOKEN"),
                dispatch="none",
                catch_up_hours=route.catch_up_hours,
            )
            summaries.append(summary)
        return build_scan_card(summaries)

    def _scan_one_route(argument: str) -> CommandCard:
        route_id = _resolve_route_id(argument)
        if not route_id:
            return CommandCard(
                title="Scan Not Started",
                description="I couldn't tell which board you wanted to scan.",
                color=0xE67E22,
            )
        try:
            summary = run_configured_route(
                resolved_config,
                strategy_id=route_id,
                token=os.getenv("OANDA_API_TOKEN"),
                dispatch="none",
            )
        except Exception as exc:
            return CommandCard(
                title="Scan Failed",
                description=f"Scan failed for `{argument}`: {exc}",
                color=0xE74C3C,
            )
        return build_scan_card([summary], query=argument)

    @client.event
    async def on_ready() -> None:
        print(f"Discord command bot connected as {client.user}", flush=True)

    @client.event
    async def on_message(message) -> None:  # noqa: ANN001
        if message.author == client.user or getattr(message.author, "bot", False):
            return
        command, argument = parse_command_message(str(message.content or ""))
        if command is None:
            return
        if command == "help":
            await _send_card(message.channel, build_help_card())
            return
        if command == "boards":
            await _send_card(message.channel, build_boards_card())
            return
        if command == "strategy":
            await _send_card(message.channel, build_strategy_card_response(argument))
            return
        if command == "status":
            await _send_card(message.channel, build_status_card(resolved_config, argument))
            return
        if command == "recent":
            await _send_card(message.channel, build_recent_card(resolved_config, argument))
            return
        if command == "ladder":
            await _send_card(message.channel, build_ladder_card(resolved_config, argument))
            return
        if command == "scan":
            if scan_lock.locked():
                await _send_card(
                    message.channel,
                    CommandCard(
                        title="Scan Already Running",
                        description="Another scan is already in progress. Give me a moment and try again.",
                        color=0xE67E22,
                    ),
                )
                return
            async with scan_lock:
                await _send_card(
                    message.channel,
                    CommandCard(
                        title="Running Scan",
                        description="I'm running a silent one-shot scan now. I'll report back with what I find, without firing live trade alerts.",
                    ),
                )
                if argument:
                    response = await asyncio.to_thread(_scan_one_route, argument)
                else:
                    response = await asyncio.to_thread(_scan_all_routes)
                await _send_card(message.channel, response)
            return

    await client.start(token)


def run_discord_command_bot_sync(*, token: str | None, config_path: str | Path) -> None:
    resolved_token = token or os.getenv("DISCORD_BOT_TOKEN")
    if not resolved_token:
        raise RuntimeError("No Discord bot token found. Set DISCORD_BOT_TOKEN in .env or pass --bot-token.")
    asyncio.run(run_discord_command_bot(token=resolved_token, config_path=config_path))
