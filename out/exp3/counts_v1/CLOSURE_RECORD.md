# Experiment 3: closure record

**Reviewer decision (on v0.38):** `STOP_INFEASIBLE` accepted. **Experiment 3 is CLOSED.**
- No threshold or condition changed. No design goes to P1.
- No return was computed. Validation and the Final Holdout are not opened. Protocol v1.2 is unchanged.

**Nature of the result (reviewer):** a failure of the experiment's **feasibility condition under the chosen framework**, NOT a failure of a strategy.

## Commit chain (the clarification the reviewer asked for)

| Commit | What it holds |
|---|---|
| `1f91f8b09c5d0b80d345511cbff2bf889d929cc5` | **Frozen code and tests (v0.37)**, the version approved for the run. The pre-run hash check verified against this commit |
| `8d9a648863542a68e5e9b7e169ebe3e855deb55f` | `PRE_RUN_HASH_CHECK.txt`, written **before** the run |
| `a5eefd59812bd76a5ad149c2ceafbb181ba4b7a4` | **The run outputs** (`exp3_counts.json`, `rd4_result.json`, logs), committed **before they were read**. This is the `a5eefd5` named in the report |
| `af8943a10cba153becd438c722430f2cf55bde07` | **The report and the registry update**, written **after** reading the outputs. It is the HEAD when the v0.38 package was built, so it is the one in `COMMIT.txt` |
| this commit | this closure record |

**Between `1f91f8b` and `af8943a`, no code, test or input file changed.** `git diff 1f91f8b af8943a -- lab tests` is empty. Only out/exp3/counts_v1 and the registry were added.

**Unchanged:** the thresholds, the designs, the frozen code. The Final Holdout is sealed. P1 is not approved.

**Next:** none started. The framework question (U7 count, positions, hold length, segments) is open. The reviewer advises settling **first** whether the intended trading model allows several open positions, before any change to the 100-trade requirement.
