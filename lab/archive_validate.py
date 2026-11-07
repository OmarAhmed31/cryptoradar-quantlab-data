"""Rule-B validation on more pairs and another month (expert conditions after v0.6).

python3 -I lab/archive_validate.py
 -> out/archive_validate/<run>/
      candles/<PAIR>-candlesticks-2026-06.zip   1m archive, month 2026-06 (UTC+8), 6 live pairs
      verified_1h/<COIN>_raw_pages.jsonl.gz     1H history-candles: BTC/ETH/SAND = earlier verified probe (copied);
                                                SOL/DOGE/LSK = fetched now, raw pages kept
      candle_comparison.md/.json                 rule A vs rule B, exact decimals
Live pairs only. LSK-USDT is chosen as a low-liquidity pair (many minutes without trades).
"""
import sys, json, time, gzip, shutil, pathlib, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab import archive_verify as A
from lab import okx_fetch as OF
from lab import candle_compare as C

MONTH = (2026, 6)
NEW = ("SOL-USDT", "DOGE-USDT", "LSK-USDT")
OLD = ("BTC-USDT", "ETH-USDT", "SAND-USDT")
PROBE = "out/okx_probe/20261107T135059Z"


def main():
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "archive_validate" / run
    for d in ("candles", "verified_1h"):
        (out / d).mkdir(parents=True, exist_ok=True)
    rep = {"run": run, "month_utc8": f"{MONTH[0]}-{MONTH[1]:02d}", "files": [], "fetch": {}}
    L = A.Lister(out / "listing_calls.jsonl.gz")
    b = A.cn_month_start(*MONTH)
    e = A.cn_month_start(MONTH[0] + (MONTH[1] == 12), MONTH[1] % 12 + 1) - 1
    for grp in (OLD, NEW):
        for g in L.split("2", list(grp), "monthly", b, e - 1000, 31 * A.D) or []:
            if int(g["dateTs"]) != b:
                continue
            assert urllib.parse.urlparse(g["url"]).hostname == "static.okx.com"
            body, rec = A.http(g["url"], cap=A.MAX_BYTES)
            if body and not rec.get("truncated"):
                guard.atomic_write(out / "candles" / g["filename"], body, mode="wb")
            rep["files"].append({"file": g["filename"], "url": g["url"], **rec})
    L.close()
    for p in OLD:
        c = p.split("-")[0]
        shutil.copyfile(guard.LAB / PROBE / f"{c}_raw_pages.jsonl.gz", out / "verified_1h" / f"{c}_raw_pages.jsonl.gz")
    for p in NEW:
        c = p.split("-")[0]
        after, pages, err = e + 2 * A.H, 0, None
        with gzip.open(out / "verified_1h" / f"{c}_raw_pages.jsonl.gz", "wt", encoding="utf-8") as raw:
            while pages < 15:
                j, err = OF.get(f"https://www.okx.com/api/v5/market/history-candles?instId={p}&bar=1H&limit=100&after={after}")
                if OF._RAW["last"]:
                    raw.write(json.dumps(OF._RAW["last"]) + "\n")
                if j is None or not j.get("data"):
                    break
                pages += 1
                after = int(j["data"][-1][0])
                if after <= b - A.H:
                    break
                time.sleep(0.15)
        rep["fetch"][p] = {"pages": pages, "error": err}
    R = C.main(out / "candles", out / "verified_1h", out)
    guard.atomic_write(out / "validate_report.json", json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1)[:3000])


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com", "static.okx.com"), job="archive-validate", fsize_mb=100)
    main()
    guard.health("done")
