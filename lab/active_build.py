"""Active Assets Historical Dataset — plan, sharded download + build, merge (expert approval after v0.8.1, 2026-11-08).

  python3 -I lab/active_build.py plan  <active_coverage_run_dir> <out_dir>
  python3 -I lab/active_build.py shard <plan.csv> <i> <n> <out_dir>
  python3 -I lab/active_build.py merge <out_dir> <shard_dir>...

Universe: ALL live OKX SPOT USDT pairs (public list; no CryptoRadar-derived set is used or written).
Rules (expert):
  * CURRENT listing only (the archive run of segments.csv flagged is_current_listing); earlier runs are never used.
  * start = max(2024-01-01 00:00 UTC, current listing start). Current listing start = listTime when it is a real
    date inside the current run; if listTime is the 2021-01-29 placeholder or before 2024, the run began before
    2024 and start = 2024-01-01 00:00 UTC.
  * end = end of the last complete monthly file (UTC+8 month 2026-10 -> 2026-10-31 16:00 UTC), exclusive.
  * 1H candle = minutes with vol > 0 only (rule B); an hour with no trade is NOT created.
  * every raw file kept exactly as received with url / time / sha256; missing files recorded as missing data.
"""
import sys, json, time, gzip, csv, io, zipfile, pathlib, collections, hashlib, datetime as dt, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import archive_verify as A
from decimal import Decimal as Dm

D, H, M = A.D, A.H, 60000
R0 = int(dt.datetime(2024, 1, 1, tzinfo=A.UTC).timestamp() * 1000)
END_MONTH = (2026, 10)                      # UTC+8, last complete monthly file at audit time
PLACEHOLDER = "2021-01-29 08:08"


def ym_next(y, m):
    return y + (m == 12), m % 12 + 1


def ms_utc(s):
    return int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=A.UTC).timestamp() * 1000)


def utc8(ms):
    return dt.datetime.fromtimestamp(ms / 1000, A.CN).strftime("%Y-%m-%d %H:%M")


def write_csv(path, rows):
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    guard.atomic_write(path, s.getvalue())


# ------------------------------------------------------------------ plan
def plan(run_dir, out_dir):
    run, out = pathlib.Path(run_dir), pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cov = {r["instrument"]: r for r in csv.DictReader(open(run / "active_coverage.csv"))}
    cur = {}
    for s in csv.DictReader(open(run / "segments.csv")):
        if s["is_current_listing"] == "1":
            cur[s["instrument"]] = s
    end = A.cn_month_start(*ym_next(*END_MONTH))
    rows = []
    for p in sorted(cov):
        c, s = cov[p], cur.get(p)
        assert s, f"{p}: no current listing run"
        seg_start = A.cn_month_start(*map(int, s["from_utc8"].split("-")))
        lt = c["listTime_utc"]
        if lt and not lt.startswith(PLACEHOLDER) and ms_utc(lt) >= seg_start - 31 * D:
            ls, basis = ms_utc(lt), "listTime"
        else:
            ls, basis = seg_start, ("current run start (listTime placeholder)" if lt.startswith(PLACEHOLDER) else "current run start")
        start = max(R0, ls)
        rows.append({"instrument": p, "start_utc": A.iso(start), "start_utc8": utc8(start),
                     "start_basis": "2024-01-01 (current listing began before 2024)" if start == R0 else basis,
                     "end_exclusive_utc": A.iso(end), "end_exclusive_utc8": utc8(end),
                     "current_run_utc8": f"{s['from_utc8']}..{s['to_utc8']}", "earlier_runs_excluded": int(s["of"]) - 1,
                     "listTime_utc": lt})
    write_csv(out / "plan.csv", rows)
    print(len(rows), "pairs planned ->", out / "plan.csv")


# ------------------------------------------------------------------ shard: list + download + build
def months_from(start_ms):
    d = dt.datetime.fromtimestamp(start_ms / 1000, A.CN)
    y, m = d.year, d.month
    while (y, m) <= END_MONTH:
        yield (y, m)
        y, m = ym_next(y, m)


def shard(plan_csv, i, n, out_dir):
    i, n = int(i), int(n)
    P = [r for k, r in enumerate(csv.DictReader(open(plan_csv))) if k % n == i]
    out = pathlib.Path(out_dir); (out / "raw").mkdir(parents=True, exist_ok=True); (out / "hourly").mkdir(exist_ok=True)
    L = A.Lister(out / f"listing_calls_shard{i}.jsonl.gz")
    want = {r["instrument"]: {A.cn_month_start(y, m) for y, m in months_from(ms_utc(r["start_utc"]))} for r in P}
    found = {p: {} for p in want}
    names = sorted(want)
    for k in range(0, len(names), 5):
        grp = names[k:k + 5]
        lo = min(min(want[p]) for p in grp)
        y, m = dt.datetime.fromtimestamp(lo / 1000, A.CN).year, dt.datetime.fromtimestamp(lo / 1000, A.CN).month
        while (y, m) <= END_MONTH:
            ey, em = y + (m - 1 + 9) // 12, (m - 1 + 9) % 12 + 1
            if (ey, em) > END_MONTH:
                ey, em = END_MONTH
            b, e = A.cn_month_start(y, m), A.cn_month_start(*ym_next(ey, em)) - 1
            for g in L.split("2", grp, "monthly", b, e, 31 * D) or []:
                p = A.pair_of(g["filename"])
                if p in found and int(g["dateTs"]) in want[p]:
                    found[p][int(g["dateTs"])] = g
            y, m = ym_next(ey, em)
    L.close()
    man, qual = [], []
    for r in P:
        p = r["instrument"]
        (out / "raw" / p).mkdir(exist_ok=True)
        for ts in sorted(want[p]):
            g = found[p].get(ts)
            if not g:
                man.append({"pair": p, "kind": "monthly", "file": "", "period_start_utc8": utc8(ts), "period_start_utc": A.iso(ts), "listed_sizeMB": "",
                            "url": "", "downloaded_utc": "", "status": "", "bytes": "", "sha256": "", "ok": 0, "error": "MISSING_FILE (not in listing)"})
                continue
            guard.check_stop()
            assert urllib.parse.urlparse(g["url"]).hostname == "static.okx.com"
            body, rec = A.http(g["url"], cap=200 * 1024 * 1024)
            ok = bool(body) and rec.get("status") == 200 and not rec.get("truncated")
            if ok:
                guard.atomic_write(out / "raw" / p / g["filename"], body, mode="wb")
            man.append({"pair": p, "kind": "monthly", "file": g["filename"], "period_start_utc8": utc8(ts), "period_start_utc": A.iso(ts),
                        "listed_sizeMB": g.get("sizeMB"), "url": g["url"], "downloaded_utc": rec.get("requested_utc"), "status": rec.get("status"),
                        "bytes": rec.get("bytes"), "sha256": rec.get("sha256"), "ok": int(ok), "error": rec.get("error", "")})
            time.sleep(0.1)
        qual.append(build_pair(out, p, r, [x for x in man if x["pair"] == p]))
    write_csv(out / f"download_manifest_shard{i}.csv", man)
    write_csv(out / f"pair_quality_shard{i}.csv", qual)
    print(json.dumps({"shard": i, "pairs": len(P), "files": len(man), "ok": sum(x["ok"] for x in man),
                      "missing_files": sum(1 for x in man if x["error"].startswith("MISSING"))}))


def build_pair(out, p, r, mf):
    start, end = ms_utc(r["start_utc"]), ms_utc(r["end_exclusive_utc"])
    mins, dup, dup_conf, other = {}, 0, 0, 0
    for fz in sorted((out / "raw" / p).glob("*.zip")):
        z = zipfile.ZipFile(fz)
        for x in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))):
            if x["instrument_name"] != p:
                other += 1; continue
            t = int(x["open_time"])
            v = (x["open"], x["high"], x["low"], x["close"], x["vol"], x["vol_ccy"])
            if t in mins:
                dup += 1; dup_conf += int(mins[t] != v); continue
            mins[t] = v
    ts = sorted(t for t in mins if start <= t < end)
    traded = [t for t in ts if Dm(mins[t][4]) > 0]
    miss = sum((b - a) // M - 1 for a, b in zip(ts, ts[1:]) if b - a > M)
    hrs = collections.defaultdict(list)
    for t in traded:
        hrs[t - t % H].append(mins[t])
    rows = []
    for h in sorted(hrs):
        ms_ = hrs[h]
        rows.append([h, A.iso(h), utc8(h), ms_[0][0], str(max(Dm(x[1]) for x in ms_)), str(min(Dm(x[2]) for x in ms_)),
                     ms_[-1][3], str(sum(Dm(x[4]) for x in ms_)), str(sum(Dm(x[5]) for x in ms_)), len(ms_)])
    sio = io.StringIO(); cw = csv.writer(sio)
    cw.writerow(["ts_utc_ms", "hour_utc", "hour_utc8", "open", "high", "low", "close", "vol_base", "vol_quote", "traded_minutes"])
    cw.writerows(rows)
    guard.atomic_write(out / "hourly" / f"{p}.csv.gz", gzip.compress(sio.getvalue().encode(), mtime=0), mode="wb")
    span = ((ts[-1] - ts[0]) // H + 1) if ts else 0
    first_tr = traded[0] if traded else None
    return {"pair": p, "start_utc": r["start_utc"], "start_basis": r["start_basis"], "end_exclusive_utc": r["end_exclusive_utc"],
            "current_run_utc8": r["current_run_utc8"], "earlier_runs_excluded": r["earlier_runs_excluded"],
            "months_planned": len(mf), "files_ok": sum(int(x["ok"]) for x in mf), "files_failed": sum(1 for x in mf if not int(x["ok"]) and x["file"]),
            "months_MISSING_FILE": sum(1 for x in mf if not x["file"]), "missing_months": ";".join(x["period_start_utc8"][:7] for x in mf if not x["file"]),
            "first_minute_utc": A.iso(ts[0]) if ts else "", "last_minute_utc": A.iso(ts[-1]) if ts else "",
            "first_traded_minute_utc": A.iso(first_tr) if first_tr else "",
            "minutes_in_range": len(ts), "missing_minutes_inside": miss, "duplicate_minutes": dup, "duplicate_conflicting": dup_conf,
            "rows_other_instrument": other, "minutes_outside_range_dropped": len(mins) - len(ts),
            "hours_span": span, "hours_with_trades": len(rows), "hours_without_trades_left_empty": span - len(rows) if span else 0}


# ------------------------------------------------------------------ merge + checks
def merge(out_dir, *shards):
    out = pathlib.Path(out_dir); (out / "hourly").mkdir(parents=True, exist_ok=True)
    man, qual = [], []
    for sd in shards:
        sd = pathlib.Path(sd)
        for f in sd.glob("download_manifest_shard*.csv"):
            man += list(csv.DictReader(open(f)))
        for f in sd.glob("pair_quality_shard*.csv"):
            qual += list(csv.DictReader(open(f)))
        for f in (sd / "hourly").glob("*.csv.gz"):
            guard.atomic_write(out / "hourly" / f.name, f.read_bytes(), mode="wb")
        for f in sd.glob("listing_calls_shard*.jsonl.gz"):
            guard.atomic_write(out / f.name, f.read_bytes(), mode="wb")
    man.sort(key=lambda x: (x["pair"], x["period_start_utc"])); qual.sort(key=lambda x: x["pair"])
    write_csv(out / "download_manifest.csv", man)
    write_csv(out / "pair_quality.csv", qual)
    write_csv(out / "dataset_index.csv", [{"pair": q["pair"], "in_dataset": 1, "hourly_file": f"hourly/{q['pair']}.csv.gz",
                                           "start_utc": q["start_utc"], "end_exclusive_utc": q["end_exclusive_utc"]} for q in qual])
    chk = checks(out)
    rep = {"dataset": "Active Assets Historical Dataset (current listings of live OKX SPOT USDT pairs; NOT the complete historical market)",
           "pairs": len(qual), "files_planned": len(man), "files_ok": sum(int(x["ok"]) for x in man),
           "files_failed": sum(1 for x in man if not int(x["ok"]) and x["file"]), "months_MISSING_FILE": sum(1 for x in man if not x["file"]),
           "raw_bytes": sum(int(x["bytes"] or 0) for x in man if int(x["ok"])), "hours_built": sum(int(q["hours_with_trades"]) for q in qual),
           "hours_span": sum(int(q["hours_span"]) for q in qual), "hours_left_empty": sum(int(q["hours_without_trades_left_empty"]) for q in qual),
           "duplicate_conflicts": sum(int(q["duplicate_conflicting"]) for q in qual), "pairs_with_missing_minutes": sum(1 for q in qual if int(q["missing_minutes_inside"])),
           "checks": chk}
    guard.atomic_write(out / "build_report.json", json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1)[:3000])
    return rep


def checks(out):
    idx = list(csv.DictReader(open(out / "dataset_index.csv")))
    Q = {q["pair"]: q for q in csv.DictReader(open(out / "pair_quality.csv"))}
    files = sorted(x.name for x in (out / "hourly").glob("*.csv.gz"))
    pr = []
    if files != sorted(f"{r['pair']}.csv.gz" for r in idx):
        pr.append("hourly/ != dataset_index")
    tot = outside = dup = bad = 0
    for r in idx:
        rows = list(csv.reader(io.StringIO(gzip.decompress((out / "hourly" / f"{r['pair']}.csv.gz").read_bytes()).decode())))[1:]
        s, e = ms_utc(r["start_utc"]), ms_utc(r["end_exclusive_utc"])
        ts = [int(x[0]) for x in rows]
        tot += len(rows)
        outside += sum(1 for t in ts if t + H <= s or t >= e)
        dup += len(ts) - len(set(ts))
        bad += sum(1 for a, b in zip(ts, ts[1:]) if b <= a)
        for x in rows:
            o, h, l, c, v = map(Dm, (x[3], x[4], x[5], x[6], x[7]))
            if not (l <= min(o, c) <= max(o, c) <= h) or v <= 0 or not 1 <= int(x[9]) <= 60:
                bad += 1
        if int(Q[r["pair"]]["hours_with_trades"]) != len(rows):
            pr.append(f"{r['pair']}: quality hours != rows")
    res = {"pairs": len(idx), "hourly_files": len(files), "rows": tot, "rows_outside_start_end": outside, "duplicate_hours": dup, "bad_rows": bad}
    if outside or dup or bad:
        pr.append("row checks failed")
    res["problems"] = pr[:20]; res["PASS"] = not pr
    guard.atomic_write(out / "dataset_checks.json", json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    cmd = sys.argv[1]
    net = ("www.okx.com", "static.okx.com") if cmd == "shard" else ()
    guard.install(write_dirs=("out", "state", "work"), net_hosts=net, job=f"active-{cmd}", cpu_s=18000, fsize_mb=500, mem_mb=6000)
    {"plan": plan, "shard": shard, "merge": merge}[cmd](*sys.argv[2:])
    guard.health("done")
