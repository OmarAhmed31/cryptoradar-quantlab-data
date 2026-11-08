# CryptoRadar Quant Lab — RESEARCH PROTOCOL v1.0

Status: **SUBMITTED FOR APPROVAL.** It becomes **FIXED** only when the expert approves **this exact sha256**.

The rules U1–U8, D1–D5 and T1–T3 are the ones the expert approved in the v0.10.1 review (2026-11-08). U9 is new and needs confirmation.

Rule for this file: it is fixed **before** any strategy research. It must not change while research is running. Any change makes a new version (v1.1, …), which must be:
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
| **Universe files (authoritative)** | `out/research_protocol/v1.0/universe/eligibility_daily_{P1,S50k,S250k}.csv.gz` | `eligible` per series per research day |

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
- **U9. Position on a pair that leaves the universe.** A position opened while the pair was eligible may be held. **No new entry** is allowed while the pair is ineligible.
  - If a pair is delisted while a position is open, the position is closed at the last traded price before the cut, and this is recorded as a forced exit.
  - *(This rule is added here for completeness; the expert must confirm it before research starts.)*

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

- `INPUTS_SHA256.txt` sha256 = `b7ce4df7e00f9c318f09cc52e54efc611022649e8129b0ed1180c920fcf13237` (918 files).
- Universe files:
  - P1 `1bbad60e87d977decbdaa16d923707e25eee1021e1e99d32cae31c5196eba10c`
  - S50k `0946424b7976a542985f0a5422224f97b5053d3c2d97327e280c484dcbcbc8a8`
  - S250k `482c681dea9b266c30957a83b3cd41016f1f077077a9f18d1abdb904af00835c`
- Code:
  - `lab/liquidity_profile.py` `32fc4fb5…40e9e9`
  - `tests/test_liquidity_pit.py` `8be844ec…48fe26`
  - `lab/guard.py` `2a2e7d88…6e848e7`
- The sha256 of **this file** is recorded outside it, in `RESEARCH_PROTOCOL_v1.0.sha256`, and in the commit message.
