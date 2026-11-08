"""Market Intelligence on DEVELOPMENT ONLY (Protocol v1.2 FIXED sha256 18d5ddcf..d969; plan v0.3.1).
Descriptive and point-in-time. No forward quantity, label, entry, exit or P&L is computed.

python3 -I lab/mi.py <out_dir>

Inputs: rule-B hourly files (Active v0.9, Delisted v0.7.1, Jan-2024 addendum) and the fixed universe files (P1/S50k/S250k).
Point-in-time convention (T5/H5): a value for UTC day d is known at d 00:00 and uses only candles CLOSED by d 00:00
(hour start + 1 h <= d) and the eligibility of day d (itself computed from days d-30..d-1).
Fixed definitions (written before any output was computed):
  close_asof(s, d)  close of the last traded hour of UTC day d-1; missing if the series had no traded hour on d-1
                    (no carry-forward of stale prices)
  r_k(s, d)         close_asof(d) / close_asof(d-k) - 1, k in {1, 7, 30}
  hourly log return log(close_h) - log(previous traded close of the same series)
  vol_w(s, d)       std of the hourly log returns of hours inside days d-w .. d-1; needs >= 50% of the 24*w hours
  corr30(s, d)      Pearson correlation of r_1 over days d-29 .. d (each r_1 known at its day) with BTC r_1 /
                    with the median-coin r_1 of that day; needs >= 20 pairs
  aggregates        over the series ELIGIBLE on day d in the scenario; missing if fewer than 20 series contribute (R6e)
Regimes: lab/mi_regimes.py (R1-R6).
"""
import sys, json, gzip, pathlib, datetime as dt
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SegmentGuard, RESEARCH_START, SEGMENTS

LAB = pathlib.Path(__file__).resolve().parents[1]
DEV_START, DEV_END = [pd.Timestamp(x) for x in SEGMENTS["development"][:2]]
SRC = {"active": LAB / "out/active_dataset/final_42445808350_retry_42448392394/hourly",
       "delisted": LAB / "out/delisted_dataset/20261107T192715Z_rebuild/hourly",
       "delisted_jan2024": LAB / "out/delisted_dataset/20261108T041031Z_jan2024_addendum/hourly"}
UNIV = LAB / "out/research_protocol/v1.2/universe"
SCEN = {"P1": "eligibility_daily_P1.csv.gz", "S50k": "eligibility_daily_S50k.csv.gz", "S250k": "eligibility_daily_S250k.csv.gz"}
MIN_N = 20
BTC = "BTC-USDT"
GUARD = SegmentGuard("development")


def load_eligibility():
    E = {}
    for k, f in SCEN.items():
        d = pd.read_csv(UNIV / f, usecols=["series", "group", "day", "eligible"])
        d["day"] = pd.to_datetime(d["day"]).dt.tz_localize("UTC")
        d = d[(d["day"] >= DEV_START) & (d["day"] < DEV_END)]              # Development days only (H6)
        E[k] = d.pivot(index="day", columns="series", values="eligible").fillna(False).astype(bool)
    groups = pd.read_csv(UNIV / SCEN["P1"], usecols=["series", "group"]).drop_duplicates().set_index("series")["group"]
    return E, groups


def assert_dev_only(H):
    """H6: refuse any candle that does not close inside [RESEARCH_START, DEV_END)."""
    from lab.segment_loader import GuardError
    if len(H.index) and (H.index.min() < pd.Timestamp(RESEARCH_START) or H.index.max() + pd.Timedelta(hours=1) > DEV_END):
        raise GuardError(f"MI input outside Development: {H.index.min()} .. {H.index.max()}")
    return True


def load_hourly(groups):
    """Hourly closes for every series, only candles that CLOSE before the end of Development (H6).
    The loader refuses anything outside [RESEARCH_START, DEV_END)."""
    cols = {}
    for s, g in groups.items():
        f = SRC[g] / f"{s.split('#')[0]}.csv.gz"
        x = pd.read_csv(f, usecols=["ts_utc_ms", "close"], dtype={"ts_utc_ms": "int64", "close": "float64"})
        t = pd.to_datetime(x["ts_utc_ms"], unit="ms", utc=True)
        keep = (t >= pd.Timestamp(RESEARCH_START)) & (t + pd.Timedelta(hours=1) <= DEV_END)
        x = pd.Series(x.loc[keep, "close"].values, index=t[keep])
        if len(x):
            assert x.index.min() >= pd.Timestamp(RESEARCH_START) and x.index.max() + pd.Timedelta(hours=1) <= DEV_END
        cols[s] = x
    H = pd.DataFrame(cols).sort_index()
    assert_dev_only(H)
    return H


def daily_tables(H):
    days = pd.date_range(DEV_START, DEV_END - pd.Timedelta(days=1), freq="D")
    day_of = H.index.floor("D")
    last_close = H.groupby(day_of).last()                                     # last traded close of each UTC day
    last_close = last_close.reindex(days)
    close_asof = last_close.shift(1)                                          # known at d 00:00 = day d-1's last close
    R = {k: close_asof / close_asof.shift(k) - 1 for k in (1, 7, 30)}
    # hourly log returns between consecutive traded hours of the same series
    LH = np.log(H)
    lr = LH - LH.ffill().shift(1)
    lr = lr.where(H.notna())
    dsum = lr.groupby(day_of).sum(min_count=1).reindex(days)
    dsq = (lr ** 2).groupby(day_of).sum(min_count=1).reindex(days)
    dcnt = lr.notna().groupby(day_of).sum().reindex(days).fillna(0)
    V = {}
    for w in (1, 7, 30):
        s1 = dsum.fillna(0).rolling(w, min_periods=w).sum().shift(1)          # days d-w .. d-1
        s2 = dsq.fillna(0).rolling(w, min_periods=w).sum().shift(1)
        n = dcnt.rolling(w, min_periods=w).sum().shift(1)
        var = (s2 - s1 ** 2 / n) / (n - 1)
        V[w] = np.sqrt(var.clip(lower=0)).where(n >= 0.5 * 24 * w)
    return days, close_asof, R, V


def market(E, R, V, groups, exclude_later_delisted=False):
    days = E.index
    out = pd.DataFrame(index=days)
    elig = E.copy()
    if exclude_later_delisted:
        later = [s for s in elig.columns if groups.get(s) != "active"]
        elig[later] = False
    out["n_eligible"] = elig.sum(axis=1)
    cols = elig.columns

    def agg(T, fn, name):
        T = T.reindex(index=days, columns=cols)
        M = T.where(elig)
        n = M.notna().sum(axis=1)
        out[name] = fn(M).where(n >= MIN_N)
        out[name + "_n"] = n

    for k in (1, 7, 30):
        Rk = R[k]
        agg(Rk, lambda M: (M > 0).sum(axis=1) / M.notna().sum(axis=1), f"breadth_{k}")
        agg(Rk, lambda M: M.median(axis=1), f"median_ret_{k}")
        agg(Rk, lambda M: M.quantile(0.75, axis=1) - M.quantile(0.25, axis=1), f"dispersion_{k}")
        alt = Rk.reindex(index=days, columns=cols).where(elig).drop(columns=[BTC], errors="ignore")
        btc = Rk.reindex(index=days)[BTC] if BTC in Rk.columns else np.nan
        out[f"btc_minus_median_alt_{k}"] = (btc - alt.median(axis=1)).where(alt.notna().sum(axis=1) >= MIN_N)
    for w in (1, 7, 30):
        agg(V[w], lambda M: M.median(axis=1), f"mkt_vol_{w}")
        out[f"btc_vol_{w}"] = V[w].reindex(index=days)[BTC]
    # M3 universe dynamics
    prev = elig.shift(1).fillna(False).astype(bool)
    out["entries"] = (elig & ~prev).sum(axis=1)
    out["exits"] = (~elig & prev).sum(axis=1)
    out.iloc[0, out.columns.get_loc("entries")] = np.nan
    out.iloc[0, out.columns.get_loc("exits")] = np.nan
    out["turnover"] = (out["entries"] + out["exits"]) / out["n_eligible"]
    # M4 correlations over r_1 of days d-29..d
    r1 = R[1].reindex(index=days)
    idx = r1.where(elig).median(axis=1)
    cb = r1.rolling(30, min_periods=20).corr(r1[BTC])
    ci = r1.rolling(30, min_periods=20).corr(idx)
    for T, name in ((cb, "median_corr_btc_30"), (ci, "median_corr_index_30")):
        M = T.drop(columns=[BTC], errors="ignore").where(elig.drop(columns=[BTC], errors="ignore"))
        n = M.notna().sum(axis=1)
        out[name] = M.median(axis=1).where(n >= MIN_N)
        out[name + "_n"] = n
    # M2 volatility band of market vol (expanding, strictly prior Development days, >= 60 prior values)
    for w in (7, 30):
        x = out[f"mkt_vol_{w}"]
        pr = pd.Series(np.nan, index=days)
        vals = x.values
        for i in range(len(vals)):
            hist = vals[:i]
            hist = hist[~np.isnan(hist)]
            if len(hist) >= 60 and not np.isnan(vals[i]):
                pr.iloc[i] = (hist < vals[i]).mean()
        out[f"mkt_vol_{w}_pct_prior"] = pr
        out[f"mkt_vol_{w}_band"] = np.where(pr.isna(), "INSUFFICIENT_HISTORY", np.where(pr < 1 / 3, "LOW", np.where(pr > 2 / 3, "HIGH", "MID")))
    return out


def guard_days(H, days):
    """Segment guard (H5/H6) for every Development day: the latest candle any value of day d can use starts at
    d - 1 h at most and the earliest at RESEARCH_START. Raises on any violation."""
    starts = H.index
    for d in days:
        used = starts[starts + pd.Timedelta(hours=1) <= d]
        if len(used):
            GUARD.check_research_statistic(d.to_pydatetime(), [used.min().to_pydatetime(), used.max().to_pydatetime()])
        else:
            GUARD.check_research_statistic(d.to_pydatetime(), [])
    return len(days)


def compute_all(H, E, groups):
    assert_dev_only(H)
    days, close_asof, R, V = daily_tables(H)
    guard_days(H, days)
    res = {}
    for k in SCEN:
        e = E[k].reindex(index=days, columns=H.columns).fillna(False).astype(bool)
        res[k] = market(e, R, V, groups)
        res[k + "_survivors_only"] = market(e, R, V, groups, exclude_later_delisted=True)
    return res


def full_pipeline(H, E, groups):
    from lab.mi_regimes import regimes
    res = compute_all(H, E, groups)
    reg = {k: regimes(res[k]) for k in SCEN}               # R6f: one model per scenario, P1 primary
    return res, reg


def main(out_dir):
    from lab.mi_regimes import models_json
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    E, groups = load_eligibility()
    H = load_hourly(groups)
    res, reg = full_pipeline(H, E, groups)
    for k, df in res.items():
        df.assign(day=df.index.strftime("%Y-%m-%d")).to_csv(out / f"mi_daily_{k}.csv", index=False)
    summ = {}
    for k, (L, models, stab, summary, anchor) in reg.items():
        L.assign(day=L.index.strftime("%Y-%m-%d")).to_csv(out / f"regimes_asof_{k}.csv", index=False)
        json.dump(models_json(models, anchor), open(out / f"regime_models_{k}.json", "w"), indent=1)
        stab.to_csv(out / f"regime_stability_{k}.csv", index=False)
        summ[k] = summary
    json.dump(summ, open(out / "regime_summary.json", "w"), indent=1, default=str)
    meta = {"segment": "development", "days": [str(DEV_START.date()), str((DEV_END - pd.Timedelta(days=1)).date())],
            "series": int(H.shape[1]), "hourly_rows": int(H.notna().sum().sum()),
            "max_candle_start_used": str(H.index.max()), "min_candle_start_used": str(H.index.min())}
    json.dump(meta, open(out / "mi_meta.json", "w"), indent=1)
    print(json.dumps(meta))
    return res


if __name__ == "__main__":
    main(sys.argv[1])
