"""Collect the OKX OFFICIAL delisting archive RAW, page by page, then every article RAW.

python3 -I lab/delist_collect.py <locale> [max_pages]      locale: ar (global) | en-eu (Europe, kept separate)

out/delisting_raw/<locale>/
  index/page_<n>.html            raw archive pages
  articles/<slug>.html           raw article pages (one per announcement)
  manifest.json                  per fetch: url, final_url, status, bytes, sha256, fetched_utc; list items (slug, title, date text)
Stops when a page adds no new article or returns non-200. Nothing is parsed into the ledger here.
"""
import sys, json, time, pathlib, re, hashlib, html as H
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import guard
from lab.delist_fetch import fetch

ITEM = re.compile(r'<li class="articleItem[^"]*"><a href="(/[a-z-]+/help/([a-z0-9-]+))"[^>]*>.*?<div class="title[^"]*">(.*?)</div>.*?<span class="compactText[^"]*">(.*?)</span>', re.S)


def main(locale, max_pages):
    base = guard.LAB / "out" / "delisting_raw" / locale
    (base / "index").mkdir(parents=True, exist_ok=True)
    (base / "articles").mkdir(parents=True, exist_ok=True)
    sec = f"https://www.okx.com/{locale}/help/section/announcements-delistings"
    fetches, items, seen = [], [], set()
    for n in range(1, max_pages + 1):
        url = sec if n == 1 else f"{sec}/page/{n}"
        body, rec = fetch(url)
        rec["kind"] = "index"; rec["page"] = n
        fetches.append(rec)
        if not body or rec.get("status") != 200:
            break
        if f"/{locale}/" not in (rec.get("final_url") or ""):
            rec["note"] = "REDIRECTED to another region - page not used"
            break
        guard.atomic_write(base / "index" / f"page_{n}.html", body, mode="wb")
        new = 0
        for href, slug, title, date in ITEM.findall(body.decode("utf-8", "replace")):
            if slug in seen:
                continue
            seen.add(slug); new += 1
            items.append({"slug": slug, "href": href, "title": H.unescape(re.sub("<[^>]+>", "", title)).strip(),
                          "date_text": H.unescape(date).replace("‏", "").strip(), "index_page": n})
        rec["new_items"] = new
        if new == 0:
            break
        time.sleep(1.0)
    for it in items:
        body, rec = fetch("https://www.okx.com" + it["href"])
        rec["kind"] = "article"; rec["slug"] = it["slug"]
        fetches.append(rec)
        it["fetched"] = bool(body) and rec.get("status") == 200 and f"/{locale}/" in (rec.get("final_url") or "")
        if body:
            guard.atomic_write(base / "articles" / f"{it['slug']}.html", body, mode="wb")
        time.sleep(0.8)
    man = {"locale": locale, "section": sec, "collected_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "pages_fetched": sum(1 for f in fetches if f["kind"] == "index" and f.get("status") == 200),
           "items": len(items), "articles_ok": sum(1 for i in items if i.get("fetched")), "list": items, "fetch_log": fetches}
    guard.atomic_write(base / "manifest.json", json.dumps(man, indent=1, ensure_ascii=False))
    print(locale, "pages", man["pages_fetched"], "items", man["items"], "articles_ok", man["articles_ok"],
          "oldest", items[-1]["date_text"] if items else None)


if __name__ == "__main__":
    guard.install(write_dirs=("out", "state"), net_hosts=("www.okx.com",), job="delist-collect")
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40)
    guard.health("done")
