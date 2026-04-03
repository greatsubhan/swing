"""Template second strategy scaffold for the multi-strategy platform."""
from __future__ import annotations

import json
from pathlib import Path

from .models import ScanResult
from .strategies import StrategyPlugin, StrategyScanRequest


class StrategyTwoTemplate(StrategyPlugin):
    strategy_id = "strategy_two_template"
    strategy_name = "Strategy Two Template"
    default_watchlist = "template-empty"

    def scan(self, request: StrategyScanRequest) -> ScanResult:
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, object]] = []
        (output_dir / "scan_results.json").write_text(json.dumps(rows, indent=2))
        (output_dir / "alerts.txt").write_text("")
        return ScanResult(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            watchlist=request.watchlist,
            signals=[],
            rows=rows,
        )
