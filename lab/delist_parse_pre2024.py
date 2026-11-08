"""Parse the separately collected pre-2024 official announcements (out/delisting_raw/ar_pre2024) with the SAME
global Arabic parser, into out/ledger/ar_pre2024/ (kept separate from the main ledger).

python3 -I lab/delist_parse_pre2024.py
"""
import sys, json, csv, io, pathlib, re, html, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import delist_parse as P

LAB = P.LAB
MON = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                   "october", "november", "december"], 1)}
WIN = re.compile(r"([A-Z][a-z]+) (\d{1,2}), (\d{4}),? (\d{1,2}):(\d{2})\s*(am|pm)?\s*-\s*(\d{1,2}):(\d{2})\s*(am|pm)\s*UTC", re.I)


def h24(h, ap):
    h = int(h)
    if ap and ap.lower() == "pm" and h != 12:
        h += 12
    if ap and ap.lower() == "am" and h == 12:
        h = 0
    return h


def english_windows(raw):
    """Old articles are served in English even on /ar/: table rows 'PAIRS;' followed by 'Month D, YYYY, H:MM-H:MM am/pm UTC'.
    Effective = window START (trading may stop any time inside the window; the end is kept too)."""
    s = raw.decode("utf-8", "replace")
    a = re.search(r"<article.*?</article>", s, re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", a.group(0) if a else s))
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    out = {}
    for i, l in enumerate(lines):
        m = WIN.search(l)
        if not m or i == 0:
            continue
        mon, d, y, h1, m1, ap1, h2, m2, ap2 = m.groups()
        ap1 = ap1 or ap2
        start = dt.datetime(int(y), MON[mon.lower()], int(d), h24(h1, ap1), int(m1))
        end = dt.datetime(int(y), MON[mon.lower()], int(d), h24(h2, ap2), int(m2))
        if end < start:            # '8:00-12:00 pm' = 08:00 -> 12:00
            start = start.replace(hour=int(h1) % 12) if ap1 and ap1.lower() == "pm" else start
        for pair in re.findall(r"\b([A-Z0-9]{2,15})-(USDT|USDC|BTC|ETH|DAI|EUR)\b", lines[i - 1]):
            out[f"{pair[0]}-{pair[1]}"] = (start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M"), lines[i - 1][:80] + " | " + l)
    return out


def main():
    src = LAB / "out" / "delisting_raw" / "ar_pre2024"
    out = LAB / "out" / "ledger" / "ar_pre2024"; out.mkdir(parents=True, exist_ok=True)
    man = json.load(open(src / "manifest.json", encoding="utf-8"))
    rows = []
    for it in man["list"]:
        p = src / "articles" / f"{it['slug']}.html"
        rs = P.parse_article(p, "ar", it, man["collected_utc"])
        ew = english_windows(p.read_bytes())
        for r in rs:
            if not r.get("effective_delisting_utc") and r.get("instrument") in ew:
                st, en, ev = ew[r["instrument"]]
                r["effective_delisting_utc"] = st
                r["date_method"] = "english_window_start"
                r["note"] = (r.get("note") or "") + f" delisting window {st} -> {en} UTC (English text served on /ar/)"
                r["evidence"] = ev
            r["region"] = "global (pre-2024 search)"; r["locale"] = "ar_pre2024"
            r["raw_file"] = f"out/delisting_raw/ar_pre2024/articles/{it['slug']}.html"
        rows += rs
    n = P.apply_corrections(rows, "ar_pre2024")
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=P.COLS, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    (out / "delisting_ledger.csv").write_text(s.getvalue(), encoding="utf-8")
    eff24 = [r for r in rows if r.get("market_type") == "spot" and (r.get("instrument") or "").endswith("-USDT") and (r.get("effective_delisting_utc") or "") >= "2024-01-01"]
    notes = {"announcements": len(man["list"]), "rows": len(rows), "corrections_applied": n,
             "spot_usdt_effective_from_2024": sorted({(r["instrument"], r["effective_delisting_utc"], r["slug"]) for r in eff24})}
    (out / "parse_notes.json").write_text(json.dumps(notes, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(notes, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
