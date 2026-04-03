"""Dispatchers for posting signals to external channels."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib import error, request

from .models import PlatformSignal


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


def discord_payload(signal: PlatformSignal, username: str = "Signal Bot") -> dict[str, object]:
    rr_text = f"{signal.risk_reward:.2f}" if signal.risk_reward is not None else "n/a"
    entry_text = f"{signal.entry:.5f}" if signal.entry is not None else "n/a"
    stop_text = f"{signal.stop_loss:.5f}" if signal.stop_loss is not None else "n/a"
    target_text = f"{signal.target_1:.5f}" if signal.target_1 is not None else "n/a"
    score_text = (
        f"{signal.quality_score}/{signal.quality_grade}"
        if signal.quality_score is not None and signal.quality_grade is not None
        else "n/a"
    )
    title_side = signal.side.upper()
    return {
        "username": username,
        "content": f"[{signal.strategy_name}] {signal.symbol} {signal.timeframe.upper()} {title_side}",
        "embeds": [
            {
                "title": f"{signal.symbol} {signal.timeframe.upper()} {title_side}",
                "description": signal.summary,
                "color": _discord_color(signal),
                "fields": [
                    {"name": "Strategy", "value": signal.strategy_name, "inline": True},
                    {"name": "RR", "value": rr_text, "inline": True},
                    {"name": "Score", "value": score_text, "inline": True},
                    {"name": "Entry", "value": entry_text, "inline": True},
                    {"name": "Stop", "value": stop_text, "inline": True},
                    {"name": "Target", "value": target_text, "inline": True},
                    {"name": "Setup ID", "value": signal.setup_id, "inline": False},
                ],
                "footer": {"text": f"{signal.strategy_id} | {signal.asset_class}"},
                "timestamp": signal.timestamp,
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


def send_discord_webhook(webhook_url: str, signal: PlatformSignal, username: str = "Signal Bot") -> None:
    payload = discord_payload(signal, username=username)
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
