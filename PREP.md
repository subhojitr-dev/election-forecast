# PREP.md — Election-Night Live Data Readiness Plan

**Goal:** be able to pull, parse, map, and display **all** live results for the 8
target states on **Election Day — Tuesday, November 3, 2026.**
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

## 1. Per-state live feed status (CONFIRM in the audit — best current understanding)

| State | Live ENR system | Scope | Ballot-mode in feed? | Ingestor needed | Test window |
|-------|-----------------|-------|----------------------|-----------------|-------------|
| **GA** | **Clarity** | statewide | Yes (runoff file proves it) | ✅ have parser | live GA special (primary past) |
| **PA** | **Clarity** | county-by-county (Allegheny…) | likely | per-county discovery | primary past |
| **TX** | **Clarity** | county-by-county (Tarrant, Denton…) | varies | per-county discovery | primary past |
| **MI** | **Clarity** (counties) + state aggregator | county + state | absentee (AV) reported | per-county discovery | **MI primary Aug 4** |
| **AZ** | **Own** (AZ SOS / county sites; Maricopa own) | state + county | usually (early vs day-of) | **build** | **AZ primary Jul 21** |
| **NV** | **Own** (NV SOS) | statewide | usually (mail/early) | **build** | primary past (Jun 9) |
| **WI** | **Own** (county clerks / WEC) | county | limited live | **build** | **WI primary Aug 11** |
| **NC** | **Own** (NCSBE ENR) | statewide | yes (by method) | **build** | primary past |

**Takeaway:** ~half are reachable via Clarity (GA statewide; PA/TX/MI per-county), the
other ~half (**AZ, NV, WI, NC**) need their own ingestors. This is the biggest build item.

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

## 3. Timeline (now → Nov 3, 2026)

**Now → mid-July (foundation + first live test)**
- [ ] Solve the Clarity 403 against a *currently-live* Clarity election (Issue #1).
- [ ] **Per-state feed audit (Issue #8):** for each of the 8, pull a sample/live detail
      file and record: system (Clarity/own), scope (state/county), does it carry
      vote-type subtotals, live vs final-only, URL pattern, ID scheme.
- [ ] Stand up the non-Clarity fetcher skeletons (AZ, NV, WI, NC).

**Jul 21 — Arizona primary (LIVE TEST · non-Clarity)**
- [ ] Pull AZ live ENR end-to-end; validate fetch + parse + a first AZ precinct crosswalk.
- [ ] Confirm whether AZ exposes early/election-day splits live.

**Aug 4 — Michigan primary (LIVE TEST · county-level Clarity)**
- [ ] Exercise the per-county Clarity discovery + fetch for MI counties.
- [ ] Build/validate the MI precinct crosswalk; check absentee (AV) reporting.

**Aug 11 — Wisconsin primary (LIVE TEST · non-Clarity)**
- [ ] Pull WI live ENR; validate parser + crosswalk; gauge how much is live vs canvass.

**Aug → Sep (harden against real feeds)**
- [ ] Finalize precinct crosswalks for tested states; county fallback everywhere.
- [ ] Build per-state "bucket name" normalization (advance/early/absentee/mail/UOCAVA).
- [ ] For GA statewide-Clarity: test against any live GA special/municipal election.

**Early–mid October**
- [ ] Election-ID auto-discovery for all 8 states.
- [ ] Non-Clarity ingestors complete + parsers validated for NV, NC (no summer primary
      to test → use their most recent live election / archives).

**~2 weeks before (mid–late October)**
- [ ] States publish the Nov general to their ENR (0% reported). Capture the **real
      2026 election IDs** for all 8.
- [ ] Full dry run end-to-end against the live (empty) feeds: fetch → parse → crosswalk
      → analytics → dashboard, all 8 states × President + Senate.

**Election week (late Oct → Nov 2)**
- [ ] Final rehearsal; set polling intervals (~60s); redundancy + monitoring + safe
      restart (full snapshots self-heal).

**Nov 3 — Election Night**
- [ ] Go live: Phase 2 poller replaces the "Next Batch" stepper (same data path).

---

## 4. Primary test calendar (what each buys us)

| Date | State | Tests | Feed type |
|------|-------|-------|-----------|
| **Jul 21** | Arizona | non-Clarity fetch + parse + crosswalk | own system |
| **Aug 4** | Michigan | per-county Clarity discovery + crosswalk | county Clarity |
| **Aug 11** | Wisconsin | non-Clarity fetch + live-vs-canvass behavior | own system |

GA/PA/TX/NV/NC primaries are already past (test those against live specials or archives).

---

## 5. Risk register

| Risk | Issue | Mitigation |
|------|-------|------------|
| Clarity 403 blocks fetch | #1 | browser-faithful session; headless-browser fallback; test on live primary |
| Live precinct → baseline mapping | #3 | crosswalk from 2026 primaries; county fallback for unmatched |
| Non-Clarity states need bespoke ingestors | #8 | build + test AZ/NV/WI/NC against summer primaries |
| Ballot-mode not published live (esp. military/UOCAVA) | #8 | mode is OPTIONAL — defaults to 'all', geography-only fallback |
| Election IDs only known ~2 wks out | — | auto-discovery + mid-Oct dry run |

---

## 6. Confidence (today)

- **Data exists in Clarity feeds:** high (~80%) — proven by the GA mode columns.
- **Reliably pull all 8 states live, this November:** moderate (~50–60% today), rising
  as we beat the 403 and build the non-Clarity ingestors and crosswalks.
- **Military/UOCAVA as a live bucket:** low — usually only in the final canvass.

The single biggest de-risker is **testing against the real July/August primaries** —
that converts election-night unknowns into a calm, fixable checklist now.
