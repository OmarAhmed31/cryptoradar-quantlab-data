# Regime threshold derivation plan v0.1: P-1 / P-2 (DRAFT for review; NOTHING computed)

**Context:**
- This plan belongs to Spec v0.1.3 (sha256 `46a2b1de…a441a`), items P-1 and P-2.
- The reviewer agreed **in principle** to derive the market-state thresholds from **indicator distributions on Development only**, with **no trading outcome of any kind**. He asked for the scope to be fixed exactly before any computation.
- This document is that scope. **No distribution has been computed. P1 is not approved.**

## 1. Hard rules for the derivation run

1. **Inputs:**
   - the Development pack (2024-01-01 → 2025-08-31);
   - the frozen FD-1 feature code;
   - the crypto-only universe (Spec §3).
   - **Nothing from Validation, the embargo or the Holdout.**
2. **Forbidden:**
   - any forward return;
   - any outcome;
   - any trade, P&L, win rate, expectancy, or IC with future returns;
   - any strategy result.

   The derivation code may import **only** the feature code, the eligibility and universe code, and the hourly bars up to each bar's close. **It may not import the FD-2, Validation, strategy or simulator modules.** A test checks this (§4).
3. **One run.** Each threshold comes from **one pre-stated statistic** (a fixed percentile or median), not from a search over candidates.
4. The output is a frozen `regime_thresholds.json` with sha256, committed **before** P1 code is run.
5. **Using full-Development distributions** to fix constants that are later applied point-in-time is the same as fitting any rule on the design segment. It is allowed under T4 ("Development: … strategy generation"), and it is stated, not hidden.

## 2. What is derived, and how (one statistic each)

| Item | Current proposal (Spec §10) | Derivation rule (fixed now) | Source distribution |
|---|---|---|---|
| **Trend thresholds** (Bull / Bear on the 20-day EW return) | ±5% `CONV` | **Bull if** the 20-day EW return > its **67th percentile**. **Bear if** it is < its **33rd percentile**. The Bull/Bear/Sideways split then follows the index's own spread of 20-day moves (tertiles). The 50-day-mean condition stays | the daily 20-day EW-index returns, Development, with ≥ 20 coins per day |
| **Volatility bands** | ⅓ / ⅔ of the expanding prior percentile | **No new constant.** The band is already a percentile of the index's own past (the MI M2 rule, approved earlier). It stays as is | — |
| **Bear: stricter confirmation** | RVOL ≥ 3 `CONV` | RVOL ≥ the **75th percentile of RVOL among bars that already pass the normal confirmation** (M: RVOL ≥ 2, CLV ≥ 0.70, stronger than BTC). "Stricter" then means the strongest quarter of confirmations | hourly breakout bars (A1 ∧ A2 ∧ C ∧ B ∧ M), Development |
| **High volatility: maximum stop distance** | 8% `CONV` | **The median stop distance** (entry − R_low)/entry among the same candidate setups. In High Vol, setups wider than the typical setup are skipped | the same setups, Development, with the entry approximated by the breakout close **for this distribution only** (no fills, no outcomes) |

## 3. What stays a design rule, and why

These are stated as **design conventions**, because no distribution identifies them without outcomes:

| Item | Value | Why it stays a convention |
|---|---|---|
| Window lengths | 20-day trend return, 50-day mean, 30-day volatility | Window lengths are **horizon choices**. A distribution of the indicator does not pick a window, only thresholds within one. They match the FD-1 windows (7 / 30 days) where possible |
| Transition window | 5 days | A "recent change" horizon. It could be tied to the median length of trend runs, but those runs depend on the thresholds above. To avoid a loop, it stays 5 days and is reported with the derived run-length distribution **for information only** |
| A2 risk in High Vol | 0.5% (half of 1%) | A risk-policy choice, not a market property |
| Minimum coins for the index | 20 | Already approved (R6e) |

**Out of scope here:** the Spec §5 entry thresholds (25th percentile, 0.80, RVOL 2×, CLV 0.70, 15% stop). The reviewer's request covered P-1/P-2 only. If the reviewer wants those derived the same way, that is a separate, explicit decision **before** this run, because the run happens once.

## 4. Acceptance tests (written before the run)

| Test | What it checks |
|---|---|
| RD1 Isolation | The inputs hold no candle closing after 2025-09-01 and no universe day ≥ 2025-09-01 |
| RD2 No outcomes | The derivation module imports none of `fd2`, `val`, `strategy`, `strategy_attrib` or a simulator. A static check covers the module source, and a runtime check covers `sys.modules` |
| RD3 Point-in-time indicators | Destructive overwrite of the future: every indicator value at t is unchanged when every bar at or after t is corrupted |
| RD4 Independent recompute | The percentiles are recomputed by a separate naive implementation |
| RD5 One statistic per item | The output JSON holds exactly the 4 derived numbers of §2 plus the reported distributions. Nothing else is tunable |

## 5. Output

- `regime_thresholds.json`, holding:
  - the derived values;
  - the count of observations behind each;
  - the distribution summaries (deciles);
  - the run-length distribution, for information only;
  - the input and code hashes.
- A short report. **It contains no performance number of any kind.**

## 6. Decision requested

1. Approve **this scope**: the 4 derived items, the rules in §2, and the conventions in §3.
2. Say whether the **§5 entry thresholds** should **also** be derived in the same single run (yes or no), before it runs.
