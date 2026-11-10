"""Pre-run tests for lab/exp3_counts.py (plan EXP3 v0.3 + addendum v0.1). SYNTHETIC data only (and the frozen
thresholds file for its exact values); NO real count is computed here. The one real run + RD4 is tests/run_exp3_once.py.
python3 -I tests/test_exp3.py [out.json]   -> exit code 1 if any test fails"""
import sys, ast, json, gzip, math, random, bisect, hashlib, tempfile, pathlib, itertools
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import exp3_counts as E

REPO = pathlib.Path(__file__).resolve().parents[1]
res = []
def rec(name, ok, detail=""):
    res.append({"test": name, "pass": bool(ok), "detail": str(detail)[:400]}); print(("PASS " if ok else "FAIL ") + name, str(detail)[:200], flush=True)
TS = lambda s: pd.Timestamp(s, tz="UTC")
H = pd.Timedelta(hours=1)

# ------------------------------------------------------------ synthetic pack (random; NOT market data)
def make_pack(root, seed=7, ncoins=24):
    rng = np.random.default_rng(seed); root = pathlib.Path(root)
    (root / "hourly").mkdir(parents=True); (root / "universe").mkdir()
    grid = pd.date_range(FF.DEV_START, FF.DEV_END - pd.Timedelta(hours=1), freq="h")
    names = ["BTC-USDT", "USDC-USDT"] + [f"C{i:02d}-USDT" for i in range(ncoins - 2)] + ["PAXG-USDT", "XAUT-USDT"]
    rng_x = None
    for k, s in enumerate(names):
        if s in ("PAXG-USDT", "XAUT-USDT"):            # excluded series = exact copies of signal-rich coins
            src = root / "hourly" / f"C{1 if s == 'PAXG-USDT' else 8:02d}-USDT.csv.gz"
            (root / "hourly" / f"{s}.csv.gz").write_bytes(src.read_bytes()); continue
        vol = rng.uniform(0.004, 0.012)
        lr = rng.normal(0, vol, len(grid))
        # quiet stretches followed by bursts, so that tight ranges, breakouts and volume spikes all occur
        quiet = (np.sin(np.arange(len(grid)) / (300 + 23 * k)) > 0.6)
        lr = np.where(quiet, lr * 0.25, lr) + np.where(rng.random(len(grid)) < 0.002, rng.uniform(0.03, 0.08, len(grid)), 0)
        if s == "USDC-USDT": lr = rng.normal(0, 0.0002, len(grid))
        c = 100 * np.exp(np.cumsum(lr)); o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, vol / 4, len(grid)))
        h = np.maximum(o, c) * (1 + rng.uniform(0, vol, len(grid))); l = np.minimum(o, c) * (1 - rng.uniform(0, vol, len(grid)))
        vq = rng.lognormal(10, 0.6, len(grid)) * np.where(rng.random(len(grid)) < 0.03, rng.uniform(5, 25, len(grid)), 1)
        keep = rng.random(len(grid)) > 0.04
        if s == "C03-USDT": keep &= grid < TS("2025-03-10 08:00")                       # delisted (ledger: PRICED)
        if s == "C04-USDT": keep &= grid < TS("2024-11-20 08:00")                       # delisted (ledger: unpriceable)
        if s == "C05-USDT": keep &= ~((grid >= TS("2025-01-05")) & (grid < TS("2025-02-20")))   # 46-day trading gap
        df = pd.DataFrame({"ts_utc_ms": grid.as_unit("ms").asi8[keep], "open": o[keep], "high": h[keep], "low": l[keep],
                           "close": c[keep], "vol_base": (vq / c)[keep], "vol_quote": vq[keep],
                           "traded_minutes": rng.integers(1, 61, len(grid))[keep]})
        with gzip.open(root / "hourly" / f"{s}.csv.gz", "wt") as fh: df.to_csv(fh, index=False)
    pd.DataFrame([(s, "active") for s in names], columns=["series", "group"]).to_csv(root / "groups.csv", index=False)
    days = pd.date_range(FF.DEV_START, FF.DEV_END - pd.Timedelta(days=1), freq="D")
    rows = [(s, "active", d.strftime("%Y-%m-%d"), i >= 30, 1.0, 1e6, i >= 31 and not (s == "C06-USDT" and 300 <= i < 330))
            for s in names for i, d in enumerate(days)]
    U = pd.DataFrame(rows, columns=["series", "group", "day", "assessable", "THR30", "DV30_med", "eligible"])
    for f in FF.SCEN.values():
        with gzip.open(root / "universe" / f, "wt") as fh: U.to_csv(fh, index=False)
    (root / "PACK_MANIFEST.json").write_text(json.dumps({"synthetic": True, "seed": seed}))
    pd.DataFrame([("C03-USDT", "syn", "2025-03-10 08:00", "stated_time", "", "", 1.23, 1, "PRICED", 60),
                  ("C04-USDT", "syn", "2024-11-20 08:00", "stated_time", "", "", 4.56, 900, "UNPRICEABLE_FORCED_EXIT", 60)],
                 columns=["series", "dataset", "cut_utc", "cutoff_precision", "window_end_utc", "last_traded_minute_utc",
                          "last_trade_price", "minutes_last_trade_to_cut", "status", "max_stale_minutes_rule"]).to_csv(root / "ledger.csv", index=False)
    return root

tmp = pathlib.Path(tempfile.mkdtemp(prefix="exp3_syn_"))
pack = make_pack(tmp / "pack")
real_T = json.loads((REPO / E.THR_FILE).read_bytes())
synT = dict(real_T); synT["thresholds"] = dict(real_T["thresholds"], E3_rvol_P75=2.5, E4_clv_median=0.6, E5_stop_P90=0.15)
thr_syn = tmp / "thr.json"; thr_syn.write_bytes(json.dumps(synT).encode())
E.THR_SHA = hashlib.sha256(thr_syn.read_bytes()).hexdigest()       # synthetic thresholds for the synthetic pack only
T = synT["thresholds"]

# ------------------------------------------------------------ X1 imports and ledger columns
ALLOWED = {"sys", "json", "bisect", "hashlib", "pathlib", "math", "numpy", "pandas", "lab.fd_features", "lab.thresholds",
           "lab.segment_loader", "lab.universe_crypto_only"}
src = (REPO / "lab/exp3_counts.py").read_text(); tree = ast.parse(src); imps = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import): imps |= {a.name for a in n.names}
    if isinstance(n, ast.ImportFrom): imps |= {f"{n.module}.{a.name}" if n.module == "lab" else n.module for a in n.names}
strs = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
rec("X1a imports allowed only", imps <= ALLOWED, sorted(imps - ALLOWED))
rec("X1b no validation/holdout segment named", not ({"validation", "holdout"} & strs), "")
_orig = pd.read_csv; seen = {}
def spy(p, *a, **k):
    if str(p).endswith("ledger.csv"): seen["usecols"] = k.get("usecols")
    return _orig(p, *a, **k)
pd.read_csv = spy; led = E.load_ledger(pack / "ledger.csv"); pd.read_csv = _orig
rec("X1c ledger read without its price column", seen.get("usecols") is not None and "last_trade_price" not in seen["usecols"], seen)
rec("X1d ledger status", led["C03-USDT"] == (TS("2025-03-10 08:00"), True) and led["C04-USDT"][1] is False, led)

# ------------------------------------------------------------ X2 frozen thresholds: exact values, sha enforced
sha_keep = E.THR_SHA; E.THR_SHA = "5dc38aa95599526c17ad42fc98aa37a87abdb10d84e071eb959805fd11758c5f"
Texact = E.load_thresholds(REPO / E.THR_FILE)
rec("X2a exact floats from thresholds.json", all(Texact[k] == real_T["thresholds"][k] for k in real_T["thresholds"]), Texact["E3_rvol_P75"])
bad = tmp / "bad.json"; bad.write_bytes((REPO / E.THR_FILE).read_bytes().replace(b"7.96", b"7.97"))
try: E.load_thresholds(bad); ok = False
except SystemExit: ok = True
rec("X2b modified thresholds file refused", ok)
rec("X2c the source pins the frozen sha", "5dc38aa95599526c17ad42fc98aa37a87abdb10d84e071eb959805fd11758c5f" in src)
E.THR_SHA = sha_keep

# ------------------------------------------------------------ full synthetic run
R = E.run(pack, thr_syn, pack / "ledger.csv")
Hh, U, groups = FF.load_pack(pack)
C = Hh["close"]; cols = list(C.columns); grid = C.index
seg = E.SEGMENTS["development"]
for d in ("D-H1", "D-H2", "D-D1"):
    print(d, R["designs"][d]["cascade"], R["designs"][d]["execution"], R["designs"][d]["L_greedy"], R["designs"][d]["L_worst"])

# ------------------------------------------------------------ X3 trend / Transition (independent loop)
ret, _, _ = E.TH.ew_index(Hh, U, groups); st = E.TH.states(ret)
trend, trans = E.trend_states(st, T)
lab = []
for i in range(len(st["index"])):
    x, m, r = st["index"].iloc[i], st["ma50"].iloc[i], st["r20"].iloc[i]
    lab.append("UNCERTAIN" if (pd.isna(r) or pd.isna(m)) else "BULL" if (x > m and r > T["R1_bull_r20_P67"]) else "BEAR" if (x < m and r < T["R2_bear_r20_P33"]) else "SIDEWAYS")
tr2 = [lab[i] == "UNCERTAIN" or (i > 0 and any(lab[j] != lab[j - 1] for j in range(max(1, i - 4), i + 1))) for i in range(len(lab))]
rec("X3 trend and Transition equal an independent loop", list(trend.values) == lab and list(trans.values) == tr2, sum(tr2))

# ------------------------------------------------------------ X4 hourly signals: independent numpy recompute
def naive_hourly(extra_clv):
    E5 = T["E5_stop_P90"]; out = set()
    elig = U["P1"]["eligible"]
    for ci, c in enumerate(cols):
        if E.is_excluded(c): continue
        cl, hi, lo, vq = (Hh[k][c].values for k in ("close", "high", "low", "vol_quote"))
        n = len(cl); W = 168
        pad = lambda a: np.r_[np.full(W, np.nan), a]
        with np.errstate(all="ignore"):
            import warnings; warnings.simplefilter("ignore")
            rh = np.nanmax(swv(pad(hi), W)[:n], 1); rl = np.nanmin(swv(pad(lo), W)[:n], 1)
            npri = np.sum(~np.isnan(swv(pad(cl), W)[:n]), 1)
            vw = swv(pad(vq), W)[:n]; med = np.nanmedian(vw, 1); med[np.sum(~np.isnan(vw), 1) < 84] = np.nan
            rvol = vq / med; stop = (cl - rl) / cl; rng_ = hi - lo; clv = np.where(rng_ > 0, (cl - lo) / rng_, np.nan)
            width = rh / rl - 1
        day = grid.floor("D")
        el = elig[c].reindex(day).fillna(False).values & ~trans.reindex(day).fillna(True).values
        cand = np.where(el & ~np.isnan(cl) & (npri >= 84) & (cl > rh) & (rvol >= T["E3_rvol_P75"]) & (stop <= E5)
                        & ((clv >= T["E4_clv_median"]) if extra_clv else True))[0]
        for t in cand:
            if t < 4320:
                w = width[:t]
            else:
                w = width[t - 4320:t]
            if np.sum(~np.isnan(w)) >= 2160 and t >= 1 and width[t] <= np.nanquantile(w, 0.25):
                out.add((c, grid[t]))
    return out
for d, cl_ in (("D-H1", False), ("D-H2", True)):
    got = set(zip(*[R["_sig"][d][k] for k in ("coin", "sig_t")])) if "_sig" in R else None
    nv = naive_hourly(cl_)
    rec(f"X4 {d} signal set equals an independent recompute", got == nv, f"code {len(got or [])} naive {len(nv)} diff {len((got or set()) ^ nv)}")

# ------------------------------------------------------------ X5 daily design: independent loop recompute
hi_h, lo_h, cl_h, vq_h = (Hh[k] for k in ("high", "low", "close", "vol_quote"))
days = list(FF.DAYS); elig = U["P1"]["eligible"]
def daily_naive():
    pops_r, pops_s, rows = [], [], []
    for c in cols:
        if E.is_excluded(c): continue
        dh, dl, dc, dv = [], [], [], []
        for i, dd in enumerate(days):
            sl = slice(i * 24, i * 24 + 24); tr = ~np.isnan(cl_h[c].values[sl])
            if tr.any():
                dh.append(np.nanmax(hi_h[c].values[sl][tr])); dl.append(np.nanmin(lo_h[c].values[sl][tr]))
                dc.append(cl_h[c].values[sl][tr][-1]); dv.append(np.nansum(vq_h[c].values[sl][tr]))
            else:
                dh.append(np.nan); dl.append(np.nan); dc.append(np.nan); dv.append(np.nan)
        dh, dl, dc, dv = map(np.array, (dh, dl, dc, dv))
        width = np.full(len(days), np.nan); feat = {}
        for i in range(len(days)):
            w = slice(max(0, i - 20), i); ok = ~np.isnan(dc[w])
            if ok.sum() >= 10:
                RH = dh[w][ok].max(); RL = dl[w][ok].min(); width[i] = RH / RL - 1
                feat[i] = (RH, RL, dv[i] / np.median(dv[w][ok]) if not np.isnan(dc[i]) else np.nan)
        for i in feat:
            RH, RL, rv = feat[i]
            if np.isnan(dc[i]) or i + 1 >= len(days) or not bool(elig[c].iloc[i + 1]) or not dc[i] > RH: continue
            sp = (dc[i] - RL) / dc[i]; ww = width[max(0, i - 180):i]
            a1 = np.sum(~np.isnan(ww)) >= 90 and width[i] <= np.nanquantile(ww, 0.25)
            pops_r.append(rv); pops_s.append(sp); rows.append((c, days[i], a1, rv, sp))
    P75, P90 = np.quantile(pops_r, 0.75), np.quantile(pops_s, 0.90)
    sig = {(c, d + pd.Timedelta(days=1)) for c, d, a1, rv, sp in rows
           if a1 and rv >= P75 and sp <= P90 and not bool(trans.reindex([d + pd.Timedelta(days=1)]).fillna(True).iloc[0])}
    return P75, P90, len(rows), sig
P75n, P90n, npop, sign = daily_naive()
dd = R["designs"]["D-D1"]
rec("X5a daily P75 / P90 equal an independent recompute", math.isclose(dd["daily_thresholds"]["RVOL_d_P75"], P75n, rel_tol=1e-12)
    and math.isclose(dd["daily_thresholds"]["stop_d_P90"], P90n, rel_tol=1e-12) and dd["daily_breakout_population"]["n"] == npop,
    (dd["daily_thresholds"], P75n, P90n, npop))
got = set(zip(R["_sig"]["D-D1"]["coin"], R["_sig"]["D-D1"]["sig_t"]))
rec("X5b daily signal set equals an independent recompute", got == sign, f"code {len(got)} naive {len(sign)}")

# ------------------------------------------------------------ X6 destructive future overwrite (no price after the entry)
tau = TS("2025-02-01")
pack2 = tmp / "pack_future"
import shutil; shutil.copytree(pack, pack2)
rng = np.random.default_rng(99)
for f in (pack2 / "hourly").glob("*.csv.gz"):
    x = pd.read_csv(f); t = pd.to_datetime(x["ts_utc_ms"], unit="ms", utc=True); m = t > tau
    for k in ("open", "high", "low", "close", "vol_quote", "vol_base"):
        x.loc[m, k] = x.loc[m, k] * rng.uniform(0.2, 5, m.sum())
    x.loc[m, "high"] = x.loc[m, ["open", "high", "low", "close"]].max(axis=1); x.loc[m, "low"] = x.loc[m, ["open", "high", "low", "close"]].min(axis=1)
    with gzip.open(f, "wt") as fh: x.to_csv(fh, index=False)
R2 = E.run(pack2, thr_syn, pack / "ledger.csv")
fx = (R["designs"]["D-D1"]["daily_thresholds"]["RVOL_d_P75"], R["designs"]["D-D1"]["daily_thresholds"]["stop_d_P90"])
R1f = E.run(pack, thr_syn, pack / "ledger.csv", _daily_fixed=fx); R2f = E.run(pack2, thr_syn, pack / "ledger.csv", _daily_fixed=fx)
def before(Rx, d):
    s = Rx["_sig"][d]; return sorted((c, t, x, e, k, w) for c, t, x, e, k, w in zip(s["coin"], s["sig_t"], s["exec"], s["end"], s["c"], s["why"])
                                     if t + 2 * H <= tau)
# daily signals of day D use the whole day D; hourly ones bar t and earlier; entry bar open may be after tau only if t+1h > tau
ok6 = all(before(R, d) == before(R2, d) for d in ("D-H1", "D-H2")) and before(R1f, "D-D1") == before(R2f, "D-D1") \
      and before(R1f, "D-D1") == before(R, "D-D1")
rec("X6 prices after tau changed: every signal, execution status and trade window before tau unchanged", ok6,
    [len(before(R, d)) for d in ("D-H1", "D-H2", "D-D1")])

# ------------------------------------------------------------ X7 trade windows (hand cases)
seg_end = pd.Timestamp(seg[1])
def tw(entry, traded, cut=None, sig_t=None, se=None):
    sig = pd.DataFrame({"coin": ["Z"], "sig_t": [sig_t if sig_t is not None else entry - H], "entry_hour": [entry]})
    tt = {"Z": np.array(sorted(pd.DatetimeIndex(traded).as_unit("ns").asi8), dtype="int64")}
    e, c, w = E.trade_windows(sig, tt, {"Z": cut} if cut else {}, se or seg_end); return e[0], c[0], w[0]
en = TS("2025-01-01 10:00")
dl = en + H + pd.Timedelta(days=7)
cases = [("normal", tw(en, [en, dl]), (dl + H, True, "TIME_EXIT")),
         ("min block 7d+2h from signal", tw(en, [en, dl], sig_t=en - H), (max(en - H + pd.Timedelta(days=7, hours=2), dl + H), True, "TIME_EXIT")),
         ("bar inside the deadline hour is not used", tw(en, [en, dl - H, dl + 5 * H]), (dl + 6 * H, True, "TIME_EXIT")),
         ("H_max boundary counted", tw(en, [en, en + pd.Timedelta(hours=719)]), (en + pd.Timedelta(hours=720), True, "TIME_EXIT")),
         ("H_max boundary +1h excluded", tw(en, [en, en + pd.Timedelta(hours=720)]), (en + pd.Timedelta(hours=721), False, "EXCLUDED_HMAX")),
         ("no bar, H_max inside segment", tw(en, [en]), (seg_end, False, "EXCLUDED_HMAX")),
         ("last entry hour: H_max ends inside the segment", tw(TS("2025-08-01 23:00"), [TS("2025-08-01 23:00"), TS("2025-08-31 23:00")]), (seg_end, False, "EXCLUDED_HMAX")),
         ("no bar, segment ends first", tw(en, [en], se=en + pd.Timedelta(days=20)), (en + pd.Timedelta(days=20), False, "OPEN_AT_SEGMENT_END")),
         ("exit bar after segment end", tw(en, [en, en + pd.Timedelta(days=21)], se=en + pd.Timedelta(days=20)), (en + pd.Timedelta(days=20), False, "OPEN_AT_SEGMENT_END")),
         ("priced delisting", tw(en, [en], cut=(en + pd.Timedelta(days=2), True)), (en + pd.Timedelta(days=2), True, "FORCED_EXIT_PRICED")),
         ("unpriceable delisting", tw(en, [en], cut=(en + pd.Timedelta(days=2), False)), (en + pd.Timedelta(days=2), False, "UNPRICEABLE_FORCED_EXIT")),
         ("priced cut after H_max", tw(en, [en], cut=(en + pd.Timedelta(hours=720), True)), (en + pd.Timedelta(hours=720), False, "EXCLUDED_HMAX")),
         ("cut after the trade ends ignored", tw(en, [en, dl], cut=(dl + pd.Timedelta(days=3), False)), (dl + H, True, "TIME_EXIT"))]
for name, got_, exp in cases:
    rec(f"X7 window: {name}", got_ == exp, (got_, exp))

inv = all(e >= t + pd.Timedelta(days=7, hours=2) for d in R["_sig"] for t, e, x in zip(R["_sig"][d]["sig_t"], R["_sig"][d]["end"], R["_sig"][d]["exec"])
          if x == "EXECUTABLE" and e is not None and (e != seg_end))
rec("X7 invariant: every non-delisting block lasts >= 7d+2h after the signal", inv)

# ------------------------------------------------------------ X8 executability (hand cases on the synthetic pack)
c0 = "C07-USDT"; ci = cols.index(c0)
tr_rows = np.where(C[c0].notna().values)[0]; un_rows = np.where(C[c0].isna().values)[0]
r_ok = int(tr_rows[(tr_rows > 2000) & (tr_rows < 9000)][0]); r_un = int(un_rows[(un_rows > 2000) & (un_rows < 9000)][0])
fill = Hh["open"][c0].values[r_ok]
def ex1(row, stop_level, limit=0.05):
    t = grid[row] if row < len(grid) else grid[-1] + H * (row - len(grid) + 1)
    s = pd.DataFrame({"coin": [c0], "sig_t": [t - H], "entry_hour": [t], "row_entry": [row], "col": [ci], "stop_level": [stop_level]})
    return E.executable(s, Hh, limit, seg)[0]
cut_row = grid.get_loc(TS("2025-08-02 00:00"))
rec("X8a untraded entry hour -> NOT_EXECUTED", ex1(r_un, 0.0) == "NOT_EXECUTED")
rec("X8b traded entry hour -> EXECUTABLE", ex1(r_ok, fill * 0.97) == "EXECUTABLE")
rec("X8c entry at the entry cut -> PAST_ENTRY_CUT", ex1(cut_row, 0.0) == "PAST_ENTRY_CUT" and ex1(cut_row - 1, -1e9, 1e18) in ("EXECUTABLE", "NOT_EXECUTED"))
rec("X8d wide stop at the fill -> SKIPPED_WIDE_STOP_AT_ENTRY", ex1(r_ok, fill * 0.90) == "SKIPPED_WIDE_STOP_AT_ENTRY")
rec("X8g wide-stop test uses the fill (entry bar open), boundary exact", ex1(r_ok, fill * (1 - 0.05) + 1e-9 * fill) == "EXECUTABLE"
    and ex1(r_ok, fill * (1 - 0.05) - 1e-9 * fill) == "SKIPPED_WIDE_STOP_AT_ENTRY", (fill, Hh["close"][c0].values[r_ok]))
rec("X8e no half-spread (first 30 days) -> SKIPPED_NO_HALF_SPREAD", ex1(int(tr_rows[tr_rows > 30][0]), 0.0, 1e9) == "SKIPPED_NO_HALF_SPREAD")
hs = E.half_spread_day(Hh["high"], Hh["low"], 100)
h = Hh["high"].values[70 * 24:100 * 24, ci]; l = Hh["low"].values[70 * 24:100 * 24, ci]; vals = []
for a in range(len(h) - 1):
    if np.isnan([h[a], h[a + 1], l[a], l[a + 1]]).any(): continue
    b = math.log(h[a] / l[a]) ** 2 + math.log(h[a + 1] / l[a + 1]) ** 2; g = math.log(max(h[a], h[a + 1]) / min(l[a], l[a + 1])) ** 2
    al = (math.sqrt(2 * b) - math.sqrt(b)) / (3 - 2 * math.sqrt(2)) - math.sqrt(g / (3 - 2 * math.sqrt(2)))
    vals.append(2 * (math.exp(al) - 1) / (1 + math.exp(al)))
rec("X8f half-spread equals an independent loop", math.isclose(hs[ci], max(float(np.median(vals)), 0) / 2, rel_tol=1e-12), (hs[ci], len(vals)))

# ------------------------------------------------------------ X9 L_greedy against an independent simulation; X10 L_worst
def mk(rnd, n, coins, span=60, dur=(5, 30)):
    X = []
    for i in range(n):
        e = rnd.randrange(0, span); X.append({"i": i, "coin": rnd.choice(coins), "entry": e, "end": e + rnd.randint(*dur),
                                              "ws": e - rnd.randint(0, 12), "c": rnd.random() < 0.7, "why": "x"})
    return X
def greedy_ref(X):
    free, last, cnt = -10 ** 9, {}, 0
    for s in sorted(X, key=lambda s: (s["entry"], s["coin"])):
        if s["entry"] >= free and s["ws"] >= last.get(s["coin"], -10 ** 9):
            cnt += s["c"]; free = s["end"]; last[s["coin"]] = s["end"]
    return cnt
def true_min(X):
    """exhaustive: every exit time (pieces of the threshold grid), every tie choice, the EXACT per-coin rule."""
    th = sorted({s["entry"] for s in X} | {s["ws"] for s in X} | {s["end"] for s in X})
    best = [10 ** 9]
    def go(free, last, cnt):
        if cnt >= best[0]: return
        el = [s for s in X if s["entry"] >= free and s["ws"] >= last.get(s["coin"], -10 ** 9)]
        if not el: best[0] = min(best[0], cnt); return
        h = min(s["entry"] for s in el)
        for s in [s for s in el if s["entry"] == h]:
            opts = [(e, 1) for e in th if s["entry"] < e < s["end"]] + [(s["end"], 1), (s["end"], int(s["c"]))]
            for e, k in opts:
                go(e, dict(last, **{s["coin"]: e}), cnt + k)
    go(-10 ** 9, {}, 0); return best[0]
def real_path(X, rnd):
    free, last, cnt = -10 ** 9, {}, 0
    while True:
        el = [s for s in X if s["entry"] >= free and s["ws"] >= last.get(s["coin"], -10 ** 9)]
        if not el: return cnt
        h = min(s["entry"] for s in el); s = rnd.choice([s for s in el if s["entry"] == h])
        if rnd.random() < 0.5: e, k = s["end"], int(s["c"])
        else: e, k = rnd.uniform(s["entry"] + 1e-6, s["end"]), 1
        cnt += k; free = e; last[s["coin"]] = e
rnd = random.Random(20261110); g_ok = w_ok = tight_ok = w_le_g = True; nd = 0
for trial in range(400):
    X = mk(rnd, rnd.randint(1, 7), ["A", "B", "C"] if trial % 2 else ["A", "B", "C", "D", "E", "F", "G", "H"])
    g, _ = E.l_greedy([dict(s) for s in X], pd.Timestamp(-10 ** 9))
    w, _ = E.l_worst([dict(s) for s in X], pd.Timestamp(-10 ** 9))
    g_ok &= g["L_greedy"] == greedy_ref(X)
    tm = true_min(X); w_ok &= w <= tm and all(real_path(X, rnd) >= w for _ in range(30))
    w_le_g &= w <= g["L_greedy"]
    if len({s["coin"] for s in X}) == len(X): tight_ok &= w == tm
    nd += w < g["L_greedy"]
rec("X9 L_greedy equals an independent greedy simulation (400 random cases)", g_ok)
rec("X10a L_worst <= exhaustive true minimum and <= every simulated real path", w_ok)
rec("X10b L_worst <= L_greedy", w_le_g, f"strictly lower in {nd}/400")
rec("X10c L_worst is exact when no coin repeats", tight_ok)
# the counterexample that motivates addendum A1: a real path can complete fewer trades than the plan's greedy L
X = [{"i": 0, "coin": "A", "entry": 0, "end": 168, "ws": -168, "c": True, "why": ""},
     {"i": 1, "coin": "B", "entry": 10, "end": 10 ** 4, "ws": -158, "c": False, "why": ""},
     {"i": 2, "coin": "C", "entry": 200, "end": 368, "ws": 32, "c": True, "why": ""},
     {"i": 3, "coin": "D", "entry": 400, "end": 568, "ws": 232, "c": True, "why": ""}]
g, _ = E.l_greedy([dict(s) for s in X], pd.Timestamp(-10 ** 9)); w, _ = E.l_worst([dict(s) for s in X], pd.Timestamp(-10 ** 9))
rec("X10d counterexample: greedy L = 3, but a stop at hour 5 then coin B (no exit) gives 1; L_worst = 1",
    g["L_greedy"] == 3 and w == 1 and true_min(X) == 1, (g["L_greedy"], w))

# re-entry blocked by an OLDER trade of the same coin (A1 exits after A3's window start; B2 sits in between):
# the real trader must skip A3 and lands on S4 (no exit). L_worst must see that path: true minimum = 2.
X = [{"i": 0, "coin": "A", "entry": 0, "end": 2, "ws": -168, "c": True, "why": ""},
     {"i": 1, "coin": "B", "entry": 2, "end": 4, "ws": -166, "c": True, "why": ""},
     {"i": 2, "coin": "A", "entry": 4, "end": 10, "ws": 1, "c": True, "why": ""},
     {"i": 3, "coin": "C", "entry": 5, "end": 10 ** 4, "ws": -163, "c": False, "why": ""}]
w, _ = E.l_worst([dict(s) for s in X], pd.Timestamp(-10 ** 9)); tm = true_min(X)
rec("X10e older same-coin exit blocks a re-entry: L_worst <= true minimum (= 2)", tm == 2 and w <= tm, (w, tm))

# ------------------------------------------------------------ X11 selection rule
ok = True
for la, lb, lc in itertools.product([99, 100], repeat=3):
    Ls = {"D-H1": la, "D-H2": lb, "D-D1": lc}
    exp = "D-D1" if lc >= 100 else "D-H1" if la >= 100 else "D-H2" if lb >= 100 else "STOP_INFEASIBLE"
    ok &= E.select(Ls) == exp
rec("X11 selection rule on all 8 pass/fail combinations", ok and E.CONDITIONS == {"D-H1": 4, "D-H2": 5, "D-D1": 4})

# ------------------------------------------------------------ X12 exclusions, eligibility, report integrity
allsig = pd.concat([R["_sig"][d] for d in R["_sig"]])
rec("X12a0 the copied coins do produce signals (so X12a has teeth)", {"C01-USDT", "C08-USDT"} & set(allsig["coin"]), sorted(set(allsig["coin"])))
rec("X12a no excluded coin in any signal", not any(E.is_excluded(c) for c in allsig["coin"]), sorted(set(allsig["coin"]))[:5])
el_ok = all(bool(U["P1"]["eligible"].loc[t.floor("D"), c]) for c, t in zip(R["_sig"]["D-H1"]["coin"], R["_sig"]["D-H1"]["sig_t"])) and \
        all(bool(U["P1"]["eligible"].loc[t, c]) for c, t in zip(R["_sig"]["D-D1"]["coin"], R["_sig"]["D-D1"]["sig_t"]))
rec("X12b hourly signals eligible on the bar day; daily ones on D+1", el_ok)
cons = all(R["designs"][d]["signals"]["n"] == R["designs"][d]["cascade"][-1][1] == sum(R["designs"][d]["execution"].values())
           and R["designs"][d]["greedy"]["taken"] + R["designs"][d]["greedy"]["blocked_open_trade"] + R["designs"][d]["greedy"]["blocked_same_coin_window"]
           == R["designs"][d]["execution"].get("EXECUTABLE", 0) for d in R["designs"])
rec("X12c report totals reconcile (cascade = signals = execution reasons; taken + blocked = executable)", cons)
rec("X12d H2 dominates H1 (D-H2 signals subset of D-H1)", set(zip(R["_sig"]["D-H2"]["coin"], R["_sig"]["D-H2"]["sig_t"])) <=
    set(zip(R["_sig"]["D-H1"]["coin"], R["_sig"]["D-H1"]["sig_t"])))
reasons = set().union(*[R["designs"][d]["trade_window_reason_all_executable"] for d in R["designs"]])
KNOWN = {"TIME_EXIT", "EXCLUDED_HMAX", "OPEN_AT_SEGMENT_END", "FORCED_EXIT_PRICED", "UNPRICEABLE_FORCED_EXIT"}
rec("X12e synthetic run has signals in all designs and only known reasons", "TIME_EXIT" in reasons and reasons <= KNOWN
    and all(R["designs"][d]["signals"]["n"] >= 15 for d in R["designs"]), reasons)

# ------------------------------------------------------------ X13 determinism (the stored json; private _sig removed)
o1, o2 = tmp / "o1", tmp / "o2"
E.main(o1, pack, thr_syn, pack / "ledger.csv"); E.main(o2, pack, thr_syn, pack / "ledger.csv")
b1 = (o1 / "exp3_counts.json").read_bytes()
rec("X13 two runs byte-identical; no private field stored", b1 == (o2 / "exp3_counts.json").read_bytes() and b'"_sig"' not in b1)
txt = b1.decode()
rec("X13b output holds no price / return field", not any(k in txt for k in ('"open"', '"close"', '"pnl"', '"return"', "last_trade_price")))

tim = all((R["_sig"][d]["entry_hour"] == R["_sig"][d]["sig_t"] + H).all() for d in ("D-H1", "D-H2")) and \
      (R["_sig"]["D-D1"]["entry_hour"] == R["_sig"]["D-D1"]["sig_t"]).all() and \
      all((grid[R["_sig"][d]["row_entry"].clip(upper=len(grid) - 1)] == R["_sig"][d]["entry_hour"])[R["_sig"][d]["row_entry"] < len(grid)].all() for d in R["_sig"]) and \
      (R["_sig"]["D-D1"]["sig_t"].dt.hour == 0).all()
rec("X12f timing: hourly entry = bar t + 1h, daily entry = D+1 00:00, entry row = entry hour", tim)

n_fail = sum(not r["pass"] for r in res)
print(f"{len(res) - n_fail}/{len(res)} passed")
if len(sys.argv) > 1: pathlib.Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
sys.exit(1 if n_fail else 0)
