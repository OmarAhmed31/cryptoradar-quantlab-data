# Experiment 3 counts code: addendum v0.3 (A4 calendar rule; NOTHING computed on real data)

**v0.3 = v0.2** (sha256 `34d287ea…aac668`) **+ the reviewer's required A4 correction** (review of v0.36). Nothing else changed: A1, A2, A3, every threshold, every condition and the selection rule. v0.1 and v0.2 stay unchanged in the repository.

## A4 (corrected). D-D1 same-coin re-entry: the calendar rule, written explicitly

**The rule:** `window_start_date >= exit_date + 1 calendar day`, where exit_date is the UTC day of the exit.

- **An exit on day X, at any hour,** makes days X+1 … X+20 the first allowed range window, so **the earliest signal day is X+21, with the entry on X+22.**
- **Signal day X+20 is refused.**
- **The same coin only.** No new signal on that coin during the cooldown.
- **It is a fixed signal-management rule, not derived from data**, and the same in the counts and in P1.
- **The hourly designs are unchanged:** a new full 168-hour window after the exit (Spec §5.5).

**The exit day in the counts code** (`trade_windows` → exit reference):

| Exit | Exit day |
|---|---|
| time exit | the day of the **exit bar**. The fill lies inside that hour, so a fill in the 23:00 bar exits on that day, even though the bar ends at 00:00 the next day |
| delisting | the day of the cut |

In code: `reentry_from()` returns the UTC midnight after the exit day for D-D1, and the trade end for the hourly designs. It is used by `l_greedy` and by `l_worst` (calendar mode).

**About the example in the review, said plainly:** for an exit at 08:00 on day X, the v0.36 code already **allowed** signal day X+21. Its window starts at X+1 00:00, which is after X 08:00. The real difference was narrower:
- a delisting cut **exactly at 00:00** of day X: v0.36 allowed X+20, while the calendar rule requires X+21;
- an L_worst early exit at exactly 00:00.

The explicit calendar rule closes both, so v0.37 follows the addendum exactly in every case.

**Tests:**

| Test | What it checks |
|---|---|
| X15a | the window offset (D-20 … D-1) |
| **X15b** | **inside `l_greedy`:** exits at 00:00, 08:00, 12:00 and 23:00 on day X → same-coin signal X+20 refused (counted as `blocked_same_coin_window`), X+21 taken; another coin unaffected |
| X15c | `reentry_from` values (D-D1 midnight after the exit day; hourly = the trade end) |
| X15d | the exit day of a time exit in the 23:00 bar, and of a cut at 00:00 |
| X15e | `l_worst` with the calendar rule ≤ the exhaustive true minimum |
| X9 / X10a | 600 random cases, 200 of them with the calendar rule, against independent references |

**New planted defects:**
- **XM30:** the old rule, comparing with the exit time;
- **XM31:** the exit day taken from the trade end instead of the exit bar;
- **XM32:** `l_worst` without the calendar rule.

## Documentation fix

The `tests/test_exp3.py` header now points to addendum v0.3, not v0.1.

## Test status (synthetic data only)

See `out/exp3/precheck/`: `tests.json` and `mutants.json`. The frozen hashes are in `FROZEN_SHA256.txt`.
