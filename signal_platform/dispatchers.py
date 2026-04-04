"""Dispatchers for posting signals to external channels."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib import error, request

from .models import JournalEntry, PlatformSignal

DEFAULT_BRAND_NAME = "Signal Platform"
SIGNAL_DESK_NAME = "Signal Desk"
REPORTS_NAME = "Signal Review"


def load_sent_setup_ids(state_path: str | Path) -> set[str]:
    path = Path(state_path)
    if not path.exists():
        return set()
    data = json.loads(path.read_text() or "{}")
    return {str(value) for value in data.get("sent_setup_ids", [])}


def save_sent_setup_ids(state_path: str | Path, setup_ids: set[str]) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sent_setup_ids": sorted(setup_ids)}, indent=2))


def new_signals_only(signals: list[PlatformSignal], sent_setup_ids: set[str]) -> list[PlatformSignal]:
    return [signal for signal in signals if signal.setup_id not in sent_setup_ids]


def _discord_color(signal: PlatformSignal) -> int:
    if signal.side.lower() == "long":
        return 0x2ECC71
    if signal.side.lower() == "short":
        return 0xE74C3C
    return 0x3498DB


def _signal_badge(side: str) -> str:
    return "LONG" if side.lower() == "long" else "SHORT" if side.lower() == "short" else "SETUP"


def _signal_emoji(side: str) -> str:
    return "🟢" if side.lower() == "long" else "🔴" if side.lower() == "short" else "🔵"


def discord_payload(signal: PlatformSignal, username: str = SIGNAL_DESK_NAME) -> dict[str, object]:
    rr_text = f"{signal.risk_reward:.2f}" if signal.risk_reward is not None else "n/a"
    entry_text = f"{signal.entry:.5f}" if signal.entry is not None else "n/a"
    stop_text = f"{signal.stop_loss:.5f}" if signal.stop_loss is not None else "n/a"
    target_text = f"{signal.target_1:.5f}" if signal.target_1 is not None else "n/a"
    score_text = (
        f"{signal.quality_score}/{signal.quality_grade}"
        if signal.quality_score is not None and signal.quality_grade is not None
        else "n/a"
    )
    stats = signal.raw_signal.get("stats_snapshot", {})
    history_text = (
        f"Signals {stats.get('total_signals', 0)} | TP {stats.get('tp_hits', 0)} | "
        f"SL {stats.get('sl_hits', 0)} | Open {stats.get('open_signals', 0)} | "
        f"Net {stats.get('total_realized_r', 0.0):.2f}R"
        if stats
        else "Signals n/a"
    )
    title_side = _signal_badge(signal.side)
    signal_emoji = _signal_emoji(signal.side)
    return {
        "username": username,
        "content": f"{signal_emoji} [{signal.strategy_name}] {signal.symbol} {signal.timeframe.upper()} {title_side}",
        "embeds": [
            {
                "title": f"{signal_emoji} {signal.symbol} {signal.timeframe.upper()} {title_side}",
                "description": f"🧠 Setup thesis\n{signal.summary}",
                "color": _discord_color(signal),
                "fields": [
                    {"name": "🧭 Strategy", "value": signal.strategy_name, "inline": True},
                    {"name": "🎯 Risk/Reward", "value": rr_text, "inline": True},
                    {"name": "📊 Signal Score", "value": score_text, "inline": True},
                    {"name": "📍 Entry", "value": entry_text, "inline": True},
                    {"name": "🛑 Stop", "value": stop_text, "inline": True},
                    {"name": "🏁 Target", "value": target_text, "inline": True},
                    {"name": "🪞 Live Record", "value": history_text, "inline": False},
                    {"name": "🆔 Setup ID", "value": signal.setup_id, "inline": False},
                ],
                "footer": {"text": f"{signal.strategy_name} ✦ {signal.asset_class} ✦ {signal.strategy_id}"},
                "timestamp": signal.timestamp,
            }
        ],
    }


def outcome_payload(entry: JournalEntry, username: str = SIGNAL_DESK_NAME) -> dict[str, object]:
    outcome = entry.outcome or "closed"
    outcome_label = "TP hit" if outcome == "tp_hit" else "SL hit" if outcome == "sl_hit" else outcome.replace("_", " ").title()
    hold_hours = entry.hold_hours()
    hold_text = f"{hold_hours:.1f}h" if hold_hours is not None else "n/a"
    color = 0x2ECC71 if outcome == "tp_hit" else 0xE74C3C if outcome == "sl_hit" else 0x3498DB
    outcome_tag = "TP" if outcome == "tp_hit" else "SL" if outcome == "sl_hit" else "CLOSED"
    outcome_emoji = "✅" if outcome == "tp_hit" else "🛑" if outcome == "sl_hit" else "📌"
    return {
        "username": username,
        "content": f"{outcome_emoji} [{entry.strategy_name}] {entry.symbol} {entry.timeframe.upper()} {outcome_label}",
        "embeds": [
            {
                "title": f"{outcome_emoji} {entry.symbol} {entry.timeframe.upper()} {outcome_label}",
                "description": f"{outcome_tag} outcome recorded for setup `{entry.setup_id}`.",
                "color": color,
                "fields": [
                    {"name": "↕️ Side", "value": entry.side.upper(), "inline": True},
                    {"name": "📌 Outcome", "value": outcome_label, "inline": True},
                    {"name": "💵 Exit Price", "value": f"{entry.exit_price:.5f}" if entry.exit_price is not None else "n/a", "inline": True},
                    {"name": "⏱️ Signal Time", "value": entry.signal_timestamp, "inline": False},
                    {"name": "🕓 Outcome Time", "value": entry.outcome_timestamp or "n/a", "inline": False},
                    {"name": "⌛ Hold Time", "value": hold_text, "inline": True},
                    {"name": "🧮 Bars Checked", "value": str(entry.bars_checked), "inline": True},
                ],
                "footer": {"text": f"{entry.strategy_name} outcome log"},
            }
        ],
    }


def simple_text_payload(content: str, username: str = SIGNAL_DESK_NAME) -> dict[str, object]:
    return {
        "username": username,
        "content": content,
    }


def report_payload(
    summary: dict[str, object],
    username: str = REPORTS_NAME,
    strategy_name: str = DEFAULT_BRAND_NAME,
) -> dict[str, object]:
    period_label = str(summary["period_label"])
    title_prefix = "Weekly" if period_label.lower().startswith("weekly") else "Monthly"
    title_emoji = "🗓️" if title_prefix == "Weekly" else "📅"
    tp_list = "\n".join(f"- {item}" for item in summary["tp_list"]) or "- none"
    sl_list = "\n".join(f"- {item}" for item in summary["sl_list"]) or "- none"
    open_list = "\n".join(f"- {item}" for item in summary["open_list"]) or "- none"
    return {
        "username": username,
        "content": f"{title_emoji} {title_prefix} review",
        "embeds": [
            {
                "title": f"{title_emoji} {period_label} Report Card",
                "description": "A concise review of signal flow, net result, and outstanding exposure.",
                "color": 0x5865F2,
                "fields": [
                    {"name": "📬 Signals", "value": str(summary["signals_sent"]), "inline": True},
                    {"name": "✅ TP Hits", "value": str(summary["tp_hits"]), "inline": True},
                    {"name": "🛑 SL Hits", "value": str(summary["sl_hits"]), "inline": True},
                    {"name": "🟡 Still Open", "value": str(summary["open_count"]), "inline": True},
                    {"name": "💰 Net Realized", "value": f"{summary['total_realized_r']:.2f}R", "inline": True},
                    {"name": "📈 Avg Closed Trade", "value": str(summary["avg_closed_r_text"]), "inline": True},
                    {"name": "⏳ Avg Hold", "value": str(summary["avg_hold_text"]), "inline": True},
                    {"name": "🏆 TP List", "value": tp_list, "inline": False},
                    {"name": "⚠️ SL List", "value": sl_list, "inline": False},
                    {"name": "🧷 Open List", "value": open_list, "inline": False},
                ],
                "footer": {"text": f"{strategy_name} review desk"},
            }
        ],
    }


def _post_json_external(webhook_url: str, payload: dict[str, object]) -> bool:
    body = json.dumps(payload)

    if sys.platform.startswith("win"):
        command = (
            "$payload = [Console]::In.ReadToEnd(); "
            "Invoke-RestMethod -Uri $env:WEBHOOK_URL -Method Post -Body $payload -ContentType 'application/json' | Out-Null"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            input=body,
            text=True,
            capture_output=True,
            env={**os.environ, "WEBHOOK_URL": webhook_url},
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Discord webhook via PowerShell failed: {stderr}")
        return True

    curl_path = shutil.which("curl")
    if curl_path:
        completed = subprocess.run(
            [
                curl_path,
                "-sS",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
                webhook_url,
            ],
            input=body,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Discord webhook via curl failed: {stderr}")
        return True

    return False


def _send_payload(webhook_url: str, payload: dict[str, object]) -> None:
    if _post_json_external(webhook_url, payload):
        return

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "signal-platform/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            status = response.getcode()
            if status < 200 or status >= 300:
                raise RuntimeError(f"Discord webhook returned status {status}")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord webhook failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Discord webhook request failed: {exc.reason}") from exc


def send_discord_webhook(webhook_url: str, signal: PlatformSignal, username: str = SIGNAL_DESK_NAME) -> None:
    _send_payload(webhook_url, discord_payload(signal, username=username))


def send_discord_outcome(webhook_url: str, entry: JournalEntry, username: str = SIGNAL_DESK_NAME) -> None:
    _send_payload(webhook_url, outcome_payload(entry, username=username))


def send_discord_text(webhook_url: str, content: str, username: str = SIGNAL_DESK_NAME) -> None:
    _send_payload(webhook_url, simple_text_payload(content, username=username))


def send_discord_report(
    webhook_url: str,
    summary: dict[str, object],
    username: str = REPORTS_NAME,
    strategy_name: str = DEFAULT_BRAND_NAME,
) -> None:
    _send_payload(webhook_url, report_payload(summary, username=username, strategy_name=strategy_name))
