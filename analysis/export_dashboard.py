"""Write the dashboard CSVs (stores, day of week, notes) from eval.json."""
import csv
import json
import sys
from pathlib import Path

DAY_NAME = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday",
            "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday"}


def pct(v):
    return f"{v * 100:.0f}%"


def insight(s, fleet):
    """Plain-language notes for one store, from its numbers only."""
    out = []
    p, prior = s["productivity"], s["prior_productivity"]
    if prior:
        d = p - prior
        if abs(d) < 0.015:
            out.append(f"Flat against the prior 4 weeks ({pct(prior)}).")
        else:
            out.append(f"{'Up' if d > 0 else 'Down'} from {pct(prior)} the prior 4 weeks.")
    if s["over_hrs_wk"] >= 10:
        out.append(f"About {s['over_hrs_wk']:.0f} hrs a week over standard, roughly ${s['over_cost_wk']:,.0f} a week.")
    elif p >= 1.0:
        out.append("At or better than standard.")
    worst = sorted(((v["over_hrs_per_day"], k) for k, v in s["dow"].items()), reverse=True)
    worst = [(v, k) for v, k in worst if v >= 1.0][:3]
    if worst:
        out.append("Most excess: " + ", ".join(f"{DAY_NAME[k]} +{v:.1f}" for v, k in worst) + " hrs a day.")
    elif p < 1.0:
        mild = [(v, k) for v, k in sorted(((v["over_hrs_per_day"], k) for k, v in s["dow"].items()), reverse=True) if v >= 0.5][:2]
        if mild:
            out.append("Small excess on " + " and ".join(f"{DAY_NAME[k]} (+{v:.1f})" for v, k in mild) + ", in hrs a day.")
    gap = s["slow_productivity"] - s["busy_productivity"]
    if gap <= -0.05:
        out.append(f"Slow days are the problem: {pct(s['slow_productivity'])} against {pct(s['busy_productivity'])} on busy days.")
    elif gap >= 0.05:
        out.append(f"Busy days are the problem: {pct(s['busy_productivity'])} against {pct(s['slow_productivity'])} on slow days.")
    if s["excl_share"] >= fleet["excl_share"] + 0.03:
        out.append(f"Admin, training and Go-Go are {s['excl_share'] * 100:.1f}% of hours against {fleet['excl_share'] * 100:.1f}% for the group: confirm those hours are real.")
    if s["sched_agree"] and s["exec_gap_wk"] >= 8:
        out.append(f"Worked about {s['exec_gap_wk']:.0f} hrs a week more than the posted schedule: shifts running long or unscheduled clock-ins.")
    if abs(s["fcst_bias"]) >= 0.10:
        out.append(f"Managers {'over' if s['fcst_bias'] > 0 else 'under'}-forecast sales by {abs(s['fcst_bias']) * 100:.0f}%.")
    if s["floor_share"] >= 0.95:
        out.append(f"{pct(s['floor_share'])} of its earned hours are the 1-person minimum, so its SPLH is limited by volume, not staffing.")
    if s["splh_potential"] - s["splh"] >= 10:
        out.append(f"Staffed to standard its SPLH would be ${s['splh_potential']:.0f} instead of ${s['splh']:.0f}.")
    return " ".join(out)


SOURCES_NOTE = ("Sources", "Sales, actual hours and earned hours come from the v2 trackers (the system of record). "
                "Go-Go, admin and training hours come from the legacy .xlsm trackers, the only place they are recorded.")


DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

if __name__ == "__main__":
    res = json.load(open(sys.argv[1]))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cols = ["rank", "store", "region", "productivity", "prior_productivity", "change", "splh", "splh_potential",
            "over_hrs_wk", "over_cost_wk", "floor_share", "excl_share", "slow_productivity", "busy_productivity",
            "fcst_bias", "w1", "w2", "w3", "w4", "sales", "service", "earned", "prior_earned", "prior_service",
            "window_start", "window_end", "insight"]
    with open(out / "store_scorecard.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for s in res["stores"]:
            wk = s["weekly_productivity"]
            w.writerow([s["rank"], s["store"], s["region"], round(s["productivity"], 4), round(s["prior_productivity"], 4),
                        round(s["productivity"] - s["prior_productivity"], 4), round(s["splh"], 2), round(s["splh_potential"], 2),
                        round(s["over_hrs_wk"], 1), round(s["over_cost_wk"]), round(s["floor_share"], 3), round(s["excl_share"], 3),
                        round(s["slow_productivity"], 3), round(s["busy_productivity"], 3), round(s["fcst_bias"], 3),
                        *wk, round(s["sales"]), round(s["service"], 2), round(s["earned"], 2),
                        round(s["prior_earned"], 2), round(s["prior_service"], 2),
                        res["window"][0], res["window"][1], insight(s, res["fleet"])])
    with open(out / "store_by_weekday.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["store", "weekday", "extra_hrs_per_day", "productivity", "avg_sales"])
        for s in res["stores"]:
            for d in DOW:
                v = s["dow"][d]
                w.writerow([s["store"], d, round(v["over_hrs_per_day"], 2), round(v["productivity"], 3), round(v["avg_sales"])])
    with open(out / "data_notes.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["topic", "note"])
        w.writerow(SOURCES_NOTE)
        w.writerows(res.get("checks", []))
        w.writerows(("Missing day", f) for f in res.get("flags", []))
    print("wrote", sorted(p.name for p in out.iterdir()))
