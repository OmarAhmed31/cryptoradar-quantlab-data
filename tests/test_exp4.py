"""Pre-run tests for lab/exp4_counts.py (spec EXP4 v0.5, frozen). SYNTHETIC data only (and the frozen thresholds file for
its exact values); NO real count is computed here. The one real run + RD4 is tests/run_exp4_once.py (after approval).
python3 -I tests/test_exp4.py [out.json]   -> exit code 1 if any test fails"""
import sys, ast, json, gzip, math, random, hashlib, tempfile, pathlib, shutil, functools
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import exp3_counts as E3
from lab import exp4_counts as E

REPO = pathlib.Path(__file__).resolve().parents[1]
res = []
def rec(name, ok, detail=""):
    res.append({"test": name, "pass": bool(ok), "detail": str(detail)[:400]}); print(("PASS " if ok else "FAIL ") + name, str(detail)[:200], flush=True)
TS = lambda s: pd.Timestamp(s, tz="UTC")
HN = 3600 * 10 ** 9

# the synthetic pack generator of the frozen Exp. 3 tests (same source, executed here; NOT market data)
_src3 = (REPO / "tests/test_exp3.py").read_text()
exec(_src3[_src3.index("def make_pack"):_src3.index("tmp = pathlib.Path")])
tmp = pathlib.Path(tempfile.mkdtemp(prefix="exp4_syn_"))
pack = make_pack(tmp / "pack")
real_T = json.loads((REPO / E3.THR_FILE).read_bytes())
synT = dict(real_T); synT["thresholds"] = dict(real_T["thresholds"], E3_rvol_P75=2.5, E4_clv_median=0.6, E5_stop_P90=0.15)
thr_syn = tmp / "thr.json"; thr_syn.write_bytes(json.dumps(synT).encode())
E3.THR_SHA = hashlib.sha256(thr_syn.read_bytes()).hexdigest()           # synthetic thresholds for the synthetic pack only

# ------------------------------------------------------------ Y1 imports
ALLOWED = {"sys", "json", "hashlib", "pathlib", "numpy", "pandas", "lab.fd_features", "lab.exp3_counts", "lab.segment_loader"}
src = (REPO / "lab/exp4_counts.py").read_text(); tree = ast.parse(src); imps = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import): imps |= {a.name for a in n.names}
    if isinstance(n, ast.ImportFrom): imps |= {f"{n.module}.{a.name}" if n.module == "lab" else n.module for a in n.names}
strs = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
rec("Y1a imports allowed only (frozen Exp. 3 code reused, no outcome module)", imps <= ALLOWED, sorted(imps - ALLOWED))
rec("Y1b no validation/holdout segment named", not ({"validation", "holdout"} & strs))
rec("Y1c frozen Exp. 3 code unchanged (sha256 at the frozen commit 1f91f8b)",
    hashlib.sha256((REPO / "lab/exp3_counts.py").read_bytes()).hexdigest() == "b6fdc2d06ab60053e207b9fa9d0f14f1c0fd5ac67ed1580119a10f133c6160f3")

# ------------------------------------------------------------ the engine: hand cases (spec v0.5 §1.3, E1-E9)
def c(i, h, coin, rvol=10.0, fill="FILLED", end=None, free_at=None, ws=-10 ** 30, rf=None, cnt=True):
    end = end if end is not None else h + 200
    return {"i": i, "h": h, "coin": coin, "rvol": rvol, "ws": ws, "fill": fill, "end": end,
            "free_at": free_at if free_at is not None else end, "rf": rf if rf is not None else end, "c": cnt, "why": "TIME_EXIT"}
def run_e(cands, K=3):
    s, r, o = E.portfolio([dict(x) for x in cands], K); return s, r, [x["i"] for x in o]
# E1: nothing open, 1 signal -> opened
s, r, o = run_e([c(0, 0, "A")]); rec("Y2 E1 lone signal opens", o == [0] and r[0] == "OPENED")
# E2: 3 open; one exits (free_at 50); batch of 3 at 60 -> best 1
cs = [c(0, 0, "A", end=50), c(1, 0, "B", end=500), c(2, 0, "C", end=500),
      c(3, 60, "D", rvol=5), c(4, 60, "E", rvol=9), c(5, 60, "F", rvol=7)]
s, r, o = run_e(cs); rec("Y2 E2 3 open, one exits, 3 new -> only the best 1", o == [0, 1, 2, 4] and r[3] == r[5] == "SKIPPED_RANK", r)
# E3: 2 open; one exits; batch of 3 -> best 2 (total 3 open)
cs = [c(0, 0, "A", end=50), c(1, 0, "B", end=500), c(3, 60, "D", rvol=5), c(4, 60, "E", rvol=9), c(5, 60, "F", rvol=7)]
s, r, o = run_e(cs); rec("Y2 E3 2 open, one exits, 3 new -> best 2", o == [0, 1, 4, 5] and r[3] == "SKIPPED_RANK", r)
# E4: 1 open with all the cash; batch of 2 -> NO_CASH although slots free
cs = [c(0, 0, "A", end=500), c(1, 10, "B"), c(2, 10, "C")]
s, r, o = run_e(cs); rec("Y2 E4 one lone position holds all cash -> later batch SKIPPED_NO_CASH", o == [0] and r[1] == r[2] == "SKIPPED_NO_CASH", r)
# E5: K = 1 (equity < $2,000), batch of 3 -> best 1
cs = [c(0, 0, "A", rvol=3), c(1, 0, "B", rvol=8), c(2, 0, "C", rvol=5)]
s, r, o = run_e(cs, K=1); rec("Y2 E5 K=1 with 3 signals -> only the best 1", o == [1] and r[0] == r[2] == "SKIPPED_RANK", r)
# E6: K = 1 with 3 positions still open (built under K=3) -> NO_SLOT until all exit
eng = E.portfolio
cs = [c(0, 0, "A", end=100), c(1, 0, "B", end=200), c(2, 0, "C", end=300), c(3, 150, "D"), c(4, 350, "E")]
s1, r1, o1 = E.portfolio([dict(x) for x in cs[:3]], 3)
rec("Y2 E6a under K=1 a batch is refused while any position is open (NO_SLOT), allowed once all exited",
    (lambda s, r, o: r[3] == "SKIPPED_NO_SLOT" and r[4] == "OPENED")(*run_e([c(0, 0, "A", end=100), c(3, 50, "D"), c(4, 150, "E")], K=1)))
# E7 covered by E4 (cash 0 with free slots); E8: failed fill share stays in cash
cs = [c(0, 0, "A", rvol=9), c(1, 0, "B", rvol=8, fill="NOT_EXECUTED"), c(2, 10, "C")]
s, r, o = run_e(cs); rec("Y2 E8 a failed fill keeps its share in cash: the next batch can still enter", o == [0, 2] and r[1] == "NOT_EXECUTED", r)
cs = [c(0, 0, "A", rvol=9), c(1, 0, "B", rvol=8, fill="SKIPPED_WIDE_STOP_AT_ENTRY"), c(2, 0, "C", rvol=7)]
s, r, o = run_e(cs, K=2); rec("Y2 E8b a failed selected signal is NOT replaced by a lower-ranked one of the same batch",
                              o == [0] and r[2] == "SKIPPED_RANK" and r[1] == "SKIPPED_WIDE_STOP_AT_ENTRY", r)
# E9: snapshot: exit at or after h does not reshape the batch at h
# batch at 0: A, B fill, X fails -> 2 open and X's third of the cash stays in cash (1 slot free, cash > 0)
cs = [c(0, 0, "A", end=500), c(1, 0, "B", end=500), c(9, 0, "X", rvol=1, fill="NOT_EXECUTED"), c(2, 100, "C", end=1000), c(3, 100, "D", rvol=1)]
cs[0]["free_at"] = 101                                      # A exits after h = 100 (e.g. at h + 20 min)
s, r, o = run_e(cs); rec("Y2 E9 exit after h: its slot/cash do not join the batch at h", r[2] == "OPENED" and r[3] == "SKIPPED_RANK", r)
cs[0]["free_at"] = 100
s, r, o = run_e(cs); rec("Y2 E9b exit strictly before h (free_at <= h): released in the snapshot", r[2] == r[3] == "OPENED", r)
rec("Y2 free_time: time exit free from h >= end; exit AT end (cut / segment end) free only after end",
    E.free_time(1000, 999 - 3599) == 1000 and E.free_time(1000, 1000) == 1001)
# coin held / re-entry
cs = [c(0, 0, "A", end=500), c(1, 100, "A")]
s, r, o = run_e(cs); rec("Y2 coin already held -> BLOCKED_COIN_HELD", r[1] == "BLOCKED_COIN_HELD")
cs = [c(0, 0, "A", end=100, rf=300), c(1, 200, "A", ws=250), c(2, 400, "A", ws=300)]
s, r, o = run_e(cs); rec("Y2 same-coin re-entry window (ws >= rf) enforced", r[1] == "BLOCKED_REENTRY_WINDOW" and r[2] == "OPENED", r)
cs = [c(0, 0, "A", cnt=False), c(1, 0, "B")]
s, r, o = run_e(cs); rec("Y2 L counts only completed trades (c)", s["L_greedy_K"] == 1 and s["opened"] == 2, s)

# ---- Y2f the fill check is called ONLY for the signals the portfolio selected (spec v0.5 step 7)
calls = []
def spy(s):
    calls.append(s["i"]); return s["fill"]
cs = [c(0, 0, "A", end=500), c(1, 10, "B"), c(2, 10, "C"),                 # 1-2: NO_CASH (A holds all the cash)
      c(3, 600, "D", rvol=9, end=2000), c(4, 600, "E", rvol=8, end=2000), c(5, 600, "F", rvol=7, end=2000), c(6, 600, "G", rvol=6),   # K=3: 6 is RANK
      c(7, 610, "D"), c(8, 900, "H", fill="NOT_EXECUTED")]                 # 7: coin held; 8: NO_SLOT
s, r, o = E.portfolio([dict(x) for x in cs], 3, spy)
rec("Y2f fill check only for selected signals: none for NO_CASH / RANK / NO_SLOT / coin held",
    sorted(calls) == [0, 3, 4, 5] and r[1] == r[2] == "SKIPPED_NO_CASH" and r[6] == "SKIPPED_RANK" and r[7] == "BLOCKED_COIN_HELD"
    and r[8] == "SKIPPED_NO_SLOT", (calls, r))

# ------------------------------------------------------------ Y3 an independent reference engine (explicit cash amounts)
def reference(cands, K):
    hours = sorted({x["h"] for x in cands}); cash = 1.0; opn = []; last = {}; reason = {}; L = 0
    def better(a, b):                                        # RVOL desc, then coin asc
        if a["rvol"] != b["rvol"]: return -1 if a["rvol"] > b["rvol"] else 1
        return -1 if a["coin"] < b["coin"] else (1 if a["coin"] > b["coin"] else 0)
    for h in hours:
        for p in list(opn):
            if p["free_at"] <= h:
                opn.remove(p); cash += p["alloc"]; last[p["coin"]] = max(last.get(p["coin"], p["rf"]), p["rf"])
        held = {p["coin"] for p in opn}; batch = []
        for x in [x for x in cands if x["h"] == h]:
            if x["coin"] in held: reason[x["i"]] = "BLOCKED_COIN_HELD"
            elif x["coin"] in last and x["ws"] < last[x["coin"]]: reason[x["i"]] = "BLOCKED_REENTRY_WINDOW"
            else: batch.append(x)
        if not batch: continue
        free = K - len(opn)
        if free <= 0:
            for x in batch: reason[x["i"]] = "SKIPPED_NO_SLOT"
            continue
        if cash <= 1e-12:
            for x in batch: reason[x["i"]] = "SKIPPED_NO_CASH"
            continue
        batch = sorted(batch, key=functools.cmp_to_key(better)); sel = batch[:free]; share = cash / len(sel)
        for x in batch[free:]: reason[x["i"]] = "SKIPPED_RANK"
        for x in sel:
            if x["fill"] == "FILLED":
                cash -= share; opn.append(dict(x, alloc=share)); reason[x["i"]] = "OPENED"; L += int(x["c"])
            else:
                reason[x["i"]] = x["fill"]
    return L, reason
rnd = random.Random(20261110); ok3 = True; n_multi = 0
for trial in range(1500):
    n = rnd.randint(1, 14); cs = []
    for i in range(n):
        h = rnd.randrange(0, 40) * 10; end = h + rnd.randrange(5, 120)
        cs.append(c(i, h, rnd.choice("ABCDEFG"), rvol=float(rnd.choice([3, 5, 5, 7, 9, 11])) + (rnd.random() * 1e-9 if rnd.random() < .3 else 0),
                    fill=rnd.choice(["FILLED"] * 6 + ["NOT_EXECUTED", "SKIPPED_WIDE_STOP_AT_ENTRY"]), end=end,
                    free_at=end + rnd.choice([0, 0, 0, 1]), ws=h - rnd.randrange(0, 150), rf=end + rnd.randrange(0, 60), cnt=rnd.random() < .8))
    K = rnd.choice([1, 2, 3])
    s, r, o = E.portfolio([dict(x) for x in cs], K); L2, r2 = reference(cs, K)
    ok3 &= (s["L_greedy_K"] == L2) and (r == r2)
    n_multi += max(map(int, s["open_positions_after_each_entry"] or {"0": 0})) > 1
rec("Y3 engine equals an independent reference with explicit cash amounts (1,500 random cases, K = 1..3)", ok3, f"cases with >1 open: {n_multi}")

# ------------------------------------------------------------ Y4 K = 1 reproduces the Exp. 3 sequential count (distinct hours, all filled)
ok4 = True
for trial in range(500):
    n = rnd.randint(1, 10); hs = rnd.sample(range(0, 60), n); cs = []
    for i, h in enumerate(sorted(hs)):
        end = h * 10 + rnd.randrange(5, 120)
        cs.append(c(i, h * 10, rnd.choice("ABCD"), end=end, ws=h * 10 - rnd.randrange(0, 150), rf=end, cnt=rnd.random() < .8))
    s, r, o = E.portfolio([dict(x) for x in cs], 1)
    X = [{"i": x["i"], "coin": x["coin"], "entry": x["h"], "end": x["end"], "ws": x["ws"], "c": x["c"], "why": "x", "rf": x["rf"]} for x in cs]
    g, tk = E3.l_greedy(X, pd.Timestamp(-10 ** 9))
    ok4 &= s["L_greedy_K"] == g["L_greedy"] and sorted(x["i"] for x in o) == sorted(tk)
rec("Y4 K = 1 equals the frozen Exp. 3 L_greedy on equivalent inputs (500 cases)", ok4)

# ------------------------------------------------------------ Y5 ranking through build_candidates (unrounded, ties by coin)
sigr = pd.DataFrame({"coin": ["BBB-USDT", "AAA-USDT", "CCC-USDT"], "entry_hour": [TS("2025-01-01 10:00")] * 3,
                     "win_start": [TS("2024-12-25")] * 3})
xr = [TS("2025-01-09 05:00")] * 3; en = [TS("2025-01-09 06:00")] * 3
cnd = [dict(x, fill="FILLED") for x in E.build_candidates(sigr, [7.0000000001, 7.0000000001, 7.0000000002], en, [True] * 3, ["TIME_EXIT"] * 3, xr, False)]
s, r, o = E.portfolio(cnd, 1); o = [x["i"] for x in o]
rec("Y5a ranking uses the unrounded RVOL (7.0000000002 beats 7.0000000001)", o == [2], (o, [x["rvol"] for x in cnd]))
cnd = [dict(x, fill="FILLED") for x in E.build_candidates(sigr, [7.0, 7.0, 6.0], en, [True] * 3, ["TIME_EXIT"] * 3, xr, False)]
s, r, o = E.portfolio(cnd, 1); o = [x["i"] for x in o]
rec("Y5b exact tie -> coin name ascending (AAA before BBB)", o == [1], o)
cnd = E.build_candidates(sigr.iloc[:1], [7.0], [TS("2025-01-09 00:00")], [True], ["TIME_EXIT"], [TS("2025-01-08 23:00")], True)
rec("Y5c D-D1 candidates use the calendar re-entry rule from the exit bar day (23:00 bar -> next midnight)",
    cnd[0]["rf"] == TS("2025-01-09").value and cnd[0]["free_at"] == TS("2025-01-09").value, cnd[0])

rec("Y2g candidates carry no fill field: the portfolio cannot read a fill except through the check it calls",
    all("fill" not in x for x in E.build_candidates(sigr, [1.0, 2.0, 3.0], en, [True] * 3, ["TIME_EXIT"] * 3, xr, False)))

# ------------------------------------------------------------ full synthetic run
R = E.run(pack, thr_syn, pack / "ledger.csv")
Hh, U, groups = FF.load_pack(pack); grid = Hh["close"].index; cols = list(Hh["close"].columns)
for d in R["designs"]:
    print(d, R["designs"][d]["reasons_all_signals"], R["designs"][d]["portfolio"]["L_greedy_K"], R["designs"][d]["portfolio"]["batch_size"])

# ------------------------------------------------------------ Y6 the ranking values = the design's own RVOL (independent recompute)
from numpy.lib.stride_tricks import sliding_window_view as swv
ok6 = True; nchk = 0
for d in ("D-H1", "D-H2"):
    sg = R["_sig"][d]["all"]
    for coin, r_, v in zip(sg["coin"], sg["row_entry"], sg["rvol_rank"]):
        vq = Hh["vol_quote"][coin].values; t = r_ - 1; w = vq[max(0, t - 168):t]
        med = np.nanmedian(w) if np.sum(~np.isnan(w)) >= 84 else np.nan
        ok6 &= math.isclose(v, vq[t] / med, rel_tol=1e-12); nchk += 1
        ok6 &= v >= synT["thresholds"]["E3_rvol_P75"]
sg = R["_sig"]["D-D1"]["all"]
for coin, r_, v in zip(sg["coin"], sg["row_entry"], sg["rvol_rank"]):
    di = r_ // 24 - 1; cl = Hh["close"][coin].values; vq = Hh["vol_quote"][coin].values
    dv = [np.nansum(vq[k * 24:(k + 1) * 24][~np.isnan(cl[k * 24:(k + 1) * 24])]) if (~np.isnan(cl[k * 24:(k + 1) * 24])).any() else np.nan for k in range(max(0, di - 20), di + 1)]
    prior = np.array(dv[:-1]); prior = prior[~np.isnan(prior)]
    ok6 &= len(prior) >= 10 and math.isclose(v, dv[-1] / np.median(prior), rel_tol=1e-12) and v >= R["designs"]["D-D1"]["daily_thresholds"]["RVOL_d_P75"]; nchk += 1
rec("Y6 ranking value = the signal's own RVOL (hourly: bar t vs prior 168; daily: day D vs prior 20 traded days), independent loop", ok6 and nchk > 30, nchk)

# ------------------------------------------------------------ Y7 pre-entry and fill checks (hand cases on the synthetic pack)
c0 = "C07-USDT"; ci = cols.index(c0); C = Hh["close"]
tr_rows = np.where(C[c0].notna().values)[0]; un_rows = np.where(C[c0].isna().values)[0]
r_ok = int(tr_rows[(tr_rows > 2000) & (tr_rows < 9000)][0]); r_un = int(un_rows[(un_rows > 2000) & (un_rows < 9000)][0])
fill = Hh["open"][c0].values[r_ok]; seg = E.SEGMENTS["development"]
def one(row, stop_level):
    t = grid[min(row, len(grid) - 1)]
    return pd.DataFrame({"coin": [c0], "sig_t": [t - pd.Timedelta(hours=1)], "entry_hour": [t], "row_entry": [row], "col": [ci], "stop_level": [stop_level]})
rec("Y7a fill: untraded entry hour -> NOT_EXECUTED", E.fill_check(one(r_un, 0.0), Hh, 0.05) == ["NOT_EXECUTED"])
rec("Y7b fill: wide-stop boundary on the entry bar OPEN", E.fill_check(one(r_ok, fill * 0.95 + 1e-9 * fill), Hh, 0.05) == ["FILLED"]
    and E.fill_check(one(r_ok, fill * 0.95 - 1e-9 * fill), Hh, 0.05) == ["SKIPPED_WIDE_STOP_AT_ENTRY"], (fill, C[c0].values[r_ok]))
cut_row = grid.get_loc(TS("2025-08-02 00:00"))
rec("Y7c pre-entry: entry at the entry cut -> PAST_ENTRY_CUT; one hour earlier passes", E.pre_entry(one(cut_row, 0.0), Hh, seg) == ["PAST_ENTRY_CUT"]
    and E.pre_entry(one(cut_row - 1, 0.0), Hh, seg) == ["OK"])
rec("Y7d pre-entry: no half-spread in the first 30 days -> SKIPPED_NO_HALF_SPREAD", E.pre_entry(one(int(tr_rows[tr_rows > 30][0]), 0.0), Hh, seg) == ["SKIPPED_NO_HALF_SPREAD"])
rec("Y7e pre-entry checks do NOT look at the fill (an untraded entry hour still passes pre-entry)", E.pre_entry(one(r_un, 0.0), Hh, seg) == ["OK"])

# ------------------------------------------------------------ Y8 report integrity on the synthetic run
okr = True
for d in R["_sig"]:                                                         # pipeline: entry bar read only for selected signals
    o_ = R["_sig"][d]["ok"]
    okr &= all((f == "NOT_CHECKED") == (p not in ("OPENED", "NOT_EXECUTED", "SKIPPED_WIDE_STOP_AT_ENTRY")) for f, p in zip(o_["fill"], o_["portfolio"]))
    okr &= all(f == p for f, p in zip(o_["fill"], o_["portfolio"]) if p in ("NOT_EXECUTED", "SKIPPED_WIDE_STOP_AT_ENTRY"))
for d, x in R["designs"].items():
    tot = sum(x["reasons_all_signals"].values()); okr &= tot == x["signals"]["n"] == x["cascade"][-1][1]
    okr &= x["reasons_all_signals"].get("OPENED", 0) == x["portfolio"]["opened"] >= x["portfolio"]["L_greedy_K"]
    okr &= max(map(int, x["portfolio"]["open_positions_after_each_entry"] or {"0": 0})) <= E.K_STAGE1
    okr &= x["L_worst"] is None
rec("Y8a reasons reconcile; OPENED = opened >= L; never more than 3 open; the entry bar was read only for selected signals", okr)
rec("Y8b selection = L_greedy(K) rule; U7 note present", R["selection"]["chosen"] == E3.select({d: R["designs"][d]["L_greedy_K"] for d in R["designs"]})
    and "NOT proof" in R["selection"]["U7_note"] and R["selection"]["K"] == 3)
multi = sum(int(k) * 0 + v for d in R["designs"] for k, v in R["designs"][d]["portfolio"]["open_positions_after_each_entry"].items() if int(k) > 1)
rec("Y8c synthetic run exercises parallel positions and several skip reasons", multi > 0 and
    len(set().union(*[R["designs"][d]["reasons_all_signals"] for d in R["designs"]]) & {"SKIPPED_NO_CASH", "SKIPPED_NO_SLOT", "SKIPPED_RANK", "BLOCKED_COIN_HELD"}) >= 1,
    [R["designs"][d]["reasons_all_signals"] for d in R["designs"]])

# ------------------------------------------------------------ Y9 destructive future overwrite (no price after the entry)
tau = TS("2025-02-01")
pack2 = tmp / "pack_future"; shutil.copytree(pack, pack2); rng = np.random.default_rng(99)
for f in (pack2 / "hourly").glob("*.csv.gz"):
    x = pd.read_csv(f); t = pd.to_datetime(x["ts_utc_ms"], unit="ms", utc=True); m = t > tau
    for k in ("open", "high", "low", "close", "vol_quote", "vol_base"):
        x.loc[m, k] = x.loc[m, k] * rng.uniform(0.2, 5, m.sum())
    x.loc[m, "high"] = x.loc[m, ["open", "high", "low", "close"]].max(axis=1); x.loc[m, "low"] = x.loc[m, ["open", "high", "low", "close"]].min(axis=1)
    with gzip.open(f, "wt") as fh: x.to_csv(fh, index=False)
fx = (R["designs"]["D-D1"]["daily_thresholds"]["RVOL_d_P75"], R["designs"]["D-D1"]["daily_thresholds"]["stop_d_P90"])
Ra = E.run(pack, thr_syn, pack / "ledger.csv", _daily_fixed=fx); Rb = E.run(pack2, thr_syn, pack / "ledger.csv", _daily_fixed=fx)
def dec(Rx, d):
    o = Rx["_sig"][d]["ok"]
    return sorted((cn, h, p, f) for cn, h, p, f in zip(o["coin"], o["entry_hour"], o["portfolio"], o["fill"]) if h + pd.Timedelta(hours=1) <= tau)
ok9 = all(dec(Ra, d) == dec(Rb, d) for d in R["designs"]) and all(dec(Ra, d) == dec(R, d) for d in ("D-H1", "D-H2"))
rec("Y9 prices after tau changed: every portfolio decision and fill check at entry hours before tau unchanged", ok9, [len(dec(Ra, d)) for d in R["designs"]])

# ------------------------------------------------------------ Y10 determinism; no price / return field; the stored json
o1, o2 = tmp / "o1", tmp / "o2"
E.main(o1, pack, thr_syn, pack / "ledger.csv"); E.main(o2, pack, thr_syn, pack / "ledger.csv")
b1 = (o1 / "exp4_counts.json").read_bytes(); txt = b1.decode()
rec("Y10a two runs byte-identical; no private field stored", b1 == (o2 / "exp4_counts.json").read_bytes() and '"_sig"' not in txt)
rec("Y10b output holds no price / return field", not any(k in txt for k in ('"open"', '"close"', '"pnl"', '"return"', "last_trade_price", '"alloc"')))

n_fail = sum(not r["pass"] for r in res)
print(f"{len(res) - n_fail}/{len(res)} passed")
if len(sys.argv) > 1: pathlib.Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
sys.exit(1 if n_fail else 0)
