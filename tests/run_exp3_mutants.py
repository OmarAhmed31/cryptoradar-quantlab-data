"""Planted-defect (mutant) runner for lab/exp3_counts.py. Each mutant is applied to a copy of the code; the synthetic
test suite tests/test_exp3.py must FAIL on it (killed). SYNTHETIC data only.
python3 -I tests/run_exp3_mutants.py [out.json]"""
import sys, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
F = "lab/exp3_counts.py"
M = [
 ("XM1 H_max 720 h -> 744 h", 'H_MAX = pd.Timedelta(hours=720)', 'H_MAX = pd.Timedelta(hours=744)'),
 ("XM2 unpriceable forced exit counted", 'ok = cut[1] and cut[0] < s.entry_hour + H_MAX', 'ok = cut[0] < s.entry_hour + H_MAX'),
 ("XM3 H_max check dropped for the time exit", 'if xb is not None and xb + HOUR <= min(s.entry_hour + H_MAX, seg_end):', 'if xb is not None and xb + HOUR <= seg_end:'),
 ("XM4 exit bar may sit inside the deadline hour", 'dl = s.entry_hour + HOUR + HOLD', 'dl = s.entry_hour + HOLD'),
 ("XM5 daily range window includes day D", 'RH = hi.where(traded).rolling(D_WIN, min_periods=D_MINW).max().shift(1)', 'RH = hi.where(traded).rolling(D_WIN, min_periods=D_MINW).max()'),
 ("XM6 daily RVOL baseline includes day D", 'vol.where(traded).rolling(D_WIN, min_periods=D_MINW).median().shift(1)', 'vol.where(traded).rolling(D_WIN, min_periods=D_MINW).median()'),
 ("XM7 RVOL_d level P75 -> P70", 'P_RVOL_D, P_STOP_D = 0.75, 0.90', 'P_RVOL_D, P_STOP_D = 0.70, 0.90'),
 ("XM8 daily thresholds taken after the A1 filter", 'P75 = _q(rvol.values[BO.values & rvol.notna().values], P_RVOL_D)', 'P75 = _q(rvol.values[(BO & a1.fillna(False)).values & rvol.notna().values], P_RVOL_D)'),
 ("XM9 daily eligibility on D instead of D+1", '.shift(-1).fillna(False).astype(bool)   # P1-eligible on D+1', '.fillna(False).astype(bool)'),
 ("XM10 daily abstention uses the state of D", 'trans.reindex(nxt).fillna(True)', 'trans.reindex(FF.DAYS).fillna(True)'),
 ("XM11 hourly entry hour = t", '"entry_hour": t + HOUR,', '"entry_hour": t,'),
 ("XM12 greedy ignores the same-coin window rule", 'if s["coin"] in last and s["ws"] < last[s["coin"]]:', 'if False:'),
 ("XM13 L_worst without the early-exit option", 'V[i] = min(full, 1 + min(W(s["coin"], ei, e) for e in early))', 'V[i] = full'),
 ("XM14 L_worst treats maybe-blocked signals as free", 'free = ci is None or s["coin"] == ci or s["ws"] >= ei', 'free = True'),
 ("XM15 excluded coins kept (daily)", 'E = U["P1"]["eligible"].copy(); E.loc[:, [c for c in E.columns if is_excluded(c)]] = False\n    elig_next', 'E = U["P1"]["eligible"].copy()\n    elig_next'),
 ("XM16 rounded hourly thresholds", 'return json.loads(b)["thresholds"]', 'return {k: round(v, 3) for k, v in json.loads(b)["thresholds"].items()}'),
 ("XM17 ledger price column read", 'd = pd.read_csv(path, usecols=LEDGER_COLS)', 'd = pd.read_csv(path)'),
 ("XM18 selection: D-H1 wins the tie", 'PREFERENCE = ["D-D1", "D-H1", "D-H2"]', 'PREFERENCE = ["D-H1", "D-D1", "D-H2"]'),
 ("XM19 wide-stop test on the bar close", 'fill = O[s.row_entry, s.col]', 'fill = C[s.row_entry, s.col]'),
 ("XM20 hourly A1 window includes bar t", 'width.rolling(180 * 24, min_periods=90 * 24).quantile(0.25).shift(1)', 'width.rolling(180 * 24, min_periods=90 * 24).quantile(0.25)'),
 ("XM21 hourly Transition abstention dropped", '("not_transition", ~abst)]:', ('("not_transition", abst | ~abst)]:')),
 ("XM22 daily close = first traded close", 'cl = g("close").last().reindex(FF.DAYS)', 'cl = g("close").first().reindex(FF.DAYS)'),
 ("XM23 thresholds sha not enforced", 'if hashlib.sha256(b).hexdigest() != THR_SHA:', 'if False:'),
 ("XM24 half-spread skip off", 'if APPLY_HS_SKIP:', 'if False:'),
 ("XM25 delisting cut ignored", 'if cut is not None and s.entry_hour <= cut[0] < block_end:', 'if False:'),
 ("XM26 entry cut ignored", 'if not (es <= s.entry_hour < ee) or s.row_entry >= n:', 'if s.row_entry >= n:'),
]
src = (REPO / F).read_text(); out = []
for name, a, b in M:
    assert src.count(a) == 1, name
    d = pathlib.Path(tempfile.mkdtemp(prefix="exp3_mut_"))
    for p in ("lab", "tests/test_exp3.py", "out/thresholds/run_v1/thresholds.json", "out/feature_discovery/feature_catalogue.json"):
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if (REPO / p).is_dir() else shutil.copy2)(REPO / p, d / p)
    (d / F).write_text(src.replace(a, b))
    r = subprocess.run([sys.executable, "-I", "tests/test_exp3.py"], cwd=d, capture_output=True, text=True, timeout=3600)
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    killed = r.returncode != 0
    out.append({"mutant": name, "killed": killed, "by": [f.split(" ")[1] for f in fails][:6] or ([r.stderr.strip().splitlines()[-1][:120]] if r.stderr.strip() else [])})
    print(("KILLED " if killed else "SURVIVED ") + name, out[-1]["by"], flush=True)
    shutil.rmtree(d)
k = sum(o["killed"] for o in out)
print(f"{k}/{len(out)} killed")
if len(sys.argv) > 1: pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
sys.exit(0 if k == len(out) else 1)
