"""Weekly labor evaluation: parse tracker extracts, pick the most recent
Sunday whose week is complete for every store, evaluate the 4 weeks
ending then, and write the dashboard CSVs.

usage: run_weekly.py <extracts dir with legacy/ and v2/> <out dir> [--end YYYY-MM-DD]
"""
import csv
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent


def latest_complete_sunday(v2_csv, stores, today):
    valid = {}
    for r in csv.DictReader(open(v2_csv)):
        ok = r["parsed"] == "True" and float(r["act_sales"] or 0) > 0 and float(r["act_hrs"] or 0) > 0
        valid[(r["store"], r["date"])] = ok
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    for _ in range(8):
        week = [sunday - timedelta(days=i) for i in range(7)]
        if all(valid.get((s, d.isoformat())) for s in stores for d in week):
            return sunday
        sunday -= timedelta(days=7)
    raise SystemExit("no complete week in the last 8")


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    end = date.fromisoformat(sys.argv[sys.argv.index("--end") + 1]) if "--end" in sys.argv else None
    today = date.today()
    start = (end or today) - timedelta(days=7 * 8 + 6)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    for script, sub, name in (("parse_tracker_text.py", "legacy", "daily_legacy.csv"), ("parse_v2_text.py", "v2", "daily_v2.csv")):
        subprocess.run([py, HERE / script, src / sub, work / name, start.isoformat(), (end or today).isoformat()], check=True)
    stores = sorted(p.stem for p in (src / "v2").glob("*.txt"))
    if end is None:
        end = latest_complete_sunday(work / "daily_v2.csv", stores, today)
    print("window ends", end)
    sales = src / "weekly_sales.json"  # Weekly Sales report's Toast cache, if fetched
    args = [py, HERE / "labor_eval.py", work / "daily_v2.csv", work / "daily_legacy.csv", end.isoformat(), work / "eval.json"]
    subprocess.run(args + ([sales] if sales.exists() else []), check=True)
    subprocess.run([py, HERE / "export_dashboard.py", work / "eval.json", out], check=True)
    res = json.load(open(work / "eval.json"))
    return res


if __name__ == "__main__":
    main()
