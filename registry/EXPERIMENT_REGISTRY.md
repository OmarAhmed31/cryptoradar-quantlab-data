# Experiment registry (U8 §6): every strategy experiment, successful or not, in order

| # | Experiment | Data used | Result | Status | Record |
|---|---|---|---|---|---|
| 1 | **A_N10**: low-volatility top 10, weekly rebalance (Strategy Plan v0.1.3) | Development (selection among 4 variants), then Validation (one run) | **PASS against B1, but NOT PROFITABLE**: −23.8% on Validation, cash beat it; defensive (stablecoins and gold) | **CLOSED** | `out/strategy/val_v0.19/STRATEGY_CLOSURE_RECORD.md` |
| 2 | **Accumulation Breakout v0.1.3**: hourly, 9 stacked conditions; thresholds derived once (`thresholds.json` sha256 `5dc38aa9…8c5f`) | Development, **indicator distributions only** | **INCONCLUSIVE BY CONSTRUCTION**: 64 candidate bars < 100 completed trades (U7). **No return computed.** This is a constraint in signal design and opportunity volume, **not** proof that profitability failed | **CLOSED** (no P1) | `out/thresholds/run_v1/CLOSURE_RECORD.md` |
| 3 | **Experiment 3: design selection** (D-H1 / D-H2 / D-D1; feasibility by a guaranteed lower bound on trades, no returns) | — | plan draft | **SPEC STAGE** | `docs/EXP3_DESIGN_SELECTION_PLAN_v0.2.md` |

**Number of strategy variants evaluated on returns so far:** 4 (all A_N10 variants, on Development). **Strategies taken to Validation:** 1. **Holdout:** sealed, 0 used.
