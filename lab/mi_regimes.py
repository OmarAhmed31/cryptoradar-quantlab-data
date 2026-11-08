"""M5 — point-in-time regime models (Protocol v1.2 R1-R6). Development only. No future return is used.

regimes(mi_daily_df) -> (labels_df, models, stability)
Inputs (R1, past-only MI quantities, fixed before any regime output was computed):
  breadth_7, breadth_30, median_ret_7, dispersion_7, mkt_vol_7, mkt_vol_30, median_corr_btc_30
R2  k in {3,4,5,6} by mean silhouette on [2024-01-01, 2024-07-01) only; tie -> smaller k; k then fixed.
R3  first model fitted on [2024-01-01, 2024-07-01), labels days from 2024-07-01; refit on the 1st of every month on an
    expanding window of Development days BEFORE the refit time; each day labelled once by the model in force (as-known).
R6a robust scaling (median / IQR) on each training window; IQR == 0 -> input dropped for that refit (logged)
R6b k-means Lloyd, n_init=50, random_state=20260108
R6c centroids -> original units -> anchor scaling -> Hungarian match to the anchor; > 2.0 anchor units = DEFINITION_DRIFT
R6d UNKNOWN: missing input | d2 == 0 | d1/d2 > 0.80 | d1 > 95th pct of the model's training nearest distances
R6e complete rows only for training; a missing input day is UNKNOWN (inputs already need >= 20 contributing series)
Anchor state names: S1..Sk ordered by the anchor centroid's median_ret_7 (ascending) — a fixed naming rule, no meaning implied.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from scipy.optimize import linear_sum_assignment

INPUTS = ["breadth_7", "breadth_30", "median_ret_7", "dispersion_7", "mkt_vol_7", "mkt_vol_30", "median_corr_btc_30"]
K_RANGE = (3, 4, 5, 6)
SEED, N_INIT = 20260108, 50
FIRST_FIT = pd.Timestamp("2024-07-01", tz="UTC")
DEV_START = pd.Timestamp("2024-01-01", tz="UTC")
DEV_END = pd.Timestamp("2025-09-01", tz="UTC")
DRIFT, AMBIG, OUTLIER_Q = 2.0, 0.80, 0.95


def _scale_fit(X):
    med = X.median()
    iqr = X.quantile(0.75) - X.quantile(0.25)
    keep = iqr[iqr > 0].index.tolist()
    return med[keep], iqr[keep], [c for c in X.columns if c not in keep]


def _fit(X, k):
    med, iqr, dropped = _scale_fit(X)
    Z = ((X[med.index] - med) / iqr).values
    km = KMeans(n_clusters=k, n_init=N_INIT, random_state=SEED, algorithm="lloyd").fit(Z)
    dist = np.sqrt(((Z[:, None, :] - km.cluster_centers_[None, :, :]) ** 2).sum(-1))
    nearest = dist.min(1)
    return {"cols": med.index.tolist(), "med": med.values, "iqr": iqr.values, "dropped": dropped,
            "centers_z": km.cluster_centers_, "centers_orig": km.cluster_centers_ * iqr.values + med.values,
            "outlier_thr": float(np.quantile(nearest, OUTLIER_Q)), "n_train": int(len(X))}


def choose_k(X):
    med, iqr, _ = _scale_fit(X)
    Z = ((X[med.index] - med) / iqr).values
    sc = {}
    for k in K_RANGE:
        lab = KMeans(n_clusters=k, n_init=N_INIT, random_state=SEED, algorithm="lloyd").fit_predict(Z)
        sc[k] = float(silhouette_score(Z, lab))
    best = max(sc.values())
    k = min(k for k, v in sc.items() if v == best)          # tie -> smaller k
    return k, sc


def _align(model, anchor):
    """map each centroid of `model` to an anchor state (Hungarian, Euclidean in the anchor's scaling)."""
    cols = anchor["cols"]
    idx = [model["cols"].index(c) for c in cols if c in model["cols"]]
    common = [c for c in cols if c in model["cols"]]
    a_idx = [cols.index(c) for c in common]
    A = (anchor["centers_orig"][:, a_idx] - anchor["med"][a_idx]) / anchor["iqr"][a_idx]
    B = (model["centers_orig"][:, idx] - anchor["med"][a_idx]) / anchor["iqr"][a_idx]
    C = np.sqrt(((B[:, None, :] - A[None, :, :]) ** 2).sum(-1))
    r, c = linear_sum_assignment(C)
    mapping = {int(i): int(j) for i, j in zip(r, c)}
    dist = {int(i): float(C[i, j]) for i, j in zip(r, c)}
    return mapping, dist


def _assign(model, x):
    if any(pd.isna(x.get(c)) for c in INPUTS):
        return None, "UNKNOWN", "missing_input"
    z = (np.array([x[c] for c in model["cols"]]) - model["med"]) / model["iqr"]
    d = np.sqrt(((model["centers_z"] - z) ** 2).sum(1))
    o = np.argsort(d)
    d1, d2 = d[o[0]], d[o[1]]
    if d2 == 0:
        return None, "UNKNOWN", "coincident_centroids"
    if d1 / d2 > AMBIG:
        return int(o[0]), "UNKNOWN", "ambiguous"
    if d1 > model["outlier_thr"]:
        return int(o[0]), "UNKNOWN", "outlier"
    return int(o[0]), None, ""


def regimes(mi):
    """mi: DataFrame indexed by UTC day (Development) with the INPUTS columns."""
    mi = mi[(mi.index >= DEV_START) & (mi.index < DEV_END)]
    X0 = mi.loc[mi.index < FIRST_FIT, INPUTS].dropna()
    k, sil = choose_k(X0)
    refits = [FIRST_FIT]
    while refits[-1] + pd.offsets.MonthBegin(1) < DEV_END:
        refits.append(refits[-1] + pd.offsets.MonthBegin(1))
    models, anchor = [], None
    for i, r in enumerate(refits):
        Xt = mi.loc[mi.index < r, INPUTS]
        dropped_rows = int(Xt.isna().any(axis=1).sum())
        m = _fit(Xt.dropna(), k)
        m.update(id=f"M{i:02d}", refit_utc=str(r), train_window=[str(DEV_START), str(r)], dropped_rows=dropped_rows,
                 valid_until=str(refits[i + 1] if i + 1 < len(refits) else DEV_END))
        if anchor is None:
            anchor = m
            order = np.argsort(m["centers_orig"][:, m["cols"].index("median_ret_7")])
            anchor["names"] = {int(c): f"S{j + 1}" for j, c in enumerate(order)}
            m["mapping"] = {c: c for c in range(k)}; m["match_dist"] = {c: 0.0 for c in range(k)}
        else:
            m["mapping"], m["match_dist"] = _align(m, anchor)
        m["definition_drift"] = any(v > DRIFT for v in m["match_dist"].values())
        models.append(m)
    rows = []
    for day, x in mi.iterrows():
        if day < FIRST_FIT:
            rows.append({"day": day, "regime_asof": "NO_MODEL", "model_id": "", "reason": "before first model"}); continue
        m = [mm for mm in models if pd.Timestamp(mm["refit_utc"]) <= day][-1]
        c, unk, why = _assign(m, x)
        name = unk or anchor["names"][m["mapping"][c]]
        rows.append({"day": day, "regime_asof": name, "model_id": m["id"], "reason": why,
                     "nearest_anchor_state": anchor["names"][m["mapping"][c]] if c is not None else ""})
    L = pd.DataFrame(rows).set_index("day")
    # R4 stability
    stab = []
    for i in range(1, len(models)):
        new, old = models[i], models[i - 1]
        w = mi.loc[(mi.index < pd.Timestamp(old["refit_utc"])), INPUTS].dropna()
        agree = []
        for _, x in w.iterrows():
            a, _, _ = _assign(old, x); b, _, _ = _assign(new, x)
            if a is not None and b is not None:
                agree.append(old["mapping"][a] == new["mapping"][b])
        stab.append({"refit": new["id"], "refit_utc": new["refit_utc"], "agreement_on_previous_window": float(np.mean(agree)) if agree else np.nan,
                     "n_compared": len(agree), "definition_drift": new["definition_drift"],
                     "max_match_dist": max(new["match_dist"].values())})
    run_stats = calendar_runs(L["regime_asof"])
    lab = L["regime_asof"]
    summary = {"k": k, "silhouette_by_k": sil, "refits": len(models), **run_stats, "label_counts": lab.value_counts().to_dict(),
               "unknown_reasons": L.loc[lab == "UNKNOWN", "reason"].value_counts().to_dict(),
               "drift_refits": [m["id"] for m in models if m["definition_drift"]]}
    return L, models, pd.DataFrame(stab), summary, anchor


def calendar_runs(lab):
    """Runs on the CALENDAR (v0.11.1): the label series is placed on every calendar day; UNKNOWN and NO_MODEL BREAK a
    run (they are never dropped first, so two separate periods can never merge). A run = maximal block of consecutive
    calendar days with the same KNOWN state. Flip rate = share of adjacent calendar-day pairs, both known, whose state
    differs; its denominator is reported."""
    cal = pd.date_range(lab.index.min(), lab.index.max(), freq="D", tz=lab.index.tz)
    x = lab.reindex(cal).fillna("MISSING_DAY")
    known = ~x.isin(["NO_MODEL", "UNKNOWN", "MISSING_DAY"])
    runs, cur, n = [], None, 0
    for v, k in zip(x.values, known.values):
        if k and v == cur:
            n += 1
        else:
            if cur is not None:
                runs.append((cur, n))
            cur, n = (v, 1) if k else (None, 0)
    if cur is not None:
        runs.append((cur, n))
    pairs = [(a, b) for a, b, ka, kb in zip(x.values[:-1], x.values[1:], known.values[:-1], known.values[1:]) if ka and kb]
    flips = sum(a != b for a, b in pairs)
    by_state = {}
    for st, ln in runs:
        by_state.setdefault(st, []).append(ln)
    return {"runs_known": len(runs), "mean_run_days_calendar": float(np.mean([r[1] for r in runs])) if runs else float("nan"),
            "median_run_days_calendar": float(np.median([r[1] for r in runs])) if runs else float("nan"),
            "run_days_by_state": {k: {"runs": len(v), "mean": float(np.mean(v)), "median": float(np.median(v)), "max": int(max(v))} for k, v in sorted(by_state.items())},
            "flip_rate_adjacent_known_pairs": float(flips / len(pairs)) if pairs else float("nan"),
            "flip_numerator": int(flips), "flip_denominator_adjacent_known_pairs": len(pairs),
            "unknown_breaks_runs": True}


def models_json(models, anchor):
    out = []
    for m in models:
        out.append({"id": m["id"], "refit_utc": m["refit_utc"], "valid_until": m["valid_until"], "train_window": m["train_window"],
                    "n_train": m["n_train"], "dropped_rows": m["dropped_rows"], "dropped_inputs_iqr0": m["dropped"],
                    "inputs": m["cols"], "scaler_median": list(map(float, m["med"])), "scaler_iqr": list(map(float, m["iqr"])),
                    "centroids_original_units": m["centers_orig"].tolist(), "outlier_threshold": m["outlier_thr"],
                    "mapping_to_anchor": {str(k): anchor["names"][v] for k, v in m["mapping"].items()},
                    "match_distance": {str(k): v for k, v in m["match_dist"].items()}, "definition_drift": m["definition_drift"]})
    return out
