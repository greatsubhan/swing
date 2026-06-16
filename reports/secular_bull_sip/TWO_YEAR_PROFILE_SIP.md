# Two-Year SIP Profile Study

## Setup

- Assets: Gold, Silver, Nasdaq 100, Dow Jones 30, Bitcoin
- Window length: 24 months
- Step between windows: 12 months
- SIP entries: first trading day of each month
- Tested leverage: `1x`, `2x`, `3x`
- Tested stops: `10%`, `15%`, `20%`
- Withdrawal overlays:
  - `none`
  - `skim_half_above_base`

## Firm Profiles

### FTMO Swing

- Daily rule mode: `start_balance`
- Daily loss: `5%`
- Overall rule mode: `static`
- Overall loss: `10%`
- Weekend holding assumed allowed: `True`
- Sources:
  - [https://ftmo.com/en/trading-objectives/](https://ftmo.com/en/trading-objectives/)
  - [https://ftmo.com/en/faq/ftmo-swing-account-type/](https://ftmo.com/en/faq/ftmo-swing-account-type/)

### The5ers High Stakes

- Daily rule mode: `max_balance_equity`
- Daily loss: `5%`
- Overall rule mode: `static`
- Overall loss: `10%`
- Weekend holding assumed allowed: `True`
- Sources:
  - [https://help.the5ers.com/what-is-the-maximum-loss-and-the-maximum-daily-loss-in-the-high-stakes-program/](https://help.the5ers.com/what-is-the-maximum-loss-and-the-maximum-daily-loss-in-the-high-stakes-program/)
  - [https://help.the5ers.com/do-i-have-to-close-my-positions-overnight/](https://help.the5ers.com/do-i-have-to-close-my-positions-overnight/)

### FundedNext Stellar Instant

- Daily rule mode: `none`
- Daily loss: `0%`
- Overall rule mode: `trailing_capped_initial`
- Overall loss: `6%`
- Weekend holding assumed allowed: `True`
- Sources:
  - [https://help.fundednext.com/en/articles/11641163-what-are-the-daily-loss-limit-and-the-maximum-loss-limit-for-the-stellar-instant-accounts](https://help.fundednext.com/en/articles/11641163-what-are-the-daily-loss-limit-and-the-maximum-loss-limit-for-the-stellar-instant-accounts)
  - [https://help.fundednext.com/en/articles/11641232-are-there-restrictions-for-overnight-or-weekend-trading](https://help.fundednext.com/en/articles/11641232-are-there-restrictions-for-overnight-or-weekend-trading)

## Best Result Per Asset / Profile / Withdrawal Mode

| Profile | Withdrawal | Asset | Best Window | Lev | Stop | Size Mult | End Equity $ | Vault $ | Total Wealth $ | Net PnL $ | Return % | Max DD % | Max Daily Loss $ | Payouts | Verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| FTMO Swing | No Withdrawal | `XAU_USD` | `2024-01-01_to_2025-12-31` | 3x | 10% | 1.00 | 446,658.59 | 0.00 | 446,658.59 | 346,658.59 | 346.66% | 21.53% | 28,270.46 | 0 | Keep |
| FTMO Swing | No Withdrawal | `XAG_USD` | `2024-01-01_to_2025-12-31` | 3x | 20% | 1.00 | 870,921.93 | 0.00 | 870,921.93 | 770,921.93 | 770.92% | 45.98% | 142,798.27 | 0 | Keep |
| FTMO Swing | No Withdrawal | `NAS100_USD` | `2023-01-01_to_2024-12-31` | 3x | 15% | 1.00 | 293,983.24 | 0.00 | 293,983.24 | 193,983.24 | 193.98% | 40.25% | 26,820.27 | 0 | Keep |
| FTMO Swing | No Withdrawal | `US30_USD` | `2020-01-01_to_2021-12-31` | 3x | 10% | 1.00 | 210,193.57 | 0.00 | 210,193.57 | 110,193.57 | 110.19% | 19.96% | 13,073.54 | 0 | Keep |
| FTMO Swing | No Withdrawal | `BTC_USD` | `2023-01-01_to_2024-12-31` | 3x | 20% | 1.00 | 969,810.42 | 0.00 | 969,810.42 | 869,810.42 | 869.81% | 50.02% | 131,835.05 | 0 | Keep |
| FTMO Swing | Skim 25% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 3x | 10% | 1.00 | 221,906.64 | 224,751.95 | 446,658.59 | 346,658.59 | 346.66% | 40.86% | 28,270.46 | 22 | Keep |
| FTMO Swing | Skim 25% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.74 | 200,328.30 | 56,771.64 | 257,099.94 | 157,099.94 | 157.10% | 23.00% | 29,553.77 | 20 | Keep |
| FTMO Swing | Skim 25% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 3x | 10% | 0.78 | 135,871.62 | 88,687.61 | 224,559.23 | 124,559.23 | 124.56% | 32.04% | 17,352.49 | 20 | Keep |
| FTMO Swing | Skim 25% of month-end profit above $100k | `US30_USD` | `2020-01-01_to_2021-12-31` | 3x | 10% | 0.75 | 122,378.36 | 60,428.23 | 182,806.59 | 82,806.59 | 82.81% | 30.05% | 9,824.31 | 18 | Keep |
| FTMO Swing | Skim 25% of month-end profit above $100k | `BTC_USD` | `2023-01-01_to_2024-12-31` | 1x | 10% | 0.33 | 122,035.03 | 34,388.48 | 156,423.51 | 56,423.51 | 56.42% | 27.38% | 8,973.95 | 19 | Caution |
| FTMO Swing | Skim 50% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 3x | 10% | 0.71 | 146,007.57 | 198,583.08 | 344,590.65 | 244,590.65 | 244.59% | 43.47% | 19,946.69 | 21 | Keep |
| FTMO Swing | Skim 50% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.59 | 160,510.78 | 63,016.84 | 223,527.61 | 123,527.61 | 123.53% | 21.93% | 23,238.12 | 17 | Keep |
| FTMO Swing | Skim 50% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 2x | 10% | 0.55 | 108,313.60 | 50,201.00 | 158,514.60 | 58,514.60 | 58.51% | 20.19% | 8,151.73 | 19 | Keep |
| FTMO Swing | Skim 50% of month-end profit above $100k | `US30_USD` | `2023-01-01_to_2024-12-31` | 2x | 10% | 0.65 | 95,381.56 | 46,022.84 | 141,404.40 | 41,404.40 | 41.40% | 25.12% | 10,528.07 | 17 | Keep |
| FTMO Swing | Skim 50% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 2x | 10% | 0.51 | 112,531.12 | 25,110.52 | 137,641.64 | 37,641.64 | 37.64% | 16.05% | 11,583.22 | 4 | Caution |
| FTMO Swing | Skim 75% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 2x | 10% | 0.74 | 119,332.67 | 150,554.86 | 269,887.53 | 169,887.53 | 169.89% | 38.38% | 13,854.55 | 19 | Keep |
| FTMO Swing | Skim 75% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.51 | 143,430.38 | 65,061.77 | 208,492.16 | 108,492.16 | 108.49% | 21.26% | 20,409.64 | 14 | Keep |
| FTMO Swing | Skim 75% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.78 | 104,050.08 | 37,874.93 | 141,925.01 | 41,925.01 | 41.93% | 16.97% | 5,840.62 | 17 | Keep |
| FTMO Swing | Skim 75% of month-end profit above $100k | `US30_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.93 | 103,379.08 | 30,778.41 | 134,157.50 | 34,157.50 | 34.16% | 16.19% | 4,052.50 | 16 | Caution |
| FTMO Swing | Skim 75% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 20% | 0.49 | 104,405.67 | 28,378.94 | 132,784.61 | 32,784.61 | 32.78% | 15.57% | 10,012.23 | 5 | Caution |
| The5ers High Stakes | No Withdrawal | `XAU_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.53 | 161,302.82 | 0.00 | 161,302.82 | 61,302.82 | 61.30% | 10.59% | 4,999.33 | 0 | Keep |
| The5ers High Stakes | No Withdrawal | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 20% | 0.10 | 126,977.25 | 0.00 | 126,977.25 | 26,977.25 | 26.98% | 4.80% | 4,997.01 | 0 | Reject |
| The5ers High Stakes | No Withdrawal | `NAS100_USD` | `2023-01-01_to_2024-12-31` | 1x | 10% | 0.61 | 136,516.25 | 0.00 | 136,516.25 | 36,516.25 | 36.52% | 15.95% | 4,999.65 | 0 | Caution |
| The5ers High Stakes | No Withdrawal | `US30_USD` | `2020-01-01_to_2021-12-31` | 2x | 10% | 0.57 | 142,129.67 | 0.00 | 142,129.67 | 42,129.67 | 42.13% | 11.25% | 4,998.33 | 0 | Keep |
| The5ers High Stakes | No Withdrawal | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 15% | 0.44 | 117,879.22 | 0.00 | 117,879.22 | 17,879.22 | 17.88% | 6.95% | 4,998.32 | 0 | Caution |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.53 | 121,557.87 | 39,744.95 | 161,302.82 | 61,302.82 | 61.30% | 15.57% | 4,999.33 | 22 | Keep |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 20% | 0.10 | 117,064.65 | 9,912.60 | 126,977.25 | 26,977.25 | 26.98% | 5.58% | 4,997.01 | 21 | Reject |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `NAS100_USD` | `2023-01-01_to_2024-12-31` | 1x | 10% | 0.61 | 108,832.40 | 27,683.84 | 136,516.25 | 36,516.25 | 36.52% | 18.68% | 4,999.65 | 23 | Caution |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `US30_USD` | `2020-01-01_to_2021-12-31` | 2x | 10% | 0.57 | 111,385.48 | 30,744.19 | 142,129.67 | 42,129.67 | 42.13% | 17.17% | 4,998.33 | 18 | Keep |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 15% | 0.44 | 111,559.11 | 6,320.11 | 117,879.22 | 17,879.22 | 17.88% | 7.26% | 4,998.32 | 3 | Caution |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.53 | 111,531.08 | 49,771.75 | 161,302.82 | 61,302.82 | 61.30% | 17.54% | 4,999.33 | 21 | Keep |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 20% | 0.10 | 113,042.39 | 13,934.85 | 126,977.25 | 26,977.25 | 26.98% | 5.92% | 4,997.01 | 17 | Reject |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.67 | 105,098.49 | 30,786.81 | 135,885.29 | 35,885.29 | 35.89% | 12.95% | 4,999.22 | 19 | Caution |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `US30_USD` | `2020-01-01_to_2021-12-31` | 2x | 10% | 0.55 | 105,867.98 | 34,647.53 | 140,515.51 | 40,515.51 | 40.52% | 18.34% | 4,806.82 | 16 | Keep |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 15% | 0.44 | 106,580.15 | 11,299.07 | 117,879.22 | 17,879.22 | 17.88% | 8.42% | 4,998.32 | 3 | Caution |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.53 | 106,976.07 | 54,326.75 | 161,302.82 | 61,302.82 | 61.30% | 18.19% | 4,999.33 | 19 | Keep |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 20% | 0.10 | 110,642.53 | 16,334.71 | 126,977.25 | 26,977.25 | 26.98% | 6.31% | 4,997.01 | 14 | Reject |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.67 | 103,466.62 | 32,418.67 | 135,885.29 | 35,885.29 | 35.89% | 14.69% | 4,999.22 | 17 | Caution |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `US30_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.93 | 103,379.08 | 30,778.41 | 134,157.50 | 34,157.50 | 34.16% | 16.19% | 4,052.50 | 16 | Caution |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 15% | 0.44 | 102,732.74 | 15,146.48 | 117,879.22 | 17,879.22 | 17.88% | 10.35% | 4,998.32 | 3 | Caution |
| FundedNext Stellar Instant | No Withdrawal | `XAU_USD` | `2024-01-01_to_2025-12-31` | 3x | 10% | 1.00 | 446,658.59 | 0.00 | 446,658.59 | 346,658.59 | 346.66% | 21.53% | 28,270.46 | 0 | Keep |
| FundedNext Stellar Instant | No Withdrawal | `XAG_USD` | `2024-01-01_to_2025-12-31` | 3x | 20% | 1.00 | 870,921.93 | 0.00 | 870,921.93 | 770,921.93 | 770.92% | 45.98% | 142,798.27 | 0 | Keep |
| FundedNext Stellar Instant | No Withdrawal | `NAS100_USD` | `2023-01-01_to_2024-12-31` | 3x | 15% | 1.00 | 293,983.24 | 0.00 | 293,983.24 | 193,983.24 | 193.98% | 40.25% | 26,820.27 | 0 | Keep |
| FundedNext Stellar Instant | No Withdrawal | `US30_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.91 | 133,422.15 | 0.00 | 133,422.15 | 33,422.15 | 33.42% | 9.50% | 3,965.26 | 0 | Caution |
| FundedNext Stellar Instant | No Withdrawal | `BTC_USD` | `2023-01-01_to_2024-12-31` | 2x | 10% | 0.65 | 318,368.44 | 0.00 | 318,368.44 | 218,368.44 | 218.37% | 35.45% | 34,730.69 | 0 | Keep |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.50 | 120,159.04 | 37,166.01 | 157,325.05 | 57,325.05 | 57.33% | 14.80% | 4,674.93 | 22 | Caution |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.22 | 129,957.09 | 16,951.48 | 146,908.57 | 46,908.57 | 46.91% | 9.15% | 8,824.48 | 20 | Reject |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.31 | 104,743.73 | 11,728.21 | 116,471.94 | 16,471.94 | 16.47% | 5.69% | 2,294.72 | 20 | Caution |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `US30_USD` | `2023-01-01_to_2024-12-31` | 1x | 10% | 0.41 | 101,669.93 | 11,512.67 | 113,182.60 | 13,182.60 | 13.18% | 7.87% | 3,351.99 | 20 | Reject |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 20% | 0.22 | 108,959.70 | 5,954.33 | 114,914.04 | 14,914.04 | 14.91% | 5.83% | 4,554.66 | 7 | Reject |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.23 | 104,950.99 | 21,370.01 | 126,321.00 | 26,321.00 | 26.32% | 8.52% | 2,146.51 | 21 | Reject |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.22 | 122,524.44 | 23,457.29 | 145,981.73 | 45,981.73 | 45.98% | 9.66% | 8,650.12 | 17 | Reject |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.29 | 102,189.84 | 13,223.19 | 115,413.03 | 15,413.03 | 15.41% | 5.80% | 2,147.21 | 19 | Caution |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `US30_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.33 | 101,740.39 | 10,276.16 | 112,016.55 | 12,016.55 | 12.02% | 5.82% | 1,425.66 | 16 | Reject |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 20% | 0.21 | 104,635.00 | 9,342.81 | 113,977.81 | 13,977.81 | 13.98% | 6.05% | 4,268.74 | 5 | Reject |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `XAU_USD` | `2024-01-01_to_2025-12-31` | 1x | 10% | 0.14 | 101,894.10 | 14,750.48 | 116,644.58 | 16,644.58 | 16.64% | 5.67% | 1,357.39 | 19 | Reject |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `XAG_USD` | `2024-01-01_to_2025-12-31` | 1x | 20% | 0.10 | 110,543.53 | 16,182.76 | 126,726.30 | 26,726.30 | 26.73% | 6.25% | 4,950.53 | 14 | Reject |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `NAS100_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.26 | 101,319.72 | 12,341.53 | 113,661.25 | 13,661.25 | 13.66% | 5.84% | 1,903.16 | 17 | Reject |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `US30_USD` | `2020-01-01_to_2021-12-31` | 1x | 10% | 0.32 | 101,165.69 | 10,617.70 | 111,783.39 | 11,783.39 | 11.78% | 5.85% | 1,398.00 | 16 | Reject |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `BTC_USD` | `2022-01-01_to_2023-12-31` | 1x | 20% | 0.19 | 101,739.31 | 11,203.71 | 112,943.02 | 12,943.02 | 12.94% | 6.80% | 3,952.72 | 5 | Reject |

## Multi-Account Sleeve Summary

| Profile | Withdrawal | Window | Total Wealth $ | End Equity $ | Vault $ | Mean Size Mult | Keep Count | Caution Count |
|---|---|---|---:|---:|---:|---:|---:|---:|
| FTMO Swing | No Withdrawal | `2020-01-01_to_2021-12-31` | 1,363,834.55 | 1,363,834.55 | 0.00 | 0.84 | 3 | 0 |
| FTMO Swing | No Withdrawal | `2021-01-01_to_2022-12-31` | 475,918.82 | 475,918.82 | 0.00 | 0.16 | 0 | 0 |
| FTMO Swing | No Withdrawal | `2022-01-01_to_2023-12-31` | 596,124.66 | 596,124.66 | 0.00 | 0.57 | 0 | 3 |
| FTMO Swing | No Withdrawal | `2023-01-01_to_2024-12-31` | 1,669,738.08 | 1,669,738.08 | 0.00 | 0.74 | 4 | 0 |
| FTMO Swing | No Withdrawal | `2024-01-01_to_2025-12-31` | 1,662,744.68 | 1,662,744.68 | 0.00 | 0.71 | 2 | 1 |
| FTMO Swing | Skim 25% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 736,875.49 | 544,743.02 | 192,132.48 | 0.52 | 2 | 0 |
| FTMO Swing | Skim 25% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 482,402.28 | 473,257.69 | 9,144.60 | 0.13 | 0 | 0 |
| FTMO Swing | Skim 25% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 595,692.95 | 556,149.89 | 39,543.06 | 0.55 | 0 | 3 |
| FTMO Swing | Skim 25% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 715,489.15 | 542,299.86 | 173,189.29 | 0.57 | 3 | 1 |
| FTMO Swing | Skim 25% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 1,026,951.18 | 719,604.39 | 307,346.80 | 0.52 | 2 | 0 |
| FTMO Swing | Skim 50% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 616,763.59 | 498,835.47 | 117,928.12 | 0.40 | 2 | 0 |
| FTMO Swing | Skim 50% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 483,781.64 | 472,111.69 | 11,669.95 | 0.19 | 0 | 0 |
| FTMO Swing | Skim 50% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 593,669.71 | 534,456.80 | 59,212.91 | 0.59 | 0 | 3 |
| FTMO Swing | Skim 50% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 669,594.02 | 495,084.41 | 174,509.60 | 0.56 | 2 | 1 |
| FTMO Swing | Skim 50% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 890,742.23 | 599,878.46 | 290,863.78 | 0.42 | 2 | 0 |
| FTMO Swing | Skim 75% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 591,863.63 | 490,952.52 | 100,911.10 | 0.52 | 1 | 1 |
| FTMO Swing | Skim 75% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 484,601.33 | 471,454.10 | 13,147.21 | 0.21 | 0 | 0 |
| FTMO Swing | Skim 75% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 587,709.00 | 521,335.30 | 66,373.69 | 0.57 | 0 | 3 |
| FTMO Swing | Skim 75% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 627,250.57 | 481,546.39 | 145,704.19 | 0.50 | 0 | 3 |
| FTMO Swing | Skim 75% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 800,799.86 | 554,679.05 | 246,120.79 | 0.41 | 2 | 0 |
| The5ers High Stakes | No Withdrawal | `2020-01-01_to_2021-12-31` | 605,488.83 | 605,488.83 | 0.00 | 0.58 | 1 | 1 |
| The5ers High Stakes | No Withdrawal | `2021-01-01_to_2022-12-31` | 475,918.82 | 475,918.82 | 0.00 | 0.16 | 0 | 0 |
| The5ers High Stakes | No Withdrawal | `2022-01-01_to_2023-12-31` | 574,918.97 | 574,918.97 | 0.00 | 0.57 | 0 | 3 |
| The5ers High Stakes | No Withdrawal | `2023-01-01_to_2024-12-31` | 639,471.14 | 639,471.14 | 0.00 | 0.51 | 1 | 2 |
| The5ers High Stakes | No Withdrawal | `2024-01-01_to_2025-12-31` | 613,717.87 | 613,717.87 | 0.00 | 0.33 | 1 | 0 |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 602,708.37 | 509,121.94 | 93,586.43 | 0.46 | 1 | 1 |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 482,402.28 | 473,257.69 | 9,144.60 | 0.13 | 0 | 0 |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 574,713.67 | 544,440.83 | 30,272.84 | 0.56 | 0 | 3 |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 639,471.14 | 526,146.53 | 113,324.59 | 0.51 | 1 | 2 |
| The5ers High Stakes | Skim 25% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 611,472.72 | 535,991.97 | 75,480.76 | 0.30 | 1 | 0 |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 594,134.28 | 495,620.36 | 98,513.93 | 0.43 | 1 | 1 |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 483,781.64 | 472,111.69 | 11,669.95 | 0.19 | 0 | 0 |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 573,907.29 | 528,505.83 | 45,401.46 | 0.57 | 0 | 3 |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 633,848.87 | 499,197.64 | 134,651.21 | 0.48 | 1 | 2 |
| The5ers High Stakes | Skim 50% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 610,904.04 | 517,933.58 | 92,970.46 | 0.29 | 1 | 0 |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 585,823.91 | 490,369.06 | 95,454.84 | 0.50 | 0 | 2 |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 484,601.33 | 471,454.10 | 13,147.21 | 0.21 | 0 | 0 |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 572,803.61 | 519,662.37 | 53,141.23 | 0.56 | 0 | 3 |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 615,808.96 | 485,051.44 | 130,757.53 | 0.43 | 0 | 3 |
| The5ers High Stakes | Skim 75% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 610,700.24 | 509,534.60 | 101,165.62 | 0.29 | 1 | 0 |
| FundedNext Stellar Instant | No Withdrawal | `2020-01-01_to_2021-12-31` | 784,730.64 | 784,730.64 | 0.00 | 0.58 | 2 | 1 |
| FundedNext Stellar Instant | No Withdrawal | `2021-01-01_to_2022-12-31` | 491,403.23 | 491,403.23 | 0.00 | 0.09 | 0 | 0 |
| FundedNext Stellar Instant | No Withdrawal | `2022-01-01_to_2023-12-31` | 549,324.45 | 549,324.45 | 0.00 | 0.30 | 0 | 2 |
| FundedNext Stellar Instant | No Withdrawal | `2023-01-01_to_2024-12-31` | 985,156.89 | 985,156.89 | 0.00 | 0.72 | 2 | 2 |
| FundedNext Stellar Instant | No Withdrawal | `2024-01-01_to_2025-12-31` | 1,634,203.42 | 1,634,203.42 | 0.00 | 0.54 | 2 | 0 |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 535,335.81 | 504,543.76 | 30,792.03 | 0.20 | 0 | 1 |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 491,856.72 | 487,331.85 | 4,524.87 | 0.08 | 0 | 0 |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 537,850.73 | 521,427.95 | 16,422.77 | 0.24 | 0 | 0 |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 573,467.25 | 512,077.07 | 61,390.17 | 0.30 | 0 | 1 |
| FundedNext Stellar Instant | Skim 25% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 616,517.88 | 550,323.13 | 66,194.75 | 0.23 | 0 | 1 |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 533,077.06 | 498,638.96 | 34,438.09 | 0.20 | 0 | 1 |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 492,001.66 | 485,831.61 | 6,170.05 | 0.09 | 0 | 0 |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 536,386.48 | 513,120.11 | 23,266.37 | 0.23 | 0 | 0 |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 539,571.06 | 499,648.05 | 39,923.01 | 0.15 | 0 | 0 |
| FundedNext Stellar Instant | Skim 50% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 584,246.84 | 525,072.47 | 59,174.37 | 0.17 | 0 | 0 |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `2020-01-01_to_2021-12-31` | 531,113.13 | 496,260.66 | 34,852.48 | 0.19 | 0 | 0 |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `2021-01-01_to_2022-12-31` | 492,164.39 | 485,001.11 | 7,163.28 | 0.10 | 0 | 0 |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `2022-01-01_to_2023-12-31` | 534,411.20 | 508,637.47 | 25,773.73 | 0.25 | 0 | 0 |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `2023-01-01_to_2024-12-31` | 537,249.84 | 495,292.55 | 41,957.29 | 0.14 | 0 | 0 |
| FundedNext Stellar Instant | Skim 75% of month-end profit above $100k | `2024-01-01_to_2025-12-31` | 555,238.11 | 509,092.70 | 46,145.40 | 0.13 | 0 | 0 |

## Notes

- `Vault` is withdrawn profit under the payout overlay. It represents money skimmed out of the account, not unrealized open equity.
- The payout overlay is a research approximation. It does not assume a specific challenge fee or exact payout schedule.
- FundedNext Stellar Instant uses a trailing max-loss rule in the profile model; because SIP is mostly open-equity driven, this remains an approximation rather than a broker-exact recreation.