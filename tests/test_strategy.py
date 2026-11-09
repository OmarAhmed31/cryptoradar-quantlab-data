"""Acceptance tests SA1-SA6 (+SA8 fast) for Strategy Plan v0.1.3. Prints pass/fail only, never a return.
Validation is touched ONLY for schedule/guard checks (SA1): no Validation return is computed here.
python3 -I tests/test_strategy.py [--fast] [out.json]"""
import sys, json, math, csv, pathlib, datetime as dt, warnings
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import fd2 as F2
from lab import strategy as ST
from lab.segment_loader import GuardError, SegmentGuard, open_holdout
from scipy.stats import rankdata
warnings.filterwarnings("ignore")

FAST = "--fast" in sys.argv
args = [a for a in sys.argv[1:] if a != "--fast"]
res = []
def rec(name, ok, detail=""):
    res.append({"test": name, "pass": bool(ok), "detail": str(detail)}); print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
def same(a, b, tol=1e-9):
    if (a is None or (isinstance(a, float) and math.isnan(a))) and (b is None or (isinstance(b, float) and math.isnan(b))): return True
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-12)
UTC = dt.timezone.utc

inp = ST.dev_inputs()
days = FF.DAYS

# SA1 schedule, guard, isolation (Development and Validation; no Validation return computed)
rb = [days[i] for i in inp.rebal]
ok = all((b - a).days == 7 for a, b in zip(rb, rb[1:])) and rb[-1] < F2.ENTRY_END and rb[-1] + pd.Timedelta(days=7) <= FF.DEV_END
ok &= inp.tradeable(inp.rebal[0], "B", "P1").sum() >= 20 and inp.tradeable(inp.rebal[0] - 1, "B", "P1").sum() < 20
for g, t in ((SegmentGuard("development"), dt.datetime(2025, 8, 2, tzinfo=UTC)), (SegmentGuard("validation"), dt.datetime(2026, 3, 2, tzinfo=UTC))):
    try:
        g.check_outcome(t, dt.timedelta(days=7)); ok = False
    except GuardError:
        pass
try:
    open_holdout(); ok = False
except GuardError:
    pass
from lab import val as V
FF_DAYS, FF_ND = FF.DAYS, FF.ND
with V.validation_context():
    vr = [V.DAYS_X[i] for i in range(len(V.DAYS_X)) if V.V_ES <= V.DAYS_X[i] < V.V_EE][::7]
okv = len(vr) == 25 and str(vr[0].date()) == "2025-09-08" and str(vr[-1].date()) == "2026-02-23" and vr[-1] + pd.Timedelta(days=7) <= V.V_DE
rec("SA1 schedule every 7 days inside the entry windows (Dev start = first day with >= 20 B-tradeable coins; Val 25 weeks "
    "2025-09-08..2026-02-23), guard refusals, Holdout sealed", ok and okv and FF.DAYS is FF_DAYS, f"dev weeks {len(rb)}")

# SA4 Corwin-Schultz vs an independent pure-Python implementation
def cs_naive(s_idx, i):
    hi = inp.Hh["high"].iloc[:, s_idx].values[(i - 30) * 24:i * 24]; lo = inp.Hh["low"].iloc[:, s_idx].values[(i - 30) * 24:i * 24]
    Ss = []
    k = 3 - 2 * math.sqrt(2)
    for t in range(len(hi) - 1):
        if any(math.isnan(v) for v in (hi[t], hi[t + 1], lo[t], lo[t + 1])): continue
        b = math.log(hi[t] / lo[t]) ** 2 + math.log(hi[t + 1] / lo[t + 1]) ** 2
        g = math.log(max(hi[t], hi[t + 1]) / min(lo[t], lo[t + 1])) ** 2
        a = (math.sqrt(2 * b) - math.sqrt(b)) / k - math.sqrt(g / k)
        Ss.append(2 * (math.exp(a) - 1) / (1 + math.exp(a)))
    if len(Ss) < 360: return float("nan")
    return max(float(np.median(Ss)), 0.0) / 2
rng = np.random.default_rng(5); ok4 = True; n4 = 0
for i in (inp.rebal[0], inp.rebal[len(inp.rebal) // 2], inp.rebal[-1]):
    hs = inp.hs(i)
    for j in rng.choice(inp.nS, size=25 if FAST else 60, replace=False):
        ok4 &= same(float(hs[j]), cs_naive(j, i), 1e-12); n4 += 1
allhs = np.concatenate([inp.hs(i) for i in inp.rebal])
rec("SA4 Corwin-Schultz half-spread equals an independent implementation; never negative; fee constants 0.10 % / 0.20 %",
    ok4 and np.nanmin(allhs) >= 0 and ST.FEES["fee_0.10"] == 0.001 and ST.FEES["fee_0.20"] == 0.002 and ST.FEES["gross"] is None, f"{n4} coin-days")

# SA2 destructive overwrite: everything decided at d is unchanged after corrupting candles >= d
dsel = [inp.rebal[10]] if FAST else [inp.rebal[10], inp.rebal[40]]
bad = 0
for i in dsel:
    d = days[i]; H2 = {}
    for k, df in inp.Hh.items():
        x = df.copy(); fut = x.index >= d
        x.loc[fut] = x.loc[fut].notna() * np.random.default_rng(1).uniform(1e-3, 1e3, size=x.loc[fut].shape)
        H2[k] = x.where(~(fut[:, None] & (x == 0)))
    F2_ = FF.features(H2, inp.U["P1"])
    inp2 = ST.Inputs(H2, inp.U, pd.read_csv(FF.PACK / "groups.csv").set_index("series")["group"], inp.fe.reset_index().set_index("series"),
                     F2_, SegmentGuard("development"), FF.DAYS[0], F2.ENTRY_END, FF.DEV_END, "first_20_B")
    for kind, N in (("A", 10), ("A", 20), ("B", 10), ("B", 20), ("B1", 0), ("B2", 1)):
        bad += int(not np.array_equal(ST.select(inp, i, kind, N, "P1"), ST.select(inp2, i, kind, N, "P1")))
    a, b = inp.hs(i), inp2.hs(i); bad += int(not np.array_equal(np.isnan(a), np.isnan(b)) or not np.allclose(a[~np.isnan(a)], b[~np.isnan(b)], rtol=0, atol=0))
    a, b = inp.ref(i), inp2.ref(i); bad += int(not np.array_equal(np.isnan(a), np.isnan(b)) or not (a[~np.isnan(a)] == b[~np.isnan(b)]).all())
rec("SA2 destructive overwrite of candles >= d: selections (4 variants, B1, B2), half-spreads and reference prices at d unchanged", bad == 0, f"days {[str(days[i].date()) for i in dsel]}")

# SA3 / SA5 independent naive simulator (strategy variants with cap, B1, B2), compared week by week
fer = {}
with open(F2.PACK2 / "forced_exit_dev.csv") as fh:
    for x in csv.DictReader(fh): fer[x["series"]] = x
S = inp.S
def naive_scores(i, kind):
    e = inp.M["P1"].values[i]
    def pr(vals):
        out = np.full(len(vals), np.nan); m = ~np.isnan(vals)
        out[m] = rankdata(vals[m]) / m.sum(); return out
    if kind == "A":
        return pr(np.where(e, -FF_features["F07"].values[i], np.nan))
    parts = [pr(np.where(e, sg * FF_features[f].values[i], np.nan)) for f, sg in (("F07", -1), ("F10", -1), ("F20", 1), ("F21", -1))]
    P = np.vstack(parts); return np.where(np.isnan(P).any(0), np.nan, P.mean(0))
FF_features = inp.F
def naive_sim(kind, N, C, fee, nweeks):
    lc = F2.last_close(inp.Hh).values; q = {}; mark = {}; hsb = {}; cash = C; out = []
    for w, i in enumerate(inp.rebal[:nweeks]):
        d = days[i]; ref = lc[i - 1]; hs = inp_hs_naive(i)
        e = inp.M["P1"].values[i]; dv = inp.U["P1"]["DV30_med"].values[i].astype(float)
        V0 = cash + sum(q[j] * mark[j] for j in q)
        if kind == "B2" and w > 0:
            tgt = {j: q[j] * mark[j] for j in q}; fees = spc = 0.0
        else:
            if kind == "B2":
                j0 = S.index("BTC-USDT"); sel = [j0] if not (math.isnan(ref[j0]) or math.isnan(hs[j0])) else []; n = 1
            else:
                trad = [j for j in range(len(S)) if e[j] and not math.isnan(ref[j]) and not math.isnan(hs[j]) and not math.isnan(dv[j])]
                if kind == "B1":
                    sel = trad; n = max(len(sel), 1)
                else:
                    sc = naive_scores(i, kind); trad = [j for j in trad if not math.isnan(sc[j])]
                    sel = sorted(trad, key=lambda j: (-sc[j], S[j]))[:N]; n = N
            H = {j: q[j] * mark[j] for j in q}; k = 1.0
            for _ in range(60):
                tgt = {j: min(k * V0 / n, 0.01 * dv[j]) for j in sel}
                cost = sum(abs(tgt.get(j, 0) - H.get(j, 0)) * (fee + (hs[j] if not math.isnan(hs[j]) else hsb.get(j, 0))) for j in set(tgt) | set(H))
                k = (V0 - cost) / V0
            fees = sum(abs(tgt.get(j, 0) - H.get(j, 0)) * fee for j in set(tgt) | set(H))
            spc = sum(abs(tgt.get(j, 0) - H.get(j, 0)) * (hs[j] if not math.isnan(hs[j]) else hsb.get(j, 0)) for j in set(tgt) | set(H))
            cash = V0 - sum(tgt.values()) - fees - spc
            q = {j: v / ref[j] for j, v in tgt.items()}
            for j in tgt: hsb[j] = hs[j]
        end = d + pd.Timedelta(days=7); ev = 0.0; mk = {}
        for j in list(q):
            r = fer.get(S[j])
            if r is not None:
                cut = pd.Timestamp(r["cut_utc"], tz="UTC")
                if d < cut < end:
                    cash += q[j] * float(r["last_trade_price"]) * (1 - fee - hsb[j]); del q[j]; continue
            px = lc[i + 6, j]
            if math.isnan(px):
                win = [v for v in lc[i:i + 7, j] if not math.isnan(v)]; px = win[-1] if win else ref[j]
            mk[j] = px; ev += q[j] * px
        mark = mk
        out.append((cash + ev) / V0 - 1)
    return out
_hsn = {}
def inp_hs_naive(i):
    if i not in _hsn:
        _hsn[i] = np.array([cs_naive(j, i) for j in range(len(S))])
    return _hsn[i]
nw = 14 if FAST else len(inp.rebal)                                   # B1 has its first forced exit in week 10
ok3 = True; det = []
for kind, N, C, fee in (("B", 10, 10_000.0, 0.001), ("A", 20, 100_000.0, 0.002), ("B1", 0, 10_000.0, 0.001), ("B2", 1, 1_000.0, 0.001)):
    inp._mark = {}
    got = ST.simulate(inp, kind, N, C, fee, "P1").ret.values[:nw - 1]       # the last code week liquidates; compare earlier weeks
    exp = naive_sim(kind, N, C, fee, nw)[:nw - 1]
    m = all(same(float(a), float(b), 1e-9) for a, b in zip(got, exp)); ok3 &= m; det.append((kind, N, int(C), m))
rec("SA3/SA5 independent naive simulator (selection, 1 % cap, costs, forced exits, marks) = code, weekly returns, incl. B1 and B2", ok3, det)

# SA6 selection rule and gate on synthetic tables
rows = []
for p, ex, to in (("A_N10", 0.002, 0.5), ("A_N20", 0.003, 0.4), ("B_N10", 0.003, 0.3), ("B_N20", 0.003, 0.3)):
    rows.append({"scenario": "P1", "capital": 10_000.0, "fee": "fee_0.10", "portfolio": p, "mean_excess_vs_B1": ex, "mean_turnover": to})
rows.append({"scenario": "P1", "capital": 1_000.0, "fee": "fee_0.10", "portfolio": "A_N10", "mean_excess_vs_B1": 0.9, "mean_turnover": 0.1})
rows.append({"scenario": "S50k", "capital": 10_000.0, "fee": "fee_0.10", "portfolio": "A_N10", "mean_excess_vs_B1": 0.9, "mean_turnover": 0.1})
rows.append({"scenario": "P1", "capital": 10_000.0, "fee": "fee_0.20", "portfolio": "A_N10", "mean_excess_vs_B1": 0.9, "mean_turnover": 0.1})
c1 = ST.choose(pd.DataFrame(rows), 10_000.0)
G = pd.DataFrame([
    {"scenario": "P1", "capital": 10_000.0, "portfolio": "X", "fee": "fee_0.10", "p_nw_one_sided": 0.01, "p_boot_one_sided": 0.02, "mean_excess_vs_B1": 0.004, "total_net_return": -0.1},
    {"scenario": "P1", "capital": 10_000.0, "portfolio": "X", "fee": "fee_0.20", "p_nw_one_sided": 0.2, "p_boot_one_sided": 0.2, "mean_excess_vs_B1": 0.001, "total_net_return": -0.2},
    {"scenario": "P1", "capital": 1_000.0, "portfolio": "X", "fee": "fee_0.10", "p_nw_one_sided": 0.01, "p_boot_one_sided": 0.07, "mean_excess_vs_B1": 0.004, "total_net_return": 0.1},
    {"scenario": "P1", "capital": 1_000.0, "portfolio": "X", "fee": "fee_0.20", "p_nw_one_sided": 0.2, "p_boot_one_sided": 0.2, "mean_excess_vs_B1": 0.001, "total_net_return": 0.0},
    {"scenario": "P1", "capital": 100_000.0, "portfolio": "X", "fee": "fee_0.10", "p_nw_one_sided": 0.01, "p_boot_one_sided": 0.01, "mean_excess_vs_B1": 0.004, "total_net_return": 0.2},
    {"scenario": "P1", "capital": 100_000.0, "portfolio": "X", "fee": "fee_0.20", "p_nw_one_sided": 0.01, "p_boot_one_sided": 0.01, "mean_excess_vs_B1": -0.001, "total_net_return": 0.1}])
g = ST.gate(G, "X", (10_000.0, 1_000.0, 100_000.0))
ok6 = c1 == "B_N10" and g["10000"]["PASS"] and g["10000"]["flag"] == "RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE" \
      and not g["1000"]["PASS"] and not g["100000"]["PASS"] and g["1000"]["flag"] == ""
rec("SA6 synthetic: selection (P1, gating capital, fee 0.10 %; tie -> lower turnover -> Top 10); gate needs both p <= 0.05 "
    "and mean > 0 at 0.20 %; RELATIVE_ONLY flag", ok6, (c1, {k: v["PASS"] for k, v in g.items()}))

# SA6b statistics against independent formulas
x = np.random.default_rng(3).normal(0.001, 0.02, 40)
t, p = ST.nw_one_sided(x)
from scipy.stats import norm
tn = x.mean() / math.sqrt(((x - x.mean()) ** 2).sum() / len(x) / len(x))
pb, lo, hi = ST.boot_one_sided(x)
r2 = np.random.default_rng(ST.SEED); st = r2.integers(0, len(x), size=(2000, len(x))); mb = x[st].mean(1)
rec("SA6b one-sided Newey-West (lag 0) and 1-week-block bootstrap p equal independent formulas",
    same(t, tn) and same(p, float(norm.sf(tn)), 1e-9) and same(pb, float((mb <= 0).mean()), 1e-12))

n_pass = sum(r["pass"] for r in res)
summary = {"passed": n_pass, "of": len(res), "PASS": n_pass == len(res), "mode": "fast" if FAST else "full"}
if args:
    json.dump({"results": res, **summary}, open(args[0], "w"), indent=1)
print(json.dumps(summary))
