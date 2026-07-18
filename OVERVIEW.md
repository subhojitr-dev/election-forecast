# OVERVIEW.md — Election Forecast Dashboard: What Exists, What's Next

A single, current snapshot of the whole project — what's built, what's live, what's
still ahead. `CONTEXT.md` is denser session-continuity notes for picking work back up;
this is the "explain it to someone new" version. Last updated 2026-07-17.

---

## 1. What this is

A real-time election-night forecasting dashboard. It holds certified past election
results as a **baseline** ("what happened last time"), ingests **live results** as
precincts report, and compares live-vs-baseline to project a win probability for each
race — an open, precinct-level version of a TV election needle. Built from scratch this
cycle for the **Nov 3, 2026 midterm**, with an eye toward reusing the same pipeline for
**Nov 2028** (President + a different set of Senate seats).

**Live now:**
| | |
|---|---|
| Dashboard | https://election-forecast-silk.vercel.app |
| API | https://election-forecast.onrender.com (`/api/health`, `/docs`) |
| Source | https://github.com/subhojitr-dev/election-forecast |

---

## 2. Architecture, phase by phase (all ✅ complete)

| Phase | What it is | Where |
|---|---|---|
| 1 — ETL | Load certified precinct-level results (Harvard Dataverse / MIT Election Lab CSVs) into a SQLite baseline | `ingestor/etl_baseline.py` (+ per-state additive loaders, see §4) |
| 2 — Live ingestor | Pull real election-night results and write them in the same shape as the baseline | `ingestor/*_live_feed.py` (one per state, see §5) |
| 3 — Analytics | Per-precinct shift → statewide weighted shift → projection → Bayesian win probability | `analytics/` (`shift_calculator.py`, `bayesian_model.py`, `rollup.py`, `engine.py`) |
| 4 — API | REST + WebSocket serving the above | `api/` (FastAPI) |
| 5 — UI | The dashboard itself | `ui/` (Vite + React + Recharts) |
| 6 — Integration test | Replays all races end-to-end, checks every winner matches reality | `integration_test.py` |
| 7 — Deploy | Public hosting | Vercel (frontend) + Render (backend), see §8 |

**The core trick that makes live results and historical baselines comparable without any
special-casing per state:** every precinct or county is keyed `{STATE}-{FIPS}-{NAME}`
(or, for live data, `{STATE}-{FIPS}-CTY` — a "county-pseudo-precinct"). As long as a
state's baseline and its live feed use the same key, the analytics engine needs **zero
state-specific code** — it just joins on that key. This has now been proven across 7
different real state government systems (open JSON APIs, bulk ZIP downloads, S3 buckets,
classic Clarity, AngularJS/API hybrids) with no changes to `analytics/` or `api/` at all.

---

## 3. What the dashboard actually does (features)

- **Election dropdown** — switches between a historical sandbox (`demo`), past-election
  replays used for testing (`pres2024`, `sen2020/2024/2018`), and the two real upcoming
  elections (`general2026`, `general2028` stub) — each with its own ballot manifest
  (which races, which states, which baseline year, real candidate names) defined in
  `api/elections.py`.
- **President / Senate / "GA Special" race toggle** — only the races actually on the
  selected election's ballot are shown (e.g. the Nov 2026 midterm has no President race).
- **Live vote bar, win-probability gauge, convergence chart** — the core "who's ahead,
  how confident are we" view, updating as more precincts report.
- **County table + shift bars + watch list** — which counties are driving the statewide
  number, and which high-impact counties haven't reported yet.
- **Ballot-mode breakdown ("County Insight")** — where the live feed exposes it
  (currently NC and PA), breaks a county's vote out by mail/early/election-day/
  provisional and explains in plain English whether the outstanding vote likely helps
  or hurts the trailing candidate (the "red mirage → blue shift" story).
- **Simulator ("Next Batch")** — since there's no real 2026 data yet, the dashboard
  replays a real past election in batches (20% → 100%) so every panel can be exercised
  today. On election night this stepper is replaced by the real live-feed poller — same
  data path, same analytics, nothing else changes.
- **`mock_feed.py`** — a synthetic, isolated ('ZZ' pseudo-state) feed for testing edge
  cases the archived elections don't happen to show, e.g. a deliberate red-mirage.

Full usage walkthrough: `DASHBOARD_GUIDE.md`. Step-by-step tests (including how to
validate a state's live feed yourself): `TESTING.md`.

---

## 4. Data coverage — 9 states now, not the original 8

The project started with 8 target swing states. **South Carolina was added 2026-07-17**
as a 9th, because its Senate seat (Graham, Class 2) is up in 2026 too — same class as
Georgia/Michigan/North Carolina/Texas.

| State | President baseline | Senate baseline | Notes |
|---|---|---|---|
| GA | 2020, 2024 | 2020 (unused) + **2021 runoff (used)** | Ossoff won the runoff; that's the seat up in 2026 |
| PA | 2020, 2024 | 2018, 2024 | No 2020 PA Senate race |
| AZ | 2020, 2024 | 2018, 2020, 2024 | 2020 = the Kelly–McSally special |
| NV | 2020, 2024 | 2018, 2024 | No 2020 NV Senate race |
| WI | 2020, 2024 | 2018, 2024 | No 2020 WI Senate race |
| MI | 2020, 2024 | 2018, 2020, 2024 | |
| NC | 2020, 2024 | 2020 | |
| TX | 2020, 2024 | 2018, 2020, 2024 | 2018 = Cruz–O'Rourke |
| **SC** | 2020, 2024 | **2020 only** | Graham vs Harrison — added 2026-07-17, not part of the original 8 |

~77,600 precincts total across all 9 states, ~511,000 historical result rows, ~3,300
county rollups (these numbers shrink over time as more states convert to county-level —
see §5, that's expected, not data loss).

**⚠️ Don't run `ingestor/etl_baseline.py` to add a state or a new year.** It
`os.remove()`s and fully rebuilds `baseline.db` from just its 5 hardcoded sources (the
original 8 states only) — that would destroy every state's live-feed work described in
§5. Adding a new state needs its own small additive loader; `ingestor/etl_sc_baseline.py`
is the template.

**Not yet loaded:** 2022 Senate (needed for the `general2028` stub — the raw CSV is
already downloaded at `data/raw/2022-SENATE-precinct-general.csv`, just not loaded into
`baseline.db` yet).

---

## 5. Live-feed readiness — 7 of 9 states wired, validated to the exact certified result

| State | Live source | Mechanism | Status |
|---|---|---|---|
| **NC** | Own dashboard, open S3 bulk file | plain httpx, live ballot-mode split | ✅ wired |
| **GA** | Enhanced Voting API | plain httpx, totals only | ✅ wired |
| **PA** | Own AngularJS SPA/API | plain httpx, live ballot-mode split, 1 call = all 67 counties | ✅ wired |
| **AZ** | Own open CDN | plain httpx, 1 call = all 15 counties × all races, electionIds pre-published | ✅ wired, **primary-night ready (Jul 21)** |
| **MI** | Own system, Cloudflare-gated | **needs a HEADED browser** (Cloudflare blocks headless) — 1 bulk ZIP = every precinct × every office | ✅ wired, **primary-night ready (Aug 4)** |
| **TX** | Own system, Cloudflare WAF-gated | **headless Playwright is enough** — 1 call = all 254 counties, keyed by FIPS directly | ✅ wired |
| **SC** | Classic Clarity ENR — **the one place it's still alive** | plain httpx, `current_ver.txt` discovery — the simplest state of any wired so far | ✅ wired |
| NV | — | — | ⚪ deprioritized — no Senate/President race on the Nov 2026 ballot (Class 3, next up 2028) |
| WI | No statewide feed exists (72 county clerk sites) | — | ⚪ deprioritized (same reason as NV) — also the one genuinely hard case regardless of timing |

Every wired state was validated against a real archived election (mostly the 2024
general; SC against its own June 2026 primary, the only election reachable on its live
system) — **exact match to certified vote totals**, not just within tolerance.

Clarity is confirmed dead/decommissioned everywhere checked **except SC**. "Clarity is
dead" turned out to be an empirical per-state finding from this project, not a universal
rule — always verify a new state directly rather than assuming.

Full per-state discovery detail: `FEED_AUDIT.md`. Election-night runbook for AZ (Jul 21)
and MI (Aug 4): `CONTEXT.md`. How to run and validate any state's live feed yourself,
with worked examples and every state's specific gotchas: `TESTING.md` §8.

---

## 6. Deployment (as-built)

- **Frontend:** Vercel, auto-deploys on push to `main`.
- **Backend:** Render Docker web service (free tier), auto-deploys on push. On boot,
  fetches `baseline.db` (gzipped) from a **GitHub Release** asset via `DB_URL`.
- **⚠️ Production DB is a static snapshot, not live-synced to your local `baseline.db`.**
  Everything in §4/§5 (SC, all 7 states' live-feed wiring, every county-pseudo baseline)
  is **local only** until someone re-gzips `baseline.db` and uploads it as a new Release
  asset. Not done as of 2026-07-17.
- **Free-tier caveat:** Render spins down after ~15 min idle → ~30–60s cold start on the
  first hit after. Fine for a demo; needs the Starter tier + a persistent disk before
  election night (see §7).

Full steps + gotchas: `DEPLOY.md`.

---

## 7. What's NOT built yet — the roadmap

Roughly in the order it needs to happen:

1. **AZ (Jul 21) and MI (Aug 4) primary-night validation.** Code is done; what's left can
   only happen on the actual nights — confirm the polling mechanics work against real,
   currently-reporting data. Runbook: `CONTEXT.md`.
2. **South Carolina** (SC): its `general2026` electionId isn't published yet
   (`enr-scvotes.org/SC/elections.json` is empty between elections) — needs a check
   closer to the date, same situation as MI.
3. **Production DB republish** — everything built this session is local-only (§6). A
   one-time re-gzip + upload before it matters for real usage.
4. **A real production poller.** Right now each `*_live_feed.py` is a manual one-off
   script. Election night needs these wrapped in a scheduler (a loop hitting each
   state's `ingest(...)` every ~60s) running as a background worker. **MI is the
   complication**: it needs a headed browser, which needs a virtual display (Xvfb) added
   to a Linux host — technically standard (the pattern many CI systems use), but not yet
   built or tested in this project. The other 6 wired states (plain httpx or headless
   Playwright) have no such requirement and could run in a normal serverless/background
   worker today.
5. **Election-ID discovery for the real Nov 2026 general**, per state, ~2 weeks before
   (mid–late Oct), once each state publishes its 0%-reporting page. AZ's ID is stable
   and already known; MI/TX auto-discover; GA/SC need a manual check.
6. **A full dry run** — all wired states × their real Nov 2026 races, against each
   state's live (empty) general-election feed, before the actual night.
7. **Render infra upgrade** — Starter tier + persistent disk, so the DB survives across
   requests during election night instead of re-downloading on every cold start.
8. **Texas, Nevada, Wisconsin, and South Carolina — whichever are still open closer to
   Nov 2028** (President + a different set of Senate classes) — not required for Nov
   2026 but useful to have ahead of time:
   - **NV and WI**, deprioritized for 2026, become live again for `general2028` (both
     have Senate seats up then). WI in particular needs real scoping work first — see
     the WI note in `CONTEXT.md` / `Issues.md` before committing to an approach (likely
     a subset of big counties, not full 72-county coverage).
   - **2022 Senate baseline** needs loading (`general2028` stub currently has no data)
     — the raw file is already on disk.
9. **Precinct-level drill-down (optional precision upgrade, explicitly NOT required).**
   The whole project runs at county granularity by design (a 2026-06-30 decision — county
   FIPS is a clean, stable join; no name-matching/crosswalk needed). If ever revisited for
   extra precision, GA (via Clarity) and NC (via its own dashboard) are the two states
   flagged as easy candidates — everyone else stays county-level permanently.

---

## 8. Doc map

| File | What it's for |
|---|---|
| **OVERVIEW.md** | ← you are here: what exists, what's next |
| `CONTEXT.md` | Dense session-continuity snapshot — start here to resume work |
| `README.md` | How to run the two local servers, deploy, find logs |
| `DASHBOARD_GUIDE.md` | Full panel-by-panel usage walkthrough |
| `TESTING.md` | Step-by-step tests: the simulator (§1–7) AND the real live feeds (§8) |
| `HANDOVER_BRIEF.md` | The original full spec — now partially superseded, see its own update banner |
| `QUICK_REFERENCE.md` | At-a-glance cheat sheet: schema, endpoints, per-state status |
| `DATA_SETUP.md` | Every data file: path, contents, source/DOI |
| `DEPLOY.md` | Deployment steps, caching, scaling, the production-poller plan |
| `FEED_AUDIT.md` | Per-state live-feed discovery detail (the "how we found it" story) |
| `PREP.md` | Election-night readiness timeline + risk register |
| `PROGRESS.md` | Chronological work log — the full "how we got here" |
| `Issues.md` | Known issues, resolutions, and the Nov 3 readiness plan |
