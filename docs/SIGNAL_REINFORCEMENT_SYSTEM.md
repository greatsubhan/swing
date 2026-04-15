# Signal Reinforcement System

This document describes the signal reinforcement layer added to the live signal platform.

## Purpose

The platform used to send multiple same-direction signals for the same symbol and timeframe while a single CWT move was still unfolding.

That caused:

- duplicate-looking trades
- inflated trade counts in the live journal
- Discord alert spam

The reinforcement layer fixes that by separating:

- the **first tradable signal** in a structure
- later **reinforcement updates** for the same active structure

## Core Model

### Root signal

The first valid signal in a structure becomes the root signal.

Characteristics:

- tradable
- journaled as a normal trade
- owns the structure state
- controls TP and SL outcome tracking

### Reinforcement update

Later signals in the same active structure become reinforcement updates.

Characteristics:

- not tradable
- not journaled as a new trade
- still dispatched to Discord
- update strength and confidence for the existing idea

## Structure Detection

The current implementation is intentionally conservative.

Signals are grouped into one active structure when they share:

- strategy
- symbol
- timeframe
- side

And the existing root structure is still active.

The structure ends when:

- the root trade closes in the journal, or
- an opposite-side root signal is accepted and the prior structure is marked `invalidated`

This keeps the implementation backtest-safe:

- no lookahead
- no repaint-based regrouping after the fact
- no change to the underlying setup scanner

## State Model

Persistent structure state is stored in:

- `platform_output/<route>/reinforcement_state.json`

Each structure records:

- `structure_id`
- `symbol`
- `timeframe`
- `side`
- `start_timestamp`
- `last_update_timestamp`
- `status`
- `root_signal_id`
- `reinforcement_count`
- `strength_score`
- `best_quality_score`
- `current_status`
- `entry`
- `stop_loss`
- `target_1`
- `last_signal_timestamp`
- `effective_r_exposure`

## Strength Model

Baseline scoring:

- base score = `50`
- quality score improved = `+5`
- continuation confirmation = `+5`
- structure holds = `+3`
- HTF alignment maintained = `+3`
- score capped at `100`

This is additive and deterministic.

## Experimental R Scaling

There is an optional feature flag for an experimental effective-R monitor.

Configuration:

- `enable_r_scaling`
- `r_scale_per_reinforcement`
- `max_effective_r_exposure`

Current behavior:

- disabled by default
- does **not** affect trade journaling
- does **not** change realized performance metrics
- only reports a logical effective-R monitor on reinforcement events when enabled

Reason:

- changing true trade sizing during reinforcement would distort current results unless a dedicated scaling backtest is built around it

## Runtime Integration

The reinforcement layer runs in the platform runtime after raw scanner output is normalized into `PlatformSignal` objects and before signals are journaled or dispatched.

Current flow:

1. scanner produces raw entry signals
2. runtime loads journal and current structure state
3. runtime classifies each signal as:
   - root signal
   - reinforcement
   - passthrough non-entry event
4. only root signals are journaled as trades
5. both roots and reinforcements can be dispatched to Discord
6. decision logs are appended to:
   - `platform_output/<route>/reinforcement_decisions.jsonl`

## Discord Output

### New root signal

Includes:

- symbol
- timeframe
- direction
- entry / stop / target
- R:R
- quality score
- strategy context

### Reinforcement update

Includes:

- reference root signal
- structure reference
- strength score
- reinforcement count
- what changed
- explicit note:
  - `No new trade. Reinforcement only for the active structure.`

## Before vs After

### Before

Example:

- `AUD_USD 5m long`
- `AUD_USD 5m long`
- `AUD_USD 5m long`

All three could be treated like separate trades.

### After

Example:

- first setup -> root signal -> tradable
- next setup -> reinforcement update -> not tradable
- next setup -> reinforcement update -> not tradable

The journal stays clean while the board still shows that the move is strengthening.

## Edge Cases

### Same root setup seen again on a later cycle

If the original root setup reappears before sent-state catches up, it stays the root signal and is not downgraded to a reinforcement.

### Opposite-side signal while a structure is active

The previous structure is marked `invalidated` in structure state and the new side can become the next root signal.

### Managed-event routes

The reinforcement layer is intended for tactical routes. Managed-event boards like SIP are not using it.

## Current Scope

The configuration is enabled for:

- `strategy_four` / CWT

It was designed in a generic enough way that future tactical routes can opt in through route config.

## Limitations

- structure continuation is currently based on active route state, not deep structural swing IDs from the scanner
- it does not rewrite older research reports automatically
- experimental R scaling is observational only right now

## Configuration

Current route configuration lives in:

- [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json)

Relevant keys:

- `reinforcement_state_file`
- `reinforcement_log_file`
- `extra.signal_reinforcement.enabled`
- `extra.signal_reinforcement.base_strength_score`
- `extra.signal_reinforcement.max_strength_score`
- `extra.signal_reinforcement.quality_improvement_points`
- `extra.signal_reinforcement.continuation_points`
- `extra.signal_reinforcement.structure_holds_points`
- `extra.signal_reinforcement.htf_alignment_points`
- `extra.signal_reinforcement.enable_r_scaling`

## Files

Core implementation files:

- [signal_platform/reinforcement.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/reinforcement.py)
- [signal_platform/models.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/models.py)
- [signal_platform/runtime.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/runtime.py)
- [signal_platform/dispatchers.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/dispatchers.py)
- [signal_platform/journal.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/journal.py)
