# Secular Bull SIP Baseline

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
| `XAU_USD` | Gold | 75 | 625,000.00 | 1,397,246.31 | 772,246.31 | 2.24 | 19.61% | 26.22% | 174,589.25 | 11.11% | 57.33% | 13.25% | -11.58% | 74.95% | -4.65% |
| `ETH_USD` | Ethereum | 74 | 616,666.67 | 1,274,185.80 | 657,519.14 | 2.07 | 48.97% | 23.98% | 1,460,838.63 | 77.12% | 51.35% | 83.13% | -48.25% | 648.64% | -41.16% |
| `NAS100_USD` | Nasdaq 100 | 75 | 625,000.00 | 1,023,223.93 | 398,223.93 | 1.64 | 17.53% | 16.00% | 67,632.28 | 15.48% | 62.67% | 14.23% | -13.58% | 44.88% | -18.92% |
| `US30_USD` | Dow Jones 30 | 75 | 625,000.00 | 836,841.65 | 211,841.65 | 1.34 | 8.24% | 9.46% | 36,938.21 | 7.10% | 61.33% | 13.79% | -14.33% | 16.96% | -5.15% |

## Notes

- `TWR Ann.` is the annualized time-weighted return across monthly contributions.
- `XIRR` is the money-weighted annualized return using monthly contributions and final liquidation value.
- `MOIC` = ending value divided by total contributed capital.
- This is the pure baseline only. Leveraged and correction-filter variants still need their own passes.