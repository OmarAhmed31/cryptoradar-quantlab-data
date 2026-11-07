"""OKX historical-data archive — limited VERIFICATION (expert approval of 2026-11-07, after v0.5).

python3 -I lab/archive_verify.py
 -> out/archive_verify/<run>/
      coverage/raw_calls.jsonl.gz      every listing call: url, time, status, sha256, body
      coverage/archive_coverage.csv    per delisted USDT pair (listing ONLY, no data download)
      candles/<PAIR>-candlesticks-<m>.zip   1 month of 1m candles for BTC, ETH, SAND only
      delist_check/<file>              last daily file(s) of ONE delisted pair (expert's extra test)
      verify_report.json

Allowed:   listings for the 142 global delisted USDT pairs; 1 month of 1m candles for BTC/ETH/SAND;
           the last daily file(s) of ONE delisted pair to check that data reaches the delisting time.
Forbidden: any other data download, research use, CryptoRadar/Router changes.
OKX archive days/months are UTC+8. Everything stored here is converted to UTC (ms or 'YYYY-MM-DD HH:MM' UTC).
"""
import sys, json, time, pathlib, hashlib, gzip, csv, io, zipfile, urllib.request, urllib.error, urllib.parse, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard

API = "https://www.okx.com/api/v5/public/market-data-history"
UA = {"User-Agent": "CryptoRadar-QuantLab/0.1 (research, read-only)"}
CN = dt.timezone(dt.timedelta(hours=8))
UTC = dt.timezone.utc
D, H = 86400000, 3600000
CANDLE_MONTH = (2026, 9)                 # UTC+8 calendar month for BTC/ETH/SAND
LIVE = ("BTC-USDT", "ETH-USDT", "SAND-USDT")
DELIST_TEST = "FITFI-USDT"               # one of the 12 probed pairs, delisted 2024-08-30 08:00 UTC
MAX_BYTES = 60 * 1024 * 1024


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%M") if ms is not None else ""


def http(url, cap=20 * 1024 * 1024):
    rec = {"url": url, "requested_utc": now()}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                body = r.read(cap + 1)
                rec.update(status=r.status, bytes=len(body), truncated=len(body) > cap, sha256=hashlib.sha256(body).hexdigest())
                return body[:cap], rec
        except urllib.error.HTTPError as e:
            rec.update(status=e.code, error=f"http {e.code}")
            if e.code != 429:
                break
        except Exception as e:
            rec.update(status=None, error=f"{type(e).__name__}: {str(e)[:150]}")
        time.sleep(2 + 3 * attempt)
    return None, rec


class Lister:
    def __init__(self, raw_path):
        self.raw = gzip.open(raw_path, "wt", encoding="utf-8")
        self.calls = 0
        self.errors = []

    def __call__(self, module, insts, agg, begin, end):
        url = f"{API}?module={module}&instType=SPOT&instIdList={','.join(insts)}&dateAggrType={agg}&begin={begin}&end={end}"
        for attempt in range(4):
            guard.check_stop()
            body, rec = http(url)
            self.calls += 1
            j = {}
            try:
                j = json.loads(body) if body else {}
            except Exception:
                pass
            self.raw.write(json.dumps({**rec, "body": body.decode("utf-8", "replace") if body else None}) + "\n")
            time.sleep(0.6)
            if j.get("code") == "0":
                out = []
                for blk in j.get("data") or []:
                    for det in blk.get("details") or []:
                        for g in det.get("groupDetails") or []:
                            out.append(g)
                return out
            if j.get("code") in ("50011",) or rec.get("status") == 429:      # rate limit -> wait and retry
                time.sleep(3 + 5 * attempt)
                continue
            break
        self.errors.append({"url": url, "status": rec.get("status"), "code": j.get("code"), "msg": j.get("msg")})
        return None

    def close(self):
        self.raw.close()


def cn_month_start(y, m):
    return int(dt.datetime(y, m, 1, tzinfo=CN).timestamp() * 1000)


def pair_of(fn):
    for sep in ("-trades-", "-candlesticks-"):
        if sep in fn:
            return fn.split(sep)[0]


def coverage(out, pairs, L):
    """pairs: {inst: effective_utc_ms}. Listing only."""
    mods = {"1": "trades", "2": "candles"}
    # monthly chunks of <= 20 months (UTC+8), Jan 2018 .. Dec 2026
    chunks, y, m = [], 2018, 1
    while (y, m) <= (2026, 12):
        ey, em = y + (m + 18) // 12, (m + 18) % 12 + 1          # +19 months -> 20 months inclusive
        if (ey, em) > (2026, 12):
            ey, em = 2026, 12
        chunks.append((cn_month_start(y, m), cn_month_start(ey + (em == 12), em % 12 + 1) - 1))
        y, m = ey + (em == 12), em % 12 + 1
    names = sorted(pairs)
    monthly = {mo: {p: set() for p in names} for mo in mods}
    daily = {mo: {p: [] for p in names} for mo in mods}
    for mo in mods:
        for k in range(0, len(names), 5):
            grp = names[k:k + 5]
            for b, e in chunks:
                got = L(mo, grp, "monthly", b, e)
                for g in got or []:
                    p = pair_of(g["filename"])
                    if p in monthly[mo]:
                        monthly[mo][p].add(int(g["dateTs"]))
        # daily: window [eff-18d, eff+1d] (OKX max 20 days) per group of pairs with the same effective time
        byeff = {}
        for p in names:
            byeff.setdefault(pairs[p], []).append(p)
        for eff, ps in sorted(byeff.items()):
            for k in range(0, len(ps), 5):
                grp = ps[k:k + 5]
                got = L(mo, grp, "daily", eff - 18 * D, eff + 1 * D)
                for g in got or []:
                    p = pair_of(g["filename"])
                    if p in daily[mo]:
                        daily[mo][p].append((int(g["dateTs"]), g["filename"], g.get("sizeMB"), g["url"]))
    rows = []
    for p in names:
        eff = pairs[p]
        r = {"instrument": p, "effective_delisting_utc": iso(eff)}
        for mo, tag in mods.items():
            ms_ = sorted(monthly[mo][p])
            ds = sorted(daily[mo][p])
            # months between first and last that are absent
            miss = 0
            if ms_:
                a = dt.datetime.fromtimestamp(ms_[0] / 1000, CN); z = dt.datetime.fromtimestamp(ms_[-1] / 1000, CN)
                n_exp = (z.year - a.year) * 12 + z.month - a.month + 1
                miss = n_exp - len(ms_)
            last_end = ds[-1][0] + D if ds else None                 # file day = [dateTs, dateTs+24h) UTC+8 day
            gap_h = round((eff - last_end) / H, 1) if last_end is not None else ""
            reaches = last_end is not None and last_end >= eff
            if not ms_ and not ds:
                st = "none"
            elif reaches:
                st = "full_apparent"
            else:
                st = "partial"
            r.update({f"{tag}_first_month_utc": iso(ms_[0]) if ms_ else "", f"{tag}_last_month_utc": iso(ms_[-1]) if ms_ else "",
                      f"{tag}_n_monthly_files": len(ms_), f"{tag}_months_missing_inside": miss,
                      f"{tag}_last_daily_file": ds[-1][1] if ds else "", f"{tag}_last_daily_start_utc": iso(ds[-1][0]) if ds else "",
                      f"{tag}_last_daily_end_utc": iso(last_end), f"{tag}_n_daily_files_in_window": len(ds),
                      f"{tag}_reaches_delisting": int(bool(reaches)), f"{tag}_gap_hours_last_data_to_delisting": gap_h,
                      f"{tag}_status": st})
        rows.append(r)
        if p == DELIST_TEST:
            r["_daily_entries"] = {tag: daily[mo][p][-2:] for mo, tag in mods.items()}
    return rows


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "archive_verify" / run
    for d in ("coverage", "candles", "delist_check"):
        (out / d).mkdir(parents=True, exist_ok=True)
    rep = {"run": run, "scope": "expert approval after v0.5: listing-only 142 pairs + 1 month 1m candles BTC/ETH/SAND + one delisted pair end check"}
    pairs = {}
    for line in open("requests/avail_instruments.txt"):
        if not line.strip():
            continue
        inst, eff, loc = line.strip().split(",")
        if loc == "ar" and inst.endswith("-USDT"):
            e = int(dt.datetime.strptime(eff, "%Y-%m-%d %H:%M").replace(tzinfo=UTC).timestamp() * 1000)
            pairs[inst] = max(pairs.get(inst, 0), e)
    rep["pairs"] = len(pairs)
    L = Lister(out / "coverage" / "raw_calls.jsonl.gz")

    # 1) one month of 1m candles, live pairs
    b = cn_month_start(*CANDLE_MONTH)
    y, m = CANDLE_MONTH
    e = cn_month_start(y + (m == 12), m % 12 + 1) - 1
    got = L("2", list(LIVE), "monthly", b, e - 1000) or []
    rep["candles"] = []
    for g in got:
        if int(g["dateTs"]) != b or pair_of(g["filename"]) not in LIVE:
            continue
        url = g["url"]
        assert urllib.parse.urlparse(url).hostname == "static.okx.com"
        body, rec = http(url, cap=MAX_BYTES)
        if body and not rec.get("truncated"):
            guard.atomic_write(out / "candles" / g["filename"], body, mode="wb")
        rep["candles"].append({"file": g["filename"], "listing": g, **rec})

    # 2) listing-only coverage, all pairs
    rows = coverage(out, pairs, L)

    # 3) expert's extra test: last daily file(s) of ONE delisted pair
    rep["delist_check"] = {"pair": DELIST_TEST, "effective_delisting_utc": iso(pairs.get(DELIST_TEST)), "files": []}
    for r in rows:
        if r["instrument"] == DELIST_TEST:
            for tag, ents in r.pop("_daily_entries").items():
                if not ents:
                    continue
                ts, fn, size, url = ents[-1]
                assert urllib.parse.urlparse(url).hostname == "static.okx.com"
                body, rec = http(url, cap=MAX_BYTES)
                if body and not rec.get("truncated"):
                    guard.atomic_write(out / "delist_check" / fn, body, mode="wb")
                rep["delist_check"]["files"].append({"kind": tag, "file": fn, "file_day_start_utc": iso(ts), **rec})
    for r in rows:
        r.pop("_daily_entries", None)
    cols = list(rows[0].keys())
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=cols); w.writeheader(); w.writerows(rows)
    guard.atomic_write(out / "coverage" / "archive_coverage.csv", s.getvalue())
    L.close()
    rep["listing_calls"] = L.calls
    rep["listing_errors"] = L.errors[:50]
    rep["listing_error_count"] = len(L.errors)
    for tag in ("trades", "candles"):
        rep[f"coverage_{tag}"] = {st: sum(1 for r in rows if r[f"{tag}_status"] == st) for st in ("full_apparent", "partial", "none")}
    guard.atomic_write(out / "verify_report.json", json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("candles",)}, indent=1, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="archive-verify", cpu_s=3000, fsize_mb=100)
    main()
    guard.health("done")
