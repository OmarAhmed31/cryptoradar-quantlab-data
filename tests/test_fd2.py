"""Acceptance tests for FD-2 (plan v0.1.1 §4/§6 FA4-FA6 + Decision Record v2 D4-D6). Development only.
Prints pass/fail only, never an IC value.
python3 -I tests/test_fd2.py [--fast] [out.json]   (--fast: T2 on 2 days, T3 on 300 rows)"""
import sys, json, math, gzip, csv, pathlib, datetime as dt, warnings
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import fd1 as FD
from lab import fd2 as F2
from lab.segment_loader import GuardError
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

Hh, U, groups = FF.load_pack()
fe = F2.load_forced()
F, M, OUT, T, C, R, dailies = F2.run(Hh, U, groups, fe)
E = M["P1"]

# T0 family (D4, D5)
conf = F2.family()
expect = [(f, 1) for f in FF.NAMES if f != "F01"] + [(f, 7) for f in FF.NAMES if f != "F02"] + [(f, 30) for f in FF.NAMES]
rec("T0 confirmatory family = exactly the 64 cells of Decision Record v2", sorted(conf) == sorted(expect) and len(set(conf)) == 64)
rec("T0 exploratory cells = {F01 x 1, F02 x 7}, labelled EXPLORATORY_SEEN_IN_FD1, outside BH/BY",
    set(map(tuple, C[C.family != "CONFIRMATORY"][["feature", "h_days"]].values.tolist())) == {("F01", 1), ("F02", 7)}
    and (C[C.family != "CONFIRMATORY"].label == "EXPLORATORY_SEEN_IN_FD1").all() and C[C.family != "CONFIRMATORY"][["p_bh", "p_by"]].isna().all().all()
    and not C[C.family != "CONFIRMATORY"].candidate.any())

# T1 H2 / H3 / guard
rec("T1 entry days: 2024-01-01 .. 2025-08-01 (t < 2025-08-02), 579 days",
    str(FF.DAYS[F2.ENTRY_IDX[0]].date()) == "2024-01-01" and str(FF.DAYS[F2.ENTRY_IDX[-1]].date()) == "2025-08-01" and len(F2.ENTRY_IDX) == 579)
rec("T1 H3 purge count = 0 and no outcome on a non-entry day", F2.purge_count(OUT) == 0
    and all(OUT[h][0].iloc[F2.ENTRY_IDX[-1] + 1:].isna().all().all() for h in F2.HS))
ok = True
for t, h in ((dt.datetime(2025, 8, 2, tzinfo=dt.timezone.utc), 1), (dt.datetime(2025, 3, 1, tzinfo=dt.timezone.utc), 31)):
    try:
        F2.GUARD.check_outcome(t, dt.timedelta(days=h)); ok = False
    except GuardError:
        pass
try:
    F2.GUARD.check_outcome_candles(dt.datetime(2025, 3, 1, tzinfo=dt.timezone.utc), dt.timedelta(days=1), [dt.datetime(2025, 3, 2, tzinfo=dt.timezone.utc)]); ok = False
except GuardError:
    pass
rec("T1 guard refuses an entry on 2025-08-02, a 31-day horizon and an outcome candle after t+h", ok)

# T2 destructive: corrupt every candle starting at or after d+h -> outcome (d, h) unchanged
rng = np.random.default_rng(3)
days = ["2024-05-10", "2025-07-15"] if FAST else ["2024-01-20", "2024-05-10", "2024-12-31", "2025-07-15"]
bad = chk = 0
for ds in days:
    d = pd.Timestamp(ds, tz="UTC"); i = list(FF.DAYS).index(d)
    for h in F2.HS:
        cut = d + pd.Timedelta(days=h)
        H2 = {}
        for k, df in Hh.items():
            x = df.copy(); fut = x.index >= cut
            x.loc[fut] = x.loc[fut].notna() * rng.uniform(1e-3, 1e3, size=x.loc[fut].shape)
            H2[k] = x.where(~(fut[:, None] & (x == 0)))
        O2 = F2.outcomes(H2, fe)
        a, b = OUT[h][0].iloc[i].values, O2[h][0].iloc[i].values
        eq = (np.isnan(a) & np.isnan(b)) | (a == b)
        chk += eq.size; bad += int((~eq).sum())
rec("T2 destructive overwrite after t+h: every outcome (d, h) unchanged", bad == 0, f"{chk - bad}/{chk}, days {days}")

# T3 independent naive outcomes from the raw pack CSV + forced_exit_dev.csv
fer = {}
with open(F2.PACK2 / "forced_exit_dev.csv") as fh:
    for x in csv.DictReader(fh):
        fer[x["series"]] = x
cache = {}
def lastclose(s):
    if s not in cache:
        with gzip.open(FF.PACK / "hourly" / f"{s}.csv.gz", "rt") as fh:
            dd = {}
            for x in csv.DictReader(fh):
                t = dt.datetime.fromtimestamp(int(x["ts_utc_ms"]) / 1000, dt.timezone.utc)
                dd[t.date()] = float(x["close"])       # rows are time-sorted: the last one per day wins
        cache[s] = dd
    return cache[s]
def naive(s, d, h):
    lc = lastclose(s); entry = lc.get((d - dt.timedelta(days=1)).date())
    r = fer.get(s)
    if r is not None:
        cut = dt.datetime.strptime(r["cut_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        if cut <= d: return float("nan")
        if cut < d + dt.timedelta(days=h):
            if entry is None or r["status"] != "PRICED" or int(r["minutes_last_trade_to_cut"]) > 60: return float("nan")
            return float(r["last_trade_price"]) / entry - 1
    ex = lc.get((d + dt.timedelta(days=h - 1)).date())
    return float("nan") if entry is None or ex is None else ex / entry - 1
pos = [(i, j) for i, j in np.argwhere(E.values) if i in set(F2.ENTRY_IDX)]
pick = [pos[k] for k in np.random.default_rng(9).choice(len(pos), size=300 if FAST else 1000, replace=False)]
forced = [(i, j, h) for h in F2.HS for i, j in np.argwhere((OUT[h][1].values == "DELISTING_FORCED_EXIT") & E.values)]
cells = [(i, j, h) for i, j in pick for h in F2.HS] + forced
bad3 = []
for i, j, h in cells:
    s = E.columns[j]; d = FF.DAYS[i].to_pydatetime()
    a = float(OUT[h][0].iat[i, j]); b = naive(s, d, h)
    if not same(a, b): bad3.append((s, str(d.date()), h))
rec("T3 independent naive outcome recompute (normal + every eligible forced exit)", not bad3,
    f"{len(cells)} outcomes ({len(forced)} forced exits); mismatches {len(bad3)} {bad3[:3]}")

# T4 forced exits used exactly where the cut falls inside (t, t+h), eligible entries
okc = True; counts = {}; LCV = F2.last_close(Hh).values
for h in F2.HS:
    n_ind = 0
    for s, r in fer.items():
        if s not in E.columns: continue
        cut = pd.Timestamp(r["cut_utc"], tz="UTC"); j = list(E.columns).index(s)
        for i in F2.ENTRY_IDX:
            d = FF.DAYS[i]
            if E.values[i, j] and d < cut < d + pd.Timedelta(days=h) and not np.isnan(LCV[i - 1, j] if i else np.nan):
                n_ind += 1
    n_code = int(((OUT[h][1].values == "DELISTING_FORCED_EXIT") & E.values).sum())
    counts[h] = (n_code, n_ind); okc &= n_code == n_ind
rec("T4 forced-exit count equals an independent recount for each h; no CUT_BEFORE_ENTRY among eligible entries",
    okc and int(sum(((OUT[h][1].values == "CUT_BEFORE_ENTRY") & E.values).sum() for h in F2.HS)) == 0, counts)

# T5 delisted coins are never dropped from outcomes or ICs
nonact = [c for c in E.columns if groups.get(c) != "active"]
have = int(sum((OUT[h][0][nonact].notna() & E[nonact]).values.sum() for h in F2.HS))
ic, n = dailies["P1"][("F03", 7)]
i = 300; m = E.values[i] & F["F03"].notna().values[i] & OUT[7][0].notna().values[i]
rec("T5 later-delisted series keep their outcomes; IC n_series counts them", have > 0 and n.iloc[i] == m.sum()
    and any(E.columns[k] in nonact for k in np.where(m)[0]), f"outcomes of later-delisted series: {have}")

# T6 IC equals scipy Spearman on eligible series
from scipy.stats import spearmanr
ok6 = True
for f, h in (("F07", 1), ("F15", 30), ("F20", 7), ("F16", 7)):
    ic, n = dailies["P1"][(f, h)]
    for i in (50, 250, 578):
        x, y = F[f].values[i], OUT[h][0].values[i]; m = E.values[i] & ~np.isnan(x) & ~np.isnan(y)
        ref = spearmanr(x[m], y[m]).statistic if m.sum() >= 20 else np.nan
        ok6 &= same(float(ic.iloc[i]), float(ref), 1e-9)
rec("T6 daily IC = scipy Spearman over series eligible on d", ok6)

# T7 Newey-West (independent double loop) and two-sided normal p
def nw_naive(x, L):
    x = [v for v in x if not math.isnan(v)]; Tn = len(x); m = sum(x) / Tn
    g = lambda l: sum((x[t] - m) * (x[t - l] - m) for t in range(l, Tn)) / Tn
    v = g(0) + 2 * sum((1 - l / (L + 1)) * g(l) for l in range(1, L + 1))
    t = m / math.sqrt(v / Tn)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return t, p
ok7 = True
P1 = C.set_index(["feature", "h_days"])
for f, h in (("F07", 1), ("F12", 7), ("F15", 30), ("F21", 30)):
    ic, _ = dailies["P1"][(f, h)]
    t, p = nw_naive(list(ic.iloc[F2.ENTRY_IDX].values), h - 1)
    ok7 &= same(P1.loc[(f, h), "nw_t"], t, 1e-9) and same(P1.loc[(f, h), "p_two_sided"], p, 1e-6) and P1.loc[(f, h), "nw_lag"] == h - 1
rec("T7 Newey-West t (Bartlett, lag h-1) and two-sided p equal an independent implementation", ok7)

# T8 BH / BY step-up from the definition (reject sets) on the 64 confirmatory p-values
def stepup(p, q, c=1.0):
    m = len(p); o = sorted(range(m), key=lambda k: p[k]); kmax = 0
    for r, k in enumerate(o, 1):
        if p[k] <= r * q / (m * c): kmax = r
    return set(o[:kmax])
cc = C[C.family == "CONFIRMATORY"].reset_index(drop=True); pv = list(cc.p_two_sided)
cm = sum(1 / i for i in range(1, 65))
ok8 = set(np.where(cc.bh_sig)[0]) == stepup(pv, 0.10) and set(np.where(cc.by_sig)[0]) == stepup(pv, 0.10, cm)
rr = np.random.default_rng(1).uniform(0, 0.05, 64)
ok8 &= set(np.where(F2.bh(rr) <= 0.1)[0]) == stepup(list(rr), 0.1) and set(np.where(F2.by(rr) <= 0.1)[0]) == stepup(list(rr), 0.1, cm)
def adj_naive(p, c=1.0):
    m = len(p); o = sorted(range(m), key=lambda k: p[k]); a = [0.0] * m
    for r in range(m):
        a[o[r]] = min(1.0, min(p[o[k]] * m * c / (k + 1) for k in range(r, m)))
    return a
for col, c in (("p_bh", 1.0), ("p_by", cm)):
    ok8 &= all(same(float(x), y, 1e-12) for x, y in zip(cc[col], adj_naive(pv, c)))
rec("T8 BH and BY (q = 0.10, same 64 p-values) equal the step-up definition; adjusted values equal an independent formula", ok8)

# T9 candidate rule (plan §4) re-derived independently; BY never changes it; labels
S = T.set_index(["scenario", "feature", "h_days"])["mean_ic"]
ok9 = True
for _, r in C.iterrows():
    sg = np.sign(r.mean_ic)
    subs = all(np.sign(r[f"sub{k}_mean_ic"]) == sg for k in (1, 2, 3))
    scen = np.sign(S.loc[("S50k", r.feature, r.h_days)]) == sg and np.sign(S.loc[("S250k", r.feature, r.h_days)]) == sg
    cand = r.family == "CONFIRMATORY" and r.p_bh <= 0.10 and subs and scen and sg != 0
    ok9 &= bool(cand) == bool(r.candidate)
    if cand:
        ok9 &= r.label == ("CANDIDATE" if r.p_by <= 0.10 else "CANDIDATE — BH_ONLY — FAILS_BY_SENSITIVITY")
rec("T9 candidates = BH & 3/3 sub-period signs & same sign in S50k and S250k; BH_ONLY label exactly where BY fails", ok9)

# T12 candidate rule on a synthetic table (data-independent: every branch of the rule is exercised)
Ts = T.copy()
Ts["p_two_sided"] = 0.9; Ts["mean_ic"] = 0.05
for k in (1, 2, 3): Ts[f"sub{k}_mean_ic"] = 0.05
def setc(f, h, **kw):
    for c, v in kw.items():
        sc = c.split("__")[0] if "__" in c else None
        col = c.split("__")[-1]
        m = (Ts.feature == f) & (Ts.h_days == h) & ((Ts.scenario == sc) if sc else True)
        Ts.loc[m, col] = v
setc("F03", 7, p_two_sided=1e-6)                                        # A: candidate, passes BY
setc("F07", 7, p_two_sided=1e-6, sub2_mean_ic=-0.01)                     # B: only 2 of 3 sub-periods
setc("F12", 7, p_two_sided=1e-6, S250k__mean_ic=-0.02)                   # C: S250k sign differs
setc("F15", 7, p_two_sided=0.004)                                       # D: BH passes, BY fails
setc("F01", 1, p_two_sided=1e-9)                                        # E: exploratory (never in BH, never candidate)
Cs = F2.classify(Ts).set_index(["feature", "h_days"])
exp = {("F03", 7): "CANDIDATE", ("F07", 7): "BH_SIGNIFICANT_NOT_STABLE", ("F12", 7): "BH_SIGNIFICANT_NOT_STABLE",
       ("F15", 7): "CANDIDATE — BH_ONLY — FAILS_BY_SENSITIVITY", ("F01", 1): "EXPLORATORY_SEEN_IN_FD1", ("F20", 30): "NOT_SIGNIFICANT"}
got = {k: Cs.loc[k, "label"] for k in exp}
rec("T12 synthetic table: 3/3 sub-periods, S50k AND S250k signs, BH rule, BY label and exploratory exclusion all enforced", got == exp, got if got != exp else "")

# T10 bootstrap: circular blocks of max(7, h) days, 2000 resamples, seed 20260108
ok10 = True
for f, h in (("F07", 1), ("F09", 30)):
    ic, _ = dailies["P1"][(f, h)]; x = ic.iloc[F2.ENTRY_IDX].values; x = x[~np.isnan(x)]; nn = len(x); B = max(7, h)
    rg = np.random.default_rng(20260108); nb = -(-nn // B)
    st = rg.integers(0, nn, size=(2000, nb))
    means = [np.mean([x[(st[r, b] + k) % nn] for b in range(nb) for k in range(B)][:nn]) for r in range(2000)]
    ok10 &= same(P1.loc[(f, h), "boot_ci95_low"], float(np.quantile(means, .025)), 1e-9) and same(P1.loc[(f, h), "boot_ci95_high"], float(np.quantile(means, .975)), 1e-9)
rec("T10 block bootstrap CI equals an independent loop (block = max(7, h))", ok10)

# T11 sub-periods partition the entry days
ok11 = all(int(r.sub1_days + r.sub2_days + r.sub3_days) == int(r.days_with_ic) for _, r in C.iterrows())
rec("T11 the 3 fixed sub-periods partition the days with an IC", ok11 and F2.SUBP[-1][1] == "2025-08-02")

n_pass = sum(r["pass"] for r in res)
summary = {"passed": n_pass, "of": len(res), "PASS": n_pass == len(res), "mode": "fast" if FAST else "full"}
if args:
    json.dump({"results": res, **summary}, open(args[0], "w"), indent=1)
print(json.dumps(summary))
