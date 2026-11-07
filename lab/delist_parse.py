"""Parse the RAW OKX delisting archive into the Delisting Ledger (offline, no network).

python3 -I lab/delist_parse.py <locale>     -> out/ledger/<locale>/delisting_ledger.csv + parse_notes.json

One row per (announcement, instrument). Rules (agreed with reviewer):
  * market_type kept separate: spot / margin / perpetual_futures / expiry_futures / options / migration / postponement / other
  * announcement date and effective delisting date are separate columns
  * full trading pair kept (e.g. ICX-USDT), never just the coin
  * whole-asset delisting is NOT inferred from pair delisting: `asset_withdrawal_suspension_utc` is filled only
    when the announcement itself states a withdrawal suspension for the affected crypto
  * every row carries the official URL, raw file sha256, collection time, and how its date was found (date_method)
"""
import sys, re, json, csv, html as H, hashlib, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

LAB = pathlib.Path(__file__).resolve().parents[1]
AR_M = {"يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "إبريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
        "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
EN_M = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
QUOTES = "USDT|USDC|USD|EUR|BTC|ETH|USDⓈ|USDS|OKB|DAI|TRY|BRL|AED|SGD|USDG|AUD|PYUSD"
PAIR = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9]{1,20})\s*[/-]\s*(" + QUOTES + r")(K?)(?![A-Za-z0-9])")
SWAP = re.compile(r"(?<![A-Z0-9])([A-Z0-9]{1,20})(USDT|USDC|USD)(?:-SWAP)?(?![A-Z0-9/])")
DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def text_of(article_html):
    t = H.unescape(re.sub(r"<[^>]+>", "\n", article_html)).translate(DIG).replace("‏", "").replace("‎", "")
    return re.sub(r"\n\s*\n+", "\n", t)


def dates_in(t, locale):
    """All (pos, date, has_year, hh:mm or None) in text order."""
    out = []
    if locale == "ar":
        rx = re.compile(r"(\d{1,2})\s+(" + "|".join(AR_M) + r")\s*،?\s*(\d{4})?")
        for m in rx.finditer(t):
            out.append((m.start(), int(m.group(1)), AR_M[m.group(2)], int(m.group(3)) if m.group(3) else None, m.end()))
    else:
        rx = re.compile(r"(" + "|".join(EN_M) + r")\s+(\d{1,2}),?\s*(\d{4})?", re.I)
        for m in rx.finditer(t):
            out.append((m.start(), int(m.group(2)), EN_M[m.group(1).lower()], int(m.group(3)) if m.group(3) else None, m.end()))
        rx2 = re.compile(r"(\d{1,2})\s+(" + "|".join(EN_M) + r"),?\s*(\d{4})?", re.I)
        for m in rx2.finditer(t):
            out.append((m.start(), int(m.group(1)), EN_M[m.group(2).lower()], int(m.group(3)) if m.group(3) else None, m.end()))
        out.sort()
    return out


def time_near(t, a, b):
    """First HH:MM inside t[a:b] (the time window start)."""
    m = re.search(r"(\d{1,2}):(\d{2})\s*(صباح|مساء|a\.?m|p\.?m)?", t[a:b], re.I)
    if not m:
        return None
    hh = int(m.group(1)) % 24
    if m.group(3) and m.group(3).lower().startswith(("مساء", "p")) and hh < 12:
        hh += 12
    if m.group(3) and m.group(3).lower().startswith(("صباح", "a")) and hh == 12:
        hh = 0
    return (hh, int(m.group(2)))


def mk_date(d, mo, y, pub, hm):
    year_inferred = y is None
    if y is None:
        y = pub.year + (1 if mo < pub.month - 1 else 0)
    try:
        x = dt.datetime(y, mo, d, *(hm or (0, 0)), tzinfo=dt.timezone.utc)
    except ValueError:
        return None, year_inferred
    return x, year_inferred


def market_type(slug, title):
    s = slug + " " + title.lower()
    if "migration" in s:
        return "migration"
    if "postpone" in s or "delay" in s:
        return "postponement"
    if "perpetual" in s or "swap" in s:
        return "perpetual_futures"
    if "expiry-futures" in s or "expiry futures" in s:
        return "expiry_futures"
    if "option" in s:
        return "options"
    if "margin" in s:
        return "margin"
    if "spot" in s:
        return "spot"
    return "other"


def section_date(t, keys, dl, pub, after_pos=0):
    """First date after any keyword (e.g. 'وقت التنفيذ', 'تعليق إيداع')."""
    for k in keys:
        i = t.find(k, after_pos)
        if i >= 0:
            for (p, d, mo, y, e) in dl:
                if p > i:
                    hm = time_near(t, max(i, p - 160), e + 40)
                    x, yi = mk_date(d, mo, y, pub, hm)
                    return x, yi, k
    return None, False, None


KEYS = {
    "ar": {"exec": ["وقت التنفيذ", "موعد التنفيذ", "الجدول الزمني", "وقت إلغاء الإدراج", "سنقوم بإلغاء إدراج", "سنُزيل", "سنقوم بإزالة"],
           "dep": ["تعليق إيداع", "تعليق عمليات إيداع", "تعليق عمليات الإيداع", "علَّقنا عمليات الإيداع", "سيتم تعليق عمليات الإيداع"],
           "wd": ["تعليق عمليات سحب", "تعليق سحب", "سنعلّق عمليات سحب", "سنُعلِّق عمليات السحب", "تعليق عمليات السحب"]},
    "en-eu": {"exec": ["Execution time", "Affected trading pairs execution schedule", "Delisting time", "will delist"],
              "dep": ["Suspension on crypto deposit", "deposits", "Deposit"], "wd": ["Suspension on crypto withdrawal", "withdrawals", "Withdrawal"]},
}


def parse_article(path, locale, meta, collected):
    raw = path.read_bytes()
    h = raw.decode("utf-8", "replace")
    a = re.search(r"<article.*?</article>", h, re.S)
    art = a.group(0) if a else ""
    t = text_of(art)
    m = re.search(r'"datePublished":"([^"]+)"', h)
    pub = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")) if m else None
    title = meta["title"]
    slug = meta["slug"]
    mt = market_type(slug, title)
    dl = dates_in(t, locale)
    K = KEYS[locale]
    base = {"region": "global" if locale == "ar" else "europe_okx_eea", "locale": locale, "slug": slug, "title": title, "market_type": mt,
            "announcement_utc": pub.strftime("%Y-%m-%d %H:%M") if pub else "", "official_url": f"https://www.okx.com/{locale}/help/{slug}",
            "raw_file": f"out/delisting_raw/{locale}/articles/{slug}.html", "raw_sha256": hashlib.sha256(raw).hexdigest(), "collected_utc": collected}
    if not pub:
        return [dict(base, instrument="", note="no datePublished in raw page")]
    ex, ex_yi, ex_k = section_date(t, K["exec"], dl, pub)
    dep, _, _ = section_date(t, K["dep"], dl, pub)
    wd, _, wd_k = section_date(t, K["wd"], dl, pub)
    if wd and dep and wd == dep:
        wd = None   # same date picked twice -> not a separate withdrawal statement
    rows = []
    # tables first: header decides the market (spot / margin / perpetual) and which column is the DELISTING time
    table_map = {}
    for tb in re.findall(r"<table.*?</table>", art, re.S):
        trs = re.findall(r"<tr.*?</tr>", tb, re.S)
        if not trs:
            continue
        hdr = [text_of(c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", trs[0], re.S)]
        h0 = " ".join(hdr[:1]).lower()
        tkind = ("margin" if ("الضمان" in h0 or "margin" in h0) else "perpetual_futures" if ("الدائمة" in h0 or "perpetual" in h0) else
                 "expiry_futures" if ("الآجلة" in h0 and "الدائمة" not in h0) or "expiry" in h0 else "spot" if ("الفوري" in h0 or "spot" in h0) else None)
        dcol = next((k for k, c in enumerate(hdr) if "إلغاء الإدراج" in c or "delist" in c.lower()), None)
        for tr in trs[1:]:
            cells = [text_of(c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if not cells:
                continue
            first = cells[0]
            ins = [f"{b.upper()}-{q.replace('Ⓢ', 'S')}" for b, q, k in PAIR.findall(first)]
            if not ins and tkind in ("perpetual_futures", None):
                ins = [f"{b}-{q}-SWAP" for b, q in SWAP.findall(first)]
            cell = cells[dcol] if dcol is not None and dcol < len(cells) else " | ".join(cells[1:])
            ds = dates_in(cell, locale)
            if ins and ds:
                p, d, mo, y, e = ds[0]
                x, yi = mk_date(d, mo, y, pub, time_near(cell, p, e + 60) or time_near(cell, 0, len(cell)))
                for i in ins:
                    table_map.setdefault(i, (x, yi, " | ".join(cells)[:140], tkind))
    found = []
    for b, q, k in PAIR.findall(t):
        i = f"{b.upper()}-{q.replace('Ⓢ', 'S')}"
        if i not in found:
            found.append(i)
    if mt == "perpetual_futures":
        for b, q in SWAP.findall(t):
            i = f"{b}-{q}-SWAP"
            if i not in found and b not in ("OKX",):
                found.append(i)
    for i in found:
        rmt = mt
        if i in table_map:
            x, yi, ev, tk = table_map[i]; meth = "table_row"; rmt = tk or mt
            if tk is None and "-SWAP" not in i and "margin" in slug:
                rmt = "margin"
        else:
            x, yi, ev = ex, ex_yi, (ex_k or ""); meth = "execution_section" if ex else "not_found"
            if "-SWAP" in i:
                rmt = "perpetual_futures"
            elif mt == "perpetual_futures" and "margin" in slug:
                rmt = "margin"
            elif mt == "perpetual_futures" and "spot" in slug:
                rmt = "spot"
        conflict = bool(x and pub and x < pub - dt.timedelta(hours=1))
        rows.append(dict(base, market_type=rmt, instrument=i, date_conflict=int(conflict), base_asset=i.split("-")[0], quote=i.split("-")[1] if "-" in i else "",
                         effective_delisting_utc=x.strftime("%Y-%m-%d %H:%M") if x else "", date_method=meth, year_inferred=int(bool(yi)),
                         deposit_suspension_utc=dep.strftime("%Y-%m-%d %H:%M") if dep else "",
                         asset_withdrawal_suspension_utc=wd.strftime("%Y-%m-%d %H:%M") if wd else "",
                         asset_full_delisting=("stated: withdrawals of the affected crypto suspended" if wd else "not stated"),
                         usdt_typo_fixed=int("USDTK" in t and i.endswith("-USDT")), evidence=(ev or "")[:140].replace("\n", " ")))
    if not rows:
        rows.append(dict(base, instrument="", date_method="no_instrument_found", note="announcement kept; no pair/contract string parsed"))
    return rows


COLS = ["region", "locale", "market_type", "instrument", "base_asset", "quote", "announcement_utc", "effective_delisting_utc", "date_method", "year_inferred",
        "deposit_suspension_utc", "asset_withdrawal_suspension_utc", "asset_full_delisting", "title", "slug", "official_url", "raw_file", "raw_sha256",
        "collected_utc", "usdt_typo_fixed", "date_conflict", "evidence", "note", "correction"]


def apply_corrections(rows, locale):
    """ledger_corrections/corrections.csv: documented, reviewed fixes. The wrong value is kept in the `correction` column."""
    f = LAB / "ledger_corrections" / "corrections.csv"
    if not f.exists():
        return 0
    n = 0
    for c in csv.DictReader(open(f, encoding="utf-8")):
        if c["locale"] != locale:
            continue
        for r in rows:
            if r.get("slug") == c["slug"] and r.get(c["field"]) == c["old_value"]:
                r[c["field"]] = c["new_value"]
                if c["field"] == "instrument":
                    r["base_asset"] = c["new_value"].split("-")[0]
                r["correction"] = f"#{c['id']}: {c['field']} {c['old_value']} -> {c['new_value']}"
                n += 1
    return n


def main(locale):
    src = LAB / "out" / "delisting_raw" / locale
    man = json.load(open(src / "manifest.json", encoding="utf-8"))
    out = LAB / "out" / "ledger" / locale
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for it in man["list"]:
        p = src / "articles" / f"{it['slug']}.html"
        if not p.exists():
            rows.append({"region": locale, "slug": it["slug"], "title": it["title"], "note": "article raw missing"}); continue
        rows += parse_article(p, locale, it, man["collected_utc"])
    n_corr = apply_corrections(rows, locale)
    with open(out / "delisting_ledger.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    import collections
    notes = {"corrections_applied": n_corr, "announcements": len(man["list"]), "rows": len(rows), "by_market_type": dict(collections.Counter(r.get("market_type", "") for r in rows)),
             "by_date_method": dict(collections.Counter(r.get("date_method", "") for r in rows)),
             "year_inferred": sum(1 for r in rows if r.get("year_inferred") == 1),
             "spot_rows_with_withdrawal_suspension": sum(1 for r in rows if r.get("market_type") == "spot" and r.get("asset_withdrawal_suspension_utc")),
             "date_conflicts": [(r["slug"], r["instrument"], r["announcement_utc"], r["effective_delisting_utc"]) for r in rows if r.get("date_conflict")]}
    (out / "parse_notes.json").write_text(json.dumps(notes, indent=1, ensure_ascii=False))
    print(json.dumps(notes, indent=1, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main(sys.argv[1])
