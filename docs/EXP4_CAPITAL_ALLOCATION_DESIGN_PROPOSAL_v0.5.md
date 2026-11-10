# Experiment 4: capital-allocation design proposal v0.5 (DESIGN ONLY: no code, no run, no counts, no returns)

**v0.5 = v0.4** (sha256 `55647db3…be0f96`) **+ two clarifications required by the reviewer.** Both are written exactly as he proposed. **Nothing else changed.**
- **(1) The decision snapshot** (§1.3, new step 0): the portfolio decision at h uses a fixed snapshot. Cash or a slot freed after h does not reshape the current batch.
- **(2) The ranking, fully deterministic** (§2.1): the higher RVOL first; at an exact tie, the coin name ascending; the unrounded value; hourly never compared with daily.

**v0.4 = v0.3 + the ranking-timing fix** (below).

**v0.4 = v0.3** (sha256 `7f60fc45…d2ec`) **+ one required fix: the timing of the ranking (§2).** The reviewer's option 1 is adopted:
- **the ranking is RVOL, then the coin name.** The stop distance at the fill is **removed** from the ranking;
- so **the ranking is fully known at the decision time**, the start of the entry hour h, when the signal bar has closed.

**One consequential change, needed for the same reason** (§1.3 step 1 and new step 7), declared openly:
- v0.3 formed the batch **after** two checks that are known only at the fill: NOT_EXECUTED (whether a traded minute exists in the entry hour) and the wide stop at the fill (A3).
- Ranking and allocation must not use them either, so in v0.4 **the decision at h uses only the information known at h**.
- Those two checks are applied afterwards, per selected position, at its own fill. **A failed check leaves its cash share in cash. No replacement is made within the hour.**
- No rule of the strategy changes: the entry rule, the A3 formula, the thresholds and the skips are all the same. **Only the moment at which the portfolio decision is taken is made explicit.**

Nothing else changed.

**v0.3 = v0.2 + the reviewer's portfolio points 1–5** (below).

**v0.3 = v0.2** (sha256 `e26d52ce…48e6`) **+ the reviewer's required points 1–5** (review of v0.40). They are written into **§1.3, the portfolio rules**, and into §2.2 and §7. Nothing else changed: the designs, the thresholds, the owner's answers, scenario A and the 7-day exit.

| Reviewer point | Where |
|---|---|
| 1. **At most 3 open positions for the whole portfolio**, not per batch; free slots after an exit | §1.3 steps 3–5, examples E2–E4 |
| 2. Equity < $2,000 with several signals in one hour → **the best 1** | §1.3 step 4, example E5 |
| 3. **L_greedy(K) ≥ 100 in the counts stage is a preliminary estimate under K ≤ 3**, not proof of U7 | §7 (selection rule and result record) |
| 4. Equity falls below $2,000 with positions open: **no close, no resize; no new entry until the open positions are under the limit** | §1.3 step 2, example E6 |
| 5. **RVOL is compared within one design only**, using the signal's own RVOL definition; hourly is never compared with daily | §2.2 |

**v0.2 = v0.1 + the owner's answers** (below).

**v0.2 = v0.1** (sha256 `d6b71903…d568`) **+ the owner's answers to O1–O3** (2026-11-10), recorded below. Nothing else changed.

| # | The owner's answer | Effect on the design |
|---|---|---|
| **O1** | the opportunities appear **in the same hour** | **Reading R1 is confirmed** (batch = same entry hour). R2 and R3 are dropped |
| **O2** | "I never exit except at the stop loss or at the take-profit" | **Scenario A is confirmed** (no replacement). **Scenario B is dropped.** See also the new point D7 |
| **O3** | the $2,000 is **my capital whether I am in a trade or not** | equity = cash + open positions. **Valuation at the last closed hourly close** (the account's current value, known at the decision time) is taken as the meaning. The owner should object if he means cost |

**A new point raised by O2, for the reviewer (D7):**
- The owner's real trading has **no time exit**: positions end only at the stop or at the target.
- The strategy's **7-day time exit** (Spec §7, `CONV`) is therefore **not** part of the owner's actual style. It is also the main reason each position blocks capital for at least 7 days.
- **Nothing is changed here.** The 7-day exit belongs to the frozen strategy, and removing it would change the strategy itself (holds become longer, up to Protocol H_max = 720 h).
- It is recorded so the reviewer can decide whether a separate, pre-registered variant without the time exit (bounded by H_max) belongs in a later experiment. **It is not a means to reach 100 trades:** without the time exit, holds get longer, so capacity would fall, not rise.

**Context:**
- Experiment 3 is CLOSED as STOP_INFEASIBLE. Under one position for the whole portfolio and a hold of ≥ 7 days, Development can hold at most about 69–82 trades, so U7 (≥ 100 completed trades) was impossible by construction.
- The system owner has now stated how he actually allocates capital (§1).
- This document proposes **how to test that policy faithfully**. **It is not a way to raise the trade count.**
- Protocol v1.2 is FIXED. The Final Holdout is sealed. P1 is not approved.

**Fixed and NOT reopened:**
- the three designs D-H1, D-H2 and D-D1, and every one of their conditions;
- the frozen hourly thresholds (`thresholds.json` sha256 `5dc38aa9…8c5f`);
- the daily derivation method;
- the execution, cost, H_max, U9b and re-entry rules (Spec v0.1.3; Exp. 3 addendum v0.3).

**A disclosure:** Experiment 3's opportunity counts are already known: D-H1 1,195 signals, L_greedy 43; D-H2 473 and 38; D-D1 119 and 19. No return is known. This proposal uses those counts only to state the problem. It **does not** use them to pick a design, a threshold or a parameter.

## 1. The owner's capital policy (as stated)

| Equity at decision time | Rule |
|---|---|
| **< $2,000** | **one position**, using all available capital |
| **≥ $2,000** | split equally among the selected opportunities: **1 opportunity → all capital; 2 → half each; 3 or more → the best 3 only, one third each** |
| always | **no extra position just because cash is available** |

### 1.1 What the rule says literally, and its consequence (confirmed by the owner: R1)

The rule allocates capital **among the opportunities that appear together**. Read literally:

- **The batch** is the executable signals that share **the same entry hour**. That is the only moment at which several opportunities "appear" together under the Spec entry rule (§5.5: the first traded minute in [t+1h, t+2h)).
- **Each batch** receives **all available cash**, split as in §1.
- **A later signal**, while that cash is invested, finds **no cash**, so it is **skipped and logged** (`NO_CASH`). It cannot take a slot just because a slot is "free".
- **When a position exits**, its cash returns, and the next batch gets the available cash.

**Consequence:** if signals rarely share an entry hour, the policy behaves almost like the single position of Experiment 3. That is a faithful result about the owner's style, **not a defect to be engineered away**.

How often signals share an entry hour has **not been measured**. It would be measured in the counts stage (§7).

**The owner must confirm which reading matches his real trading.** Three readings are possible, and **only (R1) is the literal statement:**

| Reading | Meaning | Change vs. the statement |
|---|---|---|
| **R1: literal, batch = same entry hour** | as above | none |
| R2: a daily decision batch | collect a whole day's signals, then allocate once at a fixed time | changes **entry timing**, so it would need a new pre-registered entry rule |
| R3: fixed slots, each 1/3 of equity | a lone signal gets only 1/3 | **contradicts** "1 opportunity → all capital" |

**The owner confirmed R1** (O1, v0.2).

### 1.2 Equity and the $2,000 switch

- **Equity at a decision** = cash + open positions valued at their **last closed hourly close before the decision**. That price is known at the decision time, so no future data is used.
- The number of positions allowed (K = 1 or K ≤ 3) is taken **at each batch** from that equity. A position already open is never resized.
- **Capital paths:**
  - **$10,000**, the primary path for U7 (K ≤ 3 while equity ≥ $2,000);
  - **$1,000**, **K = 1 always** while equity < $2,000.

  The $1,000 path is **single-position again**, so **U7 is infeasible on it by construction** (§4). It is reported as descriptive only.

### 1.3 Portfolio rules (fixed; applied at every entry hour, for one design at a time)

**The decision time is the start of the entry hour h.** At h, the signal bar has closed, so its values, and the RVOL used for ranking, are known. The fill is not known yet.

0. **The snapshot (v0.5).** The decision at h uses a **fixed snapshot taken at h**:
   - the open positions;
   - the available cash;
   - the equity E, valued at the last closed hourly close before h;
   - the batch.

   **An exit counts in the snapshot only if its exit time is strictly before h.** Any position that exits, or any cash that returns, **at or after h** does **not** reshape the current batch, its selection or its cash shares. That cash and that slot become available **at the next entry hour that has a batch**. So no decision is re-taken after seeing later events.

   **Example E9:** 2 positions open, 1 slot free. At h, the batch is 1 signal and takes the available cash. At h + 20 min, one of the old positions exits. **Its cash is not added to this batch.** It waits for the next entry hour with a batch.

At each entry hour h that has a **batch** = the design's signals with that entry hour that pass **every check known at h**:
- the signal conditions;
- P1 eligibility;
- the half-spread estimable from days d-30 … d-1;
- the re-entry window;
- the coin not already held.

**Not yet applied** are the two checks known only at the fill: NOT_EXECUTED and the A3 wide stop at the fill. They are applied in step 7.

1. **Equity** E = cash + open positions valued at the last closed hourly close before h (§1.2).
2. **The position limit: K = 1 if E < $2,000; K = 3 if E ≥ $2,000.** K is a limit on **all open positions in the portfolio**.
   - **Open positions are never closed, resized or rebalanced** because E crossed $2,000 in either direction.
   - If the number already open is ≥ K, the batch is skipped: `SKIPPED_NO_SLOT`.
3. **Free slots:** s = K − (open positions).
4. **Selection:** take **n = min(s, batch size)** signals, the best by the ranking of §2.
   - With **E < $2,000**, K = 1, so **only the best 1** can be taken, and only if nothing is open.
   - The signals not taken are `SKIPPED_RANK`.
5. **Cash:** the **available cash** (cash not in open positions) is split **equally among the n selected signals**.
   - **If the available cash is 0** (for example, a lone earlier signal took all of it), the batch is `SKIPPED_NO_CASH`, **even when slots are free**. This is the owner's rule: no extra position just because a slot exists.
   - Cash returns only when a position exits. **A position that is already open is never sold to fund a new one** (scenario A).
6. **A coin already held cannot be opened again** (Spec §5.5). The re-entry window rule applies after its exit.
7. **Execution, per selected signal, at its own fill** (Spec §5.5: the first traded 1-minute candle in [h, h+1h)):
   - no traded minute → `NOT_EXECUTED`;
   - (fill − stop)/fill > the frozen limit → `SKIPPED_WIDE_STOP_AT_ENTRY` (A3, unchanged).

   **In either case, that signal's cash share stays in cash.** It is **not** given to a lower-ranked signal of the same batch, because that would use fill information in the selection. It is available to the next batch.

**Logged reasons, in this order:**
- at h: `SKIPPED_NO_SLOT` → `SKIPPED_NO_CASH` → `SKIPPED_RANK`;
- at the fill: `NOT_EXECUTED` / `SKIPPED_WIDE_STOP_AT_ENTRY`.

**Example E8:** E ≥ $2,000, nothing open, 2 signals at h. Each is given half the cash. One has no traded minute in [h, h+1h), so it is `NOT_EXECUTED`. **Its half stays in cash**, and the other position runs with half the equity.

**Examples (E ≥ $2,000 unless stated):**

| # | State before hour h | Batch at h | Result |
|---|---|---|---|
| E1 | nothing open, all cash | 1 signal | it takes **all** the cash |
| E2 | 3 open; one exits, so its cash is free; 2 still open | 3 signals | s = 1, so the **best 1** takes the freed cash |
| E3 | 2 open (half each); one exits, so half the equity is in cash | 3 signals | s = 2, so the **best 2** take a quarter of the equity each. Total open = 3 |
| E4 | 1 open with all the cash | 2 signals | s = 2, but cash = 0, so `SKIPPED_NO_CASH` (both) |
| E5 | E = $1,500, nothing open | 3 signals | K = 1, so the **best 1** takes all the cash, and 2 are `SKIPPED_RANK` |
| E6 | 3 open; E falls to $1,800 | any | K = 1 and open = 3 ≥ 1, so `SKIPPED_NO_SLOT`. No position is closed or resized. A new entry is possible only once **all 3 have exited** (open = 0 < K = 1) |
| E7 | 1 open (all cash); E rises above $2,000 | 1 signal | K = 3 and s = 2, but cash = 0, so `SKIPPED_NO_CASH` |

**The counts stage can follow these rules without prices,** given an assumed K:
- whether cash is 0 depends only on events: cash becomes 0 after a batch is fully filled; it stays positive for the share of any selected signal that fails at its fill (step 7), and it becomes positive after an exit;
- the slot count is the number of open positions.

Only E, and so K, needs prices. That is why stage 1 assumes K = 3 (§7).

## 2. Choosing the best 3: the ranking

### 2.1 The criterion (no new score is invented)

The proposal uses **the strategy's own confirmation variable**, the relative volume of the breakout bar, which the designs already rank:
- **RVOL** for D-H1 and D-H2;
- **RVOL_d** for D-D1.

**Why RVOL:**
- It is the only "strength" measure that all three designs share.
- Its frozen threshold E3 was derived as "the strongest quarter of breakouts by volume" (plan v0.3.2). Ranking by it is consistent with how the strategy defines strength.
- CLV exists only in D-H2. Stop distance is a **risk** measure, not a strength measure.

**Tie-breaker (v0.4):** **the coin name**, alphabetically. This is deterministic and known at h.

**The ranking rule, written completely (v0.5):**
1. Sort the batch by **RVOL, from high to low**.
2. **On an exact tie** (equal values), sort by **the coin name, ascending** (the series name, e.g. `ABC-USDT` before `ABD-USDT`, compared character by character).
3. **The unrounded value is used:** the same float the signal condition tested. It is never rounded or binned.
4. **Hourly RVOL is never compared with daily RVOL.** A batch belongs to one design only.
5. **RVOL is always defined for a signal,** because every signal passed its RVOL condition (E3 or RVOL_d). No missing value can occur.

**Removed in v0.4:**
- the stop distance at the fill as a tie-breaker. **The fill is not known at the decision time**, and the fill minute can differ between coins;
- the "risk first" alternative, for the same reason.

The ranking is now **RVOL, then the coin name**, and both are known when the signal bar closes.

### 2.2 No future data

- The rank of a signal uses only **its own signal bar's RVOL and its coin name**. Both are known at t+1h, the start of the entry hour (for D-D1, at D+1 00:00). **No fill price is used in the ranking** (v0.4).
- **The rank is fixed when the signal appears. It is never recomputed later.**
- **Ranking happens only inside one batch** (the same entry hour). Signals from different hours are never compared in scenario A, so a later signal can never displace an earlier allocation.
- **Within one design only.** Every experiment run uses one design, so a batch never mixes designs.
  - The ranking value is **exactly the RVOL of that design's own signal definition**: RVOL = vol_quote_t / the median of the prior 168 hourly vol_quote for D-H1 and D-H2 (the E3 variable); RVOL_d = vol_D / the median of the prior 20 traded days for D-D1 (the RVOL_d condition).
  - **Hourly RVOL is never compared with daily RVOL.**
  - The tie-breaker is the coin name (v0.4). The stop level, R_low for the hourly designs and RL_D for D-D1, is used only by the A3 check at the fill, never in the ranking.

## 3. Open positions: scenario A against scenario B

| | **A: no replacement (recommended primary)** | **B: replace the weakest open position** |
|---|---|---|
| **The rule** | an open position runs to its own exit (stop, target, 7-day time exit, delisting) | when a new batch has no cash: if the new signal's rank > the **weakest open position's rank at its entry**, sell that position at the first traded minute of the new entry hour (the same fill rule), then buy the new one with the cash |
| **New parameters** | none | the comparison rule (proposed: **strictly higher RVOL**, nothing more), and whether a minimum hold applies (**proposed: none**, so that no number is invented) |
| **Weakness** | it may miss a stronger signal while invested | it compares a **stale** entry score with a fresh one. The strategy has no measure of an open position's *current* strength, and creating one would be a new, unvalidated score |
| **Costs** | as in the Spec | **two extra crossings** per replacement: exit fee + half-spread + slippage, then entry fee + half-spread + slippage |
| **Effect on U7** | trades complete naturally | **every replacement creates a completed trade.** Churn inflates the count without testing the strategy's exits. Replacement exits must be **reported separately** and **must not be counted toward U7** (proposal) |
| **Effect on risk** | the risk is set at entry | turnover is higher, and the exposure to recent breakouts is higher |

**The owner confirmed A** (O2, v0.2): positions are never replaced. **B is dropped** from Experiment 4. The comparison above stays only as the record of why.

## 4. Trade-count capacity and U7 (arithmetic only)

**Capacity ceiling, without data:**
- With **at most K open positions**, each held at least 7 days + 2–3 hours, Development holds at most about **K × 82** trades (K × 69 from April 2024, when A1 first allows signals).
- That gives **K = 1 → 69–82** and **K = 3 → 207–246**.

**This is only a ceiling.** Under the literal reading R1, positions run in parallel **only when signals share an entry hour**. A lone signal takes all the cash, so the real number lies between the single-position count and the ceiling.

**U7 is therefore decided by an empirical quantity:** how often executable signals share an entry hour while cash is free. It is unknown, and it is measured once, in the counts stage (§7).

**The $1,000 path is single-position**, so U7 is **infeasible there by construction**. **Proposal: U7 is assessed on the $10,000 path only.**

## 5. Risk, costs and exposure (defined now; computed only in P1)

**Equal capital does not mean equal risk.** The defined measures:

| Quantity | Definition |
|---|---|
| **allocated capital** a_i | the cash given to position i at entry |
| **capital at risk at the stop** r_i | a_i × (P_fill − stop)/P_fill **+** the exit costs at the stop (fee + half-spread + slippage), with a gap risk stated separately (a gap fill below the stop, Spec §6) |
| **portfolio open risk** | Σ r_i over the open positions, as a % of equity, logged at each decision |
| **cash / invested** | cash, the number of open positions, the share of equity invested |
| **exposure** | the distinct coins held; positions opened in the **same batch** (one market move, so highly correlated); the market state at entry |

**The size of the issue, from the frozen limits (no data computed):**
- A full-capital position may be up to **34.07%** from its stop on the hourly designs (E5), and up to **52.71%** on D-D1 (its derived P90).
- So **one stopped trade can cost about a third, or about half, of the equity**, before costs and gaps.
- With 3 positions of one third each, the portfolio open risk is the **average** of the three stop distances. Because breakouts in one batch tend to come from the same market move, the three stops are **not** independent.

**Proposal:**
- All risk measures are **reported**.
- **No risk cap is added** in this experiment. A cap would be a new rule needing its own evidence, and the owner's policy is equal capital.
- Whether to add a portfolio risk limit is listed as an open decision (§8), to be decided from evidence, not from an invented number.

**Costs:** unchanged (0.10% taker, Corwin–Schultz half-spread, slippage, U9b).
- More positions mean more crossings, but each crossing is smaller.
- The DV30 cap (1% of DV30_med per position) applies to each position separately.

## 6. Protocol v1.2 and the Final Holdout

- Development only, for the counts stage and for any later P1 development. Validation is used once, only after a frozen P1 passes on Development.
- **The Final Holdout stays sealed.** Experiment 4 counts toward the proposed Holdout budget of at most 3 frozen candidates (Spec §16; P-5 still open).
- Experiment 4 is a new row in the registry. It does not reopen Experiment 3.

## 7. Pre-registered test plan

| Stage | What | Allowed outputs | Gate |
|---|---|---|---|
| **0** | this proposal, then a frozen specification | — | reviewer and owner approve §8 |
| **1: counts** | the designs D-H1, D-H2 and D-D1 under the frozen policy (R1 + scenario A) on Development, **$10,000 path with K ≤ 3** | the number of batches, the batch-size distribution (1 / 2 / ≥ 3), NO_CASH skips, positions in parallel, **L_greedy(K)** with the same sequential-blocking estimate as Exp. 3, L_worst reported. **No price after the entry, no return** | the code and tests are reviewed first; one run; RD4; outputs committed before they are read |
| **1-rule** | the selection is fixed now: **L_greedy(K) ≥ 100**, then the fewest entry conditions, and D-D1 wins the tie with D-H1; **otherwise STOP**, with nothing relaxed. **L_greedy(K) ≥ 100 is a preliminary estimate under the assumption K ≤ 3 throughout Development. It is NOT proof that U7 will hold in P1.** In P1, equity may fall below $2,000 and K may drop to 1, so fewer trades are possible. The stage-1 result record must say this in these words. **U7 itself is decided only by the completed trades of the frozen P1 run on the $10,000 path** | — | — |
| **2: P1 spec** | a full P1 specification of the chosen design under the policy (costs, risk logging, both capital paths) | — | reviewer |
| **3: P1 Development** | the frozen P1 run on Development | returns, risk measures, U7 on the $10,000 path | pre-registered criteria |
| **4: Validation** | once, unchanged | — | — |

**Equity in stage 1:** it cannot be known without returns, so stage 1 assumes **K ≤ 3 throughout** on the $10,000 path. In P1, K drops to 1 if equity falls below $2,000 (an 80% drawdown). This is disclosed: the stage-1 count is an estimate under that assumption.

## 8. Open decisions

**For the owner:** O1–O3 are answered (v0.2, top of this document): **R1, scenario A, and equity at the current value.**

**For the reviewer:**

| # | Decision |
|---|---|
| D1 | The ranking criterion: **RVOL, then the coin name** (v0.4, the reviewer's option 1) |
| D2 | ~~Scenario B~~: dropped by the owner (O2) |
| D3 | U7 is assessed on the **$10,000 path only**, since the $1,000 path is single-position by the owner's rule |
| D4 | Risk is reported only, with no portfolio risk cap in this experiment (proposed) |
| D5 | Stage 1 reuses the frozen Exp. 3 counting code, extended to K positions, under a new frozen plan with its own tests and RD4 |
| D6 | Whether Experiment 4 counts as a new candidate toward the Holdout budget (P-5) |
| **D7** | The owner never uses a time exit. Keep the strategy's 7-day time exit in Experiment 4 unchanged (proposed), and decide separately whether a later pre-registered variant without it (bounded by H_max) is worth testing |

**Nothing is implemented until these are approved and the specification is frozen.**
