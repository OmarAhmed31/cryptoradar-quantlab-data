# Feature Discovery FD-1 — Development only (v0.13, 2026-11-08)

## Governance

- **Plan:** v0.1.1 APPROVED (sha256 `1126d551…683a`), FD-1 only. Protocol v1.2 FIXED.
- **Feature catalogue** `feature_catalogue.json` (sha256 `c51334e2…2024024`) was committed (`f7134d6`) **before** any feature was computed. Test FA0 checks the code against it.
- **Data:** days 2024-01-01 → 2025-08-31, from the Development pack only, plus `regimes_asof` of MI v0.11.2.
- **Not computed or used:** forward outcomes, ICs, trades, P&L, portfolio returns. Validation and Holdout were not used. FD-2 was not run.
- **Eligible series-days (P1):** 143,806. Without the later-delisted coins: 107,568, so **25% of the research universe would be lost to survivorship**.

## ⚠️ Two points for the reviewer before any FD-2 decision

**1. Q3 persistence on price features contains forward-return information (a plan issue I found while computing).**
- For a return feature, the value at d+k *is* a later return. ret_1(d+1) is exactly the plan's `fwd_1(d)`, and ret_7(d+7) is exactly `fwd_7(d)`.
- So two Q3 cells equal, up to the eligibility rule, two FD-2 ICs:

  | Q3 cell | Mean ρ | Equals |
  |---|---|---|
  | F01, k = 1 | **−0.037** | FD-2 F01 × h = 1 |
  | F02, k = 7 | **−0.042** | FD-2 F02 × h = 7 |

- Other price-based features (F03–F05, F20, F21; F01 at k = 7; F02 at k = 1) partly overlap later prices.
- These numbers are in `fd1_persistence.csv`. They are **not** interpreted here.
- **Proposal for the FD-2 approval:** treat F01 × 1 and F02 × 7 as **already seen**. Either remove them from the confirmatory family of 66 (making it 64), or keep them in BH but label them "seen in FD-1" so they can never count as a candidate. The reviewer decides.

**2. Q5 vs the FD-2 test family** (the open point from the approval). Q5 is descriptive here and excludes nothing.

## Results (P1 is primary; files `*_S50k`, `*_S250k`, `*_survivors_only` hold the rest)

### Q1 Coverage

- Over all eligible series-days, coverage is **93.5% to 100%** for every feature.
- From March 2024 on, it is **≥ 99.6%** for every feature.
- The shortfall comes only from windows that cannot be complete early in 2024. For example, F04 has no value before 2024-02-08, so it has 38 days with fewer than 20 series.

### Q3 Rank persistence (mean daily Spearman between d and d+k)

| Group | k = 1 | k = 7 |
|---|---|---|
| Liquidity/scale: F15 log DV, F18 Amihud | 0.999 | **0.988** |
| F19 traded minutes | 0.996 | 0.934 |
| 30-day vol: F07, F09 | 0.99 | 0.93–0.94 |
| Market relation: F12–F14 | 0.98 | 0.85–0.89 |
| 30-day return/position: F03–F05, F20 | 0.93–0.94 | 0.69–0.71 |
| Fast-changing: F08 vol ratio, F17 volume ratio, F11 max hourly return | 0.90–0.91 | **0.21–0.44** |
| F01, F02 | see ⚠️ 1 | see ⚠️ 1 |

### Q4/Q5 Redundancy (median daily Spearman, |ρ| ≥ 0.80)

There are **14 clusters**: 11 single features and 3 groups.

| Cluster | Q5 representative (fixed rule) |
|---|---|
| {F03 ret_30, F05 beta-adjusted ret_30} | F03 |
| {F06 vol_7, F07, F09, F11, F14, F22}: one volatility block | F06 |
| {F15 log DV, F18 Amihud, F19 traded minutes}: one liquidity block | F15 |

- **Sensitivity:**
  - At 0.70 there are 13 clusters (F04 joins F03).
  - At 0.90 there are 18 clusters: the volatility block splits into {F06, F22} and {F07, F09}, and F15 stays with F18.
- The P1 clusters are identical without the delisted coins.
- S50k differs only at 0.70.

### Q6 Relation to regimes (raw daily medians; as-known labels; 427 days)

**Circularity, stated plainly:** the regime model was fitted on MI inputs. Four features have **the same definition** as a regime input:

| Feature | Same as regime input |
|---|---|
| F02 ret_7 | median_ret_7 |
| F06 vol_7 | mkt_vol_7 |
| F07 vol_30 | mkt_vol_30 |
| F13 corr_btc_30 | median_corr_btc_30 |

F03 relates to breadth_30. **Their Q6 differences hold by construction and carry no information.**

**S1 (75 days) vs S2 (237 days):** the 95% CI excludes 0 for 14 of 22 features. The S1–S2 differences that do not hold by construction:

| Feature | S1 | S2 |
|---|---|---|
| F08 vol_7 / vol_30 | 1.08 | 0.90 (a volatility spike) |
| F15 30-day dollar volume | ~49% higher than S2 | (13.79 log) |
| F19 traded-minute share | 0.85 | 0.74 |
| F20 distance from 30-day high | −34% | −21% |
| F22 7-day range | 0.111 | 0.073 |
| F14 idiosyncratic vol | 0.045 | 0.035 |

**UNKNOWN (96 days) vs S2:** the 95% CI excludes 0 for 13 of 22 features. UNKNOWN days sit between S1 and S2 on most features.

**S3 (19 days):** `LOW_N`, so descriptive only and no CI. Its medians:
- ret_30 +56%;
- corr to BTC 0.41;
- beta 0.88;
- distance from the 30-day low +74%;
- volume ratio 1.38.

**Robustness:** the sign of every difference vs S2 agrees with P1 in **64/66** cells for S50k and **63/66** for S250k.

### Q7 Survivorship

Excluding the later-delisted coins:
- raises coverage by 0.1–1 point;
- changes 7-day persistence by at most 0.03;
- changes S1–S2 differences only slightly. The largest changes are F15 (0.398 → 0.360) and F12 (−0.044 → −0.033).

The descriptive picture is **not driven by survivors**. The universe size is: 25% of series-days come from coins that were later delisted.

### Q2 Monthly stability

Reported, not gated (`fd1_stability_monthly.csv`).
- Return features swing with the market: the monthly median of ret_30 runs from −33% to +37%.
- Volatility medians move within about ×2 (vol_7 0.82%–1.56% per hour).
- The median 30-day dollar volume moves within about ×4.
- The median beta to BTC runs from 0.58 to 1.90.

### Quality flag

**F16 thr30 = 1.0 on 81% of series-days.** The monthly median is always 1. It is heavily tied, so its ranks carry little cross-sectional information. This is reported only; nothing is dropped in FD-1.

## Acceptance

| Test | Result |
|---|---|
| FA0 Catalogue hash and code consistency | pass |
| FA1 Destructive future overwrite | Every feature and eligibility mask at days ≤ d unchanged, all 6 masks |
| FA2 Guard | Every lookback goes through `check_feature`; a value before its window is complete is refused; Validation inputs and days are refused |
| FA3 Independent naive recompute | Pure-Python implementation from the raw pack CSVs, all 22 features, relative tolerance 1e-9 |
| FQ3, FQ4, FQ6, FQ7 | Statistics recomputed independently (scipy Spearman, regimes read from file); the bootstrap block structure is verified; `LOW_N` carries no CI; the survivors mask has no delisted coin |
| FA5 Mutants | **14/14 killed** (`fd1_mutation_results.json`). M09 (vol_30 window changed to 31 days) is killed by a crash, not by an assertion |
| Results | Full mode **14/14** (FA1 on 8 days, 66.1M+ values; FA3 on 1,000 series-days = 22,000 values, 0 mismatches). Fast mode **14/14** (4 days, 300 rows). Files: `fd1_test_result_full.json`, `fd1_test_result_fast.json` |

FD-2 mutants (IC overlap, BH, forced exits, outcome crossing) are deferred with FD-2.

## Reproduction

```
cd repro
python3 -I tests/test_fd1.py --fast          # ~2 min here; 300 rows / 4 days
python3 -I tests/test_fd1.py                 # ~3.5 min here (full)
python3 -I lab/fd1.py out/fd1_check          # ~2 min here
```

- **Memory:** peak about **3.1 GB** (fast) and **3.7 GB** (full), on 2 CPUs. A sandbox with less memory or a short time limit may not finish.
- The outputs are **byte-identical** to the shipped ones (checked in `repro/`).

## Next

Review of FD-1. Then a separate decision on FD-2, which first needs points ⚠️ 1 and ⚠️ 2 settled.
