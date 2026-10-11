"""Rolling 4-week labor evaluation across stores.

Inputs (from the parsers in this folder):
  daily_v2.csv     v2 trackers (system of record): sales, actual hours,
                   earned hours (V sales + W O/C), WTW schedule, OT.
  daily_legacy.csv legacy .xlsm trackers: GM-entered Go-Go/Admin/Training
                   hours (v2 does not carry admin yet) and manager forecast.

Core measures per store over the window:
  service hours  = actual hours - (Go-Go + Admin + Training)
  earned hours   = Sales Factor staff-per-hour for actual prep items
                   (1-person floor every open hour) + opener/closer
  productivity   = earned / service   (100% = staffed exactly to standard)
  SPLH           = sales / service hours
  SPLH potential = sales / earned hours (best SPLH at the store's volume)
"""
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta

REGION = {"530": "SD", "532": "SD", "1360": "SD"}
WAGE = {"CO": 22.0, "SD": 25.0}  # all-in $/hr, as in afternoon_overstaffing.py


def f(x):
    return float(x) if x not in ("", None) else 0.0


WEEK1 = date(2025, 12, 29)  # fiscal week 1 of 2026 in the Weekly Sales report


def load_weekly_sales(path):
    """Toast weekly net sales by (store, week start) from the Weekly Sales
    report's cache (_gross_cache_2026.json: {store: {week: {g, n, t}}})."""
    if not path:
        return {}
    raw = json.load(open(path))
    return {(st, WEEK1 + timedelta(days=7 * (int(wk) - 1))): v["n"] for st, weeks in raw.items() for wk, v in weeks.items()}


def load_toast(d):
    """Toast time entries (parse_toast_time.py output): per store-day payable
    and overtime hours, and overtime hours by role."""
    if not d:
        return {}
    from pathlib import Path
    out = defaultdict(lambda: {"payable": 0.0, "ot": 0.0, "ot_roles": defaultdict(float)})
    for p in Path(d).glob("*.csv"):
        for r in csv.DictReader(open(p)):
            k = (r["store_code"], p.stem)
            out[k]["payable"] += f(r["payable_hours"])
            ot = f(r["overtime_hours"])
            out[k]["ot"] += ot
            if ot:
                out[k]["ot_roles"][r["job_title"].replace(" - Fran", "")] += ot
    return out


def load(v2_path, legacy_path):
    legacy = {(r["store"], r["date"]): r for r in csv.DictReader(open(legacy_path))}
    days = []
    for r in csv.DictReader(open(v2_path)):
        if r["parsed"] != "True":
            continue
        lg = legacy.get((r["store"], r["date"]), {})
        lg_ok = lg.get("parsed") == "True"
        d = {
            "store": r["store"], "date": date.fromisoformat(r["date"]), "dow": r["dow"],
            "region": REGION.get(r["store"], "CO"),
            "open_hrs": f(r["store_hrs"]), "sales": f(r["act_sales"]), "act": f(r["act_hrs"]),
            "earned": f(r["earned_sales"]) + f(r["earned_oc"]), "earned_floor": f(r["store_hrs"]) + f(r["earned_oc"]),
            "wtw": f(r["wtw"]), "ot": f(r["ot"]),
            # admin and training are only recorded in the legacy trackers
            "excl": f(lg.get("visible_excl")) if lg_ok else 0.0,
            "excl_missing": not lg_ok,
            "lg_sales": f(lg.get("act_sales")) if lg_ok else 0.0,
            "wtw_legacy": f(lg.get("wtw")) if lg_ok else 0.0,
            "hidden_excl": f(lg.get("ideal_excl")) - f(lg.get("visible_excl")) if lg_ok else 0.0,
            "mgr_fcst": f(lg.get("mgr_fcst")) if lg_ok else 0.0,
        }
        d["valid"] = d["sales"] > 0 and d["act"] > 0
        d["service"] = d["act"] - d["excl"]
        days.append(d)
    return days


def summarize(rows, weeks):
    s = defaultdict(float)
    for d in rows:
        for k in ("open_hrs", "sales", "act", "earned", "earned_floor", "wtw", "wtw_legacy", "ot", "excl", "service"):
            s[k] += d[k]
    s["days"] = len(rows)
    s["productivity"] = s["earned"] / s["service"] if s["service"] else 0
    s["splh"] = s["sales"] / s["service"] if s["service"] else 0
    s["splh_potential"] = s["sales"] / s["earned"] if s["earned"] else 0
    s["over_hrs_wk"] = (s["service"] - s["earned"]) / weeks
    s["floor_share"] = s["earned_floor"] / s["earned"] if s["earned"] else 0
    s["excl_share"] = s["excl"] / s["act"] if s["act"] else 0
    # schedule vs standard (WTW includes admin/training) and execution vs schedule
    s["sched_gap_wk"] = (s["wtw"] - s["earned"] - s["excl"]) / weeks
    s["exec_gap_wk"] = (s["act"] - s["wtw"]) / weeks
    s["ot_wk"] = s["ot"] / weeks
    # schedule figures are trusted only where v2 and legacy WTW agree
    s["sched_agree"] = bool(s["wtw_legacy"]) and abs(s["wtw"] / s["wtw_legacy"] - 1) <= 0.03
    fc = [d for d in rows if d["mgr_fcst"] > 0 and d["lg_sales"] > 0]
    s["fcst_days"] = len(fc)
    s["fcst_bias"] = (sum(d["mgr_fcst"] for d in fc) / sum(d["lg_sales"] for d in fc) - 1) if fc else 0
    s["fcst_mape"] = statistics.mean(abs(d["mgr_fcst"] / d["lg_sales"] - 1) for d in fc) if fc else 0
    return dict(s)


def apply_toast_sales(s, st, start, weeks, toast):
    """Use Toast net sales for the window when every week is available;
    v2 daily sales stay in use for the slow/busy split and weekday averages."""
    s["v2_sales"] = s["sales"]
    vals = [toast.get((st, start + timedelta(days=7 * i))) for i in range(weeks)]
    if toast and all(v is not None for v in vals):
        s["sales"] = sum(vals)
        s["sales_source"] = "toast_net"
    else:
        s["sales_source"] = "v2"
    s["splh"] = s["sales"] / s["service"] if s["service"] else 0
    s["splh_potential"] = s["sales"] / s["earned"] if s["earned"] else 0


def apply_toast_hours(s, st, cur, weeks, punches):
    """Overtime comes from Toast (v2's OT column is empty); also record how
    well v2 actual hours match Toast payable hours."""
    have = [d for d in cur if (st, d["date"].isoformat()) in punches]
    if not punches or not have:
        s["ot_source"] = "none"
        return
    roles = defaultdict(float)
    ot = match = 0.0
    for d in have:
        t = punches[(st, d["date"].isoformat())]
        ot += t["ot"]
        match += abs(t["payable"] - d["act"]) <= 0.05
        for k, v in t["ot_roles"].items():
            roles[k] += v
    s["ot"] = ot
    s["ot_wk"] = ot / weeks
    s["ot_share"] = ot / s["act"] if s["act"] else 0
    s["ot_top_role"] = max(roles, key=roles.get) if roles else ""
    s["ot_top_role_share"] = roles[s["ot_top_role"]] / ot if ot else 0
    s["toast_days"], s["toast_match_days"] = len(have), int(match)
    s["ot_source"] = "toast"


def evaluate(days, end, weeks=4, toast=None, punches=None):
    start = end - timedelta(days=7 * weeks - 1)
    p_end, p_start = start - timedelta(days=1), start - timedelta(days=7 * weeks)
    stores = sorted({d["store"] for d in days}, key=int)
    out, flags = [], []
    for st in stores:
        mine = [d for d in days if d["store"] == st]
        cur = [d for d in mine if start <= d["date"] <= end]
        bad = [d for d in cur if not d["valid"]]
        flags += [f"{st} {d['date']}: missing sales or hours, excluded" for d in bad]
        flags += [f"{st} {d['date']}: no legacy row, admin/training not excluded" for d in cur if d["excl_missing"]]
        cur = [d for d in cur if d["valid"]]
        prior = [d for d in mine if p_start <= d["date"] <= p_end and d["valid"]]
        s = summarize(cur, weeks)
        apply_toast_sales(s, st, start, weeks, toast or {})
        apply_toast_hours(s, st, cur, weeks, punches or {})
        s["store"], s["region"] = st, REGION.get(st, "CO")
        s["wage"] = WAGE[s["region"]]
        s["over_cost_wk"] = s["over_hrs_wk"] * s["wage"]
        ps = summarize(prior, weeks) if prior else {}
        s["prior_productivity"] = ps.get("productivity")
        s["prior_splh"] = ps.get("splh")
        s["prior_earned"], s["prior_service"] = ps.get("earned", 0), ps.get("service", 0)
        # weekly consistency
        wk = []
        for i in range(weeks):
            ws, we = start + timedelta(days=7 * i), start + timedelta(days=7 * i + 6)
            wk.append(round(summarize([d for d in cur if ws <= d["date"] <= we], 1)["productivity"], 3))
        s["weekly_productivity"] = wk
        # where the excess sits: day of week
        by_dow = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
        for d in cur:
            b = by_dow[d["dow"]]
            b[0] += d["service"]; b[1] += d["earned"]; b[2] += d["sales"]; b[3] += 1
        s["dow"] = {k: {"over_hrs_per_day": (v[0] - v[1]) / v[3], "productivity": v[1] / v[0] if v[0] else 0,
                        "avg_sales": v[2] / v[3]} for k, v in by_dow.items()}
        # slow vs busy days (split at the store's median daily sales)
        med = statistics.median(d["sales"] for d in cur)
        for name, grp in (("slow", [d for d in cur if d["sales"] < med]), ("busy", [d for d in cur if d["sales"] >= med])):
            g = summarize(grp, 1)
            s[f"{name}_productivity"] = g["productivity"]
            s[f"{name}_over_per_day"] = (g["service"] - g["earned"]) / len(grp) if grp else 0
        out.append(s)
    out.sort(key=lambda s: -s["productivity"])
    for i, s in enumerate(out, 1):
        s["rank"] = i
    win = [d for d in days if start <= d["date"] <= end]
    fleet = summarize([d for d in win if d["valid"]], weeks)
    fleet["sales"] = sum(s["sales"] for s in out)
    fleet["splh"] = fleet["sales"] / fleet["service"]
    fleet["splh_potential"] = fleet["sales"] / fleet["earned"]
    checks = data_checks(win)
    gaps = [(s["store"], s["v2_sales"] / s["sales"] - 1) for s in out if s["sales_source"] == "toast_net"]
    big = [f"{st} ({g * 100:+.0f}%)" for st, g in sorted(gaps, key=lambda x: x[1]) if abs(g) >= 0.03]
    missing = [s["store"] for s in out if s["sales_source"] != "toast_net"]
    if gaps:
        note = "SPLH uses Toast net sales from the Weekly Sales report. v2 daily sales are used only to split slow and busy days."
        if big:
            note += f" v2 sales differ from Toast net by 3% or more at {', '.join(big)}: v2 may be missing orders there, which would also lower those stores' earned hours."
        checks = [c for c in checks if c[0] != "Sales"] + [("Sales", note)]
    if punches:
        checks = [c for c in checks if c[0] != "Overtime"]
        tm = sum(s.get("toast_match_days", 0) for s in out)
        td = sum(s.get("toast_days", 0) for s in out)
        off = [s["store"] for s in out if s.get("toast_days") and s["toast_match_days"] < s["toast_days"] * 0.9]
        note = f"Overtime comes from Toast time entries. v2 actual hours match Toast payable hours on {tm} of {td} store-days"
        note += f"; the gaps are small and concentrated at {', '.join(off)}." if off else "."
        checks.append(("Hours", note))
    if missing:
        checks.append(("Sales", f"No Toast weekly sales for every week of the window at {', '.join(missing)}; v2 sales used there."))
    return {"window": [start.isoformat(), end.isoformat()], "prior": [p_start.isoformat(), p_end.isoformat()],
            "stores": out, "fleet": fleet, "flags": flags, "checks": checks}


def fmt_days(ds):
    return ", ".join(d.strftime("%b %-d") for d in sorted(ds))


def data_checks(win):
    """Data problems in the window, worded for the scorecard's notes."""
    checks = []
    hidden = defaultdict(list)
    for d in win:
        if d["hidden_excl"] > 0.01:
            hidden[d["store"]].append(d["date"])
    for st, ds in sorted(hidden.items(), key=lambda x: int(x[0])):
        checks.append((f"Store {st}", f"The legacy tracker's Sales Ideal total includes hours not in any visible Go-Go, admin or training cell on "
                       f"{fmt_days(ds)}, most likely overwritten Go-Go formulas. Only the visible cells are used here."))
    no_legacy = [d for d in win if d["valid"] and d["lg_sales"] == 0]
    for d in no_legacy:
        checks.append((f"Store {d['store']}, {d['date'].strftime('%b %-d')}", "The legacy tracker has no actuals for this day. v2 hours are used."))
    lg = sum(d["lg_sales"] for d in win if d["valid"] and d["lg_sales"] > 0)
    v2 = sum(d["sales"] for d in win if d["valid"] and d["lg_sales"] > 0)
    if lg and abs(v2 / lg - 1) >= 0.01:
        by_store = defaultdict(lambda: [0.0, 0.0])
        for d in win:
            if d["valid"] and d["lg_sales"] > 0:
                by_store[d["store"]][0] += d["sales"]; by_store[d["store"]][1] += d["lg_sales"]
        diffs = [v[0] / v[1] - 1 for v in by_store.values()]
        checks.append(("Sales", f"v2 sales run {abs(max(diffs)) * 100:.0f}–{abs(min(diffs)) * 100:.0f}% {'below' if v2 < lg else 'above'} the legacy trackers "
                       "and the Labor Hours Variance Report. SPLH here uses v2 sales."))
    off = [d for d in win if d["wtw_legacy"] and abs(d["wtw"] - d["wtw_legacy"]) > 1]
    if off:
        checks.append(("Schedules", f"Scheduled hours come from v2, which matches WhenToWork; the legacy trackers' WTW column is out of date on {len(off)} of {len(win)} store-days. "
                       "WhenToWork also holds offsite, borrowed and coverage shifts that are never punched at the store, so a store is only flagged for working more than its schedule, never less."))
    if not any(d["ot"] for d in win):
        checks.append(("Overtime", "The v2 overtime column is empty for the period, so overtime isn't shown."))
    return checks


if __name__ == "__main__":
    v2, legacy, end, dst = sys.argv[1], sys.argv[2], date.fromisoformat(sys.argv[3]), sys.argv[4]
    toast = load_weekly_sales(sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "-" else None)
    punches = load_toast(sys.argv[6] if len(sys.argv) > 6 else None)
    res = evaluate(load(v2, legacy), end, toast=toast, punches=punches)
    json.dump(res, open(dst, "w"), indent=1, default=str)
    print(f"Window {res['window']}  prior {res['prior']}")
    print(f"{'#':>2} {'st':>5} {'rg':>2} {'sales':>7} {'serv':>6} {'earn':>6} {'prod':>6} {'prior':>6} {'SPLH':>6} {'pot':>6} {'ovr/wk':>6} {'$/wk':>6} {'floor':>5} {'excl':>5} {'schG':>5} {'exeG':>5} {'OT':>4} {'fBias':>6} slow/busy")
    for s in res["stores"]:
        print(f"{s['rank']:>2} {s['store']:>5} {s['region']:>2} {s['sales']:>7.0f} {s['service']:>6.1f} {s['earned']:>6.1f} {s['productivity']:>6.1%} {s['prior_productivity'] or 0:>6.1%} {s['splh']:>6.1f} {s['splh_potential']:>6.1f} {s['over_hrs_wk']:>6.1f} {s['over_cost_wk']:>6.0f} {s['floor_share']:>5.0%} {s['excl_share']:>5.1%} {s['sched_gap_wk']:>5.1f} {s['exec_gap_wk']:>5.1f} {s['ot_wk']:>4.1f} {s['fcst_bias']:>6.1%} {s['slow_productivity']:.0%}/{s['busy_productivity']:.0%}  {s['weekly_productivity']}")
    fl = res["fleet"]
    print(f"Fleet: prod {fl['productivity']:.1%} SPLH {fl['splh']:.1f} over/wk {fl['over_hrs_wk']:.1f}")
    for x in res["flags"]:
        print("FLAG", x)
