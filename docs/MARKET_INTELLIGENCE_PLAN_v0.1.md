# Market Intelligence — plan v0.1 (for approval before any computation)

**Status:** PROPOSAL. **No Market Intelligence output has been computed yet.**

**Base:** Research Protocol v1.1, FIXED (sha256 `91718b69…678c`, tag `protocol-v1.1`). Nothing below changes it.

## 0. Decision needed FIRST: the time split

Market Intelligence means *looking* at how the market behaves. If we look at the whole period now, then every later strategy choice is made with knowledge of the whole period, the final holdout included. The holdout would then no longer be out-of-sample (see Plan §10: "If [holdout] was used to adjust a strategy, it becomes in-sample").

**So the split must be fixed before the first chart is drawn.**

**Proposed rule:** chronological, by calendar only (roughly 60/20/20), with a 7-day embargo at each boundary.

| Segment | UTC | Use |
|---|---|---|
| Development / Discovery | 2024-01-01 → 2025-08-31 (20 months) | **Market Intelligence, features, regimes, strategy generation** |
| embargo | 2025-09-01 → 2025-09-07 | none |
| Validation | 2025-09-08 → 2026-03-31 | Selection and checks only. MI is **not** run on it |
| embargo | 2026-04-01 → 2026-04-07 | none |
| Final Holdout | 2026-04-08 → 2026-10-31 | **Opened once**, at the end, for candidates already frozen |
| Forward Shadow | from 2026-11-01 | Live counters, no trading |

- The dates are set **from the calendar alone**. No result, regime or return was looked at to choose them.
- **Alternative B:** if you prefer, MI may describe the whole period at a **coarse level only** (e.g. monthly market-wide counts), and the detailed MI stays inside Development. Option A is stricter; **we recommend A**.
- The split would go into **Protocol v1.2** (a new rule T4). Only T4 would be added, and it needs approval before any MI computation.

## 1. Scope of Market Intelligence (descriptive only; inside Development only)

| Block | Output | Point-in-time rule |
|---|---|---|
| M1 Market state | daily breadth: % of eligible pairs up over 1, 7 and 30 days; median return; dispersion; BTC vs median altcoin | Day d uses data up to the close of d-1 |
| M2 Volatility | realised volatility over 1d, 7d and 30d per pair and market-wide; volatility regimes by percentile bands computed **inside Development only** | Prior data only |
| M3 Liquidity | DV30 and THR30 over time; how many pairs enter and leave the P1 universe; turnover | Taken from the fixed universe files |
| M4 Correlation | rolling 30-day correlation to BTC and to the median coin; changes in correlation | Prior data only |
| M5 Candidate regimes | unsupervised and interpretable: rule-based bands plus at most one clustering method (e.g. k-means on M1/M2 features, k fixed in advance at 3–6 with an `UNKNOWN` class), with stability across time | Labels use **past data only**, never future returns. Fitted on the first part of Development and checked on the rest |
| M6 Survivorship lens | the same statistics with and without the later-delisted series, to show the size of the bias | — |
| M7 Event calendar | **not proposed now.** It needs a new external source, so it would need separate approval | — |

**Rules:**
- No strategy, entry, exit or P&L is computed.
- No result from M1–M6 may change Protocol v1.1.
- Every statistic is reported for **P1, S50k and S250k**.
- The 150-coin, 38-coin and CryptoRadar comparisons stay **local**.

## 2. Acceptance (before moving on to Feature Discovery)

- Leakage tests in the same style as v0.10.1:
  - destructive future overwrite gives identical values for day d;
  - mutants are killed.
- Regime stability is reported: the fit on the first half of Development applied to the second half, and how often states flip.
- ZIP with code, outputs, sha256 and commit. Then **stop for review**.
