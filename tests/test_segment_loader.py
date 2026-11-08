"""Tests for lab/segment_loader.py (Protocol v1.2 access rules). Synthetic timestamps only; no market data.
python3 -I tests/test_segment_loader.py [out.json]"""
import sys, json, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SegmentGuard, GuardError, H, H_MAX

U = dt.timezone.utc
T = lambda *a: dt.datetime(*a, tzinfo=U)
res = []


def ok(name, f):
    try:
        f(); res.append({"test": name, "pass": True})
    except Exception as e:
        res.append({"test": name, "pass": False, "detail": repr(e)})


def raises(name, f):
    try:
        f(); res.append({"test": name, "pass": False, "detail": "did not raise"})
    except GuardError:
        res.append({"test": name, "pass": True})


dev, val = SegmentGuard("development"), SegmentGuard("validation")
hrs = lambda a, n: [a + i * H for i in range(n)]
# entry cuts (T4/H2)
ok("dev entry 2025-08-01 23:00 allowed", lambda: dev.check_entry(T(2025, 8, 1, 23)))
raises("dev entry 2025-08-02 00:00 refused", lambda: dev.check_entry(T(2025, 8, 2)))
ok("dev last entry + 30 d ends inside dev", lambda: dev.check_outcome(T(2025, 8, 1, 23), H_MAX))
raises("val entry 2026-03-02 00:00 refused", lambda: val.check_entry(T(2026, 3, 2)))
raises("val entry in embargo 1 refused", lambda: val.check_entry(T(2025, 9, 7, 12)))
raises("horizon 31 d refused (H1)", lambda: dev.check_outcome(T(2024, 6, 1), dt.timedelta(days=31)))
raises("outcome candle starting before t refused (T5)", lambda: dev.check_outcome_candles(T(2024, 6, 1, 10), H_MAX, [T(2024, 6, 1, 9)]))
# H3 safety net independent of H2: even with a (hypothetically) mis-set entry window, an outcome crossing the end is refused
def _h3():
    g = SegmentGuard("development"); g.ee = g.de                 # simulate a wrong entry window
    g.check_outcome(T(2025, 8, 31, 23), H_MAX)
raises("H3 purge: outcome crossing segment end refused even if the entry window were wrong", _h3)
# H5/H6 clarified: Validation may use Development history (and embargo) as feature lookback
ok("validation feature at 2025-09-10 uses 30 d of Development + embargo history",
   lambda: val.check_feature(T(2025, 9, 10), hrs(T(2025, 8, 11), 720)))
raises("validation feature using a not-yet-closed candle (future) refused", lambda: val.check_feature(T(2025, 9, 10), [T(2025, 9, 10)]))
raises("validation feature using Holdout-period data refused (future)", lambda: val.check_feature(T(2025, 12, 1), [T(2026, 5, 1)]))
raises("feature using Dec-2023 warm-up refused (T3)", lambda: dev.check_feature(T(2024, 1, 5), [T(2023, 12, 20)]))
raises("validation label/outcome crossing into embargo 2 refused", lambda: val.check_outcome(T(2026, 3, 5), H_MAX))
# H6: MI / regime fitting only on Development
raises("MI statistic on Validation refused", lambda: val.check_research_statistic(T(2025, 10, 1), []))
ok("MI statistic on Development with past data", lambda: dev.check_research_statistic(T(2024, 3, 1), hrs(T(2024, 1, 31), 24)))
raises("MI statistic on Development using future data refused", lambda: dev.check_research_statistic(T(2024, 3, 1), [T(2024, 3, 1, 5)]))
# H7: holdout sealed
raises("Final Holdout sealed without the logged opening", lambda: SegmentGuard("holdout"))
ok("holdout entry cut 2026-10-01 15:00 allowed after opening", lambda: SegmentGuard("holdout", holdout_opened=True).check_outcome(T(2026, 10, 1, 15), H_MAX))
raises("holdout entry 2026-10-01 16:00 refused (t + 30 d > T2)", lambda: SegmentGuard("holdout", holdout_opened=True).check_entry(T(2026, 10, 1, 16)))
out = {"passed": sum(r["pass"] for r in res), "of": len(res), "PASS": all(r["pass"] for r in res), "tests": res}
print(json.dumps({k: out[k] for k in ("passed", "of", "PASS")}))
for r in res:
    if not r["pass"]:
        print("FAIL", r)
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], "w"), indent=1)
sys.exit(0 if out["PASS"] else 1)
