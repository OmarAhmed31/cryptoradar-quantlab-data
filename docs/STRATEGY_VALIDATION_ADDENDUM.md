# Strategy Validation run: addendum (reviewer conditions 2026-11-09), committed BEFORE the Validation run

**The reviewer approved running only the frozen selection `A_N10`, once, with these conditions:**
- No feature, universe, parameter or method changes.
- No re-selection, and no B_N20 or any other substitute.
- The capitals, fees and S6 gate are as fixed in `STRATEGY_CAPITAL_DECISION.md`: **overall PASS = PASS($10,000) AND PASS($1,000)**.
- Validation is a **performance and screening check, not independent proof**, because it was already used for the FD-2 replication.
- The Final Holdout stays sealed.
- **The contribution of USDC, PYUSD, XAUT and every other asset is shown, with the portfolio composition and its stablecoin exposure.**

**Attribution method (descriptive; it does not change the simulation, the selection or the gate):**
- Code: `lab/strategy_attrib.py` and `lab/run_strategy_attrib.py`.
- A position's contribution = (its value at the end of the week, or its forced-exit proceeds, − its value right after the rebalance) / the portfolio value at the start of the week.
- The recorded path must equal `strategy.simulate()` to 1e-9, or the code raises. This was checked on Development at $10,000 and $1,000: equal.

**Asset classes, by ticker, fixed now:**

| Class | Tickers |
|---|---|
| fiat stablecoin | USDC, PYUSD, USDG, USD1, EURT |
| gold token | XAUT, PAXG |
| staking or wrapped | STETH, BETH, JITOSOL |
| other | everything else (USTC is "other", because it lost its peg in 2022) |

**The same attribution is produced for Development and for Validation, at all three capitals.**
