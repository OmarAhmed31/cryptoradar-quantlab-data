# Experiment 4: closure record

**Reviewer decision (on v0.48):** `STOP_INFEASIBLE` accepted. **Experiment 4 is CLOSED.**

**Results (L_greedy, K = 3):** D-D1 32, D-H1 51, D-H2 46, against 100. The dominant reason is `SKIPPED_NO_CASH` (D-H1: 883 of 1,195 signals).

**The nature of the result (reviewer):** a failure of the research feasibility condition, **not** evidence that the breakout strategy loses. No return was computed, and P1 was not tested.

**Not allowed (reviewer):**
- changing the 100-trade requirement retroactively;
- using Validation to make up the shortfall;
- running P1 on these designs within this experiment.

**The breakout family is CLOSED in its tested form** (reviewer recommendation):
- Accumulation Breakout v0.1.3 (Exp. 2), and D-H1, D-H2 and D-D1 under a single position (Exp. 3) and under the owner's policy (Exp. 4).
- **No Experiment 5 that merely adjusts the same hypothesis to rescue it.**
- Breakout ideas are not excluded from future research, but this version is not pursued further.

**Commit chain:**

| Commit | What it holds |
|---|---|
| `a342099` | the code and tests, approved and frozen |
| `92f357b` | the pre-run hash check, 8/8 match |
| `3a81793` | the outputs, committed before reading |
| `72f36bf` | the report and the registry update |
| this commit | this closure record |

**Unchanged:** the thresholds, the designs, spec v0.5, Protocol v1.2. The Final Holdout is sealed and unspent. P1 is not approved.

**Next:** a new research decision, made **before any code**:
- what is tested, and why there is a plausible economic hypothesis for it;
- its pre-registered stop conditions;
- **its feasibility arithmetic, checked first.** This is the lesson of Experiments 3 and 4: with ~579 entry days on Development and mostly one open position, reaching 100 completed trades needs an average capital lock of at most about **5.8 days** per trade. That is plain arithmetic, not a target.
