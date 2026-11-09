"""Build val_pack_v1 (Validation Plan v0.1.1 §1). Same slicing discipline as lab/mi_dev_pack.py, end = Validation end.

python3 -I lab/val_pack.py

hourly    read line by line; rows before 2024-01-01 skipped; STOP at the first candle that does not close by 2026-04-01 00:00
          (only its timestamp field is compared). Development + embargo history is kept as LOOKBACK only (H5).
universe  only the `day` field is compared; lines with day >= 2026-04-01 are skipped unparsed.
forced    rows of forced_exit_reference.csv with cut < 2026-04-01 00:00 (only the cut field is compared).
Stop condition 1 (plan §0.1): the delisting ledger must reach >= 2026-04-01 and every forced exit with a cut inside
[2025-09-01, 2026-04-01) must be PRICED with a gap <= 60 min; otherwise the build raises and writes nothing further.
"""
import sys, csv, gzip, io, json, hashlib, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SEGMENTS, RESEARCH_START

LAB = pathlib.Path(__file__).resolve().parents[1]
VAL_END = SEGMENTS["validation"][1]
END_MS = int(VAL_END.timestamp() * 1000)
START_MS = int(RESEARCH_START.timestamp() * 1000)
END_DAY = VAL_END.strftime("%Y-%m-%d")
END_TXT = VAL_END.strftime("%Y-%m-%d %H:%M")
SRC = {"active": LAB / "out/active_dataset/final_42445808350_retry_42448392394/hourly",
       "delisted": LAB / "out/delisted_dataset/20261107T192715Z_rebuild/hourly",
       "delisted_jan2024": LAB / "out/delisted_dataset/20261108T041031Z_jan2024_addendum/hourly"}
UNIV = LAB / "out/research_protocol/v1.2/universe"
FE = LAB / "out/research_protocol/v1.2/forced_exit_reference.csv"
LEDGERS = [LAB / f"out/ledger/{r}/delisting_ledger.csv" for r in ("ar", "en-eu", "ar_pre2024")]
SCEN = {"P1": "eligibility_daily_P1.csv.gz", "S50k": "eligibility_daily_S50k.csv.gz", "S250k": "eligibility_daily_S250k.csv.gz"}
PACK = LAB / "out/validation/val_pack_v1"


class StopCondition(Exception):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def stop_condition_1():
    latest = ""
    for f in LEDGERS:
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                if r["effective_delisting_utc"] and r["effective_delisting_utc"] > latest:
                    latest = r["effective_delisting_utc"]
    if latest < END_TXT:
        raise StopCondition(f"delisting ledger ends {latest} < {END_TXT}")
    bad, n = [], 0
    with open(FE, newline="") as fh:
        for r in csv.DictReader(fh):
            if "2025-09-01 00:00" <= r["cut_utc"] < END_TXT:
                n += 1
                if r["status"] != "PRICED" or int(r["minutes_last_trade_to_cut"]) > 60:
                    bad.append(r["series"])
    if bad:
        raise StopCondition(f"unpriceable forced exits inside Validation: {bad}")
    return {"ledger_latest_effective_utc": latest, "forced_exits_in_validation_window": n, "all_priced_gap_le_60": True}


def main(pack=PACK):
    sc1 = stop_condition_1()
    pack = pathlib.Path(pack); (pack / "hourly").mkdir(parents=True, exist_ok=True); (pack / "universe").mkdir(exist_ok=True)
    man = {"purpose": "Validation inputs (Plan v0.1.1): lookback from 2024-01-01, nothing closing after 2026-04-01",
           "end": str(VAL_END), "stop_condition_1": sc1, "files": {}}
    groups = {}
    for name, f in SCEN.items():
        out, kept, skipped = io.StringIO(), 0, 0
        with gzip.open(UNIV / f, "rt") as fh:
            header = fh.readline(); out.write(header)
            di = header.strip().split(",").index("day")
            for line in fh:
                if line.split(",", di + 1)[di] >= END_DAY:
                    skipped += 1; continue
                out.write(line); kept += 1
                if name == "P1":
                    g = line.split(",", 2); groups[g[0]] = g[1]
        b = gzip.compress(out.getvalue().encode(), mtime=0)
        (pack / "universe" / f).write_bytes(b)
        man["files"][f"universe/{f}"] = {"sha256": sha(b), "rows": kept, "lines_on_or_after_end_skipped_unparsed": skipped,
                                         "source_sha256": sha((UNIV / f).read_bytes())}
    for s, g in sorted(groups.items()):
        src = SRC[g] / f"{s.split('#')[0]}.csv.gz"
        out, kept, first, last, stopped = io.StringIO(), 0, None, None, False
        with gzip.open(src, "rt") as fh:
            out.write(fh.readline())
            for line in fh:
                ts = int(line.split(",", 1)[0])
                if ts + 3600000 > END_MS:
                    stopped = True; break
                if ts < START_MS:
                    continue
                out.write(line); kept += 1
                first = ts if first is None else first; last = ts
        b = gzip.compress(out.getvalue().encode(), mtime=0)
        (pack / "hourly" / f"{s}.csv.gz").write_bytes(b)
        fmt = lambda x: dt.datetime.fromtimestamp(x / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if x is not None else ""
        man["files"][f"hourly/{s}.csv.gz"] = {"group": g, "sha256": sha(b), "rows": kept, "first_candle_utc": fmt(first),
                                              "last_candle_utc": fmt(last), "stopped_at_validation_end": stopped,
                                              "source_sha256": sha(src.read_bytes())}
    (pack / "groups.csv").write_text("series,group\n" + "".join(f"{s},{g}\n" for s, g in sorted(groups.items())))
    man["files"]["groups.csv"] = {"sha256": sha((pack / "groups.csv").read_bytes()), "rows": len(groups)}
    with open(FE, newline="") as fh:
        r = csv.reader(fh); header = next(r); ci = header.index("cut_utc")
        rows = [x for x in r if x[ci] < END_TXT]
    with open(pack / "forced_exit_val.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(header); w.writerows(rows)
    man["files"]["forced_exit_val.csv"] = {"sha256": sha((pack / "forced_exit_val.csv").read_bytes()), "rows": len(rows),
                                           "source_sha256": sha(FE.read_bytes())}
    lasts = [v["last_candle_utc"] for k, v in man["files"].items() if k.startswith("hourly/") and v.get("last_candle_utc")]
    man["max_candle_start_in_pack"] = max(lasts) if lasts else ""
    (pack / "PACK_MANIFEST.json").write_text(json.dumps(man, indent=1))
    print(json.dumps({"series": len(groups), "max_candle_start_in_pack": man["max_candle_start_in_pack"], "stop_condition_1": sc1}))


if __name__ == "__main__":
    main()
