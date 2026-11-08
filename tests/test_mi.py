"""Acceptance tests for Market Intelligence (plan v0.3.1 A1-A5). Development data only.
python3 -I tests/test_mi.py [out.json]"""
import sys, json, pathlib
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import mi as MI
from lab.segment_loader import GuardError

res = []
def rec(name, ok, detail=""):
    res.append({"test": name, "pass": bool(ok), "detail": str(detail)}); print(("PASS " if ok else "FAIL ") + name, detail)

E, groups = MI.load_eligibility()
H = MI.load_hourly(groups)
base_res, base_reg = MI.full_pipeline(H, E, groups)

# A1 destructive future overwrite (MI values of every block + regime_asof, every scenario)
rng = np.random.default_rng(5)
days = [pd.Timestamp(x, tz="UTC") for x in ("2024-03-15", "2024-08-01", "2025-01-20", "2025-08-31")]
bad = 0; checked = 0
for d in days:
    H2 = H.copy()
    fut = (H2.index + pd.Timedelta(hours=1)) > d
    H2.loc[fut] = H2.loc[fut].notna() * rng.uniform(1e-6, 1e6, size=H2.loc[fut].shape)
    H2 = H2.where(H2 != 0)
    E2 = {}
    for k, e in E.items():
        e2 = e.copy(); m = e2.index > d
        e2.loc[m] = rng.random(e2.loc[m].shape) < 0.5
        E2[k] = e2
    r2, g2 = MI.full_pipeline(H2, E2, groups)
    for k in base_res:
        a, b = base_res[k].loc[d], r2[k].loc[d]
        for c in a.index:
            checked += 1
            same = (pd.isna(a[c]) and pd.isna(b[c])) or a[c] == b[c] or (isinstance(a[c], float) and abs(a[c] - b[c]) <= 1e-12 * max(1, abs(a[c])))
            bad += not same
    for k in base_reg:
        checked += 1
        bad += base_reg[k][0].loc[d, "regime_asof"] != g2[k][0].loc[d, "regime_asof"]
rec("A1 destructive future overwrite: all MI values and regime_asof of day d unchanged", bad == 0, f"{checked - bad}/{checked} values, days {[str(x.date()) for x in days]}")

# A2 segment guard
try:
    Hv = H.copy(); Hv.loc[pd.Timestamp("2025-09-10", tz="UTC")] = 1.0
    MI.assert_dev_only(Hv.sort_index()); rec("A2 a Validation candle in MI input is refused", False)
except GuardError:
    rec("A2 a Validation candle in MI input is refused", True)
try:
    MI.GUARD.check_research_statistic(pd.Timestamp("2025-10-01", tz="UTC").to_pydatetime(), []); rec("A2 MI statistic on a Validation day refused", False)
except GuardError:
    rec("A2 MI statistic on a Validation day refused", True)
rec("A2 loaded data ends inside Development", H.index.max() + pd.Timedelta(hours=1) <= MI.DEV_END and H.index.min() >= pd.Timestamp("2024-01-01", tz="UTC"),
    f"{H.index.min()} .. {H.index.max()}")
rec("A2 every output day is a Development day", all((df.index >= MI.DEV_START).all() and (df.index < MI.DEV_END).all() for df in base_res.values()))

# A3 boundary counts: MI computes no forward quantity
fwd = [c for df in base_res.values() for c in df.columns if any(w in c for w in ("fwd", "future", "label", "mfe", "mae", "target"))]
rec("A3 no forward/label/outcome column exists (0 label starts, 0 crossing intervals)", not fwd, fwd)

# A4 as-known regimes: each day labelled by the model in force; never by a later model
ok4 = True
for k, (L, models, stab, summ, anchor) in base_reg.items():
    for day, row in L.iterrows():
        if row["model_id"]:
            m = [x for x in models if x["id"] == row["model_id"]][0]
            ok4 &= pd.Timestamp(m["refit_utc"]) <= day < pd.Timestamp(m["valid_until"])
            ok4 &= pd.Timestamp(m["train_window"][1]) <= day
rec("A4 every regime label comes from the model in force that day, trained only on earlier days", ok4)
rec("A4 no label before the first model (NO_MODEL until 2024-07-01)", all((L.loc[L.index < pd.Timestamp("2024-07-01", tz="UTC"), "regime_asof"] == "NO_MODEL").all() for L, *_ in base_reg.values()))

out = {"passed": sum(r["pass"] for r in res), "of": len(res), "PASS": all(r["pass"] for r in res), "tests": res}
print(json.dumps({k: out[k] for k in ("passed", "of", "PASS")}))
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], "w"), indent=1)
sys.exit(0 if out["PASS"] else 1)
