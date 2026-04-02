"""Dispatchers for posting signals to external channels."""
from __future__ import annotations

import json
from pathlib import Path
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


def send_discord_webhook(webhook_url: str, signal: PlatformSignal, username: str = "Signal Bot") -> None:
    payload = {
        "username": username,
        "content": signal.alert_text,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
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
