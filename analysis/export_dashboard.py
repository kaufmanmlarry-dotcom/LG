"""Write the dashboard CSVs (stores, day of week, notes) from eval.json."""
import csv
import json
import sys
from pathlib import Path

INSIGHTS = {
    "99": "Best in the group and up from 95% the prior 4 weeks. At or under standard every day but Wednesday. "
          "97% of its earned hours are the 1-person minimum, so its lower SPLH is a volume limit, not a staffing one. "
          "Its schedule is the model for the other low-volume stores.",
    "246": "At standard. The only excess is Wednesday and Thursday (+0.5 and +0.8 hrs a day). Trim a mid-shift on those days.",
    "516": "Down from 103% the prior 4 weeks. Tuesday runs 1.1 hrs a day over. Admin and training are 7.9% of hours, above the 7.0% group average. Check the Tuesday schedule.",
    "1359": "Down from 102%. Admin and training are 11.8% of hours, the highest in the group: confirm those hours are real. "
            "Saturday runs 1.9 hrs a day over. Its SPLH is the lowest because 97% of earned hours are the 1-person minimum.",
    "98": "Down from 101%. The extra hours are on the weekend: Friday +0.9, Saturday +1.6, Sunday +0.6 hrs a day.",
    "680": "Flat versus the prior 4 weeks. Excess builds Thursday through Sunday (+0.6 to +1.0 hrs a day) on its busier days.",
    "532": "Up from 94%. Thursday (+1.9), Saturday (+3.3) and Sunday (+2.5 hrs a day) run over while Wednesday runs 2.0 under. "
           "Managers over-forecast sales by 13%, which builds a heavy schedule. Fix the weekend forecast first.",
    "101": "Down from 97%, and the last three weeks averaged about 91%. Slow days are the problem: Monday to Wednesday run +1.8 to +2.6 hrs a day over, "
           "and slow days score 87% against 99% on busy days. Admin and training are 11.1% of hours. Cut the weekday mid-shift when sales run under the median.",
    "491": "Flat. Busy days are the problem here (88% against 98% on slow days). Saturday +3.3, Sunday +2.5, Friday and Tuesday +1.4 hrs a day over: "
           "peak shifts carry more people than the item counts need.",
    "1360": "Flat at about 91%. The posted schedule is close to standard, but the store worked about 23 hrs a week more than it scheduled: shifts are running long "
            "or people are clocking in unscheduled. Wednesday (+3.0), Friday (+2.4) and Tuesday (+1.7 hrs a day) are worst. Managers under-forecast sales by 17%.",
    "256": "The same 89–91% every week. Over standard every day but Monday, worst Wednesday to Saturday (+1.5 to +2.9 hrs a day), on slow and busy days alike. "
           "That consistency points to a base schedule that is too rich, not a one-off.",
    "530": "Last in both periods: about 25 hrs a week over standard, roughly $620 a week. Over every day, worst Tuesday (+6.1 hrs a day) and on slow days (81%). "
           "Its SPLH is the highest in the group, which hides the gap: staffed to standard it would be about $138. It also worked about 15 hrs a week past its posted schedule.",
}

NOTES = [
    ("Sources", "Sales, actual hours and earned hours come from the v2 trackers (the system of record). Go-Go, admin and training hours come from the legacy .xlsm trackers, the only place they are recorded."),
    ("Sales", "v2 sales run 3–5% below the legacy trackers and the Labor Hours Variance Report at every store. SPLH here uses v2 sales, so it reads a little lower than the variance report."),
    ("Store 530", "Overwritten Go-Go cells remain in the legacy tracker on Aug 13–16, Sep 21–27, Oct 1 and Oct 4. They don't change this page: earned hours come from v2 and only the visible Go-Go, admin and training cells are used."),
    ("Store 516, Sep 28", "The legacy tracker never got actuals for this day. v2 sales and hours are used."),
    ("Schedules", "v2 and legacy disagree on scheduled (WTW) hours on 79 of 336 store-days, so schedule comparisons are quoted only for 530 and 1360, where both trackers agree."),
    ("Overtime", "The v2 overtime column is empty for the period, so overtime isn't shown."),
]

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
                        res["window"][0], res["window"][1], INSIGHTS[s["store"]]])
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
        w.writerows(NOTES)
    print("wrote", sorted(p.name for p in out.iterdir()))
