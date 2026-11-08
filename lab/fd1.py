"""FD-1 (plan v0.1.1 §3, approved): Q1-Q7 on Development only. NO forward outcome is computed anywhere.

python3 -I lab/fd1.py <out_dir>

Inputs: the Development pack (lab/fd_features.py) + regimes_asof_<scenario>.csv of MI v0.11.2.
Raw vs ranks (plan §2): Q3 persistence and Q4 redundancy are rank-based (Spearman = Pearson of cross-sectional
percentile ranks); Q2 stability and Q6 regime relation use RAW values; Q1 counts values.
"""
import sys, json, pathlib, warnings
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
warnings.filterwarnings("ignore", category=RuntimeWarning)

LAB = FF.LAB
REG = LAB / "out/market_intelligence/dev_v0.11.2"
MIN_N = 20
THR = (0.70, 0.80, 0.90)
LOW_N_DAYS = 30
SEED, NBOOT, BLOCK = 20260108, 2000, 7
REF = "S2"
STATES = ("S1", "S2", "S3", "UNKNOWN")
LABEL_START = pd.Timestamp("2024-07-01", tz="UTC")
FEATS = list(FF.NAMES)


def masks(U, groups):
    M = {}
    for k in FF.SCEN:
        e = U[k]["eligible"]
        M[k] = e
        s = e.copy(); s[[c for c in s.columns if groups.get(c) != "active"]] = False
        M[k + "_survivors_only"] = s
    return M


def rank_pct(X):
    """cross-sectional percentile rank of each day (row) among non-missing values; ties -> average."""
    return X.rank(axis=1, pct=True)


def q1(F, E):
    rows = []
    month = E.index.strftime("%Y-%m")
    for f in FEATS:
        v = F[f].where(E).notna()
        n_e = E.groupby(month).sum().sum(axis=1); n_v = v.groupby(month).sum().sum(axis=1)
        dv = v.sum(axis=1)
        for m in n_e.index:
            rows.append({"feature": f, "name": FF.NAMES[f], "month": m, "eligible_series_days": int(n_e[m]),
                         "with_value": int(n_v[m]), "coverage": float(n_v[m] / n_e[m]) if n_e[m] else np.nan,
                         "days_lt20_series": int((dv[month == m] < MIN_N).sum())})
        rows.append({"feature": f, "name": FF.NAMES[f], "month": "ALL", "eligible_series_days": int(E.values.sum()),
                     "with_value": int(v.values.sum()), "coverage": float(v.values.sum() / E.values.sum()),
                     "days_lt20_series": int((dv < MIN_N).sum())})
    return pd.DataFrame(rows)


def q2(F, E):
    rows = []
    month = E.index.strftime("%Y-%m")
    for f in FEATS:
        X = F[f].where(E)
        for m in sorted(set(month)):
            x = X[month == m].values.ravel(); x = x[~np.isnan(x)]
            rows.append({"feature": f, "name": FF.NAMES[f], "month": m, "n": len(x),
                         "median": float(np.median(x)) if len(x) else np.nan,
                         "iqr": float(np.quantile(x, .75) - np.quantile(x, .25)) if len(x) else np.nan})
    return pd.DataFrame(rows)


def daily_spearman(a, b):
    ok = ~np.isnan(a) & ~np.isnan(b)
    if ok.sum() < MIN_N:
        return np.nan
    ra = pd.Series(a[ok]).rank().values; rb = pd.Series(b[ok]).rank().values
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def q3_pairs(k):
    """(i, i+k) day-index pairs; d+k must be a Development day (< 2025-09-01)."""
    return [(i, i + k) for i in range(FF.ND) if i + k < FF.ND]


def q3(F, E):
    rows, daily = [], []
    for f in FEATS:
        X = F[f].where(E).values
        for k in (1, 7):
            ps = q3_pairs(k)
            r = np.array([daily_spearman(X[i], X[j]) for i, j in ps])
            v = r[~np.isnan(r)]
            rows.append({"feature": f, "name": FF.NAMES[f], "k_days": k, "day_pairs": len(ps), "days_with_value": len(v),
                         "mean": float(v.mean()) if len(v) else np.nan, "median": float(np.median(v)) if len(v) else np.nan,
                         "q25": float(np.quantile(v, .25)) if len(v) else np.nan, "q75": float(np.quantile(v, .75)) if len(v) else np.nan,
                         "last_pair": f"{FF.DAYS[ps[-1][0]].date()}->{FF.DAYS[ps[-1][1]].date()}"})
            daily.append(pd.Series(r, index=[FF.DAYS[i] for i, _ in ps], name=(f, k)))
    return pd.DataFrame(rows), daily


def q4(F, E):
    n = len(FEATS)
    per_day = np.full((FF.ND, n, n), np.nan)
    for i in range(FF.ND):
        e = E.values[i]
        if e.sum() < MIN_N:
            continue
        D = pd.DataFrame({f: F[f].values[i][e] for f in FEATS})
        per_day[i] = D.corr(method="spearman", min_periods=MIN_N).values
    med = np.nanmedian(per_day, 0)
    M = pd.DataFrame(med, index=FEATS, columns=FEATS)
    clusters = {}
    for t in THR:
        adj = (np.abs(med) >= t); np.fill_diagonal(adj, True)
        seen, comps = set(), []
        for a in range(n):
            if a in seen:
                continue
            stack, comp = [a], []
            while stack:
                x = stack.pop()
                if x in seen:
                    continue
                seen.add(x); comp.append(x)
                stack += [y for y in range(n) if adj[x, y] and y not in seen]
            comps.append(sorted(FEATS[x] for x in comp))
        clusters[str(t)] = sorted(comps)
    return M, clusters, per_day


def q5(clusters, cov_all):
    cat = {x["id"]: x["window_parameters"] for x in FF.catalogue()["features"]}
    out = {}
    for t, comps in clusters.items():
        out[t] = [{"cluster": c, "representative": sorted(c, key=lambda f: (-cov_all[f], cat[f], f))[0]} for c in comps]
    return out


def daily_medians(F, E):
    return pd.DataFrame({f: F[f].where(E).median(axis=1).where(F[f].where(E).notna().sum(axis=1) >= MIN_N) for f in FEATS})


def boot_index(n, rng):
    nb = int(np.ceil(n / BLOCK))
    starts = rng.integers(0, n, size=(NBOOT, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]) % n
    return idx.reshape(NBOOT, -1)[:, :n]


def q6(F, E, lab):
    """raw daily cross-sectional medians grouped by regime_asof; circular 7-day block bootstrap over the FULL daily series
    (feature median and its own label resampled together); LOW_N states: descriptive only."""
    Dm = daily_medians(F, E)
    lab = lab[(lab.index >= LABEL_START) & (lab.index < FF.DEV_END)]
    Dm = Dm.loc[lab.index]
    L = np.array(lab.astype(str).tolist(), dtype=object); V = Dm.values.astype(float)
    idx = boot_index(len(L), np.random.default_rng(SEED))
    Lb = L[idx]
    rows = []
    for j, f in enumerate(FEATS):
        Vb = V[:, j][idx]
        base = {s: np.nanmean(np.where(L == s, V[:, j], np.nan)) for s in STATES}
        bm = {s: np.nanmean(np.where(Lb == s, Vb, np.nan), 1) for s in STATES}
        for s in STATES:
            n_lab = int((L == s).sum()); n_val = int(((L == s) & ~np.isnan(V[:, j])).sum())
            low = n_lab < LOW_N_DAYS
            r = {"feature": f, "name": FF.NAMES[f], "state": s, "n_labelled_days": n_lab, "n_days_with_value": n_val,
                 "LOW_N": low, "mean_of_daily_median": float(base[s]),
                 "diff_vs_S2": float(base[s] - base[REF]) if s != REF else 0.0, "ci95_low": np.nan, "ci95_high": np.nan,
                 "n_boot_valid": np.nan}
            if s != REF and not low:
                d = bm[s] - bm[REF]; d = d[~np.isnan(d)]
                r.update(ci95_low=float(np.quantile(d, .025)), ci95_high=float(np.quantile(d, .975)), n_boot_valid=len(d))
            rows.append(r)
    return pd.DataFrame(rows)


def load_regimes(k):
    r = pd.read_csv(REG / f"regimes_asof_{k}.csv")
    return pd.Series(r["regime_asof"].values, index=pd.to_datetime(r["day"]).dt.tz_localize("UTC"))


def run_all(F, U, groups):
    M = masks(U, groups)
    out = {}
    for k, E in M.items():
        base = k.replace("_survivors_only", "")
        c1 = q1(F, E)
        cov_all = c1[c1.month == "ALL"].set_index("feature")["coverage"].to_dict()
        c3, _ = q3(F, E)
        R, cl, _ = q4(F, E)
        out[k] = {"q1": c1, "q2": q2(F, E), "q3": c3, "q4": R, "clusters": cl, "q5": q5(cl, cov_all),
                  "q6": q6(F, E, load_regimes(base))}
    return out, M


def survivorship(res):
    rows = []
    for k in FF.SCEN:
        a, b = res[k], res[k + "_survivors_only"]
        ca = a["q1"][a["q1"].month == "ALL"].set_index("feature"); cb = b["q1"][b["q1"].month == "ALL"].set_index("feature")
        pa = a["q3"].set_index(["feature", "k_days"]); pb = b["q3"].set_index(["feature", "k_days"])
        ga = a["q6"].set_index(["feature", "state"]); gb = b["q6"].set_index(["feature", "state"])
        for f in FEATS:
            r = {"scenario": k, "feature": f, "name": FF.NAMES[f],
                 "coverage_all": ca.loc[f, "coverage"], "coverage_survivors": cb.loc[f, "coverage"],
                 "persist1_all": pa.loc[(f, 1), "mean"], "persist1_survivors": pb.loc[(f, 1), "mean"],
                 "persist7_all": pa.loc[(f, 7), "mean"], "persist7_survivors": pb.loc[(f, 7), "mean"]}
            for s in ("S1", "S3", "UNKNOWN"):
                r[f"diff_{s}_vs_S2_all"] = ga.loc[(f, s), "diff_vs_S2"]; r[f"diff_{s}_vs_S2_survivors"] = gb.loc[(f, s), "diff_vs_S2"]
            rows.append(r)
        for t in map(str, THR):
            rows.append({"scenario": k, "feature": f"clusters@{t}", "name": "same" if a["clusters"][t] == b["clusters"][t] else "DIFFERENT"})
    return pd.DataFrame(rows)


def main(out_dir):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    FF.catalogue()
    Hh, U, groups = FF.load_pack()
    F = FF.features(Hh, U["P1"])
    res, M = run_all(F, U, groups)
    long = []
    for f in FEATS:
        x = F[f].stack(future_stack=True).dropna().rename("value").reset_index()
        x.columns = ["day", "series", "value"]; x["feature"] = f; long.append(x)
    L = pd.concat(long); L["day"] = L["day"].dt.strftime("%Y-%m-%d")
    L[["day", "series", "feature", "value"]].to_csv(out / "features_daily_raw.csv.gz", index=False, float_format="%.12g")
    for k, r in res.items():
        sfx = "" if k == "P1" else f"_{k}"
        r["q1"].to_csv(out / f"fd1_coverage{sfx}.csv", index=False)
        r["q2"].to_csv(out / f"fd1_stability_monthly{sfx}.csv", index=False)
        r["q3"].to_csv(out / f"fd1_persistence{sfx}.csv", index=False)
        r["q4"].to_csv(out / f"fd1_redundancy_matrix{sfx}.csv")
        json.dump({"clusters": r["clusters"], "representatives_q5": r["q5"],
                   "note": "Q5 is descriptive in FD-1; it excludes nothing (FD-2 test family is an open point for its approval)"},
                  open(out / f"fd1_clusters{sfx}.json", "w"), indent=1)
        r["q6"].to_csv(out / f"fd1_regime_relation{sfx}.csv", index=False)
    survivorship(res).to_csv(out / "fd1_survivorship.csv", index=False)
    meta = {"segment": "development", "days": [str(FF.DAYS[0].date()), str(FF.DAYS[-1].date())], "series": len(groups),
            "features": len(FEATS), "forward_outcome_computed": False,
            "catalogue_sha256": __import__("hashlib").sha256(FF.CATALOGUE.read_bytes()).hexdigest(),
            "eligible_series_days": {k: int(m.values.sum()) for k, m in M.items()}}
    json.dump(meta, open(out / "fd1_meta.json", "w"), indent=1)
    print(json.dumps(meta))
    return F, res


if __name__ == "__main__":
    main(sys.argv[1])
