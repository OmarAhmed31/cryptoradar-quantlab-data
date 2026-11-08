# Market Intelligence — Development, v0.11.2 (documentation fix to v0.11.1)

**Scope:** Protocol v1.2 FIXED (sha256 `18d5ddcf…d969`, tag `protocol-v1.2`), MI plan v0.3.1. Development only. Descriptive only.


**v0.11.2 change (documentation only):** §2 said 400,686 skipped post-Development universe lines *per file*. The correct figure, matching `PACK_MANIFEST.json`, is **133,562 per file, 400,686 in total across the three files**. Code, inputs, outputs and the protocol are unchanged: every file in this folder except this report is byte-identical to `dev_v0.11.1/`.

**Runtime note for reproduction:** `tests/test_mi.py` took 42 s with a peak memory of ~600 MB here (2 CPUs). A1 reruns the full pipeline for every destroyed day, so a slower machine can take several minutes. `lab/mi.py` alone takes about 25 s.

## 1. Regime runs are now counted on the calendar (your finding is confirmed)

v0.11 dropped the `UNKNOWN` days **before** counting runs. That merged separate periods into one run, and counted "flips" between days that were not adjacent.

The new `calendar_runs()` works like this:
- The labels are placed on every calendar day.
- **`UNKNOWN`, `NO_MODEL` and a missing day break a run.**
- A run is a block of consecutive calendar days with the same known state.
- The flip rate is computed only over **adjacent calendar-day pairs where both days are known**, and its denominator is reported.

| P1 | v0.11 (wrong) | **v0.11.1** |
|---|---|---|
| Mean run length | 13.8 days | **6.8 calendar days** (median **3**; 49 runs) |
| Flip rate | 7.0% | **2.1%**: 6 direct state changes out of **288** adjacent known-day pairs |
| Runs by state | — | S1: 17 runs, mean 4.4 days, max 20 · **S2: 27 runs, mean 8.8, max 41** · S3: 5 runs, mean 3.8, max 11 |

**Reading:** the market rarely jumps straight from one state to another (6 times). **Most runs end with an `UNKNOWN` phase** in between. S50k and S250k give the same picture: mean runs of 6.8 and 6.5 days, and a flip rate of 2.1% for both.

**Only `regime_summary.json` changed.** Every other output is **byte-identical** to v0.11: all `mi_daily_*`, all `regimes_asof_*`, all models and the stability files. The one exception is `mi_meta.json`: its "series" field now counts the 382 series present in the Development pack instead of every name (615).

## 2. Development-only inputs: what is read, exactly

**MI now reads only the Development pack** (`out/market_intelligence/dev_pack_v1`), built by `lab/mi_dev_pack.py`. `lab/mi.py` refers to no other input, and a test checks this.

What the slicer reads from the full files:

| Source | Read |
|---|---|
| Hourly files (time-sorted) | Read line by line, **stopping at the first candle that does not close by 2025-09-01 00:00 UTC**. That one boundary line is the only post-Development line read, and only its timestamp field is compared |
| Universe files (sorted by series, then day) | Every line is scanned, but **only the `day` field is compared**. Lines with day ≥ 2025-09-01 are skipped without parsing any other field (133,562 lines per file; 400,686 in total across the three files) |

**Pack contents:**
- 382 series, 4,096,814 hourly rows, last candle starting 2025-08-31 23:00 UTC;
- 171,755 universe rows per scenario;
- per-file sha256 in `PACK_MANIFEST.json`.

The MI outputs computed from the pack are **byte-identical** to the v0.11 outputs. So the wording now is: "post-Development data never entered MI; the slicer scanned the universe lines' `day` field and stopped the hourly files at the boundary."

## 3. Tests (`tests/test_mi.py`: **20/20 pass**; 8 from before plus 12 new)

| New test | What it checks |
|---|---|
| A2b | The loader itself drops candles after Development, even if a pack contained one |
| A4 ×3 | k and the silhouettes equal a recomputation on [2024-01-01, 2024-07-01) only (R2) |
| A6 ×5 | Synthetic cases (`UNKNOWN` breaks a run; a missing day breaks a run; exact flip numerator and denominator), plus an independent recount for P1, S50k and S250k |
| A7 ×3 | The pack has no post-Development candle and no post-Development universe day; `mi.py` references no input outside the pack |

**Mutants: 14 planted, 14 killed** (`mi_mutation_results.json`). This includes the v0.11 run bug itself (RG4), a non-adjacent flip rate (RG5), and reading the full files instead of the pack (PK1, PK2).
- PK2 is killed by a crash: the full-file path has no delisted series.
- MI6 (the loader keeps post-Development candles) and RG3 (k chosen on all of Development) survived the first rerun, because they had no effect on this pack's data. A2b and the R2 recomputation now kill them.

`tests/test_segment_loader.py`: still 32/32.

## 4. Independent reproduction (no other file needed)

```
unzip <this zip>; cd repro
python3 -I lab/mi.py out/mi_check          # ~25 s; uses repro/out/market_intelligence/dev_pack_v1
python3 -I tests/test_mi.py                 # 20/20
sha256sum -c ../FILES_SHA256.txt            # (from the zip root)
```

The pack is inside `repro/` (145 MB). Requirements: Python 3, pandas, numpy, scikit-learn and scipy.

## 5. Unchanged findings (from v0.11)

- The median coin's 30-day return was **−3.3%**.
- BTC beat the median altcoin by **+9.6 points** per 30 days.
- The median correlation to BTC was **0.63**.
- Survivorship: excluding the later-delisted coins makes breadth look **+0.8 points** better.
- Regime counts: S1 75, S2 237, S3 19 and `UNKNOWN` 96 days.
- k = 3, with no drift in P1.
