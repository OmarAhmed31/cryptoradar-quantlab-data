# Crypto-Only Strategy Specification v0.1.3 (P0.1.2 content, complete): DRAFT for review; NOTHING computed

**Version note:**
- The file name **v0.1.2** was already used, by a partial draft (sha256 `e6c8ea09…7ec7`, commit `3c058b9`) written before the reviewer's U1–U7 decisions arrived.
- Every upload gets a new version number, so the **complete** P0.1.2 requested by the reviewer is issued as **v0.1.3**.
- It contains:
  - all of P0.1.1, unchanged except where a decision requires a change;
  - the reviewer's decisions U1, U2, U3, U5, U6 and U7;
  - U8;
  - the experiment registry, multiple-testing controls and the proposed Holdout budget;
  - a list of the items still pending.

**Status:**
- No code, no simulation, no backtest, no returns.
- Protocol v1.2 FIXED. The Final Holdout is sealed.
- **P1 is NOT approved** until this document is explicitly approved.
- `CONV` = a convention fixed before any result. `PROPOSED` = a numeric proposal **that needs the reviewer's review and fixing before P1**. ❓ = still pending.

## 1. Goal

A Spot system that finds coins in **accumulation**, sees **buying pressure** appear, waits for **momentum confirmation**, enters at an executable price, and exits with **net profit after fees and slippage**. It may **abstain** when there is no opportunity, and it adapts to the market state.

Chain: **Accumulation → Breakout → Momentum Confirmation → Entry → Trade Management → Exit**.

**Not** the goal: picking the least volatile coins, or statistics without trading value. There is no real trading before the system is proven on data not used to build it.

## 2. Use of prior work

**Reused:**
- the data packs (hourly OHLCV built from 1-minute candles, with delisted pairs and forced exits);
- Protocol v1.2 machinery (segment guard, H rules, one-shot runs, decision records);
- the FD-1 features (volatility F06–F09, BTC relation F12–F13, volume F17, F18, F19, position F20–F21);
- the cost model (0.10% taker assumption, Corwin–Schultz half-spread, DV30 cap, U9b forced exits);
- the test methods (destructive overwrite, naive recompute, mutants).

**Not usable as evidence:**
- the FD-2 and Validation ICs are rank associations, not trades;
- **A_N10 is closed for good** (PASS against B1, NOT PROFITABLE). It is never re-presented as profitable;
- **the earlier Validation period is not a new independent test for this direction.**

## 3. Crypto-only universe (classified by economic nature)

**Allowed:** a USDT spot pair that is **P1-eligible on the entry day** (eligibility is known at 00:00 UTC, past-only) and not in an excluded class.

**Excluded classes:** stablecoins; fiat-linked coins even after a de-peg; gold or commodity-backed tokens; wrapped tokens; staked tokens; derivative or synthetic tokens; any token whose exposure is to an external asset.

| Ticker (dev and val packs, 423 reviewed) | Class | Status |
|---|---|---|
| USDC, PYUSD, USDG, USD1 | USD stablecoin | excluded |
| EURT | EUR stablecoin | excluded |
| BRL1 | BRL stablecoin | excluded |
| **USAT** | **USD stablecoin** (USA₮, dollar-pegged, launched January 2026, issued by Anchorage Digital Bank; sources: Cointelegraph and others, 2026-01-27) | **excluded — verified** |
| USTC | stablecoin by design, de-pegged in 2022 | excluded (reviewer) |
| XAUT, PAXG | gold-backed | excluded |
| STETH, BETH, JITOSOL, OKSOL | staked or wrapped | excluded |
| **CGL** | **not verified** (no primary source) | **excluded (U6, reviewer)** until a reliable primary source establishes its economic nature. The project is not held up for one asset |
| everything else, including BTC, ETH, LUNA/LUNC, OKB, BNB and meme coins | ordinary crypto | allowed |

The classification is fixed **before** P1 and hashed. No future information is used for past eligibility.

## 4. Bars, timing and look-ahead

- A bar t is the hourly candle [t, t+1h) and is known at t+1h. Only closed bars are used.
- 1-minute candles are used **only** for fills and intrabar ordering.
- Every quantity uses data available at decision time. There is no look-ahead.

## 5. Entry

**5.1 Accumulation (A)** at the close of bar t−1. The window W = 7 days = 168 bars `CONV`.
- `R_high` = the window's max high, `R_low` = its min low, `width` = R_high/R_low − 1.
- **A1:** width ≤ the **25th percentile** `CONV` of the same coin's 7-day widths over the prior 180 days `CONV`. It is coin-relative. The first possible signal is around July 2024.
- **A2 (after a decline):** R_high ≤ **0.80** `CONV` × the max high of the 90 days `CONV` before the window.

**5.2 Contraction (C):** at bar t−1, the 7-day realised volatility < the 30-day realised volatility (FD-1 F08 < 1).

**5.3 Breakout (B):** close_t > R_high. R_high uses bars before t.

**5.4 Momentum confirmation (M):** one rule with three parts, all on bar t:
- vol_quote_t ≥ **2** `CONV` × the median hourly vol_quote of the prior 7 days;
- close-location value ≥ **0.70** `CONV`;
- the coin's 24-hour return to close_t > BTC's 24-hour return over the same hours.

**5.5 Execution (reviewer):**
- **Entry = the open of the first traded 1-minute candle in [t+1h, t+2h).**
- If there is no traded minute, the result is **NOT_EXECUTED**. It is logged and is not a trade.
- **One open position per coin.** A re-entry needs a new full 7-day window after the exit.

**5.6 Market-state filter:** §10 (PROPOSED numbers; they must be fixed before P1).

## 6. Stop loss (reviewer rules)

- **Stop = R_low.** If (entry − R_low)/entry > **15%** `CONV`, the trade is **SKIPPED_WIDE_STOP** and logged.
- **The stop is never widened or moved away from its original level.**
- Stops are checked on 1-minute candles. **If the stop and the target are both touched in the same minute, the stop is assumed first.** If a minute opens beyond the stop (a gap), the fill is that minute's open. No ideal fills are assumed.

## 7. Exit templates (exactly three; the trailing template is removed)

| Template | Target |
|---|---|
| **X1** | **2R**: entry_ref + 2 × (entry_ref − stop) `CONV`, where entry_ref is the entry fill price before costs |
| **X2** | **Next resistance**: the lowest **confirmed** swing high above the entry within the prior 90 days. A confirmed swing high is a bar whose high is the max of the 24 bars before and after it, and those after-bars must have closed before t. If there is none, the target is 3R `CONV` |
| **X3** | **A small fixed net target of +2%** `CONV`, using the formula below (U3) |

**X3 formula (U3, reviewer):** it is built on the **actual all-in entry cost**, never on the breakout bar's close.

- `entry_all_in = P_fill × (1 + fee + hs + slip_entry)`, where:
  - `P_fill` = the open of the first traded 1-minute candle after the breakout bar closes (§5.5);
  - `fee` = 0.10% taker (0.20% in the sensitivity run);
  - `hs` = the Corwin–Schultz half-spread (§9);
  - `slip_entry` = ½ × (high − low)/open of the fill minute (§9).
- `T_X3 = entry_all_in × 1.02 / (1 − fee)`.
- At the target the costs are: **the taker exit fee only**.
  - **No breakout slippage at the target** (U3).
  - **No maker fee** is assumed.
  - The half-spread at a resting-target exit is not applied (PROPOSED: a resting sell at T receives T; to be confirmed, item P-3 in §15).

**Target fill assumption (all templates, documented):**
- A target is filled at its price when a 1-minute candle's **high ≥ target**.
- **1-minute data does not prove queue priority or that a resting order was actually filled.** This is an assumption, and it is stated as such.
- The stop-first rule (§6) applies whenever both levels are touched in the same minute.

**Exit costs by exit type:**

| Exit type | Costs |
|---|---|
| target | fee |
| stop or gap | fee + hs + slippage of the fill minute |
| time exit | fee + hs + slippage of the fill minute |
| delisting | fee + hs at the U9b last trade price |

**Time exit:**
- **7 days** maximum `CONV`, then an exit at the first traded minute.
- **Descriptive only:** the same trades without the time exit, capped at **30 days** (protocol H_max).

**Delisting during a trade:** U9b forced exit.

## 8. Capital and position management (U2, reviewer)

**P1 scenarios (single position: at most 1 open trade):**

| Scenario | Sizing | Role |
|---|---|---|
| **A1, full available capital** | position = all available cash (after entry costs), capped only by **1% of DV30_med** and by execution | **PRIMARY**, the closest to current trading |
| **A2, 1% target risk** | notional = 1% × equity / ((entry_all_in − stop)/entry_all_in), capped by the available cash and by 1% of DV30_med | comparison |
| **B, up to 10 positions** | — | **NOT in P1.** A separate future experiment. Never used to raise the trade count |

**Conflict removed:**
- **The earlier 10%-of-equity per-position cap is removed for A1 and A2.** It contradicted A1.
- The caps that stay are the available cash (no leverage) and 1% DV30_med.
- A per-position cap for scenario B will be set in B's own plan.

**Invested ≠ at risk:**
- Investing 100% of capital does **not** mean risking 100%.
- The loss is set by the stop distance, gaps, slippage and costs.
- Every trade reports:
  - **the invested share** = position / equity;
  - **the planned risk share** = position × (entry_all_in − stop)/entry_all_in / equity;
  - **the realised risk** when a gap or costs exceed the plan.

The stop is **never** widened.

**The A1 test simulates the current trading style. It is NOT a recommendation to use full capital in real trading.**

**Capital levels:** $10,000 and $1,000 (with $100,000 for capacity display only), as decided earlier.

## 9. Costs and execution

| Cost | Rule |
|---|---|
| **Fee** | 0.10% taker per side, a conservative assumption based on the account's observed fee. **A 0.20% sensitivity is run** |
| **Half-spread** | Corwin–Schultz, frozen as before: hours d-30…d-1, median, clipped at 0, ≥ 360 pairs. If it cannot be estimated, the trade is skipped and logged |
| **Breakout slippage at entry, stop, gap and time exits (data-based)** | **½ × (high − low)/open of the fill minute** |
| **X3 target price** | the §7 formula: `T = entry_all_in × 1.02 / (1 − fee)`. No breakout slippage at the target (U3) |

If the data cannot support an executable cost, the trade is not taken, and the constraint is recorded. No value is invented.

## 10. Market states as point-in-time features (U1, reviewer): numbers PROPOSED, to be fixed before P1

**Decided:**
- The state is a **point-in-time feature** (`check_feature`), from past data only.
- **The MI-learned model is not used outside Development.**
- **The trend reference is the Equal-Weight crypto index of the eligible universe**, not BTC alone. BTC stays as the coin's relative-strength reference.
- There are **two independent dimensions** plus a Transition override, so the states are **not** mutually exclusive: Bull + High Volatility is possible.

**Index (PROPOSED):**
- `EW_ret(d)` = the mean of r_1(s, d) over the coins **allowed** on day d (crypto-only, P1-eligible) that have a value. r_1 is FD-1 F01: close_asof(d)/close_asof(d−1) − 1, known at d 00:00.
- If fewer than **20** `CONV` coins have a value, the day is `UNCERTAIN`.
- `EW_index(d)` = the cumulative product of (1 + EW_ret) from 2024-01-01.
- The state of day d is computed at **d 00:00** and applies to every hourly decision that day.

| Dimension | Definition (PROPOSED) | Needs |
|---|---|---|
| **Trend** | **Bull** if EW_index(d) > its 50-day mean **and** the 20-day EW return > +5%. **Bear** if EW_index(d) < its 50-day mean **and** the 20-day EW return < −5%. **Sideways** otherwise | ≥ 50 days of index, so it starts around 2024-02-20 (before the first signals, around July 2024) |
| **Volatility** | the std of EW_ret over the prior 30 days. Its percentile among **all prior** days (expanding, ≥ 60 prior values; the MI M2 rule reused): **High** > ⅔, **Low** < ⅓, **Normal** otherwise | ≥ 90 days |
| **Transition / Uncertain** (overrides the trend) | **Transition** if the trend label changed at least once in the last **5** days (d−4 … d). **Uncertain** if the index or a dimension is missing (fewer than 20 coins, or not enough history) | — |

**Per-state actions (PROPOSED; they keep the number of alternatives small):**

| State | Action |
|---|---|
| Bull | the normal §5 rules |
| Sideways | the normal §5 rules (range breakouts are the design itself) |
| Bear | **stricter confirmation:** RVOL ≥ **3** instead of 2, **and** the coin's 7-day return > BTC's 7-day return. Otherwise **abstain** |
| High Volatility (any trend) | **skip** if the stop distance > **8%** (instead of 15%). In A2, the risk drops to **0.5%** |
| Low Volatility | the normal rules |
| Transition / Uncertain | **abstain** (no new entries). Open trades follow their own exits |

**Missing data:** a missing input means `UNCERTAIN`, which means abstain. There is no imputation.

**Reporting:** every result is shown **per trend state and per volatility state**, and no state's losses are hidden in a total.

## 11. Evaluation

**Comparisons**, on the same period, capital and costs:
- **Cash**;
- **BTC buy-and-hold**;
- **Equal-weight crypto** (the allowed universe, weekly, with costs and the cap).

**Metrics:**
- net profit;
- **expectancy per trade**, with a trade-level bootstrap 95% CI;
- profit factor;
- win rate;
- average win and average loss;
- max drawdown;
- turnover;
- trading costs;
- **capital lock**;
- trade count;
- counts of NOT_EXECUTED / SKIPPED / forced exits;
- **everything per market state.**

**Each result gets one of these labels:**
- **PROFITABLE**;
- **LOSS_REDUCTION_ONLY**;
- **NO_EDGE**;
- **STATE_SPECIFIC** (it works in named states only).

`BELOW_BTC` is shown whenever the system trails BTC.

**P1 GO gate (exploratory; it decides only whether to continue):**
- It is evaluated on **Scenario A1 (primary)**, at $10,000 **and** $1,000, for at least one exit template. A2 is reported for comparison.
- It needs **≥ 100 completed trades** `CONV`.
- It needs a net expectancy > 0 with a 95% CI lower bound > 0, and a total net return > Cash and > Equal-weight crypto.
- Otherwise: **STOP**. Nothing is tweaked to rescue it.

**U7, the trade minimum (reviewer):**

| Result | Decision |
|---|---|
| ≥ 100 completed trades | evaluate the other P1 conditions |
| < 100 | **INCONCLUSIVE**, and **P1 stops with this result** |
| < 100 with a positive return | **not** a success |
| < 100 with a negative return | **not** enough evidence that the hypothesis failed |

**Forbidden in that case:**
- lowering the 100;
- changing filters after seeing results;
- adding positions to reach 100;
- widening the period or changing the design without a separate, pre-registered plan.

## 12. Final test and independent data (U5, reviewer)

- **The earlier Validation is not clean for this direction.**
- **Proposed confirmatory test: the Final Holdout** (2026-04-08 → 2026-10-31). It stays **sealed** through P0, P1 and any further development.
- **Opening conditions (U5):**
  - **Protocol v1.3**;
  - **an independent, authorised reviewer**, who is **not** the simulation developer and **not** the person who chose the strategy;
  - **a separate approval document** bound to the sha256 of the plan, code and tests, recording **the name of the authority, the approval date and the Protocol v1.3 hash**.
- **A review or approval by the assistant is NOT an external signature and does not authorise opening.**
- **No Holdout opening or test happens in this phase.** If the opening cannot be approved, it does not happen, and the test plan does not change after results.
- **Forward Shadow** (from 2026-11-01) is for operational verification and prospective evidence. It is paper only.

## 13. Relation to CryptoRadar

- The design follows CryptoRadar's spirit:
  - **Seed → Launch → Confirmed / Failed** maps to Accumulation → Breakout → Confirmation;
  - first-touch judgment after fees maps to the stop-first, cost-inclusive fills;
  - shadow testing;
  - adoption at 15/15, then 20/20;
  - the stop is never widened;
  - no long capital lock;
  - families per market state.
- **A family that proves itself** in the Quant Lab moves to CryptoRadar through its usual Shadow and adoption path.
- **The CryptoRadar briefing remains a private reference for the reviewer and is NOT in this public repo.**

## 14. Phases

| Phase | Status | Content |
|---|---|---|
| **P0.1.2** (file v0.1.3) | **this document** | for review |
| **P1** | not started; needs explicit approval of this document | trade simulator, tests and mutants **before any result**; the breakout study on **Development only**; comparisons; per-state results |
| P2 | optional; only if P1 succeeds **and** a specific question needs it | trades data, taker side |
| P3 | after a frozen system | the Final Holdout through its formal opening; Forward Shadow |

## 15. U8: Multi-Strategy Research & Historical Backtesting (reviewer decision; documentation only)

**Official project goal:** a system that can discover, evaluate and historically test **a library of Spot swing strategies** over the whole available data and universe, and use the strategy that suits each market state.

1. **Several independent strategies** on one shared foundation. Candidate patterns, **not** approved or proven:
   - Accumulation Breakout (the current P1);
   - Momentum Continuation;
   - Volatility Expansion;
   - Mean Reversion;
   - Trend Following;
   - Range Breakout.

   Each will be added **later** through its own frozen plan.
2. **Prior research as input:** FD-1, FD-2, Validation and the tested features generate hypotheses. They are not redone without a reason, and they are never automatic evidence of profit.
3. **Historical scope:**
   - active **and** delisted coins under the eligibility and timing rules, with no survivorship bias;
   - all available periods;
   - every market state (§10);
   - liquidity levels under the approved caps;
   - several capital sizes and position scenarios.
4. **One unified simulator** with the same fees, spread and slippage, liquidity and position sizing, entry and exit execution, stop and target handling, gap handling, and capital and risk management. Any difference between strategies is documented and justified.
5. **Strategy by market state:**
   - use a strategy for a state only if testing shows it works there;
   - reduce exposure when conditions are weak;
   - abstain when there is no opportunity.

   The selection system is **never** built or tuned on final-test periods.
6. **Current limit:** **no** backtest, simulation or return now. **P1 is not widened** and no extra strategy runs in this version.

## 16. Experiment registry, multiple testing and the Holdout budget (U8 §6; the author's U9 folded in)

1. **A central registry** of every experiment: successful and failed strategies, variants, hypotheses, frozen plans (with hashes), results and decisions.
2. **Selection accounts for the total number of experiments and tests**, never the best result alone, with a suitable **multiple-testing correction** for statistical comparisons.
3. **No strategy is re-tested on the same Holdout** after its results were seen and the strategy was changed.
4. **The experiment budget is fixed before the Holdout is reached.**
5. **PROPOSED Holdout budget:**
   - **at most 3 candidate strategies per opening cycle**, all **frozen** (plans, rules, code and tests) **before** the opening;
   - all evaluated in the **same** cycle under a pre-registered plan, with a correction for the number of candidates;
   - **no reopening** for a fourth strategy, or to fix one that failed.

   This number must be fixed in the formal opening plan. It does **not** change Protocol v1.2, and it does not bypass the v1.3 and independent-signature requirements.
6. **Execution order:**
   1. fix the U1 states;
   2. fix the unified simulator and the execution and cost rules;
   3. create the registry;
   4. develop and test strategies under separate frozen plans;
   5. choose candidates by pre-set criteria, not by top return;
   6. fix the number of finalists and the Holdout budget before requesting the formal opening.

## 17. Fixed controls

- Protocol v1.2 stays fixed. The Final Holdout stays sealed.
- No code, simulation, backtest or returns under this document.
- No threshold or filter changes after seeing results.
- Every new experiment needs a frozen specification and test plan before it runs.
- Earlier associational results are not proof of profit.
- The earlier Validation is not a new independent confirmation.
- Execution and cost rules must not differ between strategies in a way that prevents a fair comparison.

## 18. Items still needing a decision or approval

| # | Item | Status |
|---|---|---|
| **P-1** | **U1 numbers** in §10: the index construction, 50-day mean, ±5% over 20 days, 30-day vol and ⅓ / ⅔ percentiles, the 5-day Transition window, the 20-coin minimum | **PROPOSED**, to be fixed before P1 |
| **P-2** | **U1 per-state actions** in §10: Bear RVOL ≥ 3 plus 7-day strength over BTC; High-Vol stop limit 8% and A2 risk 0.5%; Transition abstains | **PROPOSED**, to be fixed before P1 |
| **P-3** | Whether the half-spread is applied at a resting-target exit (§7) | **PROPOSED** "not applied", to be confirmed |
| **P-4** | The **name** of the independent authorised reviewer for the Holdout (U5) | needed before any opening request; **not needed for P1** |
| **P-5** | The Holdout budget of **3** candidates (§16.5) | **PROPOSED**; it is fixed in the formal opening plan |
| **P-6** | CGL classification | excluded until a primary source is found (U6) |
| — | **P1 itself** | **NOT approved.** It needs explicit approval of this document, then a review of the simulator design and its tests |
