from pathlib import Path

import pandas as pd

from parabolic_exhaustion.reporting.forward_test_review_parabolic import build_forward_test_review


def test_forward_test_review_summarizes_closed_trades(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    output_dir = tmp_path / "output" / "nas100_parabolic_paper"
    config_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    (config_dir / "strategy.yaml").write_text(
        "\n".join(
            [
                "provider: oanda",
                "market_scope: multi_asset",
                "session_scope: london_new_york",
                "paper_profiles:",
                "  NAS100_PARABOLIC_PAPER:",
                "    strategy_type: parabolic_exhaustion",
                "    markets: [NAS100_USD]",
                "    parameter_set_id: idx_ps07_baseline_on",
                "    discord_webhook_env_var: DISCORD_WEBHOOK_URL_NAS100_PARABOLIC_PAPER",
                "    discord_channel_name: nas100-parabolic-paper",
                "    output_subdir: nas100_parabolic_paper",
                "    forward_test_log_filename: forward_test_log_parabolic.csv",
                "    session_timezone: America/New_York",
            ]
        ),
        encoding="utf-8",
    )
    (config_dir / "backtest.yaml").write_text("replay:\n  use_kill_zones_for_entry: true\n", encoding="utf-8")
    (config_dir / "discord.yaml").write_text(
        "\n".join(
            [
                "enabled: true",
                "webhook_env_var: DISCORD_WEBHOOK_URL",
                "channel_name:",
                "username: Parabolic Exhaustion Bot",
            ]
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "symbol": "NAS100_USD",
                "parameter_set_id": "idx_ps07_baseline_on",
                "profit_factor": 2.5,
                "avg_R_per_trade": 0.8,
                "approx_trades_per_day": 0.1,
            }
        ]
    ).to_csv(tmp_path / "strategy_review_table.csv", index=False)
    pd.DataFrame(
        [
            {
                "timestamp": "2026-04-10 09:35:00-04:00",
                "symbol": "NAS100_USD",
                "profile_name": "NAS100_PARABOLIC_PAPER",
                "parameter_set_id": "idx_ps07_baseline_on",
                "state": "ENTRY_TRIGGERED",
                "setup_id": "NAS100-20260410",
                "entry": 20000.0,
                "stop": 20020.0,
                "target_1": 19970.0,
                "killzone_flag": True,
                "session": "new_york",
                "realized_result_R": None,
                "notes": "entry",
            },
            {
                "timestamp": "2026-04-10 09:55:00-04:00",
                "symbol": "NAS100_USD",
                "profile_name": "NAS100_PARABOLIC_PAPER",
                "parameter_set_id": "idx_ps07_baseline_on",
                "state": "EXITED",
                "setup_id": "NAS100-20260410",
                "entry": 20000.0,
                "stop": 20020.0,
                "target_1": 19970.0,
                "killzone_flag": True,
                "session": "new_york",
                "realized_result_R": 1.2,
                "notes": "exit",
            },
            {
                "timestamp": "2026-04-11 09:55:00-04:00",
                "symbol": "NAS100_USD",
                "profile_name": "NAS100_PARABOLIC_PAPER",
                "parameter_set_id": "idx_ps07_baseline_on",
                "state": "EXITED",
                "setup_id": "NAS100-20260411",
                "entry": 20010.0,
                "stop": 20030.0,
                "target_1": 19980.0,
                "killzone_flag": False,
                "session": "new_york",
                "realized_result_R": -0.4,
                "notes": "exit",
            },
        ]
    ).to_csv(output_dir / "forward_test_log_parabolic.csv", index=False)

    summary = build_forward_test_review(project_root=tmp_path)

    assert float(summary.iloc[0]["trade_count"]) == 2
    assert round(float(summary.iloc[0]["win_rate_pct"]), 2) == 50.0
    assert round(float(summary.iloc[0]["average_R"]), 2) == 0.40
    assert (tmp_path / "forward_test_review_parabolic.csv").exists()
