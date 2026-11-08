"""WARM-UP data (December 2023) for point-in-time liquidity eligibility ONLY (expert approval after v0.10, option b).
These hours are NEVER part of the research period (which starts 2024-01-01 00:00 UTC) and never used for trading/results.

python3 -I lab/warmup_build.py <out_dir>
 -> <out_dir>/hourly/<SERIES>.csv.gz       rule-B 1H, 2023-12-01 00:00 <= t < 2024-01-01 00:00 UTC   (WARM-UP ONLY)
    <out_dir>/download_manifest.csv         url, time, sha256 for every file
    <out_dir>/jan2024_sha_crosscheck.csv     Jan-2024 files re-downloaded only to cover 2023-12-31 16:00-24:00 UTC,
                                            sha256 compared with the earlier v0.7.1 / v0.9 manifests
    <out_dir>/warmup_quality.csv
Series (public data only): Active pairs whose CURRENT listing began before 2024 (plan.csv start_basis = 2024-01-01),
Delisted v0.7.1 + Jan-2024 addendum pairs whose data starts at the 2024 start (they existed before 2024).
DASH/ZEC/ZEN: their current listing began in Nov 2025 -> no warm-up for it; their OLD listing gets warm-up as '#old_listing'.
Files: UTC+8 month 2023-12 (2023-11-30 16:00 -> 2023-12-31 16:00 UTC) + 2024-01 (for the last 8 UTC hours of Dec 31).
"""
import sys, csv, io, gzip, json, time, zipfile, pathlib, collections, urllib.parse, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import archive_verify as A
from decimal import Decimal as Dm

W0 = int(dt.datetime(2023, 12, 1, tzinfo=A.UTC).timestamp() * 1000)
W1 = int(dt.datetime(2024, 1, 1, tzinfo=A.UTC).timestamp() * 1000)
H, D = A.H, A.D
ACT = "out/active_dataset/final_42445808350_retry_42448392394"
DEL = "out/delisted_dataset/20261107T192715Z_rebuild"
ADD = "out/delisted_dataset/20261108T041031Z_jan2024_addendum"
OLD = {"DASH-USDT", "ZEC-USDT", "ZEN-USDT"}


def series_list():
    S = {}
    for r in csv.DictReader(open(guard.LAB / "out/active_dataset/plan/plan.csv")):
        if r["start_basis"].startswith("2024-01-01"):
            S[r["instrument"]] = r["instrument"]
    for src in (DEL, ADD):
        for q in csv.DictReader(open(guard.LAB / src / "pair_quality.csv")):
            if q["first_minute_utc"] == "2023-12-31 16:00":           # data starts at the dataset start -> existed before 2024
                key = q["pair"] + ("#old_listing" if src == ADD and q["pair"] in OLD else "")
                S[key] = q["pair"]
    return S


def old_sha():
    m = {}
    for src in (ACT, DEL, ADD):
        for x in csv.DictReader(open(guard.LAB / src / "download_manifest.csv")):
            if x.get("file", "").endswith("-2024-01.zip") and x.get("sha256"):
                m[x["file"]] = (x["sha256"], src)
    return m


def main(out_dir):
    out = pathlib.Path(out_dir); (out / "raw").mkdir(parents=True, exist_ok=True); (out / "hourly").mkdir(exist_ok=True)
    S = series_list()
    inst = sorted(set(S.values()))
    L = A.Lister(out / "listing_calls.jsonl.gz")
    want = {A.cn_month_start(2023, 12), A.cn_month_start(2024, 1)}
    files = collections.defaultdict(dict)
    for k in range(0, len(inst), 5):
        for g in L.split("2", inst[k:k + 5], "monthly", A.cn_month_start(2023, 12), A.cn_month_start(2024, 2) - 1, 31 * D) or []:
            p = A.pair_of(g["filename"])
            if p in inst and int(g["dateTs"]) in want:
                files[p][int(g["dateTs"])] = g
    L.close()
    man, xs = [], []
    OS = old_sha()
    for p in inst:
        (out / "raw" / p).mkdir(exist_ok=True)
        for ts in sorted(want):
            g = files[p].get(ts)
            if not g:
                man.append({"pair": p, "file": "", "period_start_utc": A.iso(ts), "url": "", "downloaded_utc": "", "status": "", "bytes": "",
                            "sha256": "", "ok": 0, "error": "MISSING_FILE (not in listing)"}); continue
            assert urllib.parse.urlparse(g["url"]).hostname == "static.okx.com"
            body, rec = A.http(g["url"], cap=200 * 1024 * 1024)
            ok = bool(body) and rec.get("status") == 200 and not rec.get("truncated")
            if ok:
                guard.atomic_write(out / "raw" / p / g["filename"], body, mode="wb")
            man.append({"pair": p, "file": g["filename"], "period_start_utc": A.iso(ts), "url": g["url"], "downloaded_utc": rec.get("requested_utc"),
                        "status": rec.get("status"), "bytes": rec.get("bytes"), "sha256": rec.get("sha256"), "ok": int(ok), "error": rec.get("error", "")})
            if g["filename"] in OS:
                xs.append({"file": g["filename"], "earlier_sha256": OS[g["filename"]][0], "earlier_source": OS[g["filename"]][1],
                           "now_sha256": rec.get("sha256"), "identical": int(OS[g["filename"]][0] == rec.get("sha256"))})
            time.sleep(0.1)
    qual = []
    for key, p in sorted(S.items()):
        mins = {}
        for fz in sorted((out / "raw" / p).glob("*.zip")):
            z = zipfile.ZipFile(fz)
            for x in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))):
                t = int(x["open_time"])
                if x["instrument_name"] == p and W0 <= t < W1:
                    mins.setdefault(t, (x["open"], x["high"], x["low"], x["close"], x["vol"], x["vol_ccy"]))
        ts = sorted(mins)
        traded = [t for t in ts if Dm(mins[t][4]) > 0]
        hrs = collections.defaultdict(list)
        for t in traded:
            hrs[t - t % H].append(mins[t])
        sio = io.StringIO(); cw = csv.writer(sio)
        cw.writerow(["ts_utc_ms", "hour_utc", "open", "high", "low", "close", "vol_base", "vol_quote", "traded_minutes", "WARMUP_ONLY"])
        for h in sorted(hrs):
            m = hrs[h]
            cw.writerow([h, A.iso(h), m[0][0], str(max(Dm(x[1]) for x in m)), str(min(Dm(x[2]) for x in m)), m[-1][3],
                         str(sum(Dm(x[4]) for x in m)), str(sum(Dm(x[5]) for x in m)), len(m), 1])
        guard.atomic_write(out / "hourly" / f"{key}.csv.gz", gzip.compress(sio.getvalue().encode(), mtime=0), mode="wb")
        miss = sum((b - a) // 60000 - 1 for a, b in zip(ts, ts[1:]) if b - a > 60000)
        qual.append({"series": key, "pair": p, "first_minute_utc": A.iso(ts[0]) if ts else "", "last_minute_utc": A.iso(ts[-1]) if ts else "",
                     "minutes": len(ts), "missing_minutes_inside": miss, "covers_full_december": int(bool(ts) and ts[0] == W0 and ts[-1] == W1 - 60000 and miss == 0),
                     "hours_with_trades": len(hrs)})
    for name, rows in (("download_manifest.csv", man), ("jan2024_sha_crosscheck.csv", xs), ("warmup_quality.csv", qual)):
        if rows:
            s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
            guard.atomic_write(out / name, s.getvalue())
    rep = {"purpose": "WARM-UP ONLY: December 2023 for point-in-time liquidity eligibility; never research data",
           "window_utc": [A.iso(W0), A.iso(W1)], "series": len(S), "instruments": len(inst), "files": len(man), "files_ok": sum(m["ok"] for m in man),
           "missing_files": sum(1 for m in man if not m["file"]), "jan2024_crosscheck": len(xs), "jan2024_identical": sum(x["identical"] for x in xs),
           "series_full_december": sum(q["covers_full_december"] for q in qual), "listing_errors": L.errors[:20]}
    guard.atomic_write(out / "warmup_report.json", json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="warmup-dec2023", cpu_s=6000, fsize_mb=300, mem_mb=4096)
    main(sys.argv[1])
    guard.health("done")
