"""Parse daily rows from Dropbox text extracts of the v2 trackers
(Store N Labor and Sales Forecasting 2026 v2.xlsx, the system of record).

Blank cells are dropped by the extractor, so the Earned block is found by
arithmetic: Z = V + W + X + Y and AB = Z - AA. Sales are the last two $
cells (Actual, Mgr Var) checked against the forecast cells.
"""
import csv
import sys
from datetime import date, datetime
from pathlib import Path

from parse_tracker_text import DAYS, close, is_num, num


def parse_row(toks):
    dollars = [i for i, t in enumerate(toks) if "$" in t]
    if len(dollars) < 2:
        return None
    last = dollars[-1]
    vals = [num(toks[i]) for i in dollars]
    act, var = vals[-2], vals[-1]
    mgr = act - var
    stream = []
    for t in toks[last + 1:]:
        if not is_num(t):
            break
        stream.append(num(t))
    for i in range(6, min(len(stream) - 2, 12)):
        v, w, x, y, z = stream[i - 4:i + 1]
        aa, ab = stream[i + 1], stream[i + 2]
        if close(v + w + x + y, z) and close(z - aa, ab):
            return {
                "act_sales": act, "mgr_fcst": mgr if not close(var, act) else "",
                "rec_total": stream[i - 7], "wtw": stream[i - 6],
                "earned_sales": v, "earned_oc": w, "earned_admin": x, "earned_train": y,
                "earned_total": z, "act_hrs": aa, "hrs_var": ab,
                "ot": stream[i + 3] if i + 3 < len(stream) else 0.0,
            }
    return None


def parse_file(path, store, start, end):
    rows = []
    for line in Path(path).read_text().splitlines():
        toks = line.split("\t")[1:]
        if len(toks) < 5 or toks[0] not in DAYS:
            continue
        try:
            d = datetime.strptime(toks[1], "%m/%d/%y").date()
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        r = {"store": store, "date": d.isoformat(), "dow": toks[0], "store_hrs": num(toks[2])}
        p = parse_row(toks)
        r["parsed"] = bool(p)
        if p:
            r.update(p)
        rows.append(r)
    return rows


KEYS = ["store", "date", "dow", "store_hrs", "parsed", "act_sales", "mgr_fcst", "rec_total", "wtw",
        "earned_sales", "earned_oc", "earned_admin", "earned_train", "earned_total", "act_hrs", "hrs_var", "ot"]

if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    start, end = date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])
    rows = []
    for f in sorted(src.glob("*.txt")):
        rows += parse_file(f, f.stem, start, end)
    seen, uniq = set(), []
    for r in rows:
        k = (r["store"], r["date"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    with dst.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=KEYS)
        w.writeheader()
        for r in uniq:
            w.writerow({k: r.get(k, "") for k in KEYS})
    bad = [r for r in uniq if not r["parsed"]]
    print(f"{len(uniq)} rows, {len(bad)} unparsed")
    for r in bad:
        print("UNPARSED", r["store"], r["date"])
