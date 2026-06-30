# HANDOVER_BRIEF.md
# Election Forecast Dashboard — Full Project Context
> Place this file in C:\Users\subho\election-forecast\ 
> Claude Code should read this file at the start of every session

---

## 📌 UPDATE 2026-06-30 — read `CONTEXT.md` FIRST; this brief is the original spec

Several specifics below are now **superseded**. The current source of truth is
**`CONTEXT.md`** (start-here snapshot) + `PROGRESS.md` / `Issues.md`. Key changes since
this brief was written:

- **Status:** Phases 0–6 COMPLETE. **Phase 7 (deploy) IN PROGRESS — backend is LIVE on
  Render → https://election-forecast.onrender.com; frontend (Vercel) PENDING.** Repo:
  github.com/subhojitr-dev/election-forecast (data gitignored). Deploy: `DEPLOY.md`.
- **Election manifest (`api/elections.py`) REPLACED the old `SENATE_BASELINE` dict.** It
  defines, per election, which races + which states + baseline year + real nominees. The UI
  now has an **Election dropdown** + a dynamic **race toggle**, so a real election night shows
  only the contests on that ballot (Nov-2026 = Senate GA/MI/NC/TX, NO President; 2028 = Pres +
  Senate). `baseline_for`/`states_for` are election-aware; sim sessions keyed by (election,race).
- **GA Senate baseline = the Jan-2021 RUNOFF** (Ossoff/Warnock WON; county-level, 159/159,
  exactly certified — Issue #7 resolved). Plus a GA-only **"GA Special"** Warnock race view.
- **Ballot-mode dimension:** `results_live` gained a `mode` column (mail/early/election-day/
  military/all; OPTIONAL, defaults 'all' → graceful fallback). New **County Insight** panel
  (note box + ballot-type selector) + turnout/pending county columns + `mode_breakdown()` +
  `/api/state/{abbr}/county/{cty}` + a synthetic red-mirage test scenario. Highest-leverage
  real-night feature.
- **Live feeds ≠ all Clarity** (`FEED_AUDIT.md`): GA=Clarity statewide; PA/TX/MI=county-level
  Clarity; AZ/NV=own systems; NC=own dashboard (best — has by-voting-method); WI=no statewide
  feed (hardest). ⭐ Consider an **AP Elections API**. Dataverse/MIT is the BASELINE, not a feed.
- **New docs:** DEPLOY · FEED_AUDIT · TESTING · DATA_SETUP · PREP (all in CONTEXT.md doc map).

The architecture, model, panel concepts, and data approach below remain accurate.

---

## 🎯 WHAT WE ARE BUILDING

A real-time election night forecasting dashboard that does three things:

1. BASELINE — Holds historical 2020 precinct-level election results for
   8 states as our reference point (what happened last time, precinct by
   precinct, county by county)

2. LIVE INGESTION — On election night, pulls live results every 60 seconds
   from official state election XML feeds as precincts report in

3. INTELLIGENCE — Compares live results against the 2020 baseline in real
   time and tells you: is this county running ahead or behind 2020? Is the
   Democrat outperforming or underperforming? What does that mean for the
   final result? What is the win probability right now?

Think of it as building our own version of what the New York Times needle
does on election night — but open, transparent, and at the precinct level.

---

## 👤 WHO USES THIS

Someone watching election night results who wants to go DEEPER than just
"Candidate X is leading by Y votes." They want to know:

- Is that lead growing or shrinking as more precincts report?
- Which counties are still outstanding and how many votes are in them?
- Is this state trending the same direction as 2020 or is something
  different happening?
- Based on what we know right now, what is the probability of each
  candidate winning?
- Show me the precinct in Fulton County that just reported — how did it
  compare to last time?

---

## 📊 SCOPE

Target races:    US President + US Senate
Target states:   Georgia, Pennsylvania, Arizona, Nevada, Wisconsin,
                 Michigan, North Carolina + Texas (bonus)
Baseline year:   2020 (closest margins in 30 years, highest turnout
                 in 120 years — best statistical signal at precinct level)
Secondary ref:   2016 (multi-cycle directional trend detection)
Texas context:   James Talarico is the 2026 Democratic Senate nominee
                 challenging Ken Paxton — track this race live on
                 election night November 2026

---

## 🖥️ THE UI — WHAT THE USER SEES

The frontend is a React dashboard with 10 panels:

### Panel 1 — Swing State Strip (top of page)
7 clickable state cards across the top. Each shows:
- State name + Electoral Votes
- Win probability % (Democrat vs Republican)
- % of precincts reporting
- Trend vs 2020 (e.g. "D+1.8 vs 2020" or "R+2.3 vs 2020")
Click a card → drill into that state

### Panel 2 — Race Toggle
Toggle between Presidential and Senate results for the selected state

### Panel 3 — Search Bar
Type any county or precinct name → instantly filter the table below

### Panel 4 — Live Vote Bar
Candidate names, live vote totals, live percentages, margin
Blue/red split bar. Who is leading and by how much.

### Panel 5 — Convergence Tracker Chart
Line chart with two lines:
- SOLID LINE = live Democratic % as precincts report in (updates every 60s)
- DASHED LINE = 2020 baseline Democratic % (flat reference line)
- GAP between lines = convergence or divergence from 2020
- Solid ABOVE dashed → Democrat doing better than 2020
- Solid BELOW dashed → Democrat doing worse than 2020
X-axis = % of precincts reporting | Y-axis = Democratic vote share %

### Panel 6 — Win Probability Gauge
Arc/semicircle gauge:
- Left = Democrat probability (blue), Right = Republican (red)
- Needle at current probability split
- Label: "Lean D" / "Toss-Up" / "Likely R" etc.
- Confidence tier: "Very Early" / "Developing" / "Strong Signal"

### Panel 7 — County Breakdown Table
Sortable table: County | % Reporting | D% Live | D% 2020 | Shift | Votes In
- Shift column color coded: Blue = D gain, Red = R shift
- Click county row → expands to show individual precincts
- Search bar filters in real time

### Panel 8 — County Shift Bar Chart (sidebar)
Horizontal bar chart, one bar per county
Left = Republican shift | Right = Democratic shift from center

### Panel 9 — Watch List (sidebar)
Auto-generated: counties with most votes outstanding + close 2020 margins
Shows estimated votes remaining — highest impact counties flagged

### Panel 10 — Electoral Vote Tracker (sidebar)
Mini scoreboard all 7 swing states
Probability bar + EV count per state. Click to jump to that state.

---

## 📐 INTELLIGENCE LAYER — HOW WE COMPUTE PROBABILITY

### Step 1 — Shift Delta (per precinct)
  shift = live_dem_share - baseline_dem_share_2020
  Positive = Democrat doing better than 2020
  Negative = Democrat doing worse

### Step 2 — County Rollup
  county_shift = weighted average of precinct shifts
  weighted by votes cast (bigger precincts count more)

### Step 3 — Remaining Vote Projection
  votes_remaining = (1 - pct_reporting) × historical_total_votes_2020
  projected_dem_remaining = baseline_dem_share × votes_remaining
  projected_final_dem = votes_in_so_far + projected_dem_remaining

### Step 4 — Bayesian Win Probability
  Prior = 2020 baseline dem share
  < 15% reporting → stay close to prior (too early to trust live data)
  > 80% reporting → mostly live data
  Output = probability 0.0 to 1.0 that Democrat wins

### Confidence Tiers
  < 15% reporting  → "Very Early — Directional Only"
  15% to 40%       → "Early — Lean Forming"
  40% to 70%       → "Developing — Probable"
  70% to 90%       → "Strong Signal"
  > 90%            → "Near Final"

### ⚠️ Red Mirage / Blue Shift Warning
In 2020, in-person votes (more Republican) reported first on election night.
Mail ballots (more Democratic) counted later — sometimes days later.
ALWAYS compare against CERTIFIED FINAL 2020 numbers, not election-night
2020 snapshots. Flag early results with mail ballot warning when < 40% in.

---

## 🗂️ DATA FILES — WHAT EXISTS ON THIS MACHINE

Location: C:\Users\subho\election-forecast\data\raw\

PRESIDENT_precinct_general.csv (~358 MB)
  Path:    data\raw\PRESIDENT_precinct_general.csv
  Source:  MIT Election Data Science Lab, Harvard Dataverse
  DOI:     10.7910/DVN/JXPREB
  Content: Every precinct in all 50 states — Presidential votes Nov 2020
  Format:  One row per candidate per precinct
  Columns: state, county_name, precinct, candidate, party, votes + more
  Our use: Presidential baseline for all 8 states

2020-SENATE-precinct-general.csv (~164 MB)
  Path:    data\raw\2020-SENATE-precinct-general.csv
  Source:  MIT Election Data Science Lab, Harvard Dataverse
  DOI:     10.7910/DVN/ER9XTV
  Content: Every precinct with a Senate race in Nov 2020
  Covers:  GA ✅ AZ ✅ MI ✅ NC ✅ TX ✅ | PA ❌ NV ❌ WI ❌
           (PA/NV/WI had NO 2020 US Senate race — not a data gap)
  Our use: Senate baseline for GA, AZ, MI, NC, TX — PA/NV/WI come
           from the 2024 Senate file (see "Still needed" below)

Codebook + README files are in data\raw\docs\ — READ BEFORE WRITING ETL
  data\raw\docs\2020-precincts-codebook.md  (President + Senate codebooks
                                             are byte-identical)
  data\raw\docs\README-president.md
  data\raw\docs\README-senate.md

LOADED 2026-06-25 (in addition to the 2020 files above):
  2024-PRESIDENT-precinct-general.csv  → secondary reference, all 8 states
  2024-SENATE-precinct-general.csv     → PA, NV, WI (+ AZ, MI, TX)
  2018-SENATE-precinct-general.csv     → TX Cruz–O'Rourke (+ AZ, MI, NV, PA, WI)
  All keyed in baseline.db by election_year + race_type. Senate baseline now
  covers every target state: AZ/MI/TX = 2018+2020+2024; GA/NC = 2020;
  NV/PA/WI = 2018+2024.

Still optional (not downloaded):
  2016 PRESIDENT precinct-level  → only if we want a 3-cycle trend line.
  Source: MIT Election Data Science Lab, Harvard Dataverse.
  Confirmed DOIs (verified 2026-06-25 — 2020 DOIs cross-checked vs this brief):
    2024 PRESIDENT : doi:10.7910/DVN/XDJYKC
    2024 SENATE    : doi:10.7910/DVN/ZCM3BN   (PA + NV + WI)
    2018 SENATE    : doi:10.7910/DVN/DGNAFS   (TX Cruz–O'Rourke)
    2016 PRESIDENT : doi:10.7910/DVN/LYWX3D   (optional, 3-cycle trend)
    2016 SENATE    : doi:10.7910/DVN/NLTQAD   (optional)
    2022 SENATE    : doi:10.7910/DVN/IAD3XR   (superseded by 2024 for our use)
  Download page pattern:
    https://dataverse.harvard.edu/dataset.xhtml?persistentId=<doi>
  Put the precinct CSVs in data\raw\ alongside the 2020 files.
  ETL note: etl_baseline.py keys on election_year + race_type, so loading
  more years/races is additive — no schema change needed.

---

## 🔴 LIVE DATA SOURCES (Election Night)

Most swing states use Clarity Elections software — free public XML feeds:

  Georgia:       https://results.enr.clarityelections.com/GA/{election_id}/
  Pennsylvania:  https://results.enr.clarityelections.com/PA/{election_id}/
  Arizona:       https://results.enr.clarityelections.com/AZ/{election_id}/
  Nevada:        https://results.enr.clarityelections.com/NV/{election_id}/
  Texas:         https://results.enr.clarityelections.com/TX/{election_id}/
  North Carolina: https://er.ncsbe.gov/
  Wisconsin:     Wisconsin SOS direct feed
  Michigan:      Michigan SOS direct feed

{election_id} changes each election — fetch from SOS website before election night
Python library: pip install clarify (github.com/openelections/clarify)
Poll every 60 seconds. Skip if version unchanged since last poll.

---

## 🗄️ DATABASE DESIGN

Engine:   SQLite — single file at data\db\baseline.db
Why:      No server needed, built into Python, zero config, portable

```sql
CREATE TABLE precincts (
  id            TEXT PRIMARY KEY,  -- '{state_abbr}-{county_fips}-{precinct_name}'
  state         TEXT,
  state_abbr    TEXT,
  county        TEXT,
  county_fips   TEXT,
  precinct_name TEXT
);

CREATE TABLE results_historical (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  precinct_id   TEXT,
  election_year INTEGER,
  race_type     TEXT,     -- 'president' | 'senate'
  candidate     TEXT,
  party         TEXT,     -- 'DEM' | 'REP' | 'LIB' | 'GRE' | 'OTH'
  votes         INTEGER,
  vote_share    REAL,     -- 0.0 to 1.0
  FOREIGN KEY (precinct_id) REFERENCES precincts(id)
);

CREATE TABLE results_live (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  precinct_id         TEXT,
  race_type           TEXT,
  candidate           TEXT,
  party               TEXT,
  votes               INTEGER,
  vote_share          REAL,
  precincts_reporting INTEGER,
  total_precincts     INTEGER,
  last_updated        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE county_rollup (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  state         TEXT,
  county        TEXT,
  county_fips   TEXT,
  election_year INTEGER,
  race_type     TEXT,
  dem_votes     INTEGER,
  rep_votes     INTEGER,
  total_votes   INTEGER,
  dem_share     REAL,
  rep_share     REAL
);
```

---

## 🛠️ TECH STACK

  Python + pandas     → ETL (read CSV, filter, load SQLite)
  sqlite3             → database (built into Python, no install)
  clarify             → Clarity ENR XML parser (pip install clarify)
  APScheduler         → background polling every 60s
  FastAPI + uvicorn   → REST API + WebSocket server
  React + Vite        → frontend UI
  Recharts            → charts (line, bar, radial gauge)
  Tailwind CSS        → styling
  axios               → HTTP client in React
  Docker Compose      → deployment (Phase 6)

---

## 📅 6-PHASE BUILD PLAN

> STANDING INSTRUCTION (Claude): when a phase finishes, update its status
> line below to "✅ COMPLETE <date>" so the next session knows where we are.
> Also add a dated entry to PROGRESS.md. Do NOT advance to the next phase
> without the user's explicit go-ahead.

Phase 0  ✅ COMPLETE          Planning + architecture (done in Claude.ai)
Phase 1  ✅ COMPLETE 2026-06-25  ETL — load CSV files into SQLite baseline.db
Phase 2  ✅ COMPLETE 2026-06-25  Live ingestor — Clarity ENR XML poller (60s interval)
Phase 3  ✅ COMPLETE 2026-06-25  Analytics engine — shift delta + Bayesian probability
Phase 4  ✅ COMPLETE 2026-06-25  FastAPI REST API + WebSocket endpoints
Phase 5  ✅ COMPLETE 2026-06-25  React UI — wire all 10 panels to live API
Phase 6  ✅ COMPLETE 2026-06-25  Integration test with archived 2020 election night data
Phase 7  ⬜ Deploy            Public web URL — build React, host API+DB, point a
                             domain (Render/Railway/Fly/VM). NOT yet scoped; gets
                             the dashboard off localhost onto a real https:// URL.

UI prototype with simulated data was built in Claude.ai session.
Reference it when reaching Phase 5 — all 10 panels already laid out.

---

## 📁 FULL FOLDER STRUCTURE

```
C:\Users\subho\election-forecast\
├── data\
│   ├── raw\
│   │   ├── PRESIDENT_precinct_general.csv        ✅ downloaded
│   │   ├── 2020-SENATE-precinct-general.csv      ✅ downloaded
│   │   └── docs\
│   │       ├── 2020-precincts-codebook.md        ✅ downloaded
│   │       ├── README-president.md               ✅ downloaded
│   │       └── README-senate.md                  ✅ downloaded
│   └── db\
│       └── baseline.db                      ← created by ETL (Day 1)
├── ingestor\
│   ├── etl_baseline.py                      ← Day 1
│   └── clarity_poller.py                    ← Day 2
├── analytics\
│   ├── shift_calculator.py                  ← Day 3
│   ├── bayesian_model.py                    ← Day 3
│   └── rollup.py                            ← Day 3
├── api\
│   ├── main.py                              ← Day 4
│   ├── routers\
│   └── models.py
├── ui\                                      ← Day 5 (React + Vite)
├── HANDOVER_BRIEF.md                        ← this file
├── QUICK_REFERENCE.md                       ← at-a-glance cheat sheet
├── KICKOFF_PROMPT.md                        ← session start prompt
└── README.md
```

---

## 🔑 KEY DECISIONS LOG

  Baseline year        2020         Closest margins, highest turnout, best signal
  Secondary ref        2016         Multi-cycle trend detection
  Certified numbers    Yes          Avoid red mirage / blue shift distortion
  Database             SQLite→PG    Zero config dev, scalable prod
  Probability model    Bayesian+    Two models cross-validate each other
                       Shift
  Poll interval        60s          Respectful of Clarity servers
  Texas in scope       Yes          Talarico 2026 Senate — D competitiveness

---

## 📌 QA VERIFICATION TOTALS (Georgia 2020 Presidential — certified)

  Biden  (DEM): 2,473,633 votes
  Trump  (REP): 2,461,854 votes
  Margin:       +11,779 Biden (+0.23%)
  Counties:     159
  Precincts:    ~2,659

Use these numbers to confirm ETL loaded correctly.

---

## 📌 PROJECT INFO

  GitHub:       subhojitr-dev
  Machine:      Windows, C:\Users\subho\
  Python path:  C:\Users\subho\
