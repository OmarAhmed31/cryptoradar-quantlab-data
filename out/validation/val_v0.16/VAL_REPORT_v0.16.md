# Validation: replication of the 41 FD-2 hypotheses (v0.16, 2026-11-09; ONE SHOT)

## Governance

- **Rules applied:** Validation Plan v0.1.1 (APPROVED; sha256 `ede74d6c…0440`) under Protocol v1.2 FIXED. The family was frozen as `validation_family.json` (sha256 `ff2df7b9…4250`; 41 hypotheses, direction fixed from FD-2).
- **Order of work, each step committed before the next:**

  | Step | Commit |
  |---|---|
  | Plan and family | `f0d25e1` |
  | Code, tests and mutants, before any Validation data was read | `201e285` |
  | Pack built with stop condition 1 enforced in code (ledger to 2026-10-03; 32/32 forced exits in the window PRICED, maximum gap 23 min) | `aa45910` |
  | Mutants killed **14/14** | `e808056` |
  | Tests **full 8/8, fast 8/8** | `38f680a` |
  | **One run**, output committed before it was read | `84af862` |

- **Data:** entries 2025-09-08 → 2026-03-01, 175 days.
  - No entry falls in the embargo. H3 purge = **0**.
  - Lookback uses Development and embargo history (H5).
  - Nothing closes after 2026-04-01. The Holdout is untouched.
- **The FD code is byte-identical** to its accepted commits (VA0). Every one of the 3,688,909 FD-1 Development feature values is reproduced exactly (VA3).
- **Not computed:** no MI or regime analysis (refused on Validation by v1.2), no trades, P&L or costs. **An IC is a rank correlation, not a return.**
- **Outcomes, P1:** 39,974 eligible entries. Delisting forced exits: 13 (h = 1), 97 (h = 7), **423 (h = 30)**. 0 unpriceable.

## Result (P1 decides; one-sided in the FD-2 direction; BH q = 0.10 over 41; BY sensitivity)

| Label | Count |
|---|---|
| `REPLICATED` | **35** |
| `REPLICATED — BH_ONLY — FAILS_BY_SENSITIVITY` | 1 (F02 ret_7 × 1) |
| `NOT_REPLICATED` | 2 (F03 ret_30 × 1, F05 × 1) |
| `REVERSED` | 3 (F16 thr30 × 1, F01 ret_1 × 7, F03 ret_30 × 7) |

**36 of 41 hypotheses kept their direction significantly out of sample.**
- For every replicated hypothesis, the S50k and S250k signs agree with P1. For the 3 reversed ones, they also reverse.

### By FD-1 cluster (a summary of the members, not a separate test)

| Cluster | n | Label | Median Validation IC | Development IC range |
|---|---|---|---|---|
| **Volatility block** (F06, F07, F09, F11, F14, F22) | 18 | **REPLICATED 18/18** | −0.17 | −0.09 to −0.20 |
| F10 skew_30 | 3 | REPLICATED 3/3 | −0.10 | −0.06 to −0.08 |
| F20 dist_high_30 | 3 | REPLICATED 3/3 | +0.10 | +0.03 to +0.10 |
| F21 dist_low_30 | 3 | REPLICATED 3/3 | −0.09 | −0.07 to −0.09 |
| F13 corr_btc_30 | 3 | REPLICATED 3/3, **weaker**: ratio 0.46–0.78. At h = 30 the bootstrap CI touches 0 (−0.0002) | +0.07 | +0.08 to +0.15 |
| Liquidity (F18 Amihud, F19) | 3 | REPLICATED 3/3. F19 × 1 passes BY at 0.055 | −0.03 | −0.01 to −0.02 |
| F08 vol ratio, F17 volume ratio | 1 + 1 | REPLICATED | −0.03 | −0.02 |
| F02 ret_7 (h = 1) | 1 | REPLICATED, BH only | −0.03 | −0.05 |
| **Short-term reversal** F03 + F05 | 3 | **NOT_REPLICATED** (0 replicated, 1 reversed) | −0.006 | −0.03 |
| F01 ret_1 (h = 7) | 1 | **REVERSED** (+0.002, ≈ 0) | | −0.03 |
| F16 thr30 | 1 | **REVERSED** (−0.011). This was the FD-1 quality flag; the outcome was anticipated as a plausible explanation | | +0.009 |

**Magnitude.** For the volatility block the Validation IC was **larger** than in Development: ratio 1.07–1.39. h = 30 ICs were about −0.25. F20 and F18 were also larger. F13 was smaller.

**Descriptive only.** Of the 25 cells outside the family (23 FD-2 non-candidates and 2 exploratory), 15 had the same sign as in Development.

## How to read this, and its limits

1. **What replicated:**
   - "Higher volatility, skew, or large hourly spikes rank lower later."
   - "Near the 30-day high, or far from the 30-day low, ranks higher or lower in the FD-2 direction."
   - "More correlated with BTC ranks higher" (weaker).

   **What did not replicate:** short-term price reversal (ret_1 / ret_30 / beta-adjusted), and thr30.
2. **Both periods may share one market phase.**
   - Development (2024-01 → 2025-08) was a period in which the median altcoin lagged BTC (MI v0.11).
   - Validation (2025-09 → 2026-03) is a different time, but this run does **not** measure whether it was a different phase. MI on Validation is refused by Protocol v1.2.
   - So replication here shows persistence across time, **not** independence from the market phase. The Holdout (2026-04 → 2026-10) is sealed and is not part of this step.
3. **These are rank associations, not profit.** No cost, slippage, capacity or position sizing is included. A rank IC of −0.25 says nothing yet about whether any rule built on it makes money after costs.
4. **Dependence.** The 36 replicated hypotheses are not 36 independent confirmations. Twelve clusters exist, and 18 of the 36 are one volatility block.
5. **Mutant note:** W06, W07, W08 and W14, the defects in shared FD code, were killed. W08 (forced exit a day late) was killed **only** by the frozen-code hash check (VA0), not by a behavioural test. The behavioural tests did not cover that branch in the Validation sample.

## Files

| File | Contents |
|---|---|
| `val_results_41.csv` | All 41 hypotheses: Development and Validation IC, Newey-West t, one-sided p, BH/BY, CIs, S50k/S250k, ratio, label |
| `val_cluster_summary.csv` | The cluster summary |
| `val_descriptive_other_cells.csv` | The 25 cells outside the family |
| `val_outcome_counts.csv` | Outcome and forced-exit counts |
| `val_ic_daily.csv.gz` | Daily ICs |
| `val_meta.json` | Run metadata |
| `val_test_result_*.json`, `val_mutation_results.json` | Test and mutant results |

## Next (reviewer)

1. Review of the Validation result.
2. Any next stage (for example a strategy plan that uses only replicated clusters, with costs) needs **its own approved plan**, written before any further data is used. The Final Holdout stays sealed (H7). Opening it requires Protocol v1.3 with an external signature.
