"""VA7 mutation runner for the Validation run: every planted defect must make tests/test_val.py --fast FAIL.
python3 -I tests/run_val_mutants.py <out.json>"""
import sys, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
P, F2 = "lab/val.py", "lab/fd2.py"
MUT = [
 ("W01 two-sided p instead of one-sided", P, "return 0.5 * math.erfc(direction * t / math.sqrt(2)) if not np.isnan(t) else np.nan", "return math.erfc(abs(t) / math.sqrt(2)) if not np.isnan(t) else np.nan"),
 ("W02 direction not taken from FD-2 (always +1)", P, 'f, h, dirn = x["feature"], x["h_days"], x["direction"]', 'f, h, dirn = x["feature"], x["h_days"], 1'),
 ("W03 family re-selected (BH_ONLY dropped)", P, 'fam = json.loads(b)["hypotheses"]', 'fam = [x for x in json.loads(b)["hypotheses"] if "BH_ONLY" not in x["fd2_label"]]'),
 ("W04 entries in the embargo", P, "F2.ENTRY_IDX = np.where((DAYS_X >= V_ES) & (DAYS_X < V_EE))[0]", "F2.ENTRY_IDX = np.where((DAYS_X >= V_ES - pd.Timedelta(days=7)) & (DAYS_X < V_EE))[0]"),
 ("W05 outcomes crossing 2026-04-01 (entries to 2026-03-31)", P, "F2.ENTRY_IDX = np.where((DAYS_X >= V_ES) & (DAYS_X < V_EE))[0]", "F2.ENTRY_IDX = np.where((DAYS_X >= V_ES) & (DAYS_X < V_DE))[0]"),
 ("W06 same-day entry price (lookahead, shared FD-2 code)", F2, "entry = lc[i - 1] if i >= 1 else np.full(nS, np.nan)", "entry = lc[i] if i >= 1 else np.full(nS, np.nan)"),
 ("W07 delisted dropped (forced exits removed)", F2, 'V[i, j] = r["last_trade_price"] / entry - 1', "V[i, j] = np.nan"),
 ("W08 forced exit at a later day", F2, "elif c < d + pd.Timedelta(days=h):", "elif c < d + pd.Timedelta(days=h - 1):"),
 ("W09 no overlap correction (lag 0)", P, "t, _ = F2.newey_west_t(v, h - 1)", "t, _ = F2.newey_west_t(v, 0)"),
 ("W10 BY used as the rule", P, 'return "REPLICATED" if p_by <= Q else "REPLICATED — BH_ONLY — FAILS_BY_SENSITIVITY"\n    return "NOT_REPLICATED"', 'return "REPLICATED" if p_by <= Q else "NOT_REPLICATED"\n    return "NOT_REPLICATED"'),
 ("W11 eligibility ignored in the IC", P, "daily[sc][(f, h)] = F2.daily_ic(F[f], OUT[h][0], M[sc])", "daily[sc][(f, h)] = F2.daily_ic(F[f], OUT[h][0], M[sc] | ~M[sc])"),
 ("W12 cluster rule relaxed (one replicated member is enough)", P, 'lab = "CLUSTER_REPLICATED" if (R >= n / 2 and V == 0)', 'lab = "CLUSTER_REPLICATED" if (R >= 1)'),
 ("W13 ratio shown even when the Development CI includes 0", P, "if dev == 0 or (ci[0] <= 0 <= ci[1]):", "if dev == 0:"),
 ("W14 Validation features with a window reaching day d (shared FD code)", "lab/fd_features.py", "L = lr[i - w:i].reshape", "L = lr[i - w + 1:i + 1].reshape"),
]
out = []
for name, f, a, b in MUT:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="valmut_"))
    shutil.copytree(REPO / "lab", tmp / "lab"); shutil.copytree(REPO / "tests", tmp / "tests")
    (tmp / "out").symlink_to(REPO / "out")
    p = tmp / f; s = p.read_text(); assert s.count(a) == 1, (name, s.count(a))
    p.write_text(s.replace(a, b))
    r = subprocess.run([sys.executable, "-I", "tests/test_val.py", "--fast"], cwd=tmp, capture_output=True, text=True, timeout=3600)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    killed = r.returncode != 0 or '"PASS": false' in last
    how = ("crash: " + (r.stderr.strip().splitlines() or ["?"])[-1][:150]) if r.returncode != 0 else "; ".join(x[:70] for x in fails)
    out.append({"mutant": name, "killed": killed, "by": how}); print(("KILLED " if killed else "SURVIVED ") + name, "|", how, flush=True)
    shutil.rmtree(tmp)
summ = {"killed": sum(o["killed"] for o in out), "of": len(out)}
json.dump({"mutants": out, **summ}, open(sys.argv[1], "w"), indent=1); print(json.dumps(summ))
