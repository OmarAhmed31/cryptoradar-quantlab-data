# Experiment 3: counts run report (Development only; ONE run; NO return, NO outcome)

**The run:**
- Code frozen at commit `1f91f8b`. The pre-run hash check passed (`PRE_RUN_HASH_CHECK.txt`).
- Outputs committed **before** they were read (commit `a5eefd5`).
- **RD4 PASS:** three byte-identical runs: the repository run, a run with 489 outcome files corrupted (including all 20 attribution files), and an isolated run with no network. sha256 `b951c878…884f`.

## Result: STOP_INFEASIBLE

No design reaches L_greedy ≥ 100. By the fixed rule, **Experiment 3 stops**, nothing is relaxed, and the reviewer decides.

| | D-D1 (4 cond.) | D-H1 (4 cond.) | D-H2 (5 cond.) |
|---|---|---|---|
| eligible bars | 137,762 days | 3,345,081 h | 3,345,081 h |
| breakout | 5,483 | 38,874 | 38,874 |
| + A1 tight | 1,575 | 10,466 | 10,466 |
| + RVOL | 263 | 1,962 | 1,962 |
| + stop | 254 | 1,951 | 1,951 |
| + E4 CLV | — | — | 758 |
| + not Transition (**signals**) | **119** | **1,195** | **473** |
| PAST_ENTRY_CUT | 6 | 134 | 48 |
| NOT_EXECUTED / no half-spread / wide stop at entry | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| executable | 113 | 1,061 | 425 |
| blocked by the open trade | 94 | 1,018 | 387 |
| blocked by same-coin re-entry | 0 | 0 | 0 |
| **L_greedy** (estimate, not a guarantee) | **19** | **43** | **38** |
| L_worst (reported only) | 13 | 43 | 38 |
| trade-window reasons | all TIME_EXIT | all TIME_EXIT | all TIME_EXIT |

**Daily derived thresholds** (D-D1 breakout population, n = 5,483, before any filter):
- RVOL_d P75 = 4.7237. It keeps 25.00% of the population.
- stop_d P90 = 0.5271. It keeps 89.99%.

**Composition:**
- D-H1 signals come from **284 coins**, at most 14 per coin. They spread over every month except 2025-06 (1 signal).
- By state, D-H1 has 512 SIDEWAYS, 339 BULL and 306 BEAR signals (High-Vol included).
- The 43 trades taken by greedy come from 38 coins. Full splits are in `exp3_counts.json`.

## The main finding: 100 trades were arithmetically impossible on Development under these P1 rules

**The signals were not the limit.** D-H1 has 1,061 executable signals, but 1,018 of them are blocked by the one open position. The constraint that binds is **one position for the whole portfolio combined with a hold of at least 7 days**.

**The arithmetic needs no data:**
- The Development entry window is 2024-01-01 → 2025-08-02, i.e. 579 days.
- Each trade blocks at least 7 days + 3 hours (hourly) or 7 days + 2 hours (daily).
- So **at most 82 trades** fit, even with a signal right after every exit.
- A1 needs 90 days of history, so the first signals come around April 2024. That lowers the ceiling to **about 69**.

**So no design under Scenario A1 (single position) with a 7-day time exit can ever reach L ≥ 100 on Development.** That holds whatever its thresholds are.

The developer (me) should have checked this ceiling at the plan stage. It was missed in plans v0.1–v0.3, and it is recorded here.

**What this does NOT mean:**
- **No return was computed**, so nothing is known about profit or loss.
- The counts do not show that a breakout edge is absent.

**Decisions for the reviewer (not proposed as relaxations):** U7 (≥ 100 completed P1 trades on Development) cannot be met by any single-position strategy with a hold of ≥ 7 days on this segment. Any next step changes the framework itself, not this experiment's thresholds:
- the trade-count requirement;
- the scenario (positions);
- the hold length;
- the segments used for U7.

That choice belongs to the reviewer and must be pre-registered as a new experiment.

**Unchanged:** the thresholds, the designs, Protocol v1.2. The Final Holdout is sealed. P1 is not approved.
