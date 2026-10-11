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
            "mgr_fcst": f(lg.get("mgr_fcst")) if lg_ok else 0.0,
        }
        d["valid"] = d["sales"] > 0 and d["act"] > 0
        d["service"] = d["act"] - d["excl"]
        days.append(d)
    return days


def summarize(rows, weeks):
    s = defaultdict(float)
    for d in rows:
        for k in ("open_hrs", "sales", "act", "earned", "earned_floor", "wtw", "ot", "excl", "service"):
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
    fc = [d for d in rows if d["mgr_fcst"] > 0 and d["lg_sales"] > 0]
    s["fcst_days"] = len(fc)
    s["fcst_bias"] = (sum(d["mgr_fcst"] for d in fc) / sum(d["lg_sales"] for d in fc) - 1) if fc else 0
    s["fcst_mape"] = statistics.mean(abs(d["mgr_fcst"] / d["lg_sales"] - 1) for d in fc) if fc else 0
    return dict(s)


def evaluate(days, end, weeks=4):
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
    fleet = summarize([d for d in days if start <= d["date"] <= end and d["valid"]], weeks)
    return {"window": [start.isoformat(), end.isoformat()], "prior": [p_start.isoformat(), p_end.isoformat()],
            "stores": out, "fleet": fleet, "flags": flags}


if __name__ == "__main__":
    v2, legacy, end, dst = sys.argv[1], sys.argv[2], date.fromisoformat(sys.argv[3]), sys.argv[4]
    res = evaluate(load(v2, legacy), end)
    json.dump(res, open(dst, "w"), indent=1, default=str)
    print(f"Window {res['window']}  prior {res['prior']}")
    print(f"{'#':>2} {'st':>5} {'rg':>2} {'sales':>7} {'serv':>6} {'earn':>6} {'prod':>6} {'prior':>6} {'SPLH':>6} {'pot':>6} {'ovr/wk':>6} {'$/wk':>6} {'floor':>5} {'excl':>5} {'schG':>5} {'exeG':>5} {'OT':>4} {'fBias':>6} slow/busy")
    for s in res["stores"]:
        print(f"{s['rank']:>2} {s['store']:>5} {s['region']:>2} {s['sales']:>7.0f} {s['service']:>6.1f} {s['earned']:>6.1f} {s['productivity']:>6.1%} {s['prior_productivity'] or 0:>6.1%} {s['splh']:>6.1f} {s['splh_potential']:>6.1f} {s['over_hrs_wk']:>6.1f} {s['over_cost_wk']:>6.0f} {s['floor_share']:>5.0%} {s['excl_share']:>5.1%} {s['sched_gap_wk']:>5.1f} {s['exec_gap_wk']:>5.1f} {s['ot_wk']:>4.1f} {s['fcst_bias']:>6.1%} {s['slow_productivity']:.0%}/{s['busy_productivity']:.0%}  {s['weekly_productivity']}")
    fl = res["fleet"]
    print(f"Fleet: prod {fl['productivity']:.1%} SPLH {fl['splh']:.1f} over/wk {fl['over_hrs_wk']:.1f}")
    for x in res["flags"]:
        print("FLAG", x)
