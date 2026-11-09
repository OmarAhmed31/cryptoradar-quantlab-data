# Validation Review Record (reviewer decision 2026-11-09)

**Decision:** Validation v0.16 (commit `7ac7058`) is **ACCEPTED** as **one** associational replication test outside Development, under the approved Plan v0.1.1.

**Reviewer verification:**
- The Mini package was checked: 18/18 hashes, byte-identical to the full package on every shared file. The full package was also checked.
- The label counts were re-derived from the 41-row table:

  | Label | Count |
  |---|---|
  | REPLICATED (BH and BY) | 35 |
  | REPLICATED (BH only) | 1 |
  | NOT_REPLICATED | 2 |
  | REVERSED | 3 |

**Accepted reading:**
- **The volatility block is the strongest result.** All 18 replicated; the median Validation IC is about −0.173, and some members reach about −0.25 at h = 30. It is **one** related group, not 18 findings.
- **F20 dist_high_30** replicated with a positive sign, and **F21 dist_low_30** with a negative sign.
- **F13 corr_btc_30** kept its direction but weaker. At h = 30 its bootstrap CI touches 0. It must **not** be described as being as strong as volatility.
- **Not replicated:** short-term reversal (F03/F05 at h = 1 are NOT_REPLICATED; F01/F03 at h = 7 are REVERSED) and F16 thr30 (REVERSED).

**Limits kept on record:**
- Mutant W08 (forced exit a day late) was killed only by the frozen-code hash check, not by a behavioural test.
- The forced-exit counts (13 / 97 / 423) are exits across the 3 horizons and the entry days. They are not counts of unique delisted coins, and they are consistent with the 32 delistings in the window.

**Fixed after this decision:**
- no rerun;
- no re-selection;
- no retest of the reversed results;
- no Protocol v1.2 change;
- the Final Holdout stays sealed.

**Next:** a separate Strategy Plan, written and approved **before** any simulation or backtest.
