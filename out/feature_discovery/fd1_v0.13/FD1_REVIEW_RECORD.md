# FD-1 Review Record (reviewer decision 2026-11-09)

**Decision:** FD-1 v0.13 (commit `64591c5`) is **scientifically ACCEPTED within its descriptive and exploratory scope**.
- It is not evidence of predictive power, and it is not evidence that any feature is usable in a trading strategy.
- No number, file or definition of FD-1 changed. This record only adds interpretive limits. `FD1_REPORT_v0.13.md` is unchanged and keeps its sha256.

| Item | Reviewer judgement |
|---|---|
| Q1 Coverage | accepted |
| Q2 Stability | accepted. There is no exclusion rule based on it |
| Q3 Persistence | accepted, subject to D4 |
| Q4 Redundancy | accepted |
| Q5 Representatives | descriptive only |
| Q6 Regime relation | accepted **with the limits below** |
| Q7 Survivorship | accepted |

## Interpretive limits (binding on any later use of FD-1)

### Q6 circularity

- **F02 ret_7, F06 vol_7, F07 vol_30 and F13 corr_btc_30** have the same definition as inputs of the regime model.
  - Their differences between regimes are **not** an independent finding.
  - They are **not** evidence that these features distinguish regimes.
  - They are kept, not deleted and not recomputed.
- **F03 ret_30** relates to breadth_30, so it must be read with caution. It is **not** one of the four identical definitions.

### Q6 confidence intervals

- The 95% intervals are **descriptive and NOT corrected for multiple comparisons** across 22 features × 3 states.
- So "the CI excludes 0 for 14 of 22 features" does **not** mean that 14 features showed an independent or confirmatory relation.

### Q6 bootstrap scope

- The bootstrap is **conditional on the `regime_asof` sequence used**.
- It does **not** include the uncertainty from re-estimating the regime model, or from a different assignment of states.

### F16 thr30

- Its monthly median is 1.0 in every month, and its IQR is 0.
- 81% of series-days equal 1.0, so it has limited cross-sectional discrimination.
- It **stays among the 22 FD-2 features** per the fixed plan, with no change of definition. A null FD-2 result for F16 would have this as a plausible explanation.

### S3

- S3 has 19 days, so it is descriptive only and has no CI.

### Tests

- The reviewer reviewed the logic and the recorded results:
  - FA0–FA3, FQ3, FQ4, FQ6 and FQ7 pass;
  - full mode 14/14;
  - mutants 14/14.
- **Not independently re-run by the reviewer**: Mini.1 has no hourly data.
- M09 (vol_30 window changed) was killed by a crash, not by a dedicated assertion. This is accepted and does not block FD-1.

## Status after this record

| Item | Status |
|---|---|
| The 22 feature definitions | fixed |
| Q1–Q7 | accepted within these limits |
| D4, D5, D6 (Decision Record v2, sha256 `56c4dcef…2521`) | unchanged |
| Protocol v1.2 | fixed |
| FD-1 gate | **satisfied** |
| FD-2 | closed until it is formally opened |
| Final Holdout | closed |
