# Accumulation Breakout v0.1.3: closure record (reviewer decision 2026-11-10)

| Item | Status |
|---|---|
| **Threshold derivation** | **ACCEPTED** (procedure integrity): RD4 PASS; 489 outcome files corrupted in run 2, including 20/20 attribution files; 3 byte-identical runs; isolated run without network; `thresholds.json` sha256 `5dc38aa95599526c17ad42fc98aa37a87abdb10d84e071eb959805fd11758c5f`. **The 8 values are frozen for this experiment and are never changed retroactively** |
| **Accumulation Breakout v0.1.3** | **CLOSED: INCONCLUSIVE BY CONSTRUCTION ON DEVELOPMENT**. There are 64 candidate bars after all conditions, while U7 needs 100 completed trades. No return, profit or loss was computed, and no condition was relaxed. **This is a constraint in signal design and opportunity volume, not a proven failure of profitability, and not evidence that the strategy loses** |
| **P1** for this design | **not run, not approved** |
| **A new strategy design** | **ALLOWED FOR SPECIFICATION ONLY**: a separate experiment in the U8 registry, with its own specification and test plan, reviewed before any code or simulation. Opportunity counts and their composition may be compared at the design stage, **with no trading results**. **A design is not chosen merely because it yields 100 opportunities.** The soundness and executability of its signal come first |
| **Protocol v1.2 / Final Holdout** | unchanged / SEALED |

**Reviewer note:** the commit-before-read order is shown by the git history (`02252ba` before the report `5a2e309`). It cannot be proven from the zip alone.
