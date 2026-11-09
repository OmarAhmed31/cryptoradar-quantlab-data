"""FD-2 forward association (plan v0.1.1 §4 + FD-2 Decision Record v2: D4, D5, D6). Development only.
No strategy, trade, P&L, cost, quantile or portfolio return is computed.

python3 -I lab/fd2.py <out_dir>

Outcome  fwd_h(s,d) = close_asof(s, d+h) / close_asof(s, d) - 1, h in {1, 7, 30} days, t = d 00:00 UTC.
         Entry days d with t < 2025-08-02 00:00 (H2), so d+h <= 2025-08-31 < end of Development; eligible on d.
         close_asof(d) = last traded close of day d-1 (known at t, as in FD-1); the exit uses the last traded hour
         of day d+h-1, a candle inside [t, t+h] (T5). No carry-forward: no trade on day d+h-1 -> MISSING (counted).
         Delisting (D2) with the cut inside (t, t+h): U9b forced exit at last_trade_price (forced_exit_dev.csv);
         PRICED only (U9c); UNPRICEABLE -> excluded and counted. Delisted series are never dropped.
IC       daily Spearman rank IC across series eligible on d with feature and outcome (>= 20 series).
Tests    mean IC; Newey-West t (Bartlett, lag h-1 days) on the daily IC series of days with an IC; two-sided p from
         the normal distribution. Circular block bootstrap (block max(7, h) days, 2000 resamples, seed 20260108)
         -> 95% CI of the mean IC.
Family   64 confirmatory = 22 x {1,7,30} minus F01 x 1 and F02 x 7 (D4) -> EXPLORATORY_SEEN_IN_FD1, outside BH/BY.
         BH (rule) and BY (sensitivity), q = 0.10, same 64 p-values of P1 (D6).
Candidate (plan §4, fixed): BH-significant AND the mean-IC sign of all 3 sub-periods equals the overall sign AND the
         overall sign in S50k and S250k equals P1's. BH-candidate that fails BY -> label BH_ONLY — FAILS_BY_SENSITIVITY.
"""
import sys, json, math, pathlib, warnings, datetime as dt
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import fd1 as FD
from lab.segment_loader import SegmentGuard, GuardError
warnings.filterwarnings("ignore", category=RuntimeWarning)

LAB = FF.LAB
PACK2 = LAB / "out/market_intelligence/dev_pack_v2"
HS = (1, 7, 30)
ENTRY_END = pd.Timestamp("2025-08-02", tz="UTC")          # H2: t < 2025-08-02 00:00
Q = 0.10
SEED, NBOOT = 20260108, 2000
MIN_N = 20
SUBP = [("2024-01-01", "2024-07-01"), ("2024-07-01", "2025-01-01"), ("2025-01-01", "2025-08-02")]
EXPLORATORY = {("F01", 1), ("F02", 7)}                     # D4
GUARD = SegmentGuard("development")
ENTRY_IDX = np.where(FF.DAYS < ENTRY_END)[0]               # 579 entry days


def family():
    conf = [(f, h) for h in HS for f in FF.NAMES if (f, h) not in EXPLORATORY]
    assert len(conf) == 64
    return conf


def load_forced(pack2=PACK2):
    fe = pd.read_csv(pathlib.Path(pack2) / "forced_exit_dev.csv")
    fe["cut"] = pd.to_datetime(fe["cut_utc"], utc=True)
    fe["last_trade"] = pd.to_datetime(fe["last_traded_minute_utc"], utc=True)
    if (fe["cut"] >= FF.DEV_END).any():
        raise GuardError("forced exit with a cut outside Development")
    return fe.set_index("series")


def last_close(Hh):
    C = Hh["close"]
    return pd.DataFrame(C.groupby(C.index.floor("D")).last().reindex(FF.DAYS).values, index=FF.DAYS, columns=C.columns)


def outcomes(Hh, fe):
    """returns {h: (values days x series, type days x series)} for entry days only (other days NaN / '')."""
    lc = last_close(Hh).values
    S = list(Hh["close"].columns); nS = len(S)
    out = {}
    for h in HS:
        V = np.full((FF.ND, nS), np.nan); T = np.full((FF.ND, nS), "", dtype=object)
        for i in ENTRY_IDX:
            d = FF.DAYS[i]
            GUARD.check_outcome(d.to_pydatetime(), dt.timedelta(days=h))       # H2 + H_max + segment end
            entry = lc[i - 1] if i >= 1 else np.full(nS, np.nan)
            ex = lc[i + h - 1]
            V[i] = ex / entry - 1
            T[i] = np.where(np.isnan(entry), "NO_ENTRY_PRICE", np.where(np.isnan(ex), "MISSING_EXIT", "NORMAL"))
        for s, r in fe.iterrows():
            if s not in S:
                continue
            j = S.index(s); c = r["cut"]
            for i in ENTRY_IDX:
                d = FF.DAYS[i]
                if c <= d:
                    V[i, j] = np.nan; T[i, j] = "CUT_BEFORE_ENTRY"
                elif c < d + pd.Timedelta(days=h):                              # position open at the cut
                    entry = lc[i - 1, j] if i >= 1 else np.nan
                    if r["status"] == "PRICED" and r["minutes_last_trade_to_cut"] <= 60 and not np.isnan(entry):
                        GUARD.check_outcome_candles(d.to_pydatetime(), dt.timedelta(days=h), [r["last_trade"].to_pydatetime()],
                                                    candle_len=dt.timedelta(minutes=1))
                        V[i, j] = r["last_trade_price"] / entry - 1; T[i, j] = "DELISTING_FORCED_EXIT"
                    else:
                        V[i, j] = np.nan; T[i, j] = "UNPRICEABLE_FORCED_EXIT" if not np.isnan(entry) else "NO_ENTRY_PRICE"
        out[h] = (pd.DataFrame(V, index=FF.DAYS, columns=S), pd.DataFrame(T, index=FF.DAYS, columns=S))
    return out


def guard_exit_candles(Hh):
    """T5 for normal outcomes: the exit candle (last traded hour of day d+h-1) lies inside [t, t+h]."""
    for h in HS:
        for i in ENTRY_IDX:
            d = FF.DAYS[i]
            lo = d + pd.Timedelta(days=h - 1); hi = d + pd.Timedelta(days=h) - pd.Timedelta(hours=1)
            GUARD.check_outcome_candles(d.to_pydatetime(), dt.timedelta(days=h), [lo.to_pydatetime(), hi.to_pydatetime()])
    return True


def daily_ic(X, Y, E):
    """X feature, Y outcome (days x series), E eligibility; IC per entry day (NaN if < 20 series)."""
    ic = np.full(FF.ND, np.nan); n = np.zeros(FF.ND, int)
    x, y, e = X.values, Y.values, E.values
    for i in ENTRY_IDX:
        m = e[i] & ~np.isnan(x[i]) & ~np.isnan(y[i])
        n[i] = m.sum()
        if n[i] < MIN_N:
            continue
        ra = pd.Series(x[i][m]).rank().values; rb = pd.Series(y[i][m]).rank().values
        if ra.std() == 0 or rb.std() == 0:
            continue
        ic[i] = np.corrcoef(ra, rb)[0, 1]
    return pd.Series(ic, index=FF.DAYS), pd.Series(n, index=FF.DAYS)


def newey_west_t(x, lag):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; T = len(x)
    if T < 2:
        return np.nan, np.nan
    m = x.mean(); u = x - m
    v = (u @ u) / T
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (u[l:] @ u[:-l]) / T
    se = math.sqrt(v / T) if v > 0 else np.nan
    t = m / se if se and se > 0 else np.nan
    p = math.erfc(abs(t) / math.sqrt(2)) if not np.isnan(t) else np.nan
    return t, p


def boot_ci(x, block, rng):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(NBOOT, nb))
    idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(NBOOT, -1)[:, :n]
    mb = x[idx].mean(1)
    return float(np.quantile(mb, .025)), float(np.quantile(mb, .975))


def bh(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p)
    adj = np.empty(m); run = 1.0
    for r in range(m - 1, -1, -1):
        run = min(run, p[o[r]] * m / (r + 1)); adj[o[r]] = run
    return adj


def by(p):
    m = len(p); c = sum(1 / i for i in range(1, m + 1))
    return np.minimum(1.0, bh(p) * c)


def ic_table(F, OUT, E, scen):
    rows, daily = [], {}
    for h in HS:
        Y = OUT[h][0]
        for f in FF.NAMES:
            ic, n = daily_ic(F[f], Y, E)
            daily[(f, h)] = (ic, n)
            v = ic.iloc[ENTRY_IDX].values
            t, p = newey_west_t(v, h - 1)
            lo, hi = boot_ci(v, max(7, h), np.random.default_rng(SEED))
            r = {"scenario": scen, "feature": f, "name": FF.NAMES[f], "h_days": h,
                 "family": "EXPLORATORY_SEEN_IN_FD1" if (f, h) in EXPLORATORY else "CONFIRMATORY",
                 "days_with_ic": int((~np.isnan(v)).sum()), "mean_ic": float(np.nanmean(v)), "median_ic": float(np.nanmedian(v)),
                 "nw_lag": h - 1, "nw_t": t, "p_two_sided": p, "boot_ci95_low": lo, "boot_ci95_high": hi,
                 "median_series_per_day": float(np.median(n.iloc[ENTRY_IDX][n.iloc[ENTRY_IDX] > 0]))}
            for k, (a, b) in enumerate(SUBP, 1):
                w = (ic.index >= pd.Timestamp(a, tz="UTC")) & (ic.index < pd.Timestamp(b, tz="UTC"))
                r[f"sub{k}_mean_ic"] = float(np.nanmean(ic[w].values)); r[f"sub{k}_days"] = int(ic[w].notna().sum())
            rows.append(r)
    return pd.DataFrame(rows), daily


def classify(T):
    """T: ic tables of all scenarios. Adds BH/BY (P1, confirmatory 64) and the fixed candidate rule."""
    P = T[T.scenario == "P1"].copy()
    conf = P.family == "CONFIRMATORY"
    assert conf.sum() == 64
    P["p_bh"] = np.nan; P["p_by"] = np.nan
    P.loc[conf, "p_bh"] = bh(P.loc[conf, "p_two_sided"].values)
    P.loc[conf, "p_by"] = by(P.loc[conf, "p_two_sided"].values)
    P["bh_sig"] = conf & (P["p_bh"] <= Q); P["by_sig"] = conf & (P["p_by"] <= Q)
    sgn = np.sign(P["mean_ic"])
    P["subperiods_same_sign"] = sum((np.sign(P[f"sub{k}_mean_ic"]) == sgn).astype(int) for k in (1, 2, 3))
    for sc in ("S50k", "S250k"):
        o = T[T.scenario == sc].set_index(["feature", "h_days"])["mean_ic"]
        P[f"sign_same_{sc}"] = [np.sign(o.loc[(f, h)]) == s for f, h, s in zip(P.feature, P.h_days, sgn)]
    P["candidate"] = P.bh_sig & (P.subperiods_same_sign == 3) & P.sign_same_S50k & P.sign_same_S250k & (sgn != 0)
    lab = []
    for _, r in P.iterrows():
        if r.family != "CONFIRMATORY":
            lab.append("EXPLORATORY_SEEN_IN_FD1")
        elif r.candidate:
            lab.append("CANDIDATE" if r.by_sig else "CANDIDATE — BH_ONLY — FAILS_BY_SENSITIVITY")
        elif r.bh_sig:
            lab.append("BH_SIGNIFICANT_NOT_STABLE")
        else:
            lab.append("NOT_SIGNIFICANT")
    P["label"] = lab
    return P


def regime_ic(daily, lab):
    rows = []
    lab = lab[(lab.index >= FD.LABEL_START)]
    for (f, h), (ic, n) in daily.items():
        x = ic.reindex(lab.index)
        for s in FD.STATES:
            m = (lab == s).values & x.notna().values
            nd = int((lab == s).values[np.isin(lab.index, FF.DAYS[ENTRY_IDX])].sum())
            rows.append({"feature": f, "name": FF.NAMES[f], "h_days": h, "state": s, "entry_days_in_state": nd,
                         "days_with_ic": int(m.sum()), "mean_ic": float(x.values[m].mean()) if m.any() else np.nan,
                         "LOW_N": nd < FD.LOW_N_DAYS, "descriptive_only": True})
    return pd.DataFrame(rows)


def outcome_counts(OUT, M):
    rows = []
    for sc, E in M.items():
        for h in HS:
            V, T = OUT[h]
            t = T.values[ENTRY_IDX][E.values[ENTRY_IDX]]
            vc = pd.Series(t).value_counts().to_dict()
            rows.append({"mask": sc, "h_days": h, "eligible_entries": int(len(t)), **{k: int(v) for k, v in vc.items()}})
    return pd.DataFrame(rows).fillna(0)


def purge_count(OUT):
    """H3: observations whose outcome interval leaves Development (expected 0)."""
    bad = 0
    for h in HS:
        V = OUT[h][0]
        has = V.notna().any(axis=1)
        bad += int(sum(1 for d in V.index[has] if d + pd.Timedelta(days=h) > FF.DEV_END or d >= ENTRY_END))
    return bad


def run(Hh, U, groups, fe):
    F = FF.features(Hh, U["P1"])
    M = FD.masks(U, groups)
    OUT = outcomes(Hh, fe)
    guard_exit_candles(Hh)
    tabs, dailies = [], {}
    for sc in FF.SCEN:
        t, d = ic_table(F, OUT, M[sc], sc); tabs.append(t); dailies[sc] = d
    T = pd.concat(tabs, ignore_index=True)
    C = classify(T)
    R = regime_ic(dailies["P1"], FD.load_regimes("P1"))
    return F, M, OUT, T, C, R, dailies


def main(out_dir):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    FF.catalogue()
    Hh, U, groups = FF.load_pack()
    fe = load_forced()
    F, M, OUT, T, C, R, dailies = run(Hh, U, groups, fe)
    rows = []
    for sc, d in dailies.items():
        for (f, h), (ic, n) in d.items():
            x = pd.DataFrame({"day": ic.index[ENTRY_IDX].strftime("%Y-%m-%d"), "ic": ic.iloc[ENTRY_IDX].values,
                              "n_series": n.iloc[ENTRY_IDX].values})
            x["scenario"] = sc; x["feature"] = f; x["h_days"] = h; rows.append(x)
    pd.concat(rows)[["scenario", "feature", "h_days", "day", "ic", "n_series"]].to_csv(
        out / "fd2_ic_daily.csv.gz", index=False, float_format="%.12g", compression={"method": "gzip", "mtime": 0})
    T.to_csv(out / "fd2_ic_summary_all_scenarios.csv", index=False)
    C.to_csv(out / "fd2_ic_summary_P1.csv", index=False)
    C[[c for c in C.columns if c.startswith("sub") or c in ("feature", "name", "h_days", "mean_ic", "subperiods_same_sign")]].to_csv(out / "fd2_stability.csv", index=False)
    C[C.candidate].to_csv(out / "fd2_candidates.csv", index=False)
    R.to_csv(out / "fd2_regime_ic_descriptive.csv", index=False)
    oc = outcome_counts(OUT, {"P1": M["P1"], "S50k": M["S50k"], "S250k": M["S250k"]})
    oc.to_csv(out / "fd2_outcome_counts.csv", index=False)
    meta = {"segment": "development", "entry_days": [str(FF.DAYS[ENTRY_IDX[0]].date()), str(FF.DAYS[ENTRY_IDX[-1]].date())],
            "n_entry_days": int(len(ENTRY_IDX)), "horizons": list(HS), "confirmatory_tests": 64,
            "exploratory_cells": sorted(f"{f}x{h}" for f, h in EXPLORATORY), "q": Q, "purge_count_H3": purge_count(OUT),
            "candidates": int(C.candidate.sum()), "bh_significant": int(C.bh_sig.sum()), "by_significant": int(C.by_sig.sum()),
            "forced_exit_pack_sha256": __import__("hashlib").sha256((PACK2 / "forced_exit_dev.csv").read_bytes()).hexdigest()}
    json.dump(meta, open(out / "fd2_meta.json", "w"), indent=1)
    print(json.dumps(meta))
    return meta


if __name__ == "__main__":
    main(sys.argv[1])
