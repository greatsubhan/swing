# Open Questions

These items remain intentionally unresolved so they can be confirmed instead of
being hardcoded by assumption:

- Final V1 session focus: London only, New York only, London plus New York, or full 24-hour coverage.
- Exact London and New York session window definitions to use for research filtering and alerting.
- Confirm the preferred default London-New York overlap window in New York time; the config currently uses `08:00-10:00` as a provisional alert-priority window.
- Preferred default extension metric per instrument for V1 research priority: ATR multiple, raw points, percent from base, or another relative-distance variant.
- Instrument-specific transaction cost assumptions for OANDA research runs, especially spread and slippage by market.
- Whether daily candidate signals should be actionable on the same session only or across both the exhaustion day and the following session when markets span regional sessions.
- Confirm whether the replay engine should allow a second attempt after a completed trade on the same symbol/day by default, or only after pre-entry invalidation; the current implementation can re-arm while attempts remain.
- Confirm whether the risk-free add size should remain tied to `add_size_pct_of_initial` with the current default of `40%` of initial size.
- Confirm whether the current objective invalidation default is acceptable: pre-entry and post-entry invalidation on close above session VWAP.
- Confirm whether live alerting should use completed bars only from OANDA for both `1m` and `5m`; the current read-only adapter ignores incomplete candles.
- Confirm the preferred live polling cadence for OANDA in V1; the current adapter default is a provisional `10` seconds.
- Confirm whether `EXHAUSTION_WATCH` alerts should be enabled by default in production or remain optional/lower-priority only.
