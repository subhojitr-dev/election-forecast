# FEED_AUDIT.md — Per-state live ENR feed audit

**Purpose:** for each target state, confirm the live Election Night
Reporting (ENR) system, its scope, the URL, and whether it publishes the
**ballot-mode breakdown** (mail/early/election-day) live. This turns election-night
unknowns into a checklist now. Started 2026-06-28. Pairs with PREP.md.
**Updated 2026-07-17:** SC added as a 9th state (not one of the original 8 — its Senate
seat is up in 2026 too, same class as GA/MI/NC/TX; see PROGRESS.md for the baseline-load
story, which is a different kind of work than the live-feed wiring below).

> Reminder: **Dataverse/MIT is NOT a live feed** — it's the historical baseline.
> Live data on the night comes only from these systems.

---

## Per-state findings (Round 1 — desk research)

| State | Live ENR system | Scope | URL | Mode breakdown live? | Ingestor | Status |
|-------|-----------------|-------|-----|----------------------|----------|--------|
| **GA** | **Enhanced Voting** (moved off Clarity!) | statewide + per-county | **results.sos.ga.gov** · state `/api/elections/Georgia/{EID}/data`, county `/api/elections/{county-shortName}/{EID}/data` (both OPEN, plain httpx) | mode='all' only (no live split found; totals only) | ✅ **WIRED END-TO-END 2026-07-06** (ga_live_feed.py) | **strong** |
| **NC** | **Own — NCSBE dashboard** | statewide, open S3 bulk file, ~5–10 min | er.ncsbe.gov | ✅ **yes — election-day/early/mail/provisional** | ✅ **WIRED END-TO-END 2026-07-06** (nc_live_feed.py + nc_ingestor.py) | **best-case** |
| **AZ** | **Own — AngularJS SPA + open CDN** | statewide, one call returns all 15 counties x all races | results.arizona.vote (SPA, Cloudflare) → data on **cdn1.arizona.vote** (OPEN, plain httpx, no Cloudflare) | totals only, no live split found | ✅ **WIRED END-TO-END 2026-07-17** (az_live_feed.py); electionIds pre-published & stable, no discovery needed | **strong** |
| **NV** | **Own — NV SoS** | statewide | Results.NV.gov · nvsos.gov/electionresults | ⚠️ to confirm | ⚪ **DEPRIORITIZED 2026-07-17** — no Senate/President race on NV's Nov 2026 ballot (Class 3 seat, next up 2028); revisit for `general2028` prep | low urgency |
| **PA** | **Own — electionreturns.pa.gov** (AngularJS SPA, open ASP.NET API) | statewide, one call per race returns all 67 counties | electionreturns.pa.gov · `/api/ElectionReturn/GetCountyBreak?officeId=&electionid=&electiontype=` (OPEN, plain httpx) | ✅ **yes — ElectionDayVotes/MailInVotes/ProvisionalVotes** | ✅ **WIRED END-TO-END 2026-07-17** (pa_live_feed.py) | **strong** |
| **TX** | **Own — results.texas-election.com** (Angular SPA; Cloudflare WAF blocks plain httpx, but headless Playwright passes) | statewide, one call returns all 254 counties x all races, keyed by 5-digit county FIPS | `/static/data/election/{electionId}/{version}/County.json` (electionId auto-discovered via `ElectionConstants_404.json`) | totals only, no live split found | ✅ **WIRED END-TO-END 2026-07-17** (tx_live_feed.py, headless Playwright — no display needed, unlike MI) | **strong** |
| **MI** | **Own — mvic.sos.state.mi.us** (Cloudflare blocks headless + plain httpx; a HEADED browser passes) | statewide bulk ZIP, every precinct x every office in one download | `/VoteHistory/GetPrecinctResultsFile?electionId=` (tab-delimited files inside, documented readme.txt — same shape as NC's bulk file) | mode='all' (no live split found) | ✅ **WIRED END-TO-END 2026-07-17** (mi_live_feed.py, via headed Playwright); electionId NOT pre-published — auto-discovered from `#ElectionDateId` each run | **strong (mechanism); Aug 4 id not live yet**|
| **WI** | ⚠️ **NONE statewide** | 72 county clerk sites | elections.wi.gov/wisconsin-county-election-websites | ❌ minimal live | ⚪ **DEPRIORITIZED 2026-07-17** — no Senate/President race on WI's Nov 2026 ballot either (Class 3, next up 2028); AP re-priced for WI specifically, still quote-only, no shortcut found | **hardest, low urgency** |
| **SC** | **Own — enr-scvotes.org** (classic Clarity/SOE Software — the only state where this old mechanism is STILL ALIVE, plain httpx, no Cloudflare/WAF at all) | statewide, one call returns all 46 counties x all contests | `/SC/{electionId}/current_ver.txt` (discovery) → `/SC/{eid}/{version}/json/ALL.json` (⚠️ excludes a pseudo-county literally named `"-1"` or totals double) | totals only, no live split found | ✅ **WIRED END-TO-END 2026-07-17** (sc_live_feed.py) — NEW 9th state, baseline built from scratch (`etl_sc_baseline.py`) | **strong; simplest state so far** |

---

## Key takeaways — UPDATED 2026-07-17 (Round 1's Clarity assumptions were wrong; see below)

1. **Clarity is dead for every state we've checked.** GA, PA, AZ, and MI all turned out to
   run their OWN bespoke systems, not per-county Clarity instances — the original "half are
   Clarity" framing (Round 1, desk research only) didn't survive contact with the real
   sites. The one durable lesson: **verify with real network traffic, not documentation
   assumptions** — every state so far had an actual open (or headed-browser-reachable)
   data source once someone looked.
2. **NC, GA, PA, AZ, MI, TX, SC are all WIRED END-TO-END** and validated to the EXACT
   certified result (2024 general for the original 6; SC validated against its own June
   2026 primary since that's the only archived election reachable on its live system) —
   see PROGRESS.md for the discovery story on each. NC and PA additionally expose a live
   ballot-mode split; GA/AZ/MI/TX/SC are totals-only (mode='all', which the schema already
   handles gracefully).
3. **MI is the one state where the block was real** — Cloudflare rejects both plain httpx
   and headless Playwright, but a HEADED Chromium (navigator.webdriver masked) passes
   cleanly. This is the only state that needs a browser at ingest RUNTIME, not just for
   one-time discovery.
4. **SC turned out to be a genuine exception to takeaway #1** — its Clarity instance
   (enr-scvotes.org) is the ONE place the classic pre-2026 mechanism (current_ver.txt
   discovery) is still fully alive, not decommissioned. A useful reminder: "Clarity is
   dead" was true for every state we'd checked so far, but that's an empirical pattern,
   not a law — always verify per-state rather than assuming based on other states' results.
5. **WI (and NV) are DEPRIORITIZED, not just hard.** Checked `api/elections.py` directly:
   neither has a Senate OR President race on the Nov 3, 2026 ballot (both Senate seats are
   Class 3, next up 2028) — so neither gates this November at all. WI is additionally the
   one genuinely hard case — **no statewide ENR feed at all**, unofficial results come from
   **72 county clerk websites**, each potentially its own vendor/format, a fundamentally
   different (harder) problem than "find the one bespoke system per state." AP Elections
   API was priced project-wide (2026-06-30, rejected as too costly) and re-checked
   WI-specific (2026-07-17, still quote-only, no shortcut found). If picked up later:
   (a) build scrapers for a handful of big counties (Milwaukee, Dane, Waukesha, etc. —
   covers a large share of the vote even if not all 72), (b) find a common vendor several
   counties share, (c) accept a coarser/delayed WI signal as a deliberate compromise.
6. **TX turned out to be the cleanest state yet by mechanism** — one call, all 254
   counties, keyed by FIPS directly (no name-matching at all), and only needs headless
   Playwright (no display, unlike MI). **SC is the cleanest state OVERALL** — same
   one-call-gets-everything shape, plain httpx with zero bot-mitigation of any kind, and
   a stable, well-documented discovery mechanism (current_ver.txt).

---

## Remaining to confirm

- [x] ~~AZ~~ — wired 2026-07-17; primary-night mechanics smoke-tested against the live
      2026 primary structure (0% reporting, 4 days out).
- [x] ~~MI~~ — wired 2026-07-17; election-id discovery confirmed NOT to have the Aug 4
      primary listed yet (expected — will appear closer to the night).
- [x] ~~NC/GA/PA/TX~~ — wired (NC/GA 2026-07-06, PA/TX 2026-07-17).
- [x] ~~SC~~ — wired 2026-07-17 as a NEW 9th state; validated against the real June 2026
      primary (exact statewide + per-candidate match); real 2026 nominees (Graham/Andrews)
      now in the manifest. electionId for the Nov general not yet known — SC's
      `elections.json` is empty between elections; discover via browser closer to the night
      (same situation as MI).
- [x] ~~NV, WI~~ — DEPRIORITIZED 2026-07-17 (no 2026 race for either; see takeaway #5).
- [x] ~~AZ on the actual night (Jul 21)~~ — PASSED. `uploadId` incremented repeatedly,
      precincts/votes climbed off zero after poll close. See PROGRESS.md 2026-07-21.
- [x] ~~MI on the actual night (Aug 4)~~ — **FAILED for the state system specifically.**
      See Round 2 below — this is the important finding.

---

## Round 2 — LIVE CADENCE, not just mechanism (added 2026-08-05)

Round 1 confirmed each state's live feed *mechanism* works and matches certified
results. It did NOT confirm each state actually delivers data **during a real live
count**, on a real election night, at a useful pace — that's a completely different
question, and Round 1's "strong" ratings above should not be read as an answer to it.
MI's own Round 1 rating was "strong (mechanism)" right up until Aug 4 proved the
mechanism was pointed at a system that doesn't publish live at all. **Don't repeat
that mistake for GA/NC/TX/SC** — below is what's actually been verified about each
state's real cadence, either firsthand (best) or via retrospective research on that
state's own most recent real primary (second-best; still real evidence, not
documentation).

| State | Real cadence evidence | Verdict |
|---|---|---|
| **MI** | Firsthand, Aug 4, 2026: state system (`mvic.sos.state.mi.us/votehistory`) had **zero data 11 hours after polls closed** — confirmed via Votebeat's own reporting to be structural (only shows a county once 100% done), not a one-off delay. | ❌ **CONFIRMED NOT VIABLE for Nov 3** — do not rely on `mi_live_feed.py`'s state-system path. See PROGRESS.md 2026-08-04/2026-08-05, and the county-level fallback (Wayne/Kent/Washtenaw/Livingston) built the same night. |
| **SC** | Firsthand — validated live in June 2026 (SC's own primary), matched exactly. | ✅ **Directly proven**, not just documented. Strongest evidence of the 5. |
| **NC** | Retrospective, NC's own March 3, 2026 primary: multiple news sources confirm results "became available at different times... as soon as all votes were counted in each county on the evening of March 3" — same night, not next-day. Consistent with NC's own documented "5-10 min" cadence. Did NOT find an exact "first data at X:XX PM" timestamp. | 🟡 **Good secondhand evidence**, same-night confirmed, precise timing not pinned down. |
| **GA** | Retrospective, GA's own May 19, 2026 primary: "Results were updated immediately as they arrived from the Georgia Secretary of State." Consistent with GA/AZ sharing the same underlying live-updating platform family (AZ proven firsthand Jul 21). | 🟡 **Good secondhand evidence + architectural similarity to a proven system (AZ).** |
| **TX** | Retrospective, TX's own March 3, 2026 primary (same day as NC): confirmed a **real, documented mess** ("2026 primary elections start off with a Texas-sized mess" — Votebeat) — hand-count delays in Gillespie/Eastland counties (counting into the early-morning hours), and large counties (Harris/Dallas/Tarrant) acknowledged as slower to report. BUT an early-voting batch does post shortly after polls close (a real partial signal, unlike MI's total silence), and the Senate outcome was determined without needing a next-day wait. | 🟠 **Moderate risk, bounded.** Better than MI (gets an immediate partial signal, resolves same night/next morning), worse than NC/GA/SC (real documented delays for specific counties/races). Worth extra attention in the Nov 3 dry run, and possibly a county-level fallback plan for TX's biggest counties too, not just MI's. |

**Bottom line: MI is not a fluke to route around with a patch — treat every state's
"live feed works" claim as unproven until it's tested against a REAL count in
progress**, the same way MI's "strong (mechanism)" rating didn't survive contact
with Aug 4. SC and AZ are the only two states in this project with genuine firsthand
proof. NC and GA have good secondhand evidence. TX has real, documented risk that
deserves the same kind of attention MI got — not urgent to fix now (no near-term TX
primary to test against), but worth planning for before Nov 3, e.g. identifying
TX's biggest counties' own results sites now, the same way MI's fallback was found,
rather than reactively on election night.

---

## Implication for the build

- Mode is already **optional** in the code (`results_live.mode` defaults to 'all'), so
  states without a live mode breakdown degrade gracefully — proven true for GA/AZ/MI/TX/SC.
- The county-pseudo-precinct pattern (`{ST}-{fips}-CTY`) has now been proven across 7
  different state systems (open JSON API, open CDN, bulk ZIP, S3 bulk file, AngularJS/API,
  classic Clarity) with ZERO changes to the analytics engine — strong evidence the pattern
  generalizes, including to a brand-new state added mid-project (SC).
- AP Elections API was priced and skipped (see takeaway #5) — not revisiting unless
  WI turns out to be intractable without it.
- Adding a state NOT in the original 8 (SC) is meaningfully MORE work than wiring a live
  feed for an existing one — it needs its own baseline ETL first (see
  `ingestor/etl_sc_baseline.py` as the template), plus small required additions to
  `api/main.py`'s `EV`/`STATE_NAMES` dicts (the states endpoint crashes without them).
