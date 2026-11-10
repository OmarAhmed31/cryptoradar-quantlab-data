"""Experiment 3 counts run (plan docs/EXP3_DESIGN_SELECTION_PLAN_v0.3.md, approved; addendum decisions recorded in
docs/EXP3_COUNTS_CODE_ADDENDUM_v0.2.md + v0.3: A1-A4 approved; A4 calendar rule). Development only, ONE run.

NO forward return, NO outcome, NO stop/target result, NO price after the entry.
Inputs: the Development pack, the frozen hourly thresholds (sha256 checked), the U9b delisting ledger (timestamps and
status only: the price column is never read). Allowed imports: numpy, pandas, stdlib, lab.fd_features,
lab.thresholds (frozen, outcome-free), lab.segment_loader, lab.universe_crypto_only.

python3 -I lab/exp3_counts.py <out_dir> [<pack_dir>] [<thresholds.json>] [<ledger.csv>]

Conventions (all fixed before any count):
  hourly signal bar t = [t, t+1h), known at t+1h, entry hour = t+1h                      (Spec v0.1.3 §5.5)
  daily signal day D, known at D+1 00:00, entry hour = D+1 00:00                       (plan §2.1)
  an entry hour is executable iff the coin's hourly bar there is traded (>= 1 traded minute; rule B: the bar's open
  is the open of its first traded minute = the fill price)
  deadline_max = entry hour + 1h + 7 days (latest possible 7-day deadline)
  exit bar = first traded bar of the coin with label >= deadline_max (all its minutes are after any deadline)
  block_end = max(sig_t + 7d + 2h, min(exit bar + 1h, segment end)); segment end if there is no exit bar   (plan §3b)
  delisting cut in [entry hour, block_end): the trade ends at the cut                                     (plan §3c)
  counted iff the exit is guaranteed inside H_max (720 h from the entry hour) and inside the segment       (plan §3d)
  a new entry needs entry hour >= the previous exit; same coin: hourly window start >= its last exit end,
  D-D1 window start date >= exit date + 1 calendar day (addendum v0.3)
"""
import sys, json, bisect, hashlib, pathlib, math
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import thresholds as TH
from lab.segment_loader import SEGMENTS
from lab.universe_crypto_only import is_excluded

REPO = pathlib.Path(__file__).resolve().parents[1]
THR_FILE = "out/thresholds/run_v1/thresholds.json"
THR_SHA = "5dc38aa95599526c17ad42fc98aa37a87abdb10d84e071eb959805fd11758c5f"
LEDGER_FILE = "out/research_protocol/v1.2/forced_exit_reference.csv"
LEDGER_COLS = ["series", "cut_utc", "status", "minutes_last_trade_to_cut", "max_stale_minutes_rule"]   # never the price

HOUR = pd.Timedelta(hours=1)
HOLD = pd.Timedelta(days=7)                    # Spec 7-day time exit
BLOCK_MIN = pd.Timedelta(days=7, hours=2)      # plan §3b uniform minimum
H_MAX = pd.Timedelta(hours=720)                # Protocol v1.2
W_H = TH.W                                     # 168-bar hourly range window
D_WIN, D_MINW, D_A1_WIN, D_A1_MIN = 20, 10, 180, 90     # plan §2.1
P_RVOL_D, P_STOP_D = 0.75, 0.90                          # plan §2 (same method as v0.3.2)
MIN_L = 100                                              # U7
CONDITIONS = {"D-H1": 4, "D-H2": 5, "D-D1": 4}           # plan §4 (entry conditions only)
PREFERENCE = ["D-D1", "D-H1", "D-H2"]                    # fewest conditions; D-D1 wins the tie with D-H1
# Addendum decisions (reviewer, approved; fixed, never changed after the counts are seen):
APPLY_HS_SKIP = True             # A2: P1 skips a trade whose Corwin-Schultz half-spread cannot be estimated (days d-30..d-1
                                 #     of the entry day d, >= 360 pairs: the P1 window and minimum)
APPLY_ENTRY_STOP_SKIP = True     # A3: P1 skips at entry if (fill - stop)/fill > the frozen stop limit; fill = the open of the
                                 #     first traded minute of the entry hour (= the hourly open, rule B); no later candle
SELECT_ON = "L_greedy"           # A1: acceptance = L_greedy >= 100; L_worst reported beside it, never an acceptance rule
DEFINITIONS = {
    "L_greedy": "estimate of completed trades under sequential blocking (every trade held to its latest end); "
                "NOT a guaranteed minimum; the acceptance measure (L_greedy >= 100)",
    "L_worst": "guaranteed minimum under the stated assumptions (any exit time, any tie, a superset of re-entry cases); "
               "conservative, often uninformative; reported only, never an acceptance rule",
    "no_guarantee": "a design passing L_greedy >= 100 is NOT guaranteed 100 completed trades",
    "same_coin_reentry": "hourly: the signal's full 168-h range window must start at or after the coin's last exit (Spec 5.5); "
                         "D-D1: window_start_date >= exit_date + 1 calendar day (20 full calendar days after the exit day: "
                         "exit on day X -> earliest signal day X+21); a fixed signal-management rule, not derived from data",
}
MIN_PAIRS = 360
_K = 3 - 2 * math.sqrt(2)


def _q(x, p):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return float(np.quantile(x, p)) if len(x) else float("nan")


def load_thresholds(path):
    b = pathlib.Path(path).read_bytes()
    if hashlib.sha256(b).hexdigest() != THR_SHA:
        raise SystemExit("frozen thresholds.json sha256 mismatch")
    return json.loads(b)["thresholds"]                     # exact floats, never the rounded display values


def load_ledger(path):
    d = pd.read_csv(path, usecols=LEDGER_COLS)
    out = {}
    for r in d.itertuples(index=False):
        priced = (r.status == "PRICED") and float(r.minutes_last_trade_to_cut) <= float(r.max_stale_minutes_rule)
        out[r.series] = (pd.Timestamp(r.cut_utc, tz="UTC"), bool(priced))
    return out


def trend_states(st, T):
    """same rule as the frozen thresholds cascade: Transition = trend changed in the last 5 days, or Uncertain."""
    trend = pd.Series("SIDEWAYS", index=st["index"].index)
    trend[(st["index"] > st["ma50"]) & (st["r20"] > T["R1_bull_r20_P67"])] = "BULL"
    trend[(st["index"] < st["ma50"]) & (st["r20"] < T["R2_bear_r20_P33"])] = "BEAR"
    trend[st["r20"].isna() | st["ma50"].isna()] = "UNCERTAIN"
    changed = (trend != trend.shift(1)).astype(int).rolling(5, min_periods=1).sum() > 0
    changed.iloc[0] = False
    return trend, changed | (trend == "UNCERTAIN")


def half_spread_day(Hi, Lo, i):
    """Corwin-Schultz half-spread for day index i (hours of days i-30 .. i-1), per series; NaN if < 360 pairs.
    Same formula as the frozen strategy cost model (not imported: outcome module)."""
    if i < 30:
        return np.full(Hi.shape[1], np.nan)
    h = Hi.values[(i - 30) * 24:i * 24]; l = Lo.values[(i - 30) * 24:i * 24]
    h0, h1, l0, l1 = h[:-1], h[1:], l[:-1], l[1:]
    ok = ~(np.isnan(h0) | np.isnan(h1) | np.isnan(l0) | np.isnan(l1))
    with np.errstate(all="ignore"):
        beta = np.log(h0 / l0) ** 2 + np.log(h1 / l1) ** 2
        gamma = np.log(np.maximum(h0, h1) / np.minimum(l0, l1)) ** 2
        alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / _K - np.sqrt(gamma / _K)
        S = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
        S = np.where(ok, S, np.nan)
        med = np.nanmedian(S, 0)
    return np.where(ok.sum(0) >= MIN_PAIRS, np.maximum(med, 0.0) / 2, np.nan)


# ------------------------------------------------------------------ signals
def tight(width, win, minp):
    """coin-relative A1: width_t <= the 25th percentile of the coin's own widths at t-win .. t-1 (>= minp values)."""
    return width <= width.rolling(win, min_periods=minp).quantile(0.25).shift(1)


def hourly_designs(Hh, U, T, trans, trend, hv):
    ind = TH.indicators(Hh, U, None)
    C = ind["close"]
    A = TH.allowed_mask(U, None, C.index).reindex(columns=C.columns).fillna(False)
    width = ind["R_high"] / ind["R_low"] - 1
    a1 = tight(width, 180 * 24, 90 * 24)
    day = C.index.floor("D")
    abst = pd.DataFrame(np.repeat(trans.reindex(day).fillna(True).astype(bool).values[:, None], C.shape[1], 1), index=C.index, columns=C.columns)
    steps = [("H_eligible", A & C.notna() & (ind["n_prior"] >= TH.MINW)), ("B_breakout", C > ind["R_high"]), ("A1_tight", a1),
             ("E3_rvol", ind["rvol"] >= T["E3_rvol_P75"]), ("E5_stop", ind["stop"] <= T["E5_stop_P90"])]
    out = {}
    for name, extra in (("D-H1", []), ("D-H2", [("E4_clv", ind["clv"] >= T["E4_clv_median"])])):
        m = None; casc = []
        for k, cond in steps + extra + [("not_transition", ~abst)]:
            m = cond.fillna(False) if m is None else (m & cond.fillna(False)); casc.append((k, int(m.values.sum())))
        r, c = np.nonzero(m.values)
        t = C.index[r]
        sig = pd.DataFrame({"coin": C.columns[c], "sig_t": t, "entry_hour": t + HOUR, "row_entry": r + 1, "col": c,
                            "stop_level": ind["R_low"].values[r, c], "win_start": t - W_H * HOUR,
                            "trend": trend.reindex(t.floor("D")).values, "high_vol": hv.reindex(t.floor("D")).fillna(False).astype(bool).values})
        out[name] = {"cascade": casc, "signals": sig, "stop_limit": T["E5_stop_P90"]}
    return out


def daily_bars(Hh):
    g = lambda k: Hh[k].groupby(Hh[k].index.floor("D"))
    hi = g("high").max().reindex(FF.DAYS); lo = g("low").min().reindex(FF.DAYS)
    cl = g("close").last().reindex(FF.DAYS)
    vol = Hh["vol_quote"].where(Hh["close"].notna()).groupby(Hh["close"].index.floor("D")).sum(min_count=1).reindex(FF.DAYS)
    return hi, lo, cl, vol


def daily_design(Hh, U, trans, trend, hv, fixed=None):
    hi, lo, cl, vol = daily_bars(Hh)
    traded = cl.notna()
    ntr = traded.astype(float).rolling(D_WIN, min_periods=1).sum().shift(1)
    RH = hi.where(traded).rolling(D_WIN, min_periods=D_MINW).max().shift(1)
    RL = lo.where(traded).rolling(D_WIN, min_periods=D_MINW).min().shift(1)
    width = RH / RL - 1
    a1 = tight(width, D_A1_WIN, D_A1_MIN)
    rvol = vol / vol.where(traded).rolling(D_WIN, min_periods=D_MINW).median().shift(1)
    stop = (cl - RL) / cl
    E = U["P1"]["eligible"].copy(); E.loc[:, [c for c in E.columns if is_excluded(c)]] = False
    elig_next = E.reindex(index=FF.DAYS, columns=cl.columns).shift(-1).fillna(False).astype(bool)   # P1-eligible on D+1
    base = traded & elig_next & (ntr >= D_MINW)
    BO = base & (cl > RH)
    P75 = _q(rvol.values[BO.values & rvol.notna().values], P_RVOL_D)
    P90 = _q(stop.values[BO.values & stop.notna().values], P_STOP_D)
    if fixed is not None:                                   # TESTS ONLY (future-overwrite test); main() never passes it
        P75, P90 = fixed
    nxt = FF.DAYS + pd.Timedelta(days=1)
    abst = pd.DataFrame(np.repeat(trans.reindex(nxt).fillna(True).astype(bool).values[:, None], cl.shape[1], 1), index=FF.DAYS, columns=cl.columns)
    m = base; casc = [("D_eligible", int(m.values.sum()))]
    for k, cond in (("B_d_breakout", cl > RH), ("A1_d_tight", a1), ("RVOL_d", rvol >= P75), ("stop_d", stop <= P90), ("not_transition", ~abst)):
        m = m & cond.fillna(False); casc.append((k, int(m.values.sum())))
    r, c = np.nonzero(m.values)
    D = FF.DAYS[r]
    sig = pd.DataFrame({"coin": cl.columns[c], "sig_t": D + pd.Timedelta(days=1), "entry_hour": D + pd.Timedelta(days=1),
                        "row_entry": (r + 1) * 24, "col": c, "stop_level": RL.values[r, c], "win_start": D - pd.Timedelta(days=D_WIN),
                        "trend": trend.reindex(D + pd.Timedelta(days=1)).values, "high_vol": hv.reindex(D + pd.Timedelta(days=1)).fillna(False).astype(bool).values})
    pop = {"n": int(BO.values.sum()), "n_rvol": int((BO & rvol.notna()).values.sum()), "n_stop": int((BO & stop.notna()).values.sum()),
           "share_kept_rvol": float(np.mean(rvol.values[BO.values & rvol.notna().values] >= P75)) if BO.values.any() else float("nan"),
           "share_kept_stop": float(np.mean(stop.values[BO.values & stop.notna().values] <= P90)) if BO.values.any() else float("nan")}
    return {"cascade": casc, "signals": sig, "stop_limit": P90, "derived": {"RVOL_d_P75": P75, "stop_d_P90": P90}, "population": pop}


# ------------------------------------------------------------------ executability and trade windows (timestamps only)
def executable(sig, Hh, stop_limit, seg):
    es, ee = pd.Timestamp(seg[2]), pd.Timestamp(seg[3])
    C, O = Hh["close"].values, Hh["open"].values
    n = C.shape[0]; hs_cache = {}
    reason = []
    for s in sig.itertuples(index=False):
        if not (es <= s.entry_hour < ee) or s.row_entry >= n:
            reason.append("PAST_ENTRY_CUT"); continue
        if np.isnan(C[s.row_entry, s.col]):
            reason.append("NOT_EXECUTED"); continue
        if APPLY_HS_SKIP:
            di = s.row_entry // 24
            if di not in hs_cache:
                hs_cache[di] = half_spread_day(Hh["high"], Hh["low"], di)
            if np.isnan(hs_cache[di][s.col]):
                reason.append("SKIPPED_NO_HALF_SPREAD"); continue
        if APPLY_ENTRY_STOP_SKIP:
            fill = O[s.row_entry, s.col]
            if (fill - s.stop_level) / fill > stop_limit:
                reason.append("SKIPPED_WIDE_STOP_AT_ENTRY"); continue
        reason.append("EXECUTABLE")
    return reason


def trade_windows(sig, traded_times, ledger, seg_end):
    """end time, counted flag, reason and exit reference for each executable signal; no price is used.
    exit reference = the time whose UTC day is the exit day: the exit bar label (the time-exit fill lies inside that
    hour, so inside that day), the cut, or the end when there is no exit."""
    ends, cnt, why, xref = [], [], [], []
    for s in sig.itertuples(index=False):
        tt = traded_times[s.coin]
        dl = s.entry_hour + HOUR + HOLD
        k = bisect.bisect_left(tt, dl.value)
        xb = pd.Timestamp(tt[k], tz="UTC") if k < len(tt) else None
        tail = min(xb + HOUR, seg_end) if xb is not None else seg_end
        block_end = max(s.sig_t + BLOCK_MIN, tail)
        cut = ledger.get(s.coin)
        if cut is not None and s.entry_hour <= cut[0] < block_end:
            ends.append(cut[0]); xref.append(cut[0])
            ok = cut[1] and cut[0] < s.entry_hour + H_MAX
            cnt.append(ok); why.append("FORCED_EXIT_PRICED" if ok else ("UNPRICEABLE_FORCED_EXIT" if not cut[1] else "EXCLUDED_HMAX"))
            continue
        ends.append(block_end); xref.append(xb if (xb is not None and xb + HOUR <= seg_end) else block_end)
        if xb is not None and xb + HOUR <= min(s.entry_hour + H_MAX, seg_end):
            cnt.append(True); why.append("TIME_EXIT")
        elif (xb is not None and xb + HOUR > s.entry_hour + H_MAX) or (xb is None and s.entry_hour + H_MAX <= seg_end):
            cnt.append(False); why.append("EXCLUDED_HMAX")
        else:
            cnt.append(False); why.append("OPEN_AT_SEGMENT_END")
    return ends, cnt, why, xref


DAY_NS = 86_400 * 10 ** 9


def reentry_from(xref_ns, end_ns, day_ns=None):
    """earliest allowed START of a same-coin signal's range window after that coin's exit.
    hourly designs (day_ns None): the trade's end (Spec §5.5: a new full 168-hour window after the exit; unchanged);
    D-D1 (addendum v0.3 A4): window_start_date >= exit_date + 1 calendar day, i.e. the UTC midnight after the exit day.
    Exit on day X (any hour) -> days X+1 .. X+20 form the window -> earliest signal day X+21, entry X+22."""
    if day_ns is None:
        return end_ns
    return (xref_ns // day_ns) * day_ns + day_ns


# ------------------------------------------------------------------ L (plan greedy) and L_worst (rigorous bound)
def _sorted(X):
    return sorted(X, key=lambda s: (s["entry"], s["coin"]))


def l_greedy(X, seg_start):
    """plan v0.3 §3: estimate under sequential blocking; every taken trade held to its latest end; ties by coin name.
    NOT a guaranteed minimum (addendum A1)."""
    free, last = seg_start.value, {}
    out = {"taken": 0, "L_greedy": 0, "blocked_open_trade": 0, "blocked_same_coin_window": 0}
    reasons, taken = {}, []
    for s in _sorted(X):
        if s["entry"] < free:
            out["blocked_open_trade"] += 1; continue
        if s["coin"] in last and s["ws"] < last[s["coin"]]:
            out["blocked_same_coin_window"] += 1; continue
        out["taken"] += 1; out["L_greedy"] += int(s["c"]); reasons[s["why"]] = reasons.get(s["why"], 0) + 1
        free = s["end"]; last[s["coin"]] = s["rf"]; taken.append(s["i"])
    out["taken_by_reason"] = dict(sorted(reasons.items()))
    return out, taken


def l_worst(X, seg_start, day=None):
    """guaranteed minimum under the stated assumptions: min over every possible exit time (any time in (entry hour, end];
    an early exit is a completed trade), every tie choice, and a superset of the same-coin re-entry possibilities.
    Reported beside L_greedy only; never an acceptance rule (addendum A1)."""
    f = (lambda e: e) if day is None else (lambda e: (e // day) * day + day)    # re-entry threshold after an exit at e
    S = _sorted(X); n = len(S)
    ent = [s["entry"] for s in S]
    by_coin = {}
    for i, s in enumerate(S):
        by_coin.setdefault(s["coin"], []).append(s["ws"])
    for v in by_coin.values():
        v.sort()
    V = [0] * n

    def nxt(ci, fi, e, fe):
        """fe = re-entry threshold of the current coin after exit e; fi = f(entry): any older exit is <= the entry."""
        k = bisect.bisect_left(ent, e); out = set()
        while k < n:
            s = S[k]
            if s["coin"] == ci and s["ws"] < fe:
                k += 1; continue                                   # surely blocked by the current trade's exit
            free = ci is None or s["coin"] == ci or s["ws"] >= fi   # other coins: an older exit is <= the entry
            if free:
                h = ent[k]; j = k
                while j < n and ent[j] == h:
                    if not (S[j]["coin"] == ci and S[j]["ws"] < fe):
                        out.add(j)
                    j += 1
                return out
            out.add(k); k += 1                                      # maybe blocked: the adversary may take it or not
        return out

    def W(ci, fi, e, fe):
        o = nxt(ci, fi, e, fe)
        return min(V[j] for j in o) if o else 0

    for i in range(n - 1, -1, -1):
        s = S[i]; ei, end = s["entry"], s["end"]
        th = set(ent[bisect.bisect_right(ent, ei):bisect.bisect_right(ent, end)])
        ws = by_coin[s["coin"]]
        wsr = ws[bisect.bisect_right(ws, ei):bisect.bisect_right(ws, end)]
        th |= set(wsr) | {w - 1 for w in wsr if w - 1 > ei}         # daily: eligibility flips just below a window start
        early = [e for e in th if e < end] + [end]
        fi = f(ei)
        full = int(s["c"]) + W(s["coin"], fi, end, s["rf"])
        V[i] = min(full, 1 + min(W(s["coin"], fi, e, f(e)) for e in early))
    o = nxt(None, None, seg_start.value, None)
    return (min(V[j] for j in o) if o else 0), V


# ------------------------------------------------------------------ report helpers
def compose(sig, mask=None):
    s = sig if mask is None else sig[mask]
    per_coin = s.groupby("coin").size().sort_values(ascending=False)
    state = (s["trend"].astype(str) + np.where(s["high_vol"], "|HV", "")).value_counts().sort_index()
    month = s["sig_t"].dt.strftime("%Y-%m").value_counts().sort_index()
    return {"n": int(len(s)), "n_coins": int(per_coin.size), "max_per_coin": int(per_coin.max()) if len(per_coin) else 0,
            "per_coin": {k: int(v) for k, v in per_coin.items()}, "by_state": {k: int(v) for k, v in state.items()},
            "by_month": {k: int(v) for k, v in month.items()}}


def select(Ls):
    passing = [d for d in PREFERENCE if Ls[d] >= MIN_L]
    return passing[0] if passing else "STOP_INFEASIBLE"


def run(pack=FF.PACK, thr=None, ledger=None, _daily_fixed=None):
    pack = pathlib.Path(pack)
    T = load_thresholds(thr or REPO / THR_FILE)
    led = load_ledger(ledger or REPO / LEDGER_FILE)
    Hh, U, groups = FF.load_pack(pack)
    FF.assert_dev_only(Hh)
    seg = SEGMENTS["development"]; seg_start, seg_end = pd.Timestamp(seg[2]), pd.Timestamp(seg[1])
    ret, _, _ = TH.ew_index(Hh, U, groups)
    st = TH.states(ret)
    trend, trans = trend_states(st, T)
    designs = hourly_designs(Hh, U, T, trans, trend, st["high_vol"])
    designs["D-D1"] = daily_design(Hh, U, trans, trend, st["high_vol"], _daily_fixed)
    C = Hh["close"]
    traded_times = {c: C.index[C[c].notna().values].as_unit("ns").asi8 for c in C.columns}      # ns, like Timestamp.value
    res = {"designs": {}, "_sig": {}}
    Lg, Lw = {}, {}
    for name in ("D-H1", "D-H2", "D-D1"):
        d = designs[name]; sig = d["signals"].sort_values(["entry_hour", "coin"]).reset_index(drop=True)
        rs = executable(sig, Hh, d["stop_limit"], seg)
        sig["exec"] = rs
        ex = sig[sig["exec"] == "EXECUTABLE"].reset_index(drop=True)
        ends, cnt, why, xref = trade_windows(ex, traded_times, led, seg_end)
        dmode = DAY_NS if name == "D-D1" else None
        X = [{"i": i, "coin": r.coin, "entry": r.entry_hour.value, "end": e.value, "ws": r.win_start.value, "c": bool(c), "why": w,
              "rf": reentry_from(x.value, e.value, dmode)}
             for i, (r, e, c, w, x) in enumerate(zip(ex.itertuples(index=False), ends, cnt, why, xref))]
        g, taken = l_greedy(X, seg_start)
        w, _ = l_worst(X, seg_start, dmode)
        Lg[name], Lw[name] = g["L_greedy"], w
        tk_mask = np.isin(np.arange(len(ex)), taken)
        sig["end"], sig["c"], sig["why"] = None, None, None
        ix = np.where(sig["exec"].values == "EXECUTABLE")[0]
        sig.loc[ix, "end"] = pd.Series(ends, dtype=object).values
        sig.loc[ix, "c"] = pd.Series(cnt, dtype=object).values
        sig.loc[ix, "why"] = pd.Series(why, dtype=object).values
        res["_sig"][name] = sig                                  # in-memory only (tests); never written
        res["designs"][name] = {
            "conditions": CONDITIONS[name], "cascade": [[k, v] for k, v in d["cascade"]],
            "execution": dict(sorted(pd.Series(rs, dtype=object).value_counts().astype(int).to_dict().items())) if rs else {},
            "trade_window_reason_all_executable": dict(sorted(pd.Series(why, dtype=object).value_counts().astype(int).to_dict().items())) if why else {},
            "signals": compose(sig), "greedy_taken": compose(ex, tk_mask), "greedy": g, "L_greedy": g["L_greedy"], "L_worst": int(w)}
        if name == "D-D1":
            res["designs"][name]["daily_thresholds"] = d["derived"]; res["designs"][name]["daily_breakout_population"] = d["population"]
    res["definitions"] = DEFINITIONS
    res["selection"] = {"rule": "L_greedy >= 100, then fewest entry conditions, D-D1 wins the tie with D-H1; else STOP",
                        "select_on": SELECT_ON, "by_L_greedy": select(Lg), "by_L_worst": select(Lw),
                        "chosen": select(Lw if SELECT_ON == "L_worst" else Lg)}
    res["settings"] = {"APPLY_HS_SKIP": APPLY_HS_SKIP, "APPLY_ENTRY_STOP_SKIP": APPLY_ENTRY_STOP_SKIP, "SELECT_ON": SELECT_ON,
                       "hourly_thresholds_exact": {k: T[k] for k in ("E3_rvol_P75", "E4_clv_median", "E5_stop_P90", "R1_bull_r20_P67", "R2_bear_r20_P33")}}
    res["note"] = "opportunity counts and timestamp-derived bounds only; NO return, NO outcome, NO price after the entry"
    return res


def main(out_dir, pack=None, thr=None, ledger=None):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    pack = pathlib.Path(pack) if pack else FF.PACK
    res = run(pack, thr, ledger)
    res.pop("_sig")
    code = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in
            ("lab/exp3_counts.py", "lab/thresholds.py", "lab/fd_features.py", "lab/universe_crypto_only.py", "lab/segment_loader.py")}
    mf = pack / "PACK_MANIFEST.json"
    res["inputs"] = {"pack_manifest_sha256": hashlib.sha256(mf.read_bytes()).hexdigest() if mf.exists() else "",
                     "thresholds_sha256": THR_SHA,
                     "ledger_sha256": hashlib.sha256(pathlib.Path(ledger or REPO / LEDGER_FILE).read_bytes()).hexdigest()}
    res["code_sha256"] = code
    b = json.dumps(res, indent=1, sort_keys=True).encode()
    (out / "exp3_counts.json").write_bytes(b)
    print(hashlib.sha256(b).hexdigest())


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], *(a[1:] + [None] * (4 - len(a)))[:3])
