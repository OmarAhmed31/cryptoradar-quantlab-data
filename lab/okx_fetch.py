"""OKX public market-data connector (read-only, no API keys).

probe:  python3 -I lab/okx_fetch.py probe BTC ETH SOL     -> out/okx_probe/<run>/ + probe_result.json
fetch:  python3 -I lab/okx_fetch.py fetch <days> SYM ...  -> out/okx_raw/<run>/   (only after a successful probe)

Endpoint: GET https://www.okx.com/api/v5/market/history-candles?instId=<SYM>-USDT&bar=1H&limit=100&after=<ms>
  * newest first; `after` pages to older candles; CryptoRadar's own collector uses limit=100 on this endpoint
  * row = [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]; only confirm == "1" (closed) candles are kept
Instruments: GET /api/v5/public/instruments?instType=SPOT  -> listTime per pair (currently listed pairs only)

Checks per coin: duplicates, gaps (missing hours), non-positive prices, OHLC consistency, first/last candle.
Network is restricted by the guard to www.okx.com only. Nothing here can reach CryptoRadar.
"""
import sys, json, time, pathlib, urllib.request, urllib.error, ssl, os, gzip, hashlib
_RAW = {"last": None}
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard

BASE = "https://www.okx.com"
H = 3600000


def get(url, tries=3):
    last = None
    for t in range(tries):
        guard.check_stop()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CryptoRadar-QuantLab/0.1 (research, read-only)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read()
                _RAW["last"] = {"url": url, "final_url": r.geturl(), "status": r.status, "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "sha256": hashlib.sha256(body).hexdigest(), "body": body.decode("utf-8", "replace")}
                j = json.loads(body.decode())
            if j.get("code") == "0":
                return j, None
            last = f"okx code {j.get('code')} {j.get('msg', '')[:60]}"
            if j.get("code") == "51001":   # instrument does not exist: deterministic, no retry
                break
        except urllib.error.HTTPError as e:
            last = f"http {e.code}"
        except urllib.error.URLError as e:
            if isinstance(e.reason, guard.IsolationError):   # urllib wraps the guard's exception
                return None, f"isolation {e.reason}"
            last = f"url_error {str(e.reason)[:120]}"
        except guard.IsolationError as e:
            return None, f"isolation {e}"
        except Exception as e:
            last = f"{type(e).__name__} {str(e)[:120]}"
        time.sleep(1.5 * (t + 1))
    return None, last


def fetch_coin(sym, days, now_ms=None, raw_path=None):
    now_ms = now_ms or int(time.time() * 1000)
    to = now_ms // H * H - H          # last closed hour (same rule as CryptoRadar)
    frm = to - days * 24 * H
    after, rows, pages, err = to + H, {}, 0, None
    while pages < 100000:
        j, err = get(f"{BASE}/api/v5/market/history-candles?instId={sym}-USDT&bar=1H&limit=100&after={after}")
        if j is None:
            break
        data = j.get("data") or []
        pages += 1
        if raw_path is not None and _RAW["last"]:
            with gzip.open(raw_path, "at", encoding="utf-8") as g:   # every raw API page, untouched
                g.write(json.dumps(_RAW["last"]) + "\n")
        if not data:
            break
        for c in data:
            ts = int(c[0])
            if len(c) > 8 and c[8] != "1":
                continue
            rows.setdefault(ts, [ts, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[7] if len(c) > 7 and c[7] else c[5])])
        oldest = int(data[-1][0])
        if oldest <= frm:
            break
        after = oldest
        time.sleep(0.12)  # stay well under the public rate limit
    R = sorted(v for k, v in rows.items() if frm <= k <= to)
    return R, {"pages": pages, "error": err, "from": frm, "to": to}


def qc(R):
    ts = [r[0] for r in R]
    gaps = sum((b - a) // H - 1 for a, b in zip(ts, ts[1:]) if b - a != H)
    bad_px = sum(1 for r in R if min(r[1:5]) <= 0)
    bad_ohlc = sum(1 for r in R if not (r[3] <= min(r[1], r[4]) + 1e-12 and r[2] >= max(r[1], r[4]) - 1e-12))
    return {"n": len(R), "first": ts[0] if ts else None, "last": ts[-1] if ts else None, "dups": len(ts) - len(set(ts)),
            "gaps_hours": gaps, "bad_price": bad_px, "bad_ohlc": bad_ohlc}


def run(mode, days, syms):
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / ("okx_probe" if mode == "probe" else "okx_raw") / run_id
    out.mkdir(parents=True, exist_ok=True)
    res = {"run_id": run_id, "mode": mode, "days": days, "coins": {}, "started_utc": run_id}
    inst, ierr = get(f"{BASE}/api/v5/public/instruments?instType=SPOT", tries=2)
    res["instruments"] = {"ok": inst is not None, "error": ierr, "n_usdt": None}
    if inst and _RAW["last"]:
        guard.atomic_write(out / "instruments_spot_raw.json", json.dumps(_RAW["last"]))
    if inst:
        L = {x["instId"][:-5]: x.get("listTime") for x in inst["data"] if x["instId"].endswith("-USDT")}
        res["instruments"]["n_usdt"] = len(L)
        guard.atomic_write(out / "instruments_spot_usdt.json", json.dumps(L, indent=0))
    for s in syms:
        R, meta = fetch_coin(s, days, raw_path=out / f"{s}_raw_pages.jsonl.gz")
        q = qc(R) if R else {"n": 0}
        res["coins"][s] = {**meta, **q}
        if R:
            guard.atomic_write(out / f"{s}_1h.csv", "ts_ms,open,high,low,close,volume_quote\n" + "".join(",".join(map(str, r)) + "\n" for r in R))
        guard.health("running", fetched=s)
    ok = res["instruments"]["ok"] and all(c.get("n", 0) > 0 and not c.get("error") and c.get("dups") == 0 and c.get("gaps_hours") == 0 for c in res["coins"].values())
    res["verdict"] = "PASS" if ok else "FAIL"
    guard.atomic_write(out / "probe_result.json", json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "probe":
        days, syms = 400, sys.argv[2:] or ["BTC", "ETH", "SOL"]
    else:
        days, syms = int(sys.argv[2]), sys.argv[3:]
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com",), job="okx-" + mode)
    r = run(mode, days, syms)
    guard.health("done", verdict=r["verdict"])
