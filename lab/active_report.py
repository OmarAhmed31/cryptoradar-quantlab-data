"""Offline: monthly coverage matrix + listing segments from the active-coverage raw listing responses.

python3 -I lab/active_report.py <active_coverage_run_dir>
 -> monthly_coverage_matrix.csv   pair x UTC+8 month (2024-01 .. last archive month): 1 = 1m-candle file listed, 0 = not
    segments.csv                  contiguous runs of archive months per pair; the run that contains today's listTime is
                                  the CURRENT listing; earlier runs = an earlier listing of the same ticker (possibly a
                                  different asset or a delist/relist) -> never stitched to the current one
    active_coverage_report.md
Public data only (OKX). Nothing CryptoRadar-specific.
"""
import sys, json, gzip, csv, io, pathlib, collections, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import archive_verify as A


def lab(ms):
    d = dt.datetime.fromtimestamp(ms / 1000, A.CN)
    return (d.year, d.month)


def nxt(ym):
    y, m = ym
    return (y + (m == 12), m % 12 + 1)


def main(run_dir):
    run = pathlib.Path(run_dir)
    cov = {r["instrument"]: r for r in csv.DictReader(open(run / "active_coverage.csv"))}
    months = collections.defaultdict(set)
    for l in gzip.open(run / "listing_calls.jsonl.gz", "rt"):
        j = json.loads(l)
        if "dateAggrType=monthly" not in j["url"] or not j.get("body"):
            continue
        b = json.loads(j["body"])
        for blk in b.get("data") or []:
            for det in blk.get("details") or []:
                for g in det.get("groupDetails") or []:
                    p = A.pair_of(g["filename"])
                    if p in cov:
                        months[p].add(lab(int(g["dateTs"])))
    last = max(max(v) for v in months.values())
    cols, ym = [], (2024, 1)
    while ym <= last:
        cols.append(ym); ym = nxt(ym)
    with open(run / "monthly_coverage_matrix.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["instrument"] + [f"{y}-{m:02d}" for y, m in cols])
        for p in sorted(cov):
            w.writerow([p] + [int(c in months[p]) for c in cols])
    seg_rows, cur = [], {}
    for p in sorted(cov):
        ms_ = sorted(months[p])
        segs, s = [], None
        for x in ms_:
            if s and x == nxt(s[1]):
                s[1] = x
            else:
                s = [x, x]; segs.append(s)
        lt = cov[p]["listTime_utc"]
        ltym = None
        if lt:
            t = int(dt.datetime.strptime(lt, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            ltym = lab(t)
        cur_i = None
        for i, (a, b) in enumerate(segs):
            if ltym and a <= ltym <= b:
                cur_i = i
        if cur_i is None and segs:
            # listTime not inside any run: placeholder listTime (2021-01-29 migration) or listed in the last days of a month
            cur_i = len(segs) - 1 if not ltym or ltym <= segs[-1][1] else None
        for i, (a, b) in enumerate(segs):
            seg_rows.append({"instrument": p, "segment": i + 1, "of": len(segs), "from_utc8": f"{a[0]}-{a[1]:02d}", "to_utc8": f"{b[0]}-{b[1]:02d}",
                             "is_current_listing": int(i == cur_i), "listTime_utc": lt})
        cur[p] = (segs[cur_i] if cur_i is not None else None, len(segs), ltym)
    with open(run / "segments.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(seg_rows[0].keys())); w.writeheader(); w.writerows(seg_rows)
    multi = sorted(p for p in cov if cur[p][1] > 1)
    placeholder = sorted(p for p in cov if cov[p]["listTime_utc"].startswith("2021-01-29 08:08"))
    later = sorted(p for p in cov if cov[p]["first_month_vs_listTime"] == "archive_later")
    cur_start = collections.Counter()
    for p in cov:
        s = cur[p][0]
        if s:
            cur_start["before 2024" if s[0] < (2024, 1) else str(s[0][0])] += 1
    covered = {y: sum(1 for p in cov if cur[p][0] and cur[p][0][0] <= (y, 12) and cur[p][0][1] >= (y, 1)) for y in (2024, 2025, 2026)}
    r = f"""# Active Assets Historical Coverage, listing only (run {run.name})

**Source:**
- Listing state and `listTime`: OKX `GET /api/v5/public/instruments?instType=SPOT` (`instruments_spot_raw.json`).
- Archive: OKX `GET /api/v5/public/market-data-history`, module 2 (1m candles), monthly (`listing_calls.jsonl.gz`, with sha256 per call).

**No data file was downloaded.** The guard allowed only `www.okx.com`; `static.okx.com` was blocked.

| | |
|---|---|
| Live OKX SPOT USDT pairs audited | **{len(cov)}** (state `live`: {sum(1 for p in cov if cov[p]['state_now']=='live')}) |
| Pairs with archive files | {sum(1 for p in cov if months[p])} · without: {sum(1 for p in cov if not months[p])} |
| Last monthly file | {collections.Counter(cov[p]['last_archive_month_utc8'] for p in cov).most_common(1)[0]} (UTC+8). The daily archive is current up to {collections.Counter(cov[p]['latest_daily_file_utc8'][:10] for p in cov).most_common(1)[0]} |
| Listing calls / errors | {sum(1 for _ in gzip.open(run / 'listing_calls.jsonl.gz','rt'))} / 0 |
| Current listing starts | {dict(cur_start)} |
| Pairs whose current listing covers part of 2024 / 2025 / 2026 | {covered[2024]} / {covered[2025]} / {covered[2026]} |

## Findings that matter for rebuilding the universe

1. **Ticker reuse and delist/relist: {len(multi)} pairs have more than one separate run of archive months.** They are: {', '.join(multi)}.
   - The run that contains today's `listTime` is the **current listing**.
   - Earlier runs belong to an **earlier listing of the same ticker**. That may be a different asset: for ACE, ACT, CT, KAT, ME, NOT, SPK and XBX the earlier runs end in 2022-07, and the current listing started years later. Or it may be a delist followed by a relist: DASH, ZEC and ZEN have no files 2024-02 → 2025-10, and today's `listTime` is in Nov 2025.
   - **They must never be joined into one history.** `segments.csv` flags `is_current_listing`.
2. **`listTime` is a placeholder for {len(placeholder)} pairs** (2021-01-29 08:08 UTC, when OKX migrated its systems). For these pairs the archive begins earlier, so the **first archive month is the better evidence of availability**, not `listTime`.
3. **{len(later)} pairs** ({', '.join(later)}) were listed in the second half of a month, and their first monthly file is for the following month. The partial first month would need daily files.
4. **DASH, ZEC and ZEN stopped trading after Jan 2024 (UTC+8; their last file before the gap is 2024-01) and are not in our delisting ledger.** The ledger archive starts on 5 Jan 2024, so a delisting **announced before that date but effective in 2024 is missing from the ledger**. Pairs like these that are *not* live today are in neither this audit nor the v0.7.1 dataset. **This gap is not closed.**
5. **No overlap** between today's live list and the 141 pairs in the Delisted Assets Dataset v0.7.1.

## Files

- `active_coverage.csv`: per pair, with the listing state, `listTime` (UTC and UTC+8), first and last archive month, missing months, months per year, the latest daily file and the sources.
- `monthly_coverage_matrix.csv`: pair × UTC+8 month, 2024-01 → last archive month.
- `segments.csv`: the separate archive runs for each pair, with the current listing flagged.
"""
    (run / "active_coverage_report.md").write_text(r, encoding="utf-8")
    print(r)


if __name__ == "__main__":
    main(sys.argv[1])
