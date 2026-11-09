"""Strategy Plan v0.1.3 (approved; review record docs/STRATEGY_PLAN_REVIEW_RECORD.md). Spot, long-only, NO orders.
Point-in-time weekly simulation on Development (selection of 1 of 4 variants) and, once, on Validation (gate).

python3 -I lab/strategy.py dev <out_dir>          Development: 4 variants + B1/B2/B3, all capitals, fees, scenarios
python3 -I lab/strategy.py val <out_dir> <sel>    Validation: ONLY the frozen selected variant (selection json) + baselines

Conventions (plan §0.1, §0.2, §1, §2):
  decision day d (00:00 UTC) every 7 days; signal from frozen FD features known at d over P1-eligible coins (ranks among
  eligible coins with a value, FD definition); tradeable = eligible AND reference price AND half-spread AND DV30_med.
  reference price = close_asof(d) (last traded close before d) — a REFERENCE PROXY, not an executable price.
  cost per traded notional = fee + half-spread (Corwin-Schultz, hours d-30..d-1, consecutive traded hours, median,
  clipped at 0, >= 360 pairs); fee 0.10 % per side = conservative taker assumption (0.20 % sensitivity; 0 = gross).
  position cap = 1 % of DV30_med(d) for strategy AND baselines; excess stays in cash. Only weight differences trade.
  holding period [d, d+7): value at close_asof(d+7); delisting cut in (d, d+7) -> U9b forced exit at last_trade_price
  minus fee and half-spread (proceeds idle as cash); no trade on day d+6 -> last traded close inside the period
  (counted as STALE_MARK). The final week liquidates everything with costs (all portfolios alike).
  B1 equal weight over ALL tradeable eligible coins; B2 BTC buy-and-hold (cap + costs, entry and final exit); B3 cash.
Statistics: weekly net excess over B1; Newey-West lag 0 one-sided p (mean > 0); circular block bootstrap with
  block = 1 week (= max(7, h) days), 2000 resamples, seed 20260108, one-sided p = share of resampled means <= 0.
Selection (Development, S3): highest mean weekly net excess over B1 at the gating capital and fee 0.10 %;
  tie -> lower mean turnover -> Top 10. Gate (Validation, S6): both one-sided p <= 0.05 at 0.10 %, mean > 0 at 0.20 %;
  RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE if the total net return <= 0.
"""
import sys, json, math, pathlib, hashlib, warnings, datetime as dt
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import fd1 as FD
from lab import fd2 as F2
from lab.segment_loader import SegmentGuard, GuardError
warnings.filterwarnings("ignore", category=RuntimeWarning)

LAB = FF.LAB
FEES = {"fee_0.10": 0.0010, "fee_0.20": 0.0020, "gross": None}          # gross = no fee AND no spread
CAPITALS = (1_000.0, 10_000.0, 100_000.0)
CAP_SHARE = 0.01
VARIANTS = {"A_N10": ("A", 10), "A_N20": ("A", 20), "B_N10": ("B", 10), "B_N20": ("B", 20)}
SIGNAL_B = (("F07", -1), ("F10", -1), ("F20", 1), ("F21", -1))
MIN_PAIRS = 360
HOLD = 7
SEED, NBOOT = 20260108, 2000
BTC = "BTC-USDT"
K = 3 - 2 * math.sqrt(2)


# ---------------------------------------------------------------- inputs per decision day
def half_spread(Hi, Lo, i):
    """Corwin-Schultz half-spread for day index i (hours of days i-30 .. i-1), per series; NaN if < 360 pairs."""
    h = Hi.values[(i - 30) * 24:i * 24]; l = Lo.values[(i - 30) * 24:i * 24]
    if i < 30:
        return np.full(Hi.shape[1], np.nan)
    h0, h1, l0, l1 = h[:-1], h[1:], l[:-1], l[1:]
    ok = ~(np.isnan(h0) | np.isnan(h1) | np.isnan(l0) | np.isnan(l1))
    with np.errstate(all="ignore"):
        beta = np.log(h0 / l0) ** 2 + np.log(h1 / l1) ** 2
        gamma = np.log(np.maximum(h0, h1) / np.minimum(l0, l1)) ** 2
        alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / K - np.sqrt(gamma / K)
        S = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    S = np.where(ok, S, np.nan)
    n = ok.sum(0)
    med = np.nanmedian(S, 0)
    return np.where(n >= MIN_PAIRS, np.maximum(med, 0.0) / 2, np.nan)


_SC = {}


def scores(F, E, i, kind):
    """higher = better; ranks among ELIGIBLE coins with a value on day i (FD definition)."""
    key = (id(F), id(E), i, kind)
    if key not in _SC:
        _SC[key] = _scores(F, E, i, kind)
    return _SC[key]


def _scores(F, E, i, kind):
    e = E.values[i]
    if kind == "A":
        x = pd.Series(np.where(e, F["F07"].values[i], np.nan))
        return (-x).rank(pct=True).values
    rs = []
    for f, sgn in SIGNAL_B:
        x = pd.Series(np.where(e, F[f].values[i], np.nan))
        rs.append((sgn * x).rank(pct=True).values)
    R = np.vstack(rs)
    return np.where(np.isnan(R).any(0), np.nan, R.mean(0))


class Inputs:
    def __init__(self, Hh, U, groups, fe, F, guard, entry_start, entry_end, seg_end, start_rule):
        self.S = list(Hh["close"].columns); self.nS = len(self.S)
        self.lc = F2.last_close(Hh).values
        self.Hh, self.U, self.fe, self.F, self.guard = Hh, U, fe, F, guard
        self._hs = {}; self._mark = {}
        self.M = FD.masks(U, groups)
        self.seg_end, self.entry_end = seg_end, entry_end
        days = FF.DAYS
        cand = [i for i in range(len(days)) if entry_start <= days[i] < entry_end]
        if start_rule == "first_20_B":                                       # Development: first day with >= 20 B-tradeable coins
            st = None
            for i in cand:
                if self.tradeable(i, "B", "P1").sum() >= 20:
                    st = i; break
            cand = [i for i in cand if i >= st]
        self.rebal = cand[::HOLD]
        for i in self.rebal:                                                  # H2 + T5 for every holding period
            guard.check_outcome(days[i].to_pydatetime(), dt.timedelta(days=HOLD))
        self.cut = {}
        for s, r in fe.iterrows():
            if s in self.S:
                if r["status"] != "PRICED" or r["minutes_last_trade_to_cut"] > 60:
                    raise GuardError(f"STOP: unpriceable forced exit {s}")
                self.cut[self.S.index(s)] = (r["cut"], float(r["last_trade_price"]))

    def hs(self, i):
        if i not in self._hs:
            self._hs[i] = half_spread(self.Hh["high"], self.Hh["low"], i)
        return self._hs[i]

    def ref(self, i):
        return self.lc[i - 1] if i >= 1 else np.full(self.nS, np.nan)

    def dv30(self, i, scen):
        return self.U[scen]["DV30_med"].values[i].astype(float)

    def tradeable(self, i, kind, scen):
        E = self.M[scen]
        ok = E.values[i] & ~np.isnan(self.ref(i)) & ~np.isnan(self.hs(i)) & ~np.isnan(self.dv30(i, scen))
        if kind in ("A", "B"):
            ok &= ~np.isnan(scores(self.F, E, i, kind))
        return ok


# ---------------------------------------------------------------- simulation
def select(inp, i, kind, N, scen):
    ok = inp.tradeable(i, kind, scen)
    if kind == "B1":
        return np.where(ok)[0]
    if kind == "B2":
        j = inp.S.index(BTC)                                                  # BTC: needs a reference price and a spread
        return np.array([j]) if (not np.isnan(inp.ref(i)[j]) and not np.isnan(inp.hs(i)[j])) else np.array([], int)
    sc = scores(inp.F, inp.M[scen], i, kind)
    idx = np.where(ok)[0]
    order = sorted(idx, key=lambda j: (-sc[j], inp.S[j]))
    return np.array(order[:N], int)


def simulate(inp, kind, N, capital, fee, scen):
    """weekly records for one portfolio; kind in A, B, B1, B2, B3."""
    days = FF.DAYS
    gross = fee is None
    fee = 0.0 if gross else fee
    q = {}; hs_buy = {}; cash = capital
    recs = []
    reb = inp.rebal
    for w, i in enumerate(reb):
        d = days[i]
        ref = inp.ref(i); hs = inp.hs(i) if not gross else np.zeros(inp.nS)
        # value holdings at the reference price (fallback marks counted earlier)
        V0 = cash + sum(q[j] * inp._mark[j] for j in q)
        if kind == "B3":
            recs.append({"week": w, "start": str(d.date()), "V_start": V0, "V_end": V0, "ret": 0.0, "turnover": 0.0,
                         "fees": 0.0, "spread_cost": 0.0, "n_held": 0, "forced_exits": 0, "stale_marks": 0, "cash_share": 1.0})
            continue
        if kind == "B2" and w > 0:
            tgt = {j: q[j] * inp._mark[j] for j in q}                        # buy and hold: no trades after week 0
            sel = np.array(list(q.keys()), int)
            fees = spc = turn = 0.0
        else:
            sel = select(inp, i, kind, N, scen)
            cap = CAP_SHARE * inp.dv30(i, scen)
            nsel = max(len(sel), 1) if kind in ("B1", "B2") else N
            H = {j: q[j] * inp._mark[j] for j in q}
            k = 1.0
            for _ in range(6):
                base = k * V0 / nsel
                tgt = {int(j): min(base, cap[j]) for j in sel}
                cost = 0.0
                for j in set(tgt) | set(H):
                    c = fee + (hs[j] if not np.isnan(hs[j]) else hs_buy.get(j, 0.0))
                    cost += abs(tgt.get(j, 0.0) - H.get(j, 0.0)) * c
                k = (V0 - cost) / V0 if V0 > 0 else 0.0
            fees = spc = turn = 0.0
            for j in set(tgt) | set(H):
                dlt = abs(tgt.get(j, 0.0) - H.get(j, 0.0))
                h_ = hs[j] if not np.isnan(hs[j]) else hs_buy.get(j, 0.0)
                fees += dlt * fee; spc += dlt * h_; turn += dlt
            cash = V0 - sum(tgt.values()) - fees - spc
            if cash < -1e-9 * max(V0, 1):
                raise AssertionError("negative cash")
            newq = {}
            for j, v in tgt.items():
                px = ref[j] if not np.isnan(ref[j]) else inp._mark[j]
                newq[j] = v / px
                hs_buy[j] = hs[j] if not np.isnan(hs[j]) else hs_buy.get(j, 0.0)
            q = newq
        # hold to d+7
        end = days[i] + pd.Timedelta(days=HOLD); ie = i + HOLD
        forced = stale = 0; endval = 0.0; marks = {}
        for j in list(q):
            ct = inp.cut.get(j)
            if ct is not None and d < ct[0] < end:
                cash += q[j] * ct[1] * (1 - fee - hs_buy.get(j, 0.0)); fees += q[j] * ct[1] * fee
                spc += q[j] * ct[1] * hs_buy.get(j, 0.0); forced += 1; del q[j]; continue
            px = inp.lc[ie - 1, j]
            if np.isnan(px):
                win = inp.lc[i:ie, j]; nn = win[~np.isnan(win)]
                px = nn[-1] if len(nn) else (ref[j] if not np.isnan(ref[j]) else inp._mark.get(j, np.nan))
                stale += 1
            marks[j] = px; endval += q[j] * px
        inp._mark = marks
        last = (w == len(reb) - 1)
        if last:                                                             # final liquidation, same rule for all
            for j in list(q):
                v = q[j] * marks[j]; h_ = hs_buy.get(j, 0.0)
                cash += v * (1 - fee - h_); fees += v * fee; spc += v * h_; turn += v
            q = {}; endval = 0.0
        V1 = cash + endval
        recs.append({"week": w, "start": str(d.date()), "V_start": V0, "V_end": V1, "ret": V1 / V0 - 1 if V0 > 0 else np.nan,
                     "turnover": turn / V0 if V0 > 0 else np.nan, "fees": fees, "spread_cost": spc, "n_held": len(q) if not last else 0,
                     "forced_exits": forced, "stale_marks": stale, "cash_share": cash / V1 if V1 > 0 else np.nan})
    return pd.DataFrame(recs)


def run_portfolio(inp, kind, N, capital, fee, scen):
    inp._mark = {}
    return simulate(inp, kind, N, capital, fee, scen)


# ---------------------------------------------------------------- statistics
def nw_one_sided(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; T = len(x)
    m = x.mean(); v = ((x - m) @ (x - m)) / T
    t = m / math.sqrt(v / T) if v > 0 else np.nan
    return t, (0.5 * math.erfc(t / math.sqrt(2)) if not np.isnan(t) else np.nan)


def boot_one_sided(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    rng = np.random.default_rng(SEED)
    starts = rng.integers(0, n, size=(NBOOT, n))                            # block = 1 week -> one start per draw
    means = x[starts].mean(1)
    return float((means <= 0).mean()), float(np.quantile(means, .025)), float(np.quantile(means, .975))


def summarize(rec, b1):
    r = rec.ret.values; ex = r - b1.ret.values
    eq = np.cumprod(1 + r); dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    t, p_nw = nw_one_sided(ex); p_bt, lo, hi = boot_one_sided(ex)
    sd = float(np.std(r, ddof=1))
    return {"weeks": len(r), "total_net_return": float(eq[-1] - 1), "annualised": float(eq[-1] ** (52 / len(r)) - 1),
            "mean_weekly": float(r.mean()), "weekly_vol": sd, "sharpe_ann": float(r.mean() / sd * math.sqrt(52)) if sd > 0 else np.nan,
            "max_drawdown": dd, "mean_excess_vs_B1": float(ex.mean()), "nw_t": t, "p_nw_one_sided": p_nw,
            "p_boot_one_sided": p_bt, "boot_ci95_low": lo, "boot_ci95_high": hi, "hit_rate_vs_B1": float((ex > 0).mean()),
            "mean_turnover": float(np.nanmean(rec.turnover.values)), "fees_total": float(rec.fees.sum()),
            "spread_total": float(rec.spread_cost.sum()), "forced_exits": int(rec.forced_exits.sum()),
            "stale_marks": int(rec.stale_marks.sum()), "mean_cash_share": float(np.nanmean(rec.cash_share.values))}


def run_all(inp, kinds, scens=("P1", "S50k", "S250k")):
    rows, weekly = [], {}
    for scen in scens:
        for cap in CAPITALS:
            for fk, fee in FEES.items():
                b1 = run_portfolio(inp, "B1", 0, cap, fee, scen)
                port = {"B1": b1, "B2": run_portfolio(inp, "B2", 1, cap, fee, scen), "B3": run_portfolio(inp, "B3", 0, cap, fee, scen)}
                for name in kinds:
                    kind, N = VARIANTS[name]; port[name] = run_portfolio(inp, kind, N, cap, fee, scen)
                for name, rec in port.items():
                    s = summarize(rec, b1); s.update(scenario=scen, capital=cap, fee=fk, portfolio=name); rows.append(s)
                    weekly[(scen, cap, fk, name)] = rec
    return pd.DataFrame(rows), weekly


def choose(summary, gating_capital):
    """S3 on Development: highest mean weekly net excess over B1 at the gating capital, fee 0.10 %, P1;
    tie -> lower mean turnover -> Top 10."""
    s = summary[(summary.scenario == "P1") & (summary.capital == gating_capital) & (summary.fee == "fee_0.10") & summary.portfolio.isin(list(VARIANTS))]
    s = s.assign(N=[VARIANTS[p][1] for p in s.portfolio]).sort_values(["mean_excess_vs_B1", "mean_turnover", "N"], ascending=[False, True, True])
    return s.iloc[0].portfolio


def gate(summary, sel, capitals):
    out = {}
    for cap in capitals:
        g = summary[(summary.scenario == "P1") & (summary.capital == cap) & (summary.portfolio == sel)].set_index("fee")
        a, b = g.loc["fee_0.10"], g.loc["fee_0.20"]
        ok = bool(a.p_nw_one_sided <= 0.05 and a.p_boot_one_sided <= 0.05 and b.mean_excess_vs_B1 > 0)
        out[str(int(cap))] = {"PASS": ok, "p_nw": float(a.p_nw_one_sided), "p_boot": float(a.p_boot_one_sided),
                              "mean_excess_fee_0.10": float(a.mean_excess_vs_B1), "mean_excess_fee_0.20": float(b.mean_excess_vs_B1),
                              "total_net_return_fee_0.10": float(a.total_net_return),
                              "flag": "RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE" if (ok and a.total_net_return <= 0) else ""}
    return out


# ---------------------------------------------------------------- entry points
def dev_inputs():
    Hh, U, groups = FF.load_pack(); fe = F2.load_forced()
    F = FF.features(Hh, U["P1"])
    return Inputs(Hh, U, groups, fe, F, SegmentGuard("development"), FF.DAYS[0], F2.ENTRY_END, FF.DEV_END, "first_20_B")


def val_inputs_ctx():
    from lab import val as V
    Hh, U, groups, fe = V.load_pack()
    ctx = V.validation_context(); ctx.__enter__()
    F = FF.features(Hh, U["P1"])
    inp = Inputs(Hh, U, groups, fe, F, V.VGUARD, V.V_ES, V.V_EE, V.V_DE, "fixed_start")
    return inp, ctx


def main():
    if sys.argv[1] == "select":                                               # S3: python3 lab/strategy.py select <dev_summary.csv> <gating_capital> <out.json>
        summ = pd.read_csv(sys.argv[2]); cap = float(sys.argv[3])
        sel = choose(summ, cap)
        json.dump({"selected": sel, "gating_capital": cap, "rule": "max mean weekly net excess vs B1 (P1, fee 0.10 %); tie: lower turnover, then Top 10",
                   "dev_summary_sha256": hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).hexdigest()}, open(sys.argv[4], "w"), indent=1)
        print(sel); return
    mode, out = sys.argv[1], pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    FF.catalogue()
    if mode == "dev":
        inp = dev_inputs()
        summ, weekly = run_all(inp, list(VARIANTS))
    else:
        sel = json.loads(pathlib.Path(sys.argv[3]).read_text())["selected"]
        inp, ctx = val_inputs_ctx()
        try:
            summ, weekly = run_all(inp, [sel])
        finally:
            ctx.__exit__(None, None, None)
    summ.to_csv(out / f"strategy_summary_{mode}.csv", index=False)
    pd.concat([r.assign(scenario=k[0], capital=k[1], fee=k[2], portfolio=k[3]) for k, r in weekly.items()]).to_csv(
        out / f"strategy_weekly_{mode}.csv.gz", index=False, compression={"method": "gzip", "mtime": 0}, float_format="%.12g")
    meta = {"mode": mode, "rebalance_days": [str(FF.DAYS[i].date()) for i in inp.rebal][:1] + [str(FF.DAYS[inp.rebal[-1]].date())],
            "weeks": len(inp.rebal)}
    json.dump(meta, open(out / f"strategy_meta_{mode}.json", "w"), indent=1)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
