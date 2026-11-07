"""LIMITED probe of the OKX official trade-history archive (approved scope only).

python3 -I lab/archive_probe.py
 -> out/archive_probe/<run>/  listing_<yyyymm>.json (raw), sample/<file> (ONE file), probe_report.json

Scope approved by the expert (2026-11-07):
  * file listings for 2024-01, 2024-07, 2025-06 only
  * download ONE single-day file only, for a pair known to be delisted later and trading that day
  * inspect content (price, size, time, trade id), coverage, provenance (url, time, sha256)
  * NO monthly archives, NO candle building, NO research use, NO spot/futures mixing
Hosts: www.okx.com (listing API) + static.okx.com (file CDN). Nothing else.
"""
import sys, json, time, pathlib, hashlib, zipfile, io, csv, re, urllib.request, urllib.error, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard

MONTHS = ("202401", "202407", "202506")
TARGET_DAY = "2024-07-15"            # inside 2024-07 listing
# delisted later (global ledger, spot, effective 2024-08-23 / 2024-08-30) -> tried in this order, ONE download max
CANDIDATES = ("FITFI-USDT", "GARI-USDT", "XPR-USDT", "AKITA-USDT", "TAMA-USDT", "WNCG-USDT", "TUP-USDT", "THG-USDT")
LATER_DELISTED_CHECK = {"202506": ("X-USDT", "BSV-USDT", "GOG-USDT", "DIA-USDT", "BONE-USDT", "OXT-USDT"),
                        "202407": CANDIDATES}
MAX_BYTES = 200 * 1024 * 1024
UA = {"User-Agent": "CryptoRadar-QuantLab/0.1 (research, read-only)"}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def http(url, cap=20 * 1024 * 1024):
    rec = {"url": url, "requested_utc": now()}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            body = r.read(cap + 1)
            rec.update(status=r.status, final_url=r.geturl(), bytes=len(body), truncated=len(body) > cap,
                       sha256=hashlib.sha256(body).hexdigest(), content_type=r.headers.get("Content-Type"))
            return body[:cap], rec
    except urllib.error.HTTPError as e:
        rec.update(status=e.code, error=f"http {e.code}")
    except Exception as e:
        rec.update(status=None, error=f"{type(e).__name__}: {str(e)[:150]}")
    return None, rec


def names(obj):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ("filename", "file_name", "name") and isinstance(v, str):
                out.append(obj)
                break
        for v in obj.values():
            out += names(v)
    elif isinstance(obj, list):
        for v in obj:
            out += names(v)
    return out


def fname(d):
    for k in ("fileName", "filename", "file_name", "name"):
        if k in d:
            return d[k]


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "archive_probe" / run
    (out / "sample").mkdir(parents=True, exist_ok=True)
    rep = {"run": run, "scope": "limited probe, expert-approved 2026-11-07", "listings": {}, "download": None}
    files_by_month = {}
    for m in MONTHS:
        url = f"https://www.okx.com/priapi/v5/broker/public/orderRecord?t={int(time.time()*1000)}&path=cdn/okex/traderecords/trades/monthly/{m}"
        body, rec = http(url)
        if body:
            guard.atomic_write(out / f"listing_{m}.json", body, mode="wb")
        items = []
        try:
            items = names(json.loads(body)) if body else []
        except Exception as e:
            rec["parse_error"] = str(e)[:150]
        fl = sorted({fname(i) for i in items if fname(i)})
        files_by_month[m] = {fname(i): i for i in items if fname(i)}
        days = sorted({d for f in fl for d in re.findall(r"\d{4}-\d{2}-\d{2}", f)})
        spot_usdt = [f for f in fl if re.match(r"^[A-Z0-9]+-USDT-trades-", f)]
        insts = sorted({f.split("-trades-")[0] for f in fl if "-trades-" in f})
        later = {p: sum(1 for f in fl if f.startswith(p + "-trades-")) for p in LATER_DELISTED_CHECK.get(m, ())}
        rep["listings"][m] = {**rec, "files": len(fl), "instruments": len(insts), "spot_usdt_files": len(spot_usdt),
                              "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
                              "days": len(days), "sample_names": fl[:10],
                              "later_delisted_pairs_files_in_month": later,
                              "item_fields": sorted(items[0].keys()) if items else []}
        time.sleep(1.0)

    # ---- ONE download
    month = TARGET_DAY[:4] + TARGET_DAY[5:7]
    pick = None
    for p in CANDIDATES:
        for f, meta in files_by_month.get(month, {}).items():
            if f.startswith(p + "-trades-") and TARGET_DAY in f:
                pick = (p, f, meta); break
        if pick:
            break
    if not pick:
        rep["download"] = {"skipped": f"no file for candidates on {TARGET_DAY} in listing"}
    else:
        p, f, meta = pick
        url = f"https://static.okx.com/cdn/okex/traderecords/trades/monthly/{month}/{f}"
        body, rec = http(url, cap=MAX_BYTES)
        d = {"pair": p, "file": f, "listing_meta": meta, **rec}
        if body and not rec.get("truncated"):
            guard.atomic_write(out / "sample" / f, body, mode="wb")
            d.update(inspect(body, p))
        rep["download"] = d
    guard.atomic_write(out / "probe_report.json", json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1, ensure_ascii=False)[:6000])


def inspect(body, pair):
    r = {}
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
        r["zip_test"] = z.testzip() or "ok"
        r["members"] = [(i.filename, i.file_size) for i in z.infolist()]
        raw = z.read(z.infolist()[0]).decode("utf-8", "replace")
    except Exception as e:
        return {"zip_error": str(e)[:150]}
    rows = list(csv.reader(io.StringIO(raw)))
    head, data = rows[0], [x for x in rows[1:] if x]
    r["header"] = head
    r["rows"] = len(data)
    r["first_rows"] = data[:3]
    low = [h.strip().lower() for h in head]

    def col(*keys):
        for k in keys:
            for i, h in enumerate(low):
                if k in h:
                    return i
    it, ip, isz, its, iinst = col("trade_id", "tradeid", "id"), col("price", "px"), col("size", "sz", "qty"), col("time", "ts"), col("instrument", "inst")
    r["columns_found"] = {"trade_id": it, "price": ip, "size": isz, "time": its, "instrument": iinst}
    if iinst is not None:
        r["instruments_in_file"] = sorted({x[iinst] for x in data})[:5]
    if its is not None:
        ts = sorted(int(float(x[its])) for x in data)
        f = lambda t: dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        r["first_trade_utc"], r["last_trade_utc"] = f(ts[0]), f(ts[-1])
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        r["max_gap_minutes"] = round(max(gaps) / 60000, 1) if gaps else None
        hrs = {t // 3600000 for t in ts}
        r["distinct_utc_hours_with_trades"] = len(hrs)
        r["day_boundary_hint"] = "UTC+8 day" if f(ts[0])[11:13] in ("16", "17") else ("UTC day" if f(ts[0])[11:13] in ("00", "01") else "unclear")
    if it is not None:
        ids = sorted(int(x[it]) for x in data if x[it].isdigit())
        if ids:
            r["trade_id_min"], r["trade_id_max"], r["trade_id_unique"] = ids[0], ids[-1], len(set(ids))
            r["trade_id_span"] = ids[-1] - ids[0] + 1
            r["trade_id_missing_inside_span"] = r["trade_id_span"] - len(set(ids))
    if ip is not None:
        px = [float(x[ip]) for x in data]
        r["price_min"], r["price_max"], r["non_positive_prices"] = min(px), max(px), sum(1 for v in px if v <= 0)
    if isz is not None:
        r["size_sum"] = round(sum(float(x[isz]) for x in data), 6)
    return r


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="archive-probe", fsize_mb=250)
    main()
    guard.health("done")
