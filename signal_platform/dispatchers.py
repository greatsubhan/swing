"""Dispatchers for posting signals to external channels."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
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
    event_type = str(signal.raw_signal.get("event_type", "entry")).lower()
    if event_type == "reinforcement":
        return 0x5865F2
    if event_type == "move_stop":
        return 0xF1C40F
    if event_type == "basket_exit":
        reason = str(signal.raw_signal.get("exit_reason", ""))
        return 0x3498DB if reason == "trend_break" else 0xE67E22
    if event_type == "cooldown":
        return 0x95A5A6
    if signal.side.lower() == "long":
        return 0x2ECC71
    if signal.side.lower() == "short":
        return 0xE74C3C
    return 0x3498DB


def _signal_badge(side: str) -> str:
    return "LONG" if side.lower() == "long" else "SHORT" if side.lower() == "short" else "SETUP"


def _structure_badge(side: str) -> str:
    if side.lower() == "long":
        return "\u2197 HH/HL"
    if side.lower() == "short":
        return "\u2198 LH/LL"
    return "STRUCTURE"


def _signal_emoji(side: str) -> str:
    if side.lower() == "long":
        return "\U0001F4C8"
    if side.lower() == "short":
        return "\U0001F4C9"
    return "\U0001F4CD"


def _event_badge(signal: PlatformSignal) -> tuple[str, str]:
    event_type = str(signal.raw_signal.get("event_type", "entry")).lower()
    structure_badge = _structure_badge(signal.side)
    if event_type == "reinforcement":
        return (f"{structure_badge} REINFORCEMENT", _signal_emoji(signal.side))
    if event_type == "entry":
        return (f"{structure_badge} NEW SIGNAL", _signal_emoji(signal.side))
    if event_type == "add":
        return (f"{structure_badge} ADD", "\u2795")
    if event_type == "move_stop":
        return (f"{structure_badge} MOVE STOP", "\U0001F6D1")
    if event_type == "basket_exit":
        return ("BASKET EXIT", "\U0001F4E6")
    if event_type == "cooldown":
        return ("COOLDOWN", "\u23F3")
    return (_signal_badge(signal.side), _signal_emoji(signal.side))


def _format_price(value: float | None, digits: int = 5) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _format_money(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"${float(value):,.2f}"


def _bullet_lines(items: list[str]) -> str:
    return "\n".join(f"\u2022 {item}" for item in items) if items else "None"


def _join_lines(items: list[str]) -> str:
    return "\n".join(item for item in items if item)


def _footer_text(signal: PlatformSignal) -> str:
    return f"{signal.strategy_name} | {signal.asset_class} | {signal.strategy_id} | {signal.setup_id}"


def discord_payload(signal: PlatformSignal, username: str = SIGNAL_DESK_NAME) -> dict[str, object]:
    event_type = str(signal.raw_signal.get("event_type", "entry")).lower()

    if event_type == "sip_allocation":
        basket_label = str(signal.raw_signal.get("sleeve_label", signal.symbol))
        active_lines = [
            f"{leg['symbol']} | ref {_format_price(leg['price_reference'], digits=2)} | "
            f"{_format_money(leg['monthly_budget'])} | {leg['reference_units']:.4f} units"
            for leg in signal.raw_signal.get("active_legs", [])
        ]
        skipped_lines = [
            f"{leg['symbol']} | {leg.get('trend_label', 'filter blocked')}"
            for leg in signal.raw_signal.get("skipped_legs", [])
        ]
        reference = signal.raw_signal.get("reference_research") or {}
        reference_text = (
            f"{reference.get('profile_label', 'n/a')} | "
            f"{reference.get('withdrawal_label', 'n/a')} | "
            f"{reference.get('sleeve_label', 'n/a')}"
            if reference
            else "n/a"
        )
        return {
            "username": username,
            "content": f"\U0001F4C5 [{signal.strategy_name}] {basket_label} monthly allocation",
            "embeds": [
                {
                    "title": f"\U0001F4C5 {basket_label} Monthly Allocation",
                    "description": signal.summary,
                    "color": 0x3498DB,
                    "fields": [
                        {"name": "Month", "value": str(signal.raw_signal.get("allocation_month", "n/a")), "inline": True},
                        {"name": "Basket", "value": basket_label, "inline": True},
                        {"name": "Profile", "value": str(signal.raw_signal.get("profile_label", "n/a")), "inline": True},
                        {"name": "Payout Mode", "value": str(signal.raw_signal.get("payout_label", "n/a")), "inline": False},
                        {"name": "Per Asset Budget", "value": _format_money(signal.raw_signal.get("monthly_budget_per_asset", 0.0)), "inline": True},
                        {"name": "Planned This Month", "value": _format_money(signal.raw_signal.get("total_sleeve_budget", 0.0)), "inline": True},
                        {"name": "Account Reference", "value": _format_money(signal.raw_signal.get("account_size", 0.0)), "inline": True},
                        {"name": "Active Adds", "value": _bullet_lines(active_lines), "inline": False},
                        {"name": "Skipped This Month", "value": _bullet_lines(skipped_lines), "inline": False},
                        {"name": "Research Anchor", "value": reference_text, "inline": False},
                    ],
                    "footer": {"text": _footer_text(signal)},
                    "timestamp": signal.timestamp,
                }
            ],
        }

    if event_type == "sip_review":
        basket_label = str(signal.raw_signal.get("sleeve_label", signal.symbol))
        asset_lines = [
            f"{asset['symbol']} | {float(asset['month_return_pct']):+.2f}%"
            for asset in signal.raw_signal.get("assets", [])
        ]
        return {
            "username": username,
            "content": f"\U0001F4CA [{signal.strategy_name}] {basket_label} month-end review",
            "embeds": [
                {
                    "title": f"\U0001F4CA {basket_label} Month-End Review",
                    "description": signal.summary,
                    "color": 0x5865F2,
                    "fields": [
                        {"name": "Review Month", "value": str(signal.raw_signal.get("review_month", "n/a")), "inline": True},
                        {"name": "Basket", "value": basket_label, "inline": True},
                        {"name": "Basket Return", "value": f"{float(signal.raw_signal.get('sleeve_return_pct', 0.0)):+.2f}%", "inline": True},
                        {
                            "name": "Best Asset",
                            "value": f"{signal.raw_signal.get('best_asset', 'n/a')} ({float(signal.raw_signal.get('best_asset_return_pct', 0.0)):+.2f}%)",
                            "inline": True,
                        },
                        {
                            "name": "Weakest Asset",
                            "value": f"{signal.raw_signal.get('worst_asset', 'n/a')} ({float(signal.raw_signal.get('worst_asset_return_pct', 0.0)):+.2f}%)",
                            "inline": True,
                        },
                        {"name": "Payout Mode", "value": str(signal.raw_signal.get("payout_label", "n/a")), "inline": True},
                        {"name": "Asset Review", "value": _bullet_lines(asset_lines), "inline": False},
                    ],
                    "footer": {"text": _footer_text(signal)},
                    "timestamp": signal.timestamp,
                }
            ],
        }

    badge, event_emoji = _event_badge(signal)
    rr_text = f"{signal.risk_reward:.2f}" if signal.risk_reward is not None else "n/a"
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
        else "No journal stats yet."
    )
    risk_fraction = signal.raw_signal.get("risk_fraction")
    risk_fraction_text = f"{float(risk_fraction) * 100:.2f}%" if risk_fraction is not None else "n/a"
    risk_field_name = str(signal.raw_signal.get("risk_label", "Risk Rule"))
    risk_display_text = str(signal.raw_signal.get("risk_display", risk_fraction_text))
    stop_distance_pct = None
    if signal.entry is not None and signal.stop_loss is not None and float(signal.entry) != 0:
        stop_distance_pct = abs(float(signal.stop_loss) - float(signal.entry)) / abs(float(signal.entry)) * 100.0
    stop_distance_text = f"{stop_distance_pct:.2f}%" if stop_distance_pct is not None else "n/a"
    basket_id = str(signal.raw_signal.get("basket_id", "n/a"))
    tranche_id = str(signal.raw_signal.get("tranche_id", "n/a"))
    setup_name = str(
        signal.raw_signal.get("scenario_label")
        or str(signal.raw_signal.get("scenario", "")).replace("scenario", "Scenario ").strip()
    ) or "n/a"
    bias_timeframe = str(signal.raw_signal.get("bias_timeframe", "n/a")).upper()

    title = f"{event_emoji} {signal.symbol} {signal.timeframe.upper()} {badge}"
    description = signal.summary
    fields: list[dict[str, object]] = []

    if event_type in {"entry", "add"}:
        trade_plan = _join_lines(
            [
                f"\u26A1 Entry `{_format_price(signal.entry)}`",
                f"\U0001F6D1 Stop `{_format_price(signal.stop_loss)}`",
                f"\U0001F3AF Target `{_format_price(signal.target_1)}`",
                f"\U0001F4CF R/R `{rr_text}`",
                f"\u2B50 Score `{score_text}`" if score_text != "n/a" else "",
            ]
        )
        context_lines = [
            f"`{_structure_badge(signal.side)}` Structure",
            f"`{setup_name}`",
            f"`{bias_timeframe}` Bias",
        ]
        if risk_display_text != "n/a":
            context_lines.append(f"`{risk_display_text}`")
        notes_lines = [
            "Use your own account risk rule for sizing.",
            history_text,
        ]
        if stop_distance_text != "n/a":
            notes_lines.append(f"Stop distance `{stop_distance_text}`")
        if basket_id != "n/a":
            notes_lines.append(f"Basket Ref: `{basket_id}`")
        if tranche_id != "n/a":
            notes_lines.append(f"Tranche Ref: `{tranche_id}`")
        fields.extend(
            [
                {"name": "Trade Plan", "value": trade_plan, "inline": False},
                {"name": "Context", "value": _join_lines(context_lines), "inline": False},
                {"name": "Notes", "value": _join_lines(notes_lines), "inline": False},
            ]
        )
    elif event_type == "reinforcement":
        root_signal_id = str(signal.root_signal_id or signal.raw_signal.get("root_signal_id", "n/a"))
        structure_id = str(signal.structure_id or signal.raw_signal.get("structure_id", "n/a"))
        r_scaling_enabled = bool(signal.raw_signal.get("r_scaling_enabled", False))
        effective_r_exposure = float(signal.raw_signal.get("effective_r_exposure", 1.0))
        title = f"{event_emoji} {signal.symbol} {signal.timeframe.upper()} {badge}"
        description = _join_lines(
            [
                "No new trade. Reinforcement only for the active structure.",
                signal.summary,
            ]
        )
        fields.extend(
            [
                {
                    "name": "Update",
                    "value": _join_lines(
                        [
                            f"`{_structure_badge(signal.side)}` Structure",
                            f"`{int(signal.strength_score or 0)}/100` Strength",
                            f"`{signal.reinforcement_count}` Reinforcements",
                            f"`{setup_name}` | `{bias_timeframe}` Bias",
                        ]
                    ),
                    "inline": False,
                },
                {
                    "name": "Reference",
                    "value": _join_lines(
                        [
                            f"\u26A1 `{_format_price(signal.entry)}` | \U0001F6D1 `{_format_price(signal.stop_loss)}` | \U0001F3AF `{_format_price(signal.target_1)}`",
                            f"\U0001F4CF `{rr_text}R`" if rr_text != "n/a" else "",
                            f"\u2B50 `{score_text}`" if score_text != "n/a" else "",
                            f"`{risk_display_text}`" if risk_display_text != "n/a" else "",
                            (
                                f"Effective R `{effective_r_exposure:.2f}R (experimental)`"
                                if r_scaling_enabled
                                else ""
                            ),
                            f"Root `{root_signal_id}`",
                            f"Structure `{structure_id}`",
                        ]
                    ),
                    "inline": False,
                },
            ]
        )
    elif event_type == "move_stop":
        title = f"{event_emoji} {signal.symbol} {signal.timeframe.upper()} {badge}"
        fields.append(
            {
                "name": "Update",
                "value": _join_lines(
                    [
                        f"\U0001F6D1 New Stop `{_format_price(signal.stop_loss)}`",
                        f"Bars Held: `{signal.raw_signal.get('bars_held', 'n/a')}`",
                        f"Original Entry Time: `{signal.raw_signal.get('original_entry_time', 'n/a')}`",
                        f"Basket Ref: `{basket_id}`" if basket_id != "n/a" else "",
                        f"Tranche Ref: `{tranche_id}`" if tranche_id != "n/a" else "",
                    ]
                ),
                "inline": False,
            }
        )
    elif event_type == "basket_exit":
        title = f"{event_emoji} {signal.symbol} {signal.timeframe.upper()} {badge}"
        fields.append(
            {
                "name": "Basket Close",
                "value": _join_lines(
                    [
                        f"Exit Reason: `{signal.raw_signal.get('exit_reason', 'n/a')}`",
                        f"Tranches: `{signal.raw_signal.get('tranche_count', 'n/a')}`",
                        f"Basket Result: `{float(signal.raw_signal.get('basket_result_r', 0.0)):.2f}R`",
                        f"Basket Ref: `{basket_id}`" if basket_id != "n/a" else "",
                    ]
                ),
                "inline": False,
            }
        )
    elif event_type == "cooldown":
        title = f"{event_emoji} {signal.symbol} {signal.timeframe.upper()} {badge}"
        fields.append(
            {
                "name": "Cooldown",
                "value": _join_lines(
                    [
                        f"Cooldown Until: `{signal.raw_signal.get('cooldown_until', 'n/a')}`",
                        f"Basket Ref: `{basket_id}`" if basket_id != "n/a" else "",
                    ]
                ),
                "inline": False,
            }
        )
    else:
        fields.append(
            {
                "name": "Trade Plan",
                "value": _join_lines(
                    [
                        f"\u26A1 Entry `{_format_price(signal.entry)}`",
                        f"\U0001F6D1 Stop `{_format_price(signal.stop_loss)}`",
                        f"\U0001F3AF Target `{_format_price(signal.target_1)}`",
                        f"\U0001F4CF R/R `{rr_text}`",
                    ]
                ),
                "inline": False,
            }
        )

    return {
        "username": username,
        "content": f"{event_emoji} [{signal.strategy_name}] {signal.symbol} {signal.timeframe.upper()} {badge}",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": _discord_color(signal),
                "fields": fields,
                "footer": {"text": _footer_text(signal)},
                "timestamp": signal.timestamp,
            }
        ],
    }


def outcome_payload(entry: JournalEntry, username: str = SIGNAL_DESK_NAME) -> dict[str, object]:
    outcome = entry.outcome or "closed"
    normalized_outcome = "break_even" if outcome in {"breakeven", "break_even"} else outcome
    outcome_label = (
        "TP hit"
        if normalized_outcome == "tp_hit"
        else "SL hit"
        if normalized_outcome == "sl_hit"
        else "Break-even"
        if normalized_outcome == "break_even"
        else normalized_outcome.replace("_", " ").title()
    )
    hold_hours = entry.hold_hours()
    hold_text = f"{hold_hours:.1f}h" if hold_hours is not None else "n/a"
    color = (
        0x2ECC71
        if normalized_outcome == "tp_hit"
        else 0xE74C3C
        if normalized_outcome == "sl_hit"
        else 0xF1C40F
        if normalized_outcome == "break_even"
        else 0x3498DB
    )
    outcome_tag = (
        "TP"
        if normalized_outcome == "tp_hit"
        else "SL"
        if normalized_outcome == "sl_hit"
        else "BE"
        if normalized_outcome == "break_even"
        else "CLOSED"
    )
    outcome_emoji = (
        "\u2705"
        if normalized_outcome == "tp_hit"
        else "\U0001F6D1"
        if normalized_outcome == "sl_hit"
        else "\U0001F7E1"
        if normalized_outcome == "break_even"
        else "\U0001F4CC"
    )
    realized_r = entry.realized_r()
    return {
        "username": username,
        "content": f"{outcome_emoji} [{entry.strategy_name}] {entry.symbol} {entry.timeframe.upper()} {outcome_label}",
        "embeds": [
            {
                "title": f"{outcome_emoji} {entry.symbol} {entry.timeframe.upper()} {outcome_label}",
                "description": f"{outcome_tag} outcome recorded for setup `{entry.setup_id}`.",
                "color": color,
                "fields": [
                    {
                        "name": "Result",
                        "value": _join_lines(
                            [
                                f"Side: `{entry.side.upper()}`",
                                f"Outcome: `{outcome_label}`",
                                f"Realized: `{realized_r:.2f}R`" if realized_r is not None else "Realized: `n/a`",
                            ]
                        ),
                        "inline": False,
                    },
                    {
                        "name": "Exit Details",
                        "value": _join_lines(
                            [
                                f"Exit Price: `{_format_price(entry.exit_price)}`",
                                f"Signal Time: `{entry.signal_timestamp}`",
                                f"Outcome Time: `{entry.outcome_timestamp or 'n/a'}`",
                            ]
                        ),
                        "inline": False,
                    },
                    {
                        "name": "Hold",
                        "value": _join_lines(
                            [
                                f"Hold Time: `{hold_text}`",
                                f"Bars Checked: `{entry.bars_checked}`",
                            ]
                        ),
                        "inline": False,
                    },
                ],
                "footer": {"text": f"{entry.strategy_name} | outcome | {entry.setup_id}"},
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
    title_emoji = "\U0001F5D3\uFE0F" if title_prefix == "Weekly" else "\U0001F4C6"
    tp_list = "\n".join(f"\u2022 {item}" for item in summary["tp_list"]) or "\u2022 none"
    sl_list = "\n".join(f"\u2022 {item}" for item in summary["sl_list"]) or "\u2022 none"
    open_list = "\n".join(f"\u2022 {item}" for item in summary["open_list"]) or "\u2022 none"
    return {
        "username": username,
        "content": f"{title_emoji} {title_prefix} review",
        "embeds": [
            {
                "title": f"{title_emoji} {period_label} Report Card",
                "description": "A concise review of signal flow, realized result, and any open exposure still on the board.",
                "color": 0x5865F2,
                "fields": [
                    {
                        "name": "Summary",
                        "value": _join_lines(
                            [
                                f"Signals: `{summary['signals_sent']}`",
                                f"TP Hits: `{summary['tp_hits']}`",
                                f"SL Hits: `{summary['sl_hits']}`",
                                f"Still Open: `{summary['open_count']}`",
                                f"Net Realized: `{summary['total_realized_r']:.2f}R`",
                                f"Avg Closed Trade: `{summary['avg_closed_r_text']}`",
                                f"Avg Hold: `{summary['avg_hold_text']}`",
                            ]
                        ),
                        "inline": False,
                    },
                    {"name": "TP List", "value": tp_list, "inline": False},
                    {"name": "SL List", "value": sl_list, "inline": False},
                    {"name": "Open List", "value": open_list, "inline": False},
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
            env={str(key): str(value) for key, value in {**os.environ, "WEBHOOK_URL": webhook_url}.items()},
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
