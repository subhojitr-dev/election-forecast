# Next-session prompt — Election Forecast

> **UPDATE 2026-11-11 (supersedes the Nov 3 plan below — the forecast was NOT run on
> election night).** New focus: **Districts tab for GA & NC legislature** — read
> `DISTRICTS.md` first. DONE + deployed: 2026/2024 results + edge + 2028 targets for all
> 406 seats; election-night tracker (practice replay of 2026 + live mode via
> `/api/districts/live/{ST}`, poller tasks gated on `DISTRICT_LIVE_GA_EID` /
> `DISTRICT_LIVE_NC_DATE`). TODO: (1) re-run `py ingestor/district_results.py NC` once
> NCSBE posts the 2026 precinct-sorted file (late Nov); (2) test the live feed on the
> next real GA special election (check GA precinct reportingStatus behaviour);
> (3) optional: link the Districts tab from the early-vote /ga and /nc pages; more states.


Paste the block below to start the next session.

---

We're continuing the **Election Forecast Dashboard** (`C:\Users\subho\election-forecast`),
prepping for the real Nov 3, 2026 general election. Read `CONTEXT.md` first (current-state
snapshot), then `FEED_AUDIT.md`'s live-cadence tables, then `PROGRESS.md`'s 2026-08-08
entries (two of them — the build entry and the "later" debugging/UX-fixes entry) for the
full story of today's session, then this prompt.

## Where we are (as of 2026-08-08, end of session)

**Deployed and confirmed live in production today:**
- **MI county-level fallback: 18 counties, ~77-80% of the statewide primary vote**
  (Wayne, Oakland, Macomb, Kent, Washtenaw, Genesee, Ingham, Kalamazoo, Ottawa,
  Livingston, Saginaw, Bay, Eaton, Muskegon, Berrien, Monroe, Midland, Calhoun) — see
  `FEED_AUDIT.md`'s MI county table. Paused here by explicit user choice (remaining
  counties are mostly small/rural, unlikely to move a general-election outcome much) —
  optional to push toward ~90% later, not urgent.
- **GA Governor primary showcase** (May 19, 2026, already decided/certified) — proves
  GA's live-feed plumbing works against a real primary night. `ga_gov_primary_2026_test`
  election, both party fields shown (Governor is 2 separate contests per county on GA's
  Enhanced Voting system, unlike the combined-contest Senate general).
- **GA/AZ/TX Governor 2026 general** — full "governor" race type added, baseline = each
  state's 2022 result (Kemp/Hobbs/Abbott's terms all end 2026). Real 2026 nominees
  wired in: Bottoms/Jackson (GA), Hobbs/Biggs (AZ), Hinojosa/Abbott (TX). **Live feed
  for the real Nov 2026 race is still TBD** — only the historical baseline is built.
- **Maine added as a new (10th) state** — Senate 2026, Collins (R, incumbent) vs Troy
  Jackson (D, replaced Graham Platner after he withdrew in July). Baseline = 2020,
  verified against certified results almost exactly. **Live feed for Nov 2026 is
  UNRESOLVED** — Maine's official site (maine.gov) publishes static Excel/PDF exports
  per contest, not a live API like GA/NC/AZ/SC. No ME election happened during this
  project to test against firsthand. Real research needed before Nov 3 — see
  `FEED_AUDIT.md`'s cadence table, flagged ⚠️ UNRESOLVED, likely closer to WI's
  "hardest" category than a solved case.
- **4 real UX/data-safety fixes**, found by walking the user through the dashboard, not
  by testing: (1) hid Reset/Next Batch for primary showcases (they have no baseline to
  replay, so it did nothing); (2) relabeled the GA-only race toggle to "GA Special
  (Warnock)" so it's discoverable; (3) that toggle now genuinely disables when viewing
  any state other than GA; (4) **hid the simulator entirely on real elections
  (general2026/general2028)** — a real data-safety fix, not cosmetic: the simulator's
  reset() deletes+rewrites `results_live` scoped only by (race_type, state), and
  general2026's real Senate states share both the race_type string AND several states
  with Demo — an accidental Reset click on Demo's Senate race could have wiped real
  Nov 3 live data. Full detail in PROGRESS.md's "2026-08-08 (later)" entry.

**Also fixed earlier today:** hardcoded "2020" labels (now show the real baseline year
dynamically — matters since Governor=2022, GA Senate=2021, Maine/others=2020); the
election-dropdown/state-card mismatch (switching elections no longer force-jumps to
Georgia; states not on the current ballot show as grayed "Not on this ballot" instead of
disappearing, so the row of cards stays visually stable).

## New future task (user's explicit request 2026-08-08, NOT started — do NOT touch code
## for this without a fresh go-ahead, this is purely logged for later)

**Remove NV and WI state cards, add Ohio (Senate + Governor) and Kansas (Senate).**
Rationale given: NV and WI have nothing on the Nov 3, 2026 ballot we track (confirmed —
`general2026` never included them), so their cards are dead weight; OH and KS would be
genuinely new, relevant 2026 races. Scope this properly before starting, same rigor as
Maine/Governor got today:
  - **Ohio Senate 2026**: whose seat, last contested when (baseline year), real 2026
    nominees once primaries resolve.
  - **Ohio Governor 2026**: same — DeWine is term-limited, an open seat; find the last
    Governor election year for the baseline.
  - **Kansas Senate 2026**: whose seat (Roger Marshall's, if this is his class — verify,
    don't assume), last contested year, real 2026 nominees.
  - For each: MEDSL/Harvard Dataverse baseline data (check the "Precinct-Level Returns
    by Individual State" pattern used for Governor/Maine today — per-state files, much
    smaller than the national files, and check EACH new file for the same "TOTAL mode
    redundancy" and "Guestbook gate" traps hit today before assuming a clean download).
  - Live-feed research for each (same "go to the county/state's own official page,
    never trust search results" method that's worked every time this project has used
    it) — but only AFTER the historical baseline is solid, per the established pattern.
  - Removing NV/WI: just deleting their entries from `STATES`/`EV`/`STATE_NAMES` in
    `api/main.py` — trivial, but do it in the SAME pass as adding OH/KS so the state
    roster only changes once, not twice.

## The Nov 3 readiness plan, in order (carried forward, updated)

**① DONE 2026-08-05 — `mielections.us` ruled out.**

**②-④ DONE — MI county-level build-out complete, 18 counties, ~77-80%.** See "Where we
are" above.

**⑤ Contact county clerks directly** for any MI county that blocks automated access or
has no findable system — same respectful direct-outreach approach already used with
DDHQ. Not started.

**⑥ Follow up on the DDHQ pricing conversation** (contacted 2026-08-04, no response
yet as of this session). Confirmed: DDHQ's API is one unified nationwide system, not
per-state products — whether scoped/cheaper pricing exists is unknown, ask when they
respond.

**⑦ Give TX the same advance attention MI needed reactively.** TX's own March 2026
primary showed real, documented delays (hand-counts, big-county backlogs). Identify
TX's biggest counties' own results systems now, calmly — not started yet.

**⑧ NEW — Maine live-feed research.** Maine's official system is Excel/PDF exports,
not an API (confirmed 2026-08-08). Options to investigate: (a) does AP or a news
aggregator publish a scrapeable JSON feed for ME on election night (some outlets do,
worth checking before assuming this needs a from-scratch county survey); (b) do
Maine's individual counties/municipalities run their own results systems the way MI's
counties did (unlikely given ME's small size and centralized RCV tabulation, but worth
a quick check); (c) worst case, this may need to be accepted as MI-primary-night-style
(no reliable live signal) and planned for accordingly, rather than assumed solvable.

**⑨ NEW — GA/AZ/TX Governor live-feed discovery.** Currently TBD placeholders, same
status Senate's GA/NC/TX/SC slots were in before their primaries forced real research.
GA's mechanism is already proven (same Enhanced Voting system as Senate, just a
different contest — likely trivial to extend `ga_live_feed.py`'s pattern once a real
electionId exists). AZ and TX's Governor races likely ride the same underlying systems
already proven for Senate/President — verify, don't assume.

**⑩ Mid-late Oct, 2026 (already on the calendar):** states publish the real Nov 3
general at 0% reporting. Discover real electionIds for **GA/MI/NC/TX/SC/ME (Senate)**
and **GA/AZ/TX (Governor)** — six states, two races now, not five/one — and fill into
`production_poller.py`'s `build_production_tasks()` (currently mostly `_tbd()`
placeholders — will need real entries for the new Governor race and Maine too, not
just the original five Senate slots). Also: replace MI's "TBD AUG 4" candidate
placeholders in `api/elections.py` with the real certified primary winners — Aug 4's
county data strongly suggested Abdul El-Sayed, but **confirm against an actual
certified/official source before writing it into the manifest**, don't assume from
partial county data alone.

**⑪ ~2 weeks before Nov 3 (scope now includes Governor + Maine):** full dry run, all
tracked states × all tracked races (Senate: GA/MI/NC/TX/SC/ME; Governor: GA/AZ/TX),
against each state's live (empty) Nov feed. **Must specifically test TIMELINESS, not
just final accuracy** — that's the exact gap that let MI's Aug 4 problem go undetected
until election night itself. Any state/race showing MI's "mechanism works but nothing
flows live" pattern gets the same county-level-fallback playbook, with enough lead
time to do it calmly — Maine in particular should be treated as a likely candidate for
this, given today's research found no live API.

**⑫ Election week → Nov 3:** final rehearsal, `ENABLE_POLLER=1` / `POLLER_MODE=prod`,
go live.

## Reminders / gotchas (still true, carried forward + new ones from today)

- `baseline.db` is gitignored — production picks up **live-feed data** automatically
  (the poller writes directly to the persistent disk), but **baseline/historical data**
  (new states, new races) needs either a new GitHub Release + updated `DB_URL`, OR a
  self-seeding PollTask like `etl_governor_2022.py`/`etl_me_baseline.py` use (the
  pattern established today — prefer this for any future one-time historical load,
  it's proven and avoids a manual release-cutting step).
- **Never run `python ingestor/etl_baseline.py`** to add a state/year — destructive,
  rebuilds the whole DB from scratch. Use a dedicated additive script (see
  `etl_governor_2022.py` or `etl_me_baseline.py` for the current best-practice pattern:
  self-downloading with a browser UA, chunked reading, `already_seeded()` idempotency
  check, deletes-own-prior-rows-only before inserting).
- **Dataverse blocks bare Python User-Agents** (403) — always set a real browser UA
  when fetching from `dataverse.harvard.edu`. Some datasets ALSO require a one-time
  "Guestbook" form response before ANY download succeeds regardless of UA (400 Bad
  Request, distinguishable by the actual error message) — if hit again, check whether
  the needed data is small enough to just bake into a committed fixture file instead
  of fighting the download (worked well for Maine).
- **Check for redundant `mode='TOTAL'` rows** in any new MEDSL per-state file before
  trusting a naive sum — some states (GA confirmed) report a `TOTAL` row IN ADDITION
  TO granular per-mode rows for the same precinct, silently ~doubling every count if
  you sum blindly. Always sanity-check a new state's aggregate against a known real
  number before trusting it.
- Always use a **scratch race_type** for any test/mechanics run, never a real one —
  and remember `results_live` is keyed by `(race_type, precinct_id)` only, NOT by
  election — a scratch race_type used in Demo mode is invisible to real elections only
  if it doesn't collide with a real race_type string like `"senate"` or `"governor"`.
- **The simulator (Reset/Next Batch) is now hidden on real elections and primary
  showcases** — if a future new election/race needs the same protection, set
  `"real": True` in its `elections.py` entry (for genuinely-live races) or add its
  race id to `PRIMARY_RACES` in `App.jsx` (for no-baseline intra-party races).
- Local dev: after ANY change under `api/` or `ingestor/`, restart uvicorn (no
  `--reload`) AND reload the UI.

## Doc map (unchanged)
  README.md · CONTEXT.md (start here) · DASHBOARD_GUIDE.md · HANDOVER_BRIEF.md ·
  QUICK_REFERENCE.md · DATA_SETUP.md (updated today — Governor/Maine sources) ·
  PREP.md · TESTING.md · DEPLOY.md · FEED_AUDIT.md (updated today) · PROGRESS.md
  (two new 2026-08-08 entries) · Issues.md
