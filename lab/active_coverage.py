"""Active Assets Historical Coverage — Phase B, LISTING ONLY (expert approval after v0.7.1, 2026-11-07).

python3 -I lab/active_coverage.py
 -> out/active_coverage/<run>/
      instruments_spot_raw.json      raw /api/v5/public/instruments?instType=SPOT (current listing state, listTime)
      listing_calls.jsonl.gz         raw market-data-history listing responses (url, time, status, sha256, body)
      active_coverage.csv            per live USDT spot pair: listing state, listTime, first/last 1m-candle archive month,
                                     months available / missing inside, coverage per year 2024/2025/2026, latest daily file
      coverage_report.json
No candle or trade file is downloaded. All live SPOT USDT pairs are audited, so the public repo holds no
CryptoRadar-derived list (the top-150 overlap and the 38 signal coins are joined LOCALLY, outside this repo).
OKX archive months/days are UTC+8; both UTC+8 labels and UTC are written.
"""
import sys, json, time, pathlib, csv, io, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import archive_verify as A
from lab import okx_fetch as OF

D = A.D
FIRST = (2019, 12)          # earliest 1m-candle archive month seen so far (v0.6)


def utc8(ms):
    return dt.datetime.fromtimestamp(ms / 1000, A.CN).strftime("%Y-%m-%d %H:%M") if ms is not None else ""


def mlabel(ms):
    d = dt.datetime.fromtimestamp(ms / 1000, A.CN)
    return f"{d.year}-{d.month:02d}"


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "active_coverage" / run
    out.mkdir(parents=True, exist_ok=True)
    j, err = OF.get("https://www.okx.com/api/v5/public/instruments?instType=SPOT", tries=3)
    if OF._RAW["last"]:
        guard.atomic_write(out / "instruments_spot_raw.json", json.dumps(OF._RAW["last"]))
    assert j, f"instruments failed: {err}"
    inst = {x["instId"]: x for x in j["data"] if x["instId"].endswith("-USDT")}
    names = sorted(inst)
    now = dt.datetime.now(A.CN)
    # 10-month windows (UTC+8) from FIRST to the current month
    wins, (y, m) = [], FIRST
    while (y, m) <= (now.year, now.month):
        ey, em = y + (m - 1 + 9) // 12, (m - 1 + 9) % 12 + 1
        wins.append((A.cn_month_start(y, m), A.cn_month_start(ey + (em == 12), em % 12 + 1) - 1))
        y, m = ey + (em == 12), em % 12 + 1
    L = A.Lister(out / "listing_calls.jsonl.gz")
    months = {p: set() for p in names}
    daily = {p: [] for p in names}
    d_end = int(now.timestamp() * 1000)
    for k in range(0, len(names), 5):
        grp = names[k:k + 5]
        for b, e in wins:
            for g in L.split("2", grp, "monthly", b, min(e, d_end), 31 * D) or []:
                p = A.pair_of(g["filename"])
                if p in months:
                    months[p].add(int(g["dateTs"]))
        for g in L.split("2", grp, "daily", d_end - 9 * D, d_end, D) or []:      # is the archive still being produced?
            p = A.pair_of(g["filename"])
            if p in daily:
                daily[p].append(int(g["dateTs"]))
    L.close()
    rows = []
    for p in names:
        x = inst[p]
        ms_ = sorted(months[p])
        lt = int(x["listTime"]) if x.get("listTime") else None
        miss = []
        if ms_:
            a = dt.datetime.fromtimestamp(ms_[0] / 1000, A.CN); z = dt.datetime.fromtimestamp(ms_[-1] / 1000, A.CN)
            y, m = a.year, a.month
            have = {mlabel(t) for t in ms_}
            while (y, m) <= (z.year, z.month):
                if f"{y}-{m:02d}" not in have:
                    miss.append(f"{y}-{m:02d}")
                y, m = y + (m == 12), m % 12 + 1
        per_year = {yr: sum(1 for t in ms_ if mlabel(t).startswith(str(yr))) for yr in (2024, 2025, 2026)}
        lt_month = mlabel(lt) if lt else ""
        rows.append({"instrument": p, "state_now": x.get("state", ""), "listTime_utc": A.iso(lt) if lt else "",
                     "listTime_utc8": utc8(lt) if lt else "",
                     "first_archive_month_utc8": mlabel(ms_[0]) if ms_ else "", "first_archive_month_start_utc": A.iso(ms_[0]) if ms_ else "",
                     "last_archive_month_utc8": mlabel(ms_[-1]) if ms_ else "", "n_archive_months": len(ms_),
                     "missing_months_inside": len(miss), "missing_month_list": ";".join(miss),
                     "months_2024": per_year[2024], "months_2025": per_year[2025], "months_2026": per_year[2026],
                     "latest_daily_file_utc8": utc8(max(daily[p])) if daily[p] else "",
                     "first_month_vs_listTime": ("same" if ms_ and lt and mlabel(ms_[0]) == lt_month else
                                                 ("archive_later" if ms_ and lt and ms_[0] > lt else ("archive_earlier" if ms_ and lt else ""))),
                     "status": "no_archive" if not ms_ else ("gaps" if miss else "continuous"),
                     "source_listing_state": "OKX /api/v5/public/instruments?instType=SPOT (instruments_spot_raw.json)",
                     "source_archive": "OKX /api/v5/public/market-data-history module=2 (listing_calls.jsonl.gz)"})
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    guard.atomic_write(out / "active_coverage.csv", s.getvalue())
    import collections
    rep = {"run": run, "scope": "listing only, all live OKX SPOT USDT pairs, 1m candle archive (module 2)",
           "usdt_pairs": len(rows), "states": dict(collections.Counter(r["state_now"] for r in rows)),
           "status": dict(collections.Counter(r["status"] for r in rows)),
           "first_month_vs_listTime": dict(collections.Counter(r["first_month_vs_listTime"] for r in rows)),
           "listing_calls": L.calls, "listing_errors": L.errors[:30], "listing_error_count": len(L.errors),
           "windows_utc8": [[utc8(b), utc8(e)] for b, e in wins]}
    guard.atomic_write(out / "coverage_report.json", json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com",), job="active-coverage", cpu_s=3000)
    main()
    guard.health("done")
