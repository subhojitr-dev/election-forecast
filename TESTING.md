# TESTING.md — How to test the dashboard (plain-language guide)

This walks you through everything to test, the exact clicks, and **what you should
see** so you can tell pass from fail.

**Two different things get tested in this file — know which one you're doing:**
- **Sections 1–7 (below): the SIMULATOR.** Clicks in the browser only. Replays a real
  past election (or synthetic data) locally — no internet access to any government
  site, nothing can go wrong outside your own machine.
- **Sections 8+ (further down): the REAL LIVE FEEDS.** Runs the actual Python scripts
  that will pull real results from state government websites on primary nights and
  Nov 3. Needs a terminal, hits the real internet, and behaves differently per state.
  This is what you use to validate AZ/MI on their primary nights and every wired
  state on Nov 3.

---

## 0. Start the two servers

Open two terminals in the project folder (`C:\Users\subho\election-forecast`):

```
# Terminal 1 — the data/API server
uvicorn api.main:app --port 8000

# Terminal 2 — the dashboard
cd ui
npm run dev
```

Then open **http://localhost:5173** in your browser.

> Golden rule: if you change anything under `api/` or `ingestor/`, restart Terminal 1
> **and** click **Reset** in the dashboard. Changes under `ui/` apply automatically —
> just refresh the page.

---

## 1. Orientation — what you're looking at

- **Top strip:** the 8 swing states. Click one to make it the focus.
- **Scenario row:** a dropdown (the "what-if" you're watching) + **Reset** + **Next Batch ▶**.
  - **Next Batch ▶** = "let more precincts report" (20% → 40% → … → 100%).
  - **Reset** = start the night over at 0%.
- **President / Senate / GA Special** toggle = which race you're viewing.
- **Panels:** live vote bar, win-probability gauge, convergence line, county table,
  and (top-right) the new **County Insight** box.

**The mental model:** the dashboard compares *tonight's* votes against a *baseline*
(what that area did last election). "Good for the Democrat" = doing **better than the
baseline**, on **higher turnout**, with **uncounted votes leaning their way**.

---

## 2. Test — Convergence line (President)

**What it proves:** the over/under-performance line is continuous, honest, and readable.

**Steps:** Race = **President**. Scenario = **True (real 2020 results)**. Click **Reset**,
then **Next Batch ▶** a few times, watching the bottom **"Convergence vs 2020"** chart.

**What you should see (PASS):**
- The blue line **starts at the far left (0%)** at the dashed **2020 baseline (~50.1%)** —
  no blank gap.
- It is **solid** while the Democrat is **at/above 50%**, and would turn **dashed** (same
  blue) if it dips **below 50%**.
- As you click Next Batch, the line **extends to the right** across a fixed 0→100% frame —
  it does **not** rescale or appear to redraw.
- The y-axis bottom is **30%** (so the 50% line and baseline sit low on the chart).

**To see the dashed style:** switch Race = **President**, click a state the Republican won
(e.g. **NC** or **TX**) — the Democrat is below 50%, so the line shows **dashed**.

---

## 3. Test — Georgia Senate shows Ossoff winning (the runoff fix)

**What it proves:** GA Senate uses the Jan-2021 runoff (Ossoff won), not the Nov general.

**Steps:** Toggle = **Senate**. Select **GA**. Click **Reset**, then **Next Batch ▶** to 100%.

**What you should see (PASS):**
- Candidates are **Jon Ossoff (D)** vs **David A. Perdue (R)**.
- The convergence **baseline sits just above 50%** (~50.8%), and the final result is a
  **Democratic win** (Ossoff) — *not* Perdue.
- Early batches may lean Republican, then it crosses to the Democrat (the runoff pattern).

---

## 4. Test — GA Special seat (Warnock)

**What it proves:** the second Georgia runoff (Warnock vs Loeffler) can be simulated.

**Steps:** Click the **GA Special** toggle (next to President/Senate). Click **Reset**,
then **Next Batch ▶** to 100%.

**What you should see (PASS):**
- The top strip shows **only Georgia** (this race exists only for GA).
- Candidates are **Raphael Warnock (D)** vs **Kelly Loeffler (R)**.
- Progress steps smoothly **20 → 40 → 60 → 80 → 100%** (not jumpy).
- It ends in a **Democratic win** (Warnock, ~51.2%), again after an early R-looking lead.

---

## 5. Test — Ballot buckets + turnout + County Insight (the big feature)

**What it proves:** votes are tracked by type (mail/early/election-day/military); you see
the red-mirage→blue-shift swing; and the County Insight box reads out the benchmark/
turnout/pending story.

**Steps:**
1. Race = **President**. Scenario dropdown = **"TEST · +4% big-county turnout, by ballot type"**.
2. Click **Reset**. Select **GA** in the top strip.
3. Click **Next Batch ▶** once or twice (early in the night), then in the **County table**
   click the **FULTON** row.
4. Look at the **County Insight** box (top-right) and try its **Mail / Election-Day** tabs.
5. Keep clicking **Next Batch ▶** to 100%, watching the top vote bar and the County Insight box.

**What you should see (PASS):**

*Early (after 1–2 batches — the "red mirage"):*
- Georgia's vote bar shows the **Republican ahead** (Dem ~47%).
- County Insight → **Mail tab** says *"No Mail votes counted yet"* (mail reports late).
- The **Fulton note** reads something like: *"48% reporting. Democrat at 77.0% vs the 73.5%
  2020 benchmark (+3.4 pts — above benchmark). Turnout vs 2020 still settling (mail not yet
  counted). ~178,000 votes still to come — and mail (which leans Democratic) is largely
  still uncounted, so the remaining vote likely breaks toward the Democrat."*

*Late (at 100% — the "blue shift"):*
- Georgia's vote bar **flips to the Democrat** (~52%).
- County Insight → **Mail tab** now shows mail votes leaning strongly **Democratic (~69%)**,
  while **Election-Day** leans **Republican (~43%)**.
- The **Fulton note** now reads: *"99% reporting. Democrat at ~75% vs the 73.5% benchmark
  (above). Turnout tracking **+5% vs 2020**."*
- County table has **"Turn v20"** (turnout vs 2020) and **"Pending"** columns filled in.

**The point you're validating:** even though the Republican led early, the box correctly
told you the **uncounted mail would break Democratic** — and that **Fulton was hitting its
2020 benchmark on higher turnout** (the "good sign"). That's the whole upgrade: it reads the
*meaning* of the outstanding vote, not just who's ahead right now.

---

## 6. How to read the key numbers (cheat sheet)

| You see | It means |
|---------|----------|
| **D% Live vs D% 2020** | tonight's Democratic share vs that area's last result. Higher = over-performing. |
| **vs Bench** | live share minus the 2020 benchmark. Green/+ = above benchmark (good for Dem). |
| **Turn v20** | estimated turnout vs 2020 (+ = more people voted). Unreliable until mail is in. |
| **Pending** | estimated votes still to be counted (current count scaled up to 100%). |
| **Convergence line solid vs dashed** | solid = Democrat above 50%; dashed = below 50%. |
| **Mail bucket leaning D, still small** | expect the Democrat to gain as mail is counted. |
| **Win-prob gauge** | chance the Democrat wins, given the projection + how much is reported. |

---

## 7. If something looks wrong

- **Blank panels / "API error":** Terminal 1 (uvicorn on :8000) isn't running.
- **Numbers stuck / old behavior after a backend change:** restart Terminal 1, then click **Reset**.
- **Everything at 100% already:** click **Reset** to start from 0%.
- **GA Special shows only one state:** that's correct — only Georgia has that race.
- **County Insight empty:** click a county row in the table, or step at least one batch.

---

## 8. Testing the LIVE feeds — real state data, not the simulator

Everything above (sections 1–7) tests the **simulator**: it replays data we already had
sitting in `baseline.db` through a fake "election night" (`ReplayFeed`), so you can watch
the UI panels update. This section tests the **other half of the app** — the
`ingestor/*_live_feed.py` scripts that reach out to each state's REAL election-night
website and pull REAL data into the exact same `results_live` table. This is what
actually runs on Jul 21, Aug 4, and Nov 3 — the simulator is just a stand-in for it until
then.

**⚠️ The one rule that matters:** once you've run a live-feed script for a state+race,
**do NOT click Reset** (or pick a new Scenario) for that election/race in the dashboard —
`Reset` deletes every row in `results_live` for that state+race and rebuilds it from the
simulator, silently overwriting the real data you just fetched. Switching the
**Election** or **race toggle** dropdowns is safe (read-only) — only Reset/Scenario writes.

### 8.1 Walkthrough — Georgia (do this one first; every other state follows the same shape)

**What it proves:** the live-feed script fetches GA's real election-night source
(Enhanced Voting, not Clarity), maps it to county-pseudo-precincts, and the totals match
a certified result **exactly** — not approximately.

**GA is the one state with THREE tracked races**, each needing its own test election:
President (`president`), the regular Class-2 Senate seat up again in 2026 (`senate` —
Ossoff vs Perdue), and the special Class-3 Senate seat (`senate_special` — Warnock vs
Loeffler, the "GA Special" toggle). Both Senate runoffs happened on the **same day**
(Jan 5, 2021) and, usefully, GA's Enhanced Voting system has that whole day archived
under one election ID (`2021JanFedRun`) with both contests inside it — so both get a
full, apples-to-apples baseline match, not a workaround.

**Step 1 — all three races:**
```powershell
cd C:\Users\subho\election-forecast
python ingestor/ga_live_feed.py 2024NovGen "President of the US" president
python ingestor/ga_live_feed.py 2021JanFedRun "US Senate (Perdue)" senate
python ingestor/ga_live_feed.py 2021JanFedRun "US Senate (Loeffler) - Special" senate_special
```
**What you should see (PASS):** `counties: 159/159` for all three, and:
- President: Trump 2,663,117 R / Harris 2,548,017 D (certified 2024 general).
- Senate: Ossoff 2,269,923 D / Perdue 2,214,979 R (certified Jan 2021 runoff).
- GA Special: Warnock 2,289,113 D / Loeffler 2,195,841 R (certified Jan 2021 special runoff).

**Step 2 — confirm it landed correctly in the database** (independent of the script's own
printout — this is the "don't just trust the tool that wrote the data" check):
```powershell
python -c "import sqlite3; c=sqlite3.connect('data/db/baseline.db'); print(c.execute(\"SELECT race_type, COUNT(DISTINCT precinct_id), SUM(votes) FROM results_live WHERE precinct_id LIKE 'GA-%' GROUP BY race_type\").fetchall())"
```
You should see 159 distinct precincts (the county-pseudo rows) for all three race_types,
with vote sums matching what each script run printed.

**Step 3 — clear any stale cached snapshots, then check the API directly:**
`results_live` is the source of truth, but `/api/states` reads a **precomputed cache**
(`live_snapshots`) and only recomputes once when that cache is empty for a state+race —
so if you've clicked Next Batch for GA before (very likely, it's the demo's go-to state),
you'll see STALE numbers unless you clear the cached rows first:
```powershell
python -c "import sqlite3; c=sqlite3.connect('data/db/baseline.db'); c.execute(\"DELETE FROM live_snapshots WHERE state='GA' AND race_type IN ('president','senate','senate_special')\"); c.commit()"
```
Then, with uvicorn running (Terminal 1), hit the API directly. **Each race lives under a
different `election=` value** — see the table below for why:
```powershell
curl "http://localhost:8000/api/states?race=president&election=pres2024"
curl "http://localhost:8000/api/states?race=senate&election=general2026"
curl "http://localhost:8000/api/states?race=senate_special&election=demo"
```
**What you should see (PASS):** GA in each response at **100% reporting**, `statewide_shift`
essentially **zero** in all three (the live data IS the same election as the baseline, so
it should match almost exactly), and `win_prob_dem` clearly favoring whoever actually won
(near 0% for President/Trump, ~89% for Senate/Ossoff, ~98% for GA Special/Warnock).

| Race | `election=` to view it under | Why |
|---|---|---|
| `president` | `pres2024` | `general2026` has no President race at all (midterm); `pres2024`'s baseline year (2024) matches the live data exactly |
| `senate` | `general2026` | This is the REAL production config — GA's tracked 2026 baseline IS the 2021 runoff, so this is a true apples-to-apples check, not just a sandbox |
| `senate_special` | `demo` | The special seat isn't on any real upcoming ballot (Warnock already won a full term) — `demo` is the only election that tracks it |

**Step 4 — see it in the dashboard:** open **http://localhost:5173**. For President: set
**Election = "Test · 2024 President (historical)"**, toggle = President, click **GA**.
For Senate: set **Election = "General · Nov 3, 2026 (midterm)"**, toggle = Senate, click
**GA**. For GA Special: set **Election = "Demo · historical sandbox"**, toggle = **GA
Special**, click **GA**. Each should show the same numbers as Step 3 — real certified
data, not a simulator replay. **Don't click Reset or change the Scenario dropdown** for
whichever one you're looking at (see the rule above).

**Step 5 — clean up (optional, if you want the demo state back the way it was):**
```powershell
python -c "import sqlite3; c=sqlite3.connect('data/db/baseline.db'); c.execute(\"DELETE FROM results_live WHERE precinct_id LIKE 'GA-%'\"); c.execute(\"DELETE FROM live_snapshots WHERE state='GA'\"); c.commit()"
```
Then click **Reset** in the UI once (for each race you were viewing) — that rebuilds GA
from the simulator again.

### 8.2 The same pattern for every other wired state

Every other state's live-feed script follows the exact same shape as §8.1 — swap the
script name, arguments, and the certified numbers you expect. **The one thing that
changes per state is which `election=` value shows the result in the API/dashboard** —
use the wrong one and you'll see nothing (or the wrong baseline), not because the ingest
failed. Quick reference:

| State | Command (President, then Senate) | Counties | Certified result to expect | `election=` to view President / Senate |
|-------|-----------------------------------|----------|----------------------------------|---|
| **NC** | *(no President test — see §8.3)* / `python ingestor/nc_live_feed.py 2020-11-03 "US SENATE" senate` | 100 | Senate: Tillis (R) 2,665,598 beat Cunningham (D) 2,569,965 | — / `general2026` (NC's real tracked baseline is 2020 — exact match) |
| **PA** | `python ingestor/pa_live_feed.py 105 G 1 1 president` / `python ingestor/pa_live_feed.py 105 G 2 1 senate` | 67 | Trump 3,543,308 R / Harris 3,423,042 D; McCormick 3,399,295 R / Casey 3,384,180 D | `pres2024` / `sen2024` — **PA is NOT in `general2026`** (its Senate seat is Class 3, next up 2028) |
| **AZ** | `python ingestor/az_live_feed.py 47 0 "President of the United States" president` / `... "U.S. Senator" senate` | 15 | Trump 1,770,242 R / Harris 1,582,860 D; Gallego 1,676,335 D / Lake 1,595,761 R | `pres2024` / `sen2024` — **AZ is NOT in `general2026`** either (same Class-3 reason) |
| **MI** | `python ingestor/mi_live_feed.py "11/5/2024" president` / `... senate` | 83 | Trump 2,816,636 R / Harris 2,736,533 D; Slotkin 2,712,686 D / Rogers 2,693,680 R | `pres2024` / `sen2024` **or** `general2026` (MI IS tracked there too, baseline 2020 — a real, meaningful shift, not zero) |
| **TX** | `python ingestor/tx_live_feed.py 2024 G 1001 president` / `... 7958 senate` | 254 | Trump 6,393,597 R / Harris 4,835,250 D; Cruz 5,990,741 R / Allred 5,031,249 D | `pres2024` / `sen2024` **or** `general2026` (same as MI — TX is tracked there, baseline 2020) |
| **SC** | *(no President test — see §8.3)* / `python ingestor/sc_live_feed.py 126294 26001 sc_senate_mechanism_test_rep` (Republican primary) then `... 26000 sc_senate_mechanism_test_dem` (Democratic — ⚠️ **must use TWO DIFFERENT `race_type` names**, since each call's internal `DELETE` is scoped to its own race_type — reusing the same name for both would wipe the first call's rows with the second) | 46 | Graham (R) 264,091 / Andrews (D) 226,075 in their respective June 2026 primaries | — / mechanism-only, no manifest election matches (see §8.3) |

`general2026` has **no President race at all** (midterm) — always use `pres2024` for a
President dashboard check, for any state. For Senate, prefer `general2026` when the state
is actually tracked there (GA/MI/NC/TX/SC) — it's the real production config, not just a
sandbox — and fall back to `sen2024`/`sen2018`/`sen2020` otherwise.

### 8.3 State-specific things to know before testing

- **NC and PA** are the only two states with a live **ballot-mode split**
  (election-day/early/mail/provisional) — after ingesting, check
  `SELECT DISTINCT mode FROM results_live WHERE precinct_id LIKE 'NC-%'` to see all 4
  buckets (NC) or 3 (PA — no early in-person voting). Every other state writes `mode='all'`.
- **NC's baseline year is 2020, not 2024** — its Senate seat wasn't contested in 2024, so
  test against `2020-11-03` / `"US SENATE"` as shown above, not a 2024 date.
- **AZ's electionId is stable and pre-published** (`az_election_ids()` in the script) — no
  discovery step needed, ever. It's the only state where that's true.
- **MI needs a HEADED browser** (`headless=False` in Playwright) — Cloudflare blocks
  headless Chromium there specifically. Running `mi_live_feed.py` on a machine with no
  display (a bare SSH session, a headless CI box) will hang or fail; run it from a normal
  desktop session. Its electionId is also **not** pre-published — the script auto-discovers
  it from a date string and will print "NOT FOUND" until the state configures that election.
- **TX only needs HEADLESS Playwright** — confirmed identical results headed or headless,
  so it runs fine anywhere Playwright is installed, no display required.
- **SC needs a contest CODE, not a date** — `26001` (Republican primary) / `26000`
  (Democratic primary) for the June 2026 primary; the general's codes will differ once
  configured. SC's contest names in the raw JSON have **literal double spaces**
  (`"U.S.  Senate  - REP"`) — a Clarity quirk, harmless for the ingest itself but worth
  knowing if you inspect the raw JSON by hand. Also: SC's `ALL.json` includes one county
  entry literally named `"-1"` (a statewide pseudo-row) — `sc_live_feed.py` already
  excludes it, but if you're ever poking at the raw data yourself and totals look exactly
  2x what you expect, that's why.
- **GA and SC are the only two states without a Nov 2026 electionId discovery mechanism
  yet** — GA's is a human-readable string per election (`2024NovGen` → whatever the 2026
  general's equivalent is); SC's `elections.json` is empty until SC configures the
  election. Both need a quick check closer to the date, same as MI.

### 8.4 Primary-night mock/mechanics tests (AZ Jul 21, MI Aug 4)

AZ and MI don't have a President or Senate race on their own 2026 primary ballots (both
Senate seats are Class 3, next up 2028) — so their primary-night test isn't "does the
data match," it's **"does the polling mechanism work live"**: does a real, currently-
reporting election show the vote/precinct counts actually moving between polls. Use a
**scratch `race_type`** so this can never leak into the real dashboard (no election
manifest references these names, so they're invisible to the UI):

```powershell
# AZ — run every few minutes on Jul 21 night
# ⚠️ two DIFFERENT race_type names — each call's internal DELETE is scoped to its own
# race_type, so reusing one name for both would silently wipe the first with the second
python ingestor/az_live_feed.py 68 0 "Governor (DEM)" az_primary_test_dem
python ingestor/az_live_feed.py 68 0 "Governor (REP)" az_primary_test_rep

# MI — first confirm the election id has appeared (may print "NOT FOUND" until it does)
python ingestor/mi_live_feed.py "8/4/2026" senate
```

**What you should see (PASS), polled repeatedly through the night:**
- AZ: the printed `uploadId` increases between polls; `precincts` climbs off 0;
  vote totals for Governor move (not static).
- MI: `mi_live_feed.py` eventually stops printing "NOT FOUND" and instead prints a
  discovered electionId, county count, and moving vote totals as the primary reports.

**Clean up afterward** (these are scratch rows, not real data):
```powershell
python -c "import sqlite3; c=sqlite3.connect('data/db/baseline.db'); c.execute(\"DELETE FROM results_live WHERE race_type IN ('az_primary_test_dem','az_primary_test_rep')\"); c.commit()"
```

### 8.5 Election Day (Nov 3, 2026) — what's different from the tests above

The mechanism is identical — same scripts, same `results_live` writes, same
county-pseudo-precinct join — just with three changes:
1. **Real electionIds**, captured ~2 weeks before (mid–late Oct) once each state publishes
   the Nov general to their live system at 0% reporting. Re-run each state's discovery
   step then (AZ's is already known; MI/TX auto-discover; GA/SC need a fresh manual check).
2. **Real race_type values** (`president`/`senate`, not `_test` scratch names) — Nov 3 has
   no President race in our manifest (midterm), only Senate for GA/MI/NC/TX/SC.
3. **Repeated polling on an interval** instead of a single manual run — wrap the same
   `ingest(...)` calls in a loop (or the Render background-worker setup described in
   DEPLOY.md), same as the primary-night tests in §8.4 but for the real ballot.
Do a **full dry run** of all 5 states × Senate against each state's 0%-reporting Nov feed
before the actual night, exactly like §8.1's Step 1–4 — that's the complete rehearsal.
