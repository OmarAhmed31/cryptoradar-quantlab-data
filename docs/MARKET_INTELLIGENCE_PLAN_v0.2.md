> **SUPERSEDED — NOT AUTHORITATIVE.** Replaced by `docs/MARKET_INTELLIGENCE_PLAN_v0.3.md` and Research Protocol v1.2. Kept only as a record of the review history. Where this file differs from Protocol v1.2, **the protocol wins**.

# Market Intelligence — plan v0.2 (for approval; nothing computed)

**Status:** PROPOSAL.
- **No statistic or chart has been computed.**
- Protocol v1.1 is FIXED and is not changed (sha256 `91718b69…678c`, tag `protocol-v1.1`).
- **Change from v0.1:** Option B is removed (rejected). §2 adds the horizon, purge and embargo rules, as requested in the review of 2026-11-08. §3 adds the point-in-time controls for regime models.

## 1. Time split (Option A, approved in principle)

| Segment | Data range (UTC) | **Entry window** (new, §2) | Use |
|---|---|---|---|
| Development | 2024-01-01 → 2025-08-31 | 2024-01-01 → **2025-08-01** | MI, features, regime models, strategy generation |
| Embargo 1 | 2025-09-01 → 2025-09-07 | none | not used by any segment |
| Validation | 2025-09-08 → 2026-03-31 | 2025-09-08 → **2026-03-01** | selection and checks only, no MI |
| Embargo 2 | 2026-04-01 → 2026-04-07 | none | not used by any segment |
| Final Holdout | 2026-04-08 → 2026-10-31 16:00 (T2) | 2026-04-08 → **2026-10-01** | opened **once**, after the candidates are frozen |
| Forward Shadow | from 2026-11-01 | — | live counters, no trading |

All dates come from the calendar alone.

## 2. Horizon, purging and embargo (proposed for Protocol v1.2)

- **H1. Maximum horizon.** `H_max = 30 days` (720 hours) for **every** forward label, outcome and trade holding period in the Quant Lab.
  - This matches CryptoRadar's 30-day maximum hold.
  - A trade still open after 30 days is closed by a **time exit** at the close of the last traded hour of day 30, recorded as `TIME_EXIT`.
  - No label may look further ahead than 30 days.
- **H2. Entry window (no label crosses a boundary).** An entry or a labelled observation at time *t* is allowed in segment S **only if t + H_max ≤ end of S**.
  - So the last 30 days of each segment contain **no new entries and no label start points**.
  - They still serve as the outcome period of earlier entries.
  - **Every outcome therefore ends inside the segment where it started.** This is fixed by time, independent of how long a trade actually lasts, so purging never depends on the result and never favours short trades.
- **H3. Purging (safety net).** Any observation or trade whose outcome interval [t, t+h] is not fully inside a single segment is **removed** from that segment and from every statistic, label, metric and report.
  - Under H2 this should never happen.
  - A test (§4) must prove the count is **0**.
- **H4. Embargo.** The two 7-day embargoes stay as approved. No observation, label or entry starts in them.
  - With H2, the separation between the last label data of one segment and the first entry of the next is **≥ 37 days**: 30 days of entry cut plus 7 days of embargo.
- **H5. Causal warm-up is allowed across boundaries.** A **feature** computed at time *t* may use any data **before** *t*: earlier segments, the December 2023 warm-up, or the embargo.
  - Information flows forward only, so this is not leakage.
  - A **label or outcome may never use data after the end of its own segment.**
- **H6. Segment isolation of research.**
  - MI statistics, feature selection, regime-model fitting and choices of k, thresholds or parameters use **Development observations only** (H2 applies).
  - Validation and Final Holdout data are not read by any MI, feature-discovery or regime-training code.
  - This is **enforced in code**: the data loader takes a segment name and refuses timestamps outside that segment, plus an explicit warm-up range for features.
- **H7. Final Holdout is sealed.**
  - Nothing is computed or displayed on it before the candidates and their rules are **frozen and hashed**. That includes descriptive statistics, charts and counts.
  - Opening it is a logged one-time event.

## 3. Market Intelligence scope (Development only; descriptive; point-in-time)

| Block | Output | Rule |
|---|---|---|
| M1 Market state | daily breadth (% of eligible pairs up over 1, 7 and 30 days), median return, dispersion, BTC vs median altcoin | day d uses data up to the close of d-1 |
| M2 Volatility | realised volatility over 1, 7 and 30 days per pair and market-wide; volatility bands | band edges estimated **only from data before d** (expanding window inside Development) |
| M3 Liquidity | P1 universe size, entries and exits, turnover | from the fixed universe files |
| M4 Correlation | rolling 30-day correlation to BTC and to the median coin | prior data only |
| M5 Candidate regimes | rule-based bands plus at most one clustering method | see R1–R5 below |
| M6 Survivorship lens | M1–M4 with and without the later-delisted series | — |

**Every statistic is reported for P1, S50k and S250k.** No strategy, entry, exit or profit and loss is computed.

**Regime controls (point-in-time):**

- **R1. Inputs.** The inputs are **past-only** M1/M2/M4 quantities. **Future returns are never used**, either to define a regime or to choose the number of clusters.
- **R2. Choosing k.**
  - k is chosen from **3 to 6** by an internal criterion (BIC or silhouette) computed on **Development part 1** (2024-01-01 → 2024-12-31) only.
  - It is fixed before part 2 (2025-01-01 → 2025-08-01) is looked at.
  - There is always an `UNKNOWN` class for low-confidence days.
- **R3. As-known labels.**
  - The model is refit **monthly** on data up to the refit date and frozen until the next refit.
  - Each day is labelled by the model frozen at that time, and that label is **stored as it was known that day** (`regime_asof`).
  - The past is **never relabelled** with a model fitted on later data.
- **R4. Stability.**
  - Agreement of the part-1 model applied to part 2.
  - State-flip rate.
  - Mean regime duration.
- **R5. Looking at returns later.** How regimes relate to *later* returns can be studied **after** the regime definitions are frozen and hashed. That information must not feed back into the definitions.

## 4. Acceptance tests (before any MI result is shown)

| Test | Requirement |
|---|---|
| A1 Destructive future overwrite | Every MI value and `regime_asof` for day d is unchanged when day d and every later day is overwritten (as in v0.10.1) |
| A2 Segment guard | The loader **refuses** any Validation or Holdout timestamp in MI, feature and regime code: a deliberate attempt must raise |
| A3 Boundary count | H2: there are 0 Development entries or label starts after 2025-08-01. H3: 0 outcome intervals cross a segment boundary |
| A4 As-known regimes | Relabelling yesterday with today's model is detected. A mutant that relabels the past must fail the tests |
| A5 Mutants | At minimum: window includes d; no entry cut; loader without the segment guard; regime refit on all of Development. All must be killed |

## 5. Proposed new text for Protocol v1.2

Only these items would be added: **T4** (the §1 table), **H1–H7** and **R1–R5**. Every other line of v1.1 stays as it is.

Protocol v1.2 is written and hashed only after this plan is approved.
