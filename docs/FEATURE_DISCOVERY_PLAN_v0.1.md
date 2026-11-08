# Feature Discovery Plan v0.1 — Development only (for review; NOTHING executed)

**Status:** draft for review. No feature has been computed. No code for this phase exists yet.

**Governance:** Protocol v1.2 FIXED (sha256 `18d5ddcf…d969`, tag `protocol-v1.2`). MI v0.11.2 is approved (commit `cef23c7`).

**Data:**
- Development only: days 2024-01-01 → 2025-08-31.
- Inputs come only from the Development pack `dev_pack_v1` (hourly OHLCV + traded_minutes; P1/S50k/S250k eligibility), plus the MI v0.11.2 outputs (`regimes_asof_*`).
- No Validation, no embargo days as decision days, no Final Holdout. The December 2023 warm-up is not used (T3).

**Goal:** define, before seeing any result, *which* coin-level characteristics we study, *how* each is measured, and *what* is forbidden. This phase finds and describes features. It builds **no strategy**, computes **no trade, P&L, cost or portfolio return**, and selects nothing for use.

## 0. Decisions requested from the reviewer

| # | Question | Proposal |
|---|---|---|
| D1 | Does this phase include any forward outcome? | **Two parts.** Part 1 (FD-1) uses **no forward outcome**. Part 2 (FD-2, forward association) is **fully pre-registered here** but runs **only after FD-1 is reviewed and FD-2 is separately approved**. Option: drop FD-2 from this phase entirely |
| D2 | Conventional thresholds fixed before any result (they cannot come from data that has not been looked at yet) | Redundancy \|ρ\| ≥ 0.80, with sensitivity at 0.70 and 0.90. Benjamini–Hochberg q = 0.10. Minimum 20 series per day (as in R6e). A state with fewer than 30 labelled days is flagged `LOW_N` |
| D3 | FD-2 horizons | h ∈ {1, 7, 30} days (all ≤ H_max = 30) |

## 1. Point-in-time convention (same as MI, T5/H5)

- A feature for series s on UTC day d is known at **d 00:00**.
- It uses only candles **closed at or before d 00:00**, and never anything before 2024-01-01 00:00.
- It is computed only for series **eligible on day d** in the scenario. P1 is primary; S50k and S250k are sensitivity scenarios.
- `close_asof(s,d)` = close of the last traded hour of day d-1, as in MI. No carry-forward. Rule-B hours only (D1).
- A missing input leaves the value missing. There is no imputation.

## 2. Fixed feature catalogue (22 features, parameters frozen here)

Hourly log return `lr` = log close − log previous traded close of the same series. A window "w days" = days d-w … d-1.

| # | Feature | Definition | Minimum data |
|---|---|---|---|
| **Momentum / reversal** | | | |
| F01 | ret_1 | close_asof(d)/close_asof(d-1) − 1 | both closes |
| F02 | ret_7 | k = 7 | both closes |
| F03 | ret_30 | k = 30 | both closes |
| F04 | ret_30_skip7 | close_asof(d-7)/close_asof(d-30) − 1 | both closes |
| F05 | resid_mom_30 | ret_30 − beta_btc_30 · BTC ret_30 | F03, F12 |
| **Volatility / shape** | | | |
| F06 | vol_7 | std of `lr` over 7 days (as MI) | ≥ 50% of hours |
| F07 | vol_30 | same, 30 days | ≥ 50% of hours |
| F08 | vol_ratio_7_30 | vol_7 / vol_30 | F06, F07 |
| F09 | downside_vol_30 | √mean(min(lr, 0)²) over 30 days | ≥ 50% of hours |
| F10 | skew_30 | sample skewness of `lr`, 30 days | ≥ 50% of hours |
| F11 | max_hr_ret_7 | max `lr` over 7 days | ≥ 50% of hours |
| **Market relation** | | | |
| F12 | beta_btc_30 | OLS slope of daily r_1 on BTC r_1, days d-29 … d | ≥ 20 pairs |
| F13 | corr_btc_30 | Pearson correlation of the same pairs (as MI) | ≥ 20 pairs |
| F14 | idio_vol_30 | std of the F12 regression residuals | ≥ 20 pairs |
| **Liquidity / activity** | | | |
| F15 | log_dv30_med | log of `DV30_med` from the universe file of day d (built from days d-30 … d-1) | assessable |
| F16 | thr30 | `THR30` from the universe file of day d | assessable |
| F17 | dv_ratio_7_30 | median daily quote volume, 7 days / same, 30 days | ≥ 4 of 7 and ≥ 15 of 30 traded days |
| F18 | amihud_30 | median over traded days of \|daily log return\| / daily quote volume (USDT) | ≥ 15 traded days |
| F19 | traded_min_share_7 | Σ traded_minutes / (7·1440) | — |
| **Price position / range** | | | |
| F20 | dist_high_30 | close_asof(d) / max hourly `high` over 30 days − 1 | ≥ 50% of hours |
| F21 | dist_low_30 | close_asof(d) / min hourly `low` over 30 days − 1 | ≥ 50% of hours |
| F22 | range_7 | mean daily (max high − min low) / last close, 7 days | ≥ 4 traded days |

**Cross-sectional ranks:** every feature is also used as its percentile rank among the series eligible on day d. All tests below use ranks, so the scale of a feature does not matter.

**Excluded on purpose:**
- **Listing age.** The pack starts at 2024-01-01, so age is left-censored. A correct value needs instrument listing times, which are not a protocol input.
- **Funding, open interest and on-chain data.** These are not protocol inputs; the system is spot only.
- **Anything from CryptoRadar.** Its signals, the top-150 list and the 38 signal coins are local_only.

## 3. FD-1: feature quality, stability and relation to regimes (no forward outcome)

| Measure | Exact computation | Output |
|---|---|---|
| Q1 Coverage | share of eligible series-days with a value, per feature and month | table + count of days with < 20 series |
| Q2 Distribution stability | per month: cross-sectional median and IQR of the raw feature | monthly table. Reported, not gated |
| Q3 Rank persistence | daily Spearman ρ between ranks at d and d+k, k ∈ {1, 7}, over series eligible on both days; d+k < 2025-09-01. *(This uses a later feature value, not an outcome. It stays inside Development.)* | mean, median, IQR across days |
| Q4 Redundancy | daily cross-sectional Spearman ρ for every feature pair. Take the median over days. Clusters are connected components of \|median ρ\| ≥ 0.80 (also 0.70 and 0.90) | 22×22 matrix + clusters |
| Q5 Cluster representative (fixed rule) | highest Q1 coverage; tie → fewer parameters; tie → lower F-number | list |
| Q6 Relation to regimes | daily cross-sectional median of each feature's raw value, grouped by `regime_asof` (P1; as-known labels, from 2024-07-01). The difference between each state's mean and S2's mean (S2 is the largest state) gets a 95% CI from a circular block bootstrap: 7-day blocks, 2,000 resamples, seed 20260108. `UNKNOWN` is reported as its own group | table. S3 has 19 days, so it is marked `LOW_N` |
| Q7 Survivorship | Q1–Q6 recomputed without later-delisted series (as MI M6) | difference table |

**FD-1 makes no selection.** Its output is a description. Clusters (Q4/Q5) only define which features represent each cluster in FD-2. That is fixed by the rule above and decided before FD-2 runs.

## 4. FD-2: forward association (pre-registered; runs only after separate approval)

- **Outcome:**
  - `fwd_h(s,d) = close_asof(s, d+h) / close_asof(s, d) − 1` for h ∈ {1, 7, 30} days.
  - Start t = d 00:00, eligible on d. **t < 2025-08-02** (H2), so t + 30 days ≤ the end of Development.
  - It uses only candles closed in [d, d+h].
  - **Delisting within the horizon:** if the series is cut (D2) before d+h, the outcome uses the U9b forced-exit price from `forced_exit_reference.csv`.
    - Cuts before 2025-09-01 only. These rows are added to a pack `dev_pack_v2` with a manifest.
    - `UNPRICEABLE` cases are counted and excluded, never dropped silently. Delisted coins are **never** removed from outcomes, because that would be survivorship bias.
  - **H3:** the purge count must be 0 (tested).
- **Statistic:** the daily Spearman rank IC between the feature rank at d and the `fwd_h` rank, over eligible series (needs ≥ 20).
  - Per feature × h: mean IC and median IC.
  - A Newey-West t-statistic with lag h−1 days (to allow for overlapping outcomes).
  - A circular block bootstrap with block = max(7, h) days, 2,000 resamples and seed 20260108.
- **Tests:**
  - One family of 22 features × 3 horizons = **66 tests**, two-sided, with Benjamini–Hochberg at q = 0.10.
  - Regime-conditional ICs (`regime_asof`) are **descriptive only**. They are not tested, so the test count does not grow.
- **Stability:** sign of the mean IC in three fixed sub-periods: [2024-01-01, 2024-07-01), [2024-07-01, 2025-01-01), [2025-01-01, 2025-08-02).
- **Candidate label (fixed now):** BH-significant **and** the same sign in **3 of 3** sub-periods **and** the same sign in S50k and S250k.
  - A candidate is only a **hypothesis for later Validation under a future approved protocol step**. It is not a signal, not a strategy and not a decision.
- **Not computed:** quantile or long-short portfolio returns, hit rates of trades, costs, P&L, turnover of a strategy.

## 5. Forbidden

1. Validation and Holdout data, embargo days as decision days, the December 2023 warm-up.
2. Any input outside `dev_pack_v1`/`v2`, the MI v0.11.2 outputs and the forced-exit reference. CryptoRadar data is local_only.
3. Changing any feature, window, threshold or test after seeing FD-2 output.
   - A new idea after FD-2 goes to a separate list labelled **post-hoc / exploratory**, needs a new approved plan, and can never be reported as a discovery from this run.
   - Changes after FD-1 (which has no outcomes) are allowed only through plan v0.2, approved **before** FD-2 runs.
4. Any strategy, entry/exit rule, cost, P&L, or portfolio return.
5. Changing Protocol v1.2, the MI code, the CryptoRadar engine, Router A/B, the forward counters or validate.py.

## 6. Acceptance tests (written before the features are computed)

| Test | What it proves |
|---|---|
| FA1 Destructive future overwrite | Corrupt every candle and eligibility row at or after d for ≥ 4 sample days. Every feature at ≤ d is unchanged (all 22 × 3 scenarios) |
| FA2 Guard | `check_feature` for every value (t inside Development, lookback closed by t, ≥ RESEARCH_START); `check_research_statistic` for every output day |
| FA3 Independent recompute | A separate naive per-row implementation of all 22 features on 300 random series-days. Values must match to 1e-9 relative |
| FA4 Outcome boundary (FD-2) | Every outcome interval lies inside Development, t < 2025-08-02, purge count 0, forced exits used exactly where a cut falls inside the horizon |
| FA5 Mutants (≥ 12) | Must be killed: same-day close; window includes d; eligibility of d+1; full-period ranks; d+k persistence reaching past Development; IC without overlap correction; BH replaced by raw p; delisted removed from outcomes; forced exit at a later price; outcome crossing Development end; regime labels relabelled with the final model; a feature parameter changed after the catalogue |
| FA6 Reproduction | A standalone `repro/` with the pack, code and tests, a byte-identical rerun, sha256 for every file. Runtime and memory are stated, and there is a **fast test mode** (FA1 on 4 days, FA3 on 300 rows) so a reviewer can finish within a few minutes |

## 7. Deliverables

- **FD-1:**
  - `feature_catalogue.json` (definitions and parameters, hashed before the run);
  - `fd1_coverage.csv`, `fd1_stability_monthly.csv`, `fd1_persistence.csv`, `fd1_redundancy_matrix.csv`, `fd1_clusters.json`, `fd1_regime_relation.csv`, `fd1_survivorship.csv`;
  - the report, test and mutant results, and the repro pack.
- **FD-2 (after approval):** `fd2_ic_daily.parquet`, `fd2_ic_summary.csv` (with BH-adjusted values), `fd2_stability.csv`, `fd2_candidates.csv`, the report and tests.
