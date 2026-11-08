# Market Intelligence — Development (v0.11, 2026-11-08)

**Governance:**
- Protocol v1.2 FIXED (sha256 `18d5ddcf…d969`, tag `protocol-v1.2`), with MI plan v0.3.1.
- **Development only**, 2024-01-01 → 2025-08-31, 609 days. Validation and Final Holdout were not read; the Holdout has no opening path.
- **Descriptive only.** There is no strategy, entry, exit, label or P&L, and no future return anywhere.

## Acceptance

| Test | Result |
|---|---|
| A1 Destructive future overwrite (4 days, every MI value of all 6 tables and `regime_asof` of 3 scenarios) | **1020/1020 unchanged** |
| A2 Segment guard | A Validation candle in the MI input is refused. An MI statistic on a Validation day is refused. Loaded data runs 2024-01-01 00:00 → 2025-08-31 23:00. The guard is called for every output day |
| A3 Boundary | No forward, label or outcome column exists (0 label starts, 0 crossing intervals) |
| A4 As-known regimes | Every label comes from the model in force that day, trained only on earlier days. `NO_MODEL` until 2024-07-01 |
| A5 Mutants | **9 / 9 killed** (`mi_mutation_results.json`), listed below |

The 9 mutants:
- the day's own close used;
- the volatility window includes day d;
- the correlation looks one day ahead;
- the volatility band uses the full-period history;
- the next day's eligibility is used;
- the loader keeps post-Development candles;
- refits are trained on all of Development;
- the past is relabelled with the final model;
- k is chosen on all of Development.

`tests/test_mi.py`: 8/8 pass. `tests/test_segment_loader.py`: still 32/32.

## Definitions (fixed in code before any output was computed)

- **`close_asof(d)`:** the close of the last traded hour of day d-1, with no stale carry-forward.
- **Returns:** `r_k(d)` for k = 1, 7 and 30 days.
- **Volatility:** the std of hourly log returns over days d-w … d-1, needing at least 50% of the hours.
- **Correlation:** over the 30 days d-29 … d, needing at least 20 pairs.
- **Aggregates:** taken over the series eligible on day d, and only when at least 20 series contribute.
- **Volatility band:** the percentile of today's market volatility among **prior** Development days only (at least 60 of them). LOW below ⅓, HIGH above ⅔.

## Main descriptive findings (P1; the S50k and S250k values are in `summary_by_scenario.json` and are within ±10% of P1)

| | |
|---|---|
| Eligible universe | median **239** series per day (range 205–269). Turnover 0.7% per day (491 entries, 478 exits) |
| Breadth over 7 days (share of coins up) | mean **44.9%** |
| Median coin, 30-day return | mean **−3.3%** |
| **BTC minus the median altcoin, 30-day return** | mean **+9.6 percentage points**. Over Development, the typical altcoin lagged BTC strongly |
| Median correlation to BTC, 30 days | **0.63** |
| Market volatility band (30-day) | LOW 140 · MID 277 · HIGH 102 · insufficient history 90 days |

**Survivorship lens (M6):** without the later-delisted coins, the market looks better than it really was:
- breadth over 7 days is **+0.8 points** higher (45.6% vs 44.9%);
- the 30-day median return is **+0.3 points** higher (−2.95% vs −3.29%);
- volatility is lower (1.07% vs 1.10% per hour).

So research on survivors alone would have been mildly optimistic.

## M5 regimes (P1)

- **k = 3**, chosen on [2024-01-01, 2024-07-01). Silhouette: 3 → 0.487, 4 → 0.318, 5 → 0.302, 6 → 0.319.
- There were 14 monthly refits. No `DEFINITION_DRIFT` in P1; the largest match distance was 1.994, against a limit of 2.0.
- Agreement with the previous model on its own window: median **98.4%**, minimum 84.7%.

**Anchor centroids** (original units; names follow the fixed rule "sorted by median 7-day return", with no meaning implied):

| State | breadth 7d | breadth 30d | median 7d return | dispersion 7d | market vol 7d | market vol 30d | median corr to BTC |
|---|---|---|---|---|---|---|---|
| S1 | 11% | 47% | −17.1% | 0.100 | 1.78% | 1.55% | 0.59 |
| S2 | 46% | 37% | −1.4% | 0.086 | 0.93% | 1.14% | 0.62 |
| S3 | 82% | 93% | +12.7% | 0.185 | 1.49% | 1.27% | 0.24 |

Read descriptively:
- **S1** is a broad sell-off.
- **S2** is quiet or drifting.
- **S3** is a broad rally with low correlation to BTC.

**Labelled days** (from 2024-07-01, 427 days):

| Label | Days | Share |
|---|---|---|
| S2 | 237 | 55% |
| S1 | 75 | 18% |
| S3 | 19 | 4% |
| UNKNOWN | 96 | 22% (82 ambiguous, 14 outliers) |

- Mean run: **13.8 days**. Flip rate: 7% of labelled days.
- The S50k and S250k models give the same picture. S50k flagged one refit as `DEFINITION_DRIFT` (M10). It is reported, not renamed.

## Limits that matter for the next phase

1. **S3 is rare: 19 days.** Anything conditioned on S3 would rest on a very small sample.
2. **UNKNOWN is 22%.** The ambiguity rule (0.80) is strict by design.
3. **No regime labels exist for 2024-01 to 2024-06.** That window was used to fit the first model.
4. Everything here is **in-sample description of Development only**. None of it says anything yet about Validation or the Holdout.

## Next (awaiting review)

Review and acceptance of these MI outputs, then the Feature Discovery plan (protocol-bound, Development only).
