"""Two approved steps after v0.8.1 (2026-11-08), one run:

 A) old7  — LISTING ONLY for the spot pairs of the 7 pre-2024 announcements whose dates were not parsed:
            is there a 1m-candle archive file for 2024-01 (UTC+8)? No download. Dates stay `unknown` unless proven.
 B) jan8  — ADD the 8 USDT spot pairs delisted in Jan 2024 (official announcement 2023-12-29) as a SEPARATE addendum
            to the Delisted Assets Historical Dataset (v0.7.1 is NOT modified). Cut = window START
            (cutoff_precision=window_start_conservative); window end kept. DASH/ZEC/ZEN: this is their OLD listing
            segment only; their current listing (Nov 2025) is never joined to it.

python3 -I lab/jan2024_checks.py
 -> out/jan2024_checks/<run>/old7/{listing_calls.jsonl.gz, old7_pairs.csv}
    out/delisted_dataset/<run>_jan2024_addendum/   (same layout as v0.7.1 + cutoff_meta.csv; raw/ -> release asset)
"""
import sys, json, time, csv, io, re, pathlib, datetime as dt, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import archive_verify as A
from lab import delisted_build as B

D = A.D
PRE = "out/ledger/ar_pre2024/delisting_ledger.csv"


def old7(out, L):
    rows = [r for r in csv.DictReader(open(guard.LAB / PRE, encoding="utf-8")) if r["market_type"] == "spot" and not r["effective_delisting_utc"]]
    pairs = sorted({r["instrument"] for r in rows})
    slug = {r["instrument"]: (r["slug"], r["announcement_utc"]) for r in rows}
    b, e = A.cn_month_start(2023, 6), A.cn_month_start(2024, 4) - 1           # 2023-06 .. 2024-03 (10 months, UTC+8)
    got = {p: set() for p in pairs}
    for k in range(0, len(pairs), 5):
        for g in L.split("2", pairs[k:k + 5], "monthly", b, e, 31 * D) or []:
            p = A.pair_of(g["filename"])
            if p in got:
                d = dt.datetime.fromtimestamp(int(g["dateTs"]) / 1000, A.CN)
                got[p].add(f"{d.year}-{d.month:02d}")
    res = []
    for p in pairs:
        ms = sorted(got[p])
        res.append({"instrument": p, "announcement_slug": slug[p][0], "announcement_utc": slug[p][1],
                    "archive_months_2023-06_to_2024-03_utc8": ";".join(ms), "last_archive_month_utc8": ms[-1] if ms else "",
                    "has_2024-01_file": int("2024-01" in ms), "has_any_2024_file": int(any(m >= "2024-01" for m in ms)),
                    "effective_delisting_utc": "unknown",
                    "conclusion": ("REVIEW: archive has a 2024 file -> read the announcement for the execution date" if any(m >= "2024-01" for m in ms)
                                   else ("archive gives no evidence of data inside the research window (last file " + ms[-1] + ")" if ms
                                         else "no archive file 2023-06..2024-03"))})
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
    guard.atomic_write(out / "old7_pairs.csv", s.getvalue())
    return {"pairs": len(res), "with_2024_01_file": sum(r["has_2024-01_file"] for r in res), "with_any_2024_file": sum(r["has_any_2024_file"] for r in res),
            "review": [r["instrument"] for r in res if r["has_any_2024_file"]]}


def jan8(run, L):
    rows = [r for r in csv.DictReader(open(guard.LAB / PRE, encoding="utf-8"))
            if r["market_type"] == "spot" and r["instrument"].endswith("-USDT") and r["effective_delisting_utc"] >= "2024-01-01"]
    out = guard.LAB / "out" / "delisted_dataset" / f"{run}_jan2024_addendum"
    (out / "raw").mkdir(parents=True, exist_ok=True)
    pairs, meta = {}, []
    for r in rows:
        eff = int(dt.datetime.strptime(r["effective_delisting_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=A.UTC).timestamp() * 1000)
        pairs[r["instrument"]] = eff
        m = re.search(r"window (\S+ \S+) -> (\S+ \S+) UTC", r["note"])
        meta.append({"pair": r["instrument"], "effective_delisting_utc": r["effective_delisting_utc"], "window_start_utc": m.group(1) if m else "",
                     "window_end_utc": m.group(2) if m else "", "cutoff_precision": "window_start_conservative",
                     "listing_segment": ("OLD listing (ends Jan 2024); current listing Nov 2025 is separate and NOT joined" if r["instrument"] in ("DASH-USDT", "ZEC-USDT", "ZEN-USDT") else "only listing"),
                     "announcement_slug": r["slug"], "announcement_utc": r["announcement_utc"], "raw_file": r["raw_file"], "raw_sha256": r["raw_sha256"]})
    man = []
    for p, eff in sorted(pairs.items()):
        (out / "raw" / p).mkdir(exist_ok=True)
        b = A.cn_month_start(*B.START)
        ents = L.split("2", [p], "monthly", b, A.cn_month_start(2024, 2) - 1, 31 * D) or []
        for g in ents:
            if A.pair_of(g["filename"]) != p or int(g["dateTs"]) > eff:
                continue
            assert urllib.parse.urlparse(g["url"]).hostname == "static.okx.com"
            body, rec = A.http(g["url"], cap=A.MAX_BYTES)
            ok = bool(body) and rec.get("status") == 200 and not rec.get("truncated")
            if ok:
                guard.atomic_write(out / "raw" / p / g["filename"], body, mode="wb")
            man.append({"pair": p, "kind": "monthly", "file": g["filename"], "period_start_utc8": B.utc8(int(g["dateTs"])),
                        "period_start_utc": A.iso(int(g["dateTs"])), "listed_sizeMB": g.get("sizeMB"), "url": g["url"],
                        "downloaded_utc": rec.get("requested_utc"), "status": rec.get("status"), "bytes": rec.get("bytes"),
                        "sha256": rec.get("sha256"), "ok": int(ok), "error": rec.get("error", "")})
    rep = {"run": out.name, "dataset": "Delisted Assets Historical Dataset — Jan 2024 addendum (v0.7.1 unchanged)",
           "source_ledger": PRE, "pairs": sorted(pairs)}
    B.build(out, out / "raw", pairs, {}, man, rep)
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(meta[0].keys())); w.writeheader(); w.writerows(sorted(meta, key=lambda x: x["pair"]))
    guard.atomic_write(out / "cutoff_meta.csv", s.getvalue())
    return {"addendum_dir": str(out.relative_to(guard.LAB)), "pairs": len(pairs), "files": len(man), "files_ok": sum(m["ok"] for m in man)}


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "jan2024_checks" / run / "old7"
    out.mkdir(parents=True, exist_ok=True)
    L = A.Lister(out / "listing_calls.jsonl.gz")
    rep = {"run": run, "old7": old7(out, L), "jan8": jan8(run, L)}
    L.close()
    rep["listing_calls"], rep["listing_errors"] = L.calls, L.errors[:20]
    guard.atomic_write(out.parent / "report.json", json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="jan2024-checks", fsize_mb=100)
    main()
    guard.health("done")
