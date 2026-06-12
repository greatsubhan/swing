# CWT FWM Hybrid Next Steps

## Locked Decisions

- Discard `FWM Gate`.
- Keep `FWM Entry Lane` as the only Bill Williams hybrid candidate worth carrying forward.
- Do not touch live `strategy_four` yet.
- Treat the next step as a narrower research profile, not a live rollout.

## First-Pass Symbol Read

| Symbol | Baseline Net PnL | FWM Entry Lane Net PnL | Delta | Decision |
|---|---:|---:|---:|---|
| `NAS100_USD` | $70,879.50 | $64,049.98 | $-6,829.52 | Keep baseline only |
| `SPX500_USD` | $50,231.99 | $63,202.43 | $12,970.44 | Enable FWM lane |
| `UK100_GBP` | $35,697.63 | $44,408.41 | $8,710.78 | Enable FWM lane |
| `USD_JPY` | $66,670.57 | $75,304.96 | $8,634.39 | Enable FWM lane |
| `NZD_USD` | $54,636.15 | $90,991.85 | $36,355.70 | Enable FWM lane |
| `AUD_USD` | $42,000.01 | $63,370.02 | $21,370.01 | Enable FWM lane |
| `EUR_USD` | $41,390.63 | $48,986.30 | $7,595.67 | Enable FWM lane |
| `GBP_JPY` | $35,181.40 | $30,603.41 | $-4,577.99 | Keep baseline only |

## Applied Step

I applied the next research step immediately by building a `fwm_selective` mode:

- `FWM enabled`: `SPX500_USD`
- `FWM enabled`: `UK100_GBP`
- `FWM enabled`: `USD_JPY`
- `FWM enabled`: `NZD_USD`
- `FWM enabled`: `AUD_USD`
- `FWM enabled`: `EUR_USD`
- `Baseline only`: `NAS100_USD`
- `Baseline only`: `GBP_JPY`

## Selective Mode Result

| Mode | Ending Balance | Net PnL | Return | PF | Max DD | Trades Taken |
|---|---:|---:|---:|---:|---:|---:|
| baseline | $496,687.88 | $396,687.88 | 396.69% | 1.28 | $13,606.74 | 15402 |
| fwm_selective | $599,577.87 | $499,577.87 | 499.58% | 1.34 | $9,894.79 | 16385 |

## Recommended Sequence

1. Keep current live CWT unchanged.
2. Treat `fwm_selective` as the new research benchmark challenger, not `fwm_gate`.
3. Run a second-pass sensitivity study on `fwm_selective` only:
   - `FWM swing lookback`: test `6 / 8 / 10`
   - `FWM order validity`: test `1 / 2 / 3` bars
   - `FWM gate window`: do not advance unless needed later
4. Only if `fwm_selective` stays stronger after sensitivity testing should phase 2 consider fractal confirmation.
5. Keep AO / Second Wise Man / pyramiding out until after that.

## Practical Recommendation

The clean next research lane is not a global Bill Williams conversion. It is a selective hybrid: baseline CWT everywhere, with FWM entry-lane enabled only on the six symbols that improved.
