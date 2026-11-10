"""Threshold derivation (plan docs/REGIME_THRESHOLD_DERIVATION_PLAN_v0.3.2.md). Development only, ONE run.
Indicator DISTRIBUTIONS only: no forward return, no outcome, no trade. Allowed imports: numpy, pandas, stdlib,
lab.fd_features (pack loader + frozen feature code), lab.segment_loader, lab.universe_crypto_only. Nothing else.

python3 -I lab/thresholds.py <out_dir> [<pack_dir>]

Populations (plan §2): H = eligible crypto-only coin-hours with >= 84 traded bars in the prior 168;
BO = H bars with close_t > R_high (max high of the prior 168 bars); D = days with the EW index (>= 20 coins).
Statistics (plan §3, fixed): E2 P25 of R_high / max-high(90 days before the window) on H; E3 P75 RVOL on BO;
E4 median CLV on BO; E5 P90 stop distance on BO (no stop limit applied); R1/R2 P67/P33 of the 20-day EW return on D;
R3 P90 RVOL on BO; R4 median stop distance on BO bars of High-Vol days (flag known at d 00:00, prior days only).
"""
import sys, json, hashlib, pathlib
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab.universe_crypto_only import is_excluded

W = 168                    # 7-day range window (hours)          CONV (design)
MINW = 84                  # >= 50 % traded bars                FD-1 rule
PEAK = 90 * 24             # 90-day peak window before the range  CONV (design)
MIN_COINS = 20             # R6e
TREND_RET, TREND_MA, VOL_WIN, VOL_MIN_PRIOR = 20, 50, 30, 60     # CONV (design); vol rule = MI M2


def _q(x, p):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return float(np.quantile(x, p)) if len(x) else float("nan")


def indicators(Hh, U, groups):
    """hourly indicators, each using bars strictly before t (range, volume baseline) or bar t itself (close, CLV)."""
    C, Hi, Lo, VQ = (Hh[k] for k in ("close", "high", "low", "vol_quote"))
    traded = C.notna()
    n_prior = traded.astype(float).rolling(W, min_periods=1).sum().shift(1)
    R_high = Hi.rolling(W, min_periods=1).max().shift(1)
    R_low = Lo.rolling(W, min_periods=1).min().shift(1)
    peak = Hi.rolling(PEAK, min_periods=PEAK // 2).max().shift(1 + W)              # the 90 days BEFORE the window
    rvol = VQ / VQ.rolling(W, min_periods=MINW).median().shift(1)
    rng = (Hi - Lo)
    clv = ((C - Lo) / rng).where(rng > 0)
    stop = (C - R_low) / C
    ratio = R_high / peak
    return dict(n_prior=n_prior, R_high=R_high, R_low=R_low, rvol=rvol, clv=clv, stop=stop, ratio=ratio, close=C)


def allowed_mask(U, groups, index):
    """crypto-only AND P1-eligible on the bar's day, expanded to hours."""
    E = U["P1"]["eligible"].copy()
    E.loc[:, [c for c in E.columns if is_excluded(c)]] = False
    return E.reindex(index.floor("D")).set_axis(index)


def ew_index(Hh, U, groups):
    """daily EW return of allowed coins: mean of r_1 = close_asof(d)/close_asof(d-1)-1 (FD-1 F01 definition)."""
    C = Hh["close"]
    lc = C.groupby(C.index.floor("D")).last().reindex(FF.DAYS)
    ca = lc.shift(1)
    r1 = ca / ca.shift(1) - 1
    E = U["P1"]["eligible"].copy(); E.loc[:, [c for c in E.columns if is_excluded(c)]] = False
    R = r1.where(E.reindex(index=r1.index, columns=r1.columns).fillna(False))
    n = R.notna().sum(axis=1)
    ret = R.mean(axis=1).where(n >= MIN_COINS)
    return ret, n, r1


def states(ret):
    idx = (1 + ret.fillna(0)).cumprod().where(ret.notna().cumsum() > 0)
    r20 = idx / idx.shift(TREND_RET) - 1
    ma50 = idx.rolling(TREND_MA, min_periods=TREND_MA).mean()
    vol30 = ret.rolling(VOL_WIN, min_periods=VOL_WIN).std()          # ret(d) = return of day d-1 (known at d 00:00) -> days d-30 .. d-1
    pct = pd.Series(np.nan, index=ret.index)
    v = vol30.values
    for i in range(len(v)):                                                           # prior days only (expanding)
        h = v[:i]; h = h[~np.isnan(h)]
        if len(h) >= VOL_MIN_PRIOR and not np.isnan(v[i]):
            pct.iloc[i] = (h < v[i]).mean()
    high_vol = pct > 2 / 3
    return dict(index=idx, r20=r20, ma50=ma50, vol30=vol30, vol_pct=pct, high_vol=high_vol)


def derive(pack=FF.PACK):
    Hh, U, groups = FF.load_pack(pack)
    FF.assert_dev_only(Hh)
    ind = indicators(Hh, U, groups)
    A = allowed_mask(U, groups, Hh["close"].index).reindex(columns=Hh["close"].columns).fillna(False)
    H = A & ind["close"].notna() & (ind["n_prior"] >= MINW)
    BO = H & (ind["close"] > ind["R_high"])
    ret, ncoins, _ = ew_index(Hh, U, groups)
    st = states(ret)
    D = ret.notna() & st["r20"].notna()
    hv_hours = st["high_vol"].reindex(Hh["close"].index.floor("D")).fillna(False).set_axis(Hh["close"].index)
    BOhv = BO & pd.DataFrame(np.repeat(hv_hours.values[:, None], BO.shape[1], 1), index=BO.index, columns=BO.columns)

    def vals(X, M):
        return X.values[M.values]
    pops = {"H": vals(ind["ratio"], H & ind["ratio"].notna()), "BO_rvol": vals(ind["rvol"], BO & ind["rvol"].notna()),
            "BO_clv": vals(ind["clv"], BO & ind["clv"].notna()), "BO_stop": vals(ind["stop"], BO & ind["stop"].notna()),
            "D_r20": st["r20"][D].values, "BOhv_stop": vals(ind["stop"], BOhv & ind["stop"].notna())}
    T = {"E2_peak_ratio_P25": _q(pops["H"], .25), "E3_rvol_P75": _q(pops["BO_rvol"], .75), "E4_clv_median": _q(pops["BO_clv"], .5),
         "E5_stop_P90": _q(pops["BO_stop"], .90), "R1_bull_r20_P67": _q(pops["D_r20"], .67), "R2_bear_r20_P33": _q(pops["D_r20"], .33),
         "R3_bear_rvol_P90": _q(pops["BO_rvol"], .90), "R4_highvol_stop_median": _q(pops["BOhv_stop"], .5)}
    kept = {"E2": float(np.mean(pops["H"] <= T["E2_peak_ratio_P25"])), "E3": float(np.mean(pops["BO_rvol"] >= T["E3_rvol_P75"])),
            "E4": float(np.mean(pops["BO_clv"] >= T["E4_clv_median"])), "E5": float(np.mean(pops["BO_stop"] <= T["E5_stop_P90"])),
            "R1": float(np.mean(pops["D_r20"] > T["R1_bull_r20_P67"])), "R2": float(np.mean(pops["D_r20"] < T["R2_bear_r20_P33"])),
            "R3": float(np.mean(pops["BO_rvol"] >= T["R3_bear_rvol_P90"])), "R4": float(np.mean(pops["BOhv_stop"] <= T["R4_highvol_stop_median"]))}
    dec = {k: [_q(v, p / 10) for p in range(11)] for k, v in pops.items()}
    sizes = {k: int(len(v)) for k, v in pops.items()}
    return {"thresholds": T, "share_kept": kept, "population_sizes": sizes, "deciles": dec,
            "D_days": int(D.sum()), "high_vol_days": int(st["high_vol"].sum())}, (Hh, ind, H, BO, st)


def cascade(Hh, ind, BO, st, T, U):
    """counts of candidate BO bars after each entry condition in turn (NOT trades, NOT returns); plan §5."""
    C = ind["close"]; lr = np.log(C) - np.log(C.ffill().shift(1))
    lr = lr.where(C.notna())
    v7 = lr.rolling(W, min_periods=MINW).std().shift(1); v30 = lr.rolling(30 * 24, min_periods=15 * 24).std().shift(1)
    width = ind["R_high"] / ind["R_low"] - 1
    a1 = width <= width.rolling(180 * 24, min_periods=90 * 24).quantile(0.25).shift(1)
    btc = C["BTC-USDT"]; r24 = C / C.shift(24) - 1; b24 = btc / btc.shift(24) - 1
    stronger = r24.gt(b24, axis=0)
    out = {}; m = BO.copy(); out["BO"] = int(m.values.sum())
    for name, cond in (("A1_tight", a1), ("A2_E2", ind["ratio"] <= T["E2_peak_ratio_P25"]), ("C_contraction", v7 < v30),
                       ("E3_rvol", ind["rvol"] >= T["E3_rvol_P75"]), ("E4_clv", ind["clv"] >= T["E4_clv_median"]),
                       ("BTC_strength_24h", stronger), ("E5_stop", ind["stop"] <= T["E5_stop_P90"])):
        m = m & cond.fillna(False); out[name] = int(m.values.sum())
    trend = pd.Series("SIDEWAYS", index=st["index"].index)
    trend[(st["index"] > st["ma50"]) & (st["r20"] > T["R1_bull_r20_P67"])] = "BULL"
    trend[(st["index"] < st["ma50"]) & (st["r20"] < T["R2_bear_r20_P33"])] = "BEAR"
    trend[st["r20"].isna() | st["ma50"].isna()] = "UNCERTAIN"
    changed = (trend != trend.shift(1)).astype(int).rolling(5, min_periods=1).sum() > 0
    changed.iloc[0] = False
    trans = changed | (trend == "UNCERTAIN")
    hrs = C.index.floor("D")
    tr_h = trans.reindex(hrs).values; bear_h = (trend == "BEAR").reindex(hrs).values; hv_h = st["high_vol"].reindex(hrs).fillna(False).values
    r7 = C / C.shift(W) - 1; b7 = btc / btc.shift(W) - 1
    keep = ~tr_h[:, None] & m.values
    bear_ok = (ind["rvol"].values >= T["R3_bear_rvol_P90"]) & r7.gt(b7, axis=0).values
    keep &= np.where(bear_h[:, None], bear_ok, True)
    keep &= np.where(hv_h[:, None], ind["stop"].values <= T["R4_highvol_stop_median"], True)
    out["state_actions"] = int(keep.sum())
    run = (trend != trend.shift(1)).cumsum(); lengths = trend.groupby(run).size().values
    return out, {"trend_run_length_deciles_days": [_q(lengths, p / 10) for p in range(11)], "n_runs": int(len(lengths))}


def main(out_dir, pack=None):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    pack = pathlib.Path(pack) if pack else FF.PACK
    res, (Hh, ind, H, BO, st) = derive(pack)
    U = FF.load_pack(pack)[1]
    counts, runs = cascade(Hh, ind, BO, st, res["thresholds"], U)
    man = json.loads((pack / "PACK_MANIFEST.json").read_text()) if (pack / "PACK_MANIFEST.json").exists() else {}
    code = {p: hashlib.sha256((FF.LAB / p).read_bytes()).hexdigest() for p in ("lab/thresholds.py", "lab/fd_features.py", "lab/universe_crypto_only.py", "lab/segment_loader.py")}
    res.update(candidate_bar_cascade=counts, candidate_bar_note="counts of candidate BO bars, NOT trades and NOT returns; U7 applies to completed P1 trades only",
               info_only=runs, inputs={"pack_manifest_sha256": hashlib.sha256((pack / "PACK_MANIFEST.json").read_bytes()).hexdigest() if man else ""},
               code_sha256=code)
    b = json.dumps(res, indent=1, sort_keys=True).encode()
    (out / "thresholds.json").write_bytes(b)
    print(hashlib.sha256(b).hexdigest())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
