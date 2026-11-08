"""Forced-exit reference for delisted series (Protocol U9). OFFLINE. Minute data only, no strategy data.

python3 -I lab/forced_exit_reference.py <out_csv> <dataset_dir>:<raw_dir> [<dataset_dir>:<raw_dir> ...]

For each delisted series: the LAST traded minute strictly before the cut (vol > 0, open_time + 60 s <= cut),
its close (= price of the last trade in that minute), and the gap to the cut.
status = PRICED if gap <= MAX_STALE_MIN, else UNPRICEABLE_FORCED_EXIT. No price is invented or carried forward.
Minute precision: the trade happened inside [last_traded_minute, +60 s).
"""
import sys, csv, io, zipfile, pathlib, datetime as dt
from decimal import Decimal as Dm

MAX_STALE_MIN = 60
OLD = {"DASH-USDT", "ZEC-USDT", "ZEN-USDT"}


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def main(out_csv, *pairs_dirs):
    rows = []
    for spec in pairs_dirs:
        ds, raw = spec.split(":")
        add = "jan2024_addendum" in ds
        cut_meta = {}
        if add:
            cut_meta = {r["pair"]: r for r in csv.DictReader(open(pathlib.Path(ds) / "cutoff_meta.csv"))}
        for q in csv.DictReader(open(pathlib.Path(ds) / "pair_quality.csv")):
            p = q["pair"]
            cut = int(dt.datetime.strptime(q["effective_delisting_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            last = None
            for fz in sorted((pathlib.Path(raw) / p).glob("*.zip")):
                z = zipfile.ZipFile(fz)
                for x in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))):
                    t = int(x["open_time"])
                    if x["instrument_name"] == p and t + 60000 <= cut and Dm(x["vol"]) > 0 and (last is None or t > last[0]):
                        last = (t, x["close"])
            gap = round((cut - last[0]) / 60000) if last else None
            rows.append({"series": p + ("#old_listing" if add and p in OLD else ""), "dataset": "jan2024_addendum" if add else "delisted_v0.7.1",
                         "cut_utc": iso(cut), "cutoff_precision": cut_meta.get(p, {}).get("cutoff_precision", "stated_time"),
                         "window_end_utc": cut_meta.get(p, {}).get("window_end_utc", ""),
                         "last_traded_minute_utc": iso(last[0]) if last else "", "last_trade_price": last[1] if last else "",
                         "minutes_last_trade_to_cut": gap if gap is not None else "",
                         "status": ("PRICED" if gap is not None and gap <= MAX_STALE_MIN else "UNPRICEABLE_FORCED_EXIT"),
                         "max_stale_minutes_rule": MAX_STALE_MIN})
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    import collections
    print(len(rows), collections.Counter(r["status"] for r in rows), sorted((int(r["minutes_last_trade_to_cut"]) for r in rows if r["minutes_last_trade_to_cut"] != ""))[-8:])


if __name__ == "__main__":
    main(*sys.argv[1:])
