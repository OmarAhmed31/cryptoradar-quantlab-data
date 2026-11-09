"""FA5 mutation runner for FD-2: every planted defect must make tests/test_fd2.py --fast FAIL.
python3 -I tests/run_fd2_mutants.py <out.json>"""
import sys, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
P = "lab/fd2.py"
MUT = [
 ("N01 IC t-stat without overlap correction (lag 0 for every h)", P, "t, p = newey_west_t(v, h - 1)", "t, p = newey_west_t(v, 0)"),
 ("N02 BH replaced by raw p", P, 'P.loc[conf, "p_bh"] = bh(P.loc[conf, "p_two_sided"].values)', 'P.loc[conf, "p_bh"] = P.loc[conf, "p_two_sided"].values'),
 ("N03 delisted removed from outcomes (forced exits dropped)", P, 'V[i, j] = r["last_trade_price"] / entry - 1', 'V[i, j] = np.nan'),
 ("N04 forced exit only when the cut is before the last day (cuts on day d+h-1 priced late)", P, "elif c < d + pd.Timedelta(days=h):", "elif c < d + pd.Timedelta(days=h - 1):"),
 ("N05 outcome crossing Development end (entry window to 2025-08-31)", P, 'ENTRY_END = pd.Timestamp("2025-08-02", tz="UTC")', 'ENTRY_END = pd.Timestamp("2025-08-31", tz="UTC")'),
 ("N06 entry price from day d itself (lookahead)", P, "entry = lc[i - 1] if i >= 1 else np.full(nS, np.nan)", "entry = lc[i] if i >= 1 else np.full(nS, np.nan)"),
 ("N07 exploratory cells included in BH", P, 'P.loc[conf, "p_bh"] = bh(P.loc[conf, "p_two_sided"].values)', 'P.loc[conf, "p_bh"] = bh(P["p_two_sided"].values)[conf.values]'),
 ("N08 BY used as the candidate rule", P, 'P["candidate"] = P.bh_sig & (P.subperiods_same_sign == 3)', 'P["candidate"] = P.by_sig & (P.subperiods_same_sign == 3)'),
 ("N09 sub-period rule relaxed to 2 of 3", P, 'P["candidate"] = P.bh_sig & (P.subperiods_same_sign == 3)', 'P["candidate"] = P.bh_sig & (P.subperiods_same_sign >= 2)'),
 ("N10 S250k sign check dropped", P, "& P.sign_same_S50k & P.sign_same_S250k & (sgn != 0)", "& P.sign_same_S50k & (sgn != 0)"),
 ("N11 bootstrap with 1-day blocks", P, "lo, hi = boot_ci(v, max(7, h), np.random.default_rng(SEED))", "lo, hi = boot_ci(v, 1, np.random.default_rng(SEED))"),
 ("N12 eligibility ignored in the IC", P, "m = e[i] & ~np.isnan(x[i]) & ~np.isnan(y[i])", "m = ~np.isnan(x[i]) & ~np.isnan(y[i])"),
 ("N13 one-sided p instead of two-sided", P, "p = math.erfc(abs(t) / math.sqrt(2)) if not np.isnan(t) else np.nan", "p = math.erfc(abs(t) / math.sqrt(2)) / 2 if not np.isnan(t) else np.nan"),
]
out = []
for name, f, a, b in MUT:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fd2mut_"))
    shutil.copytree(REPO / "lab", tmp / "lab"); shutil.copytree(REPO / "tests", tmp / "tests")
    (tmp / "out").symlink_to(REPO / "out")
    p = tmp / f; s = p.read_text(); assert s.count(a) == 1, (name, s.count(a))
    p.write_text(s.replace(a, b))
    r = subprocess.run([sys.executable, "-I", "tests/test_fd2.py", "--fast"], cwd=tmp, capture_output=True, text=True, timeout=3000)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    killed = r.returncode != 0 or '"PASS": false' in last
    how = ("crash: " + (r.stderr.strip().splitlines() or ["?"])[-1][:150]) if r.returncode != 0 else "; ".join(x[:80] for x in fails)
    out.append({"mutant": name, "killed": killed, "by": how}); print(("KILLED " if killed else "SURVIVED ") + name, "|", how, flush=True)
    shutil.rmtree(tmp)
summ = {"killed": sum(o["killed"] for o in out), "of": len(out)}
json.dump({"mutants": out, **summ}, open(sys.argv[1], "w"), indent=1); print(json.dumps(summ))
