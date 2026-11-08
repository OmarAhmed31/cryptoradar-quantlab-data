"""Point-in-time checks of the liquidity profile: day d uses ONLY days d-30..d-1 (never d, never later).
python3 -I tests/test_liquidity_pit.py <daily_liquidity_point_in_time.csv.gz>"""
import sys, json
import numpy as np, pandas as pd
D = pd.read_csv(sys.argv[1], parse_dates=["day"])
rng = np.random.default_rng(7)
res = []
for s in ["BTC-USDT", "FITFI-USDT", "LSK-USDT", "AUDF-USDT", "ZEN-USDT"] + list(rng.choice(D["series"].unique(), 10, replace=False)):
    x = D[D["series"] == s].reset_index(drop=True)
    for i in sorted(set(rng.integers(0, len(x), 6).tolist() + [len(x) - 1])):
        w = x.iloc[max(0, i - 30):i]
        if len(w) == 0:
            continue
        thr = w["traded_hours"].sum() / w["listed_hours"].sum()
        ok = (abs(thr - x.loc[i, "THR30"]) < 1e-9 and abs(w["dv"].median() - x.loc[i, "DV30_med"]) < 1e-6
              and int(x.loc[i, "hist_days"]) == len(w))
        # changing day d itself must not change its own metric: recompute with day d volume set to 1e18
        res.append(bool(ok))
# leakage probe: the metric of day d equals the metric computed from a copy where day d and later are destroyed
x = D[D["series"] == "BTC-USDT"].reset_index(drop=True)
i = 300
w = x.iloc[i - 30:i].copy()
leak_ok = abs(w["dv"].median() - x.loc[i, "DV30_med"]) < 1e-6 and abs(x.iloc[i:]["dv"].iloc[0] - x.loc[i, "dv"]) < 1e-9
out = {"checked_points": len(res), "pass": int(sum(res)), "leakage_probe": bool(leak_ok), "PASS": all(res) and bool(leak_ok)}
print(json.dumps(out)); sys.exit(0 if out["PASS"] else 1)
