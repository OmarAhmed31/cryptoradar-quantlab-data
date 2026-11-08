"""Liquidity profiling v2 for the Research Universe Policy (v0.10.1, after expert review). OFFLINE, no network.
No strategy result, signal or return is read or used: only hourly trade counts and quote volume.

python3 -I lab/liquidity_profile.py <out_dir> <active_final_dir> <delisted_dir> <addendum_dir> [<warmup_dir>]

Point-in-time, CALENDAR window: the metric for UTC day d uses exactly the 30 calendar days d-30 .. d-1
(pandas rolling('30D', closed='left') on a complete daily calendar; day d and later never enter).
  listed_hours(day)   hours the series was inside its data range that day (0..24)
  full_day            listed MINUTES == 1440 (a day with the listing or the cut inside it is partial)
  full_days30         number of FULL days among the 30 window days   -> assessable only if == 30
  THR30               traded hours / listed hours over the window
  DV30_med / mean     median / mean of the daily quote volume (USDT ~ USD) over the window days
Warm-up (optional): December 2023 hourly used ONLY inside windows; days < 2024-01-01 are never research days.
Partial first/last days (listing mid-day, delisting cut) are partial days: they never count as full days.
"""
import sys, csv, json, pathlib
import numpy as np
import pandas as pd

R0 = pd.Timestamp("2024-01-01", tz="UTC")
W0 = pd.Timestamp("2023-12-01", tz="UTC")
OLD = {"DASH-USDT", "ZEC-USDT", "ZEN-USDT"}


# ---------------------------------------------------------------- pure computation (tested for leakage)
def compute(daily):
    """daily: columns series, day (UTC midnight, tz-aware), listed_hours, listed_minutes, traded_hours, dv.
    Returns a copy with the window metrics. Each series is first placed on a complete daily calendar
    (missing calendar days = listed 0), so the window is always 30 calendar days."""
    out = []
    for s, x in daily.groupby("series", sort=True):
        x = x.set_index("day").sort_index()
        cal = pd.date_range(x.index.min(), x.index.max(), freq="D", tz="UTC")
        x = x.reindex(cal)
        x["series"] = s
        x[["listed_hours", "listed_minutes", "traded_hours", "dv"]] = x[["listed_hours", "listed_minutes", "traded_hours", "dv"]].fillna(0)
        x["full_day"] = (x["listed_minutes"] == 1440).astype(int)          # a partial day (listing / cut inside it) is never full
        x["listed_day"] = (x["listed_hours"] > 0).astype(int)
        r = x.rolling("30D", closed="left")
        lh, th = r["listed_hours"].sum(), r["traded_hours"].sum()
        x["full_days30"] = r["full_day"].sum().fillna(0).astype(int)
        x["THR30"] = (th / lh).where(lh > 0)
        dvw = x["dv"].where(x["listed_day"] == 1)            # only listed days enter the volume statistics
        x["DV30_med"] = dvw.rolling("30D", closed="left").median()
        x["DV30_mean"] = dvw.rolling("30D", closed="left").mean()
        x["assessable"] = x["full_days30"] == 30
        out.append(x.rename_axis("day").reset_index())
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------- inputs
def hourly_counts(path, s, e):
    d = pd.read_csv(path, usecols=["ts_utc_ms", "vol_quote"], dtype={"ts_utc_ms": "int64", "vol_quote": "float64"})
    t = pd.to_datetime(d["ts_utc_ms"], unit="ms", utc=True)
    d = d[(t >= s) & (t < e)].assign(day=t.dt.floor("D"))
    return d.groupby("day").agg(traded_hours=("ts_utc_ms", "size"), dv=("vol_quote", "sum"))


def listed_by_day(s, e):
    """per UTC day: hours overlapping [s, e) (denominator of THR30) and listed MINUTES (a full day = 1440)."""
    if e <= s:
        return pd.DataFrame(columns=["listed_hours", "listed_minutes"])
    hrs = pd.date_range(s.floor("h"), e - pd.Timedelta(microseconds=1), freq="h")
    lh = pd.Series(1, index=hrs).groupby(hrs.floor("D")).sum()
    days = pd.date_range(s.floor("D"), (e - pd.Timedelta(microseconds=1)).floor("D"), freq="D")
    lm = pd.Series([int((min(d + pd.Timedelta(days=1), e) - max(d, s)) / pd.Timedelta(minutes=1)) for d in days], index=days)
    return pd.DataFrame({"listed_hours": lh, "listed_minutes": lm}).fillna(0)


def series_frame(series, group, path, s, e, warm=None):
    """listed hours count only whole hours fully inside [s, e) for the research part; warm-up adds its own range."""
    parts = []
    lb = listed_by_day(max(s, R0), e)
    hc = hourly_counts(path, max(s, R0), e)
    f = lb.join(hc, how="left").fillna({"traded_hours": 0, "dv": 0.0})
    f["warmup"] = 0
    parts.append(f)
    if warm is not None:
        wpath, ws, we = warm
        lbw = listed_by_day(ws, we)
        hcw = hourly_counts(wpath, ws, we)
        fw = lbw.join(hcw, how="left").fillna({"traded_hours": 0, "dv": 0.0})
        fw["warmup"] = 1
        parts.append(fw)
    f = pd.concat(parts).groupby(level=0).agg({"listed_hours": "sum", "listed_minutes": "sum", "traded_hours": "sum", "dv": "sum", "warmup": "max"})
    f = f.rename_axis("day").reset_index()
    f["series"], f["group"] = series, group
    return f


def load_all(active_dir, delisted_dir, addendum_dir, warmup_dir=None):
    W = {}
    if warmup_dir:
        for q in csv.DictReader(open(pathlib.Path(warmup_dir) / "warmup_quality.csv")):
            if q["first_minute_utc"]:
                W[q["series"]] = (pathlib.Path(warmup_dir) / "hourly" / f"{q['series']}.csv.gz",
                                  pd.Timestamp(q["first_minute_utc"], tz="UTC"), R0)
    F = []
    for q in csv.DictReader(open(pathlib.Path(active_dir) / "dataset_index.csv")):
        s, e = pd.Timestamp(q["start_utc"], tz="UTC"), pd.Timestamp(q["end_exclusive_utc"], tz="UTC")
        F.append(series_frame(q["pair"], "active", pathlib.Path(active_dir) / "hourly" / f"{q['pair']}.csv.gz", s, e, W.get(q["pair"])))
    for d, g in ((delisted_dir, "delisted"), (addendum_dir, "delisted_jan2024")):
        for q in csv.DictReader(open(pathlib.Path(d) / "pair_quality.csv")):
            if not q.get("first_minute_utc"):
                continue
            key = q["pair"] + ("#old_listing" if g == "delisted_jan2024" and q["pair"] in OLD else "")
            s, e = pd.Timestamp(q["first_minute_utc"], tz="UTC"), pd.Timestamp(q["effective_delisting_utc"], tz="UTC")
            F.append(series_frame(key, g, pathlib.Path(d) / "hourly" / f"{q['pair']}.csv.gz", s, e, W.get(key)))
    return pd.concat(F, ignore_index=True)


# ---------------------------------------------------------------- report tables
def tables(D, out, thr=0.90, dv=100_000):
    Rd = D[D["day"] >= R0].copy()                                   # research days only
    Rd["eligible"] = Rd["assessable"] & (Rd["THR30"] >= thr) & (Rd["DV30_med"] >= dv)
    A = Rd[Rd["assessable"]]
    q = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
    dist = {"series": int(D["series"].nunique()), "research_pair_days": int(len(Rd)), "assessable_research_pair_days": int(len(A)),
            "THR30_quantiles": {str(k): round(float(v), 4) for k, v in A["THR30"].quantile(q).items()},
            "DV30_med_quantiles_usd": {str(k): round(float(v)) for k, v in A["DV30_med"].quantile(q).items()},
            "by_group": {g: {"series": int(x["series"].nunique()), "assessable_pair_days": int(len(x)),
                             "THR30_median": round(float(x["THR30"].median()), 4), "DV30_med_median_usd": round(float(x["DV30_med"].median()))}
                         for g, x in A.groupby("group")}}
    grid_t, grid_v = [0.5, 0.8, 0.9, 0.95], [10_000, 50_000, 100_000, 250_000, 1_000_000]
    A2 = A.assign(month=A["day"].dt.strftime("%Y-%m"))
    last = A2.sort_values("day").groupby(["month", "series"]).tail(1)
    sens = []
    tot = last.groupby("month")["series"].nunique()
    for t in grid_t:
        for v in grid_v:
            el = last[(last["THR30"] >= t) & (last["DV30_med"] >= v)]
            e1 = el.groupby("month")["series"].nunique(); e2 = el[el["group"] != "active"].groupby("month")["series"].nunique()
            for m in tot.index:
                sens.append({"THR30_min": t, "DV30_med_min_usd": v, "month": m, "assessable_series": int(tot[m]), "eligible": int(e1.get(m, 0)),
                             "eligible_delisted_later": int(e2.get(m, 0)), "eligible_share": round(float(e1.get(m, 0)) / float(tot[m]), 4)})
    pd.DataFrame(sens).to_csv(out / "eligibility_sensitivity_by_month.csv", index=False)
    keep = ["series", "group", "day", "warmup", "listed_hours", "listed_minutes", "full_day", "traded_hours", "dv", "full_days30", "THR30", "DV30_med", "DV30_mean", "assessable"]
    D[keep].assign(day=D["day"].dt.strftime("%Y-%m-%d"), research_day=(D["day"] >= R0).astype(int)).to_csv(
        out / "daily_liquidity_point_in_time.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    Rd.assign(day=Rd["day"].dt.strftime("%Y-%m-%d"))[["series", "group", "day", "assessable", "THR30", "DV30_med", "eligible"]].to_csv(
        out / "eligibility_daily_P1.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    first = Rd[Rd["eligible"]].groupby("series")["day"].min()
    ps = A.groupby(["series", "group"]).agg(days=("day", "size"), THR30_median=("THR30", "median"), DV30_med_median=("DV30_med", "median"),
                                             first_assessable=("day", "min")).reset_index()
    ps["first_eligible_P1"] = ps["series"].map(first)
    for c in ("first_assessable", "first_eligible_P1"):
        ps[c] = pd.to_datetime(ps[c]).dt.strftime("%Y-%m-%d")
    ps.to_csv(out / "series_liquidity_summary.csv", index=False)
    json.dump(dist, open(out / "liquidity_distribution.json", "w"), indent=1)
    return dist, Rd


def main(out_dir, active_dir, delisted_dir, addendum_dir, warmup_dir=None):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    D = compute(load_all(active_dir, delisted_dir, addendum_dir, warmup_dir))
    dist, Rd = tables(D, out)
    print(json.dumps(dist, indent=1))
    return D, Rd


if __name__ == "__main__":
    main(*sys.argv[1:6])
