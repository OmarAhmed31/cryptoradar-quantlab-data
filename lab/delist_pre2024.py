"""Search the OFFICIAL OKX site for delisting announcements published BEFORE 2024-01-05 (the start of the
global delisting archive index), kept SEPARATE from the main ledger.

python3 -I lab/delist_pre2024.py
 -> out/delisting_raw/ar_pre2024/
      sitemaps/<n>.xml           raw OKX sitemap files used for discovery
      articles/<slug>.html       raw article, global Arabic path /ar/help/<slug> (same rule as the main ledger)
      manifest.json              discovery log + every fetch (url, final_url, status, sha256, time) + kept items

Discovery: OKX sitemap (www.okx.com) -> help URLs whose slug contains "delist" -> fetch /ar/help/<slug> ->
keep articles whose datePublished is in [2023-07-01, 2024-01-05). A seed slug found by web search
(okx-to-delist-several-spot-trading-pairs-12-29, published 2023-12-29) is always included.
Host: www.okx.com only. No candles, no trades.
"""
import sys, json, time, pathlib, re, gzip, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab.delist_fetch import fetch

LO, HI = "2023-07-01", "2024-01-05"
SEED = ["okx-to-delist-several-spot-trading-pairs-12-29"]
MAX_SITEMAPS = 80
MAX_ARTICLES = 600


def main():
    base = guard.LAB / "out" / "delisting_raw" / "ar_pre2024"
    for d in ("sitemaps", "articles"):
        (base / d).mkdir(parents=True, exist_ok=True)
    log, todo, seen_sm, slugs = [], ["https://www.okx.com/sitemap.xml"], set(), set(SEED)
    n = 0
    # robots.txt names the official sitemaps (sitemap.xml returned 404 on the first run)
    body, rec = fetch("https://www.okx.com/robots.txt")
    rec["kind"] = "robots"; log.append(rec)
    if body:
        guard.atomic_write(base / "sitemaps" / "robots.txt", body, mode="wb")
        for l in re.findall(r"(?im)^\s*sitemap:\s*(\S+)", body.decode("utf-8", "replace")):
            if "www.okx.com" in l:
                todo.append(l)
    while todo and n < MAX_SITEMAPS:
        u = todo.pop(0)
        if u in seen_sm:
            continue
        seen_sm.add(u)
        body, rec = fetch(u)
        rec["kind"] = "sitemap"; log.append(rec); n += 1
        if not body or rec.get("status") != 200:
            continue
        if u.endswith(".gz") or body[:2] == b"\x1f\x8b":
            try:
                body = gzip.decompress(body)
            except Exception:
                pass
        guard.atomic_write(base / "sitemaps" / f"{n:03d}.xml", body, mode="wb")
        txt = body.decode("utf-8", "replace")
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", txt)
        rec["locs"] = len(locs)
        for l in locs:
            if l.endswith(".xml") or l.endswith(".xml.gz") or "sitemap" in l.rsplit("/", 1)[-1]:
                if ("help" in l or "support" in l or l.count("/") <= 3 or "sitemap" in l) and "www.okx.com" in l:
                    todo.append(l)
            m = re.search(r"/help/([a-z0-9-]+)/?$", l)
            if m and "delist" in m.group(1):
                slugs.add(m.group(1))
        time.sleep(0.5)
    items, k = [], 0
    queue, done = sorted(slugs), set()
    while queue:
        s = queue.pop(0)
        if s in done:
            continue
        done.add(s)
        if k >= MAX_ARTICLES:
            break
        url = f"https://www.okx.com/ar/help/{s}"
        body, rec = fetch(url)
        rec["kind"] = "article"; rec["slug"] = s; log.append(rec); k += 1
        ok = bool(body) and rec.get("status") == 200 and "/ar/" in (rec.get("final_url") or "")
        pub = None
        if ok:
            m = re.search(rb'"datePublished"\s*:\s*"([^"]+)"', body)
            pub = m.group(1).decode() if m else None
        rec["datePublished"] = pub
        if ok:   # follow links to other delisting announcements (prev/next, related)
            for l in set(re.findall(rb'/(?:[a-z-]+/)?help/([a-z0-9-]*delist[a-z0-9-]*)', body)):
                l = l.decode()
                if l not in done and l not in queue:
                    queue.append(l); slugs.add(l)
        if ok and pub and LO <= pub[:10] < HI:
            guard.atomic_write(base / "articles" / f"{s}.html", body, mode="wb")
            t = re.search(rb"<title>(.*?)</title>", body, re.S)
            items.append({"slug": s, "href": f"/ar/help/{s}", "title": t.group(1).decode("utf-8", "replace").strip() if t else "",
                          "date_text": pub, "datePublished": pub, "fetched": True})
        time.sleep(0.6)
    items.sort(key=lambda x: x["datePublished"], reverse=True)
    man = {"locale": "ar_pre2024", "served_path": "/ar/help/<slug>", "window_published": [LO, HI],
           "collected_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sitemaps_fetched": n, "delist_slugs_found": len(slugs), "articles_fetched": k, "items": len(items),
           "pages_fetched": 0, "list": items, "fetch_log": log}
    guard.atomic_write(base / "manifest.json", json.dumps(man, indent=1, ensure_ascii=False))
    print(json.dumps({k_: v for k_, v in man.items() if k_ not in ("list", "fetch_log")}, indent=1),
          [(i["datePublished"][:10], i["slug"]) for i in items][:40])


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com",), job="delist-pre2024")
    main()
    guard.health("done")
