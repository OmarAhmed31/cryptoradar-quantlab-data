"""Follow-up to archive_verify run 20261107T164416Z (same approved scope: listing + ONE delisted pair end check).

python3 -I lab/archive_verify_fix.py out/archive_verify/20261107T164416Z
 -> <that run>/fix_<ts>/
  1. earlier candle listings (2017-01..2020-12, UTC+8) for pairs whose first candle file hit the 2021-01 query bound
  2. listing for SSWP-USDT (announcement title says SSWP; the ledger row parsed SWSP from the body)
  3. delisted-pair end check, corrected: the run above downloaded the OLDEST file of the window (sort bug);
     here the LATEST trades + candles daily file of FITFI-USDT is downloaded and its last trade / candle time
     is compared with the delisting time 2024-08-30 08:00 UTC.
OKX limits found: monthly range <= 10 months (code 50077), daily range <= 10 days (code 50076).
"""
import sys, json, time, pathlib, csv, io, zipfile, datetime as dt, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import archive_verify as A
from decimal import Decimal as Dm

D = A.D


def main(run_dir):
    base = pathlib.Path(run_dir)
    out = base / ("fix_" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(base / "coverage" / "archive_coverage.csv")))
    L = A.Lister(out / "raw_calls.jsonl.gz")
    rep = {"base_run": base.name}

    # 1) earlier candle files for pairs that hit the lower query bound
    bound = [r["instrument"] for r in rows if r["candles_first_month_utc"].startswith("2020-12-31")]
    chunks, y = [], 2017
    while y <= 2020:
        for m in (1, 7):
            b = A.cn_month_start(y, m); e = A.cn_month_start(y + (m == 7), 1 if m == 7 else 7) - 1
            chunks.append((b, e))
        y += 1
    early = {p: [] for p in bound}
    for k in range(0, len(bound), 5):
        grp = bound[k:k + 5]
        for b, e in chunks:
            for g in L.split("2", grp, "monthly", b, e, 31 * D) or []:
                p = A.pair_of(g["filename"])
                if p in early:
                    early[p].append(int(g["dateTs"]))
    rep["early_candles"] = {p: {"first_month_utc": A.iso(min(v)) if v else "none before 2021-01 (UTC+8)", "files_2017_2020": len(v)} for p, v in early.items()}

    # 2) SSWP-USDT
    eff = int(dt.datetime(2025, 4, 29, 8, tzinfo=A.UTC).timestamp() * 1000)
    ss = {}
    for mod, tag in (("1", "trades"), ("2", "candles")):
        months = []
        y, m = 2021, 1
        while (y, m) <= (2026, 7):
            b = A.cn_month_start(y, m); y2, m2 = (y + (m + 5 - 1) // 12, (m + 5 - 1) % 12 + 1)
            e = A.cn_month_start(y2 + (m2 == 12), m2 % 12 + 1) - 1
            months += [int(g["dateTs"]) for g in (L.split(mod, ["SSWP-USDT"], "monthly", b, e, 31 * D) or [])]
            y, m = y2 + (m2 == 12), m2 % 12 + 1
        days = sorted(int(g["dateTs"]) for g in (L.split(mod, ["SSWP-USDT"], "daily", eff - 8 * D, eff + D, D) or []))
        ss[tag] = {"monthly_files": len(months), "first_month_utc": A.iso(min(months)) if months else "",
                   "last_month_utc": A.iso(max(months)) if months else "", "last_daily_start_utc": A.iso(days[-1]) if days else "",
                   "reaches_delisting": bool(days) and days[-1] + D >= eff}
    rep["SSWP-USDT"] = ss

    # 3) delisted-pair end check (corrected)
    pair, eff = A.DELIST_TEST, int(dt.datetime(2024, 8, 30, 8, tzinfo=A.UTC).timestamp() * 1000)
    rep["delist_check"] = {"pair": pair, "effective_delisting_utc": A.iso(eff), "files": []}
    for mod, tag in (("1", "trades"), ("2", "candles")):
        ents = L.split(mod, [pair], "daily", eff - 3 * D, eff + 3 * D, D) or []
        ents = sorted((g for g in ents if A.pair_of(g["filename"]) == pair), key=lambda g: int(g["dateTs"]))
        if not ents:
            rep["delist_check"]["files"].append({"kind": tag, "error": "no daily file"}); continue
        g = ents[-1]
        assert urllib.parse.urlparse(g["url"]).hostname == "static.okx.com"
        body, rec = A.http(g["url"], cap=A.MAX_BYTES)
        f = {"kind": tag, "file": g["filename"], "file_day_start_utc": A.iso(int(g["dateTs"])), "listed_days_after_window_start": [A.iso(int(x["dateTs"])) for x in ents], **rec}
        if body and not rec.get("truncated"):
            guard.atomic_write(out / g["filename"], body, mode="wb")
            z = zipfile.ZipFile(io.BytesIO(body))
            rr = list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))))
            tcol = "created_time" if tag == "trades" else "open_time"
            ts = sorted(int(r[tcol]) for r in rr)
            f.update(rows=len(rr), first_utc=A.iso(ts[0]) if ts else "", last_utc=A.iso(ts[-1]) if ts else "",
                     last_minus_delisting_minutes=round((ts[-1] - eff) / 60000, 1) if ts else None)
            if tag == "candles":
                traded = sorted(int(r["open_time"]) for r in rr if Dm(r["vol"]) > 0)
                f["last_traded_minute_utc"] = A.iso(traded[-1]) if traded else ""
                f["minutes_after_delisting"] = sum(1 for t in ts if t >= eff)
                f["traded_minutes_after_delisting"] = sum(1 for t in traded if t >= eff)
            else:
                f["trades_after_delisting"] = sum(1 for t in ts if t >= eff)
                f["last_trade_utc_exact"] = dt.datetime.fromtimestamp(ts[-1] / 1000, A.UTC).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        rep["delist_check"]["files"].append(f)
    L.close()
    rep["listing_calls"], rep["listing_errors"] = L.calls, L.errors
    guard.atomic_write(out / "fix_report.json", json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="archive-verify-fix", fsize_mb=100)
    main(sys.argv[1])
    guard.health("done")
