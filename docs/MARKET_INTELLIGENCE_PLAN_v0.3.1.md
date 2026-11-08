# Market Intelligence — plan v0.3.1 (aligned with Research Protocol v1.2, sha256 18d5ddcf…d969)

**Authoritative rules:** Research Protocol v1.2, §3 (T4, T5), §4b (H1–H7) and §4c (R1–R6). This plan **adds no rule**. If anything here differs from the protocol, **the protocol wins**.

Plans v0.2 and v0.3 are SUPERSEDED.

**Change from v0.3:** only A2 now quotes the current guard results, 32/32 tests and 16/16 mutants. The holdout line notes that v1.2 has no opening path at all.

**Status:** nothing has been computed. MI starts **only after** v1.2 is approved with its exact sha256.

## What MI will produce (Development only; descriptive; point-in-time)

| Block | Output | Point-in-time basis |
|---|---|---|
| M1 Market state | daily breadth (% of eligible pairs up over 1, 7 and 30 days), median return, dispersion, BTC vs median altcoin | day d uses candles closed by d 00:00 (T5, H5) |
| M2 Volatility | realised volatility over 1, 7 and 30 days per pair and market-wide; band edges from an **expanding** window of past Development data | H5 |
| M3 Liquidity | P1 universe size, entries and exits, turnover | the fixed universe files |
| M4 Correlation | rolling 30-day correlation to BTC and to the median coin | H5 |
| M5 Regimes | as defined in R1–R6 | k chosen on [2024-01-01, 2024-07-01); labels from 2024-07-01; monthly refit; anchor alignment; `UNKNOWN`; no imputation |
| M6 Survivorship lens | M1–M4 with and without the later-delisted series | — |

**Details that follow from v1.2:**
- **Start of each feature:** a feature starts only once its lookback exists **inside the research period**. A 30-day feature therefore first exists on 2024-01-31. The December 2023 warm-up is **not** used (T3).
- **Holdout:** entry cut t < 2026-10-01 16:00 UTC. It is **not opened** in MI in any form. Under v1.2 there is **no opening path at all** (H7); opening needs Protocol v1.3.
- **No future quantity is computed:** no returns after d, no labels, no MFE or MAE.
- **Scenarios:** every statistic is reported for P1, S50k and S250k. Regime models are fitted on P1; S50k and S250k get separate models for reporting only.
- **Saved with every regime label:** the model id, the training window, the scaler parameters, the centroids, the anchor mapping, and the `DEFINITION_DRIFT` flag.

## Acceptance before results are shown

| | |
|---|---|
| A1 | Destructive future overwrite: every MI value and `regime_asof` for day d is unchanged |
| A2 | Segment guard (`tests/test_segment_loader.py`: **32/32 pass, 16/16 planted mutants killed**, v0.10.8) |
| A3 | 0 entries or label starts after the cut; 0 outcome intervals crossing a boundary |
| A4 | As-known regimes: a mutant that relabels the past with a later model must fail |
| A5 | Mutants for each block. Then a ZIP with code, outputs, sha256 and commit, and a **stop for review** |
