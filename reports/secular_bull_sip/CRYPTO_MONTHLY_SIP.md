# Secular Bull SIP Crypto Slice

## Test Setup

- Date range: `2020-01-01` to `2026-04-01`
- Starting capital reference: `$100,000`
- Monthly contribution per asset test: `$8,333.33`
- Variant: pure monthly SIP baseline
- Long-only
- No leverage
- No stop loss
- One asset per simulation

## Results

| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Month | Worst Month | Best Year | Worst Year |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BTC_USD` | Bitcoin | 75 | 625,000.00 | 1,590,286.43 | 965,286.43 | 2.54 | 43.56% | 30.52% | 1,113,782.77 | 66.26% | 54.67% | 49.59% | -41.08% | 271.79% | -40.27% |
| `ETH_USD` | Ethereum | 74 | 616,666.67 | 1,274,185.80 | 657,519.14 | 2.07 | 48.97% | 23.98% | 1,460,838.63 | 77.12% | 51.35% | 83.13% | -48.25% | 648.64% | -41.16% |
| `BCH_USD` | Bitcoin Cash | 74 | 616,666.67 | 1,089,997.97 | 473,331.30 | 1.77 | 3.72% | 18.78% | 486,739.86 | 82.58% | 48.65% | 167.46% | -50.60% | 80.73% | -52.94% |
| `LTC_USD` | Litecoin | 74 | 616,666.67 | 413,966.25 | -202,700.41 | 0.67 | -3.67% | -13.19% | 408,089.37 | 72.64% | 52.70% | 55.49% | -34.46% | 98.31% | -49.06% |

## Quick Read

- Best money-weighted return: `BTC_USD` with XIRR `30.52%` and net PnL `$965,286.43`.
- Lowest drawdown: `BTC_USD` with max DD `66.26%`.
- Crypto remains the highest-volatility sleeve in this SIP baseline, so the upside and pain should be read together.