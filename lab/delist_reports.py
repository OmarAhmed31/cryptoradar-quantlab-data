"""Build regional comparison + data coverage reports from the ledgers, live instruments and availability results.

python3 -I lab/delist_reports.py <availability_run_dir> <live_instruments_raw.json> <out_dir> [signals.csv]
signals.csv is optional and stays LOCAL (never committed to the public repo).
"""
import sys, csv, json, collections, pathlib, datetime as dt

D = 86400000


def ms(s):
    return int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def month_ends(a, b):
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        ny, nm = (y + (m == 12), m % 12 + 1)
        yield f"{y}-{m:02d}", int(dt.datetime(ny, nm, 1, tzinfo=dt.timezone.utc).timestamp() * 1000) - 1
        y, m = ny, nm


def main(avail_dir, live_raw, out_dir, signals=None):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    L = {loc: list(csv.DictReader(open(f"out/ledger/{loc}/delisting_ledger.csv", encoding="utf-8"))) for loc in ("ar", "en-eu")}
    M = {loc: json.load(open(f"out/delisting_raw/{loc}/manifest.json", encoding="utf-8")) for loc in ("ar", "en-eu")}
    AV = list(csv.DictReader(open(pathlib.Path(avail_dir) / "delisting_data_availability.csv")))
    live = json.loads(json.load(open(live_raw))["body"])["data"]
    liveU = {x["instId"]: int(x["listTime"]) if x.get("listTime") else None for x in live if x["instId"].endswith("-USDT")}

    # ---------------- regional comparison
    s = "# Regional archive comparison — global (ar) vs Europe (en-eu)\n\nThe two archives are kept SEPARATE. Nothing from one is copied into the other.\n\n"
    s += "| | global (`/ar/`) | Europe (`/en-eu/`) |\n|---|---|---|\n"
    for loc in ("ar", "en-eu"):
        pass
    a, e = M["ar"], M["en-eu"]
    s += f"| archive pages | {a['pages_fetched']} | {e['pages_fetched']} |\n| announcements | {a['items']} | {e['items']} |\n"
    s += f"| oldest / newest | {a['list'][-1]['date_text']} / {a['list'][0]['date_text']} | {e['list'][-1]['date_text']} / {e['list'][0]['date_text']} |\n"
    for loc, col in (("ar", 1), ("en-eu", 2)):
        pass
    cnt = {loc: collections.Counter(r["market_type"] for r in L[loc] if r.get("instrument")) for loc in L}
    for mt in sorted(set(cnt["ar"]) | set(cnt["en-eu"])):
        s += f"| rows: {mt} | {cnt['ar'].get(mt, 0)} | {cnt['en-eu'].get(mt, 0)} |\n"
    sa, se = {i["slug"] for i in a["list"]}, {i["slug"] for i in e["list"]}
    s += f"\n- Same announcement (slug) in both: **{len(sa & se)}** · global only: **{len(sa - se)}** · Europe only: **{len(se - sa)}**.\n"
    A = {(r["slug"], r["instrument"]): r for r in L["ar"] if r.get("instrument")}
    E = {(r["slug"], r["instrument"]): r for r in L["en-eu"] if r.get("instrument")}
    both = set(A) & set(E)
    agree = [k for k in both if A[k]["effective_delisting_utc"] == E[k]["effective_delisting_utc"]]
    spot_both = [k for k in both if A[k]["market_type"] == "spot"]
    spot_agree = [k for k in spot_both if A[k]["effective_delisting_utc"] == E[k]["effective_delisting_utc"]]
    s += f"- Same (announcement, instrument) in both: {len(both)}; effective date identical: {len(agree)}. **Spot: {len(spot_agree)} of {len(spot_both)} identical.**\n"
    dis = sorted(k for k in both if A[k]["effective_delisting_utc"] != E[k]["effective_delisting_utc"])
    if dis:
        s += "\n| announcement | instrument | global | Europe | type (global / Europe) |\n|---|---|---|---|---|\n"
        s += "".join(f"| {k[0]} | {k[1]} | {A[k]['effective_delisting_utc'] or '—'} | {E[k]['effective_delisting_utc'] or '—'} | {A[k]['market_type']} / {E[k]['market_type']} |\n" for k in dis)
    eu_only_spot = sorted({r["instrument"] for r in L["en-eu"] if r["market_type"] == "spot" and r["slug"] in (se - sa)})
    s += f"\n- **Europe-only spot delistings** (not in the global archive — do NOT apply to the global universe): {len(eu_only_spot)} pairs: {', '.join(eu_only_spot)}.\n"
    s += "\nAll announcements from the US region (`/en-us/`, served to US IPs on `/help/`) were collected in the first probe only and are **not used**.\n"
    (out / "regional_archive_comparison.md").write_text(s, encoding="utf-8")

    # ---------------- coverage
    g_spot = [r for r in L["ar"] if r["market_type"] == "spot" and r.get("instrument")]
    av = {r["instrument"]: r for r in AV}
    gU = sorted({r["instrument"] for r in g_spot if r["instrument"].endswith("-USDT")})
    st = collections.Counter(av[i]["status"] for i in gU if i in av)
    still_live = [i for i in gU if i in av and av[i]["in_live_instruments"] == "1"]
    full_wd = sum(1 for r in g_spot if r["asset_withdrawal_suspension_utc"])
    c = "# Data coverage report\n\n## 1. Sources\n\n"
    c += f"- Live pairs: OKX `/api/v5/public/instruments?instType=SPOT` (global API), {len(live)} SPOT pairs, {len(liveU)} USDT pairs, with `listTime`.\n"
    c += f"- Delisted pairs: OKX official global delisting archive (`/ar/`), {a['items']} announcements, {a['list'][-1]['date_text']} → {a['list'][0]['date_text']}.\n"
    c += "- Candles: OKX `/api/v5/market/history-candles` (1Dutc full range + 1H last 30 days before delisting), raw pages saved.\n\n"
    c += f"## 2. Delisted global spot pairs\n\n- Spot rows in the global ledger: {len(g_spot)} ({len(gU)} USDT pairs).\n"
    c += f"- Candle availability for those USDT pairs: **full {st.get('full', 0)} · partial {st.get('partial', 0)} · none {st.get('none', 0)}**.\n"
    c += f"- Of these delisted USDT pairs, still present in today's live instrument list: {len(still_live)} {still_live[:15]}.\n"
    c += f"- Spot rows whose announcement explicitly states a withdrawal suspension (asset removed from the platform): {full_wd} of {len(g_spot)}. The rest: pair delisting only, or not stated.\n\n"
    # monthly universe
    dl = {i: ms(av[i]["effective_delisting_utc"]) for i in gU if i in av}
    first = {i: (ms(av[i]["first_1d"]) if av[i]["first_1d"] else None) for i in gU if i in av}
    c += "## 3. USDT spot pairs tradable on OKX by month (point-in-time)\n\n| month end | live today & listed by then | delisted later but tradable then | total | delisted share |\n|---|---|---|---|---|\n"
    for m, end in month_ends(dt.date(2024, 1, 1), dt.date.today()):
        a1 = sum(1 for i, t in liveU.items() if t and t <= end)
        b1 = sum(1 for i in dl if dl[i] > end and first[i] is not None and first[i] <= end)
        c += f"| {m} | {a1} | {b1} | {a1 + b1} | {100 * b1 / (a1 + b1):.1f}% |\n" if a1 + b1 else ""
    c += "\n- Pairs delisted BEFORE Jan 2024 are not in the archive → months before 2024 cannot be rebuilt from this source. Coverage starts Jan 2024.\n"
    c += "- `listTime` of a live pair is its OKX listing time; for a delisted pair, the first daily candle is used as its listing proxy (flagged).\n\n"
    if signals:
        S = list(csv.DictReader(open(signals, encoding="utf-8-sig")))
        ok = late = unknown = after = 0
        for r in S:
            ts = int(r["signal_id"].rsplit("_", 1)[1]); inst = r["sym"] + "-USDT"
            if inst in liveU:
                if liveU[inst] and liveU[inst] <= ts: ok += 1
                elif liveU[inst]: late += 1
                else: unknown += 1
            elif inst in dl:
                ok += (ts < dl[inst]); after += (ts >= dl[inst])
            else:
                unknown += 1
        c += f"## 4. CryptoRadar signals (local check, not published)\n\n- {len(S)} signals: pair tradable on OKX at signal time **{ok}** · listed after signal {late} · signal after delisting {after} · unknown {unknown}.\n"
        c += "- No coin is removed from research because it is delisted today: availability is judged at the signal's own date.\n"
    (out / "data_coverage_report.md").write_text(c, encoding="utf-8")
    print("reports written to", out)


if __name__ == "__main__":
    main(*sys.argv[1:4], sys.argv[4] if len(sys.argv) > 4 else None)
