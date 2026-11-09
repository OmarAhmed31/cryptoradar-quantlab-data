# Crypto-Only Strategy Specification v0.1.2 (P0.1.2): unified + multi-strategy (DRAFT for review; NOTHING computed)

**Status:**
- **v0.1.2 = v0.1.1 + §16 (U8, reviewer decision: multi-strategy historical backtesting as an architectural goal) + §17 (U9, an author proposal: an evidence budget).** Nothing else changed.
- **U1–U7 are still unresolved.** The reviewer's consolidated decisions on them were not received, so no value was assumed.
- Specification revision only: **no code, no simulation, no backtest, no new calculations**.
- **It supersedes** the P0 v0.1 spec (sha256 `9b1267e2…1109`) and folds in the reviewer's "Unified Strategy Specification P0.1.1" message.
- It is consistent with Protocol v1.2 FIXED and with every earlier decision.
- **P1 waits for explicit approval of this document.**
- **Every number marked `CONV` is a convention fixed before any result.**
- **Every item marked ❓ is UNRESOLVED.** No value was invented for it, and §15 lists them for the reviewer.

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
| **CGL** ❓ | **not verified.** A search suggests a gaming token, but no primary source was obtained | **excluded provisionally**. If it is still unverified at P1 start, it stays excluded. One coin either way is immaterial |
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

**5.6 Market-state filter:** see §10, where this is ❓ unresolved.

## 6. Stop loss (reviewer rules)

- **Stop = R_low.** If (entry − R_low)/entry > **15%** `CONV`, the trade is **SKIPPED_WIDE_STOP** and logged.
- **The stop is never widened or moved away from its original level.**
- Stops are checked on 1-minute candles. **If the stop and the target are both touched in the same minute, the stop is assumed first.** If a minute opens beyond the stop (a gap), the fill is that minute's open. No ideal fills are assumed.

## 7. Exit templates (exactly three; the trailing template is removed per the reviewer)

| Template | Target |
|---|---|
| **X1** | **2R**: entry + 2 × (entry − stop) `CONV` |
| **X2** | **Next resistance**: the lowest **confirmed** swing high above the entry within the prior 90 days. A confirmed swing high is a bar whose high is the max of the 24 bars before **and** after it, and the 24 bars after it must have closed before t. If there is none, the target is 3R `CONV` |
| **X3** | **A small fixed net target of +2%** `CONV` (reviewer). The target price is set so that the trade nets **+2% after** the entry fee, the entry half-spread, the entry slippage, the exit fee and the exit half-spread. The exact formula is in §9. ❓ Whether a slippage add-on also applies **at the target fill** is unresolved (U3) |

**Time exit (all templates):**
- A maximum hold of **7 days** `CONV`, then an exit at the first traded minute.
- **Descriptive only:** the same trades **without** the time exit, capped at **30 days**, the protocol's H_max (H1). They can never run without limit, because the protocol caps every forward quantity at 30 days.

**Delisting during a trade:** U9b forced exit at the last trade price, minus costs.

## 8. Capital and position management

- **Target risk: 1% of equity per trade** `CONV`. Notional = 1% × equity / ((entry − stop)/entry).
- **Caps:**
  - ≤ **10% of equity** per position `CONV`;
  - ≤ 1% of DV30_med;
  - limited by the available cash;
  - costs are included.
- **When a cap binds, the actual risk taken is reported. It is never claimed to be 1%.**
- **Scenario A, single position (PRIMARY):** at most 1 open trade. ❓ Sizing is **unresolved** (U2): 1% risk with a 10% cap gives a position of about 10% of equity, which is **not** how the trades are placed today (the whole capital in one trade).
- **Scenario B, multi-position (future):** at most **10** open trades `CONV`. Signals are processed in time order, then by ticker. If there is no room, the signal is SKIPPED_CAPITAL and logged.
- Both scenarios are fixed **before** P1 and reported separately. **B can never replace A after the results.**
- **Capital levels:** $10,000 and $1,000, with $100,000 for capacity display only, as decided before.

## 9. Costs and execution

| Cost | Rule |
|---|---|
| **Fee** | 0.10% taker per side, a conservative assumption based on the account's observed fee. **A 0.20% sensitivity is run** |
| **Half-spread** | Corwin–Schultz, frozen as before: hours d-30…d-1, median, clipped at 0, ≥ 360 pairs. If it cannot be estimated, the trade is skipped and logged |
| **Breakout slippage at entry, stop, gap and time exits (data-based)** | **½ × (high − low)/open of the fill minute** |
| **X3 target price** | entry_fill_all_in × 1.02 / (1 − fee − half-spread [− slippage, ❓ U3]) |

If the data cannot support an executable cost, the trade is not taken, and the constraint is recorded. No value is invented.

## 10. Market adaptability (reviewer requirement): ❓ the main unresolved block

**Fixed principles:**
- the state is known **at decision time only**;
- no look-ahead;
- rules per state are allowed **only if fixed in advance**;
- trading is never forced in any state;
- results are **reported per state**, and no state's losses are hidden in an average;
- no rule is changed after results;
- **one adaptive system**, not a set of ad-hoc strategies.

**Required states:** Bull, Bear, Sideways, High Volatility, Low Volatility, Transition/Uncertain.

**Required behaviour:**

| State | Behaviour |
|---|---|
| Bull | breakouts and continuation |
| Bear | not every breakout; exceptional strength and stronger confirmation; abstaining allowed |
| Sideways | real accumulation and range breakouts |
| High Volatility | tighter entry and smaller risk |
| Low Volatility | watch the contraction |
| Transition | reduce exposure or abstain |

### Technical conflicts found

1. **The protocol forbids MI regime statistics outside Development.** `check_research_statistic` is Development-only, and the MI regime models (k = 3 clusters, S1/S2/S3 + UNKNOWN) produce no labels on Validation or the Holdout.
   - **Resolution path (no protocol change):** define the state as a **point-in-time feature**. It is computed from past data only, with **fixed rules and no fitted model**, and is allowed at any decision time through `check_feature`, exactly as the 22 features are.
2. **The MI clusters do not map onto the six states.** The six states need **new fixed definitions.**

### Unresolved items (no value is invented here)

- **U1a, trend state:** which index (BTC, or the equal-weight crypto universe) and which look-backs and thresholds define Bull / Bear / Sideways.
- **U1b, volatility state:** for example the existing MI M2 band (the percentile of market volatility among prior days, with LOW < ⅓ and HIGH > ⅔ already defined in MI). Is that reused?
- **U1c, Transition:** a definition, for example a trend state that changed within the last N days.
- **U1d, per-state action:** for each state, which of these applies:
  - trade normally;
  - a stricter confirmation (with which stricter number);
  - smaller risk (how much);
  - abstain.

  **Each option adds alternatives, so the total must stay small**, because of the data-snooping risk.

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
- It is evaluated on **Scenario A**, at $10,000 **and** $1,000, for at least one exit template.
- It needs **≥ 100 completed trades** `CONV`, otherwise the result is INCONCLUSIVE.
- It needs a net expectancy > 0 with a 95% CI lower bound > 0, and a total net return > Cash and > Equal-weight crypto.
- Otherwise: **STOP**. Nothing is tweaked to rescue it.
- ❓ **U7:** a single-position system with state filters may produce **fewer than 100 trades** on about 14 months of Development (signals start around July 2024). The reviewer should decide now whether INCONCLUSIVE in that case means STOP or something else.

## 12. Final test and independent data

- **The earlier Validation is not clean for this direction.**
- **Proposed confirmatory test: the Final Holdout** (2026-04-08 → 2026-10-31). It stays sealed through P0 and P1.
- It opens only after the strategy, code, tests and selection are frozen, and only through the formal procedure: **Protocol v1.3 with the external signature** (H7).
- ❓ **U5:** **who signs**, and how that signature is recorded, should be fixed now.
- If the opening cannot be approved, it is **not** opened, and the test plan does **not** change after results.
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
| **P0.1.1** | **this document** | for review |
| **P1** | not started; needs approval of P0.1.1 | trade simulator, tests and mutants **before any result**; the breakout study on **Development only**; comparisons; per-state results |
| P2 | optional; only if P1 succeeds **and** a specific question needs it | trades data, taker side |
| P3 | after a frozen system | the Final Holdout through its formal opening; Forward Shadow |

## 15. Unresolved items for the reviewer

| # | Item | Why it is open |
|---|---|---|
| **U1a–d** | Market-state definitions and per-state actions (§10) | A new requirement. MI clusters cannot be used outside Development. The numbers must come from the reviewer or from stated conventions |
| **U2** | Scenario A sizing | 1% risk (about 10% of equity per trade) **or** the full capital per trade (current practice) **or** both, reported separately with A as primary |
| **U3** | X3: is the exit slippage add-on included at the target fill? | Target fills are touches of a resting price, so they may not need the breakout slippage add-on |
| **U5** | Who gives the external signature for the Holdout, and how it is recorded | Required by H7 / v1.3 |
| **U6** | CGL classification | No primary source yet. It is excluded until verified |
| **U7** | The P1 gate when there are fewer than 100 trades | It is likely with a single position and state filters |

## 16. U8: Multi-Strategy Research & Historical Backtesting (reviewer decision, documented; NOT executed)

**Official project goal:** a system that can discover, evaluate and test **several** Spot swing strategies historically, over the whole available universe and period, and identify which strategies suit which market state.

1. **Architecture.** Strategies are **independent modules** on one shared foundation:
   - data packs;
   - the crypto-only universe;
   - point-in-time features;
   - the market-state feature (§10);
   - **one trade simulator** with the same fees, spread and slippage, liquidity and position caps, entry and exit execution, stop and target handling (including stop-first intrabar), gap handling, and capital and risk management.

   Any execution difference between two strategies must be documented and justified.
2. **Candidate patterns, NOT approved strategies:** Accumulation Breakout (the current P1), Momentum Continuation, Volatility Expansion, Mean Reversion, Trend Following, Range Breakout.
3. **Prior research is used as input for hypotheses.** FD-1, FD-2, Validation and the tested features are inputs, never automatic evidence of profit, and they are not redone without a reason.
4. **Historical scope:**
   - active **and** delisted coins, under the eligibility and timing rules, with no survivorship bias;
   - all available periods;
   - all market states;
   - liquidity levels under the approved caps;
   - several capital sizes and position scenarios.
5. **Selection by market state:**
   - use a strategy for a state only if testing shows it works there;
   - reduce exposure when conditions are weak;
   - abstain when there is no opportunity.

   The selection logic is **never** built or changed from final-test results.
6. **Integrity:**
   - Development is for discovery and development.
   - The earlier Validation is not a new independent test.
   - The Final Holdout stays sealed until its formal v1.3 opening.
   - Selection among several strategies accounts for **multiple testing**.
   - We never pick the highest return without checking its stability across periods, coins and states.
   - **Every new strategy gets its own frozen specification and test plan before it runs.**
7. **Current scope:** this is documentation only. There is no backtest, simulation or return now. **P1 stays limited to the Accumulation Breakout of §5–§9 and is not widened.**

| Item | Decision |
|---|---|
| U8 | Multi-Strategy Historical Backtesting is adopted as the future architecture, using the whole available historical universe. No extra tests start in P0.1.2, and the current P1 is not widened |

## 17. U9: evidence budget (author proposal; needs the reviewer's decision)

**Why:**
- Each strategy tried on the same Development data raises the chance that one looks good **by luck**.
- The Final Holdout can be opened **once**. If it is used to test strategies one after another, it stops being unseen.

**Proposal (no number assumed):**
1. **A pre-registered experiment log.** Every strategy and variant ever run on Development is recorded, including the failed ones. Selection accounts for the **total** number of trials, not only the best one.
2. **A fixed Holdout budget.** Before the Holdout is opened, the reviewer fixes the **maximum number K** of frozen strategies it will test. A multiple-testing correction across those K is applied, and **K cannot grow after the opening**.
3. **Order of work:**
   - first, the shared trade simulator and the market-state feature (U1), built once and tested once;
   - then strategies one by one, each with its own frozen plan;
   - the Holdout last, for the frozen set only.
