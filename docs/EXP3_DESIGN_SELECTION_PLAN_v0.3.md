# Experiment 3: design-selection plan v0.3 (DRAFT for review; NOTHING computed)

**v0.3 = v0.2** (sha256 `9cc96ffe…c185`; approved except one point) **+ one required fix:**
- **Protocol H_max = 30 days = 720 hours** now applies to the counting of L (§3 b, d).
- Plus one clarification: what "number of conditions" means (§4).

Nothing else changed: the designs, the frozen hourly thresholds, the daily derivation method, the 7 days + 2 hours block, the selection rule and Protocol v1.2.

**v0.2 = v0.1** (sha256 `df7db4d0…5a08`; the designs, reuse/derivation choices and selection rule approved in principle) **+ the reviewer's required fixes:**
- **(1)** a blocking period of **7 days + 2 hours**;
- **(2)** L counts only trades whose exit is **guaranteed** under U9, using timestamps, the delisting ledger and data availability only;
- **(3)** the D-D1 indicators and timing are fully defined;
- **(4)** **one position for the whole portfolio**, and **exact** thresholds read from `thresholds.json`.

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
| **D-D1 (daily)** | **daily** (definitions in §2.1) | B_d **∧** A1_d **∧** RVOL_d ≥ **P75** **∧** stop_d ≤ **P90**, with P75 and P90 taken on the daily breakout population **before any filter**. **States:** only Transition/Uncertain abstains | the two daily values are derived **in the same counts run**, with **the same method and populations** as v0.3.2 (P75 and P90 on the breakout population, before any filter). They cannot reuse the hourly values, which describe a different bar size |

**Removed from experiment 2, and why.** These are **design rationales recorded before any test. They are NOT statistical proof that the removed conditions are useless:**

| Removed | Why |
|---|---|
| **A2** (≥ 50% below the peak) | It turns "accumulation" into "deep crash recovery", a different idea |
| **C** (7-day vol < 30-day vol) | It largely duplicates A1 (FD-1: F06–F09 form one cluster) |
| **BTC strength over 24 hours** | It removed only 8 of 229 candidates, so it carried almost no information |
| **Bear / High-Vol actions** | They stack further conditions on a sample that is already small. **Per-state results are still reported** (U1), so state-specific behaviour can be studied, and only Transition abstains |

### 2.1 D-D1, exact definitions (fixed now)

**Daily bar of UTC day D,** built from that day's traded hourly bars:

| Field | Definition |
|---|---|
| high_D | max high |
| low_D | min low |
| close_D | the last traded close |
| vol_D | Σ vol_quote |

A day is **traded** if it has ≥ 1 traded hour.

**Window:** days D-20 … D-1 `CONV`, using only their traded days, and needing **≥ 10 traded days** (the 50% rule). In that window:
- `RH_D` = the max high_x;
- `RL_D` = the min low_x.

**Conditions:**

| Condition | Definition |
|---|---|
| **B_d** | close_D > RH_D |
| **A1_d** | width_D = RH_D / RL_D − 1 ≤ the **25th percentile** of the coin's own width values on days D-180 … D-1 (≥ 90 values). It is coin-relative, like A1 |
| **RVOL_d** | **vol_D / the median of vol_x over the traded days D-20 … D-1** |
| **stop_d** | **the stop level is RL_D**, the 20-day range low, the same structural rule as the hourly R_low. stop_d = (close_D − RL_D) / close_D |

**Timing:**
- The daily bar is complete at **D+1 00:00 UTC**, and the signal is known then.
- **Entry = the open of the first traded 1-minute candle in [D+1 00:00, D+1 01:00).** If there is none, the signal is NOT_EXECUTED.
- The stop is checked from entry on, stop first, exactly as in Spec v0.1.3.

**Daily breakout population (for P75 / P90):** the coin-days with B_d, crypto-only, P1-eligible on D+1 (the entry day), and ≥ 10 traded days in the window, **before** A1_d, RVOL_d or stop_d is applied.

**Hourly designs:** the code **reads the exact values from `thresholds.json`** and checks its sha256 (`5dc38aa9…8c5f`). The rounded numbers in this document (7.97, 0.826, 34.1%) are for display only.

## 3. Feasibility: a guaranteed lower bound on completed trades (no returns)

For each design, on Development:
1. Count the candidate signals (bars, or days for D-D1).
2. **One position for the whole portfolio** (Scenario A1). There is never more than one open trade across all coins.
3. **A greedy pass in time order:**
   - **a.** A signal is **taken** if no trade is open, its entry hour has a traded minute (otherwise NOT_EXECUTED, not taken), and the entry is before the segment's entry cut (t < 2025-08-02, H2).
   - **b.** A taken trade **blocks** new entries until:

     **block_end = max(signal_time + 7 days + 2 hours, min(first traded bar after the 7-day deadline + 1 hour, segment end))**

     - 7 days + 2 hours is the uniform minimum.
     - The second term covers a coin with no trade right after the deadline, where the time exit fills later.
     - If no traded bar comes, the trade keeps the capital **until the segment end** (U9). **No overlapping signal is ever counted while it is open.**
   - **c.** **Delisting (U9).** If the coin's official cut falls inside [entry, block_end):
     - the trade ends at the cut;
     - **it counts only if its forced exit is PRICED** (status PRICED and a gap ≤ 60 minutes in `forced_exit_reference`);
     - an `UNPRICEABLE_FORCED_EXIT` is **taken (it blocks) but NOT counted**.
   - **d.** A trade **counts** toward L only if its exit is **guaranteed within Protocol H_max (720 hours from entry)**:
     - a PRICED forced exit (c) with the cut **< entry + 720 hours**; **or**
     - a traded bar exists **after the 7-day deadline and before both entry + 720 hours and the segment end**. The time-exit fill is then certain inside H_max.

     **If no executable exit exists within H_max, the trade is NOT counted** (`EXCLUDED_HMAX`). It still blocks the capital as in (b).
   - **e.** **The report counts every excluded case by reason:** `NOT_EXECUTED`, `UNPRICEABLE_FORCED_EXIT`, `EXCLUDED_HMAX`, and blocked signals.
4. **Only timestamps, traded-bar existence and the delisting ledger are used.** No price after the entry, no return, no stop or target outcome.
5. **Why L is a lower bound:**
   - a real trade can only end **earlier** (at a stop or target), which frees capital sooner and lets more signals be taken;
   - every counted trade has a guaranteed exit.

   So the real number of completed trades is **≥ L**.

The report shows, per design:
- the count after each condition;
- the number of signals per coin;
- the split by month and by state;
- L.

## 4. Selection rule (fixed now)

1. Keep only the designs with **L ≥ 100** (U7 can then be decided, whatever the outcome).
2. Among those, choose **the fewest conditions** (parsimony). "Conditions" means **the entry conditions a signal must satisfy**: D-H1 = 4 (B, A1, E3, E5), D-H2 = 5 (+ E4), D-D1 = 4 (B_d, A1_d, RVOL_d, stop_d). The Transition/Uncertain abstention is common to all three, so it is not counted. This is never a count of indicators or lines of code. The order is: D-H1, then D-D1 (same count), then D-H2. If D-H1 and D-D1 both pass, **D-D1 wins the tie**, because daily signals are less exposed to intraday microstructure and to costs.
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
