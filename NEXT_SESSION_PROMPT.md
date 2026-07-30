# Next-session prompt — Election Forecast (LIVE-READINESS)

Paste the block below to start the next session.

---

We're continuing the **Election Forecast Dashboard** (`C:\Users\subho\election-forecast`),
a Nov 3, 2026 election-night forecasting tool. Read `CONTEXT.md` first (its
"🗓️ SCHEDULE" table near the top and the "🚀 Deployment facts" section have the current
state), then this prompt. Full story of the most recent work session is in `PROGRESS.md`'s
**2026-07-18** entry.

## Where we are (as of 2026-07-18)

**9 states of data, 7 with live feeds validated to exact certified results:**
GA, NC, PA, AZ, MI, TX, SC all have working `*_live_feed.py` scripts proven to match
certified historical results exactly (see `TESTING.md` §8). Only WI and NV lack a live
feed — NV doesn't matter (no 2026 race at all); WI is low-priority (no statewide feed,
72 county clerk sites, and not in `general2026`'s tracked senate list either).

**Production is deployed and live:** Vercel (frontend) + Render (backend), Starter tier
with a 1GB persistent disk, DB republished as GitHub Release **`db-v3`** (fixed a real
data-integrity bug found this session — MI/TX's 2020 Senate baseline had never been
converted to county-pseudo, and `results_live` for MI/TX/NC held stale/wrong data).

**A production poller now exists** (`ingestor/production_poller.py`) — a real scheduler
that wraps every state's `ingest()` call on its own interval, deployed inside the Render
web service (launched from `entrypoint.sh`, gated by `ENABLE_POLLER`/`POLLER_MODE` env
vars). **It is currently OFF** in production — deliberately, to avoid pointless polling
before MI's Aug 4 primary even has a live electionId. Dockerfile now has Xvfb +
Playwright/Chromium baked in, so MI's headed-browser requirement works on Render too
(confirmed: build succeeded).

## The concrete near-term plan, in order

1. **Jul 21, 2026 — AZ primary.** Pure mechanics smoke test, no manifest change needed
   (AZ isn't tracked by `general2026`, only by `general2028` eventually). If this session
   starts after Jul 21, just note whether anyone actually ran it and what happened.
2. **~Aug 2–3, 2026 — turn the poller on.** Render → service → Environment tab → set
   `ENABLE_POLLER=1` and `POLLER_MODE=mi-primary` → save (auto-redeploys). This runs
   `build_mi_primary_tasks()`: polls MI's Aug 4 primary every 90s, auto-discovering the
   electionId from `"8/4/2026"`, writing under **scratch race_type `mi_primary_2026`**
   (never the real `senate` race_type — that would corrupt the just-fixed Nov 2026
   tracking data). **Verify in Render's Logs tab that it actually finds the election
   BEFORE Aug 4 itself** — don't wait until election night to discover it's still "NOT
   FOUND".
3. **Aug 4, 2026 — MI primary, live.** Watch it run for real. Afterward: set
   `ENABLE_POLLER=0` again, and replace the "TBD AUG 4" candidate placeholders in
   `api/elections.py`'s `general2026` manifest with MI's actual nominees (small code
   push, not a DB change).
4. **Decide about the Starter subscription** after Aug 4 — fine to let it ride, or pause
   and resume before the October dry run (prorating a few days doesn't matter, per the
   user).
5. **Aug 11, 2026 — WI primary**, if there's spare runway (optional, not gating Nov 3).
6. **Mid–late Oct, 2026 — the real unlock.** GA/MI/NC/TX/SC publish their actual Nov 3
   general-election IDs. Fill these into `production_poller.py`'s
   `build_production_tasks()` (currently `_tbd()` placeholders) — mechanical, not new
   engineering, since MI/TX already auto-discover from a date string and the others just
   need a manual electionId lookup (see `FEED_AUDIT.md`).
7. **~2 weeks before Nov 3** — full end-to-end dry run against the real 0%-reporting
   general pages, all 5 tracked states.
8. **Election week → Nov 3** — final rehearsal, then `ENABLE_POLLER=1` /
   `POLLER_MODE=prod` for the real thing.

## Reminders / gotchas (still true, carried forward)

- `baseline.db` is gitignored — production only picks up local DB changes when you
  re-gzip + re-upload as a new GitHub Release and update Render's `DB_URL` env var
  (current tag: `db-v3`). Local changes never silently reach prod.
- **Never run `python ingestor/etl_baseline.py`** to add a state or year — it drops and
  rebuilds the whole DB from 5 hardcoded sources, destroying every live-feed
  county-pseudo baseline built since (SC's loader, `etl_sc_baseline.py`, is additive —
  that's why it exists as a separate script).
- `/api/states` reads a **pre-computed cache** (`live_snapshots`) that only refreshes
  when empty for a state+race — if numbers look stale after writing new `results_live`
  rows, clear the relevant snapshot rows (`DELETE FROM live_snapshots WHERE state=...
  AND race_type=...`) rather than assuming the write failed.
- Always use a **scratch race_type** (not a real tracked one like `senate`) for any
  primary-night mechanics test or early live-fire test — writing real-but-different
  election data under a real race_type corrupts the actual tracked comparison (this is
  exactly the MI/TX/NC bug fixed this session).
- MI needs a **headed** browser (works locally on any machine with a real display, and
  now also on Render via Xvfb). TX only needs headless. Everything else (NC/GA/PA/AZ/SC)
  is plain httpx.
- Clarity is dead everywhere checked except SC (still genuinely alive there) — verify
  per state, don't assume.
- API runs without `--reload`: restart uvicorn + click Reset in the UI after any
  api/ingestor code change.

## Longer-term / not urgent

- WI and NV live feeds — optional, `general2028` prep only.
- Precinct-level drill-down (GA Clarity + NC dashboard) — optional precision upgrade,
  not required for Nov 3 (county-level is proven sufficient).
- `general2028` needs 2022 Senate data loaded (already on disk at
  `data/raw/2022-SENATE-precinct-general.csv`, just not loaded into the DB yet).
