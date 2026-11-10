# Experiment 4 counts code: developer note v0.2 (for review with the code; NOTHING computed on real data)

**v0.2 = v0.1 + the reviewer's required change** (review of v0.44): **the fill check now runs only for the signals the portfolio selected, after the selection.**

- **Before (v0.44):** `run()` called `fill_check()` for every eligible signal before `portfolio()`. The result was not used in the ranking or the selection, but the entry bar was read early.
- **Now:**
  - `build_candidates()` carries **no fill field**. It holds only what is known at h, plus the row, column and stop that the check needs later.
  - `portfolio(cands, K, fill)` calls `fill(s)` **only for the signals selected at h** (step 7).
  - In `run()`, the entry bar's open and close are read **only inside that call**, through `fill_one()`.
  - Signals refused by rank, slot, cash, coin held or the re-entry window are recorded as `NOT_CHECKED`.
- **New tests:**
  - **Y2f:** a spy check is called only for the selected signals, never for NO_CASH, RANK, NO_SLOT or a held coin;
  - **Y2g:** the candidates carry no fill field;
  - **Y8a, extended:** on the synthetic pipeline, a fill result exists exactly for OPENED, NOT_EXECUTED and SKIPPED_WIDE_STOP_AT_ENTRY.
- **New and updated planted defects:**
  - **YM22:** the fill is checked for every batch member;
  - **YM23:** the entry bar is read for every eligible signal (the old run order);
  - **YM3, YM16 and YM21** are updated to the new code.

**The L_worst exception is approved by the reviewer:** `L_worst = null`, with the reason in the output. It is not used in selection or acceptance.

Nothing else changed: the strategy, the thresholds and the portfolio rules.


**Spec:** `EXP4_CAPITAL_ALLOCATION_DESIGN_PROPOSAL_v0.5.md`, FROZEN and approved.

| Kind | Files |
|---|---|
| **Code** | `lab/exp4_counts.py` |
| **Tests** | `tests/test_exp4.py` (synthetic only), `tests/run_exp4_mutants.py` |
| **One-run wrapper** | `tests/run_exp4_once.py` (RD4: repository run, corrupted-outcome run, isolated no-network run; byte-identical). **Not executed** |

## What is reused unchanged

**The frozen Experiment 3 code**, `lab/exp3_counts.py`, sha256 `b6fdc2d0…60f3`, commit `1f91f8b`. It is imported, not copied. Test Y1c checks its hash. It supplies:
- the signals and cascades of D-H1, D-H2 and D-D1;
- the frozen thresholds and their sha check;
- the daily derivation;
- the half-spread formula;
- the trade windows (the 7-day time exit, U9b, H_max);
- the calendar re-entry rule;
- the selection order.

## What is new: only the portfolio policy of spec v0.5 §1.3

| Spec step | Code |
|---|---|
| 0: the snapshot at h; an exit counts only if strictly before h | `free_time()` sets when a position counts as exited, and `portfolio()` releases a position only if `free_at ≤ h`. A time exit fills inside the exit bar, strictly before end = bar + 1 h, so it is free from h ≥ end. An exit **exactly at** end (a delisting cut, or no exit before the segment end) is free only after end |
| batch = the checks known at h | `pre_entry()`: the entry window and the half-spread. In `portfolio()`: the coin held (`BLOCKED_COIN_HELD`) and the re-entry window (`BLOCKED_REENTRY_WINDOW`). The signal conditions and eligibility come from the frozen Exp. 3 code |
| 2–3: K, free slots | **K = 3 throughout** (stage-1 assumption, spec §7) → `SKIPPED_NO_SLOT` |
| 5: no available cash | `SKIPPED_NO_CASH`. Cash becomes 0 after a fully filled batch. It stays positive if a selected signal fails at its fill, and it returns at an exit |
| 4: ranking | **RVOL descending, unrounded; an exact tie → the coin name ascending.** The value is the design's own RVOL at the signal bar (`rank_values()`): hourly, the frozen `indicators()["rvol"]`; D-D1, `daily_rvol()`, the same formula as the frozen RVOL_d condition (test Y6 recomputes it independently) |
| 7: at each fill | `fill_one()`, called by `portfolio()` **only for the selected signals**: `NOT_EXECUTED`, and `SKIPPED_WIDE_STOP_AT_ENTRY` on the entry bar open (A3). **A failed share stays in cash. It is never passed to a lower-ranked signal** (tests Y2 E8, E8b) |
| holding | a filled position is held to its latest end, the same sequential-blocking estimate as Exp. 3 L_greedy |

**L_greedy(K)** = the completed trades counted (the exit is guaranteed within H_max and the segment). It is reported with the spec §7 wording: **a preliminary estimate under K ≤ 3, NOT proof of U7.**

## One deviation from the frozen spec, for the reviewer's decision

**Spec §7 lists "L_worst reported" among the stage-1 outputs. The code does NOT compute L_worst for K = 3.** The output says `"L_worst": null`, with a note.

**Why:**
- The Exp. 3 worst-case method works on **one** open position: the adversary chooses one exit time at a time.
- With up to 3 concurrent positions **and** the cash rule, the state is the set of open positions, their exit times and whether cash is free. A valid worst case over every exit time of every position is a **combinatorial search with no tractable exact method** that I can prove correct.
- I would rather report nothing than report a number that claims to be a guarantee and is not. The Exp. 3 L_worst defect (fixed in v0.37) showed how easily such a bound goes wrong.
- **L_worst was reported-only and never an acceptance rule (D1/A1),** so the selection is unaffected.

**Decision requested:** accept that L_worst is not reported for Experiment 4. The alternative is to require it, which needs a separate method and its own review.

## Fixed implementation details (please confirm)

1. **The re-entry threshold after several exits of the same coin** is the latest threshold (`max`).
2. **The order of reasons:**
   - pre-entry: `PAST_ENTRY_CUT` → `SKIPPED_NO_HALF_SPREAD`;
   - at h: `BLOCKED_COIN_HELD` → `BLOCKED_REENTRY_WINDOW` → `SKIPPED_NO_SLOT` → `SKIPPED_NO_CASH` → `SKIPPED_RANK`;
   - at the fill: `NOT_EXECUTED` / `SKIPPED_WIDE_STOP_AT_ENTRY`.
3. **Reported per design:**
   - all the reasons;
   - the number of batches and the batch-size distribution;
   - the number of open positions after each entry;
   - the opened trades by trade-window reason;
   - the composition of the signals and of the opened trades;
   - L_greedy(K).
4. **The ledger price column is never read** (the frozen Exp. 3 `load_ledger`).

## Test status (synthetic data only)

- `tests/test_exp4.py`: **36/36 PASS**. These include: the spec examples E1–E9 as hand cases; an independent reference engine with explicit cash amounts (1,500 random cases, K = 1–3); K = 1 equal to the frozen Exp. 3 L_greedy (500 cases); the unrounded ranking and ties; an independent RVOL recompute; the pre-entry and fill checks; a destructive future overwrite; determinism.
- `tests/run_exp4_mutants.py`: **23/23 planted defects killed**, all by behaviour, none by a crash.
- Hashes: `out/exp4/precheck/FROZEN_SHA256.txt`.
