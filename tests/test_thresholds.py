"""Pre-run tests for lab/thresholds.py (plan v0.3.1 §6). They run on a SYNTHETIC pack (and on the real pack's manifest
only for RD1), so they derive NO real threshold. RD4 (byte-identical runs incl. an isolated environment) is executed at
the one real run by tests/run_thresholds_once.py.
python3 -I tests/test_thresholds.py [out.json]"""
import sys, ast, json, math, gzip, shutil, tempfile, pathlib, datetime as dt
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import thresholds as TH

res = []
def rec(name, ok, detail=""):
    res.append({"test": name, "pass": bool(ok), "detail": str(detail)}); print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
def same(a, b, tol=1e-12):
    if (isinstance(a, float) and math.isnan(a)) and (isinstance(b, float) and math.isnan(b)): return True
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-12)

# ---------- synthetic pack (Development calendar, random data; NOT market data)
def make_pack(root, seed=1, ncoins=26):
    rng = np.random.default_rng(seed); root = pathlib.Path(root)
    (root / "hourly").mkdir(parents=True); (root / "universe").mkdir()
    grid = pd.date_range(FF.DEV_START, FF.DEV_END - pd.Timedelta(hours=1), freq="h")
    names = ["BTC-USDT", "USDC-USDT"] + [f"C{i:02d}-USDT" for i in range(ncoins - 2)]
    groups = []
    for k, s in enumerate(names):
        vol = 0.002 if s == "USDC-USDT" else rng.uniform(0.005, 0.02)
        lr = rng.normal(0, vol, len(grid)) + 0.01 * np.sin(np.arange(len(grid)) / (500 + 37 * k))
        if s == "USDC-USDT": lr = rng.normal(0, 0.0002, len(grid))
        c = 100 * np.exp(np.cumsum(lr)); o = np.r_[c[0], c[:-1]]
        h = np.maximum(o, c) * (1 + rng.uniform(0, vol, len(grid))); l = np.minimum(o, c) * (1 - rng.uniform(0, vol, len(grid)))
        vq = rng.lognormal(10, 1, len(grid)) * (1 + 3 * (rng.random(len(grid)) < 0.02))
        keep = rng.random(len(grid)) > 0.05                                   # ~5 % untraded hours
        df = pd.DataFrame({"ts_utc_ms": (grid.as_unit("ms").asi8)[keep], "open": o[keep], "high": h[keep], "low": l[keep], "close": c[keep],
                           "vol_base": (vq / c)[keep], "vol_quote": vq[keep], "traded_minutes": rng.integers(1, 61, len(grid))[keep]})
        with gzip.open(root / "hourly" / f"{s}.csv.gz", "wt") as fh: df.to_csv(fh, index=False)
        groups.append((s, "active"))
    pd.DataFrame(groups, columns=["series", "group"]).to_csv(root / "groups.csv", index=False)
    days = pd.date_range(FF.DEV_START, FF.DEV_END - pd.Timedelta(days=1), freq="D")
    rows = []
    for s in names:
        for i, d in enumerate(days):
            el = i >= 31 and not (s == "C05-USDT" and 200 <= i < 260)
            rows.append((s, "active", d.strftime("%Y-%m-%d"), i >= 30, 1.0, 1e6, el))
    U = pd.DataFrame(rows, columns=["series", "group", "day", "assessable", "THR30", "DV30_med", "eligible"])
    for f in FF.SCEN.values():
        with gzip.open(root / "universe" / f, "wt") as fh: U.to_csv(fh, index=False)
    (root / "PACK_MANIFEST.json").write_text(json.dumps({"synthetic": True, "seed": seed}))
    return root

tmp = pathlib.Path(tempfile.mkdtemp(prefix="thr_syn_"))
pack = make_pack(tmp / "pack")

# RD2 no outcome code: static + runtime
FORBIDDEN = {"lab.fd2", "lab.val", "lab.strategy", "lab.strategy_attrib", "lab.fd1", "lab.mi", "lab.mi_regimes"}
ALLOWED = {"sys", "json", "hashlib", "pathlib", "numpy", "pandas", "lab.fd_features", "lab.universe_crypto_only"}
tree = ast.parse((FF.LAB / "lab/thresholds.py").read_text())
imps = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import): imps |= {a.name for a in n.names}
    if isinstance(n, ast.ImportFrom): imps |= {f"{n.module}.{a.name}" if n.module == "lab" else n.module for a in n.names}
res_syn, (Hh, ind, H, BO, st) = TH.derive(pack)
rec("RD2 no outcome code: static imports within the allowed set; no forbidden module loaded at runtime",
    imps <= ALLOWED and not (FORBIDDEN & set(sys.modules)), sorted(imps))

# RD1 isolation of the REAL Development pack (manifest + universe days only; nothing derived)
man = json.loads((FF.PACK / "PACK_MANIFEST.json").read_text())
lastday = max(pd.read_csv(FF.PACK / "universe" / f, usecols=["day"])["day"].max() for f in FF.SCEN.values())
rec("RD1 real Development pack: last candle starts <= 2025-08-31 23:00, last universe day <= 2025-08-31",
    man["max_candle_start_in_pack"] <= "2025-08-31 23:00" and lastday <= "2025-08-31", (man["max_candle_start_in_pack"], lastday))

# RD5 independent recompute (synthetic): indicators on sampled bars + populations + percentile formula
C, Hi, Lo, VQ = (Hh[k] for k in ("close", "high", "low", "vol_quote"))
rng = np.random.default_rng(3); ok = True; checked = 0
cols = list(C.columns)
for _ in range(400):
    t = int(rng.integers(TH.PEAK + TH.W + 10, len(C))); j = int(rng.integers(0, len(cols)))
    hp = Hi.iloc[t - TH.W:t, j].values; lp = Lo.iloc[t - TH.W:t, j].values; vp = VQ.iloc[t - TH.W:t, j].values
    nn = (~np.isnan(C.iloc[t - TH.W:t, j].values)).sum()
    rh = np.nanmax(hp) if (~np.isnan(hp)).any() else float("nan"); rl = np.nanmin(lp) if (~np.isnan(lp)).any() else float("nan")
    pk = Hi.iloc[t - TH.W - TH.PEAK:t - TH.W, j].values; pkv = np.nanmax(pk) if (~np.isnan(pk)).sum() >= TH.PEAK // 2 else float("nan")
    med = float(np.median(vp[~np.isnan(vp)])) if (~np.isnan(vp)).sum() >= TH.MINW else float("nan")
    c, h_, l_, v_ = C.iat[t, j], Hi.iat[t, j], Lo.iat[t, j], VQ.iat[t, j]
    exp = {"R_high": rh, "R_low": rl, "n_prior": float(nn), "rvol": v_ / med if not math.isnan(med) else float("nan"),
           "clv": (c - l_) / (h_ - l_) if (not math.isnan(c) and h_ > l_) else float("nan"), "stop": (c - rl) / c, "ratio": rh / pkv}
    for k, e in exp.items():
        g = float(ind[k].iat[t, j]); ok &= same(g, float(e), 1e-12); checked += 1
def q_naive(x, p):
    x = sorted(v for v in x if not math.isnan(v)); n = len(x); pos = (n - 1) * p; lo = int(math.floor(pos)); hi = min(lo + 1, n - 1)
    return x[lo] + (x[hi] - x[lo]) * (pos - lo)
U = FF.load_pack(pack)[1]
uni = pd.read_csv(pack / "universe" / FF.SCEN["P1"])                        # independent of TH.allowed_mask
elig = {(r.series, r.day) for r in uni.itertuples() if r.eligible}
pegged = {"USDC", "PYUSD", "USDG", "USD1", "USAT", "EURT", "BRL1", "USTC", "XAUT", "PAXG", "STETH", "BETH", "JITOSOL", "OKSOL", "CGL"}
dstr = C.index.strftime("%Y-%m-%d")
Am = pd.DataFrame({c: [(c, d) in elig and c.split("-")[0] not in pegged for d in dstr] for c in C.columns}, index=C.index)
Hn = Am & C.notna() & (ind["n_prior"] >= TH.MINW); BOn = Hn & (C > ind["R_high"])
okp = Hn.equals(H) and BOn.equals(BO) and not Am["USDC-USDT"].any()
T = res_syn["thresholds"]
okq = same(T["E3_rvol_P75"], q_naive(ind["rvol"].values[(BO & ind["rvol"].notna()).values], .75)) and \
      same(T["E5_stop_P90"], q_naive(ind["stop"].values[(BO & ind["stop"].notna()).values], .90)) and \
      same(T["E4_clv_median"], q_naive(ind["clv"].values[(BO & ind["clv"].notna()).values], .5)) and \
      same(T["E2_peak_ratio_P25"], q_naive(ind["ratio"].values[(H & ind["ratio"].notna()).values], .25)) and \
      same(T["R3_bear_rvol_P90"], q_naive(ind["rvol"].values[(BO & ind["rvol"].notna()).values], .90))
rec("RD5 independent recompute (synthetic): indicators on 400 sampled bars, populations H/BO, excluded coin removed, percentile formula",
    ok and okp and okq, f"{checked} indicator values")

# RD3 point-in-time indicators (synthetic): corrupt every bar >= t, indicators at t unchanged
bad = 0
for t in (TH.PEAK + TH.W + 500, len(C) - 3000):
    H2 = {}
    for k, df in Hh.items():
        x = df.copy(); x.iloc[t + 1:] = x.iloc[t + 1:].notna() * np.random.default_rng(5).uniform(1e-3, 1e3, size=x.iloc[t + 1:].shape)
        x.iloc[t + 1:] = x.iloc[t + 1:].where(x.iloc[t + 1:] != 0); H2[k] = x
    i2 = TH.indicators(H2, U, None)
    for k in ("R_high", "R_low", "rvol", "clv", "stop", "ratio", "n_prior"):
        a, b = ind[k].iloc[t].values, i2[k].iloc[t].values
        bad += int((~((np.isnan(a) & np.isnan(b)) | (a == b))).sum())
rec("RD3 destructive overwrite of bars after t: every indicator at t unchanged (synthetic)", bad == 0)

# RD8 point-in-time High-Vol flag: independent recompute from prior days + destructive check
ret, n, _ = TH.ew_index(Hh, U, None)
v = ret.rolling(30, min_periods=30).std().shift(1).values
flag = []
for i in range(len(v)):
    h = [x for x in v[:i] if not math.isnan(x)]
    flag.append(len(h) >= 60 and not math.isnan(v[i]) and sum(x < v[i] for x in h) / len(h) > 2 / 3)
ok8 = list(st["high_vol"].values) == flag
d = 300; ret2 = ret.copy(); ret2.iloc[d + 1:] = 5.0
ok8 &= bool(TH.states(ret2)["high_vol"].iloc[d] == st["high_vol"].iloc[d])
rec("RD8 High-Vol flag of day d uses prior days only (independent recompute; corrupting days > d changes nothing at d)", ok8,
    f"{int(st['high_vol'].sum())} synthetic high-vol days")

# RD6 no circularity: populations use no entry constant; derived values do not depend on any current spec constant
code = ast.parse((FF.LAB / "lab/thresholds.py").read_text())
fn = {"indicators", "allowed_mask", "ew_index", "states", "derive"}
lits = [n.value for f in code.body if isinstance(f, ast.FunctionDef) and f.name in fn for n in ast.walk(f)
        if isinstance(n, ast.Constant) and isinstance(n.value, float)]
# the populations H/BO were already shown (RD5) to equal a naive definition with NO entry filter (close > R_high only)
rec("RD6 no circularity: the derivation functions hold no current spec constant as a float (2.0, 3.0, 0.70, 0.80, 0.15, 0.08), "
    "and H/BO equal a naive definition with no entry filter (RD5)", not ({2.0, 3.0, 0.7, 0.8, 0.15, 0.08} & set(lits)) and okp, sorted(set(lits)))

shutil.rmtree(tmp)
n_pass = sum(r["pass"] for r in res)
summary = {"passed": n_pass, "of": len(res), "PASS": n_pass == len(res), "data": "synthetic (+ real manifest for RD1)"}
if len(sys.argv) > 1: json.dump({"results": res, **summary}, open(sys.argv[1], "w"), indent=1)
print(json.dumps(summary))
