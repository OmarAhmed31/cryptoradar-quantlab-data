"""FA5 mutation runner for FD-1: each mutant is a planted defect; the FD-1 tests (--fast) must FAIL for every one.
python3 -I tests/run_fd1_mutants.py <out.json>"""
import sys, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
MUT = [
 ("M01 same-day close in returns", "lab/fd_features.py", 'ca = lc[i - 1] if i >= 1 else np.full(nS, np.nan)\n        for f, k', 'ca = lc[i] if i >= 1 else np.full(nS, np.nan)\n        for f, k'),
 ("M02 hourly window includes day d", "lab/fd_features.py", "L = lr[i - w:i].reshape", "L = lr[i - w + 1:i + 1].reshape"),
 ("M03 eligibility of d+1 used", "lab/fd1.py", '        e = U[k]["eligible"]\n', '        e = U[k]["eligible"].shift(-1).fillna(False).astype(bool)\n'),
 ("M04 time-series (full-period) ranks instead of daily cross-sectional ranks in Q3", "lab/fd1.py", "        X = F[f].where(E).values\n        for k in (1, 7):", "        X = F[f].where(E).rank(pct=True).values\n        for k in (1, 7):"),
 ("M05 persistence ignores eligibility on d+k", "lab/fd1.py", "r = np.array([daily_spearman(X[i], X[j]) for i, j in ps])", "r = np.array([daily_spearman(X[i], F[f].values[j]) for i, j in ps])"),
 ("M06 regime label of d+1 attached to day d", "lab/fd1.py", 'index=pd.to_datetime(r["day"]).dt.tz_localize("UTC"))', 'index=pd.to_datetime(r["day"]).dt.tz_localize("UTC") - pd.Timedelta(days=1))'),
 ("M07 bootstrap draws single days (iid), not 7-day blocks", "lab/fd1.py", "    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]) % n\n    return idx.reshape(NBOOT, -1)[:, :n]", "    return rng.integers(0, n, size=(NBOOT, n))"),
 ("M08 LOW_N state gets a CI", "lab/fd1.py", "if s != REF and not low:", "if s != REF:"),
 ("M09 vol_30 window changed after the catalogue (31 days)", "lab/fd_features.py", '(30, "F07", None)', '(31, "F07", None)'),
 ("M10 return window shortened at the research start (wraps to a later day)", "lab/fd_features.py", "            if i - k - 1 >= 0:", "            if i - k - 1 >= -1:"),
 ("M11 survivors lens keeps later-delisted series", "lab/fd1.py", '        s = e.copy(); s[[c for c in s.columns if groups.get(c) != "active"]] = False', '        s = e.copy()'),
 ("M12 30-day high includes day d", "lab/fd_features.py", "hmax = np.nanmax(np.where(np.isnan(hi3[i - 30:i]), -np.inf, hi3[i - 30:i]), (0, 1))", "hmax = np.nanmax(np.where(np.isnan(hi3[i - 29:i + 1]), -np.inf, hi3[i - 29:i + 1]), (0, 1))"),
 ("M13 Amihud uses day d", "lab/fd_features.py", "a = np.abs(dlr[i - 30:i]) / dq[i - 30:i]", "a = np.abs(dlr[i - 29:i + 1]) / dq[i - 29:i + 1]"),
 ("M14 beta window reaches d+1", "lab/fd_features.py", "y = r1[max(0, i - 29):i + 1]", "y = r1[max(0, i - 28):i + 2]"),
]
out = []
for name, f, a, b in MUT:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fdmut_"))
    shutil.copytree(REPO / "lab", tmp / "lab"); shutil.copytree(REPO / "tests", tmp / "tests")
    (tmp / "out").symlink_to(REPO / "out")
    p = tmp / f; s = p.read_text()
    assert s.count(a) == 1, (name, s.count(a))
    p.write_text(s.replace(a, b))
    r = subprocess.run([sys.executable, "-I", "tests/test_fd1.py", "--fast"], cwd=tmp, capture_output=True, text=True, timeout=3000)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    killed = r.returncode != 0 or '"PASS": false' in last
    how = "crash: " + r.stderr.strip().splitlines()[-1][:150] if r.returncode != 0 else "; ".join(x[:90] for x in fails)
    out.append({"mutant": name, "file": f, "killed": killed, "by": how}); print(("KILLED " if killed else "SURVIVED ") + name, "|", how, flush=True)
    shutil.rmtree(tmp)
summ = {"killed": sum(o["killed"] for o in out), "of": len(out)}
json.dump({"mutants": out, **summ}, open(sys.argv[1], "w"), indent=1); print(json.dumps(summ))
