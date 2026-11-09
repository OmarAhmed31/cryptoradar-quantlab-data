"""Acceptance tests VA1-VA6 for the Validation run (Plan v0.1.1 §4). Prints pass/fail only, never an IC or a label.
python3 -I tests/test_val.py [--fast] [out.json]   (--fast: VA4 on 2 days, VA5 on 300 rows)"""
import sys, json, math, gzip, csv, hashlib, pathlib, datetime as dt, warnings
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import fd2 as F2
from lab import val as V
from lab.segment_loader import GuardError, SegmentGuard, open_holdout
warnings.filterwarnings("ignore")

FAST = "--fast" in sys.argv
args = [a for a in sys.argv[1:] if a != "--fast"]
res = []
def rec(name, ok, detail=""):
    res.append({"test": name, "pass": bool(ok), "detail": str(detail)}); print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
def same(a, b, tol=1e-12):
    an = a is None or (isinstance(a, float) and math.isnan(a)); bn = b is None or (isinstance(b, float) and math.isnan(b))
    if an or bn: return an and bn
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-12)
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
UTC = dt.timezone.utc

# VA0 frozen code and frozen family
FROZEN = {"lab/fd_features.py": "184947f33127568bd34255dc5cd67c20d10ab68bc40af7e05924400df87d8de5",
          "lab/fd1.py": "e764154d134e5349d3efee4b46caa7ceb8edf83f132c236435d94b5e0c11e677",
          "lab/fd2.py": "7218bd6140d8a9eb2fe130ffb684920f51ae9126e808909e44f4fc46d2554de4"}
rec("VA0 FD code byte-identical to its accepted commits; family and catalogue hashes frozen",
    all(sha(V.LAB / k) == v for k, v in FROZEN.items()) and sha(V.FAMILY) == V.FAMILY_SHA
    and sha(FF.CATALOGUE) == "c51334e2bbb55ed1d1cfd21cd6350966a93992cae2552e640df5649682024024")

Hh, U, groups, fe = V.load_pack()
R, CL, D, counts, purge, daily, eidx, F, OUT, M = V.run(Hh, U, groups, fe)

# VA1 isolation
man = json.loads((V.PACK / "PACK_MANIFEST.json").read_text())
maxday = max(pd.read_csv(V.PACK / "universe" / f, usecols=["day"])["day"].max() for f in FF.SCEN.values())
hmax = max(df.index[df.notna().any(axis=1)].max() for df in Hh.values())
ok = man["max_candle_start_in_pack"] <= "2026-03-31 23:00" and maxday <= "2026-03-31" and hmax + pd.Timedelta(hours=1) <= V.V_DE \
     and (fe["cut"] < V.V_DE).all()
for fn in (lambda: open_holdout(), lambda: SegmentGuard("holdout")):
    try:
        fn(); ok = False
    except GuardError:
        pass
rec("VA1 isolation: no candle closing after 2026-04-01, no universe day >= 2026-04-01, cuts < 2026-04-01; Holdout sealed", ok,
    f"last candle {man['max_candle_start_in_pack']}, last day {maxday}")

# VA2 guard / entry window / H3
ed = [V.DAYS_X[i] for i in eidx]
ok = str(ed[0].date()) == "2025-09-08" and str(ed[-1].date()) == "2026-03-01" and len(ed) == 175 and purge == 0
ok &= all(OUT[h][0].drop(index=ed).isna().all().all() for h in F2.HS)
for t, h in ((dt.datetime(2026, 3, 2, tzinfo=UTC), 1), (dt.datetime(2025, 9, 5, tzinfo=UTC), 1), (dt.datetime(2026, 3, 1, tzinfo=UTC), 31)):
    try:
        V.VGUARD.check_outcome(t, dt.timedelta(days=h)); ok = False
    except GuardError:
        pass
try:
    V.VGUARD.check_decision_time(dt.datetime(2026, 4, 8, tzinfo=UTC)); ok = False
except GuardError:
    pass
rec("VA2 entries 2025-09-08..2026-03-01 (175), none in the embargo, outcomes inside Validation, H3 = 0, guard refusals", ok)

# VA3 Development-day features equal the FD-1 values (same frozen code)
fd1 = pd.read_csv(V.LAB / "out/feature_discovery/fd1_v0.13/features_daily_raw.csv.gz")
fd1 = fd1[fd1.series.isin(F["F01"].columns)]
bad = 0; n = 0
for f, g in fd1.groupby("feature"):
    X = F[f]
    a = X.stack(future_stack=True).rename("v").reset_index(); a.columns = ["day", "series", "v"]
    a["day"] = a["day"].dt.strftime("%Y-%m-%d")
    m = g.merge(a, on=["day", "series"], how="left")
    n += len(m)
    bad += int((~((m.value - m.v).abs() <= 1e-11 * np.maximum(1, m.value.abs()))).sum())
dev_extra = 0
for f in FF.NAMES:
    Xd = F[f].loc[F[f].index < FF.DEV_END]
    dev_extra += int(Xd.stack().shape[0])
rec("VA3 every FD-1 Development feature value is reproduced by the Validation context (same code, 1e-11)", bad == 0 and n > 0
    and dev_extra >= n, f"{n - bad}/{n} values")

# VA4 destructive future overwrite (features at t; outcomes at t, t+h)
rng = np.random.default_rng(4)
days = ["2025-10-15", "2026-02-20"] if FAST else ["2025-09-08", "2025-10-15", "2025-12-31", "2026-02-20"]
badf = badh = chk = 0
for ds in days:
    d = pd.Timestamp(ds, tz="UTC"); i = list(V.DAYS_X).index(d)
    for cut, what in ((d, "feat"), (d + pd.Timedelta(days=1), "h1"), (d + pd.Timedelta(days=7), "h7"), (d + pd.Timedelta(days=30), "h30")):
        H2 = {}
        for k, df in Hh.items():
            x = df.copy(); fut = x.index >= cut
            x.loc[fut] = x.loc[fut].notna() * rng.uniform(1e-3, 1e3, size=x.loc[fut].shape)
            H2[k] = x.where(~(fut[:, None] & (x == 0)))
        with V.validation_context():
            if what == "feat":
                F2b = FF.features(H2, U["P1"])
                for f in FF.NAMES:
                    a, b = F[f].iloc[i].values, F2b[f].iloc[i].values
                    eq = (np.isnan(a) & np.isnan(b)) | (a == b); chk += eq.size; badf += int((~eq).sum())
            else:
                h = int(what[1:]); O2 = F2.outcomes(H2, fe)
                a, b = OUT[h][0].iloc[i].values, O2[h][0].iloc[i].values
                eq = (np.isnan(a) & np.isnan(b)) | (a == b); chk += eq.size; badh += int((~eq).sum())
rec("VA4 destructive overwrite: features at t unchanged after corrupting candles >= t; outcomes unchanged after >= t+h",
    badf == 0 and badh == 0, f"{chk - badf - badh}/{chk}, days {days}")

# VA5 independent naive outcomes (normal + every eligible forced exit) and IC = scipy
fer = {}
with open(V.PACK / "forced_exit_val.csv") as fh:
    for x in csv.DictReader(fh): fer[x["series"]] = x
cache = {}
def lastclose(s):
    if s not in cache:
        dd = {}
        with gzip.open(V.PACK / "hourly" / f"{s}.csv.gz", "rt") as fh:
            for x in csv.DictReader(fh):
                dd[dt.datetime.fromtimestamp(int(x["ts_utc_ms"]) / 1000, UTC).date()] = float(x["close"])
        cache[s] = dd
    return cache[s]
def naive(s, d, h):
    lc = lastclose(s); entry = lc.get((d - dt.timedelta(days=1)).date()); r = fer.get(s)
    if r is not None:
        cut = dt.datetime.strptime(r["cut_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        if cut <= d: return float("nan")
        if cut < d + dt.timedelta(days=h):
            if entry is None or r["status"] != "PRICED" or int(r["minutes_last_trade_to_cut"]) > 60: return float("nan")
            return float(r["last_trade_price"]) / entry - 1
    ex = lc.get((d + dt.timedelta(days=h - 1)).date())
    return float("nan") if entry is None or ex is None else ex / entry - 1
E = M["P1"]; eset = set(eidx)
pos = [(i, j) for i, j in np.argwhere(E.values) if i in eset]
pick = [pos[k] for k in np.random.default_rng(9).choice(len(pos), size=min(len(pos), 300 if FAST else 1000), replace=False)]
forced = [(i, j, h) for h in F2.HS for i, j in np.argwhere((OUT[h][1].values == "DELISTING_FORCED_EXIT") & E.values)]
cells = [(i, j, h) for i, j in pick for h in F2.HS] + forced
bad5 = [(E.columns[j], h) for i, j, h in cells if not same(float(OUT[h][0].iat[i, j]), naive(E.columns[j], V.DAYS_X[i].to_pydatetime(), h))]
from scipy.stats import spearmanr
ok_ic = True
for f, h in (("F07", 7), ("F13", 30), ("F21", 1), ("F16", 1)):
    ic, _ = daily["P1"][(f, h)]
    for i in (eidx[0], eidx[80], eidx[-1]):
        x, y = F[f].values[i], OUT[h][0].values[i]; m = E.values[i] & ~np.isnan(x) & ~np.isnan(y)
        ref = spearmanr(x[m], y[m]).statistic if m.sum() >= 20 else np.nan
        ok_ic &= same(float(ic.iloc[i]), float(ref), 1e-9)
rec("VA5 independent naive outcomes (incl. every eligible forced exit) and IC = scipy Spearman on eligible series",
    not bad5 and ok_ic and len(forced) > 0, f"{len(cells)} outcomes ({len(forced)} forced exits); mismatches {len(bad5)}")

# VA6 family, one-sided p, NW, BH/BY, labels (re-derived independently), synthetic rules
fam = json.loads(V.FAMILY.read_bytes())["hypotheses"]
ok = [(x["feature"], x["h_days"], x["direction"]) for x in fam] == list(zip(R.feature, R.h_days, R.direction)) and len(R) == 41
def nw_naive(x, L):
    x = [v for v in x if not math.isnan(v)]; Tn = len(x); m = sum(x) / Tn
    g = lambda l: sum((x[t] - m) * (x[t - l] - m) for t in range(l, Tn)) / Tn
    v = g(0) + 2 * sum((1 - l / (L + 1)) * g(l) for l in range(1, L + 1)); return m / math.sqrt(v / Tn)
from scipy.stats import norm          # sf is accurate in the tail (1 - cdf is not)
for _, r in R.iterrows():
    ic, _ = daily["P1"][(r.feature, r.h_days)]
    t = nw_naive(list(ic.iloc[eidx].values), r.h_days - 1)
    ok &= same(r.nw_t, t, 1e-9) and same(r.p_one_sided, float(norm.sf(r.direction * t)), 1e-7) and r.nw_lag == r.h_days - 1
def adj_naive(p, c=1.0):
    m = len(p); o = sorted(range(m), key=lambda k: p[k]); a = [0.0] * m
    for k in range(m): a[o[k]] = min(1.0, min(p[o[j]] * m * c / (j + 1) for j in range(k, m)))
    return a
cm = sum(1 / i for i in range(1, 42))
ok &= all(same(float(a), b) for a, b in zip(R.p_bh, adj_naive(list(R.p_one_sided)))) and all(same(float(a), b) for a, b in zip(R.p_by, adj_naive(list(R.p_one_sided), cm)))
for _, r in R.iterrows():
    exp = "REVERSED" if np.sign(r.val_mean_ic) != r.direction else ("NOT_REPLICATED" if r.p_bh > 0.10 else
          ("REPLICATED" if r.p_by <= 0.10 else "REPLICATED — BH_ONLY — FAILS_BY_SENSITIVITY"))
    ok &= r.label == exp
    exp_ratio = "N/A" if (r.dev_mean_ic == 0 or r.dev_boot_ci95_low <= 0 <= r.dev_boot_ci95_high) else r.val_mean_ic / r.dev_mean_ic
    ok &= (r.ratio_val_to_dev == "N/A") if exp_ratio == "N/A" else same(float(r.ratio_val_to_dev), float(exp_ratio))
rec("VA6 41 frozen hypotheses in order; NW (lag h-1), one-sided p, BH/BY and labels equal independent derivations", ok)
syn = [V.label(0.02, 1, 0.01, 0.01) == "REPLICATED", V.label(0.02, 1, 0.05, 0.2) == "REPLICATED — BH_ONLY — FAILS_BY_SENSITIVITY",
       V.label(0.02, 1, 0.3, 0.9) == "NOT_REPLICATED", V.label(-0.02, 1, 0.01, 0.01) == "REVERSED", V.label(0.0, 1, 0.01, 0.01) == "REVERSED",
       V.ratio(-0.05, -0.1, [-0.2, -0.05]) == 0.5, V.ratio(0.05, 0.1, [-0.01, 0.2]) == "N/A", V.ratio(0.05, 0.0, [0.0, 0.0]) == "N/A"]
T = pd.DataFrame({"fd1_cluster_0.80": ["A"] * 4 + ["B"] * 3 + ["C"] * 2 + ["D"] * 3,
                  "label": ["REPLICATED", "REPLICATED", "NOT_REPLICATED", "NOT_REPLICATED",
                            "REPLICATED", "REPLICATED", "REVERSED",
                            "REVERSED", "REVERSED",
                            "REPLICATED — BH_ONLY — FAILS_BY_SENSITIVITY", "NOT_REPLICATED", "NOT_REPLICATED"],
                  "val_mean_ic": [0.1] * 12})
cs = V.cluster_summary(T).set_index("cluster")["label"].to_dict()
syn.append(cs == {"A": "CLUSTER_REPLICATED", "B": "CLUSTER_NOT_REPLICATED", "C": "CLUSTER_REVERSED", "D": "CLUSTER_NOT_REPLICATED"})
rec("VA6 synthetic: label rule, BY label, ratio N/A rule and the fixed cluster rule", all(syn), [i for i, s in enumerate(syn) if not s])

n_pass = sum(r["pass"] for r in res)
summary = {"passed": n_pass, "of": len(res), "PASS": n_pass == len(res), "mode": "fast" if FAST else "full"}
if args:
    json.dump({"results": res, **summary}, open(args[0], "w"), indent=1)
print(json.dumps(summary))
