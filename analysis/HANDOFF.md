# Handoff: labor scorecard, from the cloud chat to the local chat on the PC

Read this first, then `analysis/PC_SETUP.md` (the build instructions).
Repo: `kaufmanmlarry-dotcom/LG`, branch `claude/compassionate-ptolemy-cmnx28`.

## What the user (Lar) wants

Rank the 12 stores on labor productivity over a rolling 4 weeks ending each
Sunday, and find places to improve. Admin, training and Go-Go hours are excluded
from "service hours". Open hours set the 1-person floor. The Sales Factor table
sets the earned staffing. The first run is done (below). The goal now is a
weekly run on this PC with no Claude tokens. Lar chose **Option B**: a plain
script on the PC, scheduled Monday 9:30 AM, that **emails only
kaufmanmlarry@gmail.com**.

## What is done

- Evaluation code in `analysis/` (see PC_SETUP.md for the file list). It was
  built in the cloud from Dropbox text extracts, because the cloud container
  could not open the Excel files or reach Toast/WhenToWork.
- A one-time analysis for the 4 weeks Sep 7 to Oct 4, 2026 (prior 4 weeks
  Aug 10 to Sep 6). The ranking is in PC_SETUP.md. It is the check the PC
  version must reproduce (productivity within about 0.5 points per store).
  Fleet 94.4%, about 76 hrs/wk over standard, about $1,800/wk.
- A private dashboard artifact in claude.ai (Labor Evaluation chat). It can
  only be updated from the cloud, so the PC version replaces it with the email.
- GitHub access fixed (Claude app installed on the account). Everything is pushed.

## What is left, in order

1. **On the PC: build and schedule the weekly run** per `PC_SETUP.md`. Reuse the
   existing Whirl Labor tracker reader and email method. Read workbooks
   read-only. Prove it matches the ranking, then register the Task Scheduler
   task and fire it once through Task Scheduler.
2. **Legacy tracker fixes, which Lar is doing himself, one step at a time:**
   - **Fix 1, store 516 opener/closer.** Not a single setting. In the legacy
     tracker the O/C value is 1.25 through Sun Aug 23 and 0.75 from Mon Aug 24
     on, so cells were overwritten (the same thing happened with 530's Go-Go).
     It was at "Step 2": Lar is to open `Store 516 Labor and Sales Forecasting
     2026.xlsm`, main daily sheet, Sales Ideal block, the **O/C** column, and
     report whether the formula bar shows a formula (`=...`) or a typed number
     for Aug 23 and for Aug 24. Next: restore the formula from Aug 23 down over
     the bad cells, then check that Aug 24 onward shows 1.25.
   - **Fix 2, legacy WTW column is stale** (wrong on 79 of 336 store-days; v2
     matched WhenToWork on all 336). Recommended: have the Labor Hrs Var Report
     read scheduled hours from v2 instead. A code change, so the PC session can do it.
   - **Fix 3, store 530 legacy Hours Forecast:** typed 2.0 on Oct 1 and Oct 3
     where a formula belongs. Copy the formula from the neighboring cell. Minor.
3. **Confirm Nelly reran the tracker load** for Sep 28 (516), Oct 5 and Oct 7
   (99). An email asking her went out earlier. Check the legacy actuals now exist.
4. **Raise v2 issues** with whoever maintains Whirl Labor: v2 has no admin
   hours; v2 sales run below Toast net at 516 (about -6%) and 99 (about -5%),
   which may be missing orders and understate earned hours; three hours with 42
   prep units earned 2 staff where the table says 3; v2 actual hours run a
   little high at 491 and 98; the v2 overtime column is empty.
5. **Act on the findings.** 530 (+25 hrs/wk, worst Tuesday, about 15 hrs/wk over
   its schedule), 256 (heavy base schedule), 1360 (about 23 hrs/wk over
   schedule), 101 (slow weekdays), 491 (busy days). GM overtime at 99
   (13 hrs/wk; no wage in Toast, may be salaried) and 516 (12 hrs/wk).
6. Optional later: an hour-by-hour drill-down, which needs the direct reads on the PC.

## Decisions already made (do not reopen)

- Stores: CO 98, 99, 101, 246, 256, 491, 516, 680, 1359. SD 530, 532, 1360.
  Wages CO $22, SD $25. "All 12 stores should align or we have a problem."
- v2 trackers are the system of record for sales, actual hours, earned hours and
  WTW. Admin and training exist only in the legacy trackers; v2 admin is zero.
- Actual hours: Toast corrected time entries (`Toast Files 2026/<Mon D+1>/`,
  highest run). Scheduled hours: WhenToWork. Toast auto clock-outs are fixed
  within two days.
- SPLH uses Toast net weekly sales (`Weekly Sales/_gross_cache_2026.json`, `n`).
- v2 fractional prep-unit weights are intentional.
- Opener/closer allowance is 1.25 for every store.
- Overtime comes from Toast.
- Schedule rule: flag a store only when it works more than the schedule.
  WhenToWork includes offsite, borrowed/coverage and unassigned shifts.

## Working with Lar

Plain language, no jargon. One step at a time and wait for his answer. Confirm
before anything outward-facing. Claude tokens matter to him: the org already hit
its monthly spend limit once. His Whirl Labor notes include these rules: never
save a tracker through openpyxl, close workbooks in `finally`, and keep Task
Scheduler output ASCII.

## Caveats

- It is now mid-October. Newer weeks (ending Oct 11) may be complete, so the
  PC run should pick the latest complete Sunday itself. Do not hard-code Oct 4
  except for the matching test.
- The cloud-built numbers came from text extracts that drop blank cells, so
  small differences from direct reads are expected. Explain any big ones.
