"""Parse Toast TimeEntries text extracts (one file per business date) into
CSVs with payable, regular and overtime hours per time entry.

Blank cells are dropped by the extractor, so regular and overtime hours are
read from the end of the row and checked against Payable Hours.
"""
import csv
import glob
import os
import re
import sys

DT = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2} \d{1,2}:\d{2}|\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}(:\d{2})?)$")
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-")


def num(x):
    try:
        return float(x)
    except ValueError:
        return None


def split_hours(rest, payable):
    """Regular/overtime from the tail: hourly rows end Regular, Overtime,
    Regular Pay, Overtime Pay, Total Pay; salaried rows end Regular, Overtime."""
    v = [num(x) for x in rest]
    v = [x for x in v if x is not None]
    if len(v) >= 5 and abs(v[-3] + v[-2] - v[-1]) < 0.015 and abs(v[-5] + v[-4] - payable) < 0.015:
        return v[-5], v[-4]
    if len(v) >= 2 and abs(v[-2] + v[-1] - payable) < 0.015:
        return v[-2], v[-1]
    return payable, 0.0


def parse(path):
    txt = open(path).read()
    m = re.search(r"TimeEntries_(\d{4})_(\d{2})_(\d{2})", txt)
    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    rows = []
    for line in txt.splitlines():
        t = [x.strip() for x in line.split("\t")[1:]]
        if len(t) < 10 or not re.match(r"^\d+$", t[1]):
            continue
        idx = [i for i, x in enumerate(t) if DT.match(x)]
        if len(idx) < 2:
            continue
        a, b = idx[0], idx[1]
        payable = float(t[b + 4])
        reg, ot = split_hours(t[b + 5:-1], payable)
        rows.append({"store_code": t[1].lstrip("0"), "employee_ext_id": "" if GUID.match(t[a - 6]) else t[a - 6],
                     "employee": t[a - 5], "job_title": t[a - 1], "in": t[a], "out": t[b], "total_hours": t[b + 1],
                     "payable_hours": payable, "regular_hours": reg, "overtime_hours": ot, "auto_clockout": t[-1],
                     "source_file": os.path.basename(path)})
    return date, rows


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for p in sorted(sys.argv[2:]):
        date, rows = parse(p)
        with open(os.path.join(out, f"{date}.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(date, len(rows), "entries", round(sum(r["overtime_hours"] for r in rows), 2), "OT hrs")
