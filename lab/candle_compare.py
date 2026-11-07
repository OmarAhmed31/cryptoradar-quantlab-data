"""Offline: OKX archive 1m candles (aggregated to 1H UTC) vs verified history-candles 1H (probe 20261107T135059Z).

python3 -I lab/candle_compare.py <candles_dir> <probe_dir> <out_dir>
No network. Exact decimal comparison; nothing is filled or invented.
 - archive file month/day are UTC+8; open_time is ms UTC (checked: first minute = 16:00 UTC of the previous day).
 - an hour is aggregated only from the minutes present; missing minutes are counted, never created.
"""
import sys, csv, io, json, gzip, zipfile, pathlib, collections, datetime as dt
from decimal import Decimal as Dm

H, M = 3600000, 60000


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def load_minutes(zpath):
    z = zipfile.ZipFile(zpath)
    rows = list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))))
    return rows


def load_verified(probe_dir, coin):
    out = {}
    for l in gzip.open(pathlib.Path(probe_dir) / f"{coin}_raw_pages.jsonl.gz", "rt"):
        j = json.loads(json.loads(l)["body"])
        for c in j.get("data") or []:
            if c[8] == "1":
                out.setdefault(int(c[0]), c)
    return out


def compare(zpath, probe_dir):
    coin = pathlib.Path(zpath).name.split("-")[0]
    rows = load_minutes(zpath)
    ts = [int(r["open_time"]) for r in rows]
    r0 = {"pair": f"{coin}-USDT", "file": pathlib.Path(zpath).name, "header": list(rows[0].keys()), "minutes_in_file": len(rows),
          "first_minute_utc": iso(min(ts)), "last_minute_utc": iso(max(ts))}
    span = (max(ts) - min(ts)) // M + 1
    st = sorted(set(ts))
    r0["duplicate_minutes"] = len(ts) - len(st)
    r0["expected_minutes_in_span"] = span
    r0["missing_minutes"] = span - len(st)
    r0["unconfirmed_minutes"] = sum(1 for r in rows if r["confirm"] != "1")
    zero = [r for r in rows if Dm(r["vol"]) == 0]
    r0["zero_volume_minutes"] = len(zero)
    by = {int(r["open_time"]): r for r in rows}
    flat_prev = 0
    for r in zero:
        p = by.get(int(r["open_time"]) - M)
        if r["open"] == r["high"] == r["low"] == r["close"] and p and Dm(r["close"]) == Dm(p["close"]):
            flat_prev += 1
    r0["zero_volume_minutes_flat_at_prev_close"] = flat_prev
    r0["bad_ohlc_minutes"] = sum(1 for r in rows if not (Dm(r["low"]) <= min(Dm(r["open"]), Dm(r["close"])) <= max(Dm(r["open"]), Dm(r["close"])) <= Dm(r["high"])))
    r0["vol_ccy_equals_vol_quote"] = all(r["vol_ccy"] == r["vol_quote"] for r in rows)
    # aggregate to UTC hours
    hrs = collections.defaultdict(list)
    for t in st:
        hrs[t - t % H].append(by[t])
    r0["hours_with_no_traded_minute"] = sum(1 for ms_ in hrs.values() if not any(Dm(x["vol"]) > 0 for x in ms_))
    out_rules = {}
    for rule in ("A_all_minutes", "B_traded_minutes_only"):
        agg = {}
        for h, ms_all in hrs.items():
            ms_ = ms_all if rule == "A_all_minutes" else ([x for x in ms_all if Dm(x["vol"]) > 0] or ms_all)
            agg[h] = {"o": Dm(ms_[0]["open"]), "h": max(Dm(x["high"]) for x in ms_), "l": min(Dm(x["low"]) for x in ms_),
                      "c": Dm(ms_[-1]["close"]), "vol": sum(Dm(x["vol"]) for x in ms_), "vol_ccy": sum(Dm(x["vol_ccy"]) for x in ms_),
                      "n_min": len(ms_)}
        ver = load_verified(probe_dir, coin)
        lo, hi = min(agg), max(agg)
        vh = {h: c for h, c in ver.items() if lo <= h <= hi}
        both = sorted(set(agg) & set(vh))
        r0["archive_hours"] = len(agg)
        r0["archive_hours_with_<60_minutes"] = sum(1 for a in agg.values() if a["n_min"] < 60)
        r0["verified_hours_in_span"] = len(vh)
        r0["hours_only_in_archive"] = [iso(h) for h in sorted(set(agg) - set(vh))][:20]
        r0["hours_only_in_verified"] = [iso(h) for h in sorted(set(vh) - set(agg))][:20]
        r0["hours_compared"] = len(both)
        cols = {"open": ("o", 1), "high": ("h", 2), "low": ("l", 3), "close": ("c", 4), "volume_base": ("vol", 5), "volume_quote": ("vol_ccy", 6)}
        res = {}
        for name, (k, i) in cols.items():
            diffs = []
            for h in both:
                a, v = agg[h][k], Dm(ver[h][i])
                d = abs(a - v)
                if d != 0:
                    diffs.append((d, h, a, v))
            mx = max(diffs) if diffs else None
            res[name] = {"mismatches": len(diffs),
                         "max_abs_diff": str(mx[0]) if mx else "0",
                         "max_rel_diff": f"{float(mx[0] / mx[3]):.3e}" if mx and mx[3] != 0 else "0",
                         "worst_hour_utc": iso(mx[1]) if mx else "",
                         "archive_value": str(mx[2]) if mx else "", "verified_value": str(mx[3]) if mx else "",
                         "mismatches_rel_gt_1e-9": sum(1 for d in diffs if d[3] != 0 and d[0] / d[3] > Dm("1e-9"))}
        out_rules[rule] = res
    r0["columns"] = out_rules["B_traded_minutes_only"]
    r0["columns_rule_A_all_minutes"] = out_rules["A_all_minutes"]
    return r0


def main(cdir, pdir, odir):
    out = pathlib.Path(odir); out.mkdir(parents=True, exist_ok=True)
    R = [compare(z, pdir) for z in sorted(pathlib.Path(cdir).glob("*-candlesticks-*.zip"))]
    (out / "candle_comparison.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    s = "# 1m archive → 1H vs verified history-candles (exact decimal comparison)\n\n"
    s += "| pair | minutes | missing min | dup | zero-vol min (flat at prev close) | hours compared | only archive / only verified |\n|---|---|---|---|---|---|---|\n"
    for r in R:
        s += f"| {r['pair']} | {r['minutes_in_file']} ({r['first_minute_utc']} → {r['last_minute_utc']} UTC) | {r['missing_minutes']} | {r['duplicate_minutes']} | {r['zero_volume_minutes']} ({r['zero_volume_minutes_flat_at_prev_close']}) | {r['hours_compared']} | {len(r['hours_only_in_archive'])} / {len(r['hours_only_in_verified'])} |\n"
    s += "\nZero-volume minutes are written by OKX as flat candles at the previous close (no trade). Rule A aggregates every minute; rule B aggregates only minutes with volume > 0 (an hour with no traded minute would keep its flat minutes; count shown in JSON).\n"
    s += "\n## Rule A: all minutes\n\n| pair | column | mismatches | max abs diff | max rel diff | worst hour UTC |\n|---|---|---|---|---|---|\n"
    for r in R:
        for c, v in r["columns_rule_A_all_minutes"].items():
            s += f"| {r['pair']} | {c} | {v['mismatches']} | {v['max_abs_diff']} | {v['max_rel_diff']} | {v['worst_hour_utc']} |\n"
    s += "\n## Rule B: traded minutes only\n"
    s += "\n| pair | column | mismatches | max abs diff | max rel diff | worst hour UTC (archive vs verified) |\n|---|---|---|---|---|---|\n"
    for r in R:
        for c, v in r["columns"].items():
            s += f"| {r['pair']} | {c} | {v['mismatches']} | {v['max_abs_diff']} | {v['max_rel_diff']} | {v['worst_hour_utc']} {('(' + v['archive_value'] + ' vs ' + v['verified_value'] + ')') if v['worst_hour_utc'] else ''} |\n"
    (out / "candle_comparison.md").write_text(s, encoding="utf-8")
    print(s)


if __name__ == "__main__":
    main(*sys.argv[1:4])
