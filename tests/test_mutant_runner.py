"""Tests of the mutant runner's classification (reviewer requirement, v0.46): a crash, a SyntaxError, an ImportError or an
incomplete test run is NEVER counted as a kill. Two cases run the real suite against broken code.
python3 -I tests/test_mutant_runner.py   -> exit code 1 if any test fails"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import importlib.util
spec = importlib.util.spec_from_file_location("runner", pathlib.Path(__file__).resolve().parent / "run_exp4_mutants.py")
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)        # main() is not run on import
res = []
def rec(name, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + name, str(detail)[:200], flush=True)

N = 36
ok_out = "\n".join(["PASS Y1a x"] * N) + f"\n{N}/{N} passed\n"
bh_out = "\n".join(["PASS Y1a x"] * (N - 1) + ["FAIL Y2 E1 lone signal opens {}"]) + f"\n{N-1}/{N} passed\n"
tb = 'Traceback (most recent call last):\n  File "x.py", line 1\n'
cases = [
    ("behavioural failure, complete run, exit 1 -> KILLED", (1, bh_out, ""), "KILLED"),
    ("all pass, exit 0 -> SURVIVED", (0, ok_out, ""), "SURVIVED"),
    ("SyntaxError before any test -> INVALID", (1, "", tb + "SyntaxError: invalid syntax\n"), "INVALID_TEST_RUN"),
    ("ImportError -> INVALID", (1, "", tb + "ImportError: cannot import name 'x'\n"), "INVALID_TEST_RUN"),
    ("crash midway after some FAIL lines -> INVALID", (1, "PASS Y1a x\nFAIL Y2 E1 y\n", tb + "KeyError: 3\n"), "INVALID_TEST_RUN"),
    ("FAIL lines but no summary (run cut short) -> INVALID", (1, "FAIL Y2 E1 y\n", ""), "INVALID_TEST_RUN"),
    ("summary total differs from the baseline (tests skipped) -> INVALID", (1, "FAIL Y2 E1 y\n3/30 passed\n", ""), "INVALID_TEST_RUN"),
    ("traceback printed on stdout -> INVALID", (1, bh_out + tb, ""), "INVALID_TEST_RUN"),
    ("FAIL lines but exit 0 (inconsistent) -> INVALID", (0, bh_out, ""), "INVALID_TEST_RUN"),
    ("no FAIL but exit 1 (inconsistent) -> INVALID", (1, ok_out, ""), "INVALID_TEST_RUN"),
]
for name, (rc, so, se), exp in cases:
    st, _ = R.classify(rc, so, se, N)
    rec(f"classify: {name}", st == exp, st)

# real runs of the suite against broken code (not mutants of the list): never counted as kills
src = (R.REPO / R.F).read_text()
rc, so, se = R.run_suite(src.replace("def portfolio(cands, K, fill=None):", "def portfolio(cands, K, fill=None)", 1))
st, _ = R.classify(rc, so, se, N); rec("real run: SyntaxError in the code -> INVALID_TEST_RUN, not KILLED", st == "INVALID_TEST_RUN", (st, rc))
rc, so, se = R.run_suite(src.replace("    L = int(sum(int(s[\"c\"]) for s in opened))", "    L = int(sum(int(s[\"c\"]) for s in opened)) + undefined_name", 1))
st, _ = R.classify(rc, so, se, N); rec("real run: crash (NameError) inside the engine -> INVALID_TEST_RUN, not KILLED", st == "INVALID_TEST_RUN", (st, rc))
rc, so, se = R.run_suite(src)
st, _ = R.classify(rc, so, se, N); rec("real run: unmutated code -> SURVIVED (complete 36/36)", st == "SURVIVED", (st, rc))
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
