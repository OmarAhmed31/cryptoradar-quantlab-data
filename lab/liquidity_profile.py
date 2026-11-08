"""Liquidity profiling for the Research Universe Policy (expert request after v0.9, 2026-11-08). OFFLINE, no network.
No strategy result, signal or return is read or used: only hourly trade counts and quote volume.

python3 -I lab/liquidity_profile.py <out_dir> <active_final_dir> <delisted_dir> <addendum_dir>

Point-in-time (prior data only): the metric for UTC day d uses the 30 full UTC days [d-30, d-1].
  listed_hours(d)   hours the pair was in its dataset range that day (start..end / delisting cut)
  traded_hours(d)   hours with >= 1 traded minute (rows of the rule-B hourly file)
  dv(d)             quote volume of the day in USDT (~ USD)
  THR30             sum traded_hours / sum listed_hours over the 30-day window
  DV30_med / mean   median / mean of dv over the 30 days (days listed only; a listed day with no trade counts as 0)
  hist_days         listed days in the window (a pair needs 30 to be assessable)
Research start: 2024-01-01 00:00 UTC (common start); earlier hours are ignored.
"""
import sys, csv, gzip, io, json, pathlib, datetime as dt
import numpy as np
import pandas as pd

R0 = pd.Timestamp("2024-01-01", tz="UTC")
H = pd.Timedelta(hours=1)


def load(dirp, ranges, group):
    rows = []
    for p, (s, e) in ranges.items():
        f = pathlib.Path(dirp) / "hourly" / f"{p}.csv.gz"
        d = pd.read_csv(f, usecols=["ts_utc_ms", "vol_quote"], dtype={"ts_utc_ms": "int64", "vol_quote": "float64"})
        d["pair"] = p
        rows.append(d)
    df = pd.concat(rows, ignore_index=True)
    df["ts"] = pd.to_datetime(df["ts_utc_ms"], unit="ms", utc=True)
    df = df[df["ts"] >= R0]
    df["group"] = group
    return df


def listed_hours_by_day(ranges):
    out = []
    for p, (s, e) in ranges.items():
        s = max(s, R0)
        if e <= s:
            continue
        hrs = pd.date_range(s.floor("h"), e - pd.Timedelta(microseconds=1), freq="h")
        d = pd.Series(1, index=hrs).groupby(hrs.floor("D")).sum()
        out.append(pd.DataFrame({"pair": p, "day": d.index, "listed_hours": d.values}))
    return pd.concat(out, ignore_index=True)


def ranges_active(dirp):
    r = {}
    for q in csv.DictReader(open(pathlib.Path(dirp) / "dataset_index.csv")):
        r[q["pair"]] = (pd.Timestamp(q["start_utc"], tz="UTC"), pd.Timestamp(q["end_exclusive_utc"], tz="UTC"))
    return r


def ranges_delisted(dirp):
    r = {}
    for q in csv.DictReader(open(pathlib.Path(dirp) / "pair_quality.csv")):
        if q.get("first_minute_utc"):
            r[q["pair"]] = (pd.Timestamp(q["first_minute_utc"], tz="UTC"), pd.Timestamp(q["effective_delisting_utc"], tz="UTC"))
    return r


def main(out_dir, active_dir, delisted_dir, addendum_dir):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    RA, RD, RX = ranges_active(active_dir), ranges_delisted(delisted_dir), ranges_delisted(addendum_dir)
    # a ticker in both an active current listing and a delisted OLD segment (DASH/ZEC/ZEN) is kept as two separate series
    parts = [(load(active_dir, RA, "active"), RA, "active"), (load(delisted_dir, RD, "delisted"), RD, "delisted"),
             (load(addendum_dir, RX, "delisted_jan2024"), RX, "delisted_jan2024")]
    daily = []
    for df, rng, g in parts:
        df["day"] = df["ts"].dt.floor("D")
        tr = df.groupby(["pair", "day"]).agg(traded_hours=("ts", "size"), dv=("vol_quote", "sum")).reset_index()
        lh = listed_hours_by_day(rng)
        m = lh.merge(tr, on=["pair", "day"], how="left").fillna({"traded_hours": 0, "dv": 0.0})
        m["series"] = m["pair"]
        m["group"] = g
        daily.append(m)
    D = pd.concat(daily, ignore_index=True)
    D.loc[(D["group"] == "delisted_jan2024") & D["pair"].isin(["DASH-USDT", "ZEC-USDT", "ZEN-USDT"]), "series"] = D["pair"] + "#old_listing"
    D = D.sort_values(["series", "day"]).reset_index(drop=True)
    # point-in-time rolling window over the PREVIOUS 30 listed days (shift(1) excludes day d itself)
    g = D.groupby("series", group_keys=False)
    D["lh30"] = g["listed_hours"].apply(lambda s: s.shift(1).rolling(30, min_periods=1).sum())
    D["th30"] = g["traded_hours"].apply(lambda s: s.shift(1).rolling(30, min_periods=1).sum())
    D["hist_days"] = g["listed_hours"].apply(lambda s: s.shift(1).rolling(30, min_periods=1).count())
    D["DV30_med"] = g["dv"].apply(lambda s: s.shift(1).rolling(30, min_periods=1).median())
    D["DV30_mean"] = g["dv"].apply(lambda s: s.shift(1).rolling(30, min_periods=1).mean())
    D["THR30"] = D["th30"] / D["lh30"]
    # calendar continuity check: listed days of a series must be consecutive (a gap would make "30 rows" != 30 days)
    gaps = g["day"].apply(lambda s: int((s.diff().dropna() != pd.Timedelta(days=1)).sum())).sum()
    D["assessable"] = (D["hist_days"] >= 30)
    keep = ["series", "pair", "group", "day", "listed_hours", "traded_hours", "dv", "hist_days", "THR30", "DV30_med", "DV30_mean", "assessable"]
    D[keep].assign(day=D["day"].dt.strftime("%Y-%m-%d")).to_csv(out / "daily_liquidity_point_in_time.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    A = D[D["assessable"]]
    q = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
    dist = {"series": int(D["series"].nunique()), "pair_days": int(len(D)), "assessable_pair_days": int(len(A)),
            "calendar_gaps_inside_series": int(gaps),
            "THR30_quantiles": {str(k): round(float(v), 4) for k, v in A["THR30"].quantile(q).items()},
            "DV30_med_quantiles_usd": {str(k): round(float(v)) for k, v in A["DV30_med"].quantile(q).items()},
            "by_group": {}}
    for gname, x in A.groupby("group"):
        dist["by_group"][gname] = {"series": int(x["series"].nunique()), "pair_days": int(len(x)),
                                   "THR30_median": round(float(x["THR30"].median()), 4), "DV30_med_median_usd": round(float(x["DV30_med"].median()))}
    # sensitivity grid: eligible series per month end (no returns involved)
    thr_grid, dv_grid = [0.5, 0.8, 0.9, 0.95], [10_000, 50_000, 100_000, 250_000, 1_000_000]
    A2 = A.assign(month=A["day"].dt.strftime("%Y-%m"))
    last = A2.sort_values("day").groupby(["month", "series"]).tail(1)            # each series' last day in the month
    sens = []
    for t in thr_grid:
        for v in dv_grid:
            el = last[(last["THR30"] >= t) & (last["DV30_med"] >= v)]
            byg = el.groupby("month")["series"].nunique()
            dl = el[el["group"] != "active"].groupby("month")["series"].nunique()
            tot = last.groupby("month")["series"].nunique()
            for mth in tot.index:
                sens.append({"THR30_min": t, "DV30_med_min_usd": v, "month": mth, "assessable_series": int(tot[mth]),
                             "eligible": int(byg.get(mth, 0)), "eligible_delisted_later": int(dl.get(mth, 0)),
                             "eligible_share": round(float(byg.get(mth, 0)) / float(tot[mth]), 4)})
    pd.DataFrame(sens).to_csv(out / "eligibility_sensitivity_by_month.csv", index=False)
    # per-series summary (median over its assessable days)
    ps = A.groupby(["series", "group"]).agg(days=("day", "size"), THR30_median=("THR30", "median"), DV30_med_median=("DV30_med", "median"),
                                             first_assessable=("day", "min"), last_day=("day", "max")).reset_index()
    ps["first_assessable"] = ps["first_assessable"].dt.strftime("%Y-%m-%d"); ps["last_day"] = ps["last_day"].dt.strftime("%Y-%m-%d")
    ps.to_csv(out / "series_liquidity_summary.csv", index=False)
    json.dump(dist, open(out / "liquidity_distribution.json", "w"), indent=1)
    print(json.dumps(dist, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
