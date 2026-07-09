# CONTEXT.md — START HERE EACH SESSION
# Election Forecast Dashboard — current-state snapshot
# Last updated: 2026-07-06 (LIVE-READINESS underway — CORS locked; NC + GA WIRED
#                           END-TO-END (2 live states); AZ mapped; Clarity confirmed
#                           dead; Playwright installed; plan: PA/TX/NV → SC → MI → WI)

> This is the fast on-ramp. Read this first, then `HANDOVER_BRIEF.md` for the
> full spec. `PROGRESS.md` = chronological log. `Issues.md` = problems + plans.

---

## 🚦 WHERE WE ARE RIGHT NOW

  Phases 0–6  ✅ COMPLETE   ETL · ingestor · analytics · API/WS · React UI · integration test
  Phase 7     ✅ DEPLOYED — dashboard is PUBLIC (one small CORS step left)
     ├─ Frontend ✅ LIVE on Vercel → https://election-forecast-silk.vercel.app
     └─ Backend  ✅ LIVE on Render → https://election-forecast.onrender.com
  ⚠️ URL GOTCHA (resolved 2026-07-02): OUR site is **election-forecast-SILK**.vercel.app.
     The bare `election-forecast.vercel.app` is a DIFFERENT, unrelated project (a
     national 2026 House forecast w/ US district map) that took the name first — NOT
     ours. Our app is the 8-swing-state President/Senate simulator; it has NO House,
     no all-50-states, no US map (verified: no map lib installed). Don't confuse them.

### 🔴 NEXT SESSION — START HERE  →  LIVE-READINESS (state ingestors)

**Status: 2 of 8 states WIRED END-TO-END + validated.** Dashboard is deployed/public;
CORS locked. The work now = building each state's live feed → results_live so the
analytics run unchanged on election night.

**How live ingestion works (the proven pattern):**
  - County-level data is stored as **county-pseudo-precincts** keyed `{ST}-{fips}-CTY`.
    The analytics engine is precinct-keyed, so if BOTH the baseline and the live feed
    use the same `{ST}-{fips}-CTY` ids, shift / win-prob / county table all "just work"
    with **zero core-code changes**.
  - A `*_live_feed.py` script fetches the state's live source, maps to `{ST}-{fips}-CTY`,
    and writes results_live. ⚠️ It MUST `DELETE ... WHERE precinct_id LIKE '{ST}-%'`
    first (not just `-CTY`) — leftover precinct-level rows from sims/tests double-count.

**DONE (live + validated to the exact certified result):**
  - ✅ **NC** — open S3 bulk file (`nc_ingestor.py` + `nc_live_feed.py` +
    `etl_nc_county_baseline.py`). Plain httpx, no bot-block. **Has live ballot-mode
    breakdown** (election-day/early/mail/provisional). 100 counties.
  - ✅ **GA** — open Enhanced Voting API (`ga_live_feed.py`). Plain httpx (Playwright only
    to DISCOVER the endpoint). Totals only (mode='all'; API exposes no live mode split).
    159 counties. Baseline = 2021 runoff county-pseudo (already loaded).

**THE PLAN (in order):**
  1. **PA, TX, NV** next — likely easy/GA-style (map endpoint → wire like GA). Doable NOW.
  2. **SC** — if it's easy like GA/NC, add it here too (Class-2 Graham seat; enr-scvotes.org).
  3. **MI** — take a real run BEFORE **Aug 4** primary (de-risk). Headless Playwright was
     BLOCKED by Cloudflare; try non-headless/stealth OR find an open bulk-download.
  4. **WI** — hardest (no statewide feed; 72 county sites / AP). Research approach anytime;
     validate at **Aug 11** primary. May need a pragmatic compromise (aggregator / subset).
  - **AZ** — already MAPPED (open `cdn1.arizona.vote` + Cloudflare SPA); VALIDATE at the
    **Jul 21** primary (that's the only way to test live real-time behavior).

**Playwright** (installed): drives a real Chrome to (a) DISCOVER hidden data endpoints on
JS/SPA sites and (b) pass Cloudflare "Just a moment…" guards. Needed ONGOING only where
the data endpoint itself is locked — so far just **MI**. NC/GA/AZ data is open (plain httpx);
Playwright there was one-time discovery only. **Clarity ENR = DEAD** (states moved to
Enhanced Voting; the old 403 endpoint is decommissioned, not a beatable block — don't chase it).

**Timing rule:** access/discovery work is best done NOW (de-risks hard states, leaves time
for plan B); live real-time VALIDATION can ONLY happen at each primary. Easy states (open
data) = fully buildable + testable now against archives.

Reproducible deploy steps + URLs: **DEPLOY.md → "✅ AS-BUILT"**. ⚠️ Render free tier
spins down after ~15 min idle → first hit ~30–60s cold start (re-downloads the 43 MB DB).

### 🚀 Deployment facts (so you don't re-derive them)
  - **GitHub:** github.com/subhojitr-dev/election-forecast (branch `main`). Data (CSVs +
    baseline.db, 1.4 GB) is **gitignored** — see DATA_SETUP.md to obtain/rebuild.
  - **Backend:** Render Docker web service (FREE tier). On boot, `entrypoint.sh` →
    `download_db.py` fetches baseline.db (43 MB gzip) from a **GitHub Release** (tag
    `db-v1`, asset `baseline.db.gz`) via the `DB_URL` env var, unzips to data/db/.
    - ⚠️ Free tier **spins down after ~15 min idle** → first hit after = ~30–60s cold start.
    - ⚠️ Ephemeral disk → re-downloads DB each boot; sim state resets (fine for demo).
    - For election night: upgrade to **Starter ($7/mo) + a persistent disk** at data/db/.
    - **If baseline.db changes:** re-gzip it, upload a NEW release asset, update `DB_URL`.
  - **Cache-Control** (max-age=15, swr=30) on /api/states + /api/state = the scale lever.
  - **Local dev still works** unchanged (2 terminals, below) — `VITE_API_BASE` unset = relative.

### 📋 PENDING — EXECUTION ORDER (chronological; full dated timeline in PREP.md)

  ✅ DONE: deploy (frontend Vercel + backend Render). Small wrap: confirm CORS lockdown
     saved on Render (CORS_ORIGINS = the Vercel URL).

  Everything below = LIVE-READINESS for Nov 3 (the long pole; gated by the summer primaries,
  which are the ONLY live-feed test windows — irreplaceable, so the plan is built around them):

  ① NOW → mid-July (foundation — start immediately)
     - ✅ DECIDED 2026-06-30: AP Elections API **SKIPPED** (enterprise/quote-only, likely
       $thousands/cycle — not worth it for a solo build). Going with the FREE state ENR
       feeds (Clarity + own systems). Revisit AP only if budget/scope changes. So build
       the feeds directly:
     - Build the NC ingestor (easiest; its dashboard has by-voting-method data) — proves the
       non-Clarity path and gives a clean second feed.
     - Start the Clarity 403 fix (Issue #1) — gates GA/PA/TX/MI.
  ② Jul 21 — AZ primary (live test #1): pull AZ's COUNTY feed end-to-end (clean county→county join).
  ③ Aug 4 — MI primary (live test #2): per-county Clarity discovery (county totals); fill the
     MI 2026 nominees (1-line edit in api/elections.py `candidates`).
  ④ Aug 11 — WI primary (live test #3): WI at COUNTY-level (no precinct feed exists — fine now).
  ⑤ Aug → Sep — harden: finish all 8 COUNTY ingestors; wire the live poller as a prod
     background worker (replaces "Next Batch"); load 2022 Senate (general2028 stub).
     NOTE: precinct crosswalk (Issue #3) is MOOT under county-level — DROPPED from the path.
  ⑨ AFTER everything works — OPTIONAL precision upgrade: precinct-level drill-down for GA
     (Clarity) + NC (dashboard) only. Not required for Nov 3.
  ⑥ Early–mid Oct: election-ID auto-discovery; test the no-summer-primary states
     (NV/NC/PA/TX/GA) against archives/specials.
  ⑦ ~2 wks before (mid–late Oct): capture the real 2026 election IDs (states publish the
     general at 0%); FULL end-to-end dry run, all 8 × both races; upgrade Render → Starter
     ($7/mo) + persistent disk; add monitoring (SQLite→Postgres only if very high load).
  ⑧ Election week → Nov 3: final rehearsal → GO LIVE (poller streams the real feed through
     the exact same pipeline as the simulator).

  ⟹ Start NOW (county-level v1; AP & the crosswalk are both OFF the table): (1) NC county
     ingestor · (2) Clarity 403 fix · (3) a 2nd county feed (AZ or MI) to prove the pattern.

  ⚠️ REMAINING-WORK REALITY CHECK: the live feeds DO NOT work yet. Built = the Clarity XML
  PARSER + the ReplayFeed simulator. NOT built = live Clarity fetch (403) + the per-state
  COUNTY ingestors + the prod poller. (Precinct crosswalk = MOOT under county-level.)

⚠️ Local dev: after ANY change under api/ or ingestor/, restart uvicorn (no --reload) AND click Reset in the UI.
**To see the dashboard (2 terminals):**
  1) uvicorn api.main:app --port 8000
  2) cd ui && npm run dev      → open http://localhost:5173
**DB state:** ALL 8 states populated for BOTH races. Winners match reality. GA Senate
baseline = Jan-2021 RUNOFF (county-level, **now 159/159 counties, exactly certified:
Ossoff 50.61% / Warnock 51.04%** after Issue #7 estimate-fill — RESOLVED).
**Baselines + which races are on each ballot now come from the ELECTION MANIFEST
`api/elections.py`** (not the old SENATE_BASELINE dict). 7 elections: demo (all races),
pres2024 / sen2020 / sen2024 / sen2018 (historical replays), general2026 (Senate
GA/MI/NC/TX with REAL nominees — Ossoff/Collins, Cooper/Whatley, Talarico/Paxton,
MI TBD), general2028 (stub — needs 2022 Senate data). The UI has an **Election dropdown**
+ a dynamic **race toggle** (only races on that ballot show).
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

**API** — `api/` (`main.py`, `db.py`, `elections.py`, `simulation.py`):
  - /api/health · /api/elections · /api/states?race=&election= ·
    /api/state/{abbr}?race=&election= · /api/state/{abbr}/county/{cty} (note+modes) ·
    /api/state/{abbr}/series · /api/scenarios · /api/sim/{reset,next,status} · WS /ws
  - Run:  uvicorn api.main:app --port 8000   → http://localhost:8000/docs  (no --reload)

**UI (Phase 5)** — `ui/` (Vite + React + Recharts):
  - Panels in `ui/src/components/` (incl. CountyInsight); `App.jsx` polls every 10s;
    Election dropdown + dynamic RaceToggle; `api.js` uses VITE_API_BASE (prod).
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
  GA Senate baseline USED = 2021 Jan-5 RUNOFF (county-level, **159/159 cty, exactly
    certified** — Issue #7 RESOLVED via estimate-fill), loaded via
    ingestor/etl_ga_runoff_2021.py: regular→'senate', special→'senate_special'.
    Ossoff WON the runoff (Nov general went under GA's 50% rule) and his seat is up
    2026, so the runoff is the right baseline. The 2020 Nov-general GA rows are kept
    (just unused for GA).
  ⚠️ Baselines + per-ballot races now come from the ELECTION MANIFEST **api/elections.py**
    (it REPLACED the old SENATE_BASELINE / SENATE_SPECIAL_BASELINE / RACE_STATES dicts).
  NEW — "GA Special" race view (race_type=senate_special): the Warnock vs Loeffler
    Jan-2021 runoff as a GA-ONLY race (3rd toggle in the UI). ReplayFeed auto-uses
    whole-county reveal for county-grained data (GA senate/senate_special) so % steps
    20/40/60/80/100 smoothly (proportional mode was jumpy with 1 precinct/county).

---

## 🔑 KEY DECISIONS MADE (foundational — see PROGRESS.md for the full history)
  - 2026-06-30 — SKIP the AP Elections API (enterprise/quote-only, ~$thousands; not worth it
    for a solo build). Go with the FREE state ENR feeds (Clarity + own systems). Revisit AP
    only if budget/scope changes.
  - 2026-06-30 — **GO COUNTY-LEVEL FOR ALL 8 STATES as the live v1.** Correct for the overall
    result (county totals aggregate to the SAME statewide winner / win-prob / convergence);
    only loses precinct drill-down + a little early-night precision (which `reporting_weight`
    already damps). WHY it's the right call: county FIPS is stable year-to-year, so the
    **PRECINCT CROSSWALK (Issue #3) becomes MOOT** (clean county→county join, no name-matching),
    and **WI** (no precinct feed) becomes tractable. Reuses `county_rollup` + the proven
    GA-runoff "county-as-pseudo-precinct" pattern (1 pseudo-precinct per county everywhere).
  - 2026-06-30 — **LATER (after the county-level live pipeline works end-to-end):** add
    PRECINCT-LEVEL drill-down for the EASY states only — **GA (Clarity) + NC (its dashboard)**
    — as a precision enhancement, NEVER a requirement. Other states stay county-level. Where a
    county is shown at county grain, caption it: "Precinct-level data not available for this county."
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
  #1 Clarity CDN 403s scrapers — UNSOLVED for live, but TRACTABLE: browser-faithful fetch
     (session cookies + header order) → headless browser (Playwright) fallback. Effort, not a wall.
  #3 Precinct crosswalk — **MOOT under the county-level v1 decision** (county FIPS join is
     exact; no name-matching). Only re-enters IF/when GA+NC precinct drill-down is added later.
  (RESOLVED: #4 time-series → live_snapshots · #5 perf · #6 reveal · #7 GA runoff counties · #8 feed audit.)
  Confidence on election-night live: HIGHER now — county-level erases the crosswalk + WI risk;
  the main remaining unknown is the 403 fetch. Firms up after the July/Aug primary live tests.

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
