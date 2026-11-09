"""SA7 mutation runner for the strategy simulator: every planted defect must make tests/test_strategy.py --fast FAIL.
python3 -I tests/run_strategy_mutants.py <out.json>"""
import sys, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
P = "lab/strategy.py"
MUT = [
 ("X01 same-day reference price (lookahead)", "return self.lc[i - 1] if i >= 1 else np.full(self.nS, np.nan)", "return self.lc[i] if i >= 1 else np.full(self.nS, np.nan)"),
 ("X02 buying ineligible coins", "ok = E.values[i] & ~np.isnan(self.ref(i))", "ok = (E.values[i] | ~E.values[i]) & ~np.isnan(self.ref(i))"),
 ("X03 spread cost skipped on turnover", "fees += dlt * fee; spc += dlt * h_; turn += dlt", "fees += dlt * fee; turn += dlt"),
 ("X04 spread from a window reaching day d", "h = Hi.values[(i - 30) * 24:i * 24]; l = Lo.values[(i - 30) * 24:i * 24]", "h = Hi.values[(i - 29) * 24:(i + 1) * 24]; l = Lo.values[(i - 29) * 24:(i + 1) * 24]"),
 ("X05 delisted dropped (forced-exit proceeds lost)", 'cash += q[j] * ct[1] * (1 - fee - hs_buy.get(j, 0.0)); fees += q[j] * ct[1] * fee', 'fees += q[j] * ct[1] * fee'),
 ("X06 forced exit at a later price (hourly mark)", "if ct is not None and d < ct[0] < end:", "if ct is not None and d < ct[0] < end and False:"),
 ("X07 selection not restricted to fee 0.10 % (any fee row)", "(summary.capital == gating_capital) & (summary.fee == \"fee_0.10\") &", "(summary.capital == gating_capital) &"),
 ("X08 two-sided p", "return t, (0.5 * math.erfc(t / math.sqrt(2)) if not np.isnan(t) else np.nan)", "return t, (math.erfc(abs(t) / math.sqrt(2)) if not np.isnan(t) else np.nan)"),
 ("X09 B1 without costs", "    gross = fee is None\n", "    gross = fee is None or kind == \"B1\"\n"),
 ("X10 1 % cap ignored", "tgt = {int(j): min(base, cap[j]) for j in sel}", "tgt = {int(j): base for j in sel}"),
 ("X11 tie-break prefers Top 20", 'ascending=[False, True, True])', 'ascending=[False, True, False])'),
 ("X12 Development start not the first day with >= 20 B-tradeable coins", "if self.tradeable(i, \"B\", \"P1\").sum() >= 20:", "if self.tradeable(i, \"B\", \"P1\").sum() >= 5:"),
 ("X13 RELATIVE_ONLY flag dropped", '"flag": "RELATIVE_ONLY — NOT_PROFITABLE_ABSOLUTE" if (ok and a.total_net_return <= 0) else ""', '"flag": ""'),
 ("X14 gate ignores the 2x-fee condition", "ok = bool(a.p_nw_one_sided <= 0.05 and a.p_boot_one_sided <= 0.05 and b.mean_excess_vs_B1 > 0)", "ok = bool(a.p_nw_one_sided <= 0.05 and a.p_boot_one_sided <= 0.05)"),
]
out = []
for name, a, b in MUT:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="stmut_"))
    shutil.copytree(REPO / "lab", tmp / "lab"); shutil.copytree(REPO / "tests", tmp / "tests"); (tmp / "out").symlink_to(REPO / "out")
    p = tmp / P; s = p.read_text(); assert s.count(a) == 1, (name, s.count(a)); p.write_text(s.replace(a, b))
    r = subprocess.run([sys.executable, "-I", "tests/test_strategy.py", "--fast"], cwd=tmp, capture_output=True, text=True, timeout=3600)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    killed = r.returncode != 0 or '"PASS": false' in last
    how = ("crash: " + (r.stderr.strip().splitlines() or ["?"])[-1][:150]) if r.returncode != 0 else "; ".join(x[:60] for x in fails)
    out.append({"mutant": name, "killed": killed, "by": how}); print(("KILLED " if killed else "SURVIVED ") + name, "|", how, flush=True)
    shutil.rmtree(tmp)
summ = {"killed": sum(o["killed"] for o in out), "of": len(out)}
json.dump({"mutants": out, **summ}, open(sys.argv[1], "w"), indent=1); print(json.dumps(summ))
