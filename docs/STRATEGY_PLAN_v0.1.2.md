# Strategy Plan v0.1.2: long-only spot portfolio from the replicated clusters (APPROVED with clarifications 2026-11-09; NOTHING executed)

**Status:**
- **Approved** by the reviewer on 2026-11-09, with the 5 clarifications in §0.1.
- **v0.1.2:** the S5 fee is documented (§0.2). Nothing else changed from v0.1.1.
- **No simulation, backtest, portfolio return, cost or P&L has been computed.**
- Protocol v1.2 FIXED. FD-1, FD-2 and Validation v0.16 are accepted (`VAL_REVIEW_RECORD.md`, commit `7b646d7`). The Final Holdout stays sealed (H7).
- **The CryptoRadar engine v24.65, Router A/B, the forward counters and validate.py are not touched.** No order is ever sent. The lab holds no exchange keys.

**Question:** does a simple, **spot, long-only** portfolio built only from the clusters that replicated beat a fair baseline **after realistic costs**?

## 0. Decisions requested from the reviewer

| # | Question | Proposal |
|---|---|---|
| S1 | **Signals** (direction fixed from FD-2; only replicated clusters) | **A** = volatility only: rank of **F07 vol_30**, low is better.<br>**B** = the equal-weight mean of the direction-adjusted cross-sectional ranks of F07 (−), F10 skew_30 (−), F20 dist_high_30 (+) and F21 dist_low_30 (−).<br>F13 corr_btc_30 is **left out**, because it weakened in Validation (review record). Liquidity, F08 and F17 are left out because their effect was small (\|IC\| ≈ 0.02–0.06).<br>**Why F07, not F06** (the Q5 representative): its 7-day rank persistence is 0.934 against 0.693 (FD-1 Q3), so it turns over less and costs less. That is a data reason, not a result-driven choice |
| S2 | **Portfolio** | Long the **top N** of the P1-eligible coins by signal, equal weight, **rebalanced every 7 days** at 00:00 UTC. The 7 days match the h = 7 replication and keep turnover low. N ∈ {10, 20}. The median eligible universe is 239 coins (MI), so 10 is about the top 4% and 20 about the top 8%. **Spot only. No short, no leverage.** |
| S3 | **Development grid and selection** | 2 signals × 2 N = **4 variants, all reported**. The variant with the highest Development **mean weekly net excess return over B1** is selected, by a rule fixed now. Development is the protocol's segment for strategy generation (T4) |
| S4 | **Validation check** | **One** run of the **selected variant only**. Validation is "selection and checks only" (T4). **It is the second use of Validation; the first was the IC replication.** This is stated, not hidden |
| S5 | **Fee level** | **No number is assumed here.** The OKX spot fee for the account's actual tier must be **documented** (an OKX fee page or the account's fee screen) before any run. The run uses that fee, with a **2× fee sensitivity** |
| S6 | **Acceptance gate (Validation)** | **PASS** only if the mean weekly **net** excess return over **B1** is > 0 with a **one-sided p ≤ 0.05**. The p comes from Newey-West with lag 0 for non-overlapping weeks, confirmed by a block bootstrap. It must hold at the documented fee **and** stay > 0 at the 2× fee.<br>The absolute net return, and the comparisons with **B2 (BTC)** and **B3 (cash)**, are **always reported**. If the strategy beats B1 but **loses money in absolute terms**, it is flagged `RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE` |
| S7 | **Capacity** | Reported at capital levels of $1k, $10k and $100k. A position may not exceed **1% of the coin's DV30_med**. The excess stays in cash and is reported. **1% is a convention**, to be accepted or changed by the reviewer **before** the run |
| S8 | **After a PASS** | **No live trading.** The next step is a separate, approved plan for **Forward Shadow paper tracking** (from 2026-11-01: counters only). It would run in the lab, not in the CryptoRadar counters. Opening the Holdout would need Protocol v1.3 with an external signature, and it is not proposed |

## 0.1 Reviewer clarifications (binding)

1. **S3 tie-break.** The variant with the highest Development mean weekly net excess return over B1 is selected.
   - Tie → the **lower average turnover**.
   - Still tied → **Top 10**.
   - Validation is never used to select.
2. **S4 status of Validation.**
   - Validation was already used to replicate the features, and those replicated features now design the strategy.
   - A Validation run of the selected variant is therefore **a performance and screening check, NOT an independent proof**. Its success is never described as independent evidence.
   - The final test not affected by this selection remains the **Final Holdout**: after the strategy is frozen, and only once its opening conditions are met (Protocol v1.3 with an external signature, H7). **Nothing here opens it.**
3. **S6 decision rule, bootstrap included.**
   - Both statistics are computed on the series of non-overlapping weekly net excess returns over B1:
     - a **Newey-West** t with lag 0, giving a one-sided p;
     - a **circular block bootstrap** with a block of max(7, h) = 7 days = 1 week, 2,000 resamples and seed 20260108, giving a one-sided p = the share of resampled means ≤ 0.
   - Both are reported with their values and the 95% CI.
   - **PASS requires both one-sided p ≤ 0.05**, at the documented fee, **and** a mean > 0 at 2× the fee.
   - The `RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE` flag rule is unchanged.
4. **S7 capacity applies to the baselines too.**
   - B1 uses the same 1% cap of DV30_med per coin and the same fee, spread and turnover cost model as the strategy.
   - B2 (BTC) also uses the cap and the costs.
5. **Prices and the spread estimator.**
   - `close_asof(d)` is a **reference proxy** for historical execution: the last traded close before the decision time. It is **not** an actual executable price at the rebalance.
   - The **Corwin–Schultz** half-spread is frozen exactly as follows, and tested (SA4) before any computation:
     - For each pair of **consecutive traded hours** (t, t+1h), both inside days d-30 … d-1:
       - β = ln(H_t/L_t)² + ln(H_{t+1}/L_{t+1})²
       - γ = ln(max(H_t, H_{t+1}) / min(L_t, L_{t+1}))²
       - α = (√(2β) − √β)/(3 − 2√2) − √(γ/(3 − 2√2))
       - S = 2(e^α − 1)/(1 + e^α)
     - The coin's spread is the **median S over pairs, clipped at 0**. It needs ≥ 360 pairs, the same 50% rule as vol_30; otherwise the coin is not bought.
     - **Half-spread = spread / 2.**

## 0.2 S5: documented fee (added in v0.1.2)

**Evidence:** the user's own OKX account trade history (an app screenshot, kept privately and NOT committed, because the public repo must never hold real trades or balances).
- It shows **8 spot fills** that all belong to one order and carry the same timestamp, so they are **taker** fills.
- For **every** fill, fee / filled amount = **0.10000%**, computed fill by fill.
- A separate app screen shows the account is **not VIP** (a regular account).

**Fixed for the run:**

| Item | Value |
|---|---|
| **Fee per side** | **0.10%**, taker. Every rebalance trade is treated as taker. This is conservative, because no maker fill is assumed. The maker rate is not documented and **is not used** |
| **2× sensitivity** | **0.20%** per side |

This applies equally to the strategy, B1 and B2 (§0.1.4).

## 1. Execution model (point-in-time; the same conventions as FD/Validation)

- **Decision time:** a rebalance day d at 00:00 UTC. The signal uses features known at d (frozen FD code), over the coins **eligible on d** in P1.
- **Prices:**
  - A trade at d uses `close_asof(d)`, the last traded close before d, as a **reference proxy** (§0.1.5).
  - **Buy price** = reference × (1 + fee + half-spread). **Sell price** = reference × (1 − fee − half-spread).
  - Each holding period ends at the next rebalance, d + 7.
- **Half-spread, estimated from data:** the Corwin–Schultz high-low estimator. It is computed on the coin's hourly high/low over days d-30 … d-1 (closed by d), takes the median of the hourly-pair estimates, and is clipped at 0.
  - If it cannot be estimated, the coin is **not bought**.
  - The estimator and its parameters are frozen in code before the run.
- **Delisting during a hold:** U9b forced exit at the last traded price before the cut. That cash stays idle until the next rebalance. `UNPRICEABLE` cases are reported separately (U9c).
- **Liquidity exit (U9a):** a held coin that becomes ineligible may be kept until the next rebalance. It is never newly bought.
- **Turnover:** only the difference between the old and new weights is traded, and only that difference pays costs.
- **Entry cut (H2):** every 7-day holding period must start before the segment's entry cut and end inside the segment.
  - Development: holding periods start in [first complete-feature day, 2025-08-02).
  - Validation: holding periods start in [2025-09-08, 2026-03-02).
  - **H3 purge = 0.**

## 2. Baselines (same dates, same rebalance, same costs)

| Baseline | Definition |
|---|---|
| **B1** | Equal weight over **all** P1-eligible coins, rebalanced every 7 days with the same cost model. The selection value is measured against this |
| **B2** | BTC-USDT buy and hold. Fee and half-spread are paid once on entry and once on exit |
| **B3** | Cash: 0% |

## 3. Reported metrics (all variants, both segments, P1; S50k and S250k descriptive)

- Net and gross total return, annualised.
- Mean weekly net excess return over B1, with Newey-West and block-bootstrap CIs.
- Weekly hit rate against B1.
- Volatility, Sharpe (weekly, annualised), maximum drawdown.
- Turnover, cost drag (fees and spread separately), forced and liquidity exits, cash idle share.
- Capacity at $1k, $10k and $100k.

## 4. One shot, no tuning

1. The code, the tests and the mutants are committed and passing **before** any return is computed.
2. Development runs once and selects one variant by S3.
3. **The selected variant is frozen and hashed.**
4. Validation then runs **once**.

After Validation, nothing changes: no new variant, no new parameter, no different N, no fee change, and no retry. A FAIL ends this plan.

## 5. Acceptance tests (written before results)

| Test | What it proves |
|---|---|
| SA1 | **Isolation and guard:** decision times inside the segment, holding periods inside the entry window, H3 = 0, Holdout sealed |
| SA2 | **Destructive future overwrite:** the weights at d are unchanged after corrupting every candle at or after d |
| SA3 | **Independent naive recompute** of the weights, trades, costs and weekly portfolio return for sampled weeks, including delistings and the 1% cap |
| SA4 | **Costs:** the Corwin–Schultz value is checked against an independent implementation. The fee comes from the documented value. No cost is negative |
| SA5 | **Baselines** recomputed independently |
| SA6 | **Selection rule and gate** on a synthetic table, including the `RELATIVE_ONLY` flag |
| SA7 | **Mutants (≥ 12), all killed.** Planted defects: same-day price; buying ineligible coins; costs skipped on turnover; spread from a future window; delisted dropped; forced exit at a later price; selection on Validation; gate two-sided; B1 without costs; the cap ignored; overlapping weeks without correction; the Holdout read |
| SA8 | Reviewer fast mode and a mini package |

## 6. Not in scope

- Short selling, leverage, derivatives and live orders.
- Any change to CryptoRadar, Protocol v1.2, the FD/Validation code or the 41-hypothesis family.
- Regime filters (MI is Development-only, and there are no labels on Validation).
- The Final Holdout.
