# FD-2 Decision Record v1 (recorded before any FD-2 computation)

**Status:**
- FD-2 has **not** been run.
- No forward outcome, IC or FD-2 statistic has been computed.
- FD-1 is under scientific review and is **not yet accepted**.
- Protocol v1.2 FIXED (sha256 `18d5ddcf…d969`) and v1.1 are untouched.
- The Holdout stays closed.

**Applies to:**
- Feature Discovery Plan v0.1.1 §4 (FD-2), sha256 `1126d551…683a`.
- FD-1 v0.13, commit `64591c5`, report §⚠️.

## Reviewer decisions (2026-11-09)

### D4 — The two FD-1 / FD-2 overlapping tests are excluded from the confirmatory family

- **Excluded cells:**
  - **F01 ret_1 × h = 1**, overlapping FD-1 Q3 F01, k = 1;
  - **F02 ret_7 × h = 7**, overlapping FD-1 Q3 F02, k = 7.
- **Reason:** their FD-1 Q3 values are approximately the same statistic as the FD-2 test, up to the eligibility rule. They have therefore been seen.
- **Treatment:**
  - They are **removed from the confirmatory family and from the BH correction**.
  - They are **kept in the FD-2 report** as `EXPLORATORY_SEEN_IN_FD1`.
  - They can **never** be labelled a candidate.
- **Partial overlaps:** the other price-feature Q3 cells overlap later prices only partly. They stay in the confirmatory family, unchanged. This record does not change their status.

### D5 — FD-2 tests all 22 features; Q5 representatives select nothing

- The confirmatory family is **all 22 features × h ∈ {1, 7, 30}, minus the 2 cells of D4 = 64 tests**.
- Q5 cluster representatives remain **descriptive only**. The sentence in plan §3 ("define which features represent each cluster in FD-2") is superseded by D5.
- **No result-based selection:**
  - The family, the horizons, the BH rule (q = 0.10, two-sided) and the candidate rule of plan §4 are fixed now.
  - No test is added, dropped or regrouped after FD-2 output is seen.

## Exact confirmatory family (64)

| h | Features in the family |
|---|---|
| 1 day | F02–F22 (21; F01 excluded) |
| 7 days | F01, F03–F22 (21; F02 excluded) |
| 30 days | F01–F22 (22) |

## Open point (not decided; needs the reviewer)

**Q-BY. Dependence between features.**
- BH controls the FDR under independence or positive regression dependence (PRDS).
- FD-1 shows strong dependence: 3 multi-feature clusters at |ρ| ≥ 0.80, which can include negative correlations.
- **Proposal:** keep **BH q = 0.10 as the primary rule, as approved**. Add **Benjamini–Yekutieli (BY), q = 0.10** as a **reported sensitivity only**. BY is valid under any dependence.
  - A candidate would be flagged if it **fails** under BY.
  - The candidate rule itself would not change.
- Alternatively, keep BH only. **The reviewer decides before FD-2 is approved.**

## Unchanged

Everything else in plan v0.1.1 stays as written:
- the outcome definition;
- the forced exits;
- Newey-West with lag h − 1;
- the block bootstrap;
- the sub-period stability;
- the candidate rule;
- no strategy, no trade, no P&L, no Validation and no Holdout.
