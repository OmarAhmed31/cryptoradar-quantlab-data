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

# A2b the loader itself drops any post-Development candle (even if a pack contained one)
import tempfile, gzip as _gz, shutil as _sh
tmp = pathlib.Path(tempfile.mkdtemp(prefix="mi_pack_test_"))
(tmp / "hourly").mkdir()
with _gz.open(tmp / "hourly" / "TEST-USDT.csv.gz", "wt") as fh:
    fh.write("ts_utc_ms,close\n")
    for ts in ("2025-08-31 22:00", "2025-08-31 23:00", "2025-09-01 00:00", "2025-09-20 00:00"):
        fh.write(f"{int(pd.Timestamp(ts, tz='UTC').timestamp() * 1000)},1.0\n")
_old = MI.PACK; MI.PACK = tmp
try:
    Ht = MI.load_hourly(pd.Series({"TEST-USDT": "active"}))
    rec("A2b loader drops candles that do not close inside Development", Ht.index.max() == pd.Timestamp("2025-08-31 23:00", tz="UTC") and len(Ht) == 2, str(Ht.index.max()))
except Exception as e:
    rec("A2b loader drops candles that do not close inside Development", False, repr(e))
finally:
    MI.PACK = _old

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
from lab.mi_regimes import choose_k, INPUTS as _IN, FIRST_FIT as _FF
for k, (L, models, stab, summ, anchor) in base_reg.items():
    kk, sil = choose_k(base_res[k].loc[base_res[k].index < _FF, _IN].dropna())
    rec(f"A4 {k}: k and silhouettes equal a recomputation on [2024-01-01, 2024-07-01) only (R2)",
        kk == summ["k"] and all(abs(sil[x] - summ["silhouette_by_k"][x]) < 1e-12 for x in sil), f"k={kk}")
rec("A4 no label before the first model (NO_MODEL until 2024-07-01)", all((L.loc[L.index < pd.Timestamp("2024-07-01", tz="UTC"), "regime_asof"] == "NO_MODEL").all() for L, *_ in base_reg.values()))

# A6 regime runs on the calendar: UNKNOWN breaks a run (v0.11.1)
from lab.mi_regimes import calendar_runs
idx = pd.date_range("2024-07-01", periods=8, freq="D", tz="UTC")
syn = pd.Series(["S1", "S1", "UNKNOWN", "S1", "S2", "S2", "UNKNOWN", "S2"], index=idx)
r = calendar_runs(syn)
rec("A6 synthetic: S1 S1 UNKNOWN S1 S2 S2 UNKNOWN S2 -> 4 runs (2,1,2,1), 1 flip out of 3 adjacent known pairs",
    r["runs_known"] == 4 and abs(r["mean_run_days_calendar"] - 1.5) < 1e-12 and r["flip_numerator"] == 1 and r["flip_denominator_adjacent_known_pairs"] == 3, r)
syn2 = pd.Series(["S1", "S1", "S1"], index=pd.DatetimeIndex([idx[0], idx[1], idx[3]]))      # a missing calendar day
r2 = calendar_runs(syn2)
rec("A6 synthetic: a missing calendar day breaks a run", r2["runs_known"] == 2 and r2["flip_denominator_adjacent_known_pairs"] == 1, r2)
for k, (L, models, stab, summ, anchor) in base_reg.items():
    lab = L["regime_asof"]
    cal = pd.date_range(lab.index.min(), lab.index.max(), freq="D", tz="UTC")
    x = lab.reindex(cal).fillna("MISSING").tolist()
    runs, prev = [], None
    for v in x:                                            # independent recount
        good = v not in ("NO_MODEL", "UNKNOWN", "MISSING")
        if good and runs and v == prev and runs[-1][0] == v and runs[-1][2]:
            runs[-1][1] += 1
        elif good:
            runs.append([v, 1, True])
        else:
            if runs: runs[-1][2] = False
        prev = v if good else None
    ok = len(runs) == summ["runs_known"] and abs(np.mean([r[1] for r in runs]) - summ["mean_run_days_calendar"]) < 1e-9
    rec(f"A6 {k}: run statistics equal an independent recount from regimes_asof", ok, f"{len(runs)} runs, mean {np.mean([r[1] for r in runs]):.3f}")

# A7 Development-only input pack
import json as _j, gzip as _g
man = _j.load(open(MI.PACK / "PACK_MANIFEST.json"))
bad7 = [k for k, v in man["files"].items() if k.startswith("hourly/") and v.get("last_candle_utc") and v["last_candle_utc"] > "2025-08-31 23:00"]
rec("A7 the pack holds no hourly candle that closes after Development", not bad7 and man["max_candle_start_in_pack"] <= "2025-08-31 23:00", man["max_candle_start_in_pack"])
uni_bad = 0
for f in MI.SCEN.values():
    with _g.open(MI.UNIV / f, "rt") as fh:
        fh.readline()
        uni_bad += sum(1 for line in fh if line.split(",")[2] >= "2025-09-01")
rec("A7 the pack universe files hold no day after Development", uni_bad == 0, uni_bad)
srcs = open(pathlib.Path(MI.__file__)).read()
rec("A7 lab/mi.py references no input outside the pack", all(w not in srcs for w in ("active_dataset", "delisted_dataset", "research_protocol/v1.2/universe")))

out = {"passed": sum(r["pass"] for r in res), "of": len(res), "PASS": all(r["pass"] for r in res), "tests": res}
print(json.dumps({k: out[k] for k in ("passed", "of", "PASS")}))
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], "w"), indent=1)
sys.exit(0 if out["PASS"] else 1)
