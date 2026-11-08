"""Feature Discovery FD-1: the 22 features of plan v0.1.1 (sha256 1126d551..683a), Development only.
Reads ONLY the Development pack (out/market_intelligence/dev_pack_v1). Point-in-time (plan §1): a value for day d is
known at d 00:00 and uses only candles that start in [d - L days, d) (so they close at or before d), never before
2024-01-01 00:00. A window that would need data before 2024-01-01 is NOT shortened: the value is missing.

features(P) -> dict F01..F22 of DataFrames (index = UTC day, columns = series), raw values, all series (not yet masked).
Eligibility masks are applied by the FD-1 statistics (lab/fd1.py), per scenario.
"""
import sys, json, gzip, pathlib, warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SegmentGuard, RESEARCH_START, SEGMENTS, GuardError

LAB = pathlib.Path(__file__).resolve().parents[1]
PACK = LAB / "out/market_intelligence/dev_pack_v1"
CATALOGUE = LAB / "out/feature_discovery/feature_catalogue.json"
DEV_START, DEV_END = [pd.Timestamp(x) for x in SEGMENTS["development"][:2]]
DAYS = pd.date_range(DEV_START, DEV_END - pd.Timedelta(days=1), freq="D")
ND = len(DAYS)
SCEN = {"P1": "eligibility_daily_P1.csv.gz", "S50k": "eligibility_daily_S50k.csv.gz", "S250k": "eligibility_daily_S250k.csv.gz"}
BTC = "BTC-USDT"
GUARD = SegmentGuard("development")
NAMES = {"F01": "ret_1", "F02": "ret_7", "F03": "ret_30", "F04": "ret_30_skip7", "F05": "btc_beta_adjusted_ret_30",
         "F06": "vol_7", "F07": "vol_30", "F08": "vol_ratio_7_30", "F09": "downside_vol_30", "F10": "skew_30",
         "F11": "max_hr_ret_7", "F12": "beta_btc_30", "F13": "corr_btc_30", "F14": "idio_vol_30", "F15": "log_dv30_med",
         "F16": "thr30", "F17": "dv_ratio_7_30", "F18": "amihud_30", "F19": "traded_min_share_7", "F20": "dist_high_30",
         "F21": "dist_low_30", "F22": "range_7"}
# lookback in days: the earliest candle any value of day d may use starts at d - LOOKBACK days (guard + FA2)
LOOKBACK = {"F01": 2, "F02": 8, "F03": 31, "F04": 38, "F05": 31, "F06": 7, "F07": 30, "F08": 30, "F09": 30, "F10": 30,
            "F11": 7, "F12": 31, "F13": 31, "F14": 31, "F15": 30, "F16": 30, "F17": 30, "F18": 31, "F19": 7, "F20": 30,
            "F21": 30, "F22": 7}


def load_pack(pack=PACK):
    pack = pathlib.Path(pack)
    groups = pd.read_csv(pack / "groups.csv").set_index("series")["group"]
    grid = pd.date_range(DEV_START, DEV_END - pd.Timedelta(hours=1), freq="h")
    cols = {k: {} for k in ("open", "high", "low", "close", "vol_quote", "traded_minutes")}
    for s in groups.index:
        x = pd.read_csv(pack / "hourly" / f"{s}.csv.gz", usecols=["ts_utc_ms"] + list(cols),
                        dtype={"ts_utc_ms": "int64"})
        t = pd.to_datetime(x["ts_utc_ms"], unit="ms", utc=True)
        keep = (t >= pd.Timestamp(RESEARCH_START)) & (t + pd.Timedelta(hours=1) <= DEV_END)
        for k in cols:
            cols[k][s] = pd.Series(x.loc[keep, k].astype("float64").values, index=t[keep])
    Hh = {k: pd.DataFrame(v).reindex(grid) for k, v in cols.items()}
    U = {}
    for k, f in SCEN.items():
        d = pd.read_csv(pack / "universe" / f, usecols=["series", "day", "assessable", "THR30", "DV30_med", "eligible"])
        d["day"] = pd.to_datetime(d["day"]).dt.tz_localize("UTC")
        d = d[(d["day"] >= DEV_START) & (d["day"] < DEV_END)]
        U[k] = {c: d.pivot(index="day", columns="series", values=c).reindex(index=DAYS, columns=groups.index)
                for c in ("assessable", "THR30", "DV30_med", "eligible")}
        U[k]["eligible"] = U[k]["eligible"].fillna(False).astype(bool)
        U[k]["assessable"] = U[k]["assessable"].fillna(False).astype(bool)
    return Hh, U, groups


def assert_dev_only(Hh):
    for k, df in Hh.items():
        v = df.index[df.notna().any(axis=1)]
        if len(v) and (v.min() < pd.Timestamp(RESEARCH_START) or v.max() + pd.Timedelta(hours=1) > DEV_END):
            raise GuardError(f"FD input {k} outside Development: {v.min()} .. {v.max()}")
    return True


def features(Hh, U):
    """All 22 features as raw values (days x series). U: universe of P1 (THR30 / DV30_med are scenario-independent)."""
    assert_dev_only(Hh)
    C, Hi, Lo, VQ, TM = (Hh[k] for k in ("close", "high", "low", "vol_quote", "traded_minutes"))
    S = list(C.columns); nS = len(S)
    shp = (ND, 24, nS)
    c3 = C.values.reshape(shp)
    LC = pd.DataFrame(C.groupby(C.index.floor("D")).last().reindex(DAYS).values, index=DAYS, columns=S)  # last traded close
    lc = LC.values
    LH = np.log(C)
    lr = (LH - LH.ffill().shift(1)).where(C.notna()).values.reshape(shp)            # hourly log return (MI definition)
    hi3, lo3 = Hi.values.reshape(shp), Lo.values.reshape(shp)
    vq3, tm3 = VQ.values.reshape(shp), TM.values.reshape(shp)
    traded_day = (~np.isnan(c3)).any(1)                                              # day with >= 1 traded hour
    dq = np.where(traded_day, np.nansum(vq3, 1), np.nan)                             # daily quote volume
    with np.errstate(all="ignore"):
        dh, dl = np.nanmax(np.where(np.isnan(hi3), -np.inf, hi3), 1), np.nanmin(np.where(np.isnan(lo3), np.inf, lo3), 1)
    dh = np.where(traded_day, dh, np.nan); dl = np.where(traded_day, dl, np.nan)
    dlr = np.full_like(lc, np.nan); dlr[1:] = np.log(lc[1:] / lc[:-1])              # daily log return of day j
    rng_day = (dh - dl) / lc

    def nan(): return np.full((ND, nS), np.nan)
    F = {k: nan() for k in NAMES}
    # returns from close_asof(d) = lc[i-1]
    for i in range(ND):
        ca = lc[i - 1] if i >= 1 else np.full(nS, np.nan)
        for f, k in (("F01", 1), ("F02", 7), ("F03", 30)):
            if i - k - 1 >= 0:
                F[f][i] = ca / lc[i - k - 1] - 1
        if i - 38 >= 0:
            F["F04"][i] = lc[i - 8] / lc[i - 38] - 1
    with np.errstate(all="ignore"):
        for i in range(ND):
            ca = lc[i - 1] if i >= 1 else np.full(nS, np.nan)
            for w, fv, fx in ((7, "F06", "F11"), (30, "F07", None)):
                if i - w < 0:
                    continue
                L = lr[i - w:i].reshape(-1, nS); n = (~np.isnan(L)).sum(0); ok = n >= 0.5 * 24 * w
                F[fv][i] = np.where(ok, np.nanstd(L, 0, ddof=1), np.nan)
                if fx:
                    F[fx][i] = np.where(ok, np.nanmax(np.where(np.isnan(L), -np.inf, L), 0), np.nan)
                if w == 30:
                    F["F09"][i] = np.where(ok, np.sqrt(np.nanmean(np.minimum(L, 0) ** 2, 0)), np.nan)
                    m = np.nanmean(L, 0); cc = L - m
                    m2 = np.nanmean(cc ** 2, 0); m3 = np.nanmean(cc ** 3, 0)
                    g1 = m3 / m2 ** 1.5
                    G1 = g1 * np.sqrt(n * (n - 1)) / (n - 2)
                    F["F10"][i] = np.where(ok & (m2 > 0), G1, np.nan)
                    nc = (~np.isnan(c3[i - 30:i])).sum((0, 1)); okc = nc >= 360
                    hmax = np.nanmax(np.where(np.isnan(hi3[i - 30:i]), -np.inf, hi3[i - 30:i]), (0, 1))
                    lmin = np.nanmin(np.where(np.isnan(lo3[i - 30:i]), np.inf, lo3[i - 30:i]), (0, 1))
                    F["F20"][i] = np.where(okc, ca / hmax - 1, np.nan)
                    F["F21"][i] = np.where(okc, ca / lmin - 1, np.nan)
            if i - 7 >= 0:
                F["F19"][i] = np.nansum(tm3[i - 7:i], (0, 1)) / (7 * 1440)
                q7 = dq[i - 7:i]; n7 = (~np.isnan(q7)).sum(0)
                r7 = rng_day[i - 7:i]; nr = (~np.isnan(r7)).sum(0)
                F["F22"][i] = np.where(nr >= 4, np.nanmean(r7, 0), np.nan)
            if i - 30 >= 0:
                q30 = dq[i - 30:i]; n30 = (~np.isnan(q30)).sum(0)
                F["F17"][i] = np.where((n7 >= 4) & (n30 >= 15), np.nanmedian(q7, 0) / np.nanmedian(q30, 0), np.nan)
                a = np.abs(dlr[i - 30:i]) / dq[i - 30:i]; na = (~np.isnan(a)).sum(0)
                F["F18"][i] = np.where(na >= 15, np.nanmedian(a, 0), np.nan)
    F["F08"] = F["F06"] / F["F07"]
    # market relation: daily r_1 over days d-29..d (each r_1 known at its day), >= 20 pairs
    r1 = F["F01"]; b = S.index(BTC)
    with np.errstate(all="ignore"):
        for i in range(ND):
            y = r1[max(0, i - 29):i + 1]; x = y[:, [b]]
            ok = ~np.isnan(y) & ~np.isnan(x); n = ok.sum(0)
            X = np.where(ok, x, np.nan); Y = np.where(ok, y, np.nan)
            mx, my = np.nanmean(X, 0), np.nanmean(Y, 0)
            sxy = np.nansum((X - mx) * (Y - my), 0); sxx = np.nansum((X - mx) ** 2, 0); syy = np.nansum((Y - my) ** 2, 0)
            beta = sxy / sxx; good = (n >= 20) & (sxx > 0)
            F["F12"][i] = np.where(good, beta, np.nan)
            F["F13"][i] = np.where(good & (syy > 0), sxy / np.sqrt(sxx * syy), np.nan)
            res = Y - (my + beta * (X - mx))
            F["F14"][i] = np.where(good, np.sqrt(np.nansum(res ** 2, 0) / (n - 2)), np.nan)
    for f in ("F12", "F13", "F14"):
        F[f][:, b] = np.nan                                                          # undefined for BTC itself
    F["F05"] = F["F03"] - F["F12"] * F["F03"][:, [b]]
    with np.errstate(all="ignore"):
        dv = U["DV30_med"].values.astype(float)
        F["F15"] = np.where(U["assessable"].values & (dv > 0), np.log(dv), np.nan)
    F["F16"] = np.where(U["assessable"].values, U["THR30"].values.astype(float), np.nan)
    out = {k: pd.DataFrame(v, index=DAYS, columns=S) for k, v in F.items()}
    guard(out)
    return out


# windows that must be COMPLETE inside the research period (index of the first day that may carry a value)
FIRST_INDEX = {"F01": 2, "F02": 8, "F03": 31, "F04": 38, "F05": 31, "F06": 7, "F07": 30, "F08": 30, "F09": 30, "F10": 30,
               "F11": 7, "F17": 30, "F18": 30, "F19": 7, "F20": 30, "F21": 30, "F22": 7}


def guard(F):
    """FA2: (a) the segment guard for every output day and every (day, feature) lookback, clipped at 2024-01-01;
    (b) a value whose fixed window is not complete inside the research period must be missing (never shortened).
    F12-F14 count PAIRS over days d-29..d (>= 20), as MI does; F15/F16 come from the universe row of day d."""
    for d in DAYS:
        GUARD.check_research_statistic(d.to_pydatetime(), [])
    for f, L in LOOKBACK.items():
        for d in DAYS:
            start = max(d - pd.Timedelta(days=L), pd.Timestamp(RESEARCH_START))
            last = d - pd.Timedelta(hours=1)
            GUARD.check_feature(d.to_pydatetime(), [start.to_pydatetime(), last.to_pydatetime()] if start <= last else [])
    for f, k in FIRST_INDEX.items():
        if F[f].iloc[:k].notna().any().any():
            raise GuardError(f"{f} has a value before its window is complete (first allowed day index {k})")
    return True


def catalogue():
    c = json.loads(CATALOGUE.read_text())
    assert [x["id"] for x in c["features"]] == list(NAMES), "catalogue order"
    for x in c["features"]:
        assert x["name"] == NAMES[x["id"]] and x["lookback_days"] == LOOKBACK[x["id"]], x["id"]
    return c
