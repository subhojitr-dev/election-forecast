# Next-session prompt — Election Forecast (LIVE-READINESS)

Paste the block below to start the next session.

---

We're continuing the **Election Forecast Dashboard** (`C:\Users\subho\election-forecast`).
Read `CONTEXT.md` first (the "🔴 NEXT SESSION — START HERE → LIVE-READINESS" section has
the full current state), then this prompt.

**Where we are:** dashboard is deployed & public (Vercel + Render, CORS locked). We're in
LIVE-READINESS: wiring each swing state's live results feed → `results_live` using the
**county-pseudo-precinct pattern** (`{ST}-{fips}-CTY`), so the analytics run unchanged on
election night. **2 states DONE + validated to the exact certified result:**
- **NC** — open S3 bulk file, WITH live ballot-mode split (`nc_ingestor.py`, `nc_live_feed.py`, `etl_nc_county_baseline.py`).
- **GA** — open Enhanced Voting API, totals only (`ga_live_feed.py`, fetches 159 counties in parallel).

Clarity is confirmed DEAD (don't chase the 403). Playwright is installed (real-Chrome tool
for discovering hidden endpoints + passing Cloudflare); needed ongoing only where the data
endpoint itself is locked (so far just MI).

**The plan, in order — do these:**
1. **PA, then TX, then NV** — likely easy/GA-style. For each: discover the live results
   endpoint (probably Enhanced Voting like GA; use Playwright to find it if it's a JS/SPA
   site), then wire it end-to-end like `ga_live_feed.py` → `{ST}-{fips}-CTY` → `results_live`,
   and validate against a recent archived election (statewide two-party must match certified).
2. **SC** — if it's easy like GA/NC, add it too (Class-2 Graham seat; try `enr-scvotes.org`).
   SC isn't in the `general2026` manifest yet — add it (`api/elections.py`) if we wire it.
3. **MI** — take a real run at the Cloudflare block BEFORE the **Aug 4** primary (de-risk):
   try non-headless / stealth Playwright, OR hunt for an open bulk-download, OR per-county.
4. **WI** — research the approach anytime (72 county sites / AP aggregator); validate at the
   **Aug 11** primary. A pragmatic compromise (aggregator or a subset of big counties) is OK.
- **AZ** is already mapped (open `cdn1.arizona.vote` + Cloudflare SPA); VALIDATE at the
  **Jul 21** primary.

**Reminders / gotchas:**
- Every `*_live_feed.py` MUST `DELETE ... WHERE precinct_id LIKE '{ST}-%'` first (not just
  `-CTY`) — leftover precinct-level rows from sims/tests double-count. (Hit on NC and GA.)
- Party may be embedded in the candidate NAME suffix (GA: "(Rep)/(Dem)"), not a field.
- Each state needs a county-pseudo BASELINE too (`etl_*_county_baseline.py`, like NC) unless
  one already exists (GA's 2021 senate is already county-pseudo).
- baseline.db is gitignored → local DB changes don't touch production (prod uses the released copy).
- API runs without `--reload`: restart uvicorn + click Reset in the UI after api/ingestor changes.

Start with **PA**. Report findings at each step before moving on (my working rule).
