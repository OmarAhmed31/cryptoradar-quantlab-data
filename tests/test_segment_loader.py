"""Tests for lab/segment_loader.py (Protocol v1.2 access rules). Synthetic timestamps only; no market data.
python3 -I tests/test_segment_loader.py [out.json]"""
import sys, json, pathlib, datetime as dt, tempfile, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SegmentGuard, GuardError, H, H_MAX, open_holdout


# --- a throw-away opening setup in a temp dir (NEVER the real record location)
TMP = pathlib.Path(tempfile.mkdtemp(prefix="holdout_test_"))
def _setup(name, manifest_ok=True, protocol_ok=True):
    d = TMP / name; d.mkdir()
    man = d / "candidate_freeze_manifest.json"; man.write_text('{"candidates": ["synthetic-test-only"]}')
    proto = d / "PROTOCOL.md"; proto.write_text("synthetic protocol for tests")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    appr = d / "approval.json"
    appr.write_text(json.dumps({"manifest_sha256": sha(man) if manifest_ok else "0" * 64, "protocol_sha256": sha(proto) if protocol_ok else "0" * 64,
                                "approved_by": "test", "approved_utc": "2026-01-01T00:00:00Z"}))
    return d, man, appr, proto
COMMIT = "a" * 40
_d0, _m0, _a0, _p0 = _setup("main")
REC = open_holdout(_m0, _a0, _p0, COMMIT, _d0 / "rec")

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
# decision-time lock (v0.10.6, reviewer finding): t itself must be inside the guard's own segment
hold = lambda: SegmentGuard("holdout", opening_record=REC)
ok("D1 Validation feature at a Validation date: accepted", lambda: val.check_feature(T(2025, 12, 1), [T(2025, 11, 30, 22)]))
raises("D2 Validation feature at a Development date: refused", lambda: val.check_feature(T(2025, 6, 1), [T(2025, 5, 31)]))
raises("D3 Validation feature at a Holdout date (2026-05-01), past candle only: refused", lambda: val.check_feature(T(2026, 5, 1), [T(2026, 4, 30)]))
raises("D4 Development feature at a Validation date: refused", lambda: dev.check_feature(T(2025, 10, 1), [T(2025, 9, 30)]))
raises("D5 Holdout feature before the official opening: refused", lambda: SegmentGuard("holdout").check_feature(T(2026, 5, 1), [T(2026, 4, 30)]))
ok("D6 Holdout feature after the official opening, past data only: accepted", lambda: hold().check_feature(T(2026, 5, 1), hrs(T(2026, 4, 1), 720)))
raises("D7 Validation feature at an embargo date: refused", lambda: val.check_feature(T(2025, 9, 3), [T(2025, 9, 2)]))
raises("D8 Holdout (opened) feature at a Validation date: refused", lambda: hold().check_feature(T(2026, 2, 1), [T(2026, 1, 31)]))
# H6: MI / regime fitting only on Development
raises("MI statistic on Validation refused", lambda: val.check_research_statistic(T(2025, 10, 1), []))
ok("MI statistic on Development with past data", lambda: dev.check_research_statistic(T(2024, 3, 1), hrs(T(2024, 1, 31), 24)))
raises("MI statistic on Development using future data refused", lambda: dev.check_research_statistic(T(2024, 3, 1), [T(2024, 3, 1, 5)]))
# H7: holdout sealed
raises("Final Holdout sealed without the logged opening", lambda: SegmentGuard("holdout"))
ok("holdout entry cut 2026-10-01 15:00 allowed after opening", lambda: SegmentGuard("holdout", opening_record=REC).check_outcome(T(2026, 10, 1, 15), H_MAX))
raises("holdout entry 2026-10-01 16:00 refused (t + 30 d > T2)", lambda: SegmentGuard("holdout", opening_record=REC).check_entry(T(2026, 10, 1, 16)))
# --- holdout opening procedure (v0.10.7, reviewer finding on H7)
raises("O1 holdout guard without an opening record refused", lambda: SegmentGuard("holdout"))
def _o2():
    try:
        SegmentGuard("holdout", holdout_opened=True)
    except TypeError:
        raise GuardError("boolean switch does not exist")
raises("O2 boolean switch holdout_opened=True no longer exists", _o2)
def _o3():
    d, m, a, p = _setup("o3"); m.unlink(); open_holdout(m, a, p, COMMIT, d / "rec")
raises("O3 opening without a Candidate Freeze Manifest refused", _o3)
def _o4():
    d, m, a, p = _setup("o4", manifest_ok=False); open_holdout(m, a, p, COMMIT, d / "rec")
raises("O4 manifest not matching the approved sha256 refused", _o4)
def _o5():
    d, m, a, p = _setup("o5", protocol_ok=False); open_holdout(m, a, p, COMMIT, d / "rec")
raises("O5 protocol not matching the approved protocol sha256 refused", _o5)
def _o6():
    d, m, a, p = _setup("o6"); r = open_holdout(m, a, p, COMMIT, d / "rec")
    rec = json.loads(r.read_text())
    assert rec["commit"] == COMMIT and rec["manifest_sha256"] == hashlib.sha256(m.read_bytes()).hexdigest() and rec["opened_utc"]
    SegmentGuard("holdout", opening_record=r).check_feature(T(2026, 5, 1), [T(2026, 4, 30)])
ok("O6 official opening once: record has time, protocol, commit, manifest; guard works", _o6)
def _o7():
    d, m, a, p = _setup("o7"); open_holdout(m, a, p, COMMIT, d / "rec"); open_holdout(m, a, p, COMMIT, d / "rec")
raises("O7 second opening refused (one-time event)", _o7)
def _o8():
    d, m, a, p = _setup("o8"); r = open_holdout(m, a, p, COMMIT, d / "rec"); m.write_text('{"candidates": ["changed"]}')
    SegmentGuard("holdout", opening_record=r)
raises("O8 manifest changed after opening -> guard refuses", _o8)
def _o9():
    d, m, a, p = _setup("o9"); f = d / "forged.json"
    f.write_text(json.dumps({"event": "FINAL_HOLDOUT_OPENED", "commit": COMMIT, "manifest_sha256": "1" * 64, "protocol_sha256": "2" * 64,
                             "approval_sha256": "3" * 64, "manifest_file": str(m), "approval_file": str(a), "protocol_file": str(p)}))
    SegmentGuard("holdout", opening_record=f)
raises("O9 hand-written (forged) record not matching the approval refused", _o9)
def _o10():
    d, m, a, p = _setup("o10"); open_holdout(m, a, p, "HEAD", d / "rec")
raises("O10 opening with a non-commit id refused", _o10)

out = {"passed": sum(r["pass"] for r in res), "of": len(res), "PASS": all(r["pass"] for r in res), "tests": res}
print(json.dumps({k: out[k] for k in ("passed", "of", "PASS")}))
for r in res:
    if not r["pass"]:
        print("FAIL", r)
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], "w"), indent=1)
sys.exit(0 if out["PASS"] else 1)
