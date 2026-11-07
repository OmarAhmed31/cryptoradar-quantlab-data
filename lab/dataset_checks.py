"""Offline checks on a built Delisted Assets Historical Dataset run.

python3 -I lab/dataset_checks.py <run_dir> [<previous_run_dir>]
 1. hourly/ holds exactly the pairs of dataset_index.csv; no excluded pair anywhere in hourly/
 2. every hourly row is strictly before the pair's effective delisting time
 3. no duplicate hour, hours strictly increasing, OHLC consistent, traded_minutes 1..60, vol > 0
 4. totals match pair_quality.csv and build_report.json
 5. (optional) content identical to the previous build for the same pairs (decompressed bytes)
"""
import sys, csv, gzip, json, io, pathlib, datetime as dt
from decimal import Decimal as Dm


def ms(s):
    return int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def main(run, prev=None):
    run = pathlib.Path(run)
    idx = list(csv.DictReader(open(run / "dataset_index.csv")))
    Q = {q["pair"]: q for q in csv.DictReader(open(run / "pair_quality.csv"))}
    rep = json.load(open(run / "build_report.json"))
    ex = rep.get("excluded_pairs", [])
    R = {"pairs_in_index": len(idx), "excluded": ex, "problems": []}
    files = sorted(x.name for x in (run / "hourly").glob("*"))
    if files != sorted(f"{r['pair']}.csv.gz" for r in idx):
        R["problems"].append("hourly/ does not match dataset_index")
    if any(f"{p}.csv.gz" in files for p in ex):
        R["problems"].append("excluded pair present in hourly/")
    if set(Q) != {r["pair"] for r in idx}:
        R["problems"].append("pair_quality pairs != dataset_index pairs")
    tot = after = dup = bad = 0
    same = diff = 0
    for r in idx:
        p = r["pair"]
        eff = ms(r["effective_delisting_utc"])
        rows = list(csv.reader(io.StringIO(gzip.decompress((run / "hourly" / f"{p}.csv.gz").read_bytes()).decode())))[1:]
        ts = [int(x[0]) for x in rows]
        tot += len(rows)
        after += sum(1 for t in ts if t >= eff)
        dup += len(ts) - len(set(ts))
        bad += sum(1 for a, b in zip(ts, ts[1:]) if b <= a)
        for x in rows:
            o, h, l, c, v = map(Dm, (x[3], x[4], x[5], x[6], x[7]))
            if not (l <= min(o, c) <= max(o, c) <= h) or v <= 0 or not 1 <= int(x[9]) <= 60:
                bad += 1
        if int(Q[p]["hours_with_trades"]) != len(rows):
            R["problems"].append(f"{p}: pair_quality hours != file rows")
        if prev:
            pf = pathlib.Path(prev) / "hourly" / f"{p}.csv.gz"
            if pf.exists():
                if gzip.decompress(pf.read_bytes()) == gzip.decompress((run / "hourly" / f"{p}.csv.gz").read_bytes()):
                    same += 1
                else:
                    diff += 1
    R.update(hourly_rows=tot, rows_at_or_after_delisting=after, duplicate_hours=dup, bad_rows=bad,
             report_hours_built=rep.get("hours_built"), totals_match=tot == rep.get("hours_built"))
    if prev:
        R.update(identical_to_previous_build=same, different_from_previous_build=diff)
    if after or dup or bad or not R["totals_match"]:
        R["problems"].append("row checks failed")
    R["PASS"] = not R["problems"]
    print(json.dumps(R, indent=1))
    return R


if __name__ == "__main__":
    r = main(*sys.argv[1:3])
    sys.exit(0 if r["PASS"] else 1)
