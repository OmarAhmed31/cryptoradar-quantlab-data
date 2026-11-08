"""Liquidity point-in-time tests v2 (v0.10.1). Run: python3 -I tests/test_liquidity_pit.py <daily_liquidity_point_in_time.csv.gz>

T1-T4 synthetic (exact expectations):
  T1 a series listed mid-day: that first day is partial -> first assessable day = listing day + 31
  T2 only 29 full prior days -> NOT assessable
  T3 a missing calendar day inside the window breaks "30 full days" (window is calendar, not rows)
  T4 a delisting-day cut makes that day partial
T5 destructive leakage test on the REAL daily table: for sampled (series, d), overwrite day d and EVERY later day
   with random/huge values, recompute, and require THR30, DV30_med, DV30_mean, full_days30, assessable of day d
   to be bit-identical.
T6 recomputation by hand: for sampled points, the metrics equal a direct computation over days d-30..d-1.
"""
import sys, json, pathlib
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.liquidity_profile import compute, listed_by_day

res = []


def check(name, cond, detail=""):
    res.append({"test": name, "pass": bool(cond), "detail": str(detail)}); print(("PASS " if cond else "FAIL ") + name, detail)


def synth(start, end, gap_days=()):
    s, e = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    lb = listed_by_day(s, e)
    d = lb.rename_axis("day").reset_index()
    d = d[~d["day"].isin([pd.Timestamp(g, tz="UTC") for g in gap_days])]
    d["traded_hours"] = d["listed_hours"]; d["dv"] = 1e6; d["series"] = "S"
    return compute(d).set_index("day")


x = synth("2024-03-01 10:30", "2024-05-01")
fa = x.index[x["assessable"]].min()
check("T1 mid-day listing: first assessable = listing day + 31", fa == pd.Timestamp("2024-04-01", tz="UTC"), fa)
x = synth("2024-03-02", "2024-05-01")
check("T2 exactly 29 full prior days -> not assessable; 30 -> assessable",
      (not x.loc[pd.Timestamp("2024-03-31", tz="UTC"), "assessable"]) and x.loc[pd.Timestamp("2024-04-01", tz="UTC"), "assessable"])
x = synth("2024-03-01", "2024-06-01", gap_days=["2024-04-10"])
check("T3 calendar gap: days whose window contains the gap are not assessable",
      (not x.loc[pd.Timestamp("2024-04-11", tz="UTC"), "assessable"]) and (not x.loc[pd.Timestamp("2024-05-10", tz="UTC"), "assessable"])
      and x.loc[pd.Timestamp("2024-05-11", tz="UTC"), "assessable"])
x = synth("2024-03-01", "2024-04-15 08:00")
check("T4 delisting cut at 08:00 -> that day partial (480 listed minutes)", int(x.loc[pd.Timestamp("2024-04-15", tz="UTC"), "listed_minutes"]) == 480
      and x.loc[pd.Timestamp("2024-04-15", tz="UTC"), "full_day"] == 0)

D = pd.read_csv(sys.argv[1])
D["day"] = pd.to_datetime(D["day"]).dt.tz_localize("UTC")
base_cols = ["series", "day", "listed_hours", "listed_minutes", "traded_hours", "dv"]
rng = np.random.default_rng(11)
names = ["BTC-USDT", "FITFI-USDT", "LSK-USDT", "AUDF-USDT", "ZEN-USDT", "ZEN-USDT#old_listing", "XMR-USDT"] + \
        list(rng.choice(D["series"].unique(), 12, replace=False))
M = ["THR30", "DV30_med", "DV30_mean", "full_days30", "assessable"]
n5 = bad5 = n6 = bad6 = 0
for s in names:
    x = D[D["series"] == s][base_cols].reset_index(drop=True)
    if len(x) < 3:
        continue
    ref = compute(x).set_index("day")
    for i in sorted(set(rng.integers(1, len(x), 5).tolist() + [len(x) - 1])):
        d = x.loc[i, "day"]
        y = x.copy()
        fut = y["day"] >= d
        y.loc[fut, "dv"] = rng.uniform(1e12, 1e15, fut.sum())
        y.loc[fut, "traded_hours"] = rng.integers(0, 25, fut.sum())
        y.loc[fut, "listed_hours"] = rng.integers(0, 25, fut.sum())
        y.loc[fut, "listed_minutes"] = rng.integers(0, 1441, fut.sum())
        got = compute(y).set_index("day").loc[d, M]
        exp = ref.loc[d, M]
        n5 += 1
        same = all((pd.isna(got[c]) and pd.isna(exp[c])) or got[c] == exp[c] for c in M)
        bad5 += not same
        # T6 by hand over calendar days d-30..d-1
        w = ref[(ref.index >= d - pd.Timedelta(days=30)) & (ref.index < d)]
        lw = w[w["listed_hours"] > 0]
        thr = w["traded_hours"].sum() / w["listed_hours"].sum() if w["listed_hours"].sum() else np.nan
        ok6 = (int(w["full_day"].sum()) == int(exp["full_days30"])
               and ((np.isnan(thr) and pd.isna(exp["THR30"])) or abs(thr - exp["THR30"]) < 1e-12)
               and ((len(lw) == 0 and pd.isna(exp["DV30_med"])) or abs(lw["dv"].median() - exp["DV30_med"]) < 1e-6))
        n6 += 1; bad6 += not ok6
check("T5 destructive leakage: day d metrics unchanged when d and all later days are overwritten", bad5 == 0, f"{n5 - bad5}/{n5} points, {len(names)} series")
check("T6 metrics equal direct computation over calendar days d-30..d-1", bad6 == 0, f"{n6 - bad6}/{n6} points")
out = {"tests": res, "PASS": all(r["pass"] for r in res)}
print(json.dumps({"passed": sum(r["pass"] for r in res), "of": len(res), "PASS": out["PASS"]}))
if len(sys.argv) > 2:
    json.dump(out, open(sys.argv[2], "w"), indent=1)
sys.exit(0 if out["PASS"] else 1)
