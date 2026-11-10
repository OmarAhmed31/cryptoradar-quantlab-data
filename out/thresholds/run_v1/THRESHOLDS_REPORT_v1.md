# Threshold derivation: the one run (2026-11-10). Report for review

## Governance

- **Rules applied:** plan v0.3.2 (sha256 `6a8d1880…4491`), code commit `7fa1337` (approved), run committed **before reading** (`02252ba`).
- **One run with RD4 PASS:** three executions with byte-identical output, `thresholds.json` sha256 `5dc38aa9…8c5f`:
  - in the repository;
  - in a copy with **489 outcome files corrupted, including all 20 attribution files**;
  - in an isolated directory (6 code files + the Development pack), with no network (`unshare -rn`).
- **Development only. No return, outcome or performance number was computed or read.**

## The 8 derived values (fixed; not to be changed)

| # | Value | Previous convention | Share kept | Population |
|---|---|---|---|---|
| E2 | range high ≤ **0.495** × the prior 90-day peak (≈ 50% below the peak) | 0.80 | 25.0% | H: 3,044,851 coin-hours |
| E3 | RVOL ≥ **7.97** | 2 | 25.0% | BO: 38,874 breakout bars |
| E4 | CLV ≥ **0.826** | 0.70 | 50.0% | BO |
| E5 | stop distance ≤ **34.1%** | 15% | 90.0% | BO |
| R1 | Bull if the 20-day EW return > **+6.78%** | +5% | 33.0% | D: 587 days |
| R2 | Bear if the 20-day EW return < **−10.19%** | −5% | 33.0% | D |
| R3 | Bear: RVOL ≥ **18.76** | 3 | 10.0% | BO |
| R4 | High Vol: stop distance ≤ **19.7%** | 8% | 50.0% | BO on 193 High-Vol days (10,614 bars) |

The share kept is exactly 10% for R3 here, so there were no tie effects.

**Information only:** 77 trend runs; median run length 4 days.

## Candidate-bar cascade (counts of candidate BO bars, NOT trades, NOT returns)

| Step | Candidate bars left |
|---|---|
| BO (all breakouts) | 38,874 |
| A1, tight range | 10,466 |
| A2 / E2, ≥ 50% below the peak | 3,173 |
| C, contraction | 3,013 |
| E3, RVOL ≥ 7.97 | 655 |
| E4, CLV ≥ 0.826 | 229 |
| Stronger than BTC over 24 hours | 221 |
| E5, stop ≤ 34% | 220 |
| **State actions** (Transition abstains; Bear needs RVOL ≥ 18.8 plus 7-day strength; High Vol stop ≤ 19.7%) | **64** |

## ⚠️ What this means for P1 (a structural fact, not a result)

- A completed trade needs a signal bar. So **the number of P1 trades cannot exceed 64** under these thresholds. It will be lower still, because of one position at a time (A1), one position per coin, NOT_EXECUTED cases, and the re-entry rule.
- **U7 needs ≥ 100 completed trades.** So **P1, as specified, would be INCONCLUSIVE with certainty.**
- This is known **from counts alone**: no return has been computed.
- Under the rules, **the thresholds are not changed**. Running P1 would only confirm an outcome already fixed by arithmetic.

**Options for the reviewer** (none is started):

| Option | What it means |
|---|---|
| **(a) Run P1 as specified** | INCONCLUSIVE is certain, so this spends effort for no information |
| **(b) Record now** | "Accumulation Breakout v0.1.3, as specified, is INCONCLUSIVE by construction on Development: at most 64 candidate signals < 100". The specification is closed **without** a simulation |
| **(c) A new, separately pre-registered design** | For example fewer stacked conditions, or a daily rather than hourly breakout, decided **from opportunity counts only, before any return is seen**. It would be logged in the experiment registry (U8 §6) as a second design, with this one recorded as the first |
