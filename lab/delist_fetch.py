"""Probe: fetch OKX OFFICIAL delisting announcement pages RAW (no parsing yet).

python3 -I lab/delist_fetch.py <pages> [article_limit]
  -> out/delist_raw/<run>/index_page_<n>.html, article_<k>.html, fetch_log.json

Every fetch records: requested URL, final URL (redirects show the region actually served), HTTP status,
sha256 of the body, timestamp. Only www.okx.com is reachable (guard). Parsing into the Delisting Ledger
is a separate step written AFTER inspecting this raw HTML, so we do not assume the page structure.
"""
import sys, json, time, pathlib, urllib.request, urllib.error, hashlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard

SECTION = "https://www.okx.com/help/section/announcements-delistings"


def fetch(url):
    guard.check_stop()
    rec = {"url": url, "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoRadar-QuantLab/0.1 (research, read-only)", "Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            rec.update(final_url=r.geturl(), status=r.status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            return body, rec
    except urllib.error.HTTPError as e:
        rec.update(status=e.code, error=f"http {e.code}", final_url=e.geturl())
    except urllib.error.URLError as e:
        rec.update(error=("isolation " if isinstance(e.reason, guard.IsolationError) else "url_error ") + str(e.reason)[:160])
    except Exception as e:
        rec.update(error=f"{type(e).__name__} {str(e)[:160]}")
    return None, rec


def main(pages, art_limit, section=None):
    global SECTION
    SECTION = section or SECTION
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = guard.LAB / "out" / "delist_raw" / run_id
    out.mkdir(parents=True, exist_ok=True)
    log, links = [], []
    for n in range(1, pages + 1):
        url = SECTION if n == 1 else f"{SECTION}/page/{n}"
        body, rec = fetch(url)
        log.append(rec)
        if body:
            guard.atomic_write(out / f"index_page_{n}.html", body, mode="wb")
            for h in re.findall(rb'href="(/(?:[a-z-]+/)?help/[a-z0-9-]+)"', body):
                h = h.decode()
                if "/section/" not in h and h not in links:
                    links.append(h)
        time.sleep(1.0)
    for k, h in enumerate(links[:art_limit], 1):
        body, rec = fetch("https://www.okx.com" + h)
        rec["link"] = h
        log.append(rec)
        if body:
            guard.atomic_write(out / f"article_{k:03d}.html", body, mode="wb")
        time.sleep(1.0)
    res = {"run_id": run_id, "section": SECTION, "pages_requested": pages, "links_found": len(links), "links": links,
           "fetched_ok": sum(1 for r in log if r.get("status") == 200), "log": log}
    guard.atomic_write(out / "fetch_log.json", json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "log"}, indent=1))
    print("final_urls:", sorted({r.get("final_url") for r in log if r.get("final_url")})[:5])


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com",), job="delist-probe")
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 15, sys.argv[3] if len(sys.argv) > 3 else None)
    guard.health("done")
