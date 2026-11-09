# Strategy, Validation run (v0.19, 2026-11-09): A_N10 once; screening check, NOT independent proof

## Governance

- **Order of work, each step committed before the next:**

  | Step | Commit |
  |---|---|
  | Addendum and attribution code, before the run | `e47b5a1` |
  | **One run of A_N10 only** | outputs in `3409c38` |
  | Meta and gate | `1282ec4` |

- **Incident:** `strategy.py main()` wrote both result files, then raised an IndexError while formatting its metadata line (the day grid had already been restored after the Validation context). **No rerun.** The metadata and gate were written separately from the saved summary. This is recorded in `strategy_meta_val.json`.
- **Window:** 25 weekly rebalances from 2025-09-08 to 2026-02-23. Nothing closes after 2026-04-01, and the Holdout is sealed.
- **Conditions kept:**
  - no re-selection, no substitute variant;
  - no change to features, universe, parameters or method;
  - fee 0.10% per side (conservative taker assumption) with the 0.20% sensitivity, plus the Corwin–Schultz half-spread.
- `close_asof` is a reference proxy.

## Gate (S6, decided before the run)

| Capital | NW p (one-sided) | Bootstrap p | Excess over B1 per week at 0.10% / 0.20% | Gate |
|---|---|---|---|---|
| **$10,000** | 0.0022 | 0.0015 (CI 0.96%–5.08%) | +3.03% / +3.01% | PASS |
| **$1,000** | 0.0022 | 0.0015 | +3.03% / +3.01% | PASS |
| $100,000 (display only) | 0.0008 | 0.0010 | +3.41% / +3.40% | (PASS) |

**Formal result: PASS (10k AND 1k), carrying `RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE`.**

## Money: what actually happened (P1, $10,000, fee 0.10%)

| Portfolio | Net over 25 weeks | Max drawdown |
|---|---|---|
| **A_N10** | **−23.8%** | −25.8% |
| B1, all eligible coins, equal weight | −66.9% | −69.1% |
| B2, BTC buy and hold | −41.0% | −46.8% |
| **B3, cash** | **0.0%** | 0 |

- **The strategy lost about a quarter of its capital.** It lost much less than the altcoin market and less than BTC, but **holding cash beat it**. Cash also "beats" B1 by +4.07%/week with p = 0.0017.
- **So, in a falling market, a gate against B1 mostly measures how defensive a portfolio is, not whether it earns money.**
- The scenarios agree: excess +3.19% in S50k and +2.90% in S250k.

## Why it lost less: attribution (the reviewer's condition)

**By class** (`attrib_by_class_val_A_N10_10000.csv`):

| Class | Mean portfolio weight | Total contribution |
|---|---|---|
| **fiat stablecoins** (USDC, PYUSD, USDG, USD1) | **31%** | +0.0% |
| **gold tokens** (XAUT, PAXG) | **16%** | **+7.1%** |
| staking or wrapped | 1% | −1.5% |
| **all other crypto** | 52% | **−30.7%** |

- **USDC and PYUSD were held all 25 weeks, XAUT all 25 weeks, and USDG 21 weeks.**
- **About half the portfolio sat in assets that are not volatile crypto.** That half is what made the portfolio "low volatility".
- **The crypto half lost about 31 points, the gold half gained 7, and the stablecoin half was flat.**
- BTC itself (held all 25 weeks) contributed −4.9 points.
- **On Development, the same strategy held stablecoins at 12% weight and gold at 7%.** There, the crypto part made the money (+82 points), because the market rose.

## Reading

1. The pre-registered gate is passed, but **the strategy is not profitable on Validation**. Its relative edge over B1 comes from **holding stablecoins and gold during a crypto decline**, and to a smaller extent from large caps falling less than small caps.
2. Validation was already used for the FD-2 replication, so this is a **screening check, not independent proof** (record S4).
3. A "low-volatility" rule that is allowed to pick stablecoins and gold acts as an **automatic risk-off switch**. That may have value as a **defensive tool**. It is not evidence of an edge inside crypto.

## Next steps (the reviewer decides; nothing has been started)

- **Option 1. Close this plan** with "PASS against B1, but not profitable; defensive by construction". Do **not** move to Forward Shadow as a profit strategy.
- **Option 2. A new, separately approved plan** that removes pegged assets (stablecoins, gold, staking or wrapped) **from the universe before any computation**, and re-asks the question inside crypto only. It would use Development for selection. Its unseen test would be Forward Shadow, or the Holdout under Protocol v1.3 with an external signature. **It is not a rescue of this result.**
- **Option 3.** Study the defensive behaviour openly as a risk tool: when to move to stablecoins. That is a different question, and it would need its own plan.
