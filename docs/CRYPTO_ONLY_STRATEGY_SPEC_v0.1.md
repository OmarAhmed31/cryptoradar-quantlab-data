# Crypto-Only Strategy Specification v0.1 (P0, DRAFT for review; NOTHING computed)

**Status:**
- P0 document only: no code, no backtest, no return, no new data.
- The Assessment v0.1 was approved (sha256 `5e11d706…4d6f`), with 3 reviewer amendments, which are applied here (§1, §6, §5).
- Protocol v1.2 FIXED. The Final Holdout is sealed.
- **P1 is not approved.**

**The idea, in one line:** a coin whose supply and demand balance changes. That shows first as a quiet range after a decline, then as a breakout bar with real volume and a strong close. We enter only after the move is confirmed and the confirming bar has closed.

**Discipline:**
- **One** definition per concept, **three** exit templates, and **no parameter search**.
- Every threshold below is fixed **now**, before any computation. It is either:
  - (a) a **coin-relative percentile** of the coin's own past, so no absolute number is fitted; or
  - (b) a stated **convention**, marked `CONV`.
- Nothing is tuned after results.

## 1. Universe (reviewer amendment 1: classification by economic nature, not by ticker)

- **Allowed:** a USDT spot pair that is **P1-eligible on the decision day** (the day's eligibility is known at 00:00 UTC and holds all day) **and** not in an excluded class.
- **Excluded classes, with every member in the dev and val packs (423 tickers reviewed):**

| Class (economic nature) | Members | Why excluded |
|---|---|---|
| Fiat-referenced stablecoins | USDC, PYUSD, USDG, USD1, EURT (EUR), **BRL1** (BRL) | designed to hold a fiat value |
| Failed / de-pegged stablecoins | **USTC** | stablecoin by design, **excluded even though it lost its peg** (reviewer) |
| Commodity-backed | XAUT, PAXG | gold claims |
| Liquid staking / wrapped | STETH, BETH, JITOSOL, **OKSOL** | claims on another coin |
| **To verify before P1** (sources not yet checked) | **USAT, CGL** | a possible US-dollar stablecoin and a possible gold token. Excluded **provisionally** unless documentation shows they are ordinary crypto |

- **Kept:** BTC, ETH and every other coin, including LUNA/LUNC (ordinary volatile tokens today), exchange tokens (OKB, BNB) and meme coins.
- The exclusion list is fixed now and hashed. **A ticker is never added to or removed from it after results.**

## 2. Bars and timing

- A bar t is the hourly candle [t, t+1h), and it is known at **t+1h**.
- Only traded bars exist (rule B). A missing hour means no trade.
- Indicators use **closed bars only**.

## 3. Definitions (each fixed now)

**3.1 Accumulation range (A), at the close of bar t−1, over W = 7 days = 168 hourly bars `CONV`:**
- `R_high` = the max high over the window, and `R_low` = the min low. `width` = R_high / R_low − 1.
- **A1, tight:** `width` ≤ the **25th percentile** of the same coin's 7-day widths, computed at every hour of the **prior 180 days**. This is coin-relative. It needs 180 days of history, so the first possible signal is around July 2024.
- **A2, after a decline:** R_high ≤ **0.80 ×** the max high of the 90 days **before** the window `CONV`. The range must sit at least 20% below the recent peak.

**3.2 Contraction (C), at bar t−1:**
- The 7-day realised volatility of hourly log returns < the 30-day realised volatility (the FD-1 F08 definition, < 1).

**3.3 Breakout (B), at bar t:**
- **close_t > R_high.** R_high comes from bars before t.
- The signal is available **only at t+1h**.

**3.4 Momentum confirmation (M), one rule with three parts, all on bar t:**
- **Relative volume:** vol_quote_t ≥ **2 ×** the median hourly vol_quote of the prior 7 days `CONV`.
- **Strong close:** the close-location value (close − low)/(high − low) ≥ **0.70** `CONV`.
- **Stronger than BTC:** the coin's 24-hour return to close_t > BTC's 24-hour return to the same hour.

**Signal** = A1 ∧ A2 ∧ C ∧ B ∧ M, with the coin in the allowed universe.
- **One open position per coin.**
- A new signal on that coin needs a new range, which means a full new 7-day window after the exit.

## 4. Exit templates (exactly three; the same stop for all)

**Stop:** R_low.
- If (entry − R_low)/entry > **15%** `CONV`, the trade is **skipped** and logged, because the risk is too wide for the sizing rule.

| Template | Exit rule |
|---|---|
| **X1, fixed 2R** | target = entry + 2 × (entry − stop); time exit after **7 days** `CONV` |
| **X2, next resistance** | target = the lowest prior swing high above the entry within the past 90 days. A swing high is a bar whose high is the max of ±24 bars, using past bars only. If there is none, the target is 3R. Time exit after 7 days |
| **X3, trailing** | no target. The stop trails at (the highest close since entry − 3 × ATR), with ATR = the mean hourly true range of the prior 7 days at entry, fixed for the trade. The stop never moves down. Time exit after 14 days `CONV` |

**Delisting during a trade:** U9b forced exit at the last trade price, minus costs.

## 5. Entry execution (reviewer amendment 3)

- The signal exists only after the breakout bar **closes** (t+1h).
- **Entry = the open of the first traded 1-minute candle in [t+1h, t+2h)**, plus costs (§7).
  - If there is **no traded minute** in that hour, the trade is **NO_FILL**. It is logged and not taken.
  - We never assume the breakout close as the fill price.

## 6. Intrabar ordering (reviewer amendment 2)

- Stops and targets are checked on **1-minute** candles.
- **If the stop and the target are both inside the same minute, the stop is assumed first** (worst case).
- **If a minute opens beyond a level (a gap), the fill is the minute's open** (worse than the level).
- The time exit is filled at the open of the first traded minute after the deadline.

## 7. Costs and slippage

Per side, applied to the strategy and to every baseline alike:

| Cost | Rule |
|---|---|
| **Fee** | 0.10%, a conservative taker assumption based on the account's observed fee. A 0.20% sensitivity is also run |
| **Half-spread** | Corwin–Schultz, the same frozen estimator as before: hours d-30…d-1, median, clipped at 0, ≥ 360 pairs. If it cannot be estimated, the trade is skipped |
| **Breakout and stop slippage add-on (data-based)** | **½ × (high − low)/open of the fill minute**, for entries and for stop or gap exits. It is the fill minute's own range, so it is larger exactly when the market is moving |

## 8. Position sizing and capital

- **Risk per trade:** **1% of equity** `CONV`. Notional = 1% × equity / ((entry − stop)/entry).
- **Caps:**
  - ≤ **10% of equity** per position `CONV`;
  - ≤ **1% of DV30_med** (as before);
  - at most **10 open positions** `CONV`.
- **No cash, or at the position limit:** the signal is SKIPPED_CAPITAL and logged. Signals are processed in time order, then by ticker.
- **Capital levels:** $1,000 and $10,000, with $100,000 reported for capacity only, as in the previous decision.

## 9. Comparisons (same dates, same capital, same costs)

| Baseline | Definition |
|---|---|
| **Cash** | 0% |
| **BTC** | buy and hold, with entry and exit costs |
| **Equal-weight crypto** | weekly equal weight over the **allowed** universe, with the excluded classes removed, the 1% DV30 cap and the same costs |

**Metrics:**
- **Net profit**;
- **expectancy per trade**, with a trade-level block bootstrap 95% CI;
- profit factor;
- win rate with average win and average loss;
- **max drawdown**;
- turnover and cost share;
- **capital lock** (the average share of equity in positions);
- counts of NO_FILL / SKIPPED / forced exits;
- everything by market phase (MI phases on Development).

## 10. Data roles and the P1 decision gate (pre-registered now)

- **P1 runs on Development only** (2024-01-01 → 2025-08-31). Signals need 187 days of history, so they start around July 2024.
- **The result is exploratory**: it decides only whether to continue.
- **Validation is not used.** The Holdout stays sealed.
- **GO to the next step** requires at least one template, at $10,000 **and** $1,000, with all of the following:
  - **≥ 100 completed trades** `CONV`. Below that the result is "INCONCLUSIVE", not GO.
  - **Net expectancy per trade > 0 with a 95% CI lower bound > 0.**
  - **Total net return > Cash and > Equal-weight crypto.**
  - **The BTC comparison is reported and stated plainly.** If BTC buy-and-hold beats the system, the result is labelled `BELOW_BTC`.
- **Otherwise: STOP.** We do not tweak definitions to rescue a STOP.

## 11. Evidence budget (to be decided before P3, raised now)

- **Forward Shadow** (from 2026-11-01) will collect trades slowly, because breakouts are rare.
- The **Final Holdout** (2026-04-08 → 2026-10-31, about 7 months) is the only substantial unseen block. Opening it needs Protocol v1.3 with an external signature.
- **Proposal:** decide **before P1 results** which of the two will serve as the P3 test, so the choice cannot be influenced by P1.
