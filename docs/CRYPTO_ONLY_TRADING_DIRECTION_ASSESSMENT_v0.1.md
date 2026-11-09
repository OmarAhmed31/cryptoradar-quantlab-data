# Crypto-Only Trading Direction: Assessment v0.1 (2026-11-09)

**Status:**
- Assessment only, answering Developer Assessment Request v0.1.
- **No new code, no backtest, no simulation, no return computed, no new data collected.**
- Protocol v1.2 FIXED. FD-1, FD-2, Validation and A_N10 are closed and unchanged. The Final Holdout is sealed.

**Target chain under review:** Accumulation → Buying Pressure → Momentum Confirmation → Entry → Trade Management → Exit, judged on **net profit after all costs**.

---

## 1. Current data and tools

| Asset | What it is | Time resolution | Period | Notes |
|---|---|---|---|---|
| **Hourly OHLCV**: active, 466 pairs | `open, high, low, close, vol_base, vol_quote, traded_minutes`, built from OKX official **1-minute** candles (rule B: only minutes with volume > 0; hours with no trade are empty) | **1 h** (derived from 1 min) | 2024-01-01 → 2026-10-31 | Current listings only. Survivorship is covered by the delisted sets below |
| **Hourly OHLCV**: delisted, 141 + 8 pairs | Same format, cut at the official delisting (D2) | 1 h | 2024-01 → each pair's cut | 149 forced-exit prices (U9b), all PRICED within the Validation window |
| **1-minute candles** | The raw OKX archive files (in GitHub Releases as tars, with sha256 in the manifests) | **1 min** | Same | **No taker buy/sell split** in OKX candles |
| **Daily eligibility (P1 / S50k / S250k)** | THR30, DV30_med, assessable, eligible; past-only 30-day window | 1 day | 2024-01 → 2026-10 | Protocol v1.2 inputs |
| **Feature code** (FD-1 catalogue) | 22 point-in-time features, frozen and tested | daily decisions at 00:00 UTC | — | Reusable as is |
| **OKX trades archive (module 1)** | **Probed only**, not downloaded. Fields: `trade_id, side, price, size, created_time` | **per trade** (ms) | Available monthly and daily | `side` = the **taker side**, so real aggressor buy/sell volume could be computed. Size ranges from about 1 MB/month for small pairs to far larger for majors |
| **Order book history** | **None in the lab**. Availability through the OKX archive was **not probed** | — | — | Supply walls, absorption and depth **cannot** be measured today |
| **Simulator** | `lab/strategy.py`: weekly, portfolio-level, long-only, with costs (fee 0.10% taker assumption + Corwin–Schultz half-spread), 1% DV30 cap, forced exits | weekly rebalances | — | **Not** a trade-level simulator: no stops, targets or intrabar handling |
| **Test framework** | Destructive future overwrite, independent naive recompute, mutants, segment guard, one-shot discipline | — | — | Reusable for any new module |

**CryptoRadar engine v24.65 signals** exist, but they are **local_only** and not to be used in this public lab. They are out of scope unless separately approved.

---

## 2. What can and cannot be measured

### Measurable directly from the hourly or 1-minute OHLCV we already have

- **Sideways ranges:**
  - the range high and low over a fixed look-back;
  - the range width relative to price or to ATR;
  - the number of touches near the range bounds.
- **Range contraction after a decline:**
  - ATR or realised volatility now against earlier;
  - the prior drawdown before the range.
- **Volume behaviour inside the range:**
  - relative volume (RVOL) against its own past;
  - volume on up-candles against down-candles, which is a **proxy** for pressure, not true aggressor flow.
- **Close location value:** where a candle closes inside its high–low range.
- **Relative strength against BTC:** the return difference, plus the beta/correlation already in FD-1.
- **Breakout:**
  - a close above the range high;
  - a follow-through measured over the next k bars;
  - a retest (a return to the old high that holds);
  - a **false breakout** (back inside the range within k bars).
- **Distance to the next resistance:** prior swing highs from past bars only.
- **Liquidity and tradability:** traded minutes, dollar volume, spread estimate, delisting events.

### Not provable from OHLCV alone

- **Who** is buying (institutional or retail) and the **intent** of buyers.
- **True buying pressure** (aggressor imbalance). It needs **trades with taker side**. That data exists in the OKX archive (module 1), but it is not in the lab.
- **Absorption of supply, sell walls, spoofing, depth.** These need **order-book history**, and its availability is unknown (not probed).
- **"Accumulation" as a fact.** OHLCV can only show **footprints consistent with** accumulation: a quiet range, contraction, volume rising without price falling. **High volume alone does not prove accumulation or institutional buying.**

---

## 3. Concept → measurable proxy map

| Concept | Measurable proxy | Data | Status |
|---|---|---|---|
| Sideways range | (max high − min low) over L days / price; touches of the bounds | hourly | **new** (simple) |
| Contraction after a decline | vol_7 / vol_30 (F08), ATR ratio; prior 30-day drawdown (F21 dist_low, F20 dist_high) | hourly | **exists** (F06–F08, F20, F21) plus ATR (new) |
| Lower selling pressure | down-candle volume share falling; fewer large down-candles | hourly | **new** (proxy) |
| Price defending a level | repeated lows within x% of the range low, without closes below it | hourly | **new** |
| Relative volume | volume over the last k days / the median over the prior 30 days (F17 is a version) | hourly | **exists** (F17) / small variant |
| Price up with volume up | k-day return > 0 **and** RVOL > its past | hourly | **new** (composition) |
| Close strength | CLV = (close − low)/(high − low), averaged | hourly | **new** |
| Strength against BTC | return − BTC return; beta / corr (F12–F13) | hourly | **exists** |
| Sustained demand, not a single candle | the count of positive-CLV, high-RVOL bars over k days | hourly | **new** |
| **True aggressor buying** | taker-buy volume share, trade count, large-trade share | **trades (module 1)** | **gap**: data not in the lab |
| Breakout / close above resistance | close > the range high (from past bars only), at bar close | hourly | **new** |
| Follow-through | return and max adverse excursion over the next k bars | hourly | **new** |
| Retest | a low within x% of the old range high after the breakout, then a close above | hourly | **new** |
| False breakout | a close back inside the range within k bars | hourly | **new** |
| Room to the next resistance | the distance to the nearest prior swing high above price | hourly | **new** |
| Entry / SL / TP / trailing / time exit / R:R / sizing / costs | an event-driven trade engine | hourly + **1-min** to settle intrabar SL/TP | **gap**: a new trade-level simulator is needed; the cost model and caps are reusable |

---

## 4. Reusable parts of the earlier work

- **Data and pipeline:**
  - the hourly datasets (active + delisted + Jan-2024 addendum);
  - the Development and Validation packs;
  - the delisting ledger and the forced exits;
  - the eligibility universes;
  - all hashing and manifests.
- **Protocol machinery:**
  - the segment guard (Holdout sealed);
  - the entry and horizon rules (H2/H3);
  - one-shot runs;
  - decision records.
- **Features:**
  - volatility and contraction (F06–F09);
  - distance to the 30-day high and low (F20, F21);
  - the volume ratio (F17);
  - traded-minutes share (F19);
  - BTC beta and correlation (F12, F13);
  - Amihud (F18).
- **Cost model:**
  - the fee 0.10% per side (a conservative taker assumption);
  - the Corwin–Schultz half-spread;
  - the 1% DV30 cap;
  - forced exits at delisting.
- **Tests:**
  - destructive future overwrite;
  - naive recompute;
  - mutant runner;
  - synthetic decision tables.

### What the earlier results do NOT support

- **FD-2 and Validation ICs** are cross-sectional rank associations over 1, 7 and 30 days at 00:00. **They are not entry signals and not profit.**
- **The volatility effect** was largely **stablecoins, gold and majors falling less** (A_N10 attribution). It says nothing about breakouts.
- **Short-term reversal did not replicate.** F01 and F03 at 7 days reversed. This is a caution for any "buy strength after a short move" logic, but not a verdict on breakouts, which were never tested.
- **F17 (relative volume) had a small |IC| (~0.02–0.03).** Relative volume **alone** carried little rank information.
- **A_N10's Validation PASS** was relative to B1 in a falling market. Cash beat it.

---

## 5. Real gaps

1. **A trade-level, event-driven simulator.** It must handle signals at bar close, entries at the next bar, stops, targets, trailing stops, time exits, overlapping trades, capital lock, position sizing and costs.
   - **Intrabar ambiguity:** when the stop and the target are both inside one hourly bar, the order is unknown. This needs **1-minute data** (we have it) or a fixed **worst-case rule** (stop first).
2. **Breakout execution costs.** Momentum entries pay more than the average spread. The Corwin–Schultz half-spread is an average estimate, so a **slippage add-on for breakout entries** must be fixed ex-ante, with sensitivity runs.
3. **Crypto-only universe.** Stablecoins, gold tokens and staking or wrapped tokens must be excluded **before** any computation. The ticker list is already defined: USDC, PYUSD, USDG, USD1, EURT; XAUT, PAXG; STETH, BETH, JITOSOL. USTC stays as "other".
4. **True buying pressure** needs trades with taker side (OKX module 1).
   - **This is not needed for the first test.** Collect it only if the OHLCV-only version shows a real, cost-surviving edge, and then as a **small pilot** first. Volume is large for the majors.
5. **Order-book data** is not available and not probed. Concepts that need it stay **unmeasured**, and they are labelled as such.
6. **Clean out-of-sample data for this direction:**
   - **Validation has already been used twice** (the FD-2 replication and the A_N10 check), and this direction is being designed with knowledge of those results.
   - The data not yet seen by any design decision is **Forward Shadow** (from 2026-11-01, paper only) and the **Final Holdout** (2026-04-08 → 2026-10-31). The Holdout is sealed and needs Protocol v1.3 with an external signature.

---

## 6. Minimal practical plan (each phase ends at a review gate; nothing starts without approval)

| Phase | Content | Data | Output |
|---|---|---|---|
| **P0: specification** (document only) | Exact, small definitions: one range, one contraction, one breakout, one confirmation rule, 2–3 exit templates (stop at the range low; target at the next resistance or a fixed R multiple; time exit), and one sizing rule. Plus the slippage add-on, the crypto-only universe, the metrics and baselines (cash, BTC, equal-weight crypto), and the data roles. **Hashed before any computation** | none | Strategy spec v0.1 for review |
| **P1: event study + trade simulator** | Build the event-driven simulator and its tests first, before any result. Then, **on Development only**, list the breakout events and run the **pre-registered** exit templates. Report net expectancy per trade, profit factor, win rate with average win and loss, max drawdown, capital lock and turnover, all against cash, BTC and equal-weight crypto, by market phase | hourly + 1 min (intrabar) | Go/no-go: does any template show a **positive net expectancy after costs** on Development? |
| **P2: trades pilot** (optional, only if P1 says "go") | Add true taker-buy share on a **small** pre-registered pilot set, then test whether it improves P1 | OKX module 1 (new download, approved first) | Keep or drop the order-flow filter |
| **P3: unseen test** | Freeze one system. Then run Forward Shadow paper tracking for a pre-registered period, **or** the Holdout through its own opening procedure (v1.3 + an external signature) | unseen | The first evidence that counts |

---

## 7. Methodological risks to prevent

- **Look-ahead in level definitions.** Ranges and resistances must use **past bars only**. A breakout can only be known **at the bar's close**, so entry happens at the **next** bar.
- **Intrabar optimism.** Never assume a target was hit before a stop inside the same bar. Use 1-minute data or a stop-first rule.
- **Seen-period contamination.** Validation is no longer clean for this direction. Development is for design. Only Forward Shadow and the Holdout (when lawfully opened) are evidence.
- **Data snooping.** Keep few definitions and small pre-registered grids, and log every variant tried. No "dozens of indicators". Multiple-testing control is needed if variants compete.
- **Survivorship.** Delisted pairs and forced exits stay in. Breakout systems are especially exposed to coins that pump and are then delisted.
- **Stablecoins and pegged assets** are excluded **ex-ante** (the A_N10 lesson).
- **Market-phase dependence.** Development was mostly an altcoin-lagging phase and Validation a falling market. Results are reported by phase, and the system must beat **cash and BTC**, not just equal-weight altcoins.
- **Costs at breakouts.** Spread and slippage are higher exactly when momentum entries happen. A slippage add-on and sensitivity runs are mandatory.
- **Capital lock and overlap.** Many simultaneous breakouts compete for capital, so the simulator must enforce cash and position limits.
- **Small samples.** Breakout events per coin are rare. Report event counts, and do not draw conclusions from a few hundred trades without a confidence interval.

---

## Answers to the 10 questions

1. **Available data:** 1-hour OHLCV, built from 1-minute OKX candles, for 466 active and 149 delisted USDT pairs, 2024-01 → 2026-10. Also daily eligibility and liquidity, delisting forced exits, and the 1-minute raw archives.
2. **Sufficient for accumulation and momentum?** **Yes, for price-and-volume footprints**: range, contraction, relative volume, breakout, follow-through, retest, false breakout. **No, for proof** of accumulation or buyer identity.
3. **Directly measurable:** everything marked "hourly" in §3.
4. **Needs more data:** true aggressor buying (trades with taker side, available from OKX module 1) and supply or absorption at levels (order book, not available).
5. **Reusable features:** F06–F09, F12, F13, F17–F21, the eligibility universe and the cost model.
6. **New, and only these:** range high/low/width, ATR contraction, close location value, up/down-volume share, a breakout/retest/false-breakout state, distance to the next resistance, and the trade engine.
7. **Look-ahead risks:**
   - the range defined with future bars;
   - acting before the bar closes;
   - using a day's high before that day ends;
   - intrabar SL/TP ordering;
   - eligibility is known at 00:00 only, so it must be used with that timing;
   - the OKX UTC+8 day boundaries are already handled.
8. **A complete trade:** a coin in a crypto-only, eligible universe forms a past-defined range after contraction. Volume and close strength rise inside it. A close above the range high is the trigger. The entry is the next bar's open plus costs. The stop goes below the range or a structural level. The target is the next resistance or an R multiple, with a time exit. The exit price includes costs, and every trade is logged.
9. **Avoiding seen-period selection:** pre-register the definitions and the grids, use Development for design only, and treat Validation as seen. The final evidence comes only from Forward Shadow or a lawfully opened Holdout. Every variant tried is logged.
10. **Smallest scope to a first realistic trading test:**
    - P0, the specification;
    - then P1, the trade simulator with its tests, and an event study on Development with 1–2 breakout definitions × 2–3 exit templates, costs included, judged against cash, BTC and equal-weight crypto.
