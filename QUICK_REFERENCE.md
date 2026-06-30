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

  GA:  Clarity, STATEWIDE   results.enr.clarityelections.com/GA/{id}/   (parser built; mode cols ✓)
  PA:  Clarity, COUNTY-by-county   .../PA/{county}/{id}/   (per-county discovery)
  TX:  Clarity, COUNTY-by-county   .../TX/{county}/{id}/   (per-county discovery)
  MI:  Clarity (counties) + MI SoS   .../MI/{county}/{id}/
  AZ:  OWN — results.arizona.vote   (statewide; confirm live mode)
  NV:  OWN — Results.NV.gov / nvsos.gov/electionresults   (statewide)
  NC:  OWN — er.ncsbe.gov   (dashboard WITH "by voting method" — best/easiest)
  WI:  ⚠️ NO statewide feed — 72 county clerk sites, AP-aggregated (HARDEST)

⭐ Consider an AP Elections API (uniform across all 8 + likely mode splits) — FEED_AUDIT.md.
Dataverse/MIT is the historical BASELINE, NOT a live feed. Clarify lib: pip install clarify.
Poll interval 60s · fetch current_ver.txt first · election_id changes each cycle (mid-late Oct).

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

  CLARITY IDs   election_id changes each election cycle
                Fetch from SOS website fresh before every election night

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
