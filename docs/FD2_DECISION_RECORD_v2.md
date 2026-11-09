# FD-2 Decision Record v2 (recorded before any FD-2 computation)

**v2 change:** Q-BY is now decided as **D6**. D4 and D5 are unchanged from v1 (sha256 `975bc56b…39ff`).

**Status:**
- FD-2 has **not** been run.
- No forward outcome, IC or FD-2 statistic has been computed.
- FD-1 is under scientific review and is **not yet accepted**.
- Protocol v1.2 FIXED (sha256 `18d5ddcf…d969`) and v1.1 are untouched.
- The Holdout stays closed.

**Applies to:**
- Feature Discovery Plan v0.1.1 §4 (FD-2), sha256 `1126d551…683a`.
- FD-1 v0.13, commit `64591c5`, report §⚠️.

## Reviewer decisions (2026-11-09; D4, D5 and D6 all approved)

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

### D6 — Q-BY: BH stays the rule; BY is a reported sensitivity (decided 2026-11-09)

**Reason:** negative correlations between features are possible. PRDS therefore cannot be assumed, and BH's theoretical guarantee cannot be claimed under this dependence. BY is valid under arbitrary dependence.

**Fixed now:**
1. **Same family, same p-values.** BH and BY are applied to the same 64 confirmatory tests and the same two-sided p-values (from the plan §4 Newey-West statistic).
2. **q = 0.10 in both.**
3. **The candidate rule of plan §4 is unchanged.** It uses **BH**. BY never adds, removes or changes a candidate.
4. **BY is reported as a sensitivity.** Each test shows its BH-adjusted and its BY-adjusted value. A candidate that passes BH but fails BY carries the label **`BH_ONLY — FAILS_BY_SENSITIVITY`**.
5. **Reading:** BY is usually more conservative. Failing BY does not make the BH result wrong; it means the evidence is weaker under a guarantee that holds under general dependence.
6. **No FD-2 computation** is done before this record (v2) is committed and FD-1 is accepted.

## Unchanged

Everything else in plan v0.1.1 stays as written:
- the outcome definition;
- the forced exits;
- Newey-West with lag h − 1;
- the block bootstrap;
- the sub-period stability;
- the candidate rule;
- no strategy, no trade, no P&L, no Validation and no Holdout.
