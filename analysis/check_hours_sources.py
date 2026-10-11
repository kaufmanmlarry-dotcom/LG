"""Check tracker hours against the true sources.

Actual hours: Toast time entries (corrected pull, one CSV per business date).
Scheduled hours: WhenToWork shift exports (final weekly snapshots).

usage: check_hours_sources.py <toast dir> <w2w dir> <daily_v2.csv> <daily_legacy.csv> <out.csv>
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


def f(x):
    try:
        return float(str(x).strip())
    except ValueError:
        return 0.0


def load_toast(d):
    hours, autos, emp_store = defaultdict(float), defaultdict(int), {}
    for p in sorted(Path(d).glob("*.csv")):
        date = p.stem
        for r in csv.DictReader(open(p)):
            st = r["store_code"].strip().lstrip("0")
            hours[(st, date)] += f(r["payable_hours"])
            if r["auto_clockout"].strip().lower() == "yes":
                autos[(st, date)] += 1
            if r["employee_ext_id"].strip():
                emp_store.setdefault(r["employee_ext_id"].strip(), Counter())[st] += 1
    return hours, autos, emp_store


def load_w2w(d):
    return [r for p in sorted(Path(d).glob("*.csv")) for r in csv.DictReader(open(p))]


def company_map(shifts, emp_store):
    """Map each W2W company account to a store by the employees it schedules."""
    votes = defaultdict(Counter)
    for s in shifts:
        emp = s["employee_number"].strip()
        if emp in emp_store:
            votes[s["company_id"]][emp_store[emp].most_common(1)[0][0]] += 1
    return {c: v.most_common(1)[0][0] for c, v in votes.items()}


def main():
    toast_dir, w2w_dir, v2_path, lg_path, out = sys.argv[1:6]
    t_hours, t_auto, emp_store = load_toast(toast_dir)
    shifts = load_w2w(w2w_dir)
    cmap = company_map(shifts, emp_store)
    sched = defaultdict(float)
    shared = defaultdict(list)
    by_emp_day = defaultdict(list)
    for s in shifts:
        st = cmap.get(s["company_id"], "?")
        sched[(st, s["date"])] += f(s["duration"])
        name = s["employee_name"].strip()
        if name.lower() == "shared labor":
            shared[(st, s["date"])].append(f"{s['shift_description']} {s['start_time']}-{s['end_time']}")
        elif s["employee_number"].strip():
            by_emp_day[(s["employee_number"].strip(), s["date"])].append((st, s))
    double = defaultdict(float)
    for (emp, date), rows in by_emp_day.items():
        stores = {st for st, _ in rows}
        if len(stores) > 1:
            for st, s in rows:
                double[(st, date)] += f(s["duration"])
    v2 = {(r["store"], r["date"]): r for r in csv.DictReader(open(v2_path))}
    lg = {(r["store"], r["date"]): r for r in csv.DictReader(open(lg_path))}
    keys = sorted(k for k in t_hours if k in v2)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["store", "date", "toast_hrs", "v2_act", "legacy_act", "toast_auto_left", "w2w_sched",
                    "v2_wtw", "legacy_wtw", "shared_labor", "cross_store_hrs"])
        for k in keys:
            w.writerow([k[0], k[1], round(t_hours[k], 2), v2[k]["act_hrs"], lg.get(k, {}).get("act_hrs", ""),
                        t_auto.get(k, 0), round(sched.get(k, 0), 2), v2[k]["wtw"], lg.get(k, {}).get("wtw", ""),
                        "; ".join(shared.get(k, [])), round(double.get(k, 0), 2)])
    print("company map:", dict(sorted(cmap.items(), key=lambda x: x[1])))
    print("rows:", len(keys))


if __name__ == "__main__":
    main()
