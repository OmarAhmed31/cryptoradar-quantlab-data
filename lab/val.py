"""Validation run (Validation Plan v0.1.1, approved; Protocol v1.2 FIXED). ONE SHOT. Association check only:
no strategy, trade, P&L, cost or portfolio return. No MI or regime analysis on Validation. The Holdout is not touched.

python3 -I lab/val.py <out_dir>

Reuses the FROZEN FD code unchanged (lab/fd_features.py, lab/fd1.py masks, lab/fd2.py outcome/IC/NW/bootstrap/BH/BY):
inside `validation_context()` the day grid of those modules is extended to 2024-01-01 .. 2026-03-31 (lookback, H5),
the Development guard is replaced by SegmentGuard("validation") and the entry days are the Validation entry window.
Day-d values depend only on data before d (FD-1 FA1), so Development-day values are identical to FD-1 (test VA3).

Per hypothesis (the 41 of out/validation/validation_family.json, direction fixed from FD-2):
  daily rank IC over P1-eligible series (>= 20), entries t in [2025-09-08, 2026-03-02)
  Newey-West t (Bartlett, lag h-1), ONE-SIDED p in the FD-2 direction: p = Phi(-direction * t)
  BH q = 0.10 over the 41 (rule), BY q = 0.10 (sensitivity)
  label: REVERSED if sign(mean IC) != direction; else REPLICATED if p_BH <= 0.10; else NOT_REPLICATED;
         REPLICATED with p_BY > 0.10 -> "REPLICATED — BH_ONLY — FAILS_BY_SENSITIVITY"
  ratio Validation/Development mean IC; N/A if the Development mean IC is 0 or its FD-2 bootstrap CI includes 0
  cluster summary (FD-1 clusters at 0.80): CLUSTER_REPLICATED if R >= n/2 and V == 0; CLUSTER_REVERSED if V > n/2;
         else CLUSTER_NOT_REPLICATED (a summary, not a separate test)
S50k / S250k: mean IC and sign, descriptive. The other 23 FD-2 cells and the 2 exploratory cells: descriptive only.
"""
import sys, json, math, pathlib, contextlib, warnings, hashlib
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import fd1 as FD
from lab import fd2 as F2
from lab.segment_loader import SegmentGuard, GuardError, RESEARCH_START, SEGMENTS, open_holdout
warnings.filterwarnings("ignore", category=RuntimeWarning)

LAB = FF.LAB
PACK = LAB / "out/validation/val_pack_v1"
FAMILY = LAB / "out/validation/validation_family.json"
FAMILY_SHA = "ff2df7b9d634f281deca08c01791a1c36617f9946fb4eb1f7dc40eac78264250"
V_DS, V_DE, V_ES, V_EE = [pd.Timestamp(x) for x in SEGMENTS["validation"]]
DAYS_X = pd.date_range(pd.Timestamp(RESEARCH_START), V_DE - pd.Timedelta(days=1), freq="D")
VGUARD = SegmentGuard("validation")
Q = 0.10
CLUSTERS = LAB / "out/feature_discovery/fd1_v0.13/fd1_clusters.json"


def family():
    b = FAMILY.read_bytes()
    if hashlib.sha256(b).hexdigest() != FAMILY_SHA:
        raise GuardError("validation family changed after it was frozen")
    fam = json.loads(b)["hypotheses"]
    assert len(fam) == 41
    return fam


def load_pack(pack=PACK):
    pack = pathlib.Path(pack)
    groups = pd.read_csv(pack / "groups.csv").set_index("series")["group"]
    grid = pd.date_range(DAYS_X[0], V_DE - pd.Timedelta(hours=1), freq="h")
    cols = {k: {} for k in ("open", "high", "low", "close", "vol_quote", "traded_minutes")}
    for s in groups.index:
        x = pd.read_csv(pack / "hourly" / f"{s}.csv.gz", usecols=["ts_utc_ms"] + list(cols), dtype={"ts_utc_ms": "int64"})
        t = pd.to_datetime(x["ts_utc_ms"], unit="ms", utc=True)
        keep = (t >= pd.Timestamp(RESEARCH_START)) & (t + pd.Timedelta(hours=1) <= V_DE)
        for k in cols:
            cols[k][s] = pd.Series(x.loc[keep, k].astype("float64").values, index=t[keep])
    Hh = {k: pd.DataFrame(v).reindex(grid) for k, v in cols.items()}
    U = {}
    for k, f in FF.SCEN.items():
        d = pd.read_csv(pack / "universe" / f, usecols=["series", "day", "assessable", "THR30", "DV30_med", "eligible"])
        d["day"] = pd.to_datetime(d["day"]).dt.tz_localize("UTC")
        d = d[(d["day"] >= DAYS_X[0]) & (d["day"] < V_DE)]
        U[k] = {c: d.pivot(index="day", columns="series", values=c).reindex(index=DAYS_X, columns=groups.index)
                for c in ("assessable", "THR30", "DV30_med", "eligible")}
        U[k]["eligible"] = U[k]["eligible"].fillna(False).astype(bool)
        U[k]["assessable"] = U[k]["assessable"].fillna(False).astype(bool)
    fe = pd.read_csv(pack / "forced_exit_val.csv")
    fe["cut"] = pd.to_datetime(fe["cut_utc"], utc=True); fe["last_trade"] = pd.to_datetime(fe["last_traded_minute_utc"], utc=True)
    assert_val_only(Hh, fe)
    return Hh, U, groups, fe.set_index("series")


def assert_val_only(Hh, fe=None):
    for k, df in Hh.items():
        v = df.index[df.notna().any(axis=1)]
        if len(v) and (v.min() < pd.Timestamp(RESEARCH_START) or v.max() + pd.Timedelta(hours=1) > V_DE):
            raise GuardError(f"Validation input {k} outside [2024-01-01, 2026-04-01): {v.min()} .. {v.max()}")
    if fe is not None and (fe["cut"] >= V_DE).any():
        raise GuardError("forced exit with a cut after Validation")
    return True


def _val_guard(F):
    """features: every Validation decision day passes the validation guard (lookback closed by t, >= 2024-01-01);
    windows not complete -> missing (same FIRST_INDEX rule as FD-1)."""
    for f, L in FF.LOOKBACK.items():
        for d in FF.DAYS[(FF.DAYS >= V_DS) & (FF.DAYS < V_DE)]:
            start = max(d - pd.Timedelta(days=L), pd.Timestamp(RESEARCH_START))
            VGUARD.check_feature(d.to_pydatetime(), [start.to_pydatetime(), (d - pd.Timedelta(hours=1)).to_pydatetime()])
    for f, k in FF.FIRST_INDEX.items():
        if F[f].iloc[:k].notna().any().any():
            raise GuardError(f"{f} has a value before its window is complete")
    return True


@contextlib.contextmanager
def validation_context():
    saved = dict(DAYS=FF.DAYS, ND=FF.ND, guard=FF.guard, ado=FF.assert_dev_only, eidx=F2.ENTRY_IDX, g2=F2.GUARD)
    try:
        FF.DAYS = DAYS_X; FF.ND = len(DAYS_X); FF.guard = _val_guard; FF.assert_dev_only = assert_val_only
        F2.ENTRY_IDX = np.where((DAYS_X >= V_ES) & (DAYS_X < V_EE))[0]; F2.GUARD = VGUARD
        yield
    finally:
        FF.DAYS, FF.ND, FF.guard, FF.assert_dev_only = saved["DAYS"], saved["ND"], saved["guard"], saved["ado"]
        F2.ENTRY_IDX, F2.GUARD = saved["eidx"], saved["g2"]


def purge_count(OUT):
    """H3 for Validation: outcomes whose interval is not fully inside the Validation segment or whose entry is outside
    the entry window (expected 0)."""
    bad = 0
    for h in F2.HS:
        V = OUT[h][0]
        for d in V.index[V.notna().any(axis=1)]:
            bad += int(d < V_ES or d >= V_EE or d + pd.Timedelta(days=h) > V_DE)
    return bad


def one_sided_p(t, direction):
    return 0.5 * math.erfc(direction * t / math.sqrt(2)) if not np.isnan(t) else np.nan


def label(mean_ic, direction, p_bh, p_by):
    if np.isnan(mean_ic) or np.sign(mean_ic) != direction:
        return "REVERSED"
    if p_bh <= Q:
        return "REPLICATED" if p_by <= Q else "REPLICATED — BH_ONLY — FAILS_BY_SENSITIVITY"
    return "NOT_REPLICATED"


def ratio(val, dev, ci):
    if dev == 0 or (ci[0] <= 0 <= ci[1]):
        return "N/A"
    return val / dev


def cluster_summary(rows):
    out = []
    for c, g in rows.groupby("fd1_cluster_0.80"):
        n = len(g); R = int(g.label.str.startswith("REPLICATED").sum()); V = int((g.label == "REVERSED").sum())
        lab = "CLUSTER_REPLICATED" if (R >= n / 2 and V == 0) else ("CLUSTER_REVERSED" if V > n / 2 else "CLUSTER_NOT_REPLICATED")
        out.append({"cluster": c, "n": n, "replicated": R, "reversed": V, "not_replicated": n - R - V,
                    "median_val_ic": float(g.val_mean_ic.median()), "label": lab, "note": "summary of members, not a separate test"})
    return pd.DataFrame(out)


def run(Hh, U, groups, fe):
    fam = family()
    with validation_context():
        F = FF.features(Hh, U["P1"])
        M = FD.masks(U, groups)
        OUT = F2.outcomes(Hh, fe)
        F2.guard_exit_candles(Hh)
        if any(((OUT[h][1].values == "UNPRICEABLE_FORCED_EXIT") & M["P1"].values).any() for h in F2.HS):
            raise GuardError("STOP: unpriceable forced exit among eligible Validation entries")
        daily = {sc: {} for sc in FF.SCEN}
        for sc in FF.SCEN:
            for h in F2.HS:
                for f in FF.NAMES:
                    daily[sc][(f, h)] = F2.daily_ic(F[f], OUT[h][0], M[sc])
        eidx = F2.ENTRY_IDX.copy()
        purge = purge_count(OUT)
        counts = F2.outcome_counts(OUT, {k: M[k] for k in FF.SCEN})
    rows = []
    for x in fam:
        f, h, dirn = x["feature"], x["h_days"], x["direction"]
        ic, n = daily["P1"][(f, h)]
        v = ic.iloc[eidx].values
        t, _ = F2.newey_west_t(v, h - 1)
        lo, hi = F2.boot_ci(v, max(7, h), np.random.default_rng(F2.SEED))
        r = {"feature": f, "name": x["name"], "h_days": h, "direction": dirn, "fd2_label": x["fd2_label"],
             "fd1_cluster_0.80": x["fd1_cluster_0.80"], "dev_mean_ic": x["dev_mean_ic"],
             "dev_boot_ci95_low": x["dev_boot_ci95"][0], "dev_boot_ci95_high": x["dev_boot_ci95"][1],
             "val_days_with_ic": int((~np.isnan(v)).sum()), "val_mean_ic": float(np.nanmean(v)), "val_median_ic": float(np.nanmedian(v)),
             "nw_lag": h - 1, "nw_t": t, "p_one_sided": one_sided_p(t, dirn), "val_boot_ci95_low": lo, "val_boot_ci95_high": hi}
        for sc in ("S50k", "S250k"):
            m = float(np.nanmean(daily[sc][(f, h)][0].iloc[eidx].values))
            r[f"{sc}_mean_ic"] = m; r[f"{sc}_same_sign"] = bool(np.sign(m) == dirn)
        r["ratio_val_to_dev"] = ratio(r["val_mean_ic"], r["dev_mean_ic"], x["dev_boot_ci95"])
        rows.append(r)
    R = pd.DataFrame(rows)
    R["p_bh"] = F2.bh(R.p_one_sided.values); R["p_by"] = F2.by(R.p_one_sided.values)
    R["label"] = [label(a, b, c, d) for a, b, c, d in zip(R.val_mean_ic, R.direction, R.p_bh, R.p_by)]
    famset = {(x["feature"], x["h_days"]) for x in fam}
    desc = []
    dev = pd.read_csv(LAB / "out/feature_discovery/fd2_v0.14/fd2_ic_summary_P1.csv").set_index(["feature", "h_days"])
    for h in F2.HS:
        for f in FF.NAMES:
            if (f, h) in famset:
                continue
            v = daily["P1"][(f, h)][0].iloc[eidx].values
            desc.append({"feature": f, "name": FF.NAMES[f], "h_days": h, "fd2_label": dev.loc[(f, h), "label"],
                         "dev_mean_ic": float(dev.loc[(f, h), "mean_ic"]), "val_mean_ic": float(np.nanmean(v)),
                         "same_sign_as_dev": bool(np.sign(np.nanmean(v)) == np.sign(dev.loc[(f, h), "mean_ic"])), "descriptive_only": True})
    return R, cluster_summary(R), pd.DataFrame(desc), counts, purge, daily, eidx, F, OUT, M


def main(out_dir):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    FF.catalogue()
    Hh, U, groups, fe = load_pack()
    R, CL, D, counts, purge, daily, eidx, F, OUT, M = run(Hh, U, groups, fe)
    R.to_csv(out / "val_results_41.csv", index=False)
    CL.to_csv(out / "val_cluster_summary.csv", index=False)
    D.to_csv(out / "val_descriptive_other_cells.csv", index=False)
    counts.to_csv(out / "val_outcome_counts.csv", index=False)
    rows = []
    for sc, d in daily.items():
        for (f, h), (ic, n) in d.items():
            x = pd.DataFrame({"day": ic.index[eidx].strftime("%Y-%m-%d"), "ic": ic.iloc[eidx].values, "n_series": n.iloc[eidx].values})
            x["scenario"] = sc; x["feature"] = f; x["h_days"] = h; rows.append(x)
    pd.concat(rows)[["scenario", "feature", "h_days", "day", "ic", "n_series"]].to_csv(
        out / "val_ic_daily.csv.gz", index=False, float_format="%.12g", compression={"method": "gzip", "mtime": 0})
    meta = {"segment": "validation", "entry_days": [str(DAYS_X[eidx[0]].date()), str(DAYS_X[eidx[-1]].date())], "n_entry_days": int(len(eidx)),
            "hypotheses": 41, "q": Q, "purge_count_H3": purge, "family_sha256": FAMILY_SHA,
            "labels": R.label.value_counts().to_dict(), "cluster_labels": CL.label.value_counts().to_dict(),
            "pack_manifest_sha256": hashlib.sha256((PACK / "PACK_MANIFEST.json").read_bytes()).hexdigest()}
    json.dump(meta, open(out / "val_meta.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: meta[k] for k in ("n_entry_days", "purge_count_H3")}))       # labels are NOT printed here
    return meta


if __name__ == "__main__":
    main(sys.argv[1])
