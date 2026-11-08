"""Build the DEVELOPMENT-ONLY input pack for Market Intelligence (v0.11.1). The MI code reads ONLY this pack.

python3 -I lab/mi_dev_pack.py <pack_dir>

What this slicer reads from the full files, exactly (no wording beyond this):
  hourly files   rows are time-sorted; the slicer reads line by line and STOPS at the first row whose candle does not
                 close by 2025-09-01 00:00 UTC. That single boundary line is the only post-Development line read; its
                 values are not parsed into any variable (only the timestamp field is compared).
  universe files rows are sorted by series, then day, so every line is scanned; for each line ONLY the `day` field is
                 compared, and lines whose day is >= 2025-09-01 are skipped without parsing any other field.
Output: Development rows only, plus PACK_MANIFEST.json (per-file sha256, rows, first/last timestamp, lines skipped).
"""
import sys, csv, gzip, io, json, hashlib, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SEGMENTS, RESEARCH_START

LAB = pathlib.Path(__file__).resolve().parents[1]
DEV_START, DEV_END = SEGMENTS["development"][0], SEGMENTS["development"][1]
END_MS = int(DEV_END.timestamp() * 1000)
START_MS = int(RESEARCH_START.timestamp() * 1000)
SRC = {"active": LAB / "out/active_dataset/final_42445808350_retry_42448392394/hourly",
       "delisted": LAB / "out/delisted_dataset/20261107T192715Z_rebuild/hourly",
       "delisted_jan2024": LAB / "out/delisted_dataset/20261108T041031Z_jan2024_addendum/hourly"}
UNIV = LAB / "out/research_protocol/v1.2/universe"
SCEN = {"P1": "eligibility_daily_P1.csv.gz", "S50k": "eligibility_daily_S50k.csv.gz", "S250k": "eligibility_daily_S250k.csv.gz"}
DEV_END_DAY = DEV_END.strftime("%Y-%m-%d")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main(pack):
    pack = pathlib.Path(pack); (pack / "hourly").mkdir(parents=True, exist_ok=True); (pack / "universe").mkdir(exist_ok=True)
    man = {"purpose": "Development-only MI inputs", "development": [str(DEV_START), str(DEV_END)], "files": {}}
    groups = {}
    for name, f in SCEN.items():
        out, kept, skipped = io.StringIO(), 0, 0
        with gzip.open(UNIV / f, "rt") as fh:
            header = fh.readline()
            out.write(header)
            cols = header.strip().split(",")
            di = cols.index("day")
            for line in fh:
                parts = line.split(",", di + 1)              # split only as far as the day field
                if parts[di] >= DEV_END_DAY:
                    skipped += 1
                    continue
                out.write(line); kept += 1
                if name == "P1":
                    g = line.split(",", 2)
                    groups[g[0]] = g[1]
        b = gzip.compress(out.getvalue().encode(), mtime=0)
        (pack / "universe" / f).write_bytes(b)
        man["files"][f"universe/{f}"] = {"sha256": sha(b), "rows": kept, "post_development_lines_skipped_unparsed": skipped,
                                         "source_sha256": sha((UNIV / f).read_bytes())}
    for s, g in sorted(groups.items()):
        src = SRC[g] / f"{s.split('#')[0]}.csv.gz"
        out, kept, first, last, stopped = io.StringIO(), 0, None, None, False
        with gzip.open(src, "rt") as fh:
            header = fh.readline(); out.write(header)
            for line in fh:
                ts = int(line.split(",", 1)[0])
                if ts + 3600000 > END_MS:                       # first candle not closed by DEV_END: stop reading
                    stopped = True
                    break
                if ts < START_MS:
                    continue
                out.write(line); kept += 1
                first = ts if first is None else first; last = ts
        b = gzip.compress(out.getvalue().encode(), mtime=0)
        (pack / "hourly" / f"{s}.csv.gz").write_bytes(b)
        man["files"][f"hourly/{s}.csv.gz"] = {"group": g, "sha256": sha(b), "rows": kept,
                                              "first_candle_utc": dt.datetime.fromtimestamp(first / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if first else "",
                                              "last_candle_utc": dt.datetime.fromtimestamp(last / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if last else "",
                                              "stopped_at_development_end": stopped, "source_sha256": sha(src.read_bytes())}
    (pack / "groups.csv").write_text("series,group\n" + "".join(f"{s},{g}\n" for s, g in sorted(groups.items())))
    man["files"]["groups.csv"] = {"sha256": sha((pack / "groups.csv").read_bytes()), "rows": len(groups)}
    lasts = [v["last_candle_utc"] for k, v in man["files"].items() if k.startswith("hourly/") and v.get("last_candle_utc")]
    man["max_candle_start_in_pack"] = max(lasts) if lasts else ""
    (pack / "PACK_MANIFEST.json").write_text(json.dumps(man, indent=1))
    print(json.dumps({"series": len(groups), "max_candle_start_in_pack": man["max_candle_start_in_pack"],
                      "universe_rows": {k: v["rows"] for k, v in man["files"].items() if k.startswith("universe/")}}))


if __name__ == "__main__":
    main(sys.argv[1])
