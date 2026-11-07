"""Delisted Assets Historical Dataset — download + build (expert approval of v0.6, 2026-11-07).

python3 -I lab/delisted_build.py
 -> out/delisted_dataset/<run>/
      raw/<PAIR>/<file>.zip          raw OKX files exactly as received (NOT committed: published as a release asset; sha256 in manifest)
      download_manifest.csv          every file: pair, kind, file period (UTC+8 label + UTC), url, downloaded_utc, bytes, sha256, status
      listing_calls.jsonl.gz         raw listing responses
      hourly/<PAIR>.csv.gz           1H candles, UTC, built ONLY from minutes with vol > 0, strictly before the delisting time
      pair_quality.csv               per pair: files, gaps, duplicates, minutes after delisting dropped, hours available / without trades
      build_report.json

Scope: the 142 global delisted USDT spot pairs (ledger, corrections applied), 1m candles (module 2), from Jan 2024
(UTC+8 month) up to each pair's effective delisting time. Nothing else.
Rules (expert): raw kept + sha256 + url + time; UTC+8 label kept next to UTC; hour = traded minutes only;
cut at delisting; an hour without trades is NOT created; a missing file/month is recorded as missing data,
never as a month without trading. No research use.
"""
import sys, json, time, gzip, csv, io, zipfile, pathlib, collections, datetime as dt, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import archive_verify as A
from decimal import Decimal as Dm

D, H, M = A.D, A.H, 60000
START = (2024, 1)                      # UTC+8 month


def utc8(ms):
    return dt.datetime.fromtimestamp(ms / 1000, A.CN).strftime("%Y-%m-%d %H:%M")


def months_between(a, b):
    """UTC+8 month starts (ms) from month a=(y,m) to month b=(y,m) inclusive"""
    y, m = a
    while (y, m) <= b:
        yield (y, m), A.cn_month_start(y, m)
        y, m = y + (m == 12), m % 12 + 1


def load_pairs():
    pairs, multi = {}, collections.defaultdict(list)
    for r in csv.DictReader(open(guard.LAB / "out" / "ledger" / "ar" / "delisting_ledger.csv", encoding="utf-8")):
        if r["market_type"] == "spot" and r["instrument"].endswith("-USDT") and r["effective_delisting_utc"]:
            e = int(dt.datetime.strptime(r["effective_delisting_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=A.UTC).timestamp() * 1000)
            multi[r["instrument"]].append(e)
            pairs[r["instrument"]] = max(pairs.get(r["instrument"], 0), e)
    return pairs, {k: sorted(set(v)) for k, v in multi.items() if len(set(v)) > 1}


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "delisted_dataset" / run
    for d in ("raw", "hourly"):
        (out / d).mkdir(parents=True, exist_ok=True)
    pairs, multi = load_pairs()
    rep = {"run": run, "dataset": "Delisted Assets Historical Dataset (NOT a complete historical market dataset)",
           "pairs": len(pairs), "pairs_with_several_effective_dates_latest_used": {k: [A.iso(x) for x in v] for k, v in multi.items()}}
    L = A.Lister(out / "listing_calls.jsonl.gz")
    names = sorted(pairs)
    eff_month = {p: (dt.datetime.fromtimestamp(pairs[p] / 1000, A.CN).year, dt.datetime.fromtimestamp(pairs[p] / 1000, A.CN).month) for p in names}

    # ---- listing (monthly, 10-month windows, 5 pairs per call)
    monthly = {p: {} for p in names}
    last = max(eff_month.values())
    wins, cur = [], START
    while cur <= last:
        y, m = cur
        ey, em = y + (m - 1 + 9) // 12, (m - 1 + 9) % 12 + 1
        wins.append((A.cn_month_start(y, m), A.cn_month_start(ey + (em == 12), em % 12 + 1) - 1))
        cur = (ey + (em == 12), em % 12 + 1)
    for k in range(0, len(names), 5):
        grp = names[k:k + 5]
        for b, e in wins:
            if all(A.cn_month_start(*eff_month[p]) < b for p in grp):
                continue
            for g in L.split("2", grp, "monthly", b, e, 31 * D) or []:
                p = A.pair_of(g["filename"])
                if p in monthly:
                    monthly[p][int(g["dateTs"])] = g

    # ---- plan per pair: monthly files Jan 2024 .. delisting month; daily fallback for a missing delisting-month file
    plan, month_state = {p: [] for p in names}, {p: [] for p in names}
    for p in names:
        ms_list = list(months_between(START, eff_month[p]))
        have = [ts for _, ts in ms_list if ts in monthly[p]]
        first = min(have) if have else None
        for (y, m), ts in ms_list:
            if ts in monthly[p]:
                plan[p].append(("monthly", monthly[p][ts])); month_state[p].append((f"{y}-{m:02d}", "monthly_file"))
            elif (y, m) == eff_month[p]:
                month_state[p].append((f"{y}-{m:02d}", "daily_fallback"))
            elif first is None or ts < first:
                month_state[p].append((f"{y}-{m:02d}", "before_first_file"))
            else:
                month_state[p].append((f"{y}-{m:02d}", "MISSING_FILE"))
        if (f"{eff_month[p][0]}-{eff_month[p][1]:02d}", "daily_fallback") in month_state[p]:
            b = A.cn_month_start(*eff_month[p])
            got = []
            t = b
            while t <= pairs[p]:
                e = min(t + 9 * D - 1, pairs[p])
                got += L.split("2", [p], "daily", t, e, D) or []
                t += 9 * D
            for g in sorted({int(x["dateTs"]): x for x in got if A.pair_of(x["filename"]) == p}.values(), key=lambda x: int(x["dateTs"])):
                if int(g["dateTs"]) <= pairs[p]:
                    plan[p].append(("daily", g))
            if not any(k == "daily" for k, _ in plan[p]):
                month_state[p] = [(mo, "MISSING_FILE" if s_ == "daily_fallback" else s_) for mo, s_ in month_state[p]]

    # ---- download
    man = []
    for p in names:
        (out / "raw" / p).mkdir(exist_ok=True)
        for kind, g in plan[p]:
            guard.check_stop()
            url = g["url"]
            assert urllib.parse.urlparse(url).hostname == "static.okx.com"
            body, rec = A.http(url, cap=A.MAX_BYTES)
            ok = bool(body) and rec.get("status") == 200 and not rec.get("truncated")
            if ok:
                guard.atomic_write(out / "raw" / p / g["filename"], body, mode="wb")
            man.append({"pair": p, "kind": kind, "file": g["filename"], "period_start_utc8": utc8(int(g["dateTs"])),
                        "period_start_utc": A.iso(int(g["dateTs"])), "listed_sizeMB": g.get("sizeMB"), "url": url,
                        "downloaded_utc": rec.get("requested_utc"), "status": rec.get("status"), "bytes": rec.get("bytes"),
                        "sha256": rec.get("sha256"), "ok": int(ok), "error": rec.get("error", "")})
            time.sleep(0.15)
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(man[0].keys())); w.writeheader(); w.writerows(man)
    guard.atomic_write(out / "download_manifest.csv", s.getvalue())
    L.close()

    # ---- build hourly + quality
    start_ms = A.cn_month_start(*START)
    qual = []
    for p in names:
        eff = pairs[p]
        mins, dup, dup_conf = {}, 0, 0
        for fz in sorted((out / "raw" / p).glob("*.zip")):
            z = zipfile.ZipFile(fz)
            for r in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))):
                if r["instrument_name"] != p:
                    continue
                t = int(r["open_time"])
                v = (r["open"], r["high"], r["low"], r["close"], r["vol"], r["vol_ccy"])
                if t in mins:
                    dup += 1
                    dup_conf += int(mins[t] != v)
                    continue
                mins[t] = v
        ts_all = sorted(mins)
        before = [t for t in ts_all if start_ms <= t < eff]
        after = [t for t in ts_all if t >= eff]
        traded_after = sum(1 for t in after if Dm(mins[t][4]) > 0)
        traded = [t for t in before if Dm(mins[t][4]) > 0]
        miss_min = 0
        for a, b in zip(before, before[1:]):
            if b - a > M:
                miss_min += (b - a) // M - 1
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
        guard.atomic_write(out / "hourly" / f"{p}.csv.gz", gzip.compress(sio.getvalue().encode()), mode="wb")
        span_h = ((before[-1] - before[0]) // H + 1) if before else 0
        st = collections.Counter(s for _, s in month_state[p])
        mf = [x for x in man if x["pair"] == p]
        last_tr = max(traded) if traded else None
        qual.append({"pair": p, "effective_delisting_utc": A.iso(eff), "effective_delisting_utc8": utc8(eff),
                     "files_planned": len(plan[p]), "files_ok": sum(x["ok"] for x in mf), "files_failed": sum(1 - x["ok"] for x in mf),
                     "months_monthly_file": st["monthly_file"], "months_daily_fallback": st["daily_fallback"],
                     "months_before_first_file": st["before_first_file"], "months_MISSING_FILE": st["MISSING_FILE"],
                     "missing_months": ";".join(mo for mo, s in month_state[p] if s == "MISSING_FILE"),
                     "first_minute_utc": A.iso(before[0]) if before else "", "last_minute_before_delisting_utc": A.iso(before[-1]) if before else "",
                     "last_traded_minute_utc": A.iso(last_tr) if last_tr else "",
                     "last_trade_to_delisting_minutes": round((eff - last_tr) / M, 1) if last_tr else "",
                     "minutes_in_range": len(before), "missing_minutes_inside": miss_min, "duplicate_minutes": dup, "duplicate_conflicting": dup_conf,
                     "minutes_at_or_after_delisting_dropped": len(after), "traded_minutes_after_delisting": traded_after,
                     "hours_span": span_h, "hours_with_trades": len(rows), "hours_without_trades_left_empty": span_h - len(rows) if span_h else 0})
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(qual[0].keys())); w.writeheader(); w.writerows(qual)
    guard.atomic_write(out / "pair_quality.csv", s.getvalue())
    rep.update(listing_calls=L.calls, listing_errors=L.errors[:30], files=len(man), files_ok=sum(x["ok"] for x in man),
               raw_bytes=sum(x["bytes"] or 0 for x in man if x["ok"]),
               pairs_with_missing_file_months=sum(1 for q in qual if q["months_MISSING_FILE"]),
               pairs_with_no_data=sum(1 for q in qual if not q["minutes_in_range"]),
               pairs_traded_after_delisting=sum(1 for q in qual if q["traded_minutes_after_delisting"]),
               duplicate_conflicts=sum(q["duplicate_conflicting"] for q in qual))
    guard.atomic_write(out / "build_report.json", json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="delisted-build",
                  cpu_s=6000, fsize_mb=200, mem_mb=4096)
    main()
    guard.health("done")
