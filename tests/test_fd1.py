"""Acceptance tests for FD-1 (plan v0.1.1 §6: FA1, FA2, FA3, FA6 + checks of Q3/Q4/Q6/Q7). Development only.
python3 -I tests/test_fd1.py [--fast] [out.json]
--fast: FA1 on 4 days, FA3 on 300 rows (reviewer mode). Default: FA1 on 8 days, FA3 on 1000 rows."""
import sys, json, math, gzip, csv, hashlib, pathlib, statistics, datetime as dt, warnings
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import fd1 as FD
from lab.segment_loader import GuardError
warnings.filterwarnings("ignore")

FAST = "--fast" in sys.argv
args = [a for a in sys.argv[1:] if a != "--fast"]
res = []
def rec(name, ok, detail=""):
    res.append({"test": name, "pass": bool(ok), "detail": str(detail)}); print(("PASS " if ok else "FAIL ") + name, detail, flush=True)

def same(a, b):
    if (a is None or (isinstance(a, float) and math.isnan(a))) and (b is None or (isinstance(b, float) and math.isnan(b))):
        return True
    if a is None or b is None or math.isnan(a) or math.isnan(b):
        return False
    return abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1e-12)

# FA0 catalogue frozen before the run
CAT_SHA = "c51334e2bbb55ed1d1cfd21cd6350966a93992cae2552e640df5649682024024"
rec("FA0 feature catalogue is the one hashed before any feature was computed", hashlib.sha256(FF.CATALOGUE.read_bytes()).hexdigest() == CAT_SHA)
try:
    FF.catalogue(); rec("FA0 code names and lookbacks equal the catalogue", True)
except AssertionError as e:
    rec("FA0 code names and lookbacks equal the catalogue", False, e)

Hh, U, groups = FF.load_pack()
F = FF.features(Hh, U["P1"])
M = FD.masks(U, groups)

# FA1 destructive future overwrite
rng = np.random.default_rng(11)
days = ["2024-03-15", "2024-08-01", "2025-01-20", "2025-08-01"] if FAST else \
       ["2024-02-20", "2024-03-15", "2024-06-30", "2024-08-01", "2024-11-11", "2025-01-20", "2025-05-05", "2025-08-01"]
bad = checked = 0
for ds in days:
    d = pd.Timestamp(ds, tz="UTC")
    H2 = {}
    for k, df in Hh.items():
        x = df.copy(); fut = x.index >= d                                   # every candle starting at or after d
        x.loc[fut] = x.loc[fut].notna() * rng.uniform(1e-3, 1e3, size=x.loc[fut].shape)
        H2[k] = x.where(~(fut[:, None] & (x == 0)))
    U2 = {}
    for k, u in U.items():
        U2[k] = {}
        for c, v in u.items():
            y = v.copy(); m = y.index > d                                   # universe rows after d (day d's own row is past-only)
            y.loc[m] = (rng.random(y.loc[m].shape) < 0.5) if y.dtypes.iloc[0] == bool else rng.uniform(0, 1e7, size=y.loc[m].shape)
            U2[k][c] = y
    F2 = FF.features(H2, U2["P1"]); M2 = FD.masks(U2, groups)
    upto = F["F01"].index <= d
    for sc in M:
        a_m, b_m = M[sc].loc[upto].values, M2[sc].loc[upto].values
        checked += a_m.size; bad += int((a_m != b_m).sum())
        for f in FF.NAMES:
            a = F[f].where(M[sc]).loc[upto].values; b = F2[f].where(M2[sc]).loc[upto].values
            eq = (np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= 1e-12 * np.maximum(1, np.abs(a)))
            checked += eq.size; bad += int((~eq).sum())
rec("FA1 destructive future overwrite: every feature and eligibility mask at days <= d unchanged (22 features x 6 masks)",
    bad == 0, f"{checked - bad}/{checked} values, days {days}")

# FA2 guard
try:
    G = {k: v.copy() for k, v in F.items()}; G["F04"].iloc[10, 0] = 1.0; FF.guard(G); rec("FA2 a value before its window is complete is refused", False)
except GuardError:
    rec("FA2 a value before its window is complete is refused", True)
try:
    H3 = {k: v.copy() for k, v in Hh.items()}
    H3["close"].loc[pd.Timestamp("2025-09-10", tz="UTC")] = 1.0
    FF.assert_dev_only(H3); rec("FA2 a Validation candle in FD input is refused", False)
except GuardError:
    rec("FA2 a Validation candle in FD input is refused", True)
try:
    FF.GUARD.check_research_statistic(pd.Timestamp("2025-10-01", tz="UTC").to_pydatetime(), []); rec("FA2 FD statistic on a Validation day refused", False)
except GuardError:
    rec("FA2 FD statistic on a Validation day refused", True)
rec("FA2 every feature day is a Development day", all((v.index >= FF.DEV_START).all() and (v.index < FF.DEV_END).all() for v in F.values()))

# FA3 independent naive per-row recompute (pure Python from the pack CSV files)
DAY = dt.timedelta(days=1); START = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
cache = {}
def rows(s):
    if s not in cache:
        with gzip.open(FF.PACK / "hourly" / f"{s}.csv.gz", "rt") as fh:
            r = list(csv.DictReader(fh))
        out = []
        for x in r:
            t = dt.datetime.fromtimestamp(int(x["ts_utc_ms"]) / 1000, dt.timezone.utc)
            out.append((t, float(x["high"]), float(x["low"]), float(x["close"]), float(x["vol_quote"]), float(x["traded_minutes"])))
        lr, prev = [], None
        for t, h, l, c, v, m in out:
            lr.append((t, None if prev is None else math.log(c) - math.log(prev))); prev = c
        byday = {}
        for t, h, l, c, v, m in out:
            byday.setdefault(t.date(), []).append((t, h, l, c, v, m))
        cache[s] = (out, lr, byday)
    return cache[s]
univ = {}
with gzip.open(FF.PACK / "universe" / FF.SCEN["P1"], "rt") as fh:
    for x in csv.DictReader(fh):
        univ[(x["series"], x["day"])] = x

def naive(s, d):
    out, lr, byday = rows(s)
    nan = float("nan")
    def lc(day):
        if day < START or day.date() not in byday: return None
        return byday[day.date()][-1][3]
    def ca(day):
        return lc(day - DAY)
    def ret(a, b):
        return nan if a is None or b is None else a / b - 1
    def win(w):
        return [(t, h, l, c, v, m) for t, h, l, c, v, m in out if d - w * DAY <= t < d]
    def lrw(w):
        return [x for t, x in lr if d - w * DAY <= t < d and x is not None]
    r = {}
    r["F01"] = ret(ca(d), ca(d - DAY)) if d - 2 * DAY >= START else nan
    r["F02"] = ret(ca(d), ca(d - 7 * DAY)) if d - 8 * DAY >= START else nan
    r["F03"] = ret(ca(d), ca(d - 30 * DAY)) if d - 31 * DAY >= START else nan
    r["F04"] = ret(ca(d - 7 * DAY), ca(d - 37 * DAY)) if d - 38 * DAY >= START else nan
    for w, f, fx in ((7, "F06", "F11"), (30, "F07", None)):
        x = lrw(w) if d - w * DAY >= START else []
        ok = len(x) >= 0.5 * 24 * w
        r[f] = statistics.stdev(x) if ok else nan
        if fx: r[fx] = max(x) if ok else nan
        if w == 30:
            r["F09"] = math.sqrt(sum(min(v, 0) ** 2 for v in x) / len(x)) if ok else nan
            if ok:
                n = len(x); m = sum(x) / n; m2 = sum((v - m) ** 2 for v in x) / n; m3 = sum((v - m) ** 3 for v in x) / n
                r["F10"] = (m3 / m2 ** 1.5) * math.sqrt(n * (n - 1)) / (n - 2) if m2 > 0 else nan
            else:
                r["F10"] = nan
            c30 = win(30) if d - 30 * DAY >= START else []
            ok2 = len(c30) >= 360
            r["F20"] = ca(d) / max(z[1] for z in c30) - 1 if ok2 and ca(d) is not None else nan
            r["F21"] = ca(d) / min(z[2] for z in c30) - 1 if ok2 and ca(d) is not None else nan
    r["F08"] = r["F06"] / r["F07"] if not (math.isnan(r["F06"]) or math.isnan(r["F07"])) else nan
    # market relation
    if s == FF.BTC:
        r["F12"] = r["F13"] = r["F14"] = r["F05"] = nan
    else:
        bo, blr, bday = rows(FF.BTC)
        def blc(day):
            if day < START or day.date() not in bday: return None
            return bday[day.date()][-1][3]
        xs, ys = [], []
        for j in range(29, -1, -1):
            x0 = d - j * DAY
            if x0 < START: continue
            y = ret(ca(x0), ca(x0 - DAY)); b = ret(blc(x0 - DAY), blc(x0 - 2 * DAY))
            if not (math.isnan(y) or math.isnan(b)): xs.append(b); ys.append(y)
        n = len(xs)
        if n >= 20:
            mx, my = sum(xs) / n, sum(ys) / n
            sxx = sum((a - mx) ** 2 for a in xs); syy = sum((a - my) ** 2 for a in ys); sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
            if sxx > 0:
                beta = sxy / sxx
                r["F12"] = beta; r["F13"] = sxy / math.sqrt(sxx * syy) if syy > 0 else nan
                r["F14"] = math.sqrt(sum((b - (my + beta * (a - mx))) ** 2 for a, b in zip(xs, ys)) / (n - 2))
            else:
                r["F12"] = r["F13"] = r["F14"] = nan
        else:
            r["F12"] = r["F13"] = r["F14"] = nan
        btc30 = ret(blc(d - DAY), blc(d - 31 * DAY)) if d - 31 * DAY >= START else nan
        r["F05"] = r["F03"] - r["F12"] * btc30
    u = univ.get((s, d.strftime("%Y-%m-%d")))
    ass = u is not None and u["assessable"] == "True"
    dvv = float(u["DV30_med"]) if ass and u["DV30_med"] != "" else nan
    r["F15"] = math.log(dvv) if ass and dvv > 0 else nan
    r["F16"] = float(u["THR30"]) if ass and u["THR30"] != "" else nan
    def dq(day):
        return sum(z[4] for z in byday[day.date()]) if day.date() in byday else None
    if d - 30 * DAY >= START:
        q7 = [dq(d - j * DAY) for j in range(1, 8)]; q7 = [q for q in q7 if q is not None]
        q30 = [dq(d - j * DAY) for j in range(1, 31)]; q30 = [q for q in q30 if q is not None]
        r["F17"] = statistics.median(q7) / statistics.median(q30) if len(q7) >= 4 and len(q30) >= 15 else nan
        am = []
        for j in range(1, 31):
            day = d - j * DAY
            a, b, q = lc(day), lc(day - DAY), dq(day)
            if a is not None and b is not None and q is not None:
                am.append(abs(math.log(a / b)) / q)
        r["F18"] = statistics.median(am) if len(am) >= 15 else nan
    else:
        r["F17"] = r["F18"] = nan
    if d - 7 * DAY >= START:
        r["F19"] = sum(z[5] for z in win(7)) / 10080
        rg = []
        for j in range(1, 8):
            day = d - j * DAY
            if day.date() in byday:
                z = byday[day.date()]; rg.append((max(q[1] for q in z) - min(q[2] for q in z)) / z[-1][3])
        r["F22"] = sum(rg) / len(rg) if len(rg) >= 4 else nan
    else:
        r["F19"] = r["F22"] = nan
    return r

E = M["P1"]
pos = np.argwhere(E.values)
pick = pos[np.random.default_rng(7).choice(len(pos), size=300 if FAST else 1000, replace=False)]
bad3 = []
for i, j in pick:
    d = FF.DAYS[i].to_pydatetime(); s = E.columns[j]
    nv = naive(s, d)
    for f in FF.NAMES:
        a = float(F[f].iat[i, j])
        if not same(a, nv[f]):
            bad3.append((s, str(d.date()), f, a, nv[f]))
rec("FA3 independent naive recompute of all 22 features (relative 1e-9)", not bad3,
    f"{len(pick)} series-days x 22 = {len(pick) * 22} values; mismatches {len(bad3)} {bad3[:3]}")

# Q3/Q4/Q6/Q7 checks against independent recomputation
from scipy.stats import spearmanr
res_p1 = {"q1": FD.q1(F, E)}
q3t, q3daily = FD.q3(F, E)
ok = True; det = []
for f, k in (("F07", 1), ("F15", 7), ("F02", 7)):
    ser = [x for x in q3daily if x.name == (f, k)][0]
    X = F[f].where(E)
    for i in (100, 400, 600 - k):
        a, b = X.iloc[i].values, X.iloc[i + k].values; m = ~np.isnan(a) & ~np.isnan(b)
        ref = spearmanr(a[m], b[m]).statistic if m.sum() >= 20 else np.nan
        got = ser.iloc[i]
        ok &= same(float(got), float(ref)); det.append((f, k, i, round(float(got), 6), round(float(ref), 6)))
pairs_ok = all(r["day_pairs"] == FF.ND - r["k_days"] and r["last_pair"] == f"{FF.DAYS[-1 - r['k_days']].date()}->{FF.DAYS[-1].date()}" for _, r in q3t.iterrows())
rec("FQ3 persistence equals scipy Spearman on both-days-eligible series; d+k never leaves Development", ok and pairs_ok, det[:3])
R, cl, per_day = FD.q4(F, E)
i = 300; e = E.values[i]
a, b = F["F06"].values[i][e], F["F11"].values[i][e]; m = ~np.isnan(a) & ~np.isnan(b)
rec("FQ4 redundancy cell equals scipy Spearman for a sample day", same(float(per_day[i, 5, 10]), float(spearmanr(a[m], b[m]).statistic)))
lab = FD.load_regimes("P1")
reg = pd.read_csv(FD.REG / "regimes_asof_P1.csv")
indep = dict(zip(reg["day"], reg["regime_asof"]))
q6 = FD.q6(F, E, lab)
okm = True
for f in ("F03", "F13", "F19"):
    vals = {}
    for i, dday in enumerate(FF.DAYS):
        if dday < FD.LABEL_START: continue
        x = F[f].values[i][E.values[i]]; x = x[~np.isnan(x)]
        if len(x) >= 20:
            vals.setdefault(indep[dday.strftime("%Y-%m-%d")], []).append(float(np.median(x)))
    for s in FD.STATES:
        got = q6[(q6.feature == f) & (q6.state == s)]["mean_of_daily_median"].iloc[0]
        okm &= same(float(got), float(np.mean(vals[s])))
rec("FQ6 regime means equal an independent recompute from the regimes_asof file", okm)
idx = FD.boot_index(427, np.random.default_rng(FD.SEED))
blocks_ok = all(((idx[:, b * 7 + 1:(b + 1) * 7] - idx[:, b * 7:(b + 1) * 7 - 1]) % 427 == 1).all() for b in range(427 // 7))
rec("FQ6 bootstrap = circular blocks of 7 consecutive days on the full series (labels travel with days)",
    blocks_ok and idx.shape == (2000, 427) and idx.min() >= 0 and idx.max() < 427)
low = q6[q6.LOW_N]
rec("FQ6 LOW_N states carry no CI; S3 is LOW_N in P1", low["ci95_low"].isna().all() and low["ci95_high"].isna().all()
    and set(low.state) == {"S3"} and (q6[q6.state == "S3"].n_labelled_days == 19).all())
nonactive = [c for c in E.columns if groups.get(c) != "active"]
rec("FQ7 survivors masks hold no later-delisted series", all(not M[k + "_survivors_only"][nonactive].values.any() for k in FF.SCEN)
    and all(M[k + "_survivors_only"].values.sum() < M[k].values.sum() for k in FF.SCEN))

n_pass = sum(r["pass"] for r in res)
summary = {"passed": n_pass, "of": len(res), "PASS": n_pass == len(res), "mode": "fast" if FAST else "full"}
if args:
    json.dump({"results": res, **summary}, open(args[0], "w"), indent=1)
print(json.dumps(summary))
