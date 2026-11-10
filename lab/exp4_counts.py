"""Experiment 4 counts stage (spec docs/EXP4_CAPITAL_ALLOCATION_DESIGN_PROPOSAL_v0.5.md, FROZEN and approved).
Development only, ONE run (after a separate approval). NO return, NO outcome, NO price after the entry.

It reuses the frozen Experiment 3 code unchanged (lab/exp3_counts.py at commit 1f91f8b): the signals of D-H1, D-H2 and
D-D1, the frozen thresholds, the half-spread and wide-stop checks, the trade windows (7-day time exit, U9b, H_max) and
the re-entry rules. New here is ONLY the portfolio policy of spec v0.5 §1.3 (stage 1: K <= 3 throughout, the
$10,000 path; spec §7):

  decision at the start of each entry hour h, on a SNAPSHOT taken at h (step 0):
    a position counts as exited only if its exit time is strictly before h
    batch = the design's signals with entry hour h that pass every check known at h:
            signal conditions + P1 eligibility (frozen Exp. 3), half-spread estimable, entry window,
            coin not held, same-coin re-entry window (hourly 168 h; D-D1 calendar rule)
    s = K - open;  s <= 0 -> SKIPPED_NO_SLOT;  no available cash -> SKIPPED_NO_CASH
    rank: RVOL descending (unrounded), exact tie -> coin name ascending; take the best min(s, batch); rest SKIPPED_RANK
    the available cash is split equally among the selected (cash > 0 afterwards only if a selected one fails)
  at each selected signal's own fill (step 7): NOT_EXECUTED / SKIPPED_WIDE_STOP_AT_ENTRY -> its share stays in cash,
    never passed to a lower-ranked signal; a filled position is held to its latest end (as Exp. 3 L_greedy)

L_greedy(K) = completed trades counted (exit guaranteed within H_max and the segment), a PRELIMINARY ESTIMATE under
K <= 3 throughout; it is NOT proof of U7 (spec v0.5 §7). python3 -I lab/exp4_counts.py <out_dir> [<pack>] [<thr>] [<ledger>]
"""
import sys, json, hashlib, pathlib
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import fd_features as FF
from lab import exp3_counts as E3
from lab.segment_loader import SEGMENTS

REPO = pathlib.Path(__file__).resolve().parents[1]
K_STAGE1 = 3                      # spec v0.5 §7: K <= 3 throughout Development ($10,000 path)
MIN_L = E3.MIN_L                  # 100
NOTE_U7 = ("L_greedy(K) >= 100 is a PRELIMINARY ESTIMATE under the assumption K <= 3 throughout Development. It is NOT "
           "proof that U7 will hold in P1: in P1 equity may fall below $2,000 and K may drop to 1, so fewer trades are "
           "possible. U7 itself is decided only by the completed trades of the frozen P1 run on the $10,000 path.")
NOTE_LWORST = ("L_worst is NOT computed for K > 1: a valid worst-case bound over every exit time of up to 3 concurrent "
               "positions with the cash rule is not tractable with the Exp. 3 method (developer note, for reviewer decision); "
               "it was reported-only and never an acceptance rule.")


# ------------------------------------------------------------------ inputs per signal (known at h, or at the fill)
def daily_rvol(Hh):
    """RVOL_d exactly as the frozen D-D1 condition: vol_D / median of vol over the traded days D-20 .. D-1 (>= 10)."""
    hi, lo, cl, vol = E3.daily_bars(Hh)
    traded = cl.notna()
    return vol / vol.where(traded).rolling(E3.D_WIN, min_periods=E3.D_MINW).median().shift(1)


def rank_values(sig, name, Hh, U):
    """the design's own RVOL at each signal's signal bar (unrounded floats)."""
    if name == "D-D1":
        R = daily_rvol(Hh).values
        return R[sig["row_entry"].values // 24 - 1, sig["col"].values]
    R = E3.TH.indicators(Hh, U, None)["rvol"].values
    return R[sig["row_entry"].values - 1, sig["col"].values]


def pre_entry(sig, Hh, seg):
    """checks known at h: the entry window and the half-spread (days d-30 .. d-1 of the entry day)."""
    es, ee = pd.Timestamp(seg[2]), pd.Timestamp(seg[3])
    n = Hh["close"].shape[0]; cache, out = {}, []
    for s in sig.itertuples(index=False):
        if not (es <= s.entry_hour < ee) or s.row_entry >= n:
            out.append("PAST_ENTRY_CUT"); continue
        if E3.APPLY_HS_SKIP:
            di = s.row_entry // 24
            if di not in cache:
                cache[di] = E3.half_spread_day(Hh["high"], Hh["low"], di)
            if np.isnan(cache[di][s.col]):
                out.append("SKIPPED_NO_HALF_SPREAD"); continue
        out.append("OK")
    return out


def fill_one(C, O, row, col, stop_level, stop_limit):
    """checks known only at the fill, for ONE selected signal: a traded minute in the entry hour; A3 wide stop at the
    fill (the entry bar open = the open of its first traded minute). Called by the portfolio ONLY after selection."""
    if np.isnan(C[row, col]):
        return "NOT_EXECUTED"
    fill = O[row, col]
    if E3.APPLY_ENTRY_STOP_SKIP and (fill - stop_level) / fill > stop_limit:
        return "SKIPPED_WIDE_STOP_AT_ENTRY"
    return "FILLED"


def fill_check(sig, Hh, stop_limit):
    """the same check for a table of signals (used by the tests only)."""
    C, O = Hh["close"].values, Hh["open"].values
    return [fill_one(C, O, s.row_entry, s.col, s.stop_level, stop_limit) for s in sig.itertuples(index=False)]


def free_time(end_ns, xref_ns):
    """the snapshot rule: a position counts as exited at decision h only if its exit time is strictly before h.
    time exit: the fill lies inside the exit bar, strictly before end = bar + 1h  -> free from h >= end;
    exit exactly AT end (a delisting cut, or no exit before the segment end)  -> free only from h > end."""
    return end_ns + 1 if xref_ns == end_ns else end_ns


# ------------------------------------------------------------------ the portfolio engine (spec v0.5 §1.3)
def portfolio(cands, K, fill=None):
    """cands: dicts with h, coin, rvol, ws, end, free_at, rf, c, why, i. fill(s) is the fill check; it is called ONLY
    for the signals the portfolio selected at h (spec v0.5 step 7), never before or for the others.
    Returns summary, per-signal reasons, opened."""
    fill = fill or (lambda s: s["fill"])
    by_h = {}
    for s in cands:
        by_h.setdefault(s["h"], []).append(s)
    opn, last_rf, cash = [], {}, True
    reason, opened, batch_sizes, conc = {}, [], [], []
    for h in sorted(by_h):
        keep = []
        for p in opn:                                                     # step 0: snapshot at h
            if p["free_at"] <= h:
                cash = True; last_rf[p["coin"]] = max(last_rf.get(p["coin"], p["rf"]), p["rf"])
            else:
                keep.append(p)
        opn = keep
        held = {p["coin"] for p in opn}
        batch = []
        for s in by_h[h]:
            if s["coin"] in held:
                reason[s["i"]] = "BLOCKED_COIN_HELD"
            elif s["coin"] in last_rf and s["ws"] < last_rf[s["coin"]]:
                reason[s["i"]] = "BLOCKED_REENTRY_WINDOW"
            else:
                batch.append(s)
        if not batch:
            continue
        batch_sizes.append(len(batch))
        slots = K - len(opn)
        if slots <= 0:
            for s in batch: reason[s["i"]] = "SKIPPED_NO_SLOT"
            continue
        if not cash:
            for s in batch: reason[s["i"]] = "SKIPPED_NO_CASH"
            continue
        batch.sort(key=lambda s: (-s["rvol"], s["coin"]))                 # RVOL desc, exact tie -> coin asc
        sel, rest = batch[:slots], batch[slots:]
        for s in rest: reason[s["i"]] = "SKIPPED_RANK"
        failed = False
        for s in sel:                                                     # step 7: at each fill, selected only
            f = fill(s)
            if f != "FILLED":
                reason[s["i"]] = f; failed = True                         # its share stays in cash
            else:
                reason[s["i"]] = "OPENED"; opn.append(s); opened.append(s)
                conc.append(len(opn))
        cash = failed                                                     # all available cash went to the selected
    L = int(sum(int(s["c"]) for s in opened))
    out = {"K": K, "opened": len(opened), "L_greedy_K": L, "batches": len(batch_sizes),
           "batch_size": {str(k): int(v) for k, v in sorted(pd.Series(batch_sizes, dtype=int).value_counts().items())} if batch_sizes else {},
           "open_positions_after_each_entry": {str(k): int(v) for k, v in sorted(pd.Series(conc, dtype=int).value_counts().items())} if conc else {},
           "opened_by_window_reason": dict(sorted(pd.Series([s["why"] for s in opened], dtype=object).value_counts().astype(int).to_dict().items())) if opened else {}}
    return out, reason, opened


def build_candidates(sig, rv, ends, cnt, why, xref, daily):
    """no fill information here: only what is known at h, plus the row/column/stop the fill check needs later."""
    d = E3.DAY_NS if daily else None
    return [{"i": i, "h": r.entry_hour.value, "coin": r.coin, "rvol": float(v), "ws": r.win_start.value,
             "row": int(getattr(r, "row_entry", -1)), "col": int(getattr(r, "col", -1)), "stop": float(getattr(r, "stop_level", np.nan)),
             "end": e.value, "free_at": free_time(e.value, x.value), "rf": E3.reentry_from(x.value, e.value, d), "c": bool(c), "why": w}
            for i, (r, v, e, c, w, x) in enumerate(zip(sig.itertuples(index=False), rv, ends, cnt, why, xref))]


def run(pack=FF.PACK, thr=None, ledger=None, K=K_STAGE1, _daily_fixed=None):
    pack = pathlib.Path(pack)
    T = E3.load_thresholds(thr or REPO / E3.THR_FILE)
    led = E3.load_ledger(ledger or REPO / E3.LEDGER_FILE)
    Hh, U, groups = FF.load_pack(pack)
    FF.assert_dev_only(Hh)
    seg = SEGMENTS["development"]; seg_end = pd.Timestamp(seg[1])
    ret, _, _ = E3.TH.ew_index(Hh, U, groups)
    st = E3.TH.states(ret)
    trend, trans = E3.trend_states(st, T)
    designs = E3.hourly_designs(Hh, U, T, trans, trend, st["high_vol"])
    designs["D-D1"] = E3.daily_design(Hh, U, trans, trend, st["high_vol"], _daily_fixed)
    C = Hh["close"]
    traded_times = {c: C.index[C[c].notna().values].as_unit("ns").asi8 for c in C.columns}
    res = {"designs": {}, "_sig": {}}; Lg = {}
    for name in ("D-H1", "D-H2", "D-D1"):
        d = designs[name]; sig = d["signals"].sort_values(["entry_hour", "coin"]).reset_index(drop=True)
        sig["rvol_rank"] = rank_values(sig, name, Hh, U) if len(sig) else []
        sig["pre"] = pre_entry(sig, Hh, seg)
        ok = sig[sig["pre"] == "OK"].reset_index(drop=True)
        ends, cnt, why, xref = E3.trade_windows(ok, traded_times, led, seg_end)
        cands = build_candidates(ok, ok["rvol_rank"].values, ends, cnt, why, xref, name == "D-D1")
        Cv, Ov, lim, checked = Hh["close"].values, Hh["open"].values, d["stop_limit"], {}
        def _fill(s):                                                     # the entry bar is read here, and only here
            checked[s["i"]] = fill_one(Cv, Ov, s["row"], s["col"], s["stop"], lim); return checked[s["i"]]
        summ, reason, opened = portfolio(cands, K, _fill)
        Lg[name] = summ["L_greedy_K"]
        ok["fill"] = [checked.get(i, "NOT_CHECKED") for i in range(len(ok))]
        ok["portfolio"] = [reason.get(i, "NO_DECISION") for i in range(len(ok))]
        ok["end"] = ends; ok["c"] = cnt; ok["why"] = why
        res["_sig"][name] = {"all": sig, "ok": ok, "cands": cands}
        allr = list(sig.loc[sig["pre"] != "OK", "pre"]) + list(ok["portfolio"])
        res["designs"][name] = {
            "conditions": E3.CONDITIONS[name], "cascade": [[k, v] for k, v in d["cascade"]],
            "signals": E3.compose(sig),
            "reasons_all_signals": dict(sorted(pd.Series(allr, dtype=object).value_counts().astype(int).to_dict().items())) if allr else {},
            "portfolio": summ, "opened": E3.compose(ok, ok["portfolio"].values == "OPENED") if len(ok) else E3.compose(ok),
            "L_greedy_K": summ["L_greedy_K"], "L_worst": None}
        if name == "D-D1":
            res["designs"][name]["daily_thresholds"] = d["derived"]; res["designs"][name]["daily_breakout_population"] = d["population"]
    res["selection"] = {"rule": "L_greedy(K) >= 100, then fewest entry conditions, D-D1 wins the tie with D-H1; else STOP",
                        "K": K, "by_L_greedy_K": E3.select(Lg), "chosen": E3.select(Lg), "U7_note": NOTE_U7}
    res["definitions"] = {"L_greedy_K": "estimate of completed trades under the spec v0.5 portfolio policy with K <= 3 "
                          "throughout, every filled position held to its latest end; NOT a guaranteed minimum; NOT proof of U7",
                          "L_worst": NOTE_LWORST}
    res["settings"] = {"K": K, "ranking": "RVOL descending (unrounded), exact tie -> coin name ascending",
                       "snapshot": "an exit counts at decision h only if strictly before h",
                       "failed_fill": "share stays in cash; never passed to a lower-ranked signal"}
    res["note"] = "opportunity counts only; NO return, NO outcome, NO price after the entry"
    return res


def main(out_dir, pack=None, thr=None, ledger=None):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    pack = pathlib.Path(pack) if pack else FF.PACK
    res = run(pack, thr, ledger)
    res.pop("_sig")
    res["code_sha256"] = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in
                          ("lab/exp4_counts.py", "lab/exp3_counts.py", "lab/thresholds.py", "lab/fd_features.py",
                           "lab/universe_crypto_only.py", "lab/segment_loader.py")}
    mf = pack / "PACK_MANIFEST.json"
    res["inputs"] = {"pack_manifest_sha256": hashlib.sha256(mf.read_bytes()).hexdigest() if mf.exists() else "",
                     "thresholds_sha256": E3.THR_SHA,
                     "ledger_sha256": hashlib.sha256(pathlib.Path(ledger or REPO / E3.LEDGER_FILE).read_bytes()).hexdigest()}
    b = json.dumps(res, indent=1, sort_keys=True).encode()
    (out / "exp4_counts.json").write_bytes(b)
    print(hashlib.sha256(b).hexdigest())


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], *(a[1:] + [None] * (4 - len(a)))[:3])
