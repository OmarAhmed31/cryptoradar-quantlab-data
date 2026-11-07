# Active Assets Historical Coverage, listing only (run 20261107T201140Z)

**Source:**
- Listing state and `listTime`: OKX `GET /api/v5/public/instruments?instType=SPOT` (`instruments_spot_raw.json`).
- Archive: OKX `GET /api/v5/public/market-data-history`, module 2 (1m candles), monthly (`listing_calls.jsonl.gz`, with sha256 per call).

**No data file was downloaded.** The guard allowed only `www.okx.com`; `static.okx.com` was blocked.

| | |
|---|---|
| Live OKX SPOT USDT pairs audited | **466** (state `live`: 466) |
| Pairs with archive files | 466 · without: 0 |
| Last monthly file | ('2026-10', 466) (UTC+8). The daily archive is current up to ('2026-11-06', 466) |
| Listing calls / errors | 940 / 0 |
| Current listing starts | {'before 2024': 156, '2025': 57, '2024': 49, '2026': 204} |
| Pairs whose current listing covers part of 2024 / 2025 / 2026 | 205 / 262 / 466 |

## Findings that matter for rebuilding the universe

1. **Ticker reuse and delist/relist: 11 pairs have more than one separate run of archive months.** They are: ACE-USDT, ACT-USDT, CT-USDT, DASH-USDT, KAT-USDT, ME-USDT, NOT-USDT, SPK-USDT, XBX-USDT, ZEC-USDT, ZEN-USDT.
   - The run that contains today's `listTime` is the **current listing**.
   - Earlier runs belong to an **earlier listing of the same ticker**. That may be a different asset: for ACE, ACT, CT, KAT, ME, NOT, SPK and XBX the earlier runs end in 2022-07, and the current listing started years later. Or it may be a delist followed by a relist: DASH, ZEC and ZEN have no files 2024-02 → 2025-10, and today's `listTime` is in Nov 2025.
   - **They must never be joined into one history.** `segments.csv` flags `is_current_listing`.
2. **`listTime` is a placeholder for 65 pairs** (2021-01-29 08:08 UTC, when OKX migrated its systems). For these pairs the archive begins earlier, so the **first archive month is the better evidence of availability**, not `listTime`.
3. **3 pairs** (JOE-USDT, MINA-USDT, OP-USDT) were listed in the second half of a month, and their first monthly file is for the following month. The partial first month would need daily files.
4. **DASH, ZEC and ZEN stopped trading after Jan 2024 (UTC+8; their last file before the gap is 2024-01) and are not in our delisting ledger.** The ledger archive starts on 5 Jan 2024, so a delisting **announced before that date but effective in 2024 is missing from the ledger**. Pairs like these that are *not* live today are in neither this audit nor the v0.7.1 dataset. **This gap is not closed.**
5. **No overlap** between today's live list and the 141 pairs in the Delisted Assets Dataset v0.7.1.

## Files

- `active_coverage.csv`: per pair, with the listing state, `listTime` (UTC and UTC+8), first and last archive month, missing months, months per year, the latest daily file and the sources.
- `monthly_coverage_matrix.csv`: pair × UTC+8 month, 2024-01 → last archive month.
- `segments.csv`: the separate archive runs for each pair, with the current listing flagged.
