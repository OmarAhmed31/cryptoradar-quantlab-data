"""Planted-defect (mutant) runner for lab/exp4_counts.py. Each mutant is applied to a copy of the code and the synthetic
test suite tests/test_exp4.py is run on it. SYNTHETIC data only.

A mutant counts as KILLED (behaviourally) ONLY if ALL of these hold (reviewer requirement, v0.46):
  - the test run finished normally: no "Traceback" in stdout/stderr (no crash, SyntaxError, ImportError, exception);
  - the final summary line "<passed>/<total> passed" is present and <total> equals the baseline total
    (the unmutated suite, run first, must pass completely: every test was reached);
  - at least one test line starts with "FAIL" (a wrong behaviour was detected);
  - the exit code is non-zero.
Otherwise: SURVIVED (complete run, all tests pass, exit 0) or INVALID_TEST_RUN (anything else). Neither counts as killed.
python3 -I tests/run_exp4_mutants.py [out.json]"""
import sys, re, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
F = "lab/exp4_counts.py"
M = [
 ("YM1 K 3 -> 4", 'K_STAGE1 = 3 ', 'K_STAGE1 = 4 '),
 ("YM2 cash rule removed (a free slot is enough)", '        if not cash:\n', '        if False:\n'),
 ("YM3 fill information used in the selection", '        batch.sort(key=lambda s: (-s["rvol"], s["coin"]))', '        batch = [s for s in batch if fill(s) == "FILLED"] or batch; batch.sort(key=lambda s: (-s["rvol"], s["coin"]))'),
 ("YM4 ranking ascending", 'batch.sort(key=lambda s: (-s["rvol"], s["coin"]))', 'batch.sort(key=lambda s: (s["rvol"], s["coin"]))'),
 ("YM5 tie broken by coin descending", 'batch.sort(key=lambda s: (-s["rvol"], s["coin"]))', 'batch.sort(key=lambda s: (-s["rvol"], [-ord(ch) for ch in s["coin"]]))'),
 ("YM6 rounded RVOL", '"rvol": float(v),', '"rvol": round(float(v), 1),'),
 ("YM7 snapshot counts an exit AT h", '    return end_ns + 1 if xref_ns == end_ns else end_ns', '    return end_ns'),
 ("YM8 snapshot counts exits up to h + 1h", '            if p["free_at"] <= h:', '            if p["free_at"] <= h + 3600 * 10 ** 9:'),
 ("YM9 coin-held check removed", '            if s["coin"] in held:', '            if False:'),
 ("YM10 re-entry window check removed", '            elif s["coin"] in last_rf and s["ws"] < last_rf[s["coin"]]:', '            elif False:'),
 ("YM11 slot limit removed", '        if slots <= 0:', '        if False:'),
 ("YM12 cash stays available after a fully filled batch", '        cash = failed ', '        cash = True '),
 ("YM13 RVOL from the bar before the signal bar", 'return R[sig["row_entry"].values - 1, sig["col"].values]', 'return R[sig["row_entry"].values - 2, sig["col"].values]'),
 ("YM14 daily RVOL baseline includes day D", 'rolling(E3.D_WIN, min_periods=E3.D_MINW).median().shift(1)', 'rolling(E3.D_WIN, min_periods=E3.D_MINW).median()'),
 ("YM15 half-spread skip off", '        if E3.APPLY_HS_SKIP:', '        if False:'),
 ("YM16 wide-stop test on the bar close", '    fill = O[row, col]', '    fill = C[row, col]'),
 ("YM17 entry window ignored", '        if not (es <= s.entry_hour < ee) or s.row_entry >= n:', '        if s.row_entry >= n:'),
 ("YM18 L counts every opened trade", '    L = int(sum(int(s["c"]) for s in opened))', '    L = len(opened)'),
 ("YM19 D-D1 re-entry from the trade end", '"rf": E3.reentry_from(x.value, e.value, d)', '"rf": E3.reentry_from(e.value, e.value, d)'),
 ("YM20 daily RVOL from day D+1", 'R[sig["row_entry"].values // 24 - 1, sig["col"].values]', 'R[sig["row_entry"].values // 24, sig["col"].values]'),
 ("YM21 failed share not kept (cash lost)", '                reason[s["i"]] = f; failed = True ', '                reason[s["i"]] = f; failed = False '),
 ("YM22 fill checked for every batch member before selection", '        sel, rest = batch[:slots], batch[slots:]', '        [fill(s) for s in batch]; sel, rest = batch[:slots], batch[slots:]'),
 ("YM23 entry bar read for every eligible signal (old run order)", '        summ, reason, opened = portfolio(cands, K, _fill)', '        [_fill(x) for x in cands]; summ, reason, opened = portfolio(cands, K, _fill)'),
]
COPY = ("lab", "tests/test_exp4.py", "tests/test_exp3.py", "out/thresholds/run_v1/thresholds.json", "out/feature_discovery/feature_catalogue.json")
SUMMARY = re.compile(r"^(\d+)/(\d+) passed$")


def classify(returncode, stdout, stderr, expected_total):
    """KILLED / SURVIVED / INVALID_TEST_RUN, and the failing test names."""
    lines = stdout.splitlines()
    fails = [l.split(" ")[1] for l in lines if l.startswith("FAIL ") and len(l.split(" ")) > 1]
    summ = [SUMMARY.match(l.strip()) for l in lines if SUMMARY.match(l.strip())]
    crashed = "Traceback" in stdout or "Traceback" in stderr
    complete = bool(summ) and int(summ[-1].group(2)) == expected_total
    if crashed or not complete:
        return "INVALID_TEST_RUN", fails
    if fails and returncode != 0:
        return "KILLED", fails
    if not fails and returncode == 0:
        return "SURVIVED", fails
    return "INVALID_TEST_RUN", fails                                   # inconsistent exit code / FAIL lines


def run_suite(code_text):
    """run tests/test_exp4.py against a copy of the repository whose lab/exp4_counts.py is code_text."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="exp4_mut_"))
    try:
        for p in COPY:
            (d / p).parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if (REPO / p).is_dir() else shutil.copy2)(REPO / p, d / p)
        (d / F).write_text(code_text)
        r = subprocess.run([sys.executable, "-I", "tests/test_exp4.py"], cwd=d, capture_output=True, text=True, timeout=3600)
        return r.returncode, r.stdout, r.stderr
    finally:
        shutil.rmtree(d)


def main(out_path=None):
    src = (REPO / F).read_text(); out = []
    bad = [name for name, a, b in M if src.count(a) != 1]
    if bad: raise SystemExit(f"mutant text not found exactly once: {bad}")
    rc, so, se = run_suite(src)                                       # baseline: the unmutated suite must pass completely
    base = [SUMMARY.match(l.strip()) for l in so.splitlines() if SUMMARY.match(l.strip())]
    if rc != 0 or "Traceback" in so + se or not base or base[-1].group(1) != base[-1].group(2):
        raise SystemExit("baseline test run is not a complete pass: mutants cannot be judged")
    total = int(base[-1].group(2)); print(f"baseline: {total}/{total} passed", flush=True)
    for name, a, b in M:
        rc, so, se = run_suite(src.replace(a, b))
        status, fails = classify(rc, so, se, total)
        last = (se.strip().splitlines() or so.strip().splitlines() or [""])[-1][:160]
        out.append({"mutant": name, "status": status, "killed": status == "KILLED", "exit_code": rc,
                    "by": fails[:6], "detail": "" if status == "KILLED" else last})
        print(f"{status} {name} {out[-1]['by'] or out[-1]['detail']}", flush=True)
    k = sum(o["killed"] for o in out)
    print(f"{k}/{len(out)} killed (behavioural)")
    if out_path: pathlib.Path(out_path).write_text(json.dumps({"baseline_total": total, "mutants": out}, indent=1))
    return 0 if k == len(out) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
