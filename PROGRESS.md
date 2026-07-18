# PROGRESS LOG — Election Forecast Dashboard

Running log of work, decisions, and open items. **Newest entry on top.**
See `HANDOVER_BRIEF.md` for full project context.

---

## 2026-07-17 (cont.) — TESTING.md §8 added (live-feed test guide); correction: GA's BOTH
## Jan-2021 Senate runoffs ARE fetchable live after all

Added a new TESTING.md section (§8) covering how to run and validate the real
`*_live_feed.py` scripts (distinct from the existing §1–7 simulator tests) — a GA
walkthrough as the template, a per-state quick-reference table, state-specific gotchas,
the AZ/MI primary-night mechanics tests, and what changes for Nov 3. Also created
`OVERVIEW.md` — a new single-document summary of what's built + what's still planned,
linked from README.md's doc table.

While writing §8, testing every documented command against the live API caught two real
bugs before publishing: (1) GA's originally-drafted Senate test command used a contest
name ("US Senate") that doesn't exist on the 2024 ballot at all — GA had NO Senate race
in the Nov 2024 general (Ossoff's seat is 2026, Warnock's was 2022); (2) both AZ's and
SC's primary-mechanics test commands reused the SAME scratch `race_type` for two
different candidates/parties, but each script's internal `DELETE` is scoped to that
name — the second call would have silently wiped the first call's rows. Fixed all three.

**First attempt at fixing (1) undersold GA**, framing Senate as "mechanism-test only"
(no real baseline match available) using the 2022 Warnock-vs-Walker general as a
stand-in. **User caught this as wrong** — GA actually had TWO Senate runoffs in Jan 2021
(the regular Ossoff-vs-Perdue seat AND the special Warnock-vs-Loeffler seat, same day),
and asked whether both could be included. Re-searched GA's Enhanced Voting system
properly this time (via `results.sos.ga.gov`'s own election-history page, not just
guessing URLs) and found both runoffs ARE archived together under one election ID,
`2021JanFedRun` — a single call returns both contests (`"US Senate (Perdue)"` and
`"US Senate (Loeffler) - Special"`). Fetched both: Ossoff 2,269,923 D / Perdue 2,214,979
R, and Warnock 2,289,113 D / Loeffler 2,195,841 R — **exact match** to the certified
baselines already loaded (via `etl_ga_runoff_2021.py`, back on 2026-06-28/2026-07-06).
Rewrote TESTING.md's GA walkthrough to test **all three GA races** (president, senate,
senate_special) as full apples-to-apples baseline matches, verified live against the
running API for each (`pres2024`/`general2026`/`demo` respectively — each race lives
under a different election in the manifest, which is itself a real gotcha worth
documenting: `general2026` has no President race, and `senate_special` only exists in
`demo` since Warnock already won his full term).
**Lesson:** "not independently fetchable" was a premature conclusion from insufficient
discovery, not a real limitation of GA's system — worth remembering before writing off a
similar case elsewhere as mechanism-only.

---

## 2026-07-17 (cont.) — SC added as a NEW 9th state, WIRED END-TO-END ✅ (7th live state)

User confirmed TX/NV primaries already passed (Nov-2026 prep) and asked to look at SC next,
since SC's primary is also already over. Unlike every state so far, **SC was never one of
the original 8 target states** — baseline.db had ZERO SC data (no precincts, nothing).
SC's Senate seat (Lindsey Graham, Class 2) IS up in 2026 though — same class as GA/MI/NC/TX
— so this was a legitimate, not-deprioritized addition (unlike NV/WI).

**Baseline load:** wrote `ingestor/etl_sc_baseline.py`, a standalone ADDITIVE loader —
deliberately NOT reusing the original `ingestor/etl_baseline.py`, which was discovered to
`os.remove()` and fully rebuild baseline.db from just its 5 hardcoded sources on every run
(would have destroyed all 6 states' live-feed work done earlier this session). Confirmed
the raw Harvard Dataverse CSVs already on disk (nationwide files, previously filtered to
the 8 target states) DO contain SC rows: President 2020 (34,605 rows), President 2024
(49,434 rows), Senate 2020 (27,684 rows — Graham vs Harrison; SC had no 2018/2024 Senate
race). Hit one bug on first run: inserting precincts per-dataset instead of a single
deduped union across all 3 datasets violated the `precincts.id` PRIMARY KEY (same precinct
appears in both president years) — restored from a pre-SC backup and fixed by unioning +
deduping precincts once before any insert (matching the original script's actual pattern).
Loaded cleanly on retry: 3,864 precincts, 46 counties, SC 2020 Senate sanity-checked at
DEM 1,110,828 / REP 1,369,137 (Graham won, matches real-world ~55/45 split).
`etl_sc_county_baseline.py` (NC-pattern) converts senate 2020 to 46 county-pseudo precincts.

**Live feed discovery:** enr-scvotes.org (bare domain) is a parked GoDaddy page — the real
site is `www.enr-scvotes.org/SC/`, SC's Clarity/SOE Software ENR instance. Unlike every
other state checked this session, **SC's classic Clarity mechanism is still fully alive**:
`/SC/{electionId}/current_ver.txt` returns a plain-text version number (exactly the
original pre-2026 Clarity discovery pattern described in Issues.md #1 — that mechanism
isn't dead everywhere, just decommissioned for GA/others). `/SC/elections.json` returns
`[]` right now (no election currently promoted on the homepage) — found real, still-live
election IDs via a web search that surfaced Google-indexed URLs
(`enr-scvotes.org/SC/126294/web.345435/`), landing on SC's actual June 12, 2026 primary
results. From there: `/SC/{eid}/{version}/json/en/summary.json` gives contest names/codes
+ candidate names + parties (note: contest names have literal DOUBLE SPACES, e.g.
`"U.S.  Senate  - REP"` — a Clarity quirk); `/SC/{eid}/{version}/json/ALL.json` gives
EVERY county x EVERY contest in one call, keyed by county NAME. Found and fixed one
parsing trap: ALL.json includes a county entry named literally `"-1"` — a statewide
pseudo-county rollup row that, if not excluded, silently DOUBLES every statewide total
(caught by summing and finding results were exactly 2x the real certified numbers).
Plain httpx throughout — no Cloudflare, no WAF, no Playwright — **the simplest state wired
this entire project** (all 7 wired states have now needed strictly less or equal fetch
complexity than the first one, GA).
`sc_live_feed.py` validated against the real June 2026 primary: exact match to both the
Senate REP contest (Graham 264,091 / Lynch 134,360 / ... = 465,076 total) and Senate DEM
contest (Andrews 226,075 / Brown 110,962 / Freeman 30,374 = 367,411 total), 46/46 counties,
both at the statewide AND per-candidate level. Ran the full analytics pipeline against a
synthetic Graham-vs-Andrews combination (merging the two primary contests into one
`race_type='senate'` payload, since the real 2026 general hasn't happened) purely as a
mechanics check — 100% reporting, 46 counties, shift/win-prob computed correctly, then
cleaned up (not real data, shouldn't linger in results_live).

**Manifest wiring:** got the REAL 2026 SC Senate nominees directly from the June primary
results (no guessing) — Lindsey Graham (R, incumbent, won convincingly) and Annie Andrews
(D). Added SC to `general2026`'s senate list + `senate_baseline` (2020) + `candidates` in
`api/elections.py`. Added SC to `api/main.py`'s `EV` (9 electoral votes, confirmed via
search) and `STATE_NAMES` dicts — **required**, not optional: `_states_payload()` sums
`r["ev"]` unconditionally across all states in a race with no race-type gate, so a missing
EV entry would throw `TypeError` the moment `/api/states?race=senate&election=general2026`
was hit. Verified live: started the actual API, hit `/api/states?race=senate&election=
general2026` — SC appears correctly at 0% reporting (real pre-election state, 46 total
precincts), no crash, `ev_leaning` arithmetic correct. Deliberately did NOT add SC to
`ALL8`/the `demo` election — kept the change scoped to `general2026` only, avoiding any
ripple into UI code that might assume 8 states.

⚠️ **Production DB is a static release snapshot (GitHub Release `db-v1`, gzip'd) — SC is
LOCAL ONLY until someone re-gzips and re-uploads baseline.db.gz.** Nothing in this session
touched the release.
SEVEN states now fully live: NC, GA, PA, AZ, MI, TX, SC — SC being the first true 9th-state
addition (baseline built from scratch, not just a live feed on top of existing data).

---

## 2026-07-17 (cont.) — WI deprioritized; TX WIRED END-TO-END ✅ (6th live state); NV skipped

**WI scoping (before touching any code):** user asked what Wisconsin would actually entail
before starting. Answer: unlike every state wired so far (one state-run system to find),
WI has NO statewide live results feed at all — unofficial results come from 72 separate
county clerk websites, each potentially its own vendor/format. Real work would be (1) survey
several counties to see what's actually reachable (discovery isn't a one-time thing here,
it's up to 72 one-time things), (2) accept partial coverage — probably 8-10 of the highest-
population counties, since full 72-county coverage isn't realistic solo — which introduces
a NEW architecture wrinkle (every state wired so far is 100%-of-counties; WI would be the
first with a "N of 72 counties, X% of vote covered" caveat needed somewhere in the API/UI),
(3) AP Elections API was already priced+rejected project-wide (2026-06-30) but might be
worth a WI-specific re-check since fragmentation is exactly what an aggregator solves.
User chose the AP re-check first. Result: AP pricing is still opaque everywhere (developer.ap.org,
docs, third-party listings) — quote-only, no public tier, no WI-specific option found. Also
checked whether a public news aggregator (NPR's live-results page) leaks a free/open
JSON delivery endpoint under an existing AP contract — no, NPR's page is fully static/
server-rendered with zero client-side data calls, nothing to piggyback on.
**Bigger finding surfaced during this check:** NPR's WI page only lists Governor + U.S.
House for the 2026 primary — no Senate. Cross-checked `api/elections.py`: `general2026`
senate states = `["GA","MI","NC","TX"]` — **WI has no Senate or President race on the Nov
3, 2026 ballot at all** (Senate is Class 3, next up 2028, same class as PA/AZ/NV). So WI
doesn't gate this November's election night — Aug 11 is a convenient test window for 2028
prep, not a real deadline. User agreed to deprioritize WI (revisit later, more runway).
User also asked: does NV have a 2026 Senate race? Checked the same manifest — no (NV is
also Class 3, 2028). **NV skipped for the same reason** — nothing to track for Nov 2026.

**TX**: own system at results.texas-election.com (an Angular SPA — NOT Clarity/Enhanced
Voting). A Cloudflare WAF rule blocks plain httpx outright (`"Attention Required!"` page,
not a JS challenge) — confirmed via direct httpx test. Unlike MI, **headless Playwright is
enough** to pass it (tested both headless and headed side by side — identical 1.8MB
response either way), so TX's poller can run on a normal headless box/CI, no display
needed. `tx_live_feed.py` + `etl_tx_county_baseline.py` added.
Found the best mechanism of any state so far: ONE `County.json` call returns EVERY county
x EVERY race in the whole state, keyed directly by **5-digit county FIPS** ("48001") — an
exact match to our `county_fips` column, meaning zero name-matching/aliasing needed at
all (every other state so far needed at least an uppercase county-NAME match, some with
abbreviation quirks like MI's "GD. TRAVERSE"). Two-step version discovery mirrors AZ's
uploadId pattern (`Version.json` → current version number → `County.json` at that
version). electionId is auto-discovered via `ElectionConstants_404.json`'s year+type
lookup (not hardcoded) — same idea as MI's dropdown-scan, just a cleaner data structure.
Validated vs the 2024 general (President + Senate, both on one ballot, electionId 49664):
254/254 counties, President Trump 6,393,597 R / Harris 4,835,250 D, Senate Cruz 5,990,741
R / Allred 5,031,249 D — exact match to certified for both races. Ran the analytics engine
directly against populated results_live: 100% reporting, shift≈0, win_prob correctly ~0%
D for both (Cruz/Trump won TX comfortably). No leftover precinct-level rows.
SIX states now fully live: NC, GA, PA, AZ, MI, TX. Of these, only NC/GA/MI/TX actually
gate the Nov 3, 2026 general (PA and AZ were built ahead of their own 2026 races — PA's is
2028, AZ's Senate is 2028 too — serving as mechanism-proving + 2028 prep, which the user
had already implicitly signed off on by asking for them in order).

---

## 2026-07-17 (cont.) — AZ + MI WIRED END-TO-END ✅ (4th + 5th live states, primary-night-ready)

User asked to get AZ (Jul 21 primary) and MI (Aug 4 primary) fully prepped for their
upcoming live tests. Both are now code-complete, not just mapped.

**AZ**: `results.arizona.vote` is a Cloudflare SPA, but its DATA lives on a separate open
CDN (`cdn1.arizona.vote`, plain httpx, no Cloudflare — confirmed via `results.arizona.vote`
returning `cf-mitigated: challenge` on direct httpx, while the CDN 200s cleanly). Discovered
via real-Chrome network inspection (the in-app Browser tool passed AZ's Cloudflare challenge
fine; a Playwright/httpx direct hit does not). Two-step fetch: `election_{eid}_{jid}.json`
for the current `uploadId`, then ONE `all_county_races_{eid}_{jid}_en_{uploadId}.json` call
returns EVERY county x EVERY race (simpler than GA/PA — no per-county or per-race loop).
Party is a "(CODE)" suffix — on ChoiceName for general elections, on ContestName for
primaries (AZ splits each party into its own primary contest row) — `az_live_feed.py`
checks both. electionIds are STABLE and already listed on results.arizona.vote's own
election-history page (no discovery needed): 2026 primary = 68, 2024 general = 47, etc.
(`az_election_ids()`). Added `etl_az_county_baseline.py` (NC/GA/PA pattern) for President
2024 + Senate 2024. Validated vs the 2024 general: 15/15 counties, President Trump
1,770,242 R / Harris 1,582,860 D, Senate Gallego 1,676,335 D / Lake 1,595,761 R — both
exact match to certified. Ran the analytics engine directly against populated results_live:
100% reporting, shift≈0, win_prob correct both ways. Additionally SMOKE-TESTED the actual
live 2026 primary structure (electionId 68, "Governor (DEM)", scratch race_type
`az_primary_test`): uploadId discovery worked (12868), all 15 counties matched, primary-style
party parsing (from ContestName since ChoiceName has no suffix) correctly resolved "Hobbs,
Katie" → DEM, 0 votes / 0 precincts reporting as expected 4 days out. Test rows cleaned up
after. AZ has NO President/Senate race on its own 2026 primary ballot (Senate is Class 3,
next up 2028) — Jul 21 will be a mechanics validation only (uploadId/PrecinctsReported
changing live), using Governor as the real vehicle, not a manifest data load.

**MI**: confirmed `mvic.sos.state.mi.us` blocks BOTH headless Playwright AND plain httpx
(403 "Just a moment" on every request, including the download endpoint) — but a HEADED
Chromium with `navigator.webdriver` masked passes cleanly (tested directly: headless
Playwright.request → 403; headed Playwright + in-page fetch() → 200, full 1.5MB zip).
Found a much better mechanism than the county/township/precinct UI drill-down: `/VoteHistory/
GetPrecinctResultsFile?electionId={N}` returns ONE bulk ZIP for the WHOLE STATE — every
precinct x every office, tab-delimited, fully documented by a readme.txt inside the zip
itself (same shape as NC's bulk file). `mi_live_feed.py` drives a headed Playwright browser,
fetches + unzips this in-memory, and aggregates precinct rows to county totals (83 counties,
office code 1=President/5=Senate). Added `etl_mi_county_baseline.py` for President 2024 +
Senate 2024. One county-name wrinkle: MI's file abbreviates "GD. TRAVERSE" for Grand
Traverse County — added an alias map (`COUNTY_ALIASES`); our DB already carried both
"ST CLAIR"/"ST. CLAIR" and "ST JOSEPH"/"ST. JOSEPH" spellings so period-stripping handles
those without a fips collision (checked — the unpunctuated variants have 0 historical rows).
Validated vs the 2024 general: 83/83 counties, President Trump 2,816,636 R / Harris
2,736,533 D, Senate Slotkin 2,712,686 D / Rogers 2,693,680 R — EXACT match to certified
(not just within tolerance). electionId is NOT pre-published like AZ's — MI only adds an
election to the `#ElectionDateId` dropdown once configured in their system; confirmed the
Aug 4, 2026 primary is NOT there yet (as of today), so `mi_live_feed.py` auto-discovers the
id by date-matching that dropdown each run and exits cleanly with "NOT FOUND, retry closer
to the night" rather than crashing (smoke-tested this path directly). MI Senate (Slotkin's
seat) IS on the `general2026` manifest already with "TBD AUG 4" placeholders — replace with
real nominee names once the primary decides them. Needs a machine with a real display
(headed browser) — won't run on Render or a headless CI box.
Added `playwright` to requirements.txt (previously just a commented-out "planned" note) —
it's now a hard runtime dependency for MI specifically, not just a one-time discovery tool.
FIVE states now fully live: NC, GA, PA, AZ, MI.

---

## 2026-07-17 — PA WIRED END-TO-END ✅ (3rd live state)

`ingestor/pa_live_feed.py`: PA runs its OWN election-night system at
electionreturns.pa.gov — NOT Clarity, NOT Enhanced Voting (an AngularJS SPA over an
open ASP.NET API; discovered via Playwright network-request inspection, then
confirmed OPEN to plain httpx — no Incapsula block on the API paths despite the WAF
resource loads visible on the page). Key endpoints: `GetAllElections` (full election
list + electionid), `GetOfficeNames` (officeId per race), `GetCountyBreak?officeId=
&electionid=&electiontype=` → `{"Election":{"Statewide":[{"ADAMS":[...],
"ALLEGHENY":[...], ...}]}}` — one key per county (67, exact-name match to our county
column, no crosswalk needed), each row carrying Votes AND a live ballot-mode split
(ElectionDayVotes/MailInVotes/ProvisionalVotes — PA has no early in-person voting, so
only 3 modes vs NC's 4). Maps to PA-{fips}-CTY → results_live per mode. Clears ALL
PA-% live rows first (same leftover-contamination guard as NC/GA).
Added `ingestor/etl_pa_county_baseline.py` (NC-pattern) — converts PA's existing
precinct-level President 2024 + Senate 2024 baselines to county-pseudo (67 PA-CTY
precincts; precinct-level rows for those race/years removed).
Validated end-to-end against the 2024 general (electionid 105, both races on one
ballot): 67/67 counties, **Senate: Casey 3,384,180 D / McCormick 3,399,295 R (49.9%)
— exact match to certified**; **President: Harris 3,423,042 D / Trump 3,543,308 R
(49.1%) — exact match to certified**. Ran `analytics.compute_state_analytics` directly
against the populated results_live (not the replay path) for both races: 100%
reporting, shift ≈0 (expected — baseline and live are the same certified election),
win_prob correctly favors R in both (41.2% D senate — close race; 4.2% D president —
clearer margin), all 67 counties rolled up. THREE states now fully live: NC, GA, PA.
PA is actually the RICHEST of the three — live ballot-mode split (like NC) AND single
open plain-httpx call for all counties per race (like GA, but even simpler — one
GetCountyBreak call returns all 67 counties, no per-county fetch loop needed).
NOTE: PA isn't on the `general2026` manifest (Senate is Class 3, next up 2028) — this
was validated as a standalone archived-election test, matching the CONTEXT.md plan.

---

## 2026-07-06 (cont.) — GA WIRED END-TO-END ✅ (2nd live state)

`ingestor/ga_live_feed.py`: reads GA's OPEN Enhanced Voting API — state feed lists
159 counties (childLocalities), then fetches each county's `/api/elections/
{county-shortName}/{EID}/data` (in parallel, 16 workers) → summaryResults.
ballotOptions (candidate + voteCount; party parsed from name suffix "(Rep)"/"(Dem)").
Maps to GA-{fips}-CTY (the 2021-runoff county-pseudo precincts already in the DB) →
results_live. Clears ALL GA-% live rows first (same leftover-contamination bug as NC).
Validated end-to-end: GA 2024 President → 159/159 counties, D 2,548,017 / R 2,663,117
(48.9%), shift -0.00, P(D) 1% Safe R (Trump won ✓), Fulton 535,238 D72.7% ✓.
LIMITATION: Enhanced Voting summaryResults gives TOTALS only (no live mode split) →
GA mode='all' (NC has the real mode breakdown; GA doesn't expose it here). Election
night: ga_live_feed with the 2026 EID + "US Senate" contest → GA-CTY → matches the
2021 senate county-pseudo baseline (already loaded) → analytics work. Feed proven vs
President; senate = same feed, different contest filter. TWO states now fully live: NC, GA.
NOTE: added a demo GA president-2024 county-pseudo baseline to run the analytics test
(local baseline.db only). Per-county fetch = 159 requests/poll (parallelized; consider
caching/throttle for prod).

---

## 2026-07-06 (cont.) — GA CRACKED + MI/WI recon + roadmap

**GA (was Clarity → now Enhanced Voting; CRACKED):** GA moved off the dead Clarity
endpoint to Enhanced Voting. Results at **results.sos.ga.gov**; data API
`results.sos.ga.gov/results/public/api/elections/Georgia/{EID}/data` is **OPEN to
plain httpx** (200, ~900KB JSON) despite Cloudflare on the page. EIDs human-readable
(2024NovGen, 2024MayGenPri...). JSON: jurisdiction.childLocalities (159 counties +
%reporting), ballotItems[].summaryResults.ballotOptions (candidate name + voteCount).
Validated: GA 2024 President Trump 2,663,117 / Harris 2,548,017 (matches certified).
Statewide is clean; per-county VOTE breakdown = one more endpoint to map (per-locality
call) — small follow-up. GA is strong; wire it end-to-end next (like NC).
**MI (Aug 4 primary):** MI SoS results at michigan.gov/sos/elections/election-results-
and-data + mvic.sos.state.mi.us (by county/precinct); downloadable county data exists.
Needs a focused mapping pass to find the live machine-readable endpoint; validate Aug 4.
**WI (Aug 11) — confirmed HARDEST:** NO statewide unofficial-results feed. Live numbers
come from 72 county clerk sites, AP-aggregated. elections.wi.gov posts only CERTIFIED
(weeks later). Options: AP feed ($, we're skipping AP), 72 county scrapers, or an
aggregator. Decide least-bad at the Aug 11 primary.

---

## 2026-07-06 (cont.) — AZ architecture MAPPED (via Playwright)

AZ = own system. `results.arizona.vote` is a **Cloudflare-protected AngularJS SPA**
(plain httpx → "Just a moment" 403; Playwright's real browser passes the JS
challenge). BUT the actual DATA is on a SEPARATE **open CDN `cdn1.arizona.vote`**
(S3-style, plain httpx works — no Cloudflare). URL template (seen in the SPA's
network calls): `cdn1.arizona.vote/data/{date}/{id}/election_{date}_{id}.json`
(+ tabs_{..}_en.json, translation_en.json). IDs are blank right now (no active
election → 404s). Second path: **azsos.gov FTP/HTTPS XML press feed**
(ftp.azsos.gov/ElectionResults — SUMMARY county+state + PRECINCT DETAIL).
So AZ = "open data behind a fancy front-end", like NC. PLAN: on Jul 21, Playwright
ONCE to grab the current election's date/id from the SPA, then plain httpx-poll the
open CDN JSON (or the FTP XML) → parse county-level. Can't fully build+validate the
fetcher until a real election exists (Jul 21 primary) — no active/locatable AZ
election data right now. Playwright now proven useful (passes Cloudflare).

---

## 2026-07-06 (cont.) — NC WIRED END-TO-END ✅ (first live state, validated)

NC now works through the full pipeline — with NO core-code changes (safe for prod;
baseline.db is gitignored, prod uses the released copy). Three new files in ingestor/:
- `nc_ingestor.py` — reads NCSBE open S3 file `results_pct` (handles NC's early-vote
  column rename: "One Stop" ≤2020 → "Early Voting" 2024+). County-level, by mode.
- `etl_nc_county_baseline.py` — aggregates NC's 2020 Senate precinct baseline into
  county-pseudo-precincts `NC-{fips}-CTY` (the GA-runoff pattern) and REMOVES the
  precinct-level 2020 Senate rows (county-level v1). Idempotent. Ran it: 100 counties.
- `nc_live_feed.py` — NCSBE → results_live as `NC-{fips}-CTY`, per ballot mode;
  clears all NC-% live rows first (avoids leftover-sim contamination).
Validated: ingested real NC 2020 Senate → analytics show 100/100 counties, D 2,569,965 /
R 2,665,598 (49.1%), shift +0.00 (live 2020 == baseline, exactly consistent), P(D) 3%
Likely R (Tillis won ✓), ballot modes election-day D34% / early D47% / mail D70% /
provisional D45% (the County Insight red-mirage signal). Election night = point
nc_live_feed at the Nov-2026 date + "US SENATE" on a schedule (replaces Next Batch).
Two bugs found+fixed en route: (1) DELETE too narrow → leftover precinct-level NC rows
polluted totals; (2) 2020 "One Stop" vs 2024 "Early Voting" column name.
NOTE: modified baseline.db (NC Senate → county-level). Local only; to restore precinct-
level, re-run etl_baseline. NEXT: Task 2 = Playwright to crack Clarity (GA/PA/TX/MI).

---

## 2026-07-06 — Live-readiness kickoff: CORS ready, Clarity 403 diagnosed, NC ingestor BUILT

Started the critical-path work (ahead of the Jul 9 plan).
- **CORS (Task 1):** code already reads `CORS_ORIGINS` env (defaults *). Only a
  user action left: set `CORS_ORIGINS=https://election-forecast-silk.vercel.app`
  on Render → auto-redeploys. No code change needed.
- **Clarity 403 (Task 2):** DIAGNOSED (see Issues #1 update). It's AWS CloudFront,
  NOT a bot-block — `elections.json` returns 200 to a plain request; the old data
  paths 403 for everyone incl. curl_cffi browser-TLS. Modern Clarity moved to new
  JSON endpoints. Next: Playwright network-capture to map them. NOT solved yet.
- **NC ingestor (Task 3): ✅ BUILT + VALIDATED.** `ingestor/nc_ingestor.py` fetches
  NCSBE's OPEN S3 file `dl.ncsbe.gov/ENRS/{date}/results_pct_{date}.zip` (tab-
  delimited, statewide, precinct-level, already split by voting method: election_
  day/early/mail/provisional). Aggregates to COUNTY level. Test vs 2024 President:
  100 counties, R 51.6% / D 48.4% (Trump wins NC) — matches certified exactly.
  NC has NO CloudFront/403 problem. NC 2026 primary data exists at ENRS/2026_03_03/.
  TODO next: wire into results_live via the GA-runoff county-as-pseudo-precinct
  pattern + point at the NC 2026 Senate contest name.

---

## 2026-07-02 — Resolved the "Vercel looks totally different" confusion (no code changes)

Fresh session. User reported `election-forecast.vercel.app` looked completely different
from `localhost:5173` — a national 2026 House forecast with a US district map, seat
distribution, and House-race tables — and asked "how did we build this?"

**Root cause (investigated read-only): it's NOT our app.** Our deployed frontend is
**election-forecast-SILK.vercel.app** (Vercel appended "-silk" because the plain name was
already taken). The bare **election-forecast.vercel.app** is a DIFFERENT, unrelated
project that grabbed the name first. Evidence: our code has NO "house" references, NO map
library (ui deps = axios/react/recharts only), and only the 8 swing states. So the user
had been comparing our swing-state Pres/Senate app against a stranger's national House app.

Also clarified: the local code IS in sync with our real deploy (`main` == `origin/main`,
only KICKOFF_PROMPT.md uncommitted); a "simpler" localhost was just a stale/older view.

**No files changed** (per user instruction — investigate only). Recorded the URL gotcha in
CONTEXT.md + memory so it never causes confusion again. User to verify at the -silk URL.
Open question for next session: user may want a real national House+map view built — that
would be a large NEW project (new data + a map library), not a toggle to something existing.

---

## 2026-06-29 — Backend DEPLOYED LIVE on Render (Phase 7 in progress)

- **Backend is live → https://election-forecast.onrender.com** (Render Docker web service,
  FREE tier). Verified in production: `/api/health` ok (771,834 historical rows),
  `/api/elections` (7 elections), `/api/states` (8 states + EV tally), Cache-Control header present.
- **DB provisioning solved:** baseline.db (217 MB) gzipped → **43 MB**, uploaded as a
  **GitHub Release** (tag `db-v1`, asset `baseline.db.gz`). On boot `entrypoint.sh` →
  `download_db.py` fetches it via the `DB_URL` env var and unzips to data/db/. Render logs
  confirmed `[db] baseline.db ready (226,824,192 bytes)` → uvicorn up → "service is live".
- **Free-tier caveats:** spins down after ~15 min idle (cold start re-downloads the 43 MB DB);
  ephemeral disk so sim state resets. For election night → Starter ($7/mo) + a persistent disk.
- **NEXT (USER):** Vercel frontend — vercel.com/new → import repo → **Root Directory=`ui`** →
  `VITE_API_BASE`=the Render URL → Deploy; then set `CORS_ORIGINS`=the Vercel URL on Render.
  That completes Phase 7.
- CONTEXT.md top ("WHERE WE ARE / NEXT SESSION START HERE / PENDING order") rewritten;
  cross-session memory updated.

---

## 2026-06-28 — Issue #7 fixed · Phase-7 deploy wiring · feed audit (round 1) · pushed to GitHub

- **Issue #7 RESOLVED** — `etl_ga_runoff_2021.py` now estimate-fills the 4 counties
  OpenElections omits (Camden/Chattooga/Grady/Greene): each split by its real 2020
  Senate lean + size, scaled so the missing sum = (certified − loaded). All **159**
  counties present; GA Senate statewide now EXACTLY certified (Ossoff 50.61% /
  Warnock 51.04%). Integration test still PASS.
- **Phase-7 deploy wiring** (see DEPLOY.md) — `Dockerfile` + `.dockerignore` (backend on
  Render/Fly); CORS now env-driven (`CORS_ORIGINS`, default `*`); `Cache-Control` on
  `/api/states` + `/api/state` (max-age=15, swr=30) — the scale lever; `ui/src/api.js`
  uses `VITE_API_BASE` (relative in dev, absolute in prod). UI builds clean.
- **Feed audit round 1** (desk research) → FEED_AUDIT.md. NC = best (live dashboard WITH
  a by-voting-method tab); GA solid (statewide Clarity); PA/TX/MI = county-by-county
  Clarity; AZ/NV = own statewide systems (confirm live mode); **WI = hardest (no
  statewide feed — 72 county sites, AP-aggregated)**. Recommend pricing an **AP Elections
  API** as a uniform primary source. Round 2 = test vs Jul/Aug primaries.
- **Repo pushed** to github.com/subhojitr-dev/election-forecast (`main`); 1.4 GB of data
  (CSVs + baseline.db) gitignored — see DATA_SETUP.md to rebuild.

---

## 2026-06-28 — Election ballot manifest (date-aware race dropdown) + live-poller note

Makes the race line-up DATA-DRIVEN so a real election night shows only the contests
actually happening.
- NEW `api/elections.py` — the ballot manifest: per election (demo / general2026 /
  general2028) → which races, which states, which baseline year per state. Senate
  classes make this knowable years ahead: 2026 = Class-2 (GA/MI/NC/TX, NO President);
  2028 = President + Class-3 (GA/AZ/NV/PA/WI/NC).
- `api/main.py`: `baseline_for` / `states_for` are now election-aware (default 'demo'
  = unchanged historical behavior); NEW `/api/elections`; `election` param threaded
  through /api/states, /api/state, /api/state/.../county, /api/sim/*.
- `api/simulation.py`: SimController sessions keyed by **(election, race)**; reset takes
  the election's states + per-state baseline closure.
- UI: **Election dropdown**; `RaceToggle` renders the active election's races (2026 shows
  only Senate); election threaded through every call; switching election re-points the
  toggle + resets selection.
- VERIFIED: /api/elections lists 3; general2026 Senate strip = GA/MI/NC/TX only;
  general2026 President = empty; demo President = all 8 (unchanged); **MI-2026 Senate
  uses the 2020 baseline (Peters vs James), not 2024** (the correct seat). UI builds clean.
- general2028 is stubbed — needs the **2022 Senate file** loaded (data TODO).
- ADDED same day: **real 2026 nominee labels** via manifest `candidates` (relabels the
  replayed baseline) — GA Ossoff/Collins, NC Cooper/Whatley, TX Talarico/Paxton, MI
  TBD (primary Aug 4); web-sourced (primaries Mar–Jun 2026). Plus **historical test
  elections** in the dropdown: 2024 President, 2020/2024/2018 Senate (replay real
  results for any of them). Dropdown now has 7 entries. Verified per-state.

REAL-NIGHT POLLING (no "Next Batch"): the Phase-2 poller (`ingestor/clarity_poller.py`
`run_poller`) PULLS the live feed every ~60s — election feeds are pull-only, no webhooks.
Its `on_write` hook recomputes analytics (same path as the button); the UI gets updates
via the `/ws` WebSocket push + the 10s poll.

---

## 2026-06-28 — Ballot-mode (bucket) dimension + turnout/red-mirage scenario + County Insight

Adds the highest-leverage real-night feature: track votes by BALLOT TYPE and surface
per-county benchmark / turnout / pending analysis.
- DATA: results_live gained a `mode` column (engine.ensure_schema ALTERs in place;
  LiveRow.mode; write_snapshot stores it). Modes: election_day/early/mail/military/all.
- SIMULATOR: ReplayFeed can synthesize ballot modes (MODE_DFRAC/RFRAC → mail leans D,
  election-day leans R) with TIMED release (mail lands at batch 3 → red mirage → blue
  shift), plus a turnout_bump for the N most-populous counties. New president scenario
  "turnout_buckets" (+4% big-county turnout, swing +2%, mode_split).
- ANALYTICS: county_rollups adds est_total_2pty / turnout_vs_2020 / pending_extrapolated
  (the "scale current count to 100%" method). rollup.mode_breakdown() = per-mode tally +
  lean. API builds a plain-English per-county note (share vs 2020 benchmark, turnout,
  pending + which way it leans from the mode mix; caveats turnout while mail is still out).
- API: /api/state bundle gains `modes`; NEW /api/state/{abbr}/county/{cty} (rollup +
  modes + note). turnout_buckets scenario registered.
- UI: new CountyInsight panel (note box + ballot-type selector); CountyTable rows are
  clickable (drive the note) + new "Turn v20" / "Pending" columns.
- VERIFIED end-to-end: GA president turnout_buckets steps 47.3% (red mirage, mail=0) →
  52.3% (blue shift, mail D 69%); Fulton +5% turnout, Dem 75.5% vs 73.5% benchmark.

REAL-NIGHT NOTE: mode is OPTIONAL — present in sims & Clarity feeds (the GA runoff file
has these columns), gracefully absent (defaults to 'all') for states that don't supply
it. Live-feed availability is the gating risk — see Issues #8.

---

## 2026-06-28 — GA special-seat view (Warnock) + county-grain reveal fix

**New race view "GA Special" (race_type=`senate_special`).** Exposes the Jan-2021
Warnock vs Loeffler runoff (loaded earlier today) as a GA-only race so it can be
simulated in the dashboard alongside Ossoff.
- `api/main.py`: `SENATE_SPECIAL_BASELINE={"GA":2021}`; `baseline_for` handles
  `senate_special`; new `RACE_STATES` + `states_for(race)` restrict it to GA (used
  by the strip); `SCENARIOS["senate_special"]` (true + dems_plus5).
- `api/simulation.py`: `reset()` skips states whose ReplayFeed has no data, so a
  GA-only race just sets up GA.
- UI: `RaceToggle` gains a 3rd "GA Special" button; `App.jsx` forces selected=GA on
  entry (GA-only race).
- Verified end-to-end via the API: strip shows GA only; Warnock vs Loeffler;
  baseline 51.25%; steps converge to Safe D (51.25%) at 100%.

**Fixed county-grain reveal (`ingestor/replay_harness.py`).** The GA Senate
baselines are county pseudo-precincts (1 per county). Proportional reveal rounds
each county to all-or-nothing → jumpy % and an EMPTY first batch. ReplayFeed now
auto-detects county-grained data (every county has exactly 1 precinct) and falls
back to whole-county reveal → smooth even % (20/40/60/80/100). Multi-precinct races
(president, real-precinct senate) keep proportional. Verified GA senate AND
senate_special now step 20→40→60→80→100 and converge to the right winners.

---

## 2026-06-28 — GA Senate baseline = Jan-2021 RUNOFF + convergence chart polish

**GA Senate now uses the Jan 5, 2021 RUNOFF (county level), not the Nov-2020 general.**
Why: GA requires a majority; Perdue LED the Nov general but under 50%, so the seat
went to the runoff, which Ossoff WON — and it's Ossoff's seat that is up again in
2026. The dashboard previously showed Ossoff LOSING (Nov-general Perdue +88k).
- New loader `ingestor/etl_ga_runoff_2021.py` (re-runnable, idempotent): loads BOTH
  runoff seats from OpenElections precinct data aggregated to COUNTY, as
  election_year=2021 — regular (Ossoff/Perdue) → race_type 'senate'; special
  (Warnock/Loeffler) → 'senate_special'. Each county = one pseudo-precinct
  "GA-{fips}-CTY" so the precinct-keyed engine/replay work unchanged at county grain.
- Repointed SENATE_BASELINE["GA"]=2021 (api/main.py); integration_test GA Senate
  R→D (+ fixed a Windows cp1252 emoji crash in its final print). All 16 races still
  PASS, exit 0. GA Senate baseline now Ossoff 50.82% two-party (D win).
- KNOWN GAP (Issue #7): the OpenElections runoff file omits 4 counties (Camden,
  Chattooga, Grady, Greene) → baseline reads 50.82% vs certified 50.62%. Left at
  155/159 for now (real data only; winners correct). Backfill pending a decision.

**Convergence chart (Panel 5) polish — `ui/src/components/ConvergenceChart.jsx`:**
- Anchor the live line at the 2020 baseline for the 0%-reporting row (was blank
  from 0→first-batch because vote share is null when no votes are in).
- Same blue line renders SOLID ≥50% / DASHED <50%, switching at a synthetic exact
  50%-crossing point.
- Fixed 0→100% x-frame + per-poll animation OFF so the line EXTENDS as batches
  arrive (reads as a continuation, not a redraw). Y-axis floors at 30%.

Restart note: the API repoint needs a uvicorn restart (done); UI changes are HMR/refresh.

---

## 2026-06-27 — Simulator realism: proportional county reveal (Issue #6)

Was: simulator revealed whole counties one at a time (a county could read 100%
while the state was at 40%). Now: added `order="proportional"` to ReplayFeed —
every county reports gradually + in parallel, each with a random per-county speed
(final batch forces 100%). SimController uses it. Verified: at ~41% statewide
each county ~16–48% in. Restart API + click Reset in UI to pick it up.

---

## 2026-06-27 — Performance fix: "Next Batch" was 18–50s, now ~1–2s

Symptom: clicking Next Batch appeared to do nothing (button stuck on "…").
Root causes + fixes:
- `results_live` had NO index → live queries full-scanned 183k rows. Added
  idx_rl_race / idx_rl_precinct (also baked into engine.ensure_schema + WAL).
- `/api/states` recomputed FULL analytics for all 8 states on EVERY 5s poll →
  pile-up. Now reads the latest `live_snapshots` row per state (instant); seeds
  lazily if missing. Added `light=True` mode to compute_state_analytics (skips
  county rollups/watch list) for the strip + simulation.
- Static 2020/2024 baseline was re-loaded from disk every call → added an
  in-memory baseline cache in engine (`_BASELINE_CACHE`).
- Writes committed 8× per batch (8 fsyncs) → write_snapshot/record_snapshot got
  a `commit` param; SimController.next now commits ONCE per batch. DB set to WAL
  + `synchronous=NORMAL` + `busy_timeout=10000` (api/db.py).
- UI poll interval 5s → 10s (ui/src/App.jsx).
Result: Next Batch ~0.8–1.9s; /api/states ~0.4s; /api/state full ~1.8s.
(Restart the API after pulling these: it's run without --reload here.)

---

## 2026-06-25 — Phase 6 (Integration test + simulator) ✅ COMPLETE

**Populated all 8 states, both races (true data).** President vs 2020; Senate vs
most-recent (GA/NC 2020, others 2024). Verified every winner matches reality
(Biden GA/PA/AZ/NV/WI/MI, Trump NC/TX; Senate GA-R/NC-R/AZ-D/NV-D/WI-D/MI-D/
PA-R/TX-R). API now uses per-state Senate baseline (api/main.py SENATE_BASELINE).

**Codified integration test** — `integration_test.py` (project root): replays
true results for all 8×2 through the real pipeline and ASSERTS exact convergence
+ correct winner. Run `python integration_test.py` → all 16 PASS, exit 0.

**NEW: election-night simulator (the "Next Batch" stepper).**
- `api/simulation.py` — SimController: in-memory per-race stepper (5 batches =
  20/40/60/80/100%); reset/next/status. Reuses ReplayFeed + analytics.
- `api/main.py` — endpoints /api/sim/reset, /api/sim/next, /api/sim/status,
  /api/scenarios; SCENARIOS registry.
- Scenarios built: president = true / Ossoff-vs-Vance D+5 / AOC-vs-Vance D+5;
  senate = true / Democrats D+5. (Candidate relabel + uniform swing + per-precinct
  noise via new ReplayFeed dem_name/rep_name params.)
- UI: `ui/src/components/SimControls.jsx` (scenario dropdown + Reset + Next Batch
  ▶ + progress bar); wired into App.jsx. On real election day the Phase 2 poller
  replaces the button — same data path.
- Verified in browser: stepping 0→20→...→100% updates the whole dashboard;
  screenshot confirmed at 20% in. Fixed a float-rounding display bug.

**DB state after this session:** results_live holds the TRUE 100% snapshot for all
8 states × both races (integration_test left it there).

**Still TODO for the fun tests:** a "2026 actual Senate candidates" scenario
(needs the real 2026 nominees per state + per-state name map).

---

## 2026-06-25 — Phase 5 (React UI) ✅ COMPLETE

Built the dashboard with all 10 panels (Vite + React + Recharts), wired to the
API, and verified visually in a browser via the preview tool.

**Files (in `ui/`)** — scaffolded with `npm create vite` (React), added recharts + axios.
- `vite.config.js` — proxies /api + /ws to the FastAPI backend (:8000).
- `src/App.jsx` — layout + 5s polling refresh (live feel); race + selected-state state.
- `src/api.js`, `src/format.js` — fetch helpers + formatting.
- `src/components/` — the 10 panels:
  SwingStateStrip (1), RaceToggle (2), search box in App (3), LiveVoteBar (4),
  ConvergenceChart (5, Recharts line + 2020 baseline reference), WinProbGauge
  (6, hand-drawn SVG gauge), CountyTable (7, sortable + search filter),
  CountyShiftBars (8, Recharts bars), WatchList (9), EVTracker (10).
- `src/index.css` — dark election-night theme.

**Validated**
- `npm run build` compiles clean (456 modules). ✓
- Ran API (:8000) + Vite (:5173); screenshotted the live dashboard — swing-state
  strip, vote bar (Biden 50.1/Trump 49.9, +12,670), gauge, convergence chart,
  county shift bars, county table all render with real data. ✓
- Fixed one bug found in the screenshot: gauge DEM/REP labels were swapped.
- Added per-precinct swing variation (`swing_noise`) to ReplayFeed so the demo
  shows realistic varied county shifts (the same-year replay shows zero shift).

**DB/demo state:** GA president left populated with a SYNTHETIC R+2 swing
(`engine.py GA president 2020 -0.02 0.03`) so the shift panels are populated.
True 2020 replay (zero shift): `python analytics/engine.py GA president 2020`.

**To view:** terminal 1 `uvicorn api.main:app --port 8000`; terminal 2
`cd ui && npm run dev` → http://localhost:5173

---

## 2026-06-25 — Phase 4 (FastAPI REST + WebSocket) ✅ COMPLETE

Exposes the Phase 3 analytics over HTTP so the React UI (Phase 5) can render.
Read-only API; computes analytics on demand from the DB the ingestor maintains.

**Files (in `api/`)**
- `main.py` — FastAPI app (CORS open for dev), EV + state-name maps. Endpoints:
  - GET /api/health
  - GET /api/states?race=president      → swing-state strip + EV tally (Panels 1,10)
  - GET /api/state/{abbr}?race=...       → full bundle (vote bar, gauge, counties,
    watch list, convergence series) — Panels 4-9
  - GET /api/state/{abbr}/series?race=…  → convergence time-series only (Panel 5)
  - WS  /ws?race=president               → pushes the strip on connect + when
    results_live changes (fingerprint = row count + max last_updated)
- `db.py` — read-only SQLite connection helper.
- `__init__.py` — package marker.
- requirements.txt — fastapi + uvicorn now active.

**Validated**
- TestClient: health, /api/states (8 states, EV leaning D77/R56 from the GA
  replay + priors), /api/state/GA (159 counties, watch list, 12 series points),
  /series, and a 404 for a bad state. ✓
- Real uvicorn over HTTP on :8011 — health/states/state/GA + /docs all 200. ✓
- WebSocket initial push delivers the strip. ✓

**DB note:** left GA president populated (results_live + live_snapshots) so the
API returns live data for demos/Phase 5. Re-populate any race with
`python analytics/engine.py <ST> <race> <year>`.

**Run it:** `uvicorn api.main:app --reload --port 8000` → http://localhost:8000/docs

---

## 2026-06-25 — Phase 3 (Analytics engine) ✅ COMPLETE

Built the intelligence layer (brief's 4 steps) as pure, testable modules + an
orchestrator, and a new time-series table.

**Files (in `analytics/`)**
- `shift_calculator.py` — two-party share, vote-weighted shift, uniform-swing
  projection (Steps 1-3). Pure functions.
- `bayesian_model.py` — win probability (Normal CDF via math.erf, no scipy),
  `reporting_weight` (damps swing applied to the remainder so early calls stay
  near the 2020 prior), confidence tier + lean label (Step 4).
- `rollup.py` — live county rollups + watch list (Panels 7/8/9).
- `engine.py` — `compute_state_analytics()` runs all steps off `results_live` +
  baseline; `record_snapshot()` writes the time-series; `make_recorder()` hook
  for the poller; replay+analytics demo.
- New table **`live_snapshots`** (per-poll statewide series → convergence/trend
  chart Panel 5; addresses Issue #4). Created by `engine.ensure_schema()`.
- Wired `run_poller(on_write=...)` hook in `clarity_poller.py`.

**Validated**
- GA-2020 replay vs 2020 baseline: shift = 0.000 (correct — same data), and the
  projection nails the true final (50.13%) even at 8% reporting (unbiased). ✓
- GA-2020 replay with synthetic R+3 swing: shift detector recovered -0.030
  exactly; projection anchored near prior early (49.6% @ 8%) → converged to the
  true shifted final 47.13%; P(D win) fell 47.7% → 0.0% (Safe R); tiers Very
  Early → Near Final. ✓
- `results_live` + `live_snapshots` cleared to clean slate; baseline untouched.

**Key finding (reinforces the crosswalk plan, Issue #3):** even 2020↔2024, only
**~21%** of GA precincts match by exact precinct id (562 / 2702). Confirms a
real crosswalk is required for cross-year/live precinct-level comparison; until
then, county-level comparison is the robust fallback.

**Try it:**
- `python analytics/engine.py GA president 2020`        (replay + win prob)
- `python analytics/engine.py GA president 2020 -0.03`  (with a synthetic R+3 swing)

---

## 2026-06-25 — Phase 2 (Live ingestor) ✅ COMPLETE

Built the live-results pipeline. Because there's no Nov-2026 data yet (and
Clarity's CDN 403s scrapers today), it's built feed-agnostic and validated
against archived + mock data, per the agreed approach.

**Files (in `ingestor/`)**
- `clarity_poller.py` — core engine. `FeedSource` interface + `Snapshot`/`LiveRow`;
  `parse_clarity_xml()` (uses the `clarify` lib); `write_snapshot()` (replaces
  live rows per race+state, recomputes vote_share); `run_poller()` (polls, skips
  unchanged versions, logs progress). Includes `LiveClarityFeed` (HTTP, ready for
  Nov) and `ClarityFileFeed` (saved XML).
- `replay_harness.py` — `ReplayFeed` replays a real race from baseline.db by
  revealing precincts in batches; `verify_convergence()` checks live==certified.
- `mock_feed.py` — `MockFeed` synthetic generator with red-mirage ordering.
- `requirements.txt` — added (pandas, clarify, requests).

**Validated**
- Core parse path: parsed real Clarity sample (KY 2014 Sen primary) → 165 rows,
  McConnell leading. ✓
- Replay: GA-2020-President revealed in 12 steps; lead swung D+68k → R+60k → and
  converged EXACTLY to certified (DEM 2,474,507 / REP 2,461,837 / LIB 62,138). ✓
- Mock red mirage: race led R the whole way (peak R+45k) then flipped to D+4,453
  at 100% — converged to ground truth. ✓
- `results_live` cleared back to 0 rows (clean slate); baseline untouched.

**Known limits (for November shakeout, noted in code):**
- Clarity CDN returns 403 to direct requests now; `clarify`'s URL regex predates
  modern version strings. `LiveClarityFeed` is written but needs a hardened
  fetch + real 2026 election_id (not knowable until ~Nov) before live use.
- Real-feed precinct NAME → baseline precinct_id mapping is the genuine live
  challenge (spelling differs by source). Replay sidesteps it (uses baseline ids).
- results_live has no `mode` column, so votes are summed across modes; mode-level
  storage (for richer red-mirage) is a possible future schema add.

**Source data:** real Clarity sample saved at `data/raw/clarity_samples/`
(county.xml, precinct.xml) from the openelections/clarify test fixtures.

**Try it:**
- `python ingestor/replay_harness.py GA president 2020`
- `python ingestor/replay_harness.py PA senate 2024`
- `python ingestor/mock_feed.py`

---

## 2026-06-25 — Phase 1b: multi-year baselines loaded ✅

Extended `etl_baseline.py` to load all five baselines additively (keyed on
`election_year` + `race_type`) and re-ran. DB now holds:

- **Presidents:** 2020 (all 8 states), 2024 (all 8 states — secondary reference)
- **Senate:** 2018, 2020, 2024
- Senate coverage by state: AZ/MI/TX = 2018+2020+2024; GA/NC = 2020;
  **NV/PA/WI = 2018+2024 (the old gap is now filled)**.
- Totals: precincts 72,992 | results_historical 771,198 | county_rollup 3,161.

Spot checks (all correct): GA-2020 Pres anchor still Biden 2,474,507 /
Trump 2,461,837 (PASS); TX-2018 Sen Cruz +215,557 over O'Rourke (R+2.6%);
2024 presidential R sweep across all swing states.

One bug fixed: the QA anchor query had to add `election_year=2020` — Trump
now appears in both 2020 and 2024, so the unfiltered query was summing both.

Senate race picks logged by the run: AZ-2020 = special (Kelly–McSally);
GA-2020 = regular (Ossoff–Perdue); all 2018/2024 races were single regular
generals. 2016 President still optional (not downloaded).

---

## 2026-06-25 — Phase 1 (ETL) ✅ COMPLETE

**Done**
- Built `data\db\baseline.db` from the 2020 President + Senate precinct CSVs
  for the 8 target states (`ingestor/etl_baseline.py`).
- Tables: precincts 33,127 | results_historical 260,427 | county_rollup 1,378
  | results_live 0 (filled in Phase 2).
- QA gate **PASS**: GA 2020 President Biden 2,474,507 / Trump 2,461,837
  (within ±0.1% of certified; 159/159 counties; ~2,656 precincts).

**Coverage**
- President: all 8 states (AZ GA MI NC NV PA TX WI).
- Senate (2020): GA AZ MI NC TX only.

**Decisions**
- QA tolerance = ±0.1% per candidate (MIT precinct data doesn't reconcile
  exactly to certified totals — inherent to the source).
- State filtering uses the exact `state_po` column (a Vermont precinct is
  literally named "GEORGIA_FRA-1").
- Votes summed across voting modes (absentee / early / election-day / provisional).
- Senate race pick: AZ = special (Kelly–McSally); GA = regular (Ossoff–Perdue),
  special (Warnock–Loeffler) logged + skipped.
- MI precinct 9999 keeps its −1 Biden adjustment (official correction row).

**Brief corrections**
- PA does NOT have a 2020 Senate race — fixed the coverage line in
  `HANDOVER_BRIEF.md` (was wrongly marked PA ✅).

**New data to acquire (decided with user)**
- 2024 President (secondary reference, all states).
- 2024 Senate (fills PA, NV, WI in one file).
- 2018 Senate (Texas Cruz–O'Rourke baseline).
- 2016 President — optional, for long-term trend lines.

**Download links confirmed (2026-06-25)** — verified via Dataverse API; 2020
DOIs cross-checked against the brief and match:
- 2024 President : doi:10.7910/DVN/XDJYKC
- 2024 Senate    : doi:10.7910/DVN/ZCM3BN  (PA + NV + WI)
- 2018 Senate    : doi:10.7910/DVN/DGNAFS  (TX Cruz–O'Rourke)
- 2016 President : doi:10.7910/DVN/LYWX3D  (optional)
- Page pattern: https://dataverse.harvard.edu/dataset.xhtml?persistentId=<doi>
- Drop CSVs in data\raw\ ; then re-run / extend etl_baseline.py (additive).

**Open for next session**
- User to download the above CSVs into data\raw\, then load them.
- Go-ahead for Phase 2 (Clarity ENR live poller)?
