# Experiment 4: code and test review record

**Reviewer decision (review of v0.47):** the code and tests of Experiment 4 are **APPROVED AND FROZEN**. **The real counts run is NOT yet approved.**

| Item | State |
|---|---|
| Commit approved for review | `a342099f54a2a9a26361a63fa8593ccd6cdca1a3` |
| The frozen hashes | `out/exp4/precheck/FROZEN_SHA256.txt` (8 files). The reviewer checked them against the v0.47 ZIP: all match |
| `lab/exp4_counts.py` | approved, no further change |
| `tests/test_exp4.py` | approved (36/36 on synthetic data) |
| `tests/run_exp4_once.py` (RD4) | approved, no further change |
| `tests/run_exp4_mutants.py` + `tests/test_mutant_runner.py` | approved: strict behavioural classification; 23/23 KILLED; self-test 20/20 |
| L_worst | `null`, an approved exception, never used in selection |
| Spec | `EXP4_CAPITAL_ALLOCATION_DESIGN_PROPOSAL_v0.5.md`, frozen, unchanged |

**Review chain:**
1. v0.44: the fill check had to run only after selection → v0.45;
2. v0.45: the three files were requested separately;
3. v0.46: a kill had to be behavioural;
4. v0.47: the summary had to agree with the test lines → **closed**.

**Next:** a separate, explicit approval for **ONE** Development counts run with RD4, after a pre-run hash check against `FROZEN_SHA256.txt`.

No real run has been made. P1, Validation and the Final Holdout are untouched.
