from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_file: str | Path | None, *, override: bool = True) -> dict[str, str]:
    if env_file is None:
        return {}

    path = Path(env_file)
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded
