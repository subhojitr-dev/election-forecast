# Issues Log — Election Forecast Dashboard

Known problems, their workarounds, and resolution plans.
Status legend: 🔴 OPEN · 🟡 WORKED AROUND (not fully solved) · 🟢 RESOLVED

---

## ISSUE #1 — Clarity CDN returns HTTP 403 to programmatic requests
**Logged:** 2026-06-25 (Phase 2) · **Status:** 🟡 WORKED AROUND for development; 🔴 OPEN for production

### 🔬 UPDATE 2026-07-06 — DIAGNOSED (earlier "anti-scraping" call was WRONG)
Re-tested carefully. The server is **AWS CloudFront** (not nginx). Findings:
- `https://results.enr.clarityelections.com/GA/elections.json` → **200 with a
  PLAIN request** (we CAN discover every GA election + its EID this way).
- The old data paths (`/GA/{EID}/current_ver.txt`, `.../reports/detailxml.zip`)
  → **403 for everyone**, including: full browser headers AND **`curl_cffi` with
  a byte-identical Chrome TLS fingerprint**. So it is **NOT a User-Agent / header
  / TLS bot-block.**
- Conclusion: **modern Clarity moved its data to new (JSON) endpoints;** the old
  paths no longer exist and CloudFront answers a dead path with 403 (not 404).
  So the task is **"find the new URLs," not "beat a guard."**
- **Next step:** drive a real headless browser (**Playwright**) at a live GA
  results page and capture the network calls to map the modern
  `/{ST}/{EID}/{version}/json/...` scheme + version discovery. (~150 MB install.)
- **NC does NOT have this problem** — NCSBE serves open S3 files (see nc_ingestor
  below); that's why we built NC first. **NC is now WIRED END-TO-END (2026-07-06).**

### 🔬 UPDATE 2026-07-06b — Playwright test: even a real browser gets 403
Installed Playwright, loaded `results.enr.clarityelections.com/GA/121813/` in a
real headless Chromium: **403, page never loaded, no SPA, zero data requests.**
So it is NOT a scripting/bot-block at all — a genuine browser can't load the bare
path either. Conclusion: the old Clarity ENR endpoint is **dead/decommissioned for
GA** (its `elections.json` also stops at mid-2024). **REFRAMED:** "beat the 403" is
the wrong goal. The real task is **per-state discovery of each state's CURRENT
live-results system** — exactly like we did for NC. Next: find where GA / PA / TX /
MI publish results NOW (GA SoS portal, etc.), and whether the modern Clarity lives
at a new domain (Enhanced Voting acquired Scytl/Clarity). Test against the summer
primaries (AZ Jul 21 first). The whole "Clarity 403" framing is effectively OBSOLETE.


**What happened**
When trying to fetch real Clarity ENR data from
`results.enr.clarityelections.com` directly from Python, every request returned
**HTTP 403 Forbidden** — including the small `current_ver.txt` discovery file and
the `detailxml.zip` data file. This happened even for an archived, long-past
election (Georgia 2020 general, election id `105369`).

**What I tried (all still 403)**
- Default `requests` call with a normal User-Agent.
- A full browser-like header set (Chrome UA + `Accept`, `Accept-Language`,
  `Referer` pointing at the election page).
- The `clarify` library's own `Jurisdiction` discovery flow.

It is a plain server-side `nginx` 403 (a deliberate anti-scraping block), **not**
a missing file (which would be 404) and **not** a JS/Cloudflare challenge.

**Also checked — no easy archive fallback**
- Wayback Machine has the Clarity *landing page* but **not** the underlying
  `current_ver.txt` / `detailxml.zip` data files.

**Impact**
We cannot pull live OR archived Clarity data programmatically today. This blocks
the "fetch from live Clarity" path — but NOT development, because of the
workaround below.

**Workaround (what unblocked Phase 2)**
Decoupled the poller from any single data source via a feed-adapter design
(`FeedSource`), so development/testing never depends on live Clarity:
1. **Real Clarity format** validated using a genuine Clarity XML sample pulled
   from the `openelections/clarify` GitHub **test fixtures** (saved to
   `data/raw/clarity_samples/`). Proves our parser reads the real format.
2. **Realistic full-scale testing** via `ReplayFeed` — replays our own trusted
   certified data from `baseline.db` (e.g. GA 2020, all 2,656 precincts).
3. **Edge cases** via `MockFeed` — synthetic data (e.g. red-mirage scenario).

➡️ The 403 itself is **not solved**; it is *avoided* for dev. Production fix is
tracked in the "November readiness plan" below.

**Resolution plan (for live use)**
- Test a more browser-faithful fetch (persistent session + cookies, exact header
  order, hitting the same JSON/data paths the live page uses).
- If still blocked: headless-browser fetch (e.g. Playwright) as a fallback, or an
  alternative mirror/source per state.
- Validate against a REAL, currently-live Clarity election before November
  (a 2026 primary / special), not just historical archives.

---

## ISSUE #2 — `clarify` library URL parser predates modern Clarity version strings
**Logged:** 2026-06-25 · **Status:** 🟡 WORKED AROUND

**What happened**
`clarify` 0.7.0's URL regex expects the version path segment to be all digits
(`/[0-9]+`), but modern Clarity uses alphanumeric versions like `web.264614`.
As a result `Jurisdiction` auto-discovery couldn't resolve the version, and
`report_url()` returned `None`.

**Workaround**
We don't rely on `clarify`'s URL discovery. We use `clarify` ONLY as the XML
**parser** (which works perfectly), and build the report URLs ourselves in
`LiveClarityFeed` (`current_ver.txt` → `{ver}/reports/detailxml.zip`).

**Resolution plan**
Finalize our own URL construction during the November shakeout; the parser is
solid, so no dependency on the library's networking layer.

---

## ISSUE #3 — Live precinct NAME → baseline precinct_id mapping
**Logged:** 2026-06-25 · **Status:** ⚪ DEFERRED / MOOT for v1 (2026-06-30 decision)

**DECISION 2026-06-30 — county-level v1 makes this MOOT.** We go COUNTY-LEVEL for all 8
states on election night (county FIPS is stable year-to-year → a clean exact county→county
join, no name-matching, no splits/merges). So the crosswalk is NOT needed for v1, and WI
(no precinct feed) is handled. The crosswalk only re-enters IF/when precinct-level drill-down
is added later for the easy states (GA via Clarity, NC via its dashboard) as a precision
enhancement. The original precinct strategy below is retained for that future work.


**What it is**
Clarity labels a precinct one way; our 2020/2024 baseline labels the "same"
precinct another way (spelling, punctuation, county prefixes). To compare live
vs. baseline we must match them. `ReplayFeed` sidesteps this (it uses our own
ids), so it is the key unsolved piece for the live night.

**Resolution plan — REVISED 2026-06-25 (use the 2026 primaries):**
Key insight (per user): the 2026 PRIMARY and 2026 GENERAL use the same precinct
universe + naming (precinct definitions are fixed within a cycle), so a mapping
built from the primary transfers to November with high fidelity (~95%+). This
also doubles as the live-access test for Issue #1.

Plan:
1. Pull each target state's 2026 PRIMARY from live Clarity (also validates the
   403 workaround against a real live feed).
2. From the primary, capture the EXACT 2026 precinct names we'll see in November.
3. Offline + unhurried, reconcile 2026 precincts → 2020 baseline precinct_ids
   (name normalization + county_fips + manual review of stragglers). This is the
   only place real drift exists (2020→2026: splits/merges/new precincts).
4. Graceful degradation: unmatched precincts still roll up to COUNTY level
   (county_fips is stable) — never lost, just compared at a coarser grain.

Why this helps: converts a high-pressure election-night task into a calm,
reviewable offline one. Caveat: prefer an UPCOMING/recent primary or runoff —
finished old elections may hit the same 403 as the 2020 archive.

**Concrete mechanism — `precinct_crosswalk` table (added 2026-06-25):**
A one-time, per-state, version-controlled lookup table. Not always 1:1, so it
carries a WEIGHT to handle splits/merges:

  live_2026_precinct | baseline_2020_precinct | weight
  -------------------|------------------------|-------
  GA-FULTON-SC01     | GA-FULTON-SC01         | 1.00   (clean rename/same)
  GA-COBB-12A        | GA-COBB-12             | 0.60   (2020 precinct split...)
  GA-COBB-12B        | GA-COBB-12             | 0.40   (...other half)
  GA-GWINNETT-7      | GA-GWINNETT-7A         | 1.00   (two 2020 merged into one)
  GA-GWINNETT-7      | GA-GWINNETT-7B         | 1.00
  GA-FORSYTH-99      | (none)                 |  -     (new precinct -> county fallback)

weight = fraction of the 2020 precinct's baseline attributed to that 2026
precinct, so shift math stays honest across splits/merges.

How to build (cheap -> rigorous):
  1. Name/code match — gets ~80-90% (the 1.00 rows).
  2. Spatial match — overlay 2020 vs 2026 precinct SHAPEFILES to derive split/
     merge weights. May be able to REUSE published crosswalks (VEST / Redistricting
     Data Hub) instead of building from scratch.
  3. Manual review of the residue.

Scope guidance: SHIP the simple name-based 1:1 + county fallback first (enough
for directional shift signal, which is the dashboard's purpose). Treat weighted
spatial apportionment as an optional precision upgrade. Election night = a clean
3-way join: live -> precinct_crosswalk -> 2020 baseline.

**Crosswalk data sources (researched 2026-06-25):**
- ROUTE A (recommended for building it): Redistricting Data Hub precinct
  shapefiles — https://redistrictingdatahub.org/data/download-data/ (free acct).
  Per-state: redistrictingdatahub.org/state/<state>/ . Has 2016/18/20/22; 2024
  in progress; 2026 boundaries not published until states finalize. Grab each
  state's 2020 shapefile (target side) + newest (2022/2024) as 2026 proxy.
- ROUTE B (exact live names + doubles as the 403 test): 2026 PRIMARY ENR feeds
  (the live state portals, per brief). NOT a clean download — needs per-state
  primary election_id discovery + the 403 fix, so this is part of the July
  live-access task, not a download-now item. Reminder: 2026 primary precinct
  data is NOT on Harvard Dataverse (MIT publishes long after the fact).
  Primary dates: GA done (runoff Jun 16), AZ Jul 21, MI Aug 4, WI Aug 11;
  PA/NV/NC/TX vary.

---

## ISSUE #4 — `results_live` keeps only the latest snapshot (no time-series)
**Logged:** 2026-06-25 · **Status:** 🟢 RESOLVED (Phase 3, 2026-06-25)

Each poll overwrites `results_live` with the full current snapshot. RESOLVED by
adding the `live_snapshots` table (analytics/engine.py ensure_schema +
record_snapshot, written via the poller's on_write hook). It stores a per-poll
statewide row (pct, votes, shift, projected share, win prob, tier) — the
time-series that powers the convergence chart (Panel 5).

---

## ISSUE #5 — Dashboard unbearably slow: "Next Batch" took 18–50s
**Logged:** 2026-06-27 · **Status:** 🟢 RESOLVED (2026-06-27)

**Symptom**
Clicking "Next Batch" in the UI appeared to do nothing — the button sat on "…"
for 18–50 seconds. The simulation *was* advancing on the backend, but the round
trip was so slow it looked frozen. (User report: "I clicked Next Batch, nothing
is happening.")

**Root causes (found by profiling)**
1. `results_live` (≈183k rows) had **no index** → every per-state query was a
   full table scan (~0.5s), done twice per state.
2. `/api/states` **recomputed the FULL analytics for all 8 states on every 5s
   auto-refresh**. Each took ~20s, but a new poll fired every 5s, so requests
   **piled up** and saturated the server (a feedback-loop traffic jam).
3. The static 2020/2024 **baseline was re-loaded from disk on every calculation**
   (~0.4s each), even though it never changes at runtime.
4. Advancing a batch **committed to disk 8 separate times** (once per state) —
   8 slow fsyncs per click.

**Fixes**
1. Added indexes `idx_rl_race` / `idx_rl_precinct` on `results_live` (baked into
   `engine.ensure_schema`); enabled **WAL** journal mode so reads/writes don't
   block each other; `busy_timeout=10000`, `synchronous=NORMAL` in `api/db.py`.
2. `/api/states` now **reads the latest precomputed row from `live_snapshots`**
   per state (instant) instead of recomputing; seeds lazily if missing. Added a
   `light=True` mode to `compute_state_analytics` (skips county rollups + watch
   list) for the strip and the simulation.
3. Added an **in-memory baseline cache** (`engine._BASELINE_CACHE`) — load each
   (state,race,year) baseline once, reuse thereafter.
4. `write_snapshot` / `record_snapshot` got a `commit` flag; `SimController.next`
   now **commits once per batch** (all 8 states), not per state.
5. UI auto-refresh eased from 5s → 10s (`ui/src/App.jsx`).

**Outcome**
- Next Batch: **18–50s → ~0.8–1.9s**
- `/api/states` (the auto-refresh): **~20s → ~0.4s**
- `/api/state/{abbr}` full detail: **~7s → ~1.8s**
Same results, far faster. No change to *what* is computed, only *how*.

**Note:** the API runs without `--reload` here, so it must be restarted to pick
up changes in `api/`. Re-running the ETL recreates the new indexes via
`ensure_schema`/schema; existing DBs got them applied directly.

---

## ISSUE #6 — Simulator revealed whole counties at a time (unrealistic)
**Logged:** 2026-06-27 · **Status:** 🟢 RESOLVED (2026-06-27)

**Symptom**
At 40% statewide reporting, big counties showed 100% reported while others showed
0% (e.g. Gwinnett/Cobb/DeKalb 100% but Fulton 0%). Internally consistent but not
lifelike — real counties report gradually and in parallel.

**Cause**
ReplayFeed used `order="county"`: it revealed whole counties one at a time in a
shuffled order, so "40%" meant ~40% of *counties* fully done, the rest untouched.

**Fix**
Added a new `order="proportional"` reveal mode to ReplayFeed: every county
reports GRADUALLY and IN PARALLEL, each with a random per-county "speed"
(gauss(1.0, 0.25), clamped 0.4–1.6) so some run ahead/behind; the final batch
forces all to 100% (totals still match certified). `SimController` now uses it.
Verified read-only: at ~41% statewide every county is ~16–48% in (not 0/100).

**Why we keep it (not "more realistic" but more useful):** lets you watch each
county move partial → full and see shifts evolve, instead of binary flips. The
real election night still uses the live feed's actual reporting, not this model.

**To see it:** restart the API (it has no --reload) and click **Reset** in the UI
(Reset rebuilds the simulation feeds with the new mode).

---

## ISSUE #7 — GA Jan-2021 runoff baseline missing 4 counties (OpenElections gap)
**Logged:** 2026-06-28 · **Status:** 🟢 RESOLVED (2026-06-28 — estimate-filled to exact certified)

**RESOLUTION:** `etl_ga_runoff_2021.py` now estimate-fills the 4 missing counties
(Camden, Chattooga, Grady, Greene): each is split by its real 2020 Senate-general
lean + size, scaled so the 4-county sum = (certified statewide − loaded). Result:
all **159** counties present; statewide now EXACTLY certified (Ossoff 2,269,923 /
Perdue 2,214,979 = 50.61%; Warnock 2,289,113 / Loeffler 2,195,841 = 51.04%). The 4
filled counties are flagged "ESTIMATED" in `precincts.precinct_name`.


**What it is**
The GA Senate baseline was switched to the Jan 5, 2021 RUNOFF (the seat Ossoff WON
and that is up again in 2026) instead of the Nov-2020 general (where Perdue led but
under GA's 50% majority threshold). Source = OpenElections precinct file aggregated
to county. That file **omits 4 counties entirely**: Camden, Chattooga, Grady, Greene
→ we loaded **155/159** counties.

**Impact**
These 4 are net-Republican, so the loaded baseline reads **50.82%** Dem two-party vs
the certified **50.62%** (winner unaffected — Ossoff D). On 2026 election night these
4 counties would have live results but **no baseline** (no shift signal until filled).
Exact COMBINED remainder is known by subtraction from the certified statewide totals:
Ossoff +15,331 / Perdue +32,719 ; Warnock +15,353 / Loeffler +32,694.

**Resolution options (pending user decision)**
- (a) Estimate-fill: split the exact certified remainder across the 4 using their real
  2020-general partisan lean → statewide becomes exactly certified, all 159 present
  (the 4 are lean-anchored estimates).
- (b) Certified per-county from GA SoS (Clarity — same 403 as Issue #1) / Ballotpedia /
  WaPo (JS-rendered, didn't extract via fetch).
Re-run `ingestor/etl_ga_runoff_2021.py` after adding the 4 (it's idempotent).

---

## ISSUE #8 — Election-night live FEED audit (mode availability + non-Clarity states)
**Logged:** 2026-06-28 · **Status:** 🔴 OPEN (prep task — everything hinges on it)

Surfaced while building the ballot-mode feature. Two realities for going live:
- **Dataverse/MIT is NOT a live feed** — it's the historical BASELINE only. Live data
  comes from each state's own ENR system on the night; it will NOT hold 2026 results.
- **Clarity is broader than "GA only" but often county-by-county:** GA statewide; PA /
  TX / MI via PER-COUNTY Clarity (Allegheny, Tarrant/Denton, Macomb/Oakland); AZ / NV /
  WI / NC likely run their OWN systems → need bespoke ingestors. Verify each.
- Even when a feed exists, the **ballot-mode breakdown** (mail/early/election-day/
  military) and "% expected vote" may not be published live — **military/UOCAVA is
  usually only in the final canvass**, not real-time ENR.

**Design guard already in place:** mode is OPTIONAL — `results_live.mode` defaults to
'all', so states without a live mode breakdown fall back to the geography-only model
(no regression). The simulator always has full modes for demos.

**Prep (start now / July):**
1. Solve the live fetch (Issue #1) first — mode is moot without the feed.
2. Per-state feed audit: pull a sample detail file, record system (Clarity vs own),
   geography level, whether it carries vote-type subtotals, live vs final-only.
3. Per-state "bucket name" normalization map (advance/early/absentee/mail/UOCAVA differ).
4. **Test windows:** AZ primary **Jul 21** (own system) · MI **Aug 4** (county Clarity) ·
   WI **Aug 11** (own). GA statewide-Clarity: test vs a live GA special (primary past).

**Full plan + timeline → see `PREP.md`** (per-state feed status, the 5 fetch layers,
week-by-week schedule, primary test calendar, risk register).

---

## 🗓️ NOVEMBER 3, 2026 READINESS PLAN
(Election Day = Tuesday, Nov 3, 2026. Today = 2026-06-25, ~4 months out.)

**How we ensure it works on the night**
1. Beat the 403 (Issue #1) with a hardened/browser-faithful fetch.
2. Solve precinct-name mapping (Issue #3) per target state.
3. Build election_id **auto-discovery** (IDs are only published days before).
4. Add fallback ingestors for non-Clarity states (NC, WI, MI run their own).
5. Add the snapshot-history table (Issue #4) so trends work live.
6. Redundancy + monitoring on the night; safe restart (full snapshots self-heal).

**Prep timeline**
- **Now → end of July:** solve 403 + finalize live fetch; test against a real,
  currently-live 2026 Clarity election (primary/special) — not just archives.
- **Aug → Sep:** dry-run live polling against real primaries/specials in our
  actual target states; build + validate precinct-name mapping.
- **Early–mid October:** build election_id discovery; add non-Clarity state feeds.
- **~2 weeks before (mid–late Oct):** states publish the Nov general election to
  Clarity (0% reported). Capture real election_ids; full dry run against the live
  (empty) feed end-to-end.
- **Election week:** final rehearsal + monitoring setup.
- **Nov 3 night:** go live.

**When does prep start?** The live-access work (Issue #1) should start **now /
July** — it's the riskiest unknown and benefits from testing against real 2026
primary elections while they're still live. The election-specific wiring
(real IDs) can only finish in **mid–late October** once states publish.
