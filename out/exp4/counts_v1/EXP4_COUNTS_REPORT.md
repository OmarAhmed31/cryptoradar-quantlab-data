# Experiment 4: counts run report (Development only; ONE run; NO return, NO outcome)

**The run:**
- Code frozen at `a342099`. The pre-run hash check passed 8/8 (`PRE_RUN_HASH_CHECK.txt`, commit `92f357b`).
- Outputs committed **before** they were read (commit `3a81793`).
- **RD4 PASS:** three byte-identical runs: the repository run, a run with 489 outcome files corrupted (including all 20 attribution files), and an isolated run with no network. sha256 `270fdc68…2ac4`.

## Result: STOP_INFEASIBLE

**No design reaches L_greedy(K) ≥ 100.** By the frozen rule, **Experiment 4 stops**, nothing is relaxed, and the reviewer decides.

`L_greedy(K)` is a preliminary estimate under the assumption K ≤ 3 throughout Development. It is not a guarantee, and not a test of U7. Here it does not reach 100 even under that favourable assumption. `L_worst` is not computed (the approved exception).

| | D-D1 (4 cond.) | D-H1 (4 cond.) | D-H2 (5 cond.) |
|---|---|---|---|
| signals (frozen Exp. 3 cascade) | 119 | 1,195 | 473 |
| PAST_ENTRY_CUT | 6 | 134 | 48 |
| BLOCKED_COIN_HELD / BLOCKED_REENTRY_WINDOW | 0 / 0 | 10 / 4 | 4 / 0 |
| **SKIPPED_NO_CASH** | **51** | **883** | **348** |
| SKIPPED_NO_SLOT | 28 | 102 | 23 |
| SKIPPED_RANK | 2 | 11 | 4 |
| NOT_EXECUTED / wide stop at the fill | 0 / 0 | 0 / 0 | 0 / 0 |
| **opened** | 32 | 51 | 46 |
| **L_greedy(K = 3)** | **32** | **51** | **46** |
| Exp. 3 single position (L_greedy), for reference | 19 | 43 | 38 |
| batches | 56 | 659 | 265 |
| batches of size 1 | 32 (57%) | 512 (78%) | 222 (84%) |
| open positions after an entry: 1 / 2 / 3 | 19 / 8 / 5 | 43 / 5 / 3 | 38 / 5 / 3 |
| trade-window reason of the opened trades | all TIME_EXIT | all TIME_EXIT | all TIME_EXIT |

**Composition of the opened trades:**
- **D-H1:** 46 coins, at most 2 per coin. By state: BEAR 17, BULL 15, SIDEWAYS 19 (High-Vol included).
- **D-D1:** 32 coins, 1 each. By state: BULL 17, SIDEWAYS 14, BEAR 1.
- Full splits are in `exp4_counts.json`.

## What the counts show

**1. The owner's policy rarely runs positions in parallel.**
- Most batches hold **one** signal: 78% for D-H1 and 57% for D-D1.
- By the owner's rule, a lone signal takes **all** the available cash, so the next signals find no cash. **`SKIPPED_NO_CASH` is the largest reason by far** (D-H1: 883 of 1,195 signals).
- After an entry, a second or third position was open only 8 times in D-H1, and 13 times in D-D1.

This was the consequence stated in spec v0.5 §1.1. **It is a faithful result about the policy, not a defect.**

**2. Three positions add few trades compared with the single position:** +13 for D-D1, +8 for D-H1, +8 for D-H2.
- The ceiling of about 207–246 (spec v0.5 §4) is far away, because the parallel capacity is used only when signals coincide in the same hour.

**3. So, under the owner's actual capital style (spec v0.5), the strategy does not reach 100 completed trades on Development.** This holds even under the favourable stage-1 assumption that K stays at 3.

**What this does NOT mean:**
- No return was computed, so nothing is known about profit or loss.
- The counts do not show that the breakout designs lack an edge.

## For the reviewer and the owner (no proposal to relax anything)

Experiments 3 and 4 together show that the binding constraint is the combination of:
- the U7 requirement (100 completed trades);
- the Development segment's length (entries from 2024-01-01 to 2025-08-02);
- the 7-day hold;
- a capital policy in which one opportunity takes all the cash.

Within that framework, **neither single positions nor the owner's 3-position policy reaches 100.**

Any next step changes the research framework itself, not this experiment. It is a decision for the reviewer and the owner, and it must be pre-registered:
- the trade-count requirement;
- which segments count toward U7;
- the hold rule (D7 is already recorded);
- or whether this breakout family should be closed.

**Unchanged:** the thresholds, the designs, spec v0.5, Protocol v1.2. The Final Holdout is sealed. P1 is not approved.
