"""LIMITED probe of the OKX official trade-history archive (approved scope only).

python3 -I lab/archive_probe.py
 -> out/archive_probe/<run>/  listing_<yyyymm>.json (raw), sample/<file> (ONE file), probe_report.json

Scope approved by the expert (2026-11-07):
  * file listings for 2024-01, 2024-07, 2025-06 only (official endpoint /api/v5/public/market-data-history;
    the older priapi listing returned 404 on 2026-11-07, see out/archive_probe/20261107T155922Z)
  * download ONE single-day file only, for a pair known to be delisted later and trading that day
  * inspect content (price, size, time, trade id), coverage, provenance (url, time, sha256)
  * NO monthly archives, NO candle building, NO research use, NO spot/futures mixing
Hosts: www.okx.com (listing API) + static.okx.com (file CDN). Nothing else.
"""
import sys, json, time, pathlib, hashlib, zipfile, io, csv, re, urllib.request, urllib.error, urllib.parse, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard

MONTHS = ("202401", "202407", "202506")
TARGET_DAY = "2024-07-15"            # inside 2024-07 listing
# delisted later (global ledger, spot, effective 2024-08-23 / 2024-08-30) -> tried in this order, ONE download max
CANDIDATES = ("FITFI-USDT", "GARI-USDT", "XPR-USDT", "AKITA-USDT", "TAMA-USDT", "WNCG-USDT", "TUP-USDT", "THG-USDT")
LATER_DELISTED_CHECK = {"202401": ('EM-USDT','HC-USDT','KAR-USDT','LET-USDT','MOVEZ-USDT','MRST-USDT'),
                        "202506": ("X-USDT", "BSV-USDT", "GOG-USDT", "DIA-USDT", "BONE-USDT", "OXT-USDT"),
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


def entries(obj):
    """every dict in the response that carries a download link"""
    out = []
    if isinstance(obj, dict):
        if any(isinstance(v, str) and v.startswith("http") for v in obj.values()):
            out.append(obj)
        for v in obj.values():
            out += entries(v)
    elif isinstance(obj, list):
        for v in obj:
            out += entries(v)
    return out


def link(d):
    return next(v for v in d.values() if isinstance(v, str) and v.startswith("http"))


def ms(day):
    return int(dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def mbounds(m):
    y, mo = int(m[:4]), int(m[4:])
    a = dt.datetime(y, mo, 1, tzinfo=dt.timezone.utc)
    b = dt.datetime(y + (mo == 12), mo % 12 + 1, 1, tzinfo=dt.timezone.utc)
    return int(a.timestamp() * 1000), int(b.timestamp() * 1000) - 1


API = "https://www.okx.com/api/v5/public/market-data-history"
MODULES = {"1": "trade history", "2": "1-minute candlestick"}


def listing(out, tag, module, insts, agg, begin, end):
    url = f"{API}?module={module}&instType=SPOT&instIdList={','.join(insts)}&dateAggrType={agg}&begin={begin}&end={end}"
    body, rec = http(url)
    if body:
        guard.atomic_write(out / f"listing_{tag}.json", body, mode="wb")
    ents, code = [], None
    try:
        j = json.loads(body) if body else {}
        code, rec["okx_msg"] = j.get("code"), j.get("msg")
        ents = entries(j.get("data"))
    except Exception as e:
        rec["parse_error"] = str(e)[:150]
    rec.update(okx_code=code, files=len(ents), entry_fields=sorted(ents[0].keys()) if ents else [],
               sample=ents[:4], links=[link(e) for e in ents][:60])
    time.sleep(1.0)
    return rec, ents


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "archive_probe" / run
    (out / "sample").mkdir(parents=True, exist_ok=True)
    rep = {"run": run, "scope": "limited probe, expert-approved 2026-11-07", "endpoint": API, "listings": {}, "download": None}
    for m in MONTHS:
        insts = (list(LATER_DELISTED_CHECK.get(m, ())) + ["BTC-USDT"])[:10]
        b, e = mbounds(m)
        for mod in MODULES:
            rec, _ = listing(out, f"{m}_module{mod}_monthly", mod, insts, "monthly", b, e)
            rep["listings"][f"{m} module {mod} ({MODULES[mod]}) monthly, instIdList={','.join(insts)}"] = rec
    # daily listing for the target day, trades only, then ONE download
    d0 = ms(TARGET_DAY)
    rec, ents = listing(out, f"{TARGET_DAY}_module1_daily", "1", list(CANDIDATES), "daily", d0, d0 + 86400000 - 1)
    rep["listings"][f"{TARGET_DAY} module 1 daily, instIdList={','.join(CANDIDATES)}"] = rec
    pick = None
    for p in CANDIDATES:
        for en in ents:
            if p in json.dumps(en):
                pick = (p, en); break
        if pick:
            break
    if not pick:
        rep["download"] = {"skipped": f"no trade file for candidates on {TARGET_DAY}"}
    else:
        p, en = pick
        url = link(en)
        if urllib.parse.urlparse(url).hostname not in ("static.okx.com", "www.okx.com"):
            rep["download"] = {"skipped": f"link host not approved: {urllib.parse.urlparse(url).hostname}", "url": url}
        else:
            body, rec = http(url, cap=MAX_BYTES)
            fn = url.rsplit("/", 1)[-1].split("?")[0] or "sample.bin"
            dd = {"pair": p, "listing_entry": en, "file": fn, **rec}
            if body and not rec.get("truncated"):
                guard.atomic_write(out / "sample" / fn, body, mode="wb")
                dd.update(inspect(body, p))
            rep["download"] = dd
    guard.atomic_write(out / "probe_report.json", json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1, ensure_ascii=False)[:8000])


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
