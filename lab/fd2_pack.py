"""Build dev_pack_v2 for FD-2: it EXTENDS dev_pack_v1 (hourly + universe, unchanged, referenced by its manifest sha256)
with the U9b forced-exit rows whose official cut is inside Development (cut < 2025-09-01 00:00 UTC).

python3 -I lab/fd2_pack.py

Source: out/research_protocol/v1.2/forced_exit_reference.csv (Protocol v1.2 input, byte-identical to v1.1).
Rows with cut >= 2025-09-01 are not copied (only the cut field is compared).
"""
import sys, csv, json, hashlib, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lab.segment_loader import SEGMENTS

LAB = pathlib.Path(__file__).resolve().parents[1]
SRC = LAB / "out/research_protocol/v1.2/forced_exit_reference.csv"
V1 = LAB / "out/market_intelligence/dev_pack_v1"
V2 = LAB / "out/market_intelligence/dev_pack_v2"
DEV_END = SEGMENTS["development"][1].strftime("%Y-%m-%d %H:%M")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    V2.mkdir(parents=True, exist_ok=True)
    with open(SRC, newline="") as fh:
        r = csv.reader(fh); header = next(r); ci = header.index("cut_utc")
        keep, skipped = [], 0
        for row in r:
            if row[ci] >= DEV_END:                      # "YYYY-MM-DD HH:MM" compares correctly as text
                skipped += 1; continue
            keep.append(row)
    out = V2 / "forced_exit_dev.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(header); w.writerows(keep)
    man = {"purpose": "FD-2 Development inputs = dev_pack_v1 + forced exits with cut inside Development",
           "extends": {"dev_pack_v1/PACK_MANIFEST.json": sha(V1 / "PACK_MANIFEST.json")},
           "files": {"forced_exit_dev.csv": {"sha256": sha(out), "rows": len(keep),
                                             "rows_with_cut_after_development_not_copied": skipped,
                                             "source": "out/research_protocol/v1.2/forced_exit_reference.csv",
                                             "source_sha256": sha(SRC)}}}
    (V2 / "PACK_MANIFEST.json").write_text(json.dumps(man, indent=1))
    print(json.dumps(man["files"]))


if __name__ == "__main__":
    main()
