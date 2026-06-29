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
```

---

## 🔴 Live Data — Clarity ENR Feeds (Election Night)

  GA:  https://results.enr.clarityelections.com/GA/{id}/
  PA:  https://results.enr.clarityelections.com/PA/{id}/
  AZ:  https://results.enr.clarityelections.com/AZ/{id}/
  NV:  https://results.enr.clarityelections.com/NV/{id}/
  TX:  https://results.enr.clarityelections.com/TX/{id}/
  NC:  https://er.ncsbe.gov/
  WI:  Wisconsin SOS direct feed
  MI:  Michigan SOS direct feed

Clarify library:  pip install clarify
Poll interval:    60 seconds
Version check:    Always fetch current_ver.txt first

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

  Phase 0  ✅ COMPLETE   Planning (Claude.ai)
  Phase 1  ✅ COMPLETE   ETL — CSV → SQLite baseline.db (multi-year)
  Phase 2  ✅ COMPLETE   Clarity ENR live poller (+ replay + mock)
  Phase 3  ✅ COMPLETE   Analytics — shift + projection + snapshot history + Bayesian
  Phase 4  ✅ COMPLETE   FastAPI REST API + WebSocket
  Phase 5  ✅ COMPLETE   React UI — 10 panels (Vite + Recharts)
  Phase 6  ✅ COMPLETE   Integration test + Next-Batch simulator
  Phase 7  ⬜ NEXT       Deploy — public web URL

Integration test:  python integration_test.py   (all 8 states x 2 races)
Simulator API:  /api/sim/reset · /api/sim/next · /api/sim/status · /api/scenarios

API run:  uvicorn api.main:app --reload --port 8000   (docs at /docs)
  /api/states?race=president · /api/state/{abbr}?race= · /api/state/{abbr}/series · ws /ws
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

  NV + WI       No 2020 Senate data — need 2022 file from Dataverse

---

## 🔑 Key Decisions

  Baseline year    2020 — closest margins, highest turnout, best signal
  Certified data   Yes — never use election-night 2020 as baseline
  Database         SQLite (dev) → PostgreSQL (prod)
  Models           Bayesian update + Shift extrapolation (two = safer)
  Poll rate        60s — respectful to Clarity servers
  Texas            In scope — Talarico 2026 Senate vs Ken Paxton
