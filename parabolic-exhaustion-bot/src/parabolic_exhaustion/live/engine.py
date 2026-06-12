from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from parabolic_exhaustion.backtest.replay import (
    _close_trade,
    _open_position,
    _process_open_position_bar,
    _process_pre_entry_bar,
    _record_transition,
    collapse_overlapping_candidates,
    prepare_replay_bars,
)
from parabolic_exhaustion.config import BacktestConfig, DiscordConfig, StrategyConfig
from parabolic_exhaustion.discord_bot.formatter import AlertEvent
from parabolic_exhaustion.discord_bot.publisher import AlertDeliveryResult, DiscordAlertPublisher
from parabolic_exhaustion.execution.state_machine import ReplayState
from parabolic_exhaustion.features.daily import engineer_daily_features
from parabolic_exhaustion.live.models import SymbolLiveState
from parabolic_exhaustion.signals.candidates import scan_daily_candidates


ALERT_STATES = {
    ReplayState.EXHAUSTION_WATCH,
    ReplayState.ENTRY_TRIGGERED,
    ReplayState.PARTIAL_TAKEN,
    ReplayState.BREAK_EVEN_PROTECTED,
    ReplayState.ADD_TRIGGERED,
    ReplayState.INVALIDATED,
    ReplayState.EXITED,
}


class LiveSignalEngine:
    def __init__(
        self,
        *,
        strategy_config: StrategyConfig,
        backtest_config: BacktestConfig,
        discord_config: DiscordConfig,
        publisher: DiscordAlertPublisher,
        output_dir: str | Path,
        profile_name: str | None = None,
        parameter_set_id: str | None = None,
        forward_test_log_path: str | Path | None = None,
        session_timezone: str = "America/New_York",
    ) -> None:
        self.strategy_config = strategy_config
        self.backtest_config = backtest_config
        self.discord_config = discord_config
        self.publisher = publisher
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.transition_log_path = self.output_dir / "live_state_transitions.csv"
        self.health_log_path = self.output_dir / "live_health.csv"
        self.forward_test_log_path = Path(forward_test_log_path) if forward_test_log_path is not None else None
        self.profile_name = profile_name
        self.parameter_set_id = parameter_set_id
        self.session_timezone = session_timezone
        self.symbol_states: dict[str, SymbolLiveState] = {}
        self.daily_candidates: dict[str, object] = {}
        self.next_poll_due_at: pd.Timestamp | None = None

    def refresh_daily_candidates(self, daily_bars: pd.DataFrame) -> pd.DataFrame:
        daily_features = engineer_daily_features(daily_bars)
        candidates = scan_daily_candidates(daily_features, self.strategy_config)
        candidates = candidates.loc[candidates["daily_candidate"]].copy()
        candidates = collapse_overlapping_candidates(
            candidates,
            signal_expiry_sessions=self.backtest_config.signal_expiry_sessions,
        )
        latest_candidates = candidates.sort_values(["symbol", "timestamp"]).groupby("symbol").tail(1)
        self.daily_candidates = {
            row["symbol"]: SimpleNamespace(**row.to_dict())
            for _, row in latest_candidates.iterrows()
        }
        return latest_candidates.reset_index(drop=True)

    async def run(
        self,
        *,
        live_provider,
        daily_bars: pd.DataFrame,
        symbols: list[str],
        timeframes: tuple[str, ...] = ("1m", "5m"),
        max_events: int | None = None,
    ) -> None:
        self.refresh_daily_candidates(daily_bars)
        queue: asyncio.Queue[pd.Series | None] = asyncio.Queue()
        tasks = [
            asyncio.create_task(self._consume_stream(live_provider, symbols, timeframe, queue))
            for timeframe in timeframes
        ]
        processed = 0
        try:
            while tasks:
                item = await queue.get()
                if item is None:
                    tasks = [task for task in tasks if not task.done()]
                    if not tasks and queue.empty():
                        break
                    continue
                await self.process_bar(item)
                processed += 1
                if max_events is not None and processed >= max_events:
                    break
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def process_bar(self, bar: pd.Series) -> list[AlertDeliveryResult]:
        return await self.process_bar_with_options(bar)

    async def process_bar_with_options(
        self,
        bar: pd.Series,
        *,
        publish_alerts: bool = True,
        persist_outputs: bool = True,
    ) -> list[AlertDeliveryResult]:
        symbol = str(bar["symbol"])
        timeframe = str(bar["timeframe"])
        state = self.symbol_states.setdefault(symbol, SymbolLiveState(symbol=symbol))
        frame_name = "intraday_1m" if timeframe == "1m" else "intraday_5m"
        current = getattr(state, frame_name)
        updated = pd.concat([current, pd.DataFrame([bar.drop(labels=["timeframe"])])], ignore_index=True)
        setattr(state, frame_name, updated.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True))

        timestamp = pd.Timestamp(bar["timestamp"])
        if timeframe == "1m":
            state.last_bar_timestamp_1m = timestamp
        else:
            state.last_bar_timestamp_5m = timestamp

        self.next_poll_due_at = timestamp + pd.Timedelta(minutes=1)
        if timeframe != "1m" or symbol not in self.daily_candidates or state.intraday_5m.empty:
            if persist_outputs:
                self._append_health(symbol, state, "bar buffered")
            return []

        candidate = self.daily_candidates[symbol]
        state.candidate = candidate
        replay_bars = prepare_replay_bars(
            intraday_1m=state.intraday_1m.assign(symbol=symbol),
            intraday_5m=state.intraday_5m.assign(symbol=symbol),
            strategy_config=self.strategy_config,
        )
        live_bar = replay_bars.iloc[-1]
        state.bar_index += 1
        new_rows: list[dict[str, object]] = []
        new_alert_results: list[AlertDeliveryResult] = []

        if state.current_state == ReplayState.NO_SETUP:
            state.current_state, state.sequence = _record_transition(
                new_rows,
                state.current_state,
                ReplayState.DAILY_CANDIDATE,
                "daily candidate active",
                symbol,
                candidate.timestamp,
                live_bar,
                state.attempt_count,
                state.sequence,
            )

        if state.pending_entry is not None and state.bar_index == state.pending_entry.execute_index:
            position = _open_position(
                bar=live_bar,
                candidate=candidate,
                strategy_config=self.strategy_config,
                backtest_config=self.backtest_config,
                label="initial",
                reference_high=state.pending_entry.reference_high,
            )
            if position is None:
                state.current_state, state.sequence = _record_transition(
                    new_rows,
                    state.current_state,
                    ReplayState.INVALIDATED,
                    "entry skipped because stop reference was not above entry",
                    symbol,
                    candidate.timestamp,
                    live_bar,
                    state.attempt_count,
                    state.sequence,
                )
            else:
                state.position = position
                state.attempt_count += 1
                state.entry_trade_id += 1
                state.current_state, state.sequence = _record_transition(
                    new_rows,
                    state.current_state,
                    ReplayState.ENTRY_TRIGGERED,
                    "entry executed",
                    symbol,
                    candidate.timestamp,
                    live_bar,
                    state.attempt_count,
                    state.sequence,
                )
            state.pending_entry = None

        if state.position is None:
            state.current_state, state.sequence, state.pending_entry = _process_pre_entry_bar(
                candidate=candidate,
                bar=live_bar,
                bar_index=state.bar_index,
                current_state=state.current_state,
                pending_entry=state.pending_entry,
                strategy_config=self.strategy_config,
                backtest_config=self.backtest_config,
                transitions=new_rows,
                attempt_count=state.attempt_count,
                sequence=state.sequence,
            )
        else:
            state.current_state, state.sequence, state.pending_add_index, trade = _process_open_position_bar(
                candidate=candidate,
                bar=live_bar,
                bar_index=state.bar_index,
                current_state=state.current_state,
                position=state.position,
                pending_add_index=state.pending_add_index,
                strategy_config=self.strategy_config,
                backtest_config=self.backtest_config,
                transitions=new_rows,
                attempt_count=state.attempt_count,
                sequence=state.sequence,
                trade_id=f"{symbol}-{pd.Timestamp(candidate.timestamp).strftime('%Y%m%d')}-{state.entry_trade_id}",
            )
            if trade is not None:
                state.last_trade_snapshot = trade
                if persist_outputs:
                    self._append_dataframe(pd.DataFrame([trade]), self.output_dir / "live_trade_log.csv")
                state.position = None
                state.pending_add_index = None

        for row in new_rows:
            transition_key = (
                row["symbol"],
                row["candidate_timestamp"],
                row["timestamp"],
                row["new_state"],
            )
            if transition_key in state.seen_transition_keys:
                continue
            if persist_outputs:
                state.seen_transition_keys.add(transition_key)
                self._append_dataframe(pd.DataFrame([row]), self.transition_log_path)
            if publish_alerts and row["new_state"] in ALERT_STATES:
                event = self._build_alert_event(symbol, state, row)
                if event is not None:
                    result = await self.publisher.publish(event)
                    state.last_alert_status = result.message
                    if persist_outputs:
                        self._append_forward_test_row(symbol=symbol, state=state, row=row, event=event)
                    new_alert_results.append(result)
        if persist_outputs:
            self._append_health(symbol, state, "processed 1m bar")
        return new_alert_results

    async def _consume_stream(self, live_provider, symbols: list[str], timeframe: str, queue: asyncio.Queue) -> None:
        try:
            async for bar in live_provider.stream_bars(symbols, timeframe):
                payload = bar.copy()
                payload["timeframe"] = timeframe
                await queue.put(payload)
        finally:
            await queue.put(None)

    def _build_alert_event(self, symbol: str, state: SymbolLiveState, row: dict[str, object]) -> AlertEvent | None:
        position = state.position
        trade_snapshot = state.last_trade_snapshot or {}
        side = "short" if position is not None else "flat"
        entry_price = position.weighted_entry_price if position is not None else trade_snapshot.get("entry_price")
        stop_price = position.stop_price if position is not None else trade_snapshot.get("stop_price")
        first_target = position.partial_target_price if position is not None else trade_snapshot.get("partial_target_price")
        reason = str(row["reason"])
        if state.candidate is not None:
            reason = f"{reason}; {getattr(state.candidate, 'candidate_reason', '')}".strip("; ")
        return AlertEvent(
            symbol=symbol,
            timestamp=pd.Timestamp(row["timestamp"]),
            state=getattr(row["new_state"], "name", str(row["new_state"])),
            setup_id=f"{symbol}-{pd.Timestamp(getattr(state.candidate, 'timestamp', row['timestamp'])).strftime('%Y%m%d')}",
            side=side,
            reason=reason or "VWAP rejection after parabolic extension",
            entry_price=entry_price,
            stop_price=stop_price,
            first_target_price=first_target,
            kill_zone_name=row.get("kill_zone_name"),
            alert_priority=str(row.get("alert_priority", "normal")),
        )

    def _append_health(self, symbol: str, state: SymbolLiveState, note: str) -> None:
        frame = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp.now(tz="UTC"),
                    "symbol": symbol,
                    "current_state": state.current_state,
                    "last_bar_timestamp_1m": state.last_bar_timestamp_1m,
                    "last_bar_timestamp_5m": state.last_bar_timestamp_5m,
                    "next_poll_due_at": self.next_poll_due_at,
                    "last_alert_status": state.last_alert_status,
                    "note": note,
                }
            ]
        )
        self._append_dataframe(frame, self.health_log_path)

    def _append_forward_test_row(
        self,
        *,
        symbol: str,
        state: SymbolLiveState,
        row: dict[str, object],
        event: AlertEvent,
    ) -> None:
        if self.forward_test_log_path is None:
            return

        timestamp = pd.Timestamp(row["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        local_timestamp = timestamp.tz_convert(self.session_timezone)
        trade_snapshot = state.last_trade_snapshot or {}
        frame = pd.DataFrame(
            [
                {
                    "timestamp": local_timestamp,
                    "symbol": symbol,
                    "profile_name": self.profile_name,
                    "parameter_set_id": self.parameter_set_id,
                    "state": getattr(row["new_state"], "name", str(row["new_state"])),
                    "setup_id": event.setup_id,
                    "entry": event.entry_price,
                    "stop": event.stop_price,
                    "target_1": event.first_target_price,
                    "killzone_flag": bool(row.get("kill_zone_name")),
                    "killzone_name": row.get("kill_zone_name"),
                    "session": row.get("session_name"),
                    "realized_result_R": trade_snapshot.get("r_multiple")
                    if getattr(row["new_state"], "name", str(row["new_state"])) in {"EXITED", "INVALIDATED"}
                    else None,
                    "notes": event.reason,
                    "discord_channel_name": self.discord_config.channel_name,
                }
            ]
        )
        self._append_dataframe(frame, self.forward_test_log_path)

    @staticmethod
    def _append_dataframe(frame: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        header = not path.exists()
        frame.to_csv(path, mode="a", header=header, index=False)
