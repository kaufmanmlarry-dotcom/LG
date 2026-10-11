# Weekly labor scorecard: set up on the Whirl Labor PC

These are instructions for a Claude Code session on the Whirl Labor PC. Paste
this whole file in as the first message, or point the session at it.

## Goal

Every Monday at 9:30 AM Mountain, a scheduled script ranks the 12 stores on
labor productivity over the last 4 full weeks (Monday to Sunday) and emails the
results to kaufmanmlarry@gmail.com. Claude is not involved in the weekly run.
Claude is used only to build and test it now.

## What already exists

The repo `kaufmanmlarry-dotcom/LG` (branch `claude/compassionate-ptolemy-cmnx28`),
folder `analysis/`, holds a working version built in a cloud session. That
session could reach the files only as Dropbox text extracts, so its parsers
(`parse_tracker_text.py`, `parse_v2_text.py`, `parse_toast_time.py`,
`collect_extracts.py`) reconstruct columns from text with blank cells missing.
On the PC, replace them with direct workbook reads. Keep the evaluation and its
rules:

- `labor_eval.py` is the evaluation. Keep its logic and output.
- `export_dashboard.py` writes the CSVs and the per-store insight text.
- `run_weekly.py` picks the window and runs the steps.
- `output/dashboard_index.html` is the scorecard page.
- `check_hours_sources.py` is a one-off cross-check of Toast and WhenToWork against the trackers.

Before writing new readers, look in the Whirl Labor codebase for an existing
tracker reader or Toast loader and reuse it.

## Data sources (decided with Lar; do not change without asking)

| What | Source |
|---|---|
| Daily sales, actual hours, earned hours, scheduled (WTW) hours | v2 trackers `Store N Labor and Sales Forecasting 2026 v2.xlsx`. Earned = column V (Earned Sales) + column W (O/C). Actual = AA. WTW = the v2 WTW column. |
| Admin, Training, Go-Go hours | Legacy trackers `Store N Labor and Sales Forecasting 2026.xlsm`, Sales Ideal block (visible exclusion columns). These exist only in legacy. Do not fall back to v2 (v2 admin is zero). |
| Weekly sales used for SPLH | Toast net sales from `/Whirl Labor/Weekly Sales/_gross_cache_2026.json`, key `n`. Week 1 starts 2025-12-29. |
| Overtime | Toast time entries, corrected pull: `/performance tracking/Toast Files 2026/<Mon D+1>/TimeEntries_all_stores_runN.xlsx`, highest run N. Do not use the copies under `Performance Tracking GM/Toast Files` (uncorrected). |

Other rules:
- Stores: CO 98, 99, 101, 246, 256, 491, 516, 680, 1359; SD 530, 532, 1360. Wages CO $22/hr, SD $25/hr.
- Service hours = actual − (Admin + Training + Go-Go). Productivity = earned ÷ service. SPLH = Toast net sales ÷ service hours.
- The window is the 4 weeks ending the latest Sunday where every store's week is complete in v2 (sales and actual hours > 0 every day). The prior 4 weeks are used for "change vs prior".
- v2 weighted prep units are intentional. Keep them.
- Opener/closer allowance is 1.25 for every store.

## Workbook safety (Whirl Labor lessons)

- Read only. Never save a tracker with openpyxl. An openpyxl save nulls every formula's cached value.
- Open with `openpyxl.load_workbook(path, read_only=True, data_only=True)` and always close in `finally`. On Windows an unclosed workbook keeps a file handle and locks the tracker.
- Task Scheduler runs Python with a cp1252 console. Keep log and print output ASCII, or set `PYTHONIOENCODING=utf-8`.
- Run after Daily Tracker Update (7:30 AM, about 45–60 min) has finished on Monday.

## Check it matches before scheduling

Run it for the window ending 2026-10-04 (`--end 2026-10-04`). The cloud
version produced the table below. Direct reads should match closely.
Productivity within ±0.5 points is fine because the text extracts lost a few
cells. Explain any store that is further off before going on.

| Rank | Store | Productivity | SPLH | Over hrs/wk | OT hrs/wk |
|---|---|---|---|---|---|
| 1 | 99 | 102.1% | 93.57 | −1.8 | 13.2 |
| 2 | 246 | 99.6% | 97.29 | 0.4 | 0.4 |
| 3 | 516 | 98.8% | 109.34 | 1.4 | 12.1 |
| 4 | 1359 | 98.5% | 78.46 | 1.4 | 3.8 |
| 5 | 98 | 96.8% | 85.39 | 3.2 | 0.0 |
| 6 | 680 | 96.5% | 86.55 | 3.3 | 0.3 |
| 7 | 532 | 95.9% | 110.42 | 5.3 | 3.2 |
| 8 | 101 | 93.2% | 109.15 | 9.0 | 4.9 |
| 9 | 491 | 92.7% | 85.50 | 8.8 | 1.4 |
| 10 | 1360 | 90.7% | 94.50 | 9.3 | 6.4 |
| 11 | 256 | 89.8% | 97.45 | 11.3 | 5.6 |
| 12 | 530 | 86.9% | 119.13 | 24.8 | 2.3 |

Fleet: 94.4%, about 76 hours a week over standard (about $1,800 a week).

## The Monday email

Send with the same method the existing Whirl Labor scripts use for their emails
(for example the weekly Docs and Notebooks health email). Do not add a new mail
setup.

- To: kaufmanmlarry@gmail.com only.
- Subject: `Labor scorecard: 4 weeks ending <Mon D>`
- Body: plain and short:
  1. Fleet productivity, hours a week over standard and the cost.
  2. The ranking of all 12 stores with productivity and the change from the prior 4 weeks.
  3. Stores that moved 2 or more places, or 3 or more points.
  4. The top 3 store insights (largest excess hours first), from `export_dashboard.insight`.
  5. Data warnings from `data_checks` (missing legacy days, hidden Go-Go, sales gaps).
- Attachment: the scorecard page as one self-contained HTML file. Build it from
  `output/dashboard_index.html` with the week's CSV data embedded in the page, so
  it opens offline in any browser.
- If the run fails, or no week is complete for all stores, still send an email
  saying what failed. Never send nothing.

## Schedule

Add a Task Scheduler task: weekly, Monday, 9:30 AM, the same way the other
Whirl Labor tasks are registered. Then fire it once by hand through Task
Scheduler, not just from the console, and confirm the email arrives and
`LastTaskResult = 0`.

## When finished

Commit the PC version back to the LG repo, and add the task to the Whirl Labor
CLAUDE.md list of scheduled tasks.
