"""Candle availability test for DELISTED spot pairs (OKX public API, read-only).

python3 -I lab/avail_test.py requests/avail_instruments.txt     (lines: INSTRUMENT,effective_utc,locale)
 -> out/availability/<run>/delisting_data_availability.csv, raw/<inst>.jsonl.gz, live_instruments_raw.json

Per instrument records:
  in_live_instruments   is it still in /public/instruments (SPOT) today?
  1D: first/last daily candle, n days, missing days inside [first, last]
  1H: last hourly candle, n hourly candles in the 30 days before delisting, missing hours in that window
  status: full | partial | none, and the API error text if the request failed
"""
import sys, json, time, gzip, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import okx_fetch as OF

H, D = 3600000, 86400000
BASE = "https://www.okx.com"


def pages(inst, bar, after, stop_ms, raw, max_pages):
    """Walk history-candles backwards from `after` until empty / older than stop_ms. Returns {ts: row}."""
    out, err, n = {}, None, 0
    while n < max_pages:
        OF._RAW["last"] = None
        j, err = OF.get(f"{BASE}/api/v5/market/history-candles?instId={inst}&bar={bar}&limit=100&after={after}")
        n += 1
        if OF._RAW["last"]:   # raw response kept also when OKX returns an error (e.g. 51001)
            raw.write(json.dumps({"bar": bar, **OF._RAW["last"]}) + "\n")
        if j is None:
            break
        data = j.get("data") or []
        if not data:
            break
        for c in data:
            out.setdefault(int(c[0]), c)
        oldest = int(data[-1][0])
        if oldest <= stop_ms:
            break
        after = oldest
        time.sleep(0.12)
    return out, err, n


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if ms else ""


def main(listfile, tag=""):
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + (f"_{tag}" if tag else "")
    out = guard.LAB / "out" / "availability" / run
    (out / "raw").mkdir(parents=True, exist_ok=True)
    inst_j, ierr = OF.get(f"{BASE}/api/v5/public/instruments?instType=SPOT", tries=2)
    live = {x["instId"] for x in inst_j["data"]} if inst_j else set()
    if OF._RAW["last"]:
        guard.atomic_write(out / "live_instruments_raw.json", json.dumps(OF._RAW["last"]))
    cols = ["instrument", "region_source", "effective_delisting_utc", "in_live_instruments", "status",
            "first_1d", "last_1d", "n_1d", "missing_1d_inside", "last_1h", "n_1h_last30d", "missing_1h_last30d", "api_error", "pages"]
    lines = [l.strip().split(",") for l in open(listfile) if l.strip()]
    res = []
    for k, (inst, eff, loc) in enumerate(lines, 1):
        guard.check_stop()
        e = int(dt.datetime.strptime(eff, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        with gzip.open(out / "raw" / f"{inst}.jsonl.gz", "wt", encoding="utf-8") as raw:
            d1, err1, p1 = pages(inst, "1Dutc", e + 3 * D, 0, raw, 40)
            h1, err2, p2 = pages(inst, "1H", e + 2 * D, e - 30 * D, raw, 9)
        dts = sorted(d1)
        miss_d = sum((b - a) // D - 1 for a, b in zip(dts, dts[1:]) if b - a != D)
        hts = sorted(t for t in h1 if e - 30 * D <= t <= e + 2 * D)
        win = [t for t in hts if t <= e]
        miss_h = sum((b - a) // H - 1 for a, b in zip(win, win[1:]) if b - a != H)
        status = "none" if not dts else ("full" if miss_d == 0 and win and miss_h == 0 else "partial")
        r = {"instrument": inst, "region_source": loc, "effective_delisting_utc": eff, "in_live_instruments": int(inst in live),
             "status": status, "first_1d": iso(dts[0]) if dts else "", "last_1d": iso(dts[-1]) if dts else "", "n_1d": len(dts),
             "missing_1d_inside": miss_d, "last_1h": iso(hts[-1]) if hts else "", "n_1h_last30d": len(win), "missing_1h_last30d": miss_h,
             "api_error": err1 or err2 or "", "pages": p1 + p2}
        res.append(r)
        if k % 20 == 0:
            guard.health("running", done=k, of=len(lines))
    import csv, io
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=cols); w.writeheader(); w.writerows(res)
    guard.atomic_write(out / "delisting_data_availability.csv", s.getvalue())
    summ = {"run": run, "instruments": len(res), "live_list_ok": bool(inst_j), "live_error": ierr,
            "status": {x: sum(1 for r in res if r["status"] == x) for x in ("full", "partial", "none")},
            "still_in_live_list": sum(r["in_live_instruments"] for r in res), "api_errors": sum(1 for r in res if r["api_error"])}
    guard.atomic_write(out / "summary.json", json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com",), job="avail-test", cpu_s=7000)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
    guard.health("done")
