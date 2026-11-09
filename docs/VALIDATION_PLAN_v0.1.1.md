# Validation Plan v0.1.1: replication of the FD-2 candidates (APPROVED 2026-11-09; NOTHING executed)

**Status:**
- **Approved** by the reviewer on 2026-11-09 as an execution plan under the fixed Protocol v1.2. **No v1.3 is needed**, because no protocol rule changes.
- **v0.1.1 = v0.1 + the reviewer's clarifications only:** V1 count, V3 cluster rule, V5 ratio display, and the two stop conditions.
- **No Validation data has been read.** No Validation pack, feature, outcome or IC exists.
- Protocol v1.2 FIXED. FD-2 accepted (`FD2_REVIEW_RECORD.md`, commit `6e1b826`). The Final Holdout stays closed, with no opening path (H7).

**Goal:** a single, pre-registered check of whether the **41 FD-2 candidates keep their sign out of sample**, on the Validation segment.
- It is an association check (rank IC), exactly as in FD-2.
- It is **not** a strategy, a trade, P&L or a profit test.

## 0. Decisions requested from the reviewer

| # | Question | Proposal |
|---|---|---|
| V0 ✅ | Protocol form | Protocol v1.2 **already** defines Validation as "selection and checks only" (T4), with its guard, entry window and lookback rules (H5). This plan **changes no protocol rule**. **Proposal:** approve it as a hashed plan, like FD plan v0.1.1. If the reviewer prefers, it becomes the annex of a Protocol v1.3, with only this text added. |
| V1 ✅ | Hypothesis family | **All 41 FD-2 candidates, unchanged**, including the 4 `BH_ONLY` (18 at h = 1, 13 at h = 7, 10 at h = 30). There is no new selection: removing or merging them now would be selection on Development results after the fact. The 23 non-candidates and the 2 exploratory cells are reported **descriptively only**. |
| V2 ✅ | Test | **One-sided** in the FD-2 direction: H1 is that the Validation mean IC has the same sign as in Development. The statistic is Newey-West with lag h − 1 and the normal p, as in FD-2. **BH q = 0.10** over the 41 is the rule. **BY q = 0.10** is a sensitivity, with the label `BH_ONLY — FAILS_BY_SENSITIVITY` (as in D6). |
| V3 ✅ | Result labels (fixed now) | `REPLICATED`: BH-significant, same sign. `NOT_REPLICATED`: not significant, same sign. `REVERSED`: the opposite sign, whatever its p. These are reported per hypothesis and **per FD-1 cluster**: the cluster counts and the median of its members' ICs |
| V4 ✅ | Scenarios | **P1 decides.** S50k and S250k means and signs are reported, not gating. Validation has about 175 entry days, so a second gate would mostly cost power |
| V5 ✅ | Magnitude | The ratio Validation mean IC / Development mean IC is reported **descriptively, with no threshold**. A cut-off would have no data basis |

## 0.1 Reviewer clarifications (binding)

- **V1 count.** The family is **41 hypotheses in total**: 37 passed BH and BY in FD-2, and 4 passed BH only. The 4 `BH_ONLY` are **part of** the 41, not extra tests. Nothing is removed, merged or newly selected.
- **V3 cluster rule (fixed before any result).**
  - A cluster's label is a **summary** of its member hypotheses, using the FD-1 clusters at |ρ| ≥ 0.80.
  - It is **not** a separate test and **not** statistically independent of its members.
  - Take n = its member cells among the 41, R = members `REPLICATED`, V = members `REVERSED`:

    | Cluster label | Condition |
    |---|---|
    | `CLUSTER_REPLICATED` | R ≥ n/2 and V = 0 |
    | `CLUSTER_REVERSED` | V > n/2 |
    | `CLUSTER_NOT_REPLICATED` | otherwise |

  - The counts R, V and n − R − V and the median member Validation IC are always shown.
- **V5 display.** Every hypothesis shows the Development mean IC, the Validation mean IC and the ratio Validation/Development.
  - The ratio is shown as **`N/A`**, with the raw values kept, when the Development mean IC is 0 or its FD-2 block-bootstrap 95% CI includes 0.
  - That is a data-based definition of "near zero". It needs no extra threshold.
  - All 41 candidates have Development CIs that exclude 0, so this is a safeguard.
- **Stop condition 1, the delisting ledger.**
  - **Before any computation**, the ledger must cover the Validation window, up to 2026-04-01, and every forced exit inside it must be priceable under U9b/U9c.
  - If coverage is incomplete or a case is unpriceable: **stop and report. No assumption fills the gap.**
- **Stop condition 2, the guard.**
  - **No Validation result is read** before all of these hold:
    - time isolation is proven (VA1/VA2 pass);
    - the plan, the family, the test direction and their hashes are committed.

## 0.2 Stop condition 1, checked before any Validation data was read (ledger metadata only)

| Check | Result |
|---|---|
| Latest effective delisting in the ledger (OKX AR / EN-EU / pre-2024) | **2026-10-03 08:00**, which is later than 2026-04-01 |
| USDT spot delistings effective in [2025-09-01, 2026-04-01) | **32**. All 32 are in `forced_exit_reference.csv` (Protocol v1.2 input) and vice versa |
| Their U9 status | **32/32 PRICED**, with a maximum gap of 23 minutes (≤ 60) |

**Stop condition 1 is satisfied.**

## 1. Data: `val_pack_v1`, built with the same slicing discipline as dev_pack_v1

- **Hourly candles:** start ≥ 2024-01-01 00:00 and close ≤ **2026-04-01 00:00**, the Validation end.
  - Development and embargo history is allowed **as lookback only** (H5).
  - The reader **stops** at the first candle that does not close by 2026-04-01. Nothing from the second embargo or the Holdout is read.
- **Universe:** days ≤ 2026-03-31, for P1, S50k and S250k. Lines with a later day are skipped without being parsed.
- **Forced exits:** cut < 2026-04-01 00:00.
- **The manifest records:**
  - the sha256 of every file;
  - the last candle and day;
  - the lines skipped;
  - **a coverage check of the delisting ledger**: the latest effective delisting date it covers must be ≥ 2026-04-01. If it is not, **stop and report** before any outcome is computed.

## 2. Computation (frozen definitions; the code is reused unchanged where possible)

- **Features:** the 22 features of `feature_catalogue.json` (sha256 `c51334e2…`), with the same code (`lab/fd_features.py`).
  - Their decision time t is a Validation day: `SegmentGuard("validation").check_feature`.
  - **No parameter is re-estimated.** Features have no fitted parameters. Ranks are cross-sectional per day.
- **Entries:** t ∈ [2025-09-08, 2026-03-02), about 175 days (T4/H2). The first embargo (2025-09-01 → 09-07) holds no entry.
- **Outcomes:** the FD-2 definition — close_asof ratio, U9b forced exits, `UNPRICEABLE` counted. Every outcome ends ≤ 2026-04-01. **H3 purge count = 0** (tested).
- **IC:** daily Spearman over eligible series (≥ 20), as in FD-2. The block bootstrap uses max(7, h) days, 2,000 resamples and seed 20260108, and gives a CI only.
- **No regime analysis.** Protocol v1.2 refuses MI on Validation, and Validation days have no `regime_asof`.

## 3. One shot

1. The code, tests and mutants are committed and pass **before** any Validation result is computed.
2. The computation then runs **once**. The output is frozen and hashed.
3. **After results, nothing is changed.**
   - A `NOT_REPLICATED` or `REVERSED` hypothesis is not re-tuned, re-defined or re-tested on Validation.
   - New ideas go to a new, separately approved plan. They can never be reported as validated by this run.
   - An implementation **bug** found after results may be fixed only with the reviewer's approval. The original output is kept, and the diff and both outputs are reported.

## 4. Acceptance tests (written before results)

| Test | What it proves |
|---|---|
| VA1 | **Isolation:** no candle closing after 2026-04-01, no universe day ≥ 2026-04-01 and no Holdout timestamp in the pack. The Holdout guard still raises |
| VA2 | **Guard:** every decision time is in Validation, entries t < 2026-03-02, outcomes end ≤ 2026-04-01, H3 = 0, no entry in the embargo |
| VA3 | **Feature equality:** Validation-day features use the frozen FD code. On overlapping lookback, feature values for 2025-08-31 (in the pack) equal the FD-1 values exactly |
| VA4 | **Destructive future overwrite:** corrupt every candle at or after t+h, and every candle at or after t for the features. Outcomes and features are unchanged |
| VA5 | **Independent naive recompute:** outcomes, including every forced exit, and ICs (scipy) |
| VA6 | **Family and labels:** exactly the 41 candidate cells, one-sided in the FD-2 sign; BH/BY against an independent formula; `REPLICATED` / `NOT_REPLICATED` / `REVERSED` on a synthetic table |
| VA7 | **Mutants (≥ 12), all killed.** Planted defects: two-sided p; the sign not taken from FD-2; the family re-selected; an entry in the embargo; an outcome crossing 2026-04-01; reading Holdout candles; same-day entry price; dropping delisted coins; forced exit at a later price; no overlap correction; BY as the rule; ignoring eligibility |
| VA8 | **Reviewer fast mode:** about 2 minutes. A **mini review package** is produced as well |

## 5. Not in scope

- Strategy discovery, entries/exits, costs, P&L, portfolio returns.
- Any Holdout access.
- Any change to Protocol v1.2, D4–D6, the 22 definitions or the 41-cell family.
