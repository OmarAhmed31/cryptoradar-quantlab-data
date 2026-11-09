"""python3 -I lab/run_strategy_attrib.py <dev|val> <out_dir> <selection.json>  -> per-asset / per-class contribution (descriptive)."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab import strategy as ST, strategy_attrib as SA

mode, out = sys.argv[1], pathlib.Path(sys.argv[2]); sel = json.loads(pathlib.Path(sys.argv[3]).read_text())["selected"]
kind, N = ST.VARIANTS[sel]
ctx = None
inp = ST.dev_inputs() if mode == "dev" else None
if mode == "val":
    inp, ctx = ST.val_inputs_ctx()
try:
    meta = {}
    for cap in ST.CAPITALS:
        P, by_asset, by_class, m = SA.attribution(inp, kind, N, cap, ST.FEES["fee_0.10"], "P1")
        tag = f"{mode}_{sel}_{int(cap)}"
        P.to_csv(out / f"attrib_positions_{tag}.csv", index=False); by_asset.to_csv(out / f"attrib_by_asset_{tag}.csv", index=False)
        by_class.to_csv(out / f"attrib_by_class_{tag}.csv", index=False); meta[str(int(cap))] = m
    json.dump(meta, open(out / f"attrib_meta_{mode}.json", "w"), indent=1)
    print("attribution written (consistent with strategy.simulate to 1e-9)")
finally:
    if ctx is not None:
        ctx.__exit__(None, None, None)
