"""Weekly labor scorecard on the Whirl Labor PC (no Claude involved).

Reads the v2 + legacy trackers and Toast files directly (read-only), picks the
latest Sunday whose week is complete for all 12 stores, runs labor_eval, and
emails the scorecard to Lar only.

usage:
  run_pc.py [--end YYYY-MM-DD] [--out DIR] [--no-send] [--send-test]
Always sends an email when --send is given (the default for the scheduled task is
--send); failures are reported by email too. ASCII output only.
"""
import html
import json
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import pc_readers as R  # noqa: E402
import labor_eval  # noqa: E402
import export_dashboard as X  # noqa: E402

TO = ["kaufmanmlarry@gmail.com"]
NOTIFY_DIR = (Path.home() / "Dropbox" / "performance tracking" / "Performance Tracking GM" / "support"
              / "new implementation" / "04_drafts" / "ingestion")
DEFAULT_OUT = Path.home() / "Dropbox" / "Whirl Labor" / "Labor Scorecard"
DAY_NAME = X.DAY_NAME


def pct(v):
    return f"{v * 100:.1f}%"


def mdy(s):
    d = date.fromisoformat(s)
    return f"{d:%b} {d.day}"


def send(subject, body, attachments=()):
    sys.path.insert(0, str(NOTIFY_DIR))
    import notifications
    ok = notifications.send_email(subject, body, TO, attachments=[str(a) for a in attachments] or None)
    print("email sent" if ok else "EMAIL NOT SENT (see notifications log)")
    return ok


def build_body(res, errors):
    stores, fleet = res["stores"], res["fleet"]
    w0, w1 = res["window"]
    L = []
    L.append(f"Labor scorecard: 4 weeks {mdy(w0)} to {mdy(w1)}, 2026")
    L.append("")
    L.append(f"1. FLEET: productivity {pct(fleet['productivity'])}. "
             f"About {fleet['over_hrs_wk']:.0f} hrs a week over standard, roughly "
             f"${sum(s['over_cost_wk'] for s in stores):,.0f} a week.")
    L.append("")
    L.append("2. RANKING (productivity, change vs prior 4 weeks, hrs/wk over standard)")
    for s in stores:
        ch = (s["productivity"] - s["prior_productivity"]) * 100 if s["prior_productivity"] else 0
        L.append(f"  {s['rank']:>2}. Store {s['store']:>4}  {pct(s['productivity']):>6}  {ch:+5.1f} pts  {s['over_hrs_wk']:+6.1f} hrs/wk")
    L.append("")
    # 3. movers: rank vs prior rank, or 3+ points
    prior_rank = {}
    prior = [(s["store"], s["prior_productivity"]) for s in stores if s["prior_productivity"]]
    for i, (st, _) in enumerate(sorted(prior, key=lambda x: -x[1]), 1):
        prior_rank[st] = i
    movers = []
    for s in stores:
        pr = prior_rank.get(s["store"])
        if pr is None:
            continue
        ch = (s["productivity"] - s["prior_productivity"]) * 100
        if abs(pr - s["rank"]) >= 2 or abs(ch) >= 3:
            movers.append(f"  Store {s['store']}: rank {pr} -> {s['rank']}, {ch:+.1f} pts")
    L.append("3. MOVERS (2+ places or 3+ points)")
    L += movers or ["  None this week."]
    L.append("")
    L.append("4. TOP 3 TO LOOK AT (most excess hours first)")
    for s in sorted(stores, key=lambda s: -s["over_hrs_wk"])[:3]:
        L.append(f"  Store {s['store']} ({s['over_hrs_wk']:.0f} hrs/wk over): {X.insight(s, fleet)}")
    L.append("")
    L.append("5. DATA WARNINGS")
    warn = [f"  {t}: {n}" for t, n in res.get("checks", []) if t != "Sales" or "differ" in n]
    warn += [f"  {f}" for f in res.get("flags", [])]
    warn += [f"  COULD NOT READ {k}: {v}" for k, v in errors.items()]
    L += warn or ["  None."]
    L.append("")
    L.append("Full scorecard page attached (opens in any browser).")
    return "\n".join(L)


def build_html(res, errors):
    stores = res["stores"]
    w0, w1 = res["window"]
    e = html.escape
    rows = []
    for s in stores:
        ch = (s["productivity"] - s["prior_productivity"]) * 100 if s["prior_productivity"] else 0
        col = "#b00020" if s["productivity"] < 0.92 else ("#1b7f3b" if s["productivity"] >= 0.98 else "#222")
        rows.append(f"<tr><td>{s['rank']}</td><td>{s['store']}</td><td>{s['region']}</td>"
                    f"<td style='color:{col};font-weight:600'>{pct(s['productivity'])}</td><td>{ch:+.1f}</td>"
                    f"<td>{s['splh']:.2f}</td><td>{s['over_hrs_wk']:+.1f}</td><td>${s['over_cost_wk']:,.0f}</td>"
                    f"<td>{s.get('ot_wk', 0):.1f}</td><td>{e(X.insight(s, res['fleet']))}</td></tr>")
    dow = []
    for s in stores:
        cells = "".join(
            f"<td style='background:rgba(176,0,32,{min(max(s['dow'][d]['over_hrs_per_day'], 0) / 4, 1):.2f})'>{s['dow'][d]['over_hrs_per_day']:+.1f}</td>"
            for d in X.DOW)
        dow.append(f"<tr><td>{s['store']}</td>{cells}</tr>")
    notes = [X.SOURCES_NOTE] + list(res.get("checks", [])) + [("Missing day", f) for f in res.get("flags", [])]
    notes += [("Could not read", f"{k}: {v}") for k, v in errors.items()]
    nl = "".join(f"<li><b>{e(t)}:</b> {e(n)}</li>" for t, n in notes)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Labor scorecard {w1}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222}}table{{border-collapse:collapse;margin:12px 0}}
td,th{{border:1px solid #ddd;padding:4px 8px;font-size:13px;text-align:left}}th{{background:#f3f3f3}}h1{{font-size:20px}}h2{{font-size:16px;margin-top:28px}}li{{margin:4px 0;font-size:13px}}</style></head><body>
<h1>Labor scorecard: 4 weeks {mdy(w0)} to {mdy(w1)}, 2026</h1>
<p>Fleet productivity {pct(res['fleet']['productivity'])}; about {res['fleet']['over_hrs_wk']:.0f} hrs a week over standard.
Productivity = earned hours / service hours (100% = staffed exactly to standard).</p>
<table><tr><th>#</th><th>Store</th><th>Rgn</th><th>Productivity</th><th>vs prior (pts)</th><th>SPLH</th><th>Hrs/wk over</th><th>$/wk over</th><th>OT hrs/wk</th><th>Notes</th></tr>{''.join(rows)}</table>
<h2>Extra hours per day, by weekday</h2>
<table><tr><th>Store</th>{''.join(f'<th>{DAY_NAME[d][:3]}</th>' for d in X.DOW)}</tr>{''.join(dow)}</table>
<h2>About the data</h2><ul>{nl}</ul></body></html>"""


def run(end_arg, out_dir, today):
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    start = (end_arg or today) - timedelta(days=7 * 8 + 6)
    errors = R.build_daily(work, start, end_arg or today)
    if end_arg is None:
        end = R.latest_complete_sunday(work / "daily_v2.csv", R.STORES, today)
        if end is None:
            raise RuntimeError("no week in the last 8 is complete for all 12 stores in v2 (sales and hours > 0 every day)")
    else:
        end = end_arg
    print("window ends", end)
    win_start = end - timedelta(days=7 * 4 - 1)
    R.build_toast_punches(work / "toast", win_start - timedelta(days=0), end)
    missing = R.check_sales_cache(end)
    sales = R.SALES_CACHE if R.SALES_CACHE.exists() else None
    toast = labor_eval.load_weekly_sales(sales)
    punches = labor_eval.load_toast(work / "toast")
    days = labor_eval.load(work / "daily_v2.csv", work / "daily_legacy.csv")
    res = labor_eval.evaluate(days, end, toast=toast, punches=punches)
    if missing:
        res["checks"].append(("Sales", "Toast weekly sales missing for: " + ", ".join(missing) + "; v2 sales used there."))
    json.dump(res, open(work / "eval.json", "w"), indent=1, default=str)
    X_args = [sys.executable, str(HERE / "export_dashboard.py"), str(work / "eval.json"), str(out_dir)]
    subprocess.run(X_args, check=True)
    page = out_dir / f"labor_scorecard_{end.isoformat()}.html"
    page.write_text(build_html(res, errors), encoding="utf-8")
    return res, errors, page, end


def main():
    argv = sys.argv[1:]
    end_arg = date.fromisoformat(argv[argv.index("--end") + 1]) if "--end" in argv else None
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else DEFAULT_OUT
    do_send = "--send" in argv
    today = date.today()
    try:
        res, errors, page, end = run(end_arg, out_dir, today)
        body = build_body(res, errors)
        print(body)
        subject = f"Labor scorecard: 4 weeks ending {end:%b} {end.day}"
        if do_send:
            send(subject, body, [page])
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        if do_send:
            send("Labor scorecard FAILED", "The weekly labor scorecard did not run.\n\n"
                 "Nothing was changed in any tracker. Error:\n\n" + tb[-3000:])
        sys.exit(1)


if __name__ == "__main__":
    main()
