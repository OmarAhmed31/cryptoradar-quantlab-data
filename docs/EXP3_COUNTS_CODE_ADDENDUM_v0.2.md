# Experiment 3 counts code: addendum v0.2 (reviewer decisions recorded; NOTHING computed on real data)

**v0.2 = v0.1** (sha256 `098e35af…f5c00a`) **+ the reviewer's decisions on A1–A4**, all approved, two of them with conditions. v0.1 stays in the repository unchanged.

These decisions are **methodological approvals**. They are **not** an approval of the code and **not** permission to run. The code and tests in this package are for the final review before the run.

## A1. L_greedy and L_worst: APPROVED, with corrected wording

| Measure | Definition (fixed) | Role |
|---|---|---|
| **L_greedy** | an **estimate** of completed trades under **sequential blocking**: every trade is held to its latest end, and ties are broken by coin name. **It is NOT a guaranteed minimum.** | **Acceptance rule: L_greedy ≥ 100**, then the fewest entry conditions, and D-D1 wins the tie with D-H1 |
| **L_worst** | a **guaranteed minimum under the stated assumptions**: any exit time (an early exit is a completed trade), any tie choice, and a superset of the re-entry cases. Conservative, and often uninformative | **reported beside L_greedy only**, as an extra conservatism check. **Never an acceptance rule** |

- **No design is described as guaranteeing 100 trades.**
- The plan's sentence "the real number of completed trades is ≥ L" (v0.3 §3.5) is **withdrawn** for L_greedy. The counterexample is test X10d.
- In the code: `SELECT_ON = "L_greedy"`, and a `definitions` block is written into the output.
- Tests: X14 checks the settings and the definitions; XM29 plants "select on L_worst" and must be killed.

## A2. Half-spread: APPROVED

- **The P1 window and minimum:** the hours of days d-30 … d-1, where d is **the entry day**, with ≥ 360 valid consecutive-hour pairs. This is the same formula as the frozen P1 cost model (`lab/strategy.py` `half_spread`), re-implemented because that module is an outcome module and cannot be imported.
- Data from before the entry day only.
- Exclusions are counted as `SKIPPED_NO_HALF_SPREAD`.
- Test X8f checks the formula against an independent loop; X8e checks the skip; XM24 plants "skip off".

## A3. Stop distance at entry: APPROVED, with conditions

- **The fill is the Spec §5.5 execution price:** the open of the first traded 1-minute candle in the entry hour.
  - **Verified in the pack builder** (`lab/active_build.py` `build_pair`): the hourly `open` is the open of the first minute with volume > 0 in that hour (`ms_[0][0]` over the time-sorted traded minutes).
  - So the hourly open **is** that fill. The check is made at the moment of entry only.
- **No later candle is used:** no high, low or close of the entry bar or after it. Test X8g checks the exact boundary on the open, and XM19 plants "use the close".
- **The frozen limit, unchanged:** E5 = `0.3407346823316945` for the hourly designs (exact, from `thresholds.json`), and stop_d P90 for D-D1, derived in the same run.
- **The same formula in P1:** skip if (fill − stop)/fill > limit, with stop = R_low (hourly) or RL_D (daily). **P1 must use this exact formula.**
- Exclusions are counted as `SKIPPED_WIDE_STOP_AT_ENTRY`.

## A4. D-D1 same-coin re-entry: APPROVED, with conditions

- **This is a fixed signal-management rule. It is NOT derived from the data.** It prevents re-using the same 20-day breakout window for the same coin.
- **The rule:** a new D-D1 signal on the same coin needs its full range window (days D-20 … D-1) to start at or after that coin's last exit.
  - If the exit falls on day X, then days X+1 … X+20 are **20 full calendar days**, and the earliest new signal is on day X+21, with the entry on X+22.
  - No new signal on that coin is allowed during the cooldown.
- **It applies to the same coin only.** Other coins are unaffected.
- The hourly designs keep Spec §5.5 (a new full 168-hour window after the exit).
- **It is fixed for the counts run and for P1. It is not changed after the counts are seen.**
- Tests: X15 checks the window offset; X9 and X12 check the rule in the greedy count. XM28 (a 19-day window) and XM12 (rule removed) must be killed.

## Other fixed conventions (unchanged from v0.1 §A4)

- The time-exit bar is the first traded bar wholly after the latest possible deadline.
- The H_max test uses the entry hour + 720 h.
- The next entry needs an entry hour ≥ the previous exit.
- The ledger is read without its price column.
- States: an hourly bar uses its own day's state; D-D1 uses the state of D+1.

## Check: the counts follow P1 eligibility

| P1 rule (Spec v0.1.3) | In the counts code |
|---|---|
| crypto-only universe, P1-eligible | yes: hourly on the bar's day, daily on D+1 (X12a, X12b) |
| entry = first traded minute in the entry hour; otherwise NOT_EXECUTED | yes (X8a, X12f) |
| entry window of the segment (< 2025-08-02) | yes, PAST_ENTRY_CUT (X8c, XM26) |
| half-spread estimable | yes, A2 |
| stop distance at entry ≤ the limit | yes, A3 |
| one position for the whole portfolio | yes, greedy and L_worst (X9, X10) |
| re-entry after a new full window | yes, A4 and Spec §5.5 |
| 7-day time exit at the first traded minute | yes, a conservative exit bar (X7) |
| U9b delisting, PRICED only | yes (X7, XM2, XM25) |
| H_max 720 h | yes (X7, XM1, XM3) |
| DV30 cap | **not a skip** (it only caps size), so it does not change counts |

## Test status (synthetic data only)

See `out/exp3/precheck/`: `tests.json` and `mutants.json`. The frozen hashes are in `FROZEN_SHA256.txt`.
