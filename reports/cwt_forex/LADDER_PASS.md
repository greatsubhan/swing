# CWT Ladder Pass

## Ladder Tested

Working ladder used for this pass:

- `0.15%`
- `0.30%`
- `0.60%`
- `1.20%`

Reset rule:

- after a winning trade, reset to `0.15%`
- after a losing or non-positive trade, advance one step
- once `1.20%` is reached, remain capped there until a win resets the ladder

This is the mathematically consistent `+0.15% recovery` ladder from the lecture notes.

## Scope

Focused symbols:

- `USD_JPY`
- `EUR_USD`
- `NZD_USD`
- `USD_CAD`

All tests were run on:

- `M5`
- `H1` bias
- `Scenario 1`, `Scenario 2`, and `both`
- exits:
  - `1:1`
  - `Jaw trailing`

## Main Read

### Where the ladder clearly helps

The ladder improved net percentage on every tested `1:1` configuration in this pass.

Strong examples:

- `USD_JPY rr1 both`: `20.949% -> 56.934%`
- `NZD_USD rr1 both`: `10.985% -> 37.687%`
- `EUR_USD rr1 both`: `7.503% -> 34.773%`
- `USD_CAD rr1 both`: `10.895% -> 33.414%`

This is where the ladder currently looks most believable.

### Where the ladder is mixed

The ladder also improved many `Jaw trailing` runs, but those need more caution.

Some examples:

- `USD_JPY jaw both`: `27.021% -> 192.872%`
- `NZD_USD jaw both`: `20.166% -> 122.504%`
- `EUR_USD jaw both`: `14.927% -> 23.273%`

But:

- `EUR_USD jaw scenario1`: `6.682% -> -0.241%`

So trailing plus ladder is not uniformly better.

### Where results are suspicious

Some trailing results, especially on `USD_CAD`, are too explosive to trust at face value:

- `USD_CAD jaw both`: `345.106% -> 2769.014%`
- `USD_CAD jaw scenario2`: `352.543% -> 2789.072%`

These are likely being amplified by extremely tight structural stop distances in the current approximate Cambist model.

They are saved in the raw report, but should not be used as proof of production-grade edge yet.

## Scenario Read

### 1:1

Scenario 2 generally looks stronger than Scenario 1.

Examples:

- `USD_JPY rr1`
  - Scenario 1 ladder: `39.192%`
  - Scenario 2 ladder: `29.242%`
  - Both ladder: `56.934%`

- `NZD_USD rr1`
  - Scenario 1 ladder: `7.338%`
  - Scenario 2 ladder: `22.936%`
  - Both ladder: `37.687%`

- `USD_CAD rr1`
  - Scenario 1 ladder: `15.658%`
  - Scenario 2 ladder: `30.877%`
  - Both ladder: `33.414%`

So for `1:1`, Scenario 2 is usually the better single scenario.

### Jaw trailing

Scenario 2 often carries more of the upside, but it also brings much longer losing streaks.

Examples:

- `USD_JPY jaw scenario2`
  - max loss streak: `34`
- `EUR_USD jaw scenario2`
  - max loss streak: `27`

This means Scenario 2 + trailing + ladder can make more money on paper, but it is much harder to trust emotionally and operationally.

## Keep / Caution / Discard

### Keep for next pass

- `USD_JPY rr1`
- `NZD_USD rr1`
- `EUR_USD rr1`
- `USD_CAD rr1`

These are the cleanest ladder beneficiaries.

### Keep with caution

- `USD_JPY jaw_trail`
- `NZD_USD jaw_trail`
- `EUR_USD jaw_trail`

These improve, but the low hit rate and longer loss streaks make them much more dangerous with a recovery ladder.

### Do not trust yet

- `USD_CAD jaw_trail`

The current output is too extreme and likely distorted by the stop-distance model.

## Current Recommendation

If we had to freeze a practical CWT money-management version right now, it would be:

- `H1` bias
- `M5`
- `Scenario 1 + Scenario 2`
- fixed `1:1`
- ladder: `0.15 / 0.30 / 0.60 / 1.20`

This is not necessarily the most exciting version, but it is the most believable version after the first ladder pass.
