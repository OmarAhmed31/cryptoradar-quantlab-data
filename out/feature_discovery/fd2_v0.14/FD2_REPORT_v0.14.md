# Feature Discovery FD-2: forward association, Development only (v0.14, 2026-11-09)

## Governance

- **Rules applied:** plan v0.1.1 §4, FD-2 Decision Record v2 (D4, D5, D6; sha256 `56c4dcef…2521`), the FD-1 Review Record, and Protocol v1.2 FIXED.
- **FD-2 was opened by the reviewer** on 2026-11-09.
- **Committed before any FD-2 result was produced:** the code, the tests and dev_pack_v2 (commit `d6a03af`). Two test fixes followed, also before any result was viewed:
  - T8 now checks the adjusted values, because mutant N02 had survived;
  - T12 adds a synthetic candidate-rule table, because N09 and N10 had survived.

  Then the mutants were killed 13/13 (`d39f550`). Only after that were the results computed.
- **Development only.** Entries run 2024-01-01 → 2025-08-01 (t < 2025-08-02, H2), so every outcome ends by 2025-08-31.
  - H3 purge count = **0**.
  - Validation and Holdout were not used.
- **Not computed:** trades, P&L, costs, quantile or portfolio returns.
- **An IC is a rank correlation, not a return.**

## Inputs and outcomes

- **dev_pack_v2** = dev_pack_v1 (unchanged) + `forced_exit_dev.csv`.
  - It holds 106 rows with the cut inside Development, all PRICED (≤ 60 minutes).
  - Source: `forced_exit_reference.csv`, sha256 `67221b10…3e59`, the same as the Protocol v1.2 control hash.
- **Outcome counts** (P1 eligible entries, 136,301):

  | h | Normal | Delisting forced exit | No entry price | Unpriceable | Missing exit |
  |---|---|---|---|---|---|
  | 1 | 136,015 | 48 | 238 | 0 | 0 |
  | 7 | 135,743 | 320 | 238 | 0 | 0 |
  | 30 | 134,817 | **1,246** | 238 | 0 | 0 |

  Delisted coins are never dropped.

## Result: 41 of 64 confirmatory tests are candidates (BH, q = 0.10)

- **BH:** 41 of 64 significant. All 41 also meet the stability rule (3/3 sub-periods, same sign in S50k and S250k), so **41 are candidates**.
- **BY sensitivity:** 37 of 64 significant.
  - **4 candidates are `BH_ONLY — FAILS_BY_SENSITIVITY`**: F16 × 1, F19 × 1, F03 × 7, F18 × 7.
- **Exploratory cells (D4)** are outside BH and BY and are never candidates:

  | Cell | Mean IC |
  |---|---|
  | F01 × 1 | −0.035 |
  | F02 × 7 | −0.037 |

### Candidates grouped by FD-1 redundancy cluster (|ρ| ≥ 0.80)

**41 candidates are not 41 independent findings.** They fall in 12 of the 14 clusters, and 18 of them are one volatility block.

| FD-1 cluster | Candidates (h) | Mean IC range | Direction (descriptive, Development only) |
|---|---|---|---|
| **Volatility block**: F06 vol_7, F07 vol_30, F09 downside vol, F11 max hourly return, F14 idio vol, F22 range | 18 (1, 7, 30) | **−0.09 to −0.20** | Higher-volatility coins ranked lower on later returns |
| F13 corr_btc_30 | 3 (1, 7, 30) | **+0.08 to +0.15** | Coins more correlated with BTC ranked higher |
| F21 dist_low_30 | 3 (1, 7, 30) | −0.07 to −0.09 | Coins far above their 30-day low ranked lower |
| F20 dist_high_30 | 3 (1, 7, 30) | +0.03 to +0.10 | Coins near their 30-day high ranked higher |
| F10 skew_30 | 3 (1, 7, 30) | −0.06 to −0.08 | Positive skew ranked lower |
| F03 + F05 (30-day return) | 3 (1, 7) | −0.03 | Short-term reversal |
| F02 ret_7 (h = 1), F01 ret_1 (h = 7) | 2 | −0.05, −0.03 | Short-term reversal |
| F15 + F18 + F19 liquidity block | 3 (1, 7) | −0.01 to −0.02 | Weak |
| F08, F17, F16 | 3 (h = 1 only) | −0.02 to +0.01 | Weak; F16 is BH_ONLY (see the FD-1 flag) |

**Not significant at any horizon:** F04 ret_30_skip7, F12 beta_btc_30, F15 log DV (alone).

**At h = 30, only the volatility block, F10, F13, F20 and F21 remain.** Every return and liquidity feature is not significant at 30 days.

### Robustness

- The P1, S50k and S250k means are close. For example:

  | Cell | P1 | S50k | S250k |
  |---|---|---|---|
  | F07 × 7 | −0.150 | −0.148 | −0.152 |
  | F13 × 7 | +0.114 | +0.109 | +0.119 |

- **Block-bootstrap 95% CIs** exclude 0 for all 41 candidates.
- **Regimes (descriptive only):** the volatility effect is present in S1, S2 and UNKNOWN (F07 × 7: −0.153, −0.156, −0.168). F13 is strongest in S2 (+0.142) and weaker in S1 (+0.054). S3 is `LOW_N`.

## Limits that bind any use of these results

1. **In-sample.** These are Development-only associations. They are hypotheses for later Validation under a future approved protocol step, not signals.
2. **IC is not profit.** It ignores costs, slippage, position sizing and capacity. A rank IC of −0.15 does not translate into any return figure here.
3. **One period, one market phase.** Over Development the median altcoin lagged BTC (MI v0.11). A "low volatility and high BTC correlation ranks higher" pattern is consistent with that phase, and it may not hold in another one.
4. **h = 30 overlaps heavily.** 579 entry days hold only about 19 non-overlapping 30-day windows. Newey-West with lag 29 is approximate there; the block bootstrap with 30-day blocks agrees in sign and exclusion of 0.
5. **Partial FD-1 overlap** (Decision Record v2, D4) applies to the price-feature cells F01 × 7, F02 × 1, F03 × 1/7, F05 × 1, F20 and F21. They stay in the family, as decided, but these cells were not fully unseen.
6. **Dependence.** BH's FDR guarantee is not claimed under the present dependence (D6). BY was reported for this reason.

## Acceptance

| Test | Result |
|---|---|
| `tests/test_fd2.py` | full **16/16**, fast **16/16** |
| T0 | family = the 64 exact cells; exploratory cells outside BH/BY |
| T1 | entry window, H3 = 0 and guard refusals |
| T2 | destructive overwrite after t+h: outcomes unchanged |
| T3 | independent naive recompute of 4,614 outcomes, including all 1,614 eligible forced exits |
| T4 | forced-exit counts match an independent recount |
| T5 | delisted series kept |
| T6 | IC = scipy Spearman |
| T7 | Newey-West matches an independent implementation |
| T8 | BH and BY reject sets and adjusted values |
| T9 | candidate rule |
| T10 | bootstrap blocks |
| T11 | sub-periods |
| T12 | synthetic rule table |
| **Mutants** | **13/13 killed** (`fd2_mutation_results.json`) |
| **Rerun** | byte-identical |

## Reproduction

Use `repro/` from the v0.13 package, which holds the hourly pack, and copy this overlay over it (`lab/`, `tests/`, `out/market_intelligence/dev_pack_v2/`). Then:

```
python3 -I tests/test_fd2.py --fast      # ~1.5 min, ~1.6 GB
python3 -I lab/fd2.py out/fd2_check      # ~1.2 min
```

## Next (reviewer)

Review of FD-2. Any later stage (Validation design, strategy discovery) needs its own approved step, such as protocol v1.3, before Validation is touched.
