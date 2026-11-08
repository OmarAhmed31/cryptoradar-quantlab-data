"""Tests for lab/segment_loader.py (Protocol v1.2 access rules). Synthetic timestamps only; no market data.
python3 -I tests/test_segment_loader.py [out.json]"""
import sys, json, pathlib, datetime as dt, tempfile, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SegmentGuard, GuardError, H, H_MAX, open_holdout, SEGMENTS


# --- files that LOOK like a valid opening (correct hashes), in a temp dir: used only to prove they are refused
TMP = pathlib.Path(tempfile.mkdtemp(prefix="holdout_test_"))
def _valid_looking(name):
    d = TMP / name; d.mkdir()
    man = d / "candidate_freeze_manifest.json"; man.write_text('{"candidates": ["synthetic-test-only"]}')
    proto = d / "PROTOCOL.md"; proto.write_text("synthetic protocol for tests")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    appr = d / "approval.json"
    appr.write_text(json.dumps({"manifest_sha256": sha(man), "protocol_sha256": sha(proto), "approved_by": "test", "approved_utc": "2026-01-01T00:00:00Z"}))
    rec = d / "HOLDOUT_OPENED.json"           # the reviewer's forgery: hand-written record with CORRECT hashes
    rec.write_text(json.dumps({"event": "FINAL_HOLDOUT_OPENED", "opened_utc": "2026-01-01T00:00:00Z", "commit": "a" * 40,
                               "manifest_sha256": sha(man), "protocol_sha256": sha(proto), "approval_sha256": sha(appr),
                               "manifest_file": str(man), "approval_file": str(appr), "protocol_file": str(proto)}))
    return d, man, appr, proto, rec
COMMIT = "a" * 40

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
ok("D1 Validation feature at a Validation date: accepted", lambda: val.check_feature(T(2025, 12, 1), [T(2025, 11, 30, 22)]))
raises("D2 Validation feature at a Development date: refused", lambda: val.check_feature(T(2025, 6, 1), [T(2025, 5, 31)]))
raises("D3 Validation feature at a Holdout date (2026-05-01), past candle only: refused", lambda: val.check_feature(T(2026, 5, 1), [T(2026, 4, 30)]))
raises("D4 Development feature at a Validation date: refused", lambda: dev.check_feature(T(2025, 10, 1), [T(2025, 9, 30)]))
raises("D5 Holdout feature: refused (no Holdout guard can exist in v1.2)", lambda: SegmentGuard("holdout").check_feature(T(2026, 5, 1), [T(2026, 4, 30)]))
raises("D7 Validation feature at an embargo date: refused", lambda: val.check_feature(T(2025, 9, 3), [T(2025, 9, 2)]))
# H6: MI / regime fitting only on Development
raises("MI statistic on Validation refused", lambda: val.check_research_statistic(T(2025, 10, 1), []))
ok("MI statistic on Development with past data", lambda: dev.check_research_statistic(T(2024, 3, 1), hrs(T(2024, 1, 31), 24)))
raises("MI statistic on Development using future data refused", lambda: dev.check_research_statistic(T(2024, 3, 1), [T(2024, 3, 1, 5)]))
# H7: holdout sealed
raises("Final Holdout sealed without the logged opening", lambda: SegmentGuard("holdout"))
def _cut():                                   # T4 constants for the Holdout, checked statically (no guard can be built)
    ds, de, es, ee = SEGMENTS["holdout"]
    assert ee == T(2026, 10, 1, 16) and ee + H_MAX == de and es == ds == T(2026, 4, 8)
ok("holdout entry cut constant = 2026-10-01 16:00 = T2 - 30 d (static check)", _cut)
# --- Holdout: NO opening path in v1.2 (v0.10.8, after the reviewer's forgery finding)
raises("O1 holdout guard with no argument refused", lambda: SegmentGuard("holdout"))
def _o2():
    try:
        SegmentGuard("holdout", holdout_opened=True)
    except TypeError:
        raise GuardError("no such switch")
raises("O2 boolean switch holdout_opened=True does not exist", _o2)
def _o3():
    d, m, a, p, r = _valid_looking("o3")
    try:
        SegmentGuard("holdout", opening_record=r)
    except TypeError:
        raise GuardError("no such argument")
raises("O3 reviewer's forgery: hand-written record with CORRECT hashes cannot open a Holdout guard", _o3)
def _o4():
    d, m, a, p, r = _valid_looking("o4"); open_holdout(m, a, p, COMMIT, d / "rec")
raises("O4 opening with a valid-looking manifest + approval + protocol + commit refused", _o4)
def _o5():
    d, m, a, p, r = _valid_looking("o5")
    try:
        open_holdout(m, a, p, COMMIT, d / "rec")
    except GuardError:
        pass
    assert not (d / "rec").exists()
ok("O5 a refused opening writes nothing (no record dir created)", _o5)
def _o6():
    d, m, a, p, r = _valid_looking("o6"); r.unlink()
    open_holdout(m, a, p, COMMIT, d)       # 'delete the record and re-open'
raises("O6 deleting a record and re-opening refused", _o6)
raises("O7 opening with keyword arguments only refused", lambda: open_holdout(manifest="x", approval="y", protocol_file="z", commit=COMMIT, record_dir="w"))
def _o8():
    import lab.segment_loader as L
    assert not any(hasattr(L, n) for n in ("verify_opening_record", "_verify_inputs")), "an opening/verification path still exists"
ok("O8 no record-verification code path exists in the module", _o8)

out = {"passed": sum(r["pass"] for r in res), "of": len(res), "PASS": all(r["pass"] for r in res), "tests": res}
print(json.dumps({k: out[k] for k in ("passed", "of", "PASS")}))
for r in res:
    if not r["pass"]:
        print("FAIL", r)
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], "w"), indent=1)
sys.exit(0 if out["PASS"] else 1)
