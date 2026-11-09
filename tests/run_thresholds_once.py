"""THE ONE derivation run + RD4 (plan v0.3.1 §6). Executes lab/thresholds.py three times and requires byte-identical output:
  run 1  in the repository;
  run 2  in a copy where every earlier OUTCOME file (FD-2, Validation, strategy, attribution) is overwritten with garbage;
  run 3  in an ISOLATED directory holding only the derivation code, the frozen feature code, the segment guard, the
         exclusion list and the Development pack (no outcome files, no repository history), with network disabled
         for the process (unshare -rn) and python -I.
python3 -I tests/run_thresholds_once.py <out_dir>   (writes thresholds.json + rd4_result.json)"""
import sys, json, shutil, hashlib, subprocess, tempfile, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
PACK = "out/market_intelligence/dev_pack_v1"
CODE = ["lab/__init__.py", "lab/thresholds.py", "lab/fd_features.py", "lab/segment_loader.py", "lab/universe_crypto_only.py",
        "out/feature_discovery/feature_catalogue.json"]
OUTCOME_DIRS = ["out/feature_discovery/fd2_v0.14", "out/validation", "out/strategy"]
# Strategy ATTRIBUTION outputs live under out/strategy/dev_v0.18 and out/strategy/val_v0.19 (attrib_*). The runner
# verifies that below: every attribution file anywhere under out/ must be inside OUTCOME_DIRS, else it stops.
_attr = [f for f in (REPO / "out").rglob("attrib*") if f.is_file()]
_outside = [str(f.relative_to(REPO)) for f in _attr if not any(str(f.relative_to(REPO)).startswith(d + "/") for d in OUTCOME_DIRS)]
if not _attr or _outside:
    raise SystemExit(f"RD4 precondition failed: attribution files missing or outside the corrupted paths: {_outside}")

def run(cwd, dest, isolate=False):
    cmd = [sys.executable, "-I", "lab/thresholds.py", str(dest)]
    if isolate:
        cmd = ["unshare", "-rn"] + cmd
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=7200)
    if r.returncode != 0:
        raise SystemExit(f"run failed in {cwd}: {r.stderr[-500:]}")
    return (pathlib.Path(dest) / "thresholds.json").read_bytes()

b1 = run(REPO, out / "run1_repo")
tmp = pathlib.Path(tempfile.mkdtemp(prefix="thr_rd4_"))
c2 = tmp / "corrupted"; c2.mkdir()
for p in CODE: (c2 / p).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(REPO / p, c2 / p)
shutil.copytree(REPO / PACK, c2 / PACK)
n_corrupt = 0; n_attr_corrupt = 0
for d in OUTCOME_DIRS:
    for f in (REPO / d).rglob("*"):
        if f.is_file():
            g = c2 / f.relative_to(REPO); g.parent.mkdir(parents=True, exist_ok=True); g.write_bytes(b"CORRUPTED" * 7); n_corrupt += 1
            n_attr_corrupt += f.name.startswith("attrib")
b2 = run(c2, tmp / "out2")
c3 = tmp / "isolated"; c3.mkdir()
for p in CODE: (c3 / p).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(REPO / p, c3 / p)
shutil.copytree(REPO / PACK, c3 / PACK)
present = sorted(str(p.relative_to(c3)) for p in c3.rglob("*") if p.is_file() and not str(p).startswith(str(c3 / PACK)))
b3 = run(c3, tmp / "out3", isolate=True)
same = (b1 == b2 == b3) and int(n_attr_corrupt) == len(_attr)
(out / "thresholds.json").write_bytes(b1)
res = {"RD4_PASS": same, "sha256": [hashlib.sha256(b).hexdigest() for b in (b1, b2, b3)], "outcome_files_corrupted_in_run2": n_corrupt, "attribution_files_found": len(_attr), "attribution_files_corrupted_in_run2": int(n_attr_corrupt),
       "isolated_run3_files_besides_pack": present, "isolated_run3_network": "disabled (unshare -rn)"}
(out / "rd4_result.json").write_text(json.dumps(res, indent=1))
shutil.rmtree(tmp)
print(json.dumps({"RD4_PASS": same, "thresholds_sha256": res["sha256"][0]}))
