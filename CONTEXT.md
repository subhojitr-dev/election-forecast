# CONTEXT.md — START HERE EACH SESSION
# Election Forecast Dashboard — current-state snapshot
# Last updated: 2026-07-17 (LIVE-READINESS underway — CORS locked; NC+GA+PA+AZ+MI+TX+SC
#                           WIRED END-TO-END (7 live states — SC is a NEW 9th state, not
#                           one of the original 8, baseline loaded from scratch); AZ + MI
#                           primary-night-ready for Jul 21 / Aug 4; NV+WI DEPRIORITIZED (no
#                           2026 race); Clarity confirmed dead everywhere but SC (still alive
#                           there); plan: WI (2028 prep) whenever there's spare runway)

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

**Status: 7 states WIRED END-TO-END + validated (6 of the original 8, PLUS SC as a NEW 9th
state); NV + WI DEPRIORITIZED (see below).** Dashboard is deployed/public;
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
  - ✅ **PA** — own system at electionreturns.pa.gov (NOT Clarity/Enhanced Voting; an
    AngularJS SPA over an open ASP.NET API — `pa_live_feed.py` + `etl_pa_county_baseline.py`).
    Plain httpx works (no Incapsula block on the API paths). One `GetCountyBreak` call
    returns ALL 67 counties for a race (no per-county loop, simpler than GA). **Has live
    ballot-mode split** (election-day/mail/provisional — no early in-person in PA).
    Validated vs the 2024 general (President + Senate, both on one ballot) — exact match
    to certified for both races, 67/67 counties.
  - ✅ **AZ** — own system at results.arizona.vote (Cloudflare SPA) / open CDN
    `cdn1.arizona.vote` (`az_live_feed.py` + `etl_az_county_baseline.py`). Plain httpx
    works on the CDN (no Cloudflare there — only the SPA page has it, and we don't need
    the page). ONE call (`all_county_races_{eid}_{jid}_en_{uploadId}.json`) returns ALL 15
    counties x ALL races in one shot. Totals only, mode='all'. Election IDs are STABLE and
    already published (`az_election_ids()`) — **2026 primary = electionId 68**, confirmed
    live right now (0% reporting, 4 days out). Validated vs the 2024 general (President +
    Senate) — exact match to certified, 15/15 counties. **Primary-night mechanics smoke-
    tested against the live electionId 68 structure** (uploadId discovery, county mapping,
    primary-style party parsing via ContestName suffix all confirmed working at 0%).
  - ✅ **TX** — own system at results.texas-election.com (Angular SPA; a Cloudflare WAF rule
    blocks plain httpx outright — "Attention Required!", not a JS challenge — but
    Playwright passes, and **headless is enough** here, unlike MI) (`tx_live_feed.py` +
    `etl_tx_county_baseline.py`). ONE call (`County.json`) returns ALL 254 counties x ALL
    races, keyed directly by **5-digit county FIPS** ("48001") — no name-matching needed at
    all, the simplest join of any state so far. Totals only, mode='all'. electionId is
    auto-discovered from `ElectionConstants_404.json`'s year+type lookup (not hardcoded).
    Validated vs the 2024 general (President + Senate) — exact match to certified,
    254/254 counties.
  - ✅ **MI** — own system at mvic.sos.state.mi.us. Cloudflare blocks headless browsers AND
    plain httpx (403 on every request) — **but a HEADED Chromium with `navigator.webdriver`
    masked passes clean** (`mi_live_feed.py` + `etl_mi_county_baseline.py`, via Playwright).
    Found a MUCH better mechanism than per-county drilling: `/VoteHistory/
    GetPrecinctResultsFile?electionId={N}` returns ONE bulk ZIP with every precinct x every
    office statewide (tab-delimited, documented in the zip's own readme.txt) — same shape
    as NC's bulk file. We aggregate precinct rows to county totals ourselves. Election IDs
    are NOT pre-published (unlike AZ) — the script re-discovers the id each run by scanning
    the `#ElectionDateId` dropdown for the target date; **as of 2026-07-17 the Aug 4, 2026
    primary is NOT in that dropdown yet** (confirmed — script correctly reports "not found,
    retry closer to the night" rather than crashing). Validated vs the 2024 general
    (President + Senate) — exact match to certified, 83/83 counties.
  - ✅ **SC** — a NEW 9th state (not one of the original 8 — had ZERO data loaded before
    this). Added because SC's Senate seat (Graham, Class 2) IS up in 2026, same class as
    GA/MI/NC/TX. Loaded baseline data from scratch via `etl_sc_baseline.py` (president
    2020/2024 + senate 2020 Graham-vs-Harrison, additively — **NEVER run the original
    `etl_baseline.py` to add a state, it DROPS AND REBUILDS the whole DB from just its 5
    hardcoded sources**), then `etl_sc_county_baseline.py` for the county-pseudo senate
    2020 baseline. Live feed: `sc_live_feed.py` — SC runs the OLD classic Clarity ENR
    (enr-scvotes.org) and, unlike every other state, **it's still fully alive and open**
    (plain httpx, `current_ver.txt` discovery exactly like the pre-2026 Clarity docs
    describe, no Cloudflare/WAF/Playwright at all — the simplest state wired so far). ONE
    call (`ALL.json`) returns every county x every contest (⚠️ one county entry is the
    literal string `"-1"` — a pseudo-county/statewide rollup row that must be excluded or
    every total doubles). electionId is NOT pre-published (SC's `elections.json` is empty
    between elections) — discover via browser close to the night, same as MI. Validated
    against the real June 12, 2026 SC primary (only archived election reachable on their
    live system) — exact statewide AND per-candidate match for both Senate primaries
    (Graham 264,091 R; Andrews 226,075 D). Ran the full analytics pipeline against a
    synthetic Graham-vs-Andrews combination (mechanics only, cleaned up after) — 46/46
    counties, correct shift/win-prob. **Real 2026 nominees now in the manifest**: Graham
    (R, incumbent) vs Andrews (D) — both confirmed from the June primary results.
    Added SC to `api/main.py`'s `EV` (9) + `STATE_NAMES` dicts (required — the states
    endpoint sums EV unconditionally and would crash with a `None` otherwise). Verified
    live against the actual running API: `/api/states?race=senate&election=general2026`
    shows SC correctly at 0% reporting (real pre-election state), no crash.

**⚠️ NV and WI are DEPRIORITIZED — neither has a race on the Nov 3, 2026 ballot.**
Checked directly against `api/elections.py`: `general2026` races = `{"senate": ["GA",
"MI", "NC", "TX"]}` — NV's Senate seat is Class 3 (next up 2028, same class as WI/PA/AZ),
and there's no President race in a midterm year at all. So NV (like WI) has NOTHING to
track for THIS November — it only matters for `general2028`. Not "never needed," just not
urgent: no live primary/test window is forcing the issue the way Jul 21/Aug 4 do for
AZ/MI. (AP Elections API re-checked for WI specifically per user request — still
quote-only, no public pricing tier found; no free workaround found either via a public
news-aggregator JSON endpoint.)

**THE PLAN (in order):**
  1. **WI** — hardest (no statewide feed; 72 county sites). Not urgent (see above) — revisit
     with more runway before 2028. If picked up anyway, Aug 11 primary is a free test window.
  2. **NV** — not urgent (see above); revisit for `general2028` prep whenever convenient.
  - **AZ**, **MI**, **TX**, and **SC** are now code-complete. AZ/MI are additionally
    primary-night-ready — see the runbook below. What's LEFT for AZ/MI is just VALIDATION
    against real live data on the actual night (Jul 21 / Aug 4), which can only happen then.
    SC has nothing left to validate against (already matched real primary data exactly) —
    just needs its Nov 2026 electionId discovered whenever SC configures the general.

### 🗓️ ELECTION-NIGHT RUNBOOK — AZ (Jul 21) and MI (Aug 4)

**AZ — Jul 21 primary:**
  - electionId is already known: **68** (jurisdictionId 0). No discovery needed.
  - AZ's 2026 primary has NO President/Senate race (Senate is Class 3, next up 2028;
    matches `api/elections.py`) — the marquee statewide race is **Governor**. So Jul 21 is
    a MECHANICS validation (does polling correctly pick up new uploadIds / rising
    PrecinctsReported / moving vote totals in real time), not a manifest data load.
  - Run repeatedly through the night (e.g. every few minutes):
    `python ingestor/az_live_feed.py 68 0 "Governor (DEM)" az_primary_test`
    `python ingestor/az_live_feed.py 68 0 "Governor (REP)" az_primary_test`
    (race_type is a scratch value — never appears in any election manifest, so it can't
    leak into the UI; inspect via `sqlite3 data/db/baseline.db "SELECT * FROM results_live
    WHERE race_type='az_primary_test'"`.) Watch for: uploadId incrementing, PrecinctsReported
    climbing from 0, vote totals moving. Clean up the test rows afterward (`DELETE FROM
    results_live WHERE race_type='az_primary_test'`) — they're not a tracked race.

**MI — Aug 4 primary:**
  - electionId is NOT yet known — MI hasn't added it to `#ElectionDateId` as of 2026-07-17.
  - **Days before Aug 4:** re-run `python ingestor/mi_live_feed.py "8/4/2026" senate`
    periodically — it auto-discovers the id once MI configures it and will print it (or
    "NOT FOUND, retry closer to the night" until then). Once it succeeds, the id is stable
    for the rest of the night.
  - MI Senate IS on the `general2026` manifest already (`api/elections.py` lists MI with
    candidates "TBD AUG 4" — confirmed via web search that U.S. Senate is on MI's 2026
    primary ballot). **Once the Aug 4 primary picks the nominees, replace the TBD
    placeholders in `api/elections.py` with the real winner names.**
  - Needs a **headed** browser (a machine with a real display) — this will NOT run
    headless on a CI box or the Render server. Run it locally from a machine you can see,
    or over RDP/VNC with a real desktop session (not purely SSH).
  - `pip install playwright && playwright install chromium` if not already done on the
    machine you run it from.

**Playwright**: used for (a) one-time DISCOVERY of hidden data endpoints on JS/SPA sites
(GA, PA, AZ — all now use plain httpx after that one-time discovery) and (b) ONGOING
Cloudflare bypass where the data endpoint itself is locked — **MI and TX are the only
states that need it at runtime** (MI needs headed; TX works headless). NC/GA/PA/AZ/SC are
plain httpx only, no browser dependency at all. **Clarity ENR is DEAD everywhere we've
checked EXCEPT SC** — SC's `enr-scvotes.org` is the one place the classic Clarity mechanism
(current_ver.txt discovery) is still fully alive and open; don't assume it's dead there
just because it is for GA/PA/AZ.

**⚠️ Production DB is a static snapshot — SC (and anything else added locally) won't
appear on the live Vercel/Render site until baseline.db is re-gzipped and re-uploaded as a
new GitHub Release asset** (see "Deployment facts" below / DEPLOY.md). Nothing in this
session touched that release — SC is local-only for now.

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
**DB state:** ALL 8 original states populated for BOTH races, **PLUS SC (2026-07-17, a
NEW 9th state — president 2020/2024 + senate 2020 only, added via `etl_sc_baseline.py`,
NOT the original `etl_baseline.py`)**. Winners match reality. GA Senate baseline = Jan-2021
RUNOFF (county-level, **now 159/159 counties, exactly certified: Ossoff 50.61% / Warnock
51.04%** after Issue #7 estimate-fill — RESOLVED).
**Baselines + which races are on each ballot now come from the ELECTION MANIFEST
`api/elections.py`** (not the old SENATE_BASELINE dict). 7 elections: demo (all races,
still the original 8 — SC NOT added to `ALL8`/demo, only to `general2026` specifically),
pres2024 / sen2020 / sen2024 / sen2018 (historical replays), general2026 (Senate
GA/MI/NC/TX/**SC** with REAL nominees — Ossoff/Collins, Cooper/Whatley, Talarico/Paxton,
Graham/Andrews, MI TBD), general2028 (stub — needs 2022 Senate data, which IS already on
disk at `data/raw/2022-SENATE-precinct-general.csv`, just not loaded yet). The UI has an
**Election dropdown** + a dynamic **race toggle** (only races on that ballot show).
Re-populate any race: python analytics/engine.py <ST> <race> <year> [swing] [noise]
(API has no --reload here; restart uvicorn after editing api/ code.)
⚠️ **Never run `python ingestor/etl_baseline.py` to add a state or a year** — it
`os.remove()`s baseline.db and rebuilds it FROM SCRATCH using only its 5 hardcoded
SOURCES, which would destroy every live-feed county-pseudo baseline (NC/GA/PA/AZ/MI/TX/SC)
and SC's whole existence. Use a dedicated additive script instead (see `etl_sc_baseline.py`
for the pattern if adding another new state).

---

## ✅ WHAT'S BUILT AND WORKING

**Database** — `data\db\baseline.db` (SQLite). 5 baselines loaded, QA-passed, for the
original 8 states, **PLUS SC's president 2020/2024 + senate 2020 (2026-07-17)**:
  - President: 2020 + 2024 (original 8 states + SC)
  - Senate: 2018, 2020, 2024 (coverage per state below; SC = 2020 only)
  - 72,992+3,864 precincts · 771,198+37,885 historical rows · 3,161+184 county rollups
    (original 8 + SC added separately — see `etl_sc_baseline.py`)
  - `results_live` + `live_snapshots` currently hold the TRUE 100% replay for
    the original 8 states × both races (left by integration_test.py). Re-runnable.
    SC has NO results_live yet (correct — real pre-election state; its 2026 electionId
    isn't published, see the live-feed section above).

**ETL** — `ingestor/etl_baseline.py` (re-runnable for the ORIGINAL 8 states + their 5
hardcoded year/race sources; **DESTRUCTIVE** — drops+rebuilds the whole DB, see the
warning above). New states (like SC) get their OWN small additive script instead.

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

## 🗳️ SENATE BASELINE COVERAGE (after Phase 1b; SC added 2026-07-17)
  AZ, MI, TX  → 2018 + 2020 + 2024
  GA, NC      → 2020   (GA also has 2021; see below)
  NV, PA, WI  → 2018 + 2024   (PA/NV/WI had NO 2020 Senate race)
  SC          → 2020 only (Graham vs Harrison — the Class-2 seat up again in 2026;
    SC had NO 2018/2024 Senate race, same pattern as NV/PA/WI having no 2020 race)
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
