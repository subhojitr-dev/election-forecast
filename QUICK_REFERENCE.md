# QUICK_REFERENCE.md
# Election Forecast Dashboard — At-a-Glance Cheat Sheet
# Keep this open in a second window while working in Claude Code
# ================================================================

## 📁 Project Root
C:\Users\subho\election-forecast\

## 📂 Key Files
HANDOVER_BRIEF.md              Full context — read this in Claude Code
KICKOFF_PROMPT.md              Paste into Claude Code to start session
QUICK_REFERENCE.md             This file — keep open while working
data\raw\PRESIDENT_precinct_general.csv   341 MB — Presidential 2020
data\raw\SENATE_precinct_general.csv      120 MB — Senate 2020
data\db\baseline.db            SQLite — created by ETL on Day 1

---

## 🗺️ Target States
Georgia, Pennsylvania, Arizona, Nevada, Wisconsin, Michigan,
North Carolina, Texas (Talarico 2026 bonus)
+ **South Carolina** (added 2026-07-17 — a 9th state, NOT part of the original 8; Graham's
Class-2 Senate seat is up in 2026 too. Scoped to `general2026` only, not the `demo`/ALL8 set.)

## 🗳️ Target Races
US President + US Senate

## 📅 Baseline Year
2020 certified final results (NOT election-night numbers)

---

## 📥 Harvard Dataverse Downloads (all LOADED unless noted)

| File | DOI | Status |
|---|---|---|
| President 2020 precinct | 10.7910/DVN/JXPREB | ✅ Loaded |
| Senate 2020 precinct | 10.7910/DVN/ER9XTV | ✅ Loaded |
| President 2024 precinct | 10.7910/DVN/XDJYKC | ✅ Loaded |
| Senate 2024 precinct | 10.7910/DVN/ZCM3BN | ✅ Loaded (PA/NV/WI) |
| Senate 2018 precinct | 10.7910/DVN/DGNAFS | ✅ Loaded (TX Cruz–Beto) |
| President 2016 precinct | 10.7910/DVN/LYWX3D | ⬜ Optional (3-cycle trend) |

Page pattern: https://dataverse.harvard.edu/dataset.xhtml?persistentId=<doi>
Files live in data\raw\ ; codebook/READMEs in data\raw\docs\

---

## 🗓️ Senate Baseline Coverage (after Phase 1b — all loaded)

| State | Years available | Note |
|---|---|---|
| AZ | 2018 + 2020 + 2024 | 2020 = special (Kelly–McSally) |
| MI | 2018 + 2020 + 2024 | |
| TX | 2018 + 2020 + 2024 | 2018 = Cruz–O'Rourke baseline |
| GA | 2020 | 2020 = regular (Ossoff–Perdue) |
| NC | 2020 | |
| NV | 2018 + 2024 | NO 2020 Senate race |
| PA | 2018 + 2024 | NO 2020 Senate race |
| WI | 2018 + 2024 | NO 2020 Senate race |
| SC | 2020 only | Graham–Harrison (Class-2 seat up again 2026); loaded 2026-07-17 via `etl_sc_baseline.py`, NOT the original `etl_baseline.py` |

---

## 🗄️ Database Schema (SQLite — data\db\baseline.db)

```sql
TABLE precincts
  id TEXT PK          -- 'GA-13121-Precinct01A'
  state TEXT
  state_abbr TEXT
  county TEXT
  county_fips TEXT
  precinct_name TEXT

TABLE results_historical
  id INTEGER PK
  precinct_id TEXT FK
  election_year INTEGER
  race_type TEXT       -- 'president' | 'senate'
  candidate TEXT
  party TEXT           -- 'DEM' | 'REP' | 'LIB' | 'GRE' | 'OTH'
  votes INTEGER
  vote_share REAL      -- 0.0 to 1.0

TABLE results_live
  id INTEGER PK
  precinct_id TEXT
  race_type TEXT
  candidate TEXT
  party TEXT
  votes INTEGER
  vote_share REAL
  precincts_reporting INTEGER
  total_precincts INTEGER
  mode TEXT            -- election_day|early|mail|military|all (ballot-mode dim; default 'all')
  last_updated TIMESTAMP

TABLE county_rollup
  id INTEGER PK
  state TEXT
  county TEXT
  county_fips TEXT
  election_year INTEGER
  race_type TEXT
  dem_votes INTEGER
  rep_votes INTEGER
  total_votes INTEGER
  dem_share REAL
  rep_share REAL

TABLE live_snapshots          -- per-poll statewide time-series (powers the convergence chart)
  id INTEGER PK
  captured_at TIMESTAMP
  state TEXT
  race_type TEXT
  baseline_year INTEGER
  pct_reporting REAL
  dem_votes / rep_votes / total_votes INTEGER
  dem_share_2pty / statewide_shift / projected_dem_share / win_prob_dem REAL
  confidence_tier TEXT
```

GA Senate also stores election_year=2021 (the Jan runoff, county-level pseudo-precincts
"GA-{fips}-CTY"): race_type 'senate' (Ossoff/Perdue) + 'senate_special' (Warnock/Loeffler).

---

## 🔴 Live Data — per-state ENR systems (Election Night) — see FEED_AUDIT.md
## Updated 2026-07-17 — Clarity is DEAD for every state checked EXCEPT SC (still alive there).

  ✅ NC:  WIRED — own dashboard, open S3 bulk file, er.ncsbe.gov (nc_live_feed.py). Live
          ballot-mode split (election_day/early/mail/provisional). 100 counties.
  ✅ GA:  WIRED — Enhanced Voting API, results.sos.ga.gov (ga_live_feed.py). Totals only
          (mode='all'). 159 counties.
  ✅ PA:  WIRED — own AngularJS SPA/API, electionreturns.pa.gov (pa_live_feed.py). Live
          ballot-mode split. ONE call returns all 67 counties.
  ✅ AZ:  WIRED — own CDN, cdn1.arizona.vote (az_live_feed.py). Totals only. ONE call
          returns all 15 counties x all races. electionIds pre-published & stable.
          PRIMARY-NIGHT READY for Jul 21 (no President/Senate race on AZ's own 2026
          ballot — mechanics smoke test only, using Governor).
  ✅ MI:  WIRED — own system, mvic.sos.state.mi.us (mi_live_feed.py, via Playwright).
          Cloudflare blocks headless AND plain httpx — needs a HEADED browser. ONE bulk
          ZIP (GetPrecinctResultsFile) = every precinct x every office statewide.
          electionId auto-discovered (NOT pre-published like AZ's). PRIMARY-NIGHT READY
          for Aug 4 — MUST run from a machine with a real display.
  ✅ TX:  WIRED — own system, results.texas-election.com (tx_live_feed.py). Cloudflare WAF
          blocks plain httpx, but HEADLESS Playwright passes (no display needed, unlike
          MI). ONE call (County.json) = all 254 counties x all races, keyed by 5-digit
          county FIPS directly — no name-matching at all.
  ✅ SC:  WIRED — NEW 9th state (2026-07-17, not one of the original 8; baseline loaded
          from scratch via etl_sc_baseline.py). enr-scvotes.org — the ONE state where the
          classic Clarity mechanism (current_ver.txt) is still alive, plain httpx, no
          Cloudflare/WAF/Playwright at all. ONE call (ALL.json) = all 46 counties x all
          contests (⚠️ excludes a pseudo-county literally named "-1"). Validated against
          the real June 2026 primary — exact match. Real nominees in manifest: Graham (R)
          vs Andrews (D). Nov 2026 electionId not yet known (discover closer to the night).
  ⚪ NV:  DEPRIORITIZED — no Senate/President race on NV's Nov 2026 ballot (Class 3 seat,
          next up 2028). Revisit for general2028 prep.
  ⚪ WI:  DEPRIORITIZED — same reason as NV (Class 3, 2028) — ALSO the hardest case (NO
          statewide feed, 72 county clerk sites). AP Elections API priced project-wide AND
          re-checked WI-specific (2026-07-17) — still quote-only, no shortcut found.

All 7 wired states validated to the EXACT certified/real result (6 vs the 2024 general;
SC vs its own June 2026 primary). Every `*_live_feed.py` maps to county-pseudo-precincts
`{ST}-{fips}-CTY` so the analytics run unchanged.
Dataverse/MIT is the historical BASELINE, NOT a live feed.
Before committing build time to a state, check it actually has a race on the CURRENT
election's manifest (`api/elections.py`) — NV/WI didn't, which cost nothing to check.

⚠️ **`ingestor/etl_baseline.py` is DESTRUCTIVE** — it drops and rebuilds baseline.db from
scratch using only its 5 hardcoded sources for the original 8 states. NEVER run it to add
a state or a year; it would wipe every live-feed county-pseudo baseline built up above.
Adding a state (like SC) needs its OWN small additive loader instead
(`etl_sc_baseline.py` is the template) — and requires adding `EV`/`STATE_NAMES` entries in
`api/main.py` too (the states endpoint crashes on a missing EV entry, not just cosmetic).

⚠️ **Production DB is a static release snapshot** (GitHub Release `db-v1`, gzip'd) — local
changes (SC, all the county-pseudo work) don't reach the live Vercel/Render site until
someone re-gzips baseline.db and uploads a new release asset (see DEPLOY.md). Not done yet.

---

## 🛠️ Tech Stack & Install Commands

  pip install pandas
  pip install clarify
  pip install apscheduler
  pip install fastapi uvicorn
  npm create vite@latest ui -- --template react
  npm install recharts tailwindcss axios

---

## 📅 Phase Status  (see CONTEXT.md for the live snapshot)

  Phases 0–6  ✅ COMPLETE   Planning · ETL · poller · analytics · API/WS · React UI · integration test
  Phase 7     🔄 IN PROGRESS  Deploy — BACKEND LIVE on Render; frontend (Vercel) PENDING

## 🚀 Deployment (2026-06)
  Backend (live):  https://election-forecast.onrender.com   (Render Docker, free tier)
  Frontend:        Vercel — PENDING (Root Directory=ui, env VITE_API_BASE=<render URL>)
  GitHub:          github.com/subhojitr-dev/election-forecast  (data gitignored)
  DB on host:      baseline.db gzipped (43 MB) as GitHub Release tag db-v1; entrypoint.sh
                   + download_db.py fetch it via DB_URL env var on boot. See DEPLOY.md.

## 🗳️ Election manifest (api/elections.py — replaces old SENATE_BASELINE)
  Per-election: which races, which states, baseline year, real nominees. 7 elections:
  demo (all races) · pres2024 · sen2020 · sen2024 · sen2018 (historical replays) ·
  general2026 (Senate GA/MI/NC/TX, real nominees, NO President) · general2028 (stub).
  UI has an Election dropdown + dynamic race toggle (real night shows only ballot races).

Integration test:  python integration_test.py   (all 16 races converge + correct winner)
Simulator API:  /api/sim/{reset,next,status} · /api/scenarios   (all take ?election= &race=)

API run (local):  uvicorn api.main:app --port 8000   (docs at /docs)
  /api/elections · /api/states?race=&election= · /api/state/{abbr}?race=&election=
  /api/state/{abbr}/county/{cty}  (county note + ballot-mode breakdown) · /api/state/{abbr}/series · ws /ws
UI run:   cd ui && npm run dev   → http://localhost:5173  (needs API running)

---

## 📌 QA Check Values (Georgia 2020 Presidential — certified)

  Biden  2,473,633 votes
  Trump  2,461,854 votes
  Margin +11,779 Biden (+0.23%)
  Counties  159
  Precincts ~2,659

---

## ⚠️ Critical Watch-Outs

  RED MIRAGE    In-person (R-leaning) reports first on election night
                Mail ballots (D-leaning) counted later → looks R early
                Use CERTIFIED 2020 totals, not 2020 election-night snapshot

  BLUE SHIFT    Results shift Democratic as mail ballots counted
                Flag "mail ballots outstanding" when < 40% reporting

  PRECINCT IDs  Some precincts renamed after 2020 redistricting
                Use county FIPS as fallback join key if name mismatch

  ELECTION IDS  Changes each cycle; AZ's are pre-published & stable, others (MI, and
                whatever TX/NV turn out to be) must be re-discovered close to the night

  2022 SENATE   Not yet loaded — needed for the general2028 stub (Class-3 seats).
                DOI 10.7910/DVN/IAD3XR. NV/PA/WI had no 2020 Senate (use 2018/2024).

---

## 🔑 Key Decisions

  Baseline year    2020 — closest margins, highest turnout, best signal
  Certified data   Yes — never use election-night 2020 as baseline
  Database         SQLite (dev) → PostgreSQL (prod)
  Models           Bayesian update + Shift extrapolation (two = safer)
  Poll rate        60s — respectful to Clarity servers
  Texas            In scope — Talarico 2026 Senate vs Ken Paxton
