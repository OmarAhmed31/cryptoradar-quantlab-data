# CryptoRadar Quant Lab — RESEARCH PROTOCOL v1.2

Status: **SUBMITTED FOR APPROVAL.** It becomes **FIXED** only when the expert approves **this exact sha256**.

**Change from v1.1** (FIXED, sha256 `91718b69…678c`, tag `protocol-v1.1`): **only additions.**
- Rules **T4** (time split), **H1–H7** (horizon, entry cut, purge, embargo, warm-up, isolation, holdout seal) and **R1–R6** (point-in-time regime models) are added. They come from Market Intelligence plan v0.2, as approved on 2026-11-08 with three clarifications.
- §1 paths now point to `v1.2/` copies of the same files, which are byte-identical.
- Every rule of v1.1 is unchanged, word for word.

Rule for this file: it is fixed **before** any strategy research. It must not change while research is running. Any change makes a new version (v1.3, …), which must be:
- written **before** looking at any result that the change could affect;
- hashed and committed;
- approved by the expert.

## 1. Data (inputs; sha256 of every file in `INPUTS_SHA256.txt`)

| Part | Location | Role |
|---|---|---|
| Active Assets Historical Dataset | `out/active_dataset/final_42445808350_retry_42448392394/` (hourly shipped in the v0.9 ZIP; per-file sha256 in `hourly_files_sha256.txt`) | 466 live OKX SPOT USDT pairs, **current listing only** |
| Delisted Assets Historical Dataset | `out/delisted_dataset/20261107T192715Z_rebuild/` (v0.7.1) | 141 pairs delisted with announcements from 2024-01-05 on; USDC-USDT excluded (correction #2) |
| Jan-2024 addendum | `out/delisted_dataset/20261108T041031Z_jan2024_addendum/` | 8 pairs delisted on 5 and 12 Jan 2024. DASH, ZEC and ZEN = **old listing only** (`#old_listing`) |
| Warm-up | `out/warmup_dec2023/run_42455759208/` | **December 2023, for liquidity eligibility only** (`WARMUP_ONLY=1`) |
| Liquidity table | `out/liquidity_profile/20261108_v0.10.1/daily_liquidity_point_in_time.csv.gz` | Point-in-time metrics per series per day |
| **Universe files (authoritative)** | `out/research_protocol/v1.2/universe/eligibility_daily_{P1,S50k,S250k}.csv.gz` (byte-identical to v1.0 and v1.1) | `eligible` per series per research day |
| **Forced-exit reference (U9)** | `out/research_protocol/v1.2/forced_exit_reference.csv` (byte-identical to v1.1) (built by `lab/forced_exit_reference.py` from the raw 1m files) | For each delisted series: the cut, the last traded minute before it, its price, the gap, and the status |

## 2. Fixed data rules

- **D1.** Hourly candle = rule B: only minutes with volume > 0. **An hour with no trade does not exist.** It is never filled with a price.
- **D2.** Delisted pairs are cut at the official effective time. A window is cut at its **start** (`cutoff_precision=window_start_conservative`). Nothing at or after the cut is used.
- **D3.** Separate listings of the same ticker are **never** joined: ticker reuse, delist and relist.
- **D4.** All times are UTC. The UTC+8 archive labels are kept only as metadata.
- **D5.** A missing file or missing minute is missing data. It is never treated as a period with no trading.

## 3. Research period

- **T1.** Research start: **2024-01-01 00:00 UTC**, or the pair's actual listing time if that is later.
- **T2.** Research end: **2026-10-31 16:00 UTC** (exclusive), the last complete archive month.
- **T3.** December 2023 is warm-up only. **No December 2023 hour enters any research result, signal or trade.**

- **T4. Time split.** It is chronological and fixed by the calendar alone. Every boundary is a UTC instant, and every range is half-open, [start, end).

  | Segment | Data range | Entry / label-start window | Use |
  |---|---|---|---|
  | Development | [2024-01-01 00:00, 2025-09-01 00:00) | **t < 2025-08-02 00:00** | MI, features, regime models, strategy generation |
  | Embargo 1 | [2025-09-01 00:00, 2025-09-08 00:00) | none | not used |
  | Validation | [2025-09-08 00:00, 2026-04-01 00:00) | 2025-09-08 00:00 ≤ **t < 2026-03-02 00:00** | selection and checks only |
  | Embargo 2 | [2026-04-01 00:00, 2026-04-08 00:00) | none | not used |
  | Final Holdout | [2026-04-08 00:00, 2026-10-31 16:00) (= T2) | 2026-04-08 00:00 ≤ **t < 2026-10-01 16:00** | opened once (H7) |
  | Forward Shadow | from 2026-11-01 00:00 | — | live counters, no trading |

  - **Holdout note.** The holdout entry cut is **2026-10-01 16:00 UTC**, not 2026-10-02 00:00. The research data end (T2) is **2026-10-31 16:00 UTC**, the end of the last complete UTC+8 archive month, and t + 30 days must stay ≤ T2. Development and Validation end at 00:00, so their cuts are exactly segment end − 30 days.
- **T5. Time stamps.** t is the time the entry price or the label start is taken.
  - For hourly data, a decision made with candles up to the close of hour h is taken at t = h + 1 h, and it may only use candles that **closed at or before t**.
  - An outcome over [t, t + h] uses only candles that **start at or after t and end at or before t + h**.

## 4. Universe (point-in-time liquidity eligibility)

- **U1. Window.** For UTC day d, use exactly the **30 calendar days d-30 … d-1**. Day d and anything later are never used.
- **U2. Full day.** A day counts as full only with **1440 listed minutes**. A day containing a listing or a cut is partial.
- **U3. Assessable.** A pair is assessable only with **30 full days** in the window. The window is never shortened, for any pair.
- **U4. P1 (primary).** Eligible on day d if assessable **and THR30 ≥ 0.90 and DV30_med ≥ $100,000**.
  - THR30 = traded hours ÷ listed hours.
  - DV30_med = median daily quote volume in USDT.
- **U5. Daily.** Eligibility is recomputed every day. A pair may enter or leave the universe on any day.
- **U6. Scenarios.** **S50k** (DV30_med ≥ $50,000) and **S250k** (≥ $250,000), both with THR30 ≥ 0.90.
- **U7. The scenarios are independent.** P1, S50k and S250k are **separate eligibility scenarios**, not three chances to pick the best one.
  - Every result is reported under **all three**.
  - P1 is the primary scenario and **cannot be replaced** by a scenario that looks better after results are seen.
- **U8. No strategy data.** The thresholds were set from execution logic and from the liquidity distribution only. They must **never be changed or chosen using strategy results**, signals, returns or backtests.
- **U9. Exits that do not come from the strategy.** These are recorded as separate exit types, never as an ordinary loss or a stop-loss.
  - **U9a. Liquidity exit from the universe** (`LIQUIDITY_INELIGIBLE`). This is not a forced exit: a position opened while the pair was eligible **may be held**, and **no new entry** is allowed while the pair is ineligible.
  - **U9b. Delisting forced exit** (`DELISTING_FORCED_EXIT`). A position still open at the official cut (D2) is closed at the **last actual traded price strictly before the cut**:
    - **Price source:** the `close` of the last 1-minute candle with volume > 0 whose minute ends at or before the cut, i.e. the price of the last trade in that minute. Minute precision.
    - **Never** the close of a candle that contains or passes the cut, never a later price, and never an assumed or ideal price.
    - **Recorded for each such exit:** `last_trade_timestamp_utc` (minute), `last_trade_price`, and `minutes_last_trade_to_cut`.
  - **U9c. Price reliability.** The exit is **PRICED** only if `minutes_last_trade_to_cut ≤ 60`.
    - Otherwise, or if there is no trade before the cut, it is **`UNPRICEABLE_FORCED_EXIT`**.
    - In that case no price is assigned, and the trade is reported **separately**, outside the profit and loss figures, with a count and the capital affected.
    - The limit of 60 minutes was set in code before the table was computed, and it uses no strategy data.
  - **U9d. Relisting.** If a pair is listed again later, it is a **new listing series** (D3). Nothing carries over from the old listing: no position, no eligibility, no history.
  - **U9e. Reporting.** `LIQUIDITY_INELIGIBLE`, `DELISTING_FORCED_EXIT` (priced) and `UNPRICEABLE_FORCED_EXIT` are shown as **separate categories** in the trade logs and in every report.
  - **Reference values** come from `forced_exit_reference.csv` (149 delisted series). All 149 are PRICED: the median gap is 1 minute, the 90th percentile 7 minutes, and the maximum **60 minutes (KCAL-USDT)**, which sits exactly on the limit.

## 4b. Horizon, purging, embargo and segment isolation

- **H1. H_max = 30 days (720 hours) for every forward-looking quantity.** This covers:
  - trade holding periods;
  - forward returns;
  - every label;
  - outcome metrics, including MFE (maximum favourable excursion), MAE (maximum adverse excursion), time-to-target and time-to-stop;
  - any feature-selection or evaluation statistic that uses a future outcome.

  A trade still open after 30 days is closed by a **time exit** (`TIME_EXIT`) at the close of the last traded hour at or before t + 720 h. Nothing looks further ahead than 30 days.
- **H2. Entry cut.** An entry or label start at t is allowed in a segment only inside its entry window (T4). This guarantees **t + H_max ≤ end of segment**, so every outcome ends inside the segment where it started.
  - The cut is fixed by time, independent of how long any trade actually lasts.
  - The full 30 days of outcome data, up to the last complete candle, lie inside the segment.
- **H3. Purge (safety net).** Any observation whose outcome interval is not fully inside one segment is removed from every statistic, label, metric and report. The expected count is **0**, and this is tested.
- **H4. Embargo.** The two 7-day embargoes (T4) hold no observation, label or entry.
  - The minimum separation between the last permitted entry in one segment and the first permitted entry in the next segment is **37 days**: the 30-day outcome horizon is completed inside the originating segment, followed by the 7-day embargo.
  - The last outcome data of a segment therefore precedes the first permitted entry of the next segment by **7 days** (the embargo).
- **H5. Access types.** Every read of data is one of these, and is checked by `lab/segment_loader.py`:

  | Access | Rule |
  |---|---|
  | **Entry / label start** at t | only inside the assigned segment's **entry window** (T4) |
  | **Label / outcome** over [t, t+h] | h ≤ H_max, and every candle used starts ≥ t and ends ≤ t+h ≤ the **end of the assigned segment** (T5) |
  | **Feature lookback** at t | the decision time **t itself must lie inside the assigned segment's data range**: never in an embargo, an earlier segment or a later segment. A Validation guard can therefore never compute a feature at a Holdout or Development date. Lookback = any **research-period** history strictly before t: candles **closed at or before t**, including earlier segments and embargoes (causal warm-up). Never before 2024-01-01 00:00 UTC, because the December 2023 warm-up is forbidden here (T3) |
  | **Future timestamp** (anything not closed by t) | **always refused** |
  | **Final Holdout** | sealed (H7). Every access raises until the logged opening |

- **H6. Segment isolation of research.**
  - Market Intelligence statistics, feature selection, regime-model fitting and every choice of k, a threshold or a parameter are computed **only for days inside Development**.
  - Their inputs follow the feature-lookback rule of H5, so they use only research-period history before the day.
  - **Validation and Final Holdout data never enter them.**
  - Validation and Holdout entries may use earlier history as feature lookback (H5). That is the only way earlier data reaches them.
  - **Test requirement:** `tests/test_segment_loader.py` must show four things:
    - Validation can use Development and embargo history as feature lookback.
    - Validation **cannot** read a future timestamp or Holdout-period data.
    - Market Intelligence on Validation is refused.
    - Every planted mutant of the guard is killed.
- **H7. Final Holdout seal.**
  - Nothing is computed or shown on the Final Holdout before the candidates and their rules are frozen and hashed. That includes descriptive statistics, charts and counts.
  - **Under this protocol version there is no way to open the Final Holdout at all.** `lab/segment_loader.py` refuses every Holdout guard and every call to `open_holdout`, whatever files, records, flags or arguments are passed. A refused attempt writes nothing.
  - A hand-written opening record with **correct** hashes is refused as well, because no code path reads records.
  - **Opening requires Protocol v1.3.** It must define, test and get approval for an **externally verifiable** approval *before* any opening. That means a cryptographic signature that cannot be produced inside the lab, plus a one-time consumption logged in an **external, append-only** place (for example a GitHub-verified commit by the owner's account, executed by a dedicated workflow).
  - **Limit:** whoever can edit the code can remove the seal. Any such edit is visible in the git history and the code hash (§7), and it breaks the approved hash.

## 4c. Regime models (point-in-time)

- **R1. Inputs.** Only past-only Market Intelligence quantities. **Future returns are never used**, either to define a regime or to choose k.
- **R2. Choosing k.**
  - k is chosen from **{3, 4, 5, 6}** by the mean silhouette score. A tie goes to the smaller k.
  - The choice uses **only [2024-01-01, 2024-07-01)**, the first training window. k is then **fixed** for all later refits.
- **R3. As-known labels.**
  - The first model is fitted on [2024-01-01, 2024-07-01) and **labels days from 2024-07-01**. Days before that have no regime (`NO_MODEL`).
  - From then on the model is refit **monthly**, on the 1st at 00:00 UTC, on an expanding window of all Development data before the refit time. It is frozen until the next refit.
  - Each day is labelled once by the model frozen at that time, and stored as `regime_asof`. **The past is never relabelled.**
- **R4. Stability metrics.** For each refit after the first:
  - agreement of the new model with the previous one on the previous training window, after alignment (R6c);
  - the state-flip rate;
  - the mean regime duration.
- **R5. After freezing.** How regimes relate to *later* returns may be studied **only after** the regime definitions are frozen and hashed, and it must never feed back into them.
- **R6. Fixed training mechanics** (they apply to every refit):
  - **a) Scaling.** Robust standardisation: (x − median) / IQR of each input over **that refit's training window only**.
    - The parameters are stored with the model and applied unchanged until the next refit.
    - An input with IQR = 0 in the window is dropped for that refit, and this is logged.
  - **b) Algorithm.** k-means (Lloyd), `n_init = 50`, `random_state = 20260108`, on the scaled inputs.
  - **c) Label alignment.**
    - Each refit's centroids are first converted back to original units.
    - They are then matched to the **anchor**, the first model's centroids in the anchor's scaling, by minimum-cost one-to-one assignment (Hungarian method, Euclidean distance).
    - Regime names come from the anchor and never change.
    - If a matched centroid is more than **2.0** anchor-scaled units from its anchor centroid, the refit is flagged `DEFINITION_DRIFT`. It is reported, never silently renamed.
  - **d) `UNKNOWN`.** A day is `UNKNOWN` if any of these holds:
    - any input is missing;
    - (distance to the nearest centroid) / (distance to the second nearest) > **0.80** (ambiguous). If the second-nearest distance is 0, the day is `UNKNOWN`: two centroids coincide, so the case is ambiguous by definition. If only the nearest distance is 0, the ratio is 0 and the day is not ambiguous;
    - the distance to the nearest centroid is above the **95th percentile** of the training-set nearest-centroid distances of the model in force (outlier).
  - **e) Missing values.** **No imputation.**
    - Training uses complete rows only, and the number of dropped rows is logged per refit.
    - A day with a missing input is `UNKNOWN` (d).
    - An input is computed only if at least **20** eligible series (P1) contribute that day; otherwise it is missing.
  - **f) Scenarios.** The regime model is fitted on **P1** market aggregates, and that is the primary model. The same frozen mechanics are re-run on S50k and S250k as **separate** models for reporting only, never to choose between them.

## 5. Separation and audit

- **A1.** The 150-coin universe, the 38 signal coins and anything else derived from CryptoRadar stay **local**. They are never in the public repo.
- **A2.** Every research run records:
  - the protocol version and its sha256;
  - the sha256 of the universe file it used;
  - the commit of its code.
- **A3.** Every rejected or abandoned experiment is logged too, not only the winners.
- **A4.** No change to CryptoRadar v24.65, Router A/B, the forward counters or validate.py comes from research. Any proposal goes through the normal review.

## 6. Known limits (accepted, not hidden)

- **L1.** Delistings announced before 2023-07 and effective in 2024 were not searched. This is very unlikely but not proven.
- **L2.** Pairs removed with no announcement cannot be found.
- **L3.** An archive file is not proof of tradability. Trading suspensions are not documented separately; rule B leaves those hours empty.
- **L4.** This is a **Research Dataset Candidate**, not the complete historical tradable universe.

## 7. Control hashes

- `INPUTS_SHA256.txt` sha256 = `b7ce4df7e00f9c318f09cc52e54efc611022649e8129b0ed1180c920fcf13237` (918 files; unchanged from v1.0 and v1.1).
- `forced_exit_reference.csv` sha256 = `67221b1037e2800ca4a5a7696b996a78df14df898944e5aecb8f0c924c1e3e59`; `lab/forced_exit_reference.py` sha256 = `a552764df5e848270c4f418d32bd75c1abe71844f437890e8b4f1e20d8bc5a51`.
- Universe files:
  - P1 `1bbad60e87d977decbdaa16d923707e25eee1021e1e99d32cae31c5196eba10c`
  - S50k `0946424b7976a542985f0a5422224f97b5053d3c2d97327e280c484dcbcbc8a8`
  - S250k `482c681dea9b266c30957a83b3cd41016f1f077077a9f18d1abdb904af00835c`
- Code:
  - `lab/liquidity_profile.py` `32fc4fb5…40e9e9`
  - `tests/test_liquidity_pit.py` `8be844ec…48fe26`
  - `lab/guard.py` `2a2e7d88…6e848e7`
- Segment guard: `lab/segment_loader.py` `158eac908876f27098280f2ea6952d0eb39e44fc4f12e4b0841725f7db4f7ff3`; `tests/test_segment_loader.py` `2a893057ee4e8e23546c307c0ed91ea504da1590e1675bb3912cc40d3d06d725` (32/32 pass; 16/16 planted mutants killed, including 6 that try to re-open the Holdout).
- The sha256 of **this file** is recorded outside it, in `RESEARCH_PROTOCOL_v1.2.sha256`, and in the commit message.
