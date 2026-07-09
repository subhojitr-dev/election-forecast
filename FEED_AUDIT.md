# FEED_AUDIT.md — Per-state live ENR feed audit

**Purpose:** for each of the 8 target states, confirm the live Election Night
Reporting (ENR) system, its scope, the URL, and whether it publishes the
**ballot-mode breakdown** (mail/early/election-day) live. This turns election-night
unknowns into a checklist now. Started 2026-06-28. Pairs with PREP.md.

> Reminder: **Dataverse/MIT is NOT a live feed** — it's the historical baseline.
> Live data on the night comes only from these systems.

---

## Per-state findings (Round 1 — desk research)

| State | Live ENR system | Scope | URL | Mode breakdown live? | Ingestor | Status |
|-------|-----------------|-------|-----|----------------------|----------|--------|
| **GA** | **Enhanced Voting** (moved off Clarity!) | statewide + per-county | **results.sos.ga.gov** · state `/api/elections/Georgia/{EID}/data`, county `/api/elections/{county-shortName}/{EID}/data` (both OPEN, plain httpx) | mode='all' only (no live split found; totals only) | ✅ **WIRED END-TO-END 2026-07-06** (ga_live_feed.py) | **strong** |
| **NC** | **Own — NCSBE dashboard** | statewide, ~5–10 min | er.ncsbe.gov | ✅ **yes — "Results by Voting Method" tab** | build (clean) | **best-case** |
| **AZ** | **Own — AngularJS SPA + open CDN** | statewide + county | results.arizona.vote (SPA) → data on **cdn1.arizona.vote** | ⚠️ to confirm | build (2 open paths) | **mapped 2026-07-06** |
| **NV** | **Own — NV SoS** | statewide | Results.NV.gov · nvsos.gov/electionresults | ⚠️ to confirm | build | medium |
| **PA** | **Clarity** (Scytl) | county-by-county | results.enr.clarityelections.com/PA/<county> | likely (per-county) | per-county discovery | medium |
| **TX** | **Clarity** (Scytl) | county-by-county | results.enr.clarityelections.com/TX/<county> | varies by county | per-county discovery | medium |
| **MI** | MI SoS (mvic) — Cloudflare; old systems dead | county + state | mvic.sos.state.mi.us (Cloudflare) · michigan.gov/sos (Akamai) | ⚠️ | **harder** — headless Playwright BLOCKED by Cloudflare (2026-07-06); needs non-headless/stealth OR find open bulk-download OR per-county EV | **hard** |
| **WI** | ⚠️ **NONE statewide** | 72 county clerk sites | elections.wi.gov/wisconsin-county-election-websites | ❌ minimal live | **hardest** — scrape 72 sites or use an aggregator (AP) | **risk** |

---

## Key takeaways

1. **NC is the easiest + richest** — a real-time dashboard that already breaks results
   out **by voting method**. Build a clean JSON/table ingestor for it; great for the
   ballot-mode feature.
2. **GA is solid** — statewide Clarity, parser already built, mode columns confirmed
   (the runoff file). The remaining work is the 403 fetch + precinct crosswalk.
3. **PA / TX / MI are Clarity but county-by-county** — need per-county election-ID
   discovery (one Clarity instance per county), not one statewide pull.
4. **AZ / NV are their own statewide systems** — buildable; **confirm live mode subtotals**
   (both states lean heavily on early/mail, so the data likely exists).
5. **WI is the real problem** — **no statewide ENR feed at all.** Unofficial results come
   from **72 county clerk websites**, aggregated by the **AP**. Options: (a) license/consume
   an **AP results feed** (covers all states uniformly — worth pricing), (b) build 72
   county scrapers (heavy), or (c) accept county-level WI from an aggregator with no live
   mode breakdown. Decide early.

---

## Remaining to confirm (Round 2 — against live primaries)

- [ ] **AZ** (primary **Jul 21**): pull results.arizona.vote live — confirm precinct grain + whether early/election-day split is exposed live.
- [ ] **MI** (primary **Aug 4**): exercise per-county Clarity discovery + the AV (absentee) breakdown.
- [ ] **WI** (primary **Aug 11**): test the county-clerk-site / AP path; gauge how much is live vs canvass-only.
- [ ] **NC**: hit er.ncsbe.gov's data export/API; confirm the "by voting method" data is machine-readable live.
- [ ] **GA/PA/TX/NV**: primaries are past — test against a live special/municipal, or the most recent archived election.
- [ ] **Cross-cutting:** price an **AP Elections API** subscription — it would cover all 8 states uniformly (incl. WI) and likely carries vote-method splits, potentially replacing several bespoke ingestors.

---

## Implication for the build

- Mode is already **optional** in the code (`results_live.mode` defaults to 'all'), so
  states without a live mode breakdown degrade gracefully.
- Priority order to build ingestors: **NC** (clean + mode) → **AZ/NV** (own, statewide)
  → **PA/TX/MI** (per-county Clarity) → **WI** (hardest; consider AP feed).
- Strongly consider an **AP Elections API** as the primary source with the bespoke
  ingestors as backup — it may collapse most of this work into one integration.
