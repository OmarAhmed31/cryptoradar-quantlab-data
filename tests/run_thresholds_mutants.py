"""RD7 mutation runner (synthetic tests): every planted defect must make tests/test_thresholds.py FAIL.
python3 -I tests/run_thresholds_mutants.py <out.json>"""
import sys, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
P = "lab/thresholds.py"
MUT = [
 ("TM1 range high includes bar t", "R_high = Hi.rolling(W, min_periods=1).max().shift(1)", "R_high = Hi.rolling(W, min_periods=1).max()"),
 ("TM2 RVOL baseline includes bar t", "rvol = VQ / VQ.rolling(W, min_periods=MINW).median().shift(1)", "rvol = VQ / VQ.rolling(W, min_periods=MINW).median()"),
 ("TM3 peak window overlaps the range", "peak = Hi.rolling(PEAK, min_periods=PEAK // 2).max().shift(1 + W)", "peak = Hi.rolling(PEAK, min_periods=PEAK // 2).max().shift(1)"),
 ("TM4 excluded (pegged) coins kept", "    E.loc[:, [c for c in E.columns if is_excluded(c)]] = False\n    return E.reindex", "    return E.reindex"),
 ("TM5 eligibility ignored", "    E = U[\"P1\"][\"eligible\"].copy()\n    E.loc", "    E = U[\"P1\"][\"eligible\"].copy() | True\n    E.loc"),
 ("TM6 a stop limit applied before E5", "\"BO_stop\": vals(ind[\"stop\"], BO & ind[\"stop\"].notna())", "\"BO_stop\": vals(ind[\"stop\"], BO & (ind[\"stop\"] <= 0.05))"),
 ("TM7 RVOL >= 2 applied before R3", "\"R3_bear_rvol_P90\": _q(pops[\"BO_rvol\"], .90)", "\"R3_bear_rvol_P90\": _q(pops[\"BO_rvol\"][pops[\"BO_rvol\"] >= 2], .90)"),
 ("TM8 percentile levels swapped (E3 <-> R3)", "\"E3_rvol_P75\": _q(pops[\"BO_rvol\"], .75)", "\"E3_rvol_P75\": _q(pops[\"BO_rvol\"], .90)"),
 ("TM9 High-Vol from the full-period distribution", "        h = v[:i]; h = h[~np.isnan(h)]", "        h = v[~np.isnan(v)]"),
 ("TM10 an outcome module imported", "from lab.universe_crypto_only import is_excluded", "from lab.universe_crypto_only import is_excluded\nfrom lab import fd2"),
 ("TM11 E2 taken from BO instead of H", "pops = {\"H\": vals(ind[\"ratio\"], H & ind[\"ratio\"].notna())", "pops = {\"H\": vals(ind[\"ratio\"], BO & ind[\"ratio\"].notna())"),
 ("TM12 volatility window one day late (the reviewer's finding: extra shift)", "vol30 = ret.rolling(VOL_WIN, min_periods=VOL_WIN).std()", "vol30 = ret.rolling(VOL_WIN, min_periods=VOL_WIN).std().shift(1)"),
 ("TM13 volatility window uses a return not yet known at d", "vol30 = ret.rolling(VOL_WIN, min_periods=VOL_WIN).std()", "vol30 = ret.rolling(VOL_WIN, min_periods=VOL_WIN).std().shift(-1)"),
]
out = []
for name, a, b in MUT:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="thmut_"))
    shutil.copytree(REPO / "lab", tmp / "lab"); shutil.copytree(REPO / "tests", tmp / "tests"); (tmp / "out").symlink_to(REPO / "out")
    p = tmp / P; s = p.read_text(); assert s.count(a) == 1, (name, s.count(a)); p.write_text(s.replace(a, b))
    r = subprocess.run([sys.executable, "-I", "tests/test_thresholds.py"], cwd=tmp, capture_output=True, text=True, timeout=1800)
    last = (r.stdout.strip().splitlines() or [""])[-1]; fails = [l[:70] for l in r.stdout.splitlines() if l.startswith("FAIL")]
    killed = r.returncode != 0 or '"PASS": false' in last
    how = ("crash: " + (r.stderr.strip().splitlines() or ["?"])[-1][:120]) if r.returncode != 0 else "; ".join(fails)
    out.append({"mutant": name, "killed": killed, "by": how}); print(("KILLED " if killed else "SURVIVED ") + name, "|", how, flush=True)
    shutil.rmtree(tmp)
summ = {"killed": sum(o["killed"] for o in out), "of": len(out)}
json.dump({"mutants": out, **summ}, open(sys.argv[1], "w"), indent=1); print(json.dumps(summ))
