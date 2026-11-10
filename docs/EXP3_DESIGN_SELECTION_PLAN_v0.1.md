# Experiment 3: design-selection plan v0.1 (DRAFT for review; NOTHING computed)

**Context:**
- This is registry experiment 3. Experiment 2 (Accumulation Breakout v0.1.3) is closed as INCONCLUSIVE BY CONSTRUCTION, with 64 candidate bars against a minimum of 100.
- The reviewer allowed a **new, separate design**, at **specification stage only**. Opportunity counts and their composition may be compared, **with no trading result of any kind.** A design is **not** chosen just because it yields 100 opportunities.
- Protocol v1.2 FIXED. The Holdout is sealed. **P1 is not approved.**

## 1. The principle

1. **Signal soundness first.** Each candidate keeps the core idea: a quiet range, then a breakout with real volume. Each condition is one the idea needs, not a filter added for its own sake.
2. **Feasibility second.** It is measured **without returns**, as a **guaranteed lower bound on the number of completed trades** under the P1 rules (§3).
3. **A fixed selection rule** (§4), written now.

## 2. Candidate designs (exactly three; frozen now)

All three use the **crypto-only universe**, P1 eligibility, the entry and fill rules of Spec v0.1.3 §5.5–§9 (first traded minute after the signal; stop first; costs), the **exit templates X1, X2 and X3**, the **7-day time exit**, and **Scenario A1, a single position**.

| Design | Bars | Conditions | Thresholds |
|---|---|---|---|
| **D-H1 (minimal hourly)** | hourly | B: close_t > R_high (prior 168 bars) **∧** A1: tight range (coin-relative 25th percentile, unchanged) **∧** E3: RVOL ≥ 7.97 **∧** E5: stop ≤ 34.1%. **States:** only Transition/Uncertain abstains | **reused unchanged** from the frozen `thresholds.json` (sha256 `5dc38aa9…8c5f`). It is a different experiment, but the values were derived without outcomes, so reusing them adds **no** new fitting |
| **D-H2 (hourly + close strength)** | hourly | D-H1 **∧** E4: CLV ≥ 0.826 | same as D-H1 |
| **D-D1 (daily)** | **daily** (UTC day; known at the next 00:00) | B_d: daily close > the max high of the prior **20** days `CONV` **∧** A1_d: 20-day range width ≤ the coin's own 25th percentile of the prior 180 days **∧** RVOL_d ≥ **P75 of daily RVOL on daily breakout days** **∧** stop_d ≤ **P90 of daily stop distance on daily breakout days**. **States:** only Transition/Uncertain abstains | the two daily values are derived **in the same counts run**, with **the same method and populations** as v0.3.2 (P75 and P90 on the breakout population, before any filter). They cannot reuse the hourly values, which describe a different bar size |

**Removed from experiment 2, and why (signal soundness, not counts):**

| Removed | Why |
|---|---|
| **A2** (≥ 50% below the peak) | It turns "accumulation" into "deep crash recovery", a different idea |
| **C** (7-day vol < 30-day vol) | It largely duplicates A1 (FD-1: F06–F09 form one cluster) |
| **BTC strength over 24 hours** | It removed only 8 of 229 candidates, so it carried almost no information |
| **Bear / High-Vol actions** | They stack further conditions on a sample that is already small. **Per-state results are still reported** (U1), so state-specific behaviour can be studied, and only Transition abstains |

## 3. Feasibility: a guaranteed lower bound on completed trades (no returns)

For each design, on Development:
1. Count the candidate signals (bars, or days for D-D1).
2. Compute **L = the number of signals a single-position trader is guaranteed to complete.** Take the signals in time order, accept one, then block every signal in the next **7 days + 1 hour** (the maximum hold under the time exit, plus the entry delay), then accept the next one, and so on. Trades can only end earlier than 7 days, which frees capital sooner, so **the real number of completed trades is ≥ L.**
3. Apply one-position-per-coin and NOT_EXECUTED (no traded minute in the entry hour) using **timestamps only**. **No price after the entry, and no return, is used.**

The report shows, per design:
- the count after each condition;
- the number of signals per coin;
- the split by month and by state;
- L.

## 4. Selection rule (fixed now)

1. Keep only the designs with **L ≥ 100** (U7 can then be decided, whatever the outcome).
2. Among those, choose **the fewest conditions** (parsimony): D-H1, then D-D1 (same count), then D-H2. If D-H1 and D-D1 both pass, **D-D1 wins the tie**, because daily signals are less exposed to intraday microstructure and to costs.
3. If **no** design reaches L ≥ 100: **STOP.** Experiment 3 is recorded as INFEASIBLE, nothing is relaxed, and the reviewer decides.
4. The chosen design then gets its **full specification** for review. **Only after that is the P1 code written.**

## 5. Rules for the counts run

- One run, with the outputs committed before they are read.
- The same isolation as the threshold derivation: no outcome module, no Validation or Holdout data.
- The RD4-style isolated, corrupted-outcome re-run must be byte-identical.
- **Tests and code are reviewed before the run**, as before.
- **Printed and stored:** counts, compositions, timestamps-derived L, and the two daily derived thresholds. **Nothing else.**

## 6. Decision requested

1. Approve the **three candidate designs** (§2).
2. Approve the **lower-bound method L** (§3) and the **selection rule** (§4).
3. Approve **reusing** the frozen hourly thresholds, and **deriving the two daily ones** by the same method in the counts run.
