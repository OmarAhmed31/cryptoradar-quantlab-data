"""Planted-defect (mutant) runner for lab/exp4_counts.py. Each mutant is applied to a copy of the code; the synthetic
test suite tests/test_exp4.py must FAIL on it (killed). SYNTHETIC data only.
python3 -I tests/run_exp4_mutants.py [out.json]"""
import sys, json, shutil, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
F = "lab/exp4_counts.py"
M = [
 ("YM1 K 3 -> 4", 'K_STAGE1 = 3 ', 'K_STAGE1 = 4 '),
 ("YM2 cash rule removed (a free slot is enough)", '        if not cash:\n', '        if False:\n'),
 ("YM3 fill information used in the selection", '        batch.sort(key=lambda s: (-s["rvol"], s["coin"]))', '        batch = [s for s in batch if s["fill"] == "FILLED"] or batch; batch.sort(key=lambda s: (-s["rvol"], s["coin"]))'),
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
 ("YM16 wide-stop test on the bar close", '        fill = O[s.row_entry, s.col]', '        fill = C[s.row_entry, s.col]'),
 ("YM17 entry window ignored", '        if not (es <= s.entry_hour < ee) or s.row_entry >= n:', '        if s.row_entry >= n:'),
 ("YM18 L counts every opened trade", '    L = int(sum(int(s["c"]) for s in opened))', '    L = len(opened)'),
 ("YM19 D-D1 re-entry from the trade end", '"rf": E3.reentry_from(x.value, e.value, d)', '"rf": E3.reentry_from(e.value, e.value, d)'),
 ("YM20 daily RVOL from day D+1", 'R[sig["row_entry"].values // 24 - 1, sig["col"].values]', 'R[sig["row_entry"].values // 24, sig["col"].values]'),
 ("YM21 failed share not kept (cash lost)", '                reason[s["i"]] = s["fill"]; failed = True ', '                reason[s["i"]] = s["fill"]; failed = False '),
 ("YM22 fill checks applied before the portfolio (v0.3 timing)", '        fills = fill_check(ok, Hh, d["stop_limit"])', '        fills = fill_check(ok, Hh, d["stop_limit"]); ok = ok[[f == "FILLED" for f in fills]].reset_index(drop=True); fills = ["FILLED"] * len(ok)'),
]
src = (REPO / F).read_text(); out = []
bad = [name for name, a, b in M if src.count(a) != 1]
if bad: raise SystemExit(f"mutant text not found exactly once: {bad}")
for name, a, b in M:
    assert src.count(a) == 1, name
    d = pathlib.Path(tempfile.mkdtemp(prefix="exp4_mut_"))
    for p in ("lab", "tests/test_exp4.py", "tests/test_exp3.py", "out/thresholds/run_v1/thresholds.json", "out/feature_discovery/feature_catalogue.json"):
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if (REPO / p).is_dir() else shutil.copy2)(REPO / p, d / p)
    (d / F).write_text(src.replace(a, b))
    r = subprocess.run([sys.executable, "-I", "tests/test_exp4.py"], cwd=d, capture_output=True, text=True, timeout=3600)
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
    killed = r.returncode != 0
    out.append({"mutant": name, "killed": killed, "by": [f.split(" ")[1] for f in fails][:6] or ([r.stderr.strip().splitlines()[-1][:120]] if r.stderr.strip() else [])})
    print(("KILLED " if killed else "SURVIVED ") + name, out[-1]["by"], flush=True)
    shutil.rmtree(d)
k = sum(o["killed"] for o in out)
print(f"{k}/{len(out)} killed")
if len(sys.argv) > 1: pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
sys.exit(0 if k == len(out) else 1)
