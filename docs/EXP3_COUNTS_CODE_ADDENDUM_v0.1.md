# Experiment 3 counts code: developer addendum v0.1 (for review with the code; NOTHING computed on real data)

**Base:** plan `EXP3_DESIGN_SELECTION_PLAN_v0.3.md` (sha256 `b18f4559…baba1`), APPROVED — EXPERIMENT 3 COUNTS PLAN.
**Code:** `lab/exp3_counts.py`. **Tests:** `tests/test_exp3.py` (synthetic only), `tests/run_exp3_mutants.py`.
**One-run wrapper:** `tests/run_exp3_once.py` (RD4: repository run, corrupted-outcome run, isolated no-network run; byte-identical). **Not executed.**

Writing the code exposed four points that the plan does not settle. Each is now one constant in the code, fixed **before** the run. **The reviewer decides each one.**

## A1. "L is a guaranteed lower bound" is not true in general (correction of plan §3.5)

The plan argues: a real trade can only end earlier, so the real number of completed trades is ≥ L. **That argument fails when trades block for different lengths.**

**Counterexample** (test X10d):
- A on coin A at hour 0, ends at hour 168;
- B on coin B at hour 10, with no exit, so it blocks to the segment end and does not count;
- C at hour 200 and D at hour 400, both normal.

The plan's greedy count holds A to hour 168, so B is blocked, then C and D are taken: **L = 3**.

But if A's real stop hits at hour 5, the real trader is free at hour 10, takes B, and is stuck: **1 completed trade**.

The induction "real k-th entry ≤ greedy k-th entry" holds only when every block has the same length. Here the blocks vary: 7 days, plus a gap until the next traded bar, or a cut.

**What the code does:**

| Measure | Definition | Status |
|---|---|---|
| **L_greedy** | the plan's count: every trade held to its latest end; ties broken by coin name | exactly the approved method. **Its meaning is corrected**: the count on the full-hold path, **not** a guarantee |
| **L_worst** | the true minimum over every exit time (an early exit is a completed trade), every tie choice and a superset of the same-coin re-entry cases | **rigorous**: real completed trades ≥ L_worst. Verified by tests X10a–c against an exhaustive search and simulated paths |

**The problem with L_worst:** a single reachable signal with no exit (for example a coin with a long trading gap) drags it down to almost nothing.

On a random synthetic set (3,000 signals, 3% with no exit), **L_greedy = 51 against L_worst = 2.** Without prices, an early stop is always possible, so any guaranteed bound becomes degenerate.

**Decision A1:**
- **(a) Recommended: select on L_greedy**, as approved, with the corrected wording, and report L_worst alongside it as a diagnostic.
- **(b) Select on L_worst.** It is fully conservative, but it will probably stop every design.

The code is set to (a): `SELECT_ON = "L_greedy"`.

## A2. Half-spread skip (Spec §9) applied in the count

P1 **skips** a trade whose Corwin–Schultz half-spread cannot be estimated (fewer than 360 valid hour pairs in days d-30…d-1). Without this rule, L would count trades that P1 cannot take.

- It uses only highs and lows **before** the entry day. It is the same formula as the frozen cost model, re-implemented because that module is an outcome module and cannot be imported.
- Reported as `SKIPPED_NO_HALF_SPREAD`. Constant: `APPLY_HS_SKIP = True`.

## A3. Entry-time wide-stop check (Spec §6) applied in the count

P1 skips at entry if (fill − stop)/fill > the stop limit.

- **The fill is the entry bar's open.** By rule B, that is the open of its first traded minute, i.e. the entry price itself. **It is not a later price and not an outcome**, but plan §3.4 lists only timestamps. **This needs explicit approval.**
- The limit is E5 for the hourly designs and stop_d P90 for D-D1.
- Reported as `SKIPPED_WIDE_STOP_AT_ENTRY`. Constant: `APPLY_ENTRY_STOP_SKIP = True`.
- If rejected, it is switched off, and the signal-close check (E5 / stop_d) remains the only stop test.

## A4. Conventions fixed in the code (please confirm)

1. **The time-exit bar** is the first traded bar with a label ≥ entry hour + 1 h + 7 days, so that all its minutes are after any possible deadline. The trade ends at that bar + 1 h.
   - This already implies a block ≥ signal + 7 days + 3 hours for the hourly designs, so the 7 d + 2 h minimum never binds. It is kept as written.
   - Its mutant would be equivalent, so a test checks the invariant instead (X7 invariant).
2. **H_max:** counted only if that end is ≤ entry hour + 720 h, or a PRICED cut is < entry hour + 720 h.
   - Because the entry cut (2025-08-02) + 720 h falls before the segment end, `OPEN_AT_SEGMENT_END` **cannot occur in Development**. Any unfinished trade is `EXCLUDED_HMAX`.
3. **The next entry** needs an entry hour ≥ the previous exit, i.e. a later hour, never the same entry hour.
4. **Same-coin re-entry (Spec §5.5):** the signal's range window must start at or after that coin's last exit.
   - That window is 168 h for the hourly designs and **20 days for D-D1** (the daily analogue, which needs confirmation).
5. **The delisting ledger** is read without its price column (test X1c). All 149 rows are currently PRICED.
6. **States:** an hourly bar uses its day's state, as in the frozen Experiment 2 cascade. A D-D1 signal uses the state of D+1, which is known at D+1 00:00.

## Defects found and fixed while testing (before any real run)

- **The time unit:** traded-bar times were in the index's unit (not ns), while Timestamp.value is ns, so no exit bar was ever found. Fixed with `as_unit("ns")`; the X7 cases catch it.
- **The abstention mask** became an object array after `fillna`. `~` on Python booleans gives −1/−2, so Transition days were not removed from D-D1. Fixed with `astype(bool)`; X5b catches it.

## Test status

- `tests/test_exp3.py`: **48/48 PASS** on synthetic data.
- `tests/run_exp3_mutants.py`: see `out/exp3/precheck/mutants.json` (26 planted defects).
