# CONTEXT.md — START HERE EACH SESSION
# Election Forecast Dashboard — current-state snapshot
# Last updated: 2026-06-28 (GA Senate = Jan-2021 runoff; "GA Special" Warnock view;
#                           convergence chart polish; county-grain reveal fix;
#                           ballot-mode buckets + turnout scenario + County Insight;
#                           election ballot manifest = date-aware race dropdown)

> This is the fast on-ramp. Read this first, then `HANDOVER_BRIEF.md` for the
> full spec. `PROGRESS.md` = chronological log. `Issues.md` = problems + plans.

---

## 🚦 WHERE WE ARE RIGHT NOW

  Phase 0  ✅ COMPLETE   Planning / architecture
  Phase 1  ✅ COMPLETE   ETL — baseline.db built + QA-verified
  Phase 2  ✅ COMPLETE   Live ingestor — poller + replay + mock
  Phase 3  ✅ COMPLETE   Analytics — shift, projection, snapshot history, win prob
  Phase 4  ✅ COMPLETE   FastAPI REST + WebSocket (serves analytics)
  Phase 5  ✅ COMPLETE   React UI (10 panels) — Vite, consumes the API
  Phase 6  ✅ COMPLETE   Integration test — all 8 states × 2 races reproduce reality
  Phase 7  ⬜ NEXT       Deploy — public web URL (host API+DB+UI; pick a domain)

**Next action:** Phase 7 (deploy) — OR the "for fun" hypotheticals (scenarios
already built: in the UI scenario dropdown pick Ossoff vs Vance D+5 / AOC vs
Vance D+5, then click Next Batch). 2026-Senate-candidates scenario still TODO.

**NEW — election-night simulator:** UI has a scenario dropdown + Reset + "Next
Batch ▶" stepper (20→40→...→100%). Backend: api/simulation.py + /api/sim/*.
On real election day the Phase 2 poller replaces the button (same data path).
integration_test.py = repeatable end-to-end assertion (run: python integration_test.py).
PERF (2026-06-27, Issue #5): Next Batch ~1-2s (was 18-50s). Fixes: results_live
indexes + WAL, /api/states reads live_snapshots (no recompute), in-memory
baseline cache, one-commit-per-batch.
REVEAL (2026-06-27, Issue #6): simulator now reveals counties PROPORTIONALLY /
in parallel (ReplayFeed order="proportional") — at X% statewide each county is
~X% in (was: whole counties one at a time). NOTE in true-2020 mode shift≈0 &
convergence hugs baseline BY DESIGN (same data); use a swing scenario (Ossoff/
Vance D+5) to see real shift/convergence. See PROGRESS.md / Issues.md.
⚠️ After ANY change under api/ or ingestor/: restart the API (no --reload) AND
click Reset in the UI (Reset rebuilds the sim feeds).
**To see the dashboard (2 terminals):**
  1) uvicorn api.main:app --port 8000
  2) cd ui && npm run dev      → open http://localhost:5173
**DB state:** ALL 8 states populated TRUE (zero swing) for BOTH races —
President vs 2020; Senate vs most-recent (GA = Jan-2021 RUNOFF county-level,
NC 2020, others 2024). Winners match reality (GA Senate now Ossoff D 50.82%).
API uses per-state Senate baseline (SENATE_BASELINE in api/main.py).
Re-populate any race: python analytics/engine.py <ST> <race> <year> [swing] [noise]
(API has no --reload here; restart uvicorn after editing api/ code.)

---

## ✅ WHAT'S BUILT AND WORKING

**Database** — `data\db\baseline.db` (SQLite). 5 baselines loaded, QA-passed:
  - President: 2020 + 2024 (all 8 states)
  - Senate: 2018, 2020, 2024 (coverage per state below)
  - 72,992 precincts · 771,198 historical rows · 3,161 county rollups
  - `results_live` + `live_snapshots` currently hold the TRUE 100% replay for
    all 8 states × both races (left by integration_test.py). Re-runnable.

**ETL** — `ingestor/etl_baseline.py` (re-runnable; additive by election_year)

**Live ingestor** — `ingestor/`:
  - `clarity_poller.py`  core engine (feed-agnostic; parses real Clarity XML;
                         optional on_write hook for analytics)
  - `replay_harness.py`  replays real baseline data as a fake "election night"
                         (supports a synthetic `swing` to test the analytics)
  - `mock_feed.py`       synthetic data incl. red-mirage demo

**Analytics** — `analytics/`:
  - `shift_calculator.py` per-precinct/county/state shift + projection (two-party)
  - `bayesian_model.py`   win probability, confidence tier, lean label
  - `rollup.py`           live county rollups + watch list (Panels 7/8/9)
  - `engine.py`           orchestrator; writes `live_snapshots` time-series;
                          replay+analytics demo
  New table: `live_snapshots` (per-poll statewide series → trend chart Panel 5)

**API (Phase 4)** — `api/` (`main.py`, `db.py`):
  - GET /api/health · /api/states?race= (strip+EV) · /api/state/{abbr}?race=
    (full bundle) · /api/state/{abbr}/series?race= · WS /ws?race=
  - Run:  uvicorn api.main:app --reload --port 8000   → http://localhost:8000/docs

**UI (Phase 5)** — `ui/` (Vite + React + Recharts):
  - All 10 panels in `ui/src/components/`; `App.jsx` polls the API every 5s.
  - Vite proxies /api + /ws to :8000 (see ui/vite.config.js).
  - Run: `cd ui && npm run dev` → http://localhost:5173 (needs the API running).
  - .claude/launch.json (in C:\Users\subho) registers it for the preview tool.

**Try it:**
  python ingestor/replay_harness.py GA president 2020
  python analytics/engine.py GA president 2020          # replay + win-prob
  python analytics/engine.py GA president 2020 -0.03     # same, w/ R+3 swing
  python ingestor/mock_feed.py
  pip install -r requirements.txt   # pandas, clarify, requests

---

## 🗳️ SENATE BASELINE COVERAGE (after Phase 1b)
  AZ, MI, TX  → 2018 + 2020 + 2024
  GA, NC      → 2020   (GA also has 2021; see below)
  NV, PA, WI  → 2018 + 2024   (PA/NV/WI had NO 2020 Senate race)
  GA Senate baseline USED = 2021 Jan-5 RUNOFF (county-level, 155/159 cty — Issue #7),
    loaded via ingestor/etl_ga_runoff_2021.py: regular→'senate', special→'senate_special'.
    Ossoff WON the runoff (Nov general went under GA's 50% rule) and his seat is up
    2026, so the runoff is the right baseline. The 2020 Nov-general GA rows are kept
    (just unused for GA). SENATE_BASELINE["GA"]=2021 in api/main.py.
  NEW — "GA Special" race view (race_type=senate_special): the Warnock vs Loeffler
    Jan-2021 runoff as a GA-ONLY race (3rd toggle in the UI). RACE_STATES limits it
    to GA; SENATE_SPECIAL_BASELINE["GA"]=2021. ReplayFeed auto-uses whole-county
    reveal for county-grained data (GA senate/senate_special) so % steps 20/40/60/
    80/100 smoothly (proportional mode was jumpy with 1 precinct/county).

---

## 🔑 KEY DECISIONS MADE (this session)
  - QA tolerance ±0.1% per candidate (MIT precinct data ≠ exact certified).
  - Added 2024 President as secondary reference (chosen over 2016).
  - Added 2018 Senate (TX Cruz–O'Rourke) + 2024 Senate (fills PA/NV/WI).
  - Live testing approach = archived replay + mock (no 2026 data exists yet).
  - LIVE-ACCESS STRATEGY (important): pull 2026 PRIMARY results to (a) beat the
    Clarity 403 against a real live feed and (b) capture the exact 2026 precinct
    names. Then build a `precinct_crosswalk` table (2026→2020, with weights for
    splits/merges) OFFLINE; unmatched precincts fall back to county level.
    Ship simple name-match + county fallback first; spatial weighting later.

---

## ⚠️ TOP OPEN RISKS (full detail in Issues.md)
  #1 Clarity CDN 403s scrapers — worked around for dev, UNSOLVED for live.
  #3 Live precinct-name → 2020 baseline mapping (the crosswalk; the real live
     challenge) — strategy decided, not yet built.
  (#4 results_live had no time-series — RESOLVED in Phase 3 via live_snapshots.)
  Confidence on election-night live: ~70-75% overall; firms up after the
  July live-access test against a real 2026 primary.

---

## 🗓️ NOVEMBER 3, 2026 PREP
  Election Day = Tue Nov 3, 2026. Live-access work should START ~July
  (test vs real 2026 primaries). Real election IDs only knowable mid–late Oct.
  Full timeline in Issues.md.

---

## 📋 WORKING RULES (how the user wants this run)
  - Report findings at each step BEFORE moving on.
  - Do NOT advance to the next Phase without explicit go-ahead.
  - Read the codebook when column names are ambiguous.
  - Print progress as scripts run; verify output with an independent query after.
  - When a phase finishes: update phase status in HANDOVER_BRIEF.md + CONTEXT.md,
    add a PROGRESS.md entry, log any problems in Issues.md.

---

## 🗂️ DOC MAP
  README.md          project intro + how to start the two servers (run commands)
  CONTEXT.md         ← you are here: current state, start each session here
  DASHBOARD_GUIDE.md user guide: how to read/run/simulate the dashboard
  HANDOVER_BRIEF.md  full spec: UI panels, model, schema, data, phase plan
  QUICK_REFERENCE.md at-a-glance cheat sheet (schema, URLs, DOIs)
  DATA_SETUP.md      every data file: full path, contents, source/DOI (all in data\raw\)
  PREP.md            election-night live-data readiness: per-state feeds + timeline + tests
  TESTING.md         plain-language test guide: what to click, what you should see, pass/fail
  DEPLOY.md          Phase 7 deploy plan: frontend→Vercel, backend→Render/Fly, caching
  FEED_AUDIT.md      per-state live ENR feed audit (Clarity vs own; mode availability)
  PROGRESS.md        chronological work log (newest on top)
  Issues.md          problems, workarounds, November readiness plan
  requirements.txt   Python deps
