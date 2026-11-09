# Threshold derivation plan v0.3.2: entry + market-state thresholds, one run (DRAFT for review; NOTHING computed)

**v0.3.2 = v0.3.1 + one count correction** (v0.3.1 sha256 `0e3b6024…8708`): the derived values are **8**, not 9 (E2, E3, E4, E5, R1, R2, R3, R4). No statistic, population or order changed, and no threshold was added.

**v0.3.1 = v0.3 + two clarifications required by the reviewer** (v0.3 sha256 `2c816497…d8e8d`): candidate bars ≠ completed trades (§5), and what R3 actually keeps (§3). Nothing else changed.

**Changes from v0.2** (sha256 `c211f466…096b`, approved in principle with 3 required amendments):
- **(a)** Sample sizes are reported at every stage, and the derived values are never changed to reach 100 trades (§5).
- **(b)** The High-Vol day set for R4 is explicitly point-in-time, and the stop distances are taken before any stop limit (§3, R4).
- **(c)** RD4 also runs in an **isolated environment** without any outcome files (§6).

**The 7 statistics are approved as written:** E2 P25, E3 P75, E4 median, E5 P90, R1/R2 P67/P33, R3 P90, R4 median.

**Changes from v0.1** (sha256 `712553fb…84dc`), all at the reviewer's request:
1. **The 5 entry thresholds are added.**
2. **Every threshold has ONE statistic fixed now.**
3. **No circularity:** every reference sample is defined **without** the threshold being derived, and without any other derived threshold.
4. **A test proves that outcome files cannot affect the result.**

**Status:** nothing has been computed, and P1 is not approved. Spec v0.1.3 (sha256 `46a2b1de…a441a`) stays the base.

## 1. Hard rules (unchanged from v0.1)

- **Inputs:** the Development pack only (bars closing ≤ 2025-09-01; universe days < 2025-09-01), the frozen FD-1 feature code, and the crypto-only universe.
- **No forward return or outcome of any kind.** The module may not import `fd2`, `val`, `strategy`, `strategy_attrib` or any simulator.
- **One run.** The output `thresholds.json` is committed with sha256 **before** any P1 code runs.
- Constants fitted on full Development and later applied point-in-time are allowed (T4: Development is for design). This is stated openly.

## 2. Reference populations (defined with NO derived threshold)

| Population | Definition |
|---|---|
| **H**: all hours | Every hourly bar t on Development for a coin that is crypto-only and P1-eligible on t's day, and whose prior 168 bars hold ≥ 84 traded bars (50%, the FD-1 rule) |
| **BO**: breakout bars | The bars of H with **close_t > R_high**, where R_high is the max high of the prior 168 bars. The breakout itself is structural (a close above the range), so it has **no tunable constant**. Each indicator is computed on BO **before any filter** |
| **D**: Development days | The days with the EW index defined (≥ 20 coins; R6e) |

## 3. The thresholds: one fixed statistic each

| # | Threshold (Spec ref) | Current value | Statistic, fixed now | Population | Meaning of the choice |
|---|---|---|---|---|---|
| **E1** | A1, tight range (§5.1) | 25th percentile of the coin's own prior 180-day widths | **Unchanged: it is already data-derived per coin.** The rule *is* "the lower quartile of the coin's own history". Deriving a level for a percentile rank from that same rank's distribution would be circular (it is uniform by construction) | — | "tighter than 3 out of 4 of its own past weeks" |
| **E2** | A2, below the prior peak (§5.1) | 0.80 | **The 25th percentile** of R_high / (the max high of the 90 days before the window) | H | "a range sitting clearly below the recent peak": the lower quartile of the market's usual distance from the peak |
| **E3** | M, relative volume (§5.4) | 2× | **The 75th percentile of RVOL** | BO | "the strongest quarter of breakouts by volume" |
| **E4** | M, close strength (§5.4) | 0.70 | **The median CLV** | BO | "a stronger close than the typical breakout". The median is used, not the 75th, because E3 already keeps only the top quarter, and two top-quarter filters would shrink the sample sharply (the 100-trade minimum, U7) |
| **E5** | Maximum stop distance (§6) | 15% | **The 90th percentile of (close_t − R_low)/close_t, computed BEFORE any stop limit** (reviewer point 2) | BO | "skip only the widest tenth of breakouts", the outliers |
| **R1/R2** | Trend Bull / Bear (§10) | ±5% over 20 days | **The 67th and 33rd percentiles of the 20-day EW-index return** | D | the tertiles of the market's own 20-day moves |
| **R3** | Bear, stricter volume (§10) | 3× | **The 90th percentile of RVOL** | **BO (the same population as E3; it does not depend on E3's value)** | "about the strongest tenth of breakouts". The value is ≥ E3's value by construction. **With tied values, the share of bars it keeps may not be exactly 10%.** The actual share is reported and never described as exactly 10%. **This removes the circularity** of v0.1, which sampled only bars that had already passed RVOL ≥ 2 (reviewer point 1) |
| **R4** | High volatility, maximum stop distance (§10) | 8% | **The median stop distance (close_t − R_low)/close_t**, taken **before any stop limit** (neither E5 nor R4 is applied to the sample) | **BO bars on High-Vol days.** "High-Vol on day d" is the band **known at d 00:00**: the percentile of the EW index's 30-day volatility (days d-30 … d-1) among the values of **all earlier days only** (expanding, ≥ 60 prior values), > ⅔. It is **never** recomputed with later data. A test checks it (RD8) | "in high volatility, only setups no wider than the typical high-vol breakout" |
| — | Volatility bands | ⅓ / ⅔ of the expanding prior percentile | **No constant** (the MI M2 rule, already approved) | — | — |

**Computation order:** E2, E3, E4, E5 and R3 (all independent), then R1/R2, then the High-Vol day set, then R4. **No step uses a value derived in a later step.**

## 4. What stays a design or policy rule (stated, not derived)

| Rule | Value | Why |
|---|---|---|
| Window lengths | 7-day range, 180-day history, 90-day peak, 20 / 50 / 30-day state windows, 24-hour strength over BTC | A distribution chooses thresholds, not horizons |
| Contraction (C) | 7-day vol < 30-day vol | A ratio below 1 is a structural definition, not a tuned level |
| Transition window | 5 days | The run-length distribution is reported for information only (§5) |
| Policy | X3 +2% net, 2R / 3R targets, 7-day time exit, A2 risk 1% (0.5% in High Vol), 20-coin minimum | Trading-policy choices, kept as decided earlier |

## 5. Output (no performance number of any kind)

**Sample sizes (amendment a).**
- The report gives the size of every population: H, BO, BO on Bear days, BO on High-Vol days, D.
- It also gives **the number of BO bars that remain after each entry condition is applied in turn**: A1, A2/E2, C, E3, E4, the BTC strength rule, E5, the state actions.
- These are **counts of candidate bars, not trades and not returns.**
- **Candidate bars and completed trades are different units:**
  - A count of candidate bars is a **count of candidate opportunities**, not of trades.
    - **Fewer than 100 candidate bars** is recorded as a **warning** about opportunity volume. It is **not** declared INCONCLUSIVE on that basis alone.
    - **More than 100 candidate bars** does **not** guarantee 100 completed trades either. Capital, one-position-per-coin, NOT_EXECUTED and SKIPPED cases all reduce the number.
  - **U7 (≥ 100) applies only to completed trades in the P1 simulation.** If P1 completes fewer than 100 trades, the result is INCONCLUSIVE and P1 stops.
- **In every case, the derived values are never changed to reach any count.**


`thresholds.json`, holding:
- the **8** derived values (E2, E3, E4, E5, R1, R2, R3, R4);
- for each: the population size, the deciles, and the share of the population each threshold keeps;
- the trend-run-length distribution (information only);
- the input and code hashes.

## 6. Acceptance tests (written before the run)

| Test | What it checks |
|---|---|
| RD1 Isolation | No input candle closes after 2025-09-01, and no universe day ≥ 2025-09-01 |
| RD2 No outcome code | A static scan and a runtime `sys.modules` check: none of the forbidden modules is imported |
| RD3 Point-in-time indicators | Destructive overwrite of every bar at or after t, for sampled bars, leaves their RVOL, CLV, R_high/R_low, stop distance, peak ratio and index return unchanged |
| **RD4 Outcomes cannot matter** (amendment c) | Two runs must produce the same `thresholds.json` byte-for-byte. **(1) Corrupted copy:** every earlier outcome file (FD-2, Validation, strategy, attribution) is overwritten with garbage. **(2) Isolated environment:** a fresh directory holding **only** the derivation module, the frozen FD-1 feature code, the segment guard, the Development pack, the feature catalogue and the exclusion list. **No `out/feature_discovery/fd2_*`, `out/validation/`, `out/strategy/`, attribution file or repo history is present.** The interpreter runs with `-I` and with network access disabled for the process |
| RD8 Point-in-time High-Vol | The High-Vol flag of every day d equals an independent recomputation that uses only days < d. Corrupting every day ≥ d leaves the flag of d unchanged |
| RD5 Independent recompute | Each population and each percentile is recomputed by a separate naive implementation |
| RD6 No circularity | E3, E5 and R3 are computed on BO with no entry filter. The test shows that changing the current constants (2×, 15%, 3×, 0.80, 0.70) leaves every derived value unchanged |
| RD7 Mutants (≥ 9), all killed (one more: the High-Vol flag computed from the full-period distribution) | Planted defects: a Validation bar in the input; a filter applied before E5; RVOL ≥ 2 applied before R3; percentile levels swapped; a window that includes bar t; excluded coins kept; an outcome module imported; deciles taken from the wrong population |

## 7. Decision requested

Approve v0.3.2: the populations (§2), the 8 derived values with their fixed statistics (§3), the stated conventions (§4) and the tests (§6). **Order after approval:**
1. Code and tests are written, committed and **sent for review**.
2. After that review: the **one** run.
3. `thresholds.json` is frozen with its sha256.
4. The results are reviewed.
5. A **separate** decision is taken on P1.

**No P1 work starts before that.** No new indicators or percentiles are added (reviewer).
