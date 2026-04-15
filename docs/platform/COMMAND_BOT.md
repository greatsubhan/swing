# Discord Command Bot

## Purpose

The command bot is a lightweight inbound Discord assistant for operators who need:

- a board directory
- plain-language strategy explanations
- health snapshots
- recent activity summaries
- safe manual scans from inside Discord

It lives in [discord_command_bot.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/discord_command_bot.py).

## Start Command

```bash
python -m signal_platform --env-file .env command-bot --config config/platform.example.json
```

Desktop launcher:

- [RUN_signal_platform_command_bot.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform_command_bot.bat)

PowerShell wrapper:

- [scripts/run_signal_platform_command_bot.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/run_signal_platform_command_bot.ps1)

## Required Environment Variable

Set `DISCORD_BOT_TOKEN` in [\.env.example](/C:/Users/Seeker/Documents/swing-pr1/.env.example).

The bot will not start without that token.

## Discord Developer Portal Requirement

Enable **Message Content Intent** for the bot application. Without it, the bot will connect but it will not see plain text commands like:

- `help`
- `boards`
- `status`
- `scan cwt`

## Supported Commands

| Command | Purpose |
|---|---|
| `help` | Show the command guide |
| `boards` | Show all live boards |
| `strategy <name>` | Explain one board |
| `status` | Show health of all enabled routes |
| `status <name>` | Show one board's health |
| `recent` | Show recent activity for all boards |
| `recent <name>` | Show recent activity for one board |
| `scan` | Run a silent one-shot scan for all enabled routes |
| `scan <name>` | Run a silent one-shot scan for one board |

Prefixes supported:

- `!`
- `/`
- `.`

Examples:

- `boards`
- `strategy cwt`
- `status trend`
- `recent measured`
- `scan`
- `scan cwt`

## Safety Model

The command bot intentionally uses:

- `dispatch="none"` for scan commands
- a shared `asyncio.Lock` so only one Discord-triggered scan runs at a time

That means:

- it reports findings back into Discord
- it does not fire live trade alerts from user-triggered scans
- it avoids overlapping scans when multiple users trigger commands quickly

## Content Sources

The bot builds responses from:

- [command_content.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/command_content.py)
- [runtime.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/runtime.py)
- route output files such as `health_snapshot.json`, `platform_run_summary.json`, and `signal_journal.json`

The `status` and `recent` commands therefore reflect the current state of the bot suite, not hardcoded static text.

## Board Explanations

The command bot maintains a curated board guide with aliases for:

- Measured Drift
- Trend Current
- Cambist With Trend
- Secular Bull SIP

These explanations are intended for users inside Discord who need quick context without opening the repo.

## Troubleshooting

| Problem | Likely cause |
|---|---|
| Bot never connects | `DISCORD_BOT_TOKEN` missing or invalid |
| Bot connects but ignores messages | Message Content Intent not enabled |
| `scan` replies slowly | Route scans are fetching market data synchronously |
| `scan` says another scan is running | The scan lock is protecting the bot from overlapping scan requests |

## Operational Recommendation

Run the command bot alongside the normal shared platform runner, not instead of it. It is an operator interface, not the outbound signal engine.
