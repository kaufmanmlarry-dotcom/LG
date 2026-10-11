"""Parse daily rows from Dropbox text extracts of the store Labor and Sales
Forecasting trackers (.xlsm).

Dropbox text extraction drops blank cells, so columns are located by
arithmetic checks instead of fixed positions:
  - Actual sales: the last two $ cells before the hours block (Total, Var).
  - Hours forecast block ends Schedule, WTW, WTW Var with Var = Sched - WTW.
  - Sales Ideal block starts Sales, O/C ... and ends Total, Act Hrs, Hrs Var
    with Total = sum(block) and Var = Total - Act Hrs.
"""
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
NUM_RE = re.compile(r"^\(?-?[\d,]*\.?\d+\)?$")


def num(tok):
    t = tok.replace("$", "").replace(",", "").strip()
    if t in ("-", "- 0", ""):
        return 0.0
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    v = float(t)
    return -v if neg else v


def is_num(tok):
    t = tok.replace("$", "").replace(",", "").strip()
    return t in ("-", "- 0") or bool(NUM_RE.match(t))


def close(a, b, tol=0.02):
    return abs(a - b) <= tol


def parse_hours(stream):
    """Return dict for forecast + ideal blocks from a numeric stream.

    Some trackers hide the Go-Go cell in the Sales Ideal block (it is counted
    in Total but not visible in the extract), and a zero Hrs Var shows as a
    blank. Exact matches are tried first, then those relaxed forms.
    """
    n = len(stream)
    for relaxed in (False, True):
        for a in range(3, min(n, 12)):
            # WTW Var = Schedule - WTW
            if not close(stream[a], stream[a - 2] - stream[a - 1]):
                continue
            for k in range(a + 3, min(n - 1, a + 10)):
                ideal = stream[a + 1:k]
                total, act = stream[k], stream[k + 1]
                var = stream[k + 2] if k + 2 < n else None
                if not relaxed:
                    ok = var is not None and close(sum(ideal), total) and close(total - act, var)
                else:
                    sum_ok = total >= sum(ideal) - 0.02
                    ok = sum_ok and ((var is not None and close(total - act, var)) or close(total, act))
                if ok and len(ideal) >= 2:
                    # excluded hours never below the visible Go-Go/Admin/Training cells
                    excl = max(total - ideal[0] - ideal[1], sum(ideal[2:]))
                    return {
                        "sched": stream[a - 2], "wtw": stream[a - 1],
                        "fcst_hours_total": stream[a - 3],
                        "ideal_sales": ideal[0], "ideal_oc": ideal[1],
                        "ideal_excl": excl,
                        "visible_excl": sum(ideal[2:]),
                        "ideal_total": total, "act_hrs": act, "hrs_var": total - act,
                    }
    return None


def parse_file(path, store, year, start, end):
    out = []
    sheet = None
    for line in Path(path).read_text().splitlines():
        if line and not line.startswith("\t"):
            sheet = line.strip()
            continue
        toks = line.split("\t")[1:]
        if not toks or toks[0] not in DAYS or not sheet or not sheet.startswith("P"):
            continue
        try:
            d = datetime.strptime(f"{toks[1]}-{year}", "%d-%b-%Y").date()
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        store_hrs = num(toks[2])
        dollar_idx = [i for i, t in enumerate(toks) if "$" in t]
        if len(dollar_idx) < 2:
            continue
        vi = dollar_idx[-1]
        act_sales, sales_var = num(toks[vi - 1]) if "$" in toks[vi - 1] else num(toks[dollar_idx[-2]]), num(toks[vi])
        stream = []
        for t in toks[vi + 1:]:
            if not is_num(t):
                break
            stream.append(num(t))
        h = parse_hours(stream)
        row = {"store": store, "date": d.isoformat(), "dow": toks[0], "store_hrs": store_hrs,
               "act_sales": act_sales, "mgr_fcst": act_sales - sales_var, "parsed": bool(h)}
        if h:
            row.update(h)
        out.append(row)
    return out


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    start, end = date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])
    rows = []
    for f in sorted(src.glob("*.txt")):
        rows += parse_file(f, f.stem, start.year, start, end)
    keys = ["store", "date", "dow", "store_hrs", "act_sales", "mgr_fcst", "parsed", "fcst_hours_total",
            "sched", "wtw", "ideal_sales", "ideal_oc", "ideal_excl", "visible_excl", "ideal_total", "act_hrs", "hrs_var"]
    with dst.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    bad = [r for r in rows if not r["parsed"]]
    print(f"{len(rows)} rows, {len(bad)} unparsed")
    for r in bad:
        print("UNPARSED", r["store"], r["date"])
