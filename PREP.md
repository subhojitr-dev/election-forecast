# PREP.md — Election-Night Live Data Readiness Plan

**Goal:** be able to pull, parse, map, and display **all** live results for the 8
target states — **plus SC, added 2026-07-17** as a 9th (its Senate seat is up in 2026
too) — on **Election Day — Tuesday, November 3, 2026.**
**Today:** 2026-06-28 (~18 weeks out). Owner: project.
**Read with:** `Issues.md` (#1 fetch, #3 crosswalk, #8 feed audit) and `HANDOVER_BRIEF.md`.

---

## 0. The core reality (read this first)

- **Harvard Dataverse / MIT is NOT a live feed.** It is the *historical baseline*
  (2018/2020/2024 + the GA 2021 runoff) — published months-to-years after the fact.
  It will **not** contain any 2026 results on election night. We use it only as the
  "what happened last time" yardstick.
- **Live results come from each state's own Election Night Reporting (ENR) system.**
  Some are Clarity (the system we've built around); several are **not** and need
  bespoke ingestors.
- **Three things must all work** to get a state's live data:
  1. **Reach the feed** (beat the Clarity 403 / build a fetcher per non-Clarity state) — Issue #1
  2. **Discover the election ID** (only published ~2 weeks before the election)
  3. **Map live precincts → our baseline** (the crosswalk) — Issue #3
  - …plus an **optional 4th layer**: the **ballot-mode breakdown** (mail/early/
    election-day/military) — Issue #8. Built to degrade gracefully if absent.

---

## 1. Per-state live feed status — UPDATED 2026-07-17 (was all wrong — Clarity assumption
## busted; every state we've checked runs its OWN system. See FEED_AUDIT.md for full detail.)

| State | Live ENR system | Scope | Ballot-mode in feed? | Ingestor | Status |
|-------|-----------------|-------|----------------------|----------|--------|
| **NC** | **Own** — NCSBE dashboard | statewide, open S3 bulk file | ✅ yes (by method) | `nc_live_feed.py` | ✅ **WIRED**, exact match to certified |
| **GA** | **Own** — Enhanced Voting (was Clarity) | statewide + per-county | totals only | `ga_live_feed.py` | ✅ **WIRED**, exact match to certified |
| **PA** | **Own** — electionreturns.pa.gov (AngularJS/API) | statewide, 1 call = all 67 counties | ✅ yes (election-day/mail/provisional) | `pa_live_feed.py` | ✅ **WIRED**, exact match to certified |
| **AZ** | **Own** — cdn1.arizona.vote (open CDN) | statewide, 1 call = all 15 counties x all races | totals only | `az_live_feed.py` | ✅ **WIRED**, primary-night-ready **Jul 21** |
| **MI** | **Own** — mvic.sos.state.mi.us (Cloudflare; needs HEADED browser) | statewide bulk ZIP, every precinct x every office | totals only | `mi_live_feed.py` (Playwright) | ✅ **WIRED**, primary-night-ready **Aug 4** |
| **TX** | **Own** — results.texas-election.com (Cloudflare WAF; headless Playwright is enough) | statewide, 1 call = all 254 counties x all races, keyed by FIPS directly | totals only | `tx_live_feed.py` (headless Playwright) | ✅ **WIRED**, exact match to certified |
| **SC** | **Own** — enr-scvotes.org (classic Clarity, STILL ALIVE — the one exception; plain httpx, no Cloudflare) | statewide, 1 call = all 46 counties x all contests | totals only | `sc_live_feed.py` | ✅ **WIRED**, NEW 9th state (baseline built from scratch), exact match to the real June 2026 primary |
| **NV** | unknown — not mapped | — | — | not started | ⚪ **DEPRIORITIZED** — no 2026 race (Class 3, next up 2028) |
| **WI** | ⚠️ **NONE statewide** | 72 county clerk sites | ❌ minimal live | AP priced + re-checked WI-specific — **still SKIPPED** (quote-only, no shortcut) | ⚪ **DEPRIORITIZED** — no 2026 race either (same reason as NV); also the hardest case regardless |

**Takeaway:** the original "half are Clarity" model was wrong — Clarity's old endpoints are
confirmed dead across GA/PA/AZ/MI/TX. **SC is the one exception** — added as a NEW 9th
state (never one of the original 8) specifically because its Clarity ENR is still fully
alive, and its Senate seat is up in 2026 too. Every state mapped so far runs its own
system (or, for SC, the still-live classic one), discoverable via real-browser network
inspection (Playwright or a controlled Chrome). 6/8 original + SC wired; NV+WI
deprioritized (no 2026 race — see timeline below); WI remains the one true hard case
whenever it's picked back up.

---

## 2. What "pull all the live data" actually requires (the 5 layers)

1. **Fetch** — Clarity: beat the 403 (browser-faithful session, or headless-browser
   fallback). Non-Clarity: one fetcher per state ENR (HTML/JSON/CSV as published).
2. **Election-ID discovery** — IDs are only posted days before; build auto-discovery
   (Clarity `current_ver.txt`; per-state equivalents).
3. **Parse** — Clarity XML parser ✅ done. Non-Clarity parsers: build + validate per state.
4. **Precinct crosswalk** (Issue #3) — map 2026 live precinct names → baseline ids;
   county fallback for unmatched. Build from the 2026 primaries.
5. **Ballot-mode** (Issue #8, optional) — read vote-type subtotals if present; else
   default `mode='all'` (already wired so nothing breaks).

---

## 3. Timeline (now → Nov 3, 2026) — UPDATED 2026-07-17

**⚠️ SUPERSEDED ASSUMPTION:** everything below originally assumed a precinct-name
CROSSWALK (Issue #3) was required. **DECISION 2026-06-30: county-level v1 makes the
crosswalk MOOT** — we join live-to-baseline on county FIPS (`{ST}-{fips}-CTY`), which is
stable year-to-year and needs no name-matching. So "crosswalk" items below are done-by-
design, not a build task. See CONTEXT.md's "county-pseudo-precinct pattern" for the
mechanism actually used by every wired state (NC/GA/PA/AZ/MI/TX).

**Now → mid-July (foundation + first live test)** — ✅ DONE, but not as originally planned:
- [x] ~~Solve the Clarity 403~~ — REFRAMED: Clarity is dead/decommissioned everywhere we
      checked; the real task was per-state discovery of each state's CURRENT system
      (Enhanced Voting, or a bespoke state-run site), not beating a block.
- [x] **Per-state feed audit (Issue #8):** done for GA/NC/PA/AZ/MI/TX — see FEED_AUDIT.md.
- [x] Fetchers built + validated for NC, GA, PA, AZ, MI, TX (all 6 match certified exactly).

**Jul 21 — Arizona primary (LIVE TEST)**
- [x] AZ live ingest built + validated against the 2024 general (exact match, 15/15
      counties); electionId (68) confirmed live now, mechanics smoke-tested at 0%.
- [ ] **On the night:** run the runbook in CONTEXT.md; confirm real vote/precinct numbers
      move as counties report (AZ's 2026 primary has no President/Senate race, so this is
      a mechanics validation using Governor, not a manifest data load).

**Aug 4 — Michigan primary (LIVE TEST)**
- [x] MI live ingest built + validated against the 2024 general (exact match, 83/83
      counties) — via a headed Playwright browser + a bulk-ZIP endpoint (not per-county
      Clarity — that assumption was wrong; MI runs its own system).
- [ ] **On the night:** the election isn't in MI's dropdown yet (checked 2026-07-17) —
      poll `mi_live_feed.py "8/4/2026" senate` in the days before to catch it appearing,
      then run the runbook in CONTEXT.md. Needs a machine with a real display.

**Aug 11 — Wisconsin primary** — ⚪ **DEPRIORITIZED 2026-07-17.** WI has no Senate or
President race on the Nov 3, 2026 ballot (Class 3 seat, next up 2028) — confirmed against
`api/elections.py`. Not gating this November; Aug 11 is a free test window IF picked back
up, not a deadline. If/when resumed: no statewide feed exists — likely a per-county build
(top ~8-10 counties by population) or a deliberate coarser compromise; AP Elections API
re-priced WI-specific per user request, still quote-only, no shortcut found.

**Aug → Sep (harden against real feeds)**
- [x] Wire TX — done 2026-07-17 (own system, headless Playwright, cleanest join of any
      state — one call, 254 counties, keyed by FIPS directly).
- [x] ~~NV~~ — DEPRIORITIZED 2026-07-17, same reason as WI (no 2026 race, Class 3/2028).
- [ ] Wire WI (or land on a deliberate compromise) — only if picked back up; not urgent.
- [ ] Add SC if it turns out to be easy (Class-2 Graham seat, `enr-scvotes.org`).
- [x] ~~Precinct crosswalks~~ — moot, see note above.
- [x] ~~Bucket-name normalization~~ — done per-state as each feed was wired (PARTY maps
      in each `*_live_feed.py`; MODE_COLS-style maps for NC/PA's ballot-mode splits).

**Early–mid October**
- [ ] Election-ID auto-discovery for any state that still needs it on election night
      (AZ's is pre-published/stable; MI/TX auto-discover already; check WI/NV whenever
      they're picked back up).

**~2 weeks before (mid–late October)**
- [ ] States publish the Nov general to their live systems (0% reported). Capture the
      **real 2026 election IDs** for whichever states need fresh discovery.
- [ ] Full dry run end-to-end: fetch → parse → county-pseudo mapping → analytics →
      dashboard, all wired states × President + Senate.

**Election week (late Oct → Nov 2)**
- [ ] Final rehearsal; set polling intervals; redundancy + monitoring + safe restart
      (full snapshots self-heal).

**Nov 3 — Election Night**
- [ ] Go live: the `*_live_feed.py` scripts (or a scheduler wrapping them) replace the
      "Next Batch" stepper (same data path — zero analytics/UI changes).

---

## 4. Primary test calendar (what each buys us)

| Date | State | Tests | Status |
|------|-------|-------|--------|
| **Jul 21** | Arizona | mechanics: uploadId/precinct-count/vote changes live | ✅ code-ready, awaiting the night |
| **Aug 4** | Michigan | headed-Playwright + bulk-ZIP mechanism live; election-id discovery | ✅ code-ready, awaiting the night |
| **Aug 11** | Wisconsin | whatever approach we land on, IF picked back up (no longer urgent) | ⚪ deprioritized (no 2026 race) |

GA/PA/NC/TX primaries are already past — those 4 were validated against the 2024 general
archive instead (the only option once a primary has passed). NV/WI deprioritized (no 2026
race for either — see Issue #8 update in Issues.md).

---

## 5. Risk register — UPDATED 2026-07-17

| Risk | Status | Mitigation |
|------|--------|------------|
| ~~Clarity 403 blocks fetch~~ | 🟢 moot | Clarity confirmed dead everywhere checked — not the actual obstacle |
| ~~Live precinct → baseline mapping~~ | 🟢 moot | county-level v1 (FIPS join) eliminated this — see Issues.md #3 |
| MI's Cloudflare block | 🟢 resolved | headed Playwright + webdriver mask passes; headless does not |
| TX's Cloudflare WAF block | 🟢 resolved | headless Playwright passes (confirmed identical to headed — no display needed) |
| Election IDs not always pre-known | 🟡 ongoing | AZ: pre-published. MI/TX: auto-discovered, not live yet for Aug 4/whenever needed. NV/WI: deprioritized, unknown until picked back up |
| Wisconsin has no statewide feed | 🟡 open but not urgent | doesn't gate Nov 2026 (no race) — see the WI scoping note (Issues.md / CONTEXT.md); revisit ahead of 2028 |
| NV/WI have no 2026 race | 🟢 resolved (by deprioritizing) | confirmed against `api/elections.py`; not a build risk, just deferred to 2028 prep |
| Ballot-mode not published live everywhere | 🟢 handled | mode is OPTIONAL — defaults to 'all'; NC + PA have it, GA + AZ + MI + TX don't (fine) |

---

## 6. Confidence (today) — UPDATED 2026-07-17

- **7 states wired + validated** (not just within tolerance): NC, GA, PA, AZ, MI, TX — the
  6 of 8 original targets — PLUS **SC, a NEW 9th state** added because its Senate seat is
  up in 2026 too. AZ and MI are additionally primary-night-ready for Jul 21 / Aug 4.
- **Reliably pull every state that actually gates Nov 3, 2026:** HIGH — NC, GA, MI, TX, SC
  (the full `general2026` senate list) are all wired and validated. PA and AZ are also
  wired (ahead of their own 2028 races, serving as mechanism-proving + 2028 prep).
- **NV and WI:** deprioritized, not a risk to Nov 2026 — neither has a race on this
  November's ballot (confirmed against `api/elections.py`). Revisit ahead of `general2028`.
  Wisconsin remains the one place the "find the bespoke system" pattern may genuinely not
  apply (no state-run aggregator exists) — worth extra lead time whenever it's picked up.
- **Military/UOCAVA as a live bucket:** low — usually only in the final canvass. Not
  blocking (mode defaults to 'all').

The single biggest de-risker was **testing the discovery methodology against real
government sites** (not just desk research) — every state so far had an actual open data
source once someone looked at real network traffic instead of assuming Clarity. The second
biggest de-risker was **checking each state's actual ballot before spending build time on
it** — NV and WI turned out to have nothing to track for 2026, caught only by checking
`api/elections.py` directly rather than assuming all 8 states matter equally.
