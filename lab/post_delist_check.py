"""Offline: minutes with trades AT/AFTER the ledger's effective delisting time, per pair (from the raw release files).

python3 -I lab/post_delist_check.py <raw_dir> <pair_quality.csv> <out_csv>
Only the file(s) covering the delisting time are read. Nothing is changed in the dataset.
"""
import sys, csv, io, zipfile, pathlib, datetime as dt
from decimal import Decimal as Dm

M = 60000


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def main(raw_dir, quality, out_csv):
    Q = list(csv.DictReader(open(quality)))
    res = []
    for q in Q:
        p = q["pair"]
        eff = int(dt.datetime.strptime(q["effective_delisting_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        traded_after, all_after, last_any = [], 0, None
        for fz in sorted((pathlib.Path(raw_dir) / p).glob("*.zip")):
            z = zipfile.ZipFile(fz)
            for r in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))):
                t = int(r["open_time"])
                if t >= eff:
                    all_after += 1
                    last_any = max(last_any or t, t)
                    if Dm(r["vol"]) > 0:
                        traded_after.append((t, r["vol"], r["close"]))
        traded_after.sort()
        res.append({"pair": p, "effective_delisting_utc": q["effective_delisting_utc"], "minutes_after_in_files": all_after,
                    "last_minute_in_files_utc": iso(last_any) if last_any else "",
                    "traded_minutes_after": len(traded_after),
                    "first_traded_after_utc": iso(traded_after[0][0]) if traded_after else "",
                    "last_traded_after_utc": iso(traded_after[-1][0]) if traded_after else "",
                    "last_traded_after_minutes_past_effective": round((traded_after[-1][0] - eff) / M) if traded_after else "",
                    "base_volume_after": str(sum(Dm(x[1]) for x in traded_after)) if traded_after else "0"})
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
    return res


if __name__ == "__main__":
    main(*sys.argv[1:4])
