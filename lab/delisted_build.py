"""Delisted Assets Historical Dataset — download + build (expert approval of v0.6, 2026-11-07).

python3 -I lab/delisted_build.py                                 (download + build, GitHub Actions)
python3 -I lab/delisted_build.py --rebuild <prev_run> <raw_dir>   (offline rebuild from verified raw files, no network)
 -> out/delisted_dataset/<run>/
      raw/<PAIR>/<file>.zip          raw OKX files exactly as received (NOT committed: published as a release asset; sha256 in manifest)
      download_manifest.csv          every file: pair, kind, file period (UTC+8 label + UTC), url, downloaded_utc, bytes, sha256, status
      listing_calls.jsonl.gz         raw listing responses
      excluded/                      pairs removed by a ledger correction: evidence only, never an hourly file
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


def corrections():
    f = guard.LAB / "ledger_corrections" / "corrections.csv"
    return list(csv.DictReader(open(f, encoding="utf-8"))) if f.exists() else []


def load_pairs():
    """Pair list AFTER corrections: corrections.csv is applied here too (idempotent if the ledger already carries it),
    so a corrected-away pair can never enter the dataset. Returns (pairs, multi, excluded)."""
    C = [c for c in corrections() if c["locale"] == "ar"]
    pairs, multi, excluded = {}, collections.defaultdict(list), {}
    for r in csv.DictReader(open(guard.LAB / "out" / "ledger" / "ar" / "delisting_ledger.csv", encoding="utf-8")):
        orig = dict(r)
        for c in C:
            if r["slug"] == c["slug"] and r["instrument"] == c.get("instrument", r["instrument"]) and r.get(c["field"]) == c["old_value"]:
                r[c["field"]] = c["new_value"]
                r["correction"] = f"#{c['id']}: {c['field']} {c['old_value']} -> {c['new_value']}"
        hit = [c for c in C if c["slug"] == r["slug"] and c.get("instrument") in (orig["instrument"], r["instrument"])]
        if r["instrument"].endswith("-USDT") and orig["market_type"] in ("spot", "not_delisted") and r["market_type"] != "spot" and hit:
            c = hit[0]
            excluded[r["instrument"]] = {"pair": r["instrument"], "correction_id": c["id"], "change": f"{c['field']} {c['old_value']} -> {c['new_value']}",
                                         "reason": c["reason"], "approved_by": c["approved_by"], "evidence_raw_file": c["evidence_raw_file"],
                                         "evidence_raw_sha256": c["evidence_raw_sha256"], "ledger_effective_utc": r["effective_delisting_utc"]}
            continue
        if r["market_type"] == "spot" and r["instrument"].endswith("-USDT") and r["effective_delisting_utc"]:
            e = int(dt.datetime.strptime(r["effective_delisting_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=A.UTC).timestamp() * 1000)
            multi[r["instrument"]].append(e)
            pairs[r["instrument"]] = max(pairs.get(r["instrument"], 0), e)
    for x in excluded:
        pairs.pop(x, None)
    return pairs, {k: sorted(set(v)) for k, v in multi.items() if len(set(v)) > 1}, excluded


def month_states(eff_ms, have_month_ts, daily_n):
    """Per UTC+8 month Jan 2024 .. delisting month: monthly_file / daily_file(s) / before_first_file / MISSING_FILE"""
    em = dt.datetime.fromtimestamp(eff_ms / 1000, A.CN)
    ms_list = list(months_between(START, (em.year, em.month)))
    have = [ts for _, ts in ms_list if ts in have_month_ts]
    first = min(have) if have else None
    out = []
    for (y, m), ts in ms_list:
        if ts in have_month_ts:
            out.append((f"{y}-{m:02d}", "monthly_file"))
        elif (y, m) == (em.year, em.month):
            out.append((f"{y}-{m:02d}", "daily_fallback" if daily_n else "MISSING_FILE"))
        elif first is None or ts < first:
            out.append((f"{y}-{m:02d}", "before_first_file"))
        else:
            out.append((f"{y}-{m:02d}", "MISSING_FILE"))
    return out


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "delisted_dataset" / run
    for d in ("raw", "hourly"):
        (out / d).mkdir(parents=True, exist_ok=True)
    pairs, multi, excluded = load_pairs()
    rep = {"run": run, "excluded_by_correction": excluded, "dataset": "Delisted Assets Historical Dataset (NOT a complete historical market dataset)",
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

    build(out, out / "raw", pairs, excluded, man, rep, listing=(L.calls, L.errors))


def read_minutes(raw_pair_dir, pair):
    mins, dup, dup_conf = {}, 0, 0
    for fz in sorted(pathlib.Path(raw_pair_dir).glob("*.zip")):
        z = zipfile.ZipFile(fz)
        for r in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))):
            if r["instrument_name"] != pair:
                continue
            t = int(r["open_time"])
            v = (r["open"], r["high"], r["low"], r["close"], r["vol"], r["vol_ccy"])
            if t in mins:
                dup += 1
                dup_conf += int(mins[t] != v)
                continue
            mins[t] = v
    return mins, dup, dup_conf


def pair_stats(p, eff, mins, dup, dup_conf, mstate, mf):
    start_ms = A.cn_month_start(*START)
    ts_all = sorted(mins)
    before = [t for t in ts_all if start_ms <= t < eff]
    after = [t for t in ts_all if t >= eff]
    traded_after = [t for t in after if Dm(mins[t][4]) > 0]
    traded = [t for t in before if Dm(mins[t][4]) > 0]
    miss_min = sum((b - a) // M - 1 for a, b in zip(before, before[1:]) if b - a > M)
    span_h = ((before[-1] - before[0]) // H + 1) if before else 0
    st = collections.Counter(x for _, x in mstate)
    last_tr = max(traded) if traded else None
    last_act = max(traded + traded_after) if (traded or traded_after) else None
    q = {"pair": p, "effective_delisting_utc": A.iso(eff), "effective_delisting_utc8": utc8(eff),
         "files": len(mf), "files_ok": sum(int(x["ok"]) for x in mf), "files_failed": sum(1 - int(x["ok"]) for x in mf),
         "months_monthly_file": st["monthly_file"], "months_daily_fallback": st["daily_fallback"],
         "months_before_first_file": st["before_first_file"], "months_MISSING_FILE": st["MISSING_FILE"],
         "missing_months": ";".join(mo for mo, x in mstate if x == "MISSING_FILE"),
         "first_minute_utc": A.iso(before[0]) if before else "", "last_minute_before_delisting_utc": A.iso(before[-1]) if before else "",
         "last_traded_minute_before_delisting_utc": A.iso(last_tr) if last_tr else "",
         "last_trade_to_delisting_minutes": round((eff - last_tr) / M, 1) if last_tr else "",
         "META_last_actual_traded_minute_utc": A.iso(last_act) if last_act else "",
         "META_last_actual_trade_minutes_past_effective": round((last_act - eff) / M) if last_act is not None and last_act >= eff else 0,
         "minutes_in_range": len(before), "missing_minutes_inside": miss_min, "duplicate_minutes": dup, "duplicate_conflicting": dup_conf,
         "minutes_at_or_after_delisting_dropped": len(after), "traded_minutes_after_delisting_dropped": len(traded_after),
         "hours_span": span_h, "hours_with_trades": 0, "hours_without_trades_left_empty": 0}
    post = {"pair": p, "effective_delisting_utc": A.iso(eff), "minutes_after_in_files": len(after),
            "last_minute_in_files_utc": A.iso(max(after)) if after else "", "traded_minutes_after": len(traded_after),
            "first_traded_after_utc": A.iso(traded_after[0]) if traded_after else "",
            "last_traded_after_utc": A.iso(traded_after[-1]) if traded_after else "",
            "last_traded_after_minutes_past_effective": round((traded_after[-1] - eff) / M) if traded_after else "",
            "base_volume_after": str(sum(Dm(mins[t][4]) for t in traded_after)) if traded_after else "0"}
    return q, post, traded


def write_csv(path, rows):
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    guard.atomic_write(path, s.getvalue())


def build(out, raw_dir, pairs, excluded, man, rep, listing=None):
    """Offline. Only `pairs` (after corrections) are built into hourly/. Excluded pairs get evidence only, in excluded/."""
    (out / "hourly").mkdir(parents=True, exist_ok=True)
    (out / "excluded").mkdir(parents=True, exist_ok=True)
    keep = [x for x in man if x["pair"] in pairs]
    write_csv(out / "download_manifest.csv", keep)
    qual, post = [], []
    for p in sorted(pairs):
        eff = pairs[p]
        mf = [x for x in keep if x["pair"] == p]
        have = {int(dt.datetime.strptime(x["period_start_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=A.UTC).timestamp() * 1000)
                for x in mf if x["kind"] == "monthly" and int(x["ok"])}
        mstate = month_states(eff, have, sum(1 for x in mf if x["kind"] == "daily" and int(x["ok"])))
        mins, dup, dup_conf = read_minutes(pathlib.Path(raw_dir) / p, p)
        q, po, traded = pair_stats(p, eff, mins, dup, dup_conf, mstate, mf)
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
        q["hours_with_trades"] = len(rows)
        q["hours_without_trades_left_empty"] = q["hours_span"] - len(rows) if q["hours_span"] else 0
        qual.append(q); post.append(po)
    write_csv(out / "pair_quality.csv", qual)
    write_csv(out / "post_delisting_trades.csv", post)
    # excluded pairs: evidence only (no hourly file anywhere in the dataset)
    ex_rows = []
    for p, info in sorted(excluded.items()):
        mf = [x for x in man if x["pair"] == p]
        ev = dict(info, raw_files=len(mf), raw_files_sha256=[(x["file"], x["sha256"]) for x in mf])
        if mf and (pathlib.Path(raw_dir) / p).exists():
            eff = int(dt.datetime.strptime(info["ledger_effective_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=A.UTC).timestamp() * 1000)
            mins, dup, dup_conf = read_minutes(pathlib.Path(raw_dir) / p, p)
            q, po, _ = pair_stats(p, eff, mins, dup, dup_conf, [], mf)
            ev["trading_after_the_misparsed_date"] = po
        guard.atomic_write(out / "excluded" / f"{p}_evidence.json", json.dumps(ev, indent=1, ensure_ascii=False))
        ex_rows.append({"pair": p, "in_dataset": 0, "correction_id": info["correction_id"], "change": info["change"], "approved_by": info["approved_by"]})
    idx = [{"pair": q["pair"], "in_dataset": 1, "hourly_file": f"hourly/{q['pair']}.csv.gz", "effective_delisting_utc": q["effective_delisting_utc"]} for q in qual]
    write_csv(out / "dataset_index.csv", idx)
    if ex_rows:
        write_csv(out / "excluded" / "excluded_index.csv", ex_rows)
    files_on_disk = sorted(x.name for x in (out / "hourly").glob("*.csv.gz"))
    assert files_on_disk == sorted(f"{p}.csv.gz" for p in pairs), "hourly/ must contain exactly the dataset pairs"
    assert not any(f"{p}.csv.gz" in files_on_disk for p in excluded), "an excluded pair is in hourly/"
    rep.update(dataset_pairs=len(qual), excluded_pairs=sorted(excluded), hourly_files=len(files_on_disk),
               files=len(keep), files_ok=sum(int(x["ok"]) for x in keep), raw_bytes=sum(int(x["bytes"] or 0) for x in keep if int(x["ok"])),
               hours_built=sum(q["hours_with_trades"] for q in qual), hours_span=sum(q["hours_span"] for q in qual),
               hours_left_empty=sum(q["hours_without_trades_left_empty"] for q in qual),
               pairs_with_missing_file_months=sum(1 for q in qual if q["months_MISSING_FILE"]),
               pairs_with_no_data=sum(1 for q in qual if not q["minutes_in_range"]),
               pairs_traded_after_delisting=sum(1 for q in qual if q["traded_minutes_after_delisting_dropped"]),
               traded_minutes_after_delisting_dropped=sum(q["traded_minutes_after_delisting_dropped"] for q in qual),
               duplicate_conflicts=sum(q["duplicate_conflicting"] for q in qual))
    if listing:
        rep.update(listing_calls=listing[0], listing_errors=listing[1][:30])
    guard.atomic_write(out / "build_report.json", json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in rep.items() if k != "excluded_by_correction"}, indent=1, ensure_ascii=False)[:4000])


def rebuild(prev_run_dir, raw_dir):
    """Offline rebuild from an earlier run's raw files + manifest (no network). New run dir, earlier run untouched."""
    prev = pathlib.Path(prev_run_dir)
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_rebuild"
    out = guard.LAB / "out" / "delisted_dataset" / run
    out.mkdir(parents=True, exist_ok=True)
    pairs, multi, excluded = load_pairs()
    man = list(csv.DictReader(open(prev / "download_manifest.csv")))
    # verify every raw file against the manifest sha256 before using it
    import hashlib
    bad = []
    for x in man:
        f = pathlib.Path(raw_dir) / x["pair"] / x["file"]
        if int(x["ok"]) and (not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != x["sha256"]):
            bad.append(x["file"])
    assert not bad, f"raw files differ from manifest: {bad[:5]}"
    missing_pairs = sorted(p for p in pairs if not any(x["pair"] == p for x in man))
    assert not missing_pairs, f"pairs without downloaded files: {missing_pairs}"
    rep = {"run": run, "mode": "offline rebuild", "from_run": prev.name, "raw_files_verified_sha256": len(man),
           "dataset": "Delisted Assets Historical Dataset (NOT a complete historical market dataset)",
           "excluded_by_correction": excluded, "pairs_with_several_effective_dates_latest_used": {k: [A.iso(x) for x in v] for k, v in multi.items()}}
    build(out, raw_dir, pairs, excluded, man, rep)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rebuild":
        guard.install(write_dirs=("out", "state"), net_hosts=(), job="delisted-rebuild", cpu_s=6000, fsize_mb=200, mem_mb=4096)
        rebuild(sys.argv[2], sys.argv[3])
    else:
        guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="delisted-build",
                      cpu_s=6000, fsize_mb=200, mem_mb=4096)
        main()
    guard.health("done")
