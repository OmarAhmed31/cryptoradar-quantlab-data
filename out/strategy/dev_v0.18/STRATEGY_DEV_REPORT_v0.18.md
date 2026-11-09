# Strategy, Development run (v0.18, 2026-11-09): selection done; Validation NOT opened

## Governance

- **Rules applied:** Plan v0.1.3, the review record, and the capital decision (sha256 `dee4edf7…273b`, bound to the plan, code and test hashes).
- **Order of work, each step committed before the next:**

  | Step | Commit |
  |---|---|
  | Code and tests, before any return | `ce80075` |
  | Mutants: 13/14 killed, and X12 **proved equivalent** on this data (the start day has 222 B-tradeable coins; the 5 days before have 0) | `8ee1496` |
  | Tests full 6/6, fast 6/6 | `8ee1496` |
  | Capital decision | `72629f8` |
  | **One Development run**, committed before it was read | `47f9cad` |
  | **Rule-based selection** | `0b1a35a` |

- **Development:** 79 weekly rebalances from 2024-01-31 to 2025-07-30. B1 had 39 forced delisting exits, and the variants had 0.
- **Fee:** 0.10% per side, a conservative taker assumption (0.20% sensitivity), plus the Corwin–Schultz half-spread.
- **Prices:** `close_asof` is a reference proxy, not an executable price.

## S3 selection (at $10,000, P1, fee 0.10%): **A_N10**, volatility only, top 10

| Portfolio | Net total | Annualised | Sharpe | Max DD | Mean weekly excess over B1 | p NW / boot (one-sided) | Turnover per week | Mean cash |
|---|---|---|---|---|---|---|---|---|
| **A_N10** | **+81.7%** | +48.2% | 1.01 | −32.0% | **+0.77%** | 0.18 / 0.19 | 31% | 2.9% |
| A_N20 | +47.7% | +29.2% | 0.71 | −43.4% | +0.60% | 0.18 / 0.19 | 35% | 1.3% |
| B_N10 | −4.3% | −2.9% | 0.28 | −54.8% | +0.15% | 0.42 / 0.42 | 88% | 1.9% |
| B_N20 | +0.3% | +0.2% | 0.34 | −55.3% | +0.25% | 0.31 / 0.31 | 75% | 1.3% |
| **B1** equal weight, all eligible | **−33.8%** | −23.8% | 0.13 | −73.8% | 0 | — | 14% | 1.4% |
| **B2** BTC buy and hold | **+164.9%** | +89.9% | 1.52 | −28.1% | +1.25% | 0.08 / 0.09 | — | — |
| B3 cash | 0 | 0 | — | 0 | −0.22% | — | — | — |

**Robustness:**

| Check | A_N10 | Other variants |
|---|---|---|
| At $1,000 (fee 0.10%) | +77.6% net, excess +0.74%/week (p 0.19) | Same ordering |
| At $100,000 (display only), with the 1% cap binding | +80.3% net with 26% average cash, excess +0.65%/week | — |
| 0.20% fee | Excess +0.75%/week | B_N10/B_N20 turn negative in absolute terms |
| Scenarios (excess at $10k) | S50k +0.84%, S250k +0.70% | Same sign everywhere |

## Two facts the reviewer must see before Validation

**1. Even on Development, the selected variant is NOT significant against B1** (one-sided p ≈ 0.18). It also **lagged plain BTC buy-and-hold by a wide margin** (+81.7% against +164.9%). The plan's Validation gate compares to B1 only. B2 is reported, so a PASS would still sit below BTC on this evidence.

**2. What "low volatility" actually buys** (`strategy_holdings_frequency_dev.csv`). A_N10 held, out of 79 weeks:

| Coin | Weeks held | What it is |
|---|---|---|
| **USDC-USDT** | **79** | stablecoin |
| BTC | 78 | — |
| TRX | 73 | — |
| BNB | 66 | — |
| **XAUT** | **59** | gold token |
| NFT | 54 | — |
| ZKJ | 47 | — |
| OKB | 41 | — |
| ETH | 32 | — |
| **stETH / BETH** | 28 / 22 | ETH derivatives |
| **PYUSD** | **16** | stablecoin |

- So the portfolio is largely **stablecoins, gold, ETH derivatives and the largest coins**. These are pegged or near-pegged assets that are mechanically low-volatility.
- **The same mechanism is part of what FD-2 and Validation measured** for the volatility block. Stablecoins and pegged tokens rank as "low volatility" with near-zero returns, and in a phase where altcoins fall, they rank high.
- **This is not a bug.** USDC-USDT was kept in the universe on purpose (ledger correction #2, approved). But it means the replicated volatility effect is, at least partly, **"pegged assets and majors did not fall like altcoins"**, not a broad low-volatility premium among altcoins.
- Nothing is changed or re-run here. Excluding pegged assets would be a **new, separately approved analysis**. It must not be a post-hoc tweak of this plan.

## Status

| Item | Status |
|---|---|
| Selection | **A_N10**, frozen (`strategy_selection.json`) |
| Validation | **not opened**. It waits for the reviewer's go-ahead, as instructed |
| Protocol v1.2 | unchanged |
| Final Holdout | sealed |
