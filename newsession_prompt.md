We're continuing the Election Forecast Dashboard (C:\Users\subho\election-forecast),
prepping for the real Nov 3, 2026 general election. Read CONTEXT.md first (current-state
snapshot), then FEED_AUDIT.md's live-cadence tables, then PROGRESS.md's 2026-08-08
entries (two of them - the build entry and the "later" debugging/UX-fixes entry) for the
full story of the most recent session, then this prompt.

Where we are (as of 2026-08-08, end of session):

Deployed and confirmed live in production: MI county-level fallback at 18 counties,
~77-80% of the statewide primary vote (Wayne, Oakland, Macomb, Kent, Washtenaw,
Genesee, Ingham, Kalamazoo, Ottawa, Livingston, Saginaw, Bay, Eaton, Muskegon,
Berrien, Monroe, Midland, Calhoun) - paused here by explicit user choice, remaining
counties are mostly small/rural, unlikely to move a general-election outcome much.

GA Governor primary showcase (May 19, 2026, already decided/certified) - proves GA's
live-feed plumbing works against a real primary night, both party fields shown.

GA/AZ/TX Governor 2026 general - full "governor" race type added, baseline = each
state's 2022 result. Real 2026 nominees wired in: Bottoms/Jackson (GA),
Hobbs/Biggs (AZ), Hinojosa/Abbott (TX). Live feed for the real Nov 2026 race is
still TBD - only the historical baseline is built.

Maine added as a new (10th) state - Senate 2026, Collins (R, incumbent) vs Troy
Jackson (D). Baseline = 2020, verified against certified results almost exactly.
Live feed for Nov 2026 is UNRESOLVED - Maine's official site publishes static
Excel/PDF exports per contest, not a live API. Real research needed before Nov 3.

4 real UX/data-safety fixes found by walking the user through the dashboard: hid
Reset/Next Batch for primary showcases (no baseline to replay); relabeled the
GA-only race toggle to "GA Special (Warnock)" so it's discoverable; that toggle now
genuinely disables when viewing any state other than GA; and - the important one -
hid the simulator entirely on real elections (general2026/general2028), since its
Reset button deletes+rewrites results_live scoped only by (race_type, state), not
by election, and general2026's real Senate states share both the race_type string
and several states with Demo mode - an accidental Reset click on Demo could have
wiped real Nov 3 live data.

Also fixed earlier the same session: hardcoded "2020" labels now show the real
baseline year dynamically (matters since Governor=2022, GA Senate=2021); the
election-dropdown/state-card mismatch (switching elections no longer force-jumps to
Georgia; states not on the current ballot show as grayed "Not on this ballot"
instead of disappearing).

NEW FUTURE TASK (user's explicit request, NOT started - do not touch code for this
without a fresh go-ahead): Remove NV and WI state cards (nothing on the Nov 3, 2026
ballot we track), add Ohio (Senate + Governor) and Kansas (Senate). Scope this
properly before starting - whose seats, last-contested baseline years, real 2026
nominees, MEDSL/Dataverse per-state files (check for the same "TOTAL mode
redundancy" and "Guestbook gate" traps hit with Georgia/Maine this session before
assuming a clean download), then live-feed research after the baseline is solid.

The Nov 3 readiness plan, in order (updated):

(1) DONE - mielections.us ruled out.
(2)-(4) DONE - MI county-level build-out complete, 18 counties, ~77-80%.
(5) Contact county clerks directly for blocked/unfindable MI counties - not started.
(6) Follow up on the DDHQ pricing conversation (contacted 2026-08-04, no response
    yet).
(7) Give TX the same advance attention MI needed reactively - not started.
(8) NEW - Maine live-feed research. Check for a news-aggregator JSON feed before
    assuming a from-scratch county survey is needed; check if ME's own
    municipalities run individual systems; worst case, plan for MI-primary-night-
    style unreliability.
(9) NEW - GA/AZ/TX Governor live-feed discovery, same TBD status Senate's slots
    were in before their primaries forced real research. GA likely extends
    ga_live_feed.py's already-proven pattern; verify AZ/TX ride their existing
    proven Senate/President systems, don't assume.
(10) Mid-late Oct 2026: states publish the real Nov 3 general at 0% reporting.
     Discover real electionIds for GA/MI/NC/TX/SC/ME (Senate) and GA/AZ/TX
     (Governor) - six states, two races now. Replace MI's "TBD AUG 4" candidate
     placeholders with the real certified winner (confirm against an official
     source, don't assume from partial county data).
(11) ~2 weeks before Nov 3: full dry run, all tracked states x all tracked races,
     testing TIMELINESS not just final accuracy. Maine is a likely candidate for
     needing the same county-fallback playbook MI needed.
(12) Election week to Nov 3: final rehearsal, ENABLE_POLLER=1 / POLLER_MODE=prod,
     go live.

Reminders / gotchas, carried forward plus new ones from this session:

baseline.db is gitignored - production picks up live-feed data automatically (the
poller writes directly to the persistent disk), but baseline/historical data needs
either a new GitHub Release + updated DB_URL, OR a self-seeding PollTask like
etl_governor_2022.py / etl_me_baseline.py use (prefer this pattern going forward).

Never run python ingestor/etl_baseline.py to add a state/year - destructive,
rebuilds the whole DB from scratch. Use a dedicated additive script.

Dataverse blocks bare Python User-Agents (403) - always set a real browser UA.
Some datasets ALSO require a one-time "Guestbook" form response before ANY
download succeeds regardless of UA (400 Bad Request) - if the needed data is
small, consider baking it into a committed fixture file instead of fighting the
download, like Maine's data.

Check for redundant mode='TOTAL' rows in any new MEDSL per-state file before
trusting a naive sum - some states report a TOTAL row IN ADDITION TO granular
per-mode rows for the same precinct, silently doubling every count. Always
sanity-check a new state's aggregate against a known real number.

The simulator (Reset/Next Batch) is now hidden on real elections and primary
showcases - if a future new election/race needs the same protection, set
"real": True in its elections.py entry, or add its race id to PRIMARY_RACES in
App.jsx.

Local dev: after ANY change under api/ or ingestor/, restart uvicorn (no
--reload) AND reload the UI.
