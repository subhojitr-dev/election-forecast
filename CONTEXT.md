# CONTEXT.md — START HERE EACH SESSION
# Election Forecast Dashboard — current-state snapshot
# Last updated: 2026-07-18 (7 states WIRED END-TO-END, all validated + LIVE ON PRODUCTION
#                           (db-v3, deployed); found+fixed a real data bug (MI/TX's 2020
#                           Senate baseline was never county-converted, NC's live data had
#                           been emptied by testing) — all 5 general2026 states now
#                           consistent; built production_poller.py (the real election-night
#                           scheduler) + Dockerfile Xvfb/Chromium for MI; Render UPGRADED TO
#                           STARTER + 1GB persistent disk (/app/data/db); poller wired into
#                           entrypoint.sh but OFF (ENABLE_POLLER unset) — turn on ~Aug 2-3
#                           for the Aug 4 MI primary. See "🗓️ SCHEDULE" below.)

> This is the fast on-ramp. Read this first, then `HANDOVER_BRIEF.md` for the
> full spec. `PROGRESS.md` = chronological log. `Issues.md` = problems + plans.

---

## 🗓️ SCHEDULE — update this as dates come and go

| When | What | Status |
|---|---|---|
| **Jul 21, 2026** | AZ primary — mechanics validation (uploadId/precinct-count/vote changes live). Runbook below. | ⬜ upcoming |
| **~Aug 2–3, 2026** | Set `ENABLE_POLLER=1` + `POLLER_MODE=mi-primary` on Render (Environment tab) — starts the in-process poller checking for MI's Aug 4 election every 90s. Confirm it finds the electionId before the 4th (don't wait until the night itself). | ⬜ upcoming |
| **Aug 4, 2026** | MI primary — the actual live validation. **Result: MI's own state system never worked** (structural — only shows a county once it's 100% done — see PROGRESS.md 2026-08-04). Found and shipped a real fallback live tonight: 3 individual MI county systems (Wayne/TotalVote, Kent/EnhancedVoting, Washtenaw/custom). Combined result: El-Sayed 61.8%, Stevens 34.9%, McMorrow 3.3%. | ✅ done (via fallback, not the original plan) |
| **After Aug 4** | Set `ENABLE_POLLER=0` again (or leave running harmlessly — it'll just sit idle with nothing to poll). Decide whether to keep the Starter subscription through Oct/Nov or downgrade in between (if downgrading: **back up the DB to a new GitHub Release first** — the persistent disk goes away on Free tier). | ⬜ upcoming |
| **Before mid-Oct** | **CONFIRMED 2026-08-05: MI's state system (`mi_live_feed.py`'s source) is NOT viable for Nov 3** — checked 11 hours after Aug 4 polls closed, still an empty file. Not "probably slow," confirmed dead for live purposes. Needs a real replacement plan, not a patch: (1) a calm, unhurried survey of MI's top 10-15 counties for more live-results sources (Aug 4 found 4 by real effort, each on a DIFFERENT vendor — user flagged this patchwork-of-one-offs approach as unsustainable, needs a simpler unified strategy, not more one-off scrapers); (2) follow up on the DDHQ pricing conversation (contacted 2026-08-04, no public pricing — quote-only); (3) research each OTHER tracked state's (GA/NC/TX/SC) own actual most-recent primary night — did their real systems deliver live data, and when did it start flowing — using real evidence, not just policy documentation. See PROGRESS.md 2026-08-04 and 2026-08-05 entries for full context. | ⬜ upcoming |
| **Mid–late Oct 2026** | States publish the real Nov 3 general at 0% reporting. Discover the real electionIds for GA/MI/NC/TX/SC (AZ/PA not tracked this cycle) and fill them into `production_poller.py`'s `build_production_tasks()` (currently mostly `_tbd()` placeholders). Replace MI's "TBD AUG 4" candidate placeholders in `api/elections.py` with the real Aug 4 primary winners. | ⬜ upcoming |
| **~2 weeks before Nov 3** | Full dry run: all 5 tracked states × Senate, against each state's live (empty) Nov feed. `--mode prod --once` is the smoke test. **Critically: this must check TIMELINESS, not just final accuracy** — Aug 4 proved a state can look fine on paper (documented as fast) and still not deliver live data in practice. If any of GA/NC/TX/SC turns out to have MI's problem, the same "hunt down county-level fallbacks" playbook from Aug 4 applies — do it now, not live on election night. | ⬜ upcoming |
| **Election week (late Oct – Nov 2)** | Final rehearsal. Re-subscribe to Starter if it was downgraded. Confirm disk + poller + `ENABLE_POLLER=1`/`POLLER_MODE=prod`. | ⬜ upcoming |
| **Nov 3, 2026** | Election night — go live. | ⬜ upcoming |

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

**MI — Aug 4 primary — RESOLVED 2026-08-05. Aug 4 has passed; this section is
now a post-mortem, kept for what it teaches about Nov 3, not as a live plan.**

**Outcome:** Path A ran correctly (poller live on Render, checking every 90s)
but its target — MI's state system — never delivered. Checked again 11 hours
after polls closed (2026-08-05 ~7 AM ET): election now configured
(`electionId 706`) but the results file is still 0 bytes. **CONFIRMED not
viable for live Nov 3 tracking, not just "was slow that one night."** What
actually worked instead: 4 individual MI county systems, discovered and
wired in live during the night (Wayne/TotalVote, Kent/EnhancedVoting,
Washtenaw/custom HTML, Livingston/PDF) — see PROGRESS.md's 2026-08-04 entry
for the full story, each a genuinely different vendor/format. Flagged by the
user as an unsustainable pattern to repeat 5 states over — Nov 3 needs a
real plan, not more one-off scrapers. That planning is in progress; see
CONTEXT.md's schedule table ("Before mid-Oct" row).

  **Path A (as originally planned — kept for reference, not recommended as-is for Nov 3):**
  - Render is now on **Starter tier** with a **1GB persistent disk mounted at `/app/data/db`**
    (upgraded 2026-07-18 specifically for this). The Dockerfile has Xvfb + Chromium +
    Playwright's OS deps baked in (confirmed working — the build succeeded on Render).
    `entrypoint.sh` optionally launches `production_poller.py` in the background alongside
    uvicorn, in the SAME service (not a separate Render service — Render doesn't let two
    services share one disk anyway, confirmed via the Disk UI: "Other services can't access
    this service's disk").
  - **It's currently OFF** (`ENABLE_POLLER` unset in Render's Environment tab) — deliberately,
    to avoid ~2 weeks of pointless headed-Chromium launches every 90s checking for an election
    that doesn't exist yet (not "respectful" polling, and wastes Starter-tier resources for no
    reason). **Turn it on ~Aug 2–3**: set `ENABLE_POLLER=1` and `POLLER_MODE=mi-primary` in
    Render's Environment tab, save (auto-redeploys). This runs `production_poller.py`'s
    `build_mi_primary_tasks()` — MI only, polling every 90s, auto-discovering the electionId
    from `"8/4/2026"`, writing to a **scratch race_type `mi_primary_2026`** (NOT `senate` —
    writing real Aug 4 primary data under the real race_type would corrupt the already-correct
    `general2026` tracking, the same mistake found & fixed for MI/TX/NC's 2020 baseline this
    session — see PROGRESS.md 2026-07-18).
  - Verify it found the election **before** the night itself (check Render's Logs tab for
    `mi_primary_2026: OK` instead of `NOT FOUND`), so there's no surprise on Aug 4.
  - After Aug 4: set `ENABLE_POLLER=0` again (or leave it — it'll just idle harmlessly with
    nothing new to find until Nov).

  **Path B (fallback / what to do if Path A isn't working): run it manually.**
  - `python ingestor/mi_live_feed.py "8/4/2026" senate mi_primary_2026` from any machine
    with a real display (this machine, or the user's) — auto-discovers the id, prints
    "NOT FOUND, retry closer to the night" until MI configures it. The 2nd arg (`senate`)
    picks the OFFICE (must stay `senate`/`president`, not a scratch name — those are the
    only two OFFICE_CODE keys the script understands); the 3rd arg is the scratch DB
    label the results get stored under, so it can safely be anything (omit it entirely
    and it defaults to the same value as the 2nd arg — i.e. writes to the REAL `senate`
    race_type, which is what you want for Nov 3 itself, just not for a primary-night
    test). Needs `pip install playwright && playwright install chromium` if not already
    done. This only updates the LOCAL database — has no effect on the public site unless
    manually synced (gzip → new GitHub Release → update `DB_URL`, same as `db-v2`/`db-v3`).
  - ⚠️ **This 2-arg-vs-3-arg split was added 2026-07-30** after finding the original
    2-arg scratch-race_type instructions here (and the equivalent poller code) would have
    crashed with `KeyError` — `race_type` used to double as both the office selector AND
    the DB label, so a scratch name like `mi_primary_2026` wasn't valid to pass as the
    2nd arg at all. Fixed in `mi_live_feed.py`'s `ingest()` (new `db_race_type` param)
    and `production_poller.py`'s `build_mi_primary_tasks()`. See PROGRESS.md 2026-07-30.

  ⚠️ **Don't rely on a locally-scheduled wake-up/reminder task to catch this window** —
  tried that for AZ's Jul 21 test (a one-time `mcp__scheduled-tasks__*` trigger set for
  10:30 PM ET) and it silently never fired; the app wasn't open at that moment, and
  scheduled tasks only run while the app is open (or on next launch — but "next launch"
  turned out to be well after the target time here). Ended up just re-running the poll
  commands manually once back at the keyboard, which worked fine. **This does NOT apply
  to Path A above** (the Render-hosted `production_poller.py` running inside the
  always-on Starter-tier web service) — that's a real server-side loop, not a
  locally-scheduled task, so it keeps polling on its own regardless of whether anyone's
  local app is open. See PROGRESS.md's 2026-07-21 entry for the full story.

  - MI Senate IS on the `general2026` manifest already (`api/elections.py` lists MI with
    candidates "TBD AUG 4"). **Once the Aug 4 primary picks the nominees, replace the TBD
    placeholders in `api/elections.py` with the real winner names** — then re-deploy (a
    normal code push, not a DB sync).

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

Reproducible deploy steps + URLs: **DEPLOY.md → "✅ AS-BUILT"**. Starter tier stays up
24/7 (no more cold starts — see below), so this note about free-tier spin-down no longer
applies but is left here as history.

### 🚀 Deployment facts (so you don't re-derive them) — UPDATED 2026-07-18
  - **GitHub:** github.com/subhojitr-dev/election-forecast (branch `main`). Data (CSVs +
    baseline.db, 1.4 GB) is **gitignored** — see DATA_SETUP.md to obtain/rebuild.
  - **Backend:** Render Docker web service, **Starter tier ($7/mo, subscribed 2026-07-18)**
    with a **1GB persistent disk mounted at `/app/data/db`**. Upgraded specifically to
    unlock (a) One-Off Jobs / always-on service (no cold starts) and (b) a disk that
    survives redeploys, which the in-process poller needs (Render confirmed: "Other
    services can't access this service's disk" — that's WHY the poller runs inside this
    same web service rather than as a separate Background Worker).
    - On boot, `entrypoint.sh` → `download_db.py` fetches baseline.db (gzip) from a
      **GitHub Release** — current tag **`db-v3`** (asset `baseline.db.gz`), via the
      `DB_URL` env var, unzips to `/app/data/db/`. (`db-v1` and `db-v2` are now
      superseded — `db-v3` is the one with the MI/TX/NC data-integrity fix, see
      PROGRESS.md 2026-07-18.)
    - **If baseline.db changes:** re-gzip it, upload a NEW release asset (new tag,
      e.g. `db-v4`), update `DB_URL` in Render's Environment tab (triggers auto-redeploy).
    - **The poller** (`ingestor/production_poller.py`) is deployed in the image and
      wired into `entrypoint.sh`, but **currently OFF** — `ENABLE_POLLER` is unset in
      Render's Environment tab. Turn on via `ENABLE_POLLER=1` + `POLLER_MODE=test`
      (or `mi-primary` / `prod`) — see the MI runbook above for the concrete Aug 4 plan.
    - Dockerfile now installs Xvfb + `playwright install --with-deps chromium`, so MI's
      headed-browser requirement works on Render (confirmed: build succeeded, Events
      tab showed green "Deploy live").
  - **Cache-Control** (max-age=15, swr=30) on /api/states + /api/state = the scale lever.
  - **Local dev still works** unchanged (2 terminals, below) — `VITE_API_BASE` unset = relative.

### 📋 PENDING — EXECUTION ORDER — UPDATED 2026-07-18 (full dated timeline in PREP.md
  and the "🗓️ SCHEDULE" table near the top of this file)

  ✅ DONE (as of 2026-07-18):
     - Frontend on Vercel, backend on Render — deployed, CORS locked to the Vercel URL.
     - **7 of 9 states have working, validated live-feed ingestors**: GA, NC, PA, AZ, MI,
       TX, SC — each proven to exactly match certified historical results end-to-end
       (see TESTING.md §8). Only WI and NV lack a live feed (NV has no 2026 race at all,
       so it doesn't matter; WI's Aug 11 primary is the next open item — see below).
     - 9-state data coverage: original 8 (GA/NC/PA/AZ/MI/TX/WI/NV) + **SC added
       2026-07-17** (President 2020/2024 + Senate 2020, county-pseudo, via the additive
       `etl_sc_baseline.py`, NOT the destructive `etl_baseline.py`).
     - `production_poller.py` built and deployed (scheduler wrapping every state's
       `ingest()` call, per-task error isolation, Xvfb auto-start for MI) — currently
       OFF in production (`ENABLE_POLLER` unset), by design (see Deployment facts above).
     - Render upgraded to **Starter tier + 1GB persistent disk** (2026-07-18) —
       always-on (no cold starts), disk survives redeploys, unlocks One-Off Jobs.
     - **Data-integrity bug found & fixed 2026-07-18**: MI/TX's 2020 Senate baseline had
       never been converted to county-pseudo, and `results_live` for MI/TX/NC held
       stale/wrong-election data. Fixed, verified, republished as **`db-v3`** (see
       PROGRESS.md 2026-07-18 for the full story).

  🔜 NEXT UP, in order:
  ① Jul 21, 2026 — AZ primary: pure mechanics test (scratch race_type), no manifest
     change needed — AZ isn't tracked by `general2026` (only `general2028` will use it).
  ② ~Aug 2–3, 2026 — flip `ENABLE_POLLER=1` / `POLLER_MODE=mi-primary` on Render (see MI
     runbook above). Verify in Render's Logs tab that it finds MI's Aug 4 electionId
     BEFORE the night itself.
  ③ Aug 4, 2026 — MI primary: watch the poller write real results under scratch
     race_type `mi_primary_2026`; after, replace the "TBD AUG 4" candidate placeholders
     in `api/elections.py`'s `general2026` with the real nominees (small code push).
  ④ After Aug 4 — decide: let the Starter subscription ride, or pause/resume before the
     ~2-week-out dry run in October (either is fine — prorating a few days doesn't matter).
  ⑤ Aug 11, 2026 — WI primary: WI still has NO live feed built. If pursued, same
     county-pseudo pattern as the other 7 states; otherwise WI stays simulator-only
     (acceptable — WI isn't in `general2026`'s senate list either).
  ⑥ Mid–late Oct, 2026 — the real payoff moment: GA/MI/NC/TX/SC publish their actual
     Nov 3 general-election IDs. Fill these into `production_poller.py`'s
     `build_production_tasks()` (currently all `_tbd()` placeholders) — this is a small,
     mechanical edit once the IDs are known, not new engineering.
  ⑦ ~2 weeks before Nov 3 — full end-to-end dry run against the real (0%-reporting)
     general-election pages, all 5 tracked states.
  ⑧ Election week → Nov 3 — final rehearsal, then flip `ENABLE_POLLER=1` /
     `POLLER_MODE=prod` for the real thing.

  ⚠️ Precinct-level drill-down (GA Clarity + NC dashboard) remains an OPTIONAL future
  precision upgrade, not required for Nov 3 — county-level is proven sufficient.

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
