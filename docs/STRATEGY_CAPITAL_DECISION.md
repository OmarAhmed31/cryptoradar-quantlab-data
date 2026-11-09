# Strategy gating-capital decision record (reviewer decision 2026-11-09, before any Development run)

**Bound to these files** (sha256):

| File | sha256 |
|---|---|
| `docs/STRATEGY_PLAN_v0.1.3.md` | `58e63af030efebe31ccf7d6746e603f4f3938f11ee17136e61dde0e9fc89a245` |
| `docs/STRATEGY_PLAN_REVIEW_RECORD.md` | `b5b683443b4f74190c0ff4b05f24a0f1c4937da73107ed2a3e94e798ba1bd7f4` |
| `lab/strategy.py` | `78345e00c9851b7a2954129afd886ae7bd7ca5bc8c2cb8b9b79db07b5da81328` |
| `tests/test_strategy.py` | `b41579e724aebe8bc944df5cf381aa1975ca6a157a34da2a474baa471a46e5a5` |
| `tests/run_strategy_mutants.py` | `23053da24faa430e0053fc01736cffc2c031c238c6a6c9ee6a1d41e7fa23c214` |

Recorded at commit `8ee1496` (+ this file).

| Capital | Use | Decision |
|---|---|---|
| **$10,000** | **S3 selection** and **S6 gate** | the primary criterion |
| **$1,000** | S6 robustness | **must pass S6 in full** |
| $100,000 | capacity and performance display only | not part of the selection and not part of PASS/FAIL |

## S3 (Development only)

- All 4 variants are computed at $10,000.
- Select the highest mean weekly net excess over B1 (P1, fee 0.10%).
- Tie → the lower mean turnover → Top 10.
- **$1,000 and $100,000 results are never used** for selection or for breaking a tie.
- **Validation is never used for selection.**

## S6 (Validation, the selected variant only)

At **both** $10,000 **and** $1,000:
- mean weekly net excess over B1 > 0;
- Newey-West one-sided p ≤ 0.05;
- block-bootstrap one-sided p ≤ 0.05;
- at the 0.10% fee per side;
- **and** a mean excess still > 0 at the 0.20% fee per side.

The test values and CIs are reported separately for each capital.

- **Overall PASS = PASS($10,000) AND PASS($1,000).**
- A PASS at $10,000 with a FAIL at $1,000 is **FAIL**. **The second-ranked variant is never tried as a substitute.**
- The `RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE` flag rule is unchanged.

## $100,000

The following are shown and never affect PASS/FAIL:
- the net return;
- trading costs;
- the liquidity and capacity limits;
- the uninvested cash share.

## Code mapping (no code change)

- `choose(summary, 10000)` implements S3.
- `gate(summary, sel, (10000, 1000, 100000))` returns PASS per capital. The overall result is the AND of the 10,000 and 1,000 entries, and 100,000 is reported only.

**Not changed:** Protocol v1.2. Validation and the Final Holdout are not opened by this record.
