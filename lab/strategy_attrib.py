"""Per-asset contribution for one portfolio path (reviewer condition for the Validation run, 2026-11-09).
Descriptive only; it never changes the simulation, the selection or the gate.

contribution(asset, week) = q_asset * (end mark or forced-exit proceeds before costs) / V_start  -  value bought / V_start
   i.e. (position value at the end of the week - position value right after the rebalance) / V_start
The week's return = sum of asset contributions + cash change (fees, spread, liquidation costs) / V_start.
The path is recomputed from the frozen lab/strategy.py functions, and its weekly returns must equal
strategy.simulate() to 1e-9 (checked in attribution(); otherwise it raises).
Asset classes (fixed BEFORE the Validation run, by ticker, descriptive):
  fiat_stablecoin  USDC, PYUSD, USDG, USD1, EURT          gold_token  XAUT, PAXG
  staking_or_wrapped  STETH, BETH, JITOSOL               other  everything else (USTC included: it lost its peg in 2022)
"""
import sys, math, pathlib
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import strategy as ST

CLASSES = {"fiat_stablecoin": ("USDC", "PYUSD", "USDG", "USD1", "EURT"), "gold_token": ("XAUT", "PAXG"),
           "staking_or_wrapped": ("STETH", "BETH", "JITOSOL")}


def asset_class(series):
    base = series.split("-")[0]
    for k, v in CLASSES.items():
        if base in v:
            return k
    return "other"


def path(inp, kind, N, capital, fee, scen):
    """mirror of strategy.simulate() that also records positions; same arithmetic, same order."""
    days = FF.DAYS; gross = fee is None; fee = 0.0 if gross else fee
    q = {}; hs_buy = {}; cash = capital; mark = {}; weeks = []
    for w, i in enumerate(inp.rebal):
        d = days[i]; ref = inp.ref(i); hs = inp.hs(i) if not gross else np.zeros(inp.nS)
        V0 = cash + sum(q[j] * mark[j] for j in q)
        sel = ST.select(inp, i, kind, N, scen); cap = ST.CAP_SHARE * inp.dv30(i, scen)
        nsel = max(len(sel), 1) if kind in ("B1", "B2") else N
        H = {j: q[j] * mark[j] for j in q}; k = 1.0
        for _ in range(6):
            base = k * V0 / nsel
            tgt = {int(j): min(base, cap[j]) for j in sel}
            cost = sum(abs(tgt.get(j, 0.0) - H.get(j, 0.0)) * (fee + (hs[j] if not np.isnan(hs[j]) else hs_buy.get(j, 0.0)))
                       for j in set(tgt) | set(H))
            k = (V0 - cost) / V0 if V0 > 0 else 0.0
        fees = spc = 0.0
        for j in set(tgt) | set(H):
            dlt = abs(tgt.get(j, 0.0) - H.get(j, 0.0)); h_ = hs[j] if not np.isnan(hs[j]) else hs_buy.get(j, 0.0)
            fees += dlt * fee; spc += dlt * h_
        cash = V0 - sum(tgt.values()) - fees - spc
        q = {}
        for j, v in tgt.items():
            q[j] = v / ref[j]; hs_buy[j] = hs[j] if not np.isnan(hs[j]) else hs_buy.get(j, 0.0)
        end = d + pd.Timedelta(days=ST.HOLD); ie = i + ST.HOLD
        contrib = {}; endval = 0.0; mk = {}
        for j in list(q):
            ct = inp.cut.get(j)
            if ct is not None and d < ct[0] < end:
                proceeds = q[j] * ct[1]; cost_ = proceeds * (fee + hs_buy.get(j, 0.0))
                contrib[j] = (proceeds - tgt[j]) / V0; cash += proceeds - cost_; fees += proceeds * fee; spc += proceeds * hs_buy.get(j, 0.0)
                del q[j]; continue
            px = inp.lc[ie - 1, j]
            if np.isnan(px):
                win = inp.lc[i:ie, j]; nn = win[~np.isnan(win)]
                px = nn[-1] if len(nn) else ref[j]
            mk[j] = px; endval += q[j] * px; contrib[j] = (q[j] * px - tgt[j]) / V0
        mark = mk
        last = (w == len(inp.rebal) - 1)
        if last:
            for j in list(q):
                v = q[j] * mark[j]; h_ = hs_buy.get(j, 0.0); cash += v * (1 - fee - h_); fees += v * fee; spc += v * h_
            q = {}; endval = 0.0
        V1 = cash + endval
        weeks.append({"week": w, "start": str(d.date()), "V_start": V0, "ret": V1 / V0 - 1,
                      "costs_share": (fees + spc) / V0, "positions": {inp.S[j]: (tgt[j] / V0, contrib[j]) for j in tgt}})
        cash_after = cash
    return weeks


def attribution(inp, kind, N, capital, fee, scen):
    inp._mark = {}
    ref = ST.simulate(inp, kind, N, capital, fee, scen).ret.values
    W = path(inp, kind, N, capital, fee, scen)
    got = np.array([w["ret"] for w in W])
    if not np.allclose(got, ref, rtol=0, atol=1e-9):
        raise AssertionError("attribution path differs from strategy.simulate()")
    rows = []
    for w in W:
        for s, (wt, c) in w["positions"].items():
            rows.append({"week": w["week"], "start": w["start"], "series": s, "class": asset_class(s), "weight_after_rebalance": wt,
                         "contribution": c})
    P = pd.DataFrame(rows)
    by_asset = P.groupby(["series", "class"]).agg(weeks_held=("week", "nunique"), mean_weight=("weight_after_rebalance", "mean"),
                                                  sum_contribution=("contribution", "sum")).reset_index().sort_values("sum_contribution")
    wk = P.groupby(["week", "class"]).agg(weight=("weight_after_rebalance", "sum"), contribution=("contribution", "sum")).reset_index()
    nweeks = len(W)
    by_class = wk.groupby("class").agg(mean_weight_per_week=("weight", lambda x: x.sum() / nweeks),
                                       sum_contribution=("contribution", "sum")).reset_index()
    costs = sum(w["costs_share"] for w in W)
    return P, by_asset, by_class, {"weeks": nweeks, "sum_weekly_returns": float(got.sum()), "sum_cost_shares": float(costs)}
