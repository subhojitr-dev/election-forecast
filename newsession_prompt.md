We're continuing the Election Forecast Dashboard (C:\Users\subho\election-forecast),
prepping for the real Nov 3, 2026 general election. Read CONTEXT.md first (its
SCHEDULE table and the MI runbook section have the current state), then
FEED_AUDIT.md's "Round 2 - LIVE CADENCE" section (the state-by-state readiness
evidence this whole plan is built on), then this prompt. Full story of the Aug 4
MI primary night is in PROGRESS.md's 2026-08-04 and 2026-08-05 entries.

Where we are (as of 2026-08-05): The core finding from Aug 4 is that a state's
live feed mechanism working and matching certified historical results (what all
5 tracked states had before Aug 4) is a different, weaker claim than "delivers
usable data during a real live count." MI had a "strong (mechanism)" rating
right up until election night proved its actual state system
(mvic.sos.state.mi.us/votehistory) doesn't publish live data at all -
confirmed twice: nothing 3 hours post-close, still nothing (0-byte results
file) 11 hours post-close the next morning. This is the central risk for
Nov 3: any of GA/NC/TX/SC could have the same gap, and we won't know until
tested against a real count.

What was done about it Aug 4, live, under pressure: found and wired up 4
individual Michigan county results systems (Wayne/TotalVote,
Kent/EnhancedVoting, Washtenaw/custom HTML, Livingston/PDF) as a real-time
fallback - genuinely working, genuinely deployed, but explicitly flagged by
the user as not a sustainable pattern - one-off scraper per county doesn't
scale to covering enough of MI, let alone repeating for another state if TX
turns out to have the same problem.

Retrospective research done the morning after (not live-tested, but real
evidence from each state's own most recent actual primary): NC (Mar 3, 2026)
and GA (May 19, 2026) both have good evidence of same-night, real-time
reporting. TX (Mar 3, 2026) had a real, documented mess - hand-count delays
past midnight in some counties, big counties (Harris/Dallas/Tarrant)
acknowledged as slow - moderate, bounded risk, not MI-bad, but real. SC and AZ
remain the only states with firsthand proof (both directly tested live).

The Nov 3 readiness plan, in order:

1. First (cheap, do immediately): re-check mielections.us. This is a separate
   official MI domain from votehistory, found via michigan.gov's own link -
   unreachable from multiple independent connections during Aug 4's peak
   traffic (likely overload, not a dead end). If it's actually a fast,
   unified statewide MI portal once traffic is normal, it could replace most
   of the county-by-county work below. One check settles this - do it before
   investing further in MI county work.

2. Turn MI's "4 one-off scrapers" into a smaller set of vendor-level
   ingestors, then just add counties. The real insight: MI's 83 counties use
   a handful of vendors, not 83 unique systems. mi_totalvote_feed.py and
   mi_enhancedvoting_feed.py are already vendor-generic - adding another
   county on either is a one-line addition to production_poller.py's
   MI_TOTALVOTE_COUNTIES / MI_ENHANCEDVOTING_COUNTIES lists, zero new code.
   mi_washtenaw_feed.py and mi_livingston_feed.py are genuine one-offs
   (custom system, PDF) - fine to leave as-is. The actual task is discovery,
   not engineering: find which of MI's other big counties are on TotalVote
   or EnhancedVoting.

3. Re-check Oakland, Macomb, and Genesee's Clarity instances. All three said
   "Elections not available!" on Aug 4 - meaning not yet activated, not that
   Clarity itself is a dead end. Clarity is a platform this project already
   has strong, proven tooling for (same family as GA/AZ). If active now,
   that's 3 more counties essentially for free.

4. A calm, proper survey of MI's top ~15-20 counties by population - MI's
   vote is concentrated enough that this likely covers 75%+ of the state.
   Candidates to check next: Oakland, Macomb, Genesee (#3 above), then
   Ingham, Ottawa, Kalamazoo, Saginaw, Berrien, and others. For each: find
   their actual results page, identify the vendor, and either add to an
   existing vendor list (cheap) or decide if a new one-off is worth it.

5. Contact county clerks directly for any county that blocks automated
   access (Oakland's main oakgov.com site returned 403 - a separate
   elections.oaklandcountymi.gov domain wasn't blocked and is worth using
   instead) or has no findable online system at all.

6. Follow up on the DDHQ pricing conversation (contacted 2026-08-04, no
   public pricing - quote-only). Confirmed via research: DDHQ's API is one
   unified nationwide system, not per-state products - but whether they
   offer scoped (fewer-states) pricing is unknown, ask directly when they
   respond. If workable, this could replace the whole county-by-county
   approach for MI, and possibly serve as a prepared fallback for TX too.

7. Give TX the same advance attention MI needed reactively. TX's own March
   2026 primary showed real, documented delays for specific counties
   (hand-counts, big-county backlogs). Before Nov 3, identify TX's biggest
   counties' own results systems now.

8. Mid-late Oct, 2026 (already on the calendar): states publish the real
   Nov 3 general at 0% reporting. Discover real electionIds for GA/MI/NC/TX/SC
   and fill into production_poller.py's build_production_tasks(). Also:
   replace MI's "TBD AUG 4" candidate placeholders in api/elections.py with
   the real primary winners - Aug 4's county data strongly suggested Abdul
   El-Sayed (60%+ across Wayne/Kent/Washtenaw/Livingston), but confirm
   against an actual certified/official source before writing it into the
   manifest, don't assume from partial county data alone.

9. ~2 weeks before Nov 3 (already on the calendar, scope now sharpened): full
   dry run, all 5 tracked states x Senate, against each state's live (empty)
   Nov feed. This must specifically test TIMELINESS, not just final
   accuracy - that's the exact gap that let MI's problem go undetected until
   election night itself. If any of GA/NC/TX/SC shows the same "mechanism
   works but nothing flows live" pattern, apply the same
   county-level-fallback playbook developed for MI, with enough lead time to
   do it calmly.

10. Election week -> Nov 3: final rehearsal, ENABLE_POLLER=1 /
    POLLER_MODE=prod, go live.

Reminders / gotchas (still true, carried forward): baseline.db is gitignored
- production only picks up local DB changes via a new GitHub Release +
updated DB_URL (current tag: db-v3). Never run
python ingestor/etl_baseline.py to add a state/year - destructive, rebuilds
the whole DB from scratch. Always use a scratch race_type for any
test/mechanics run, never a real tracked one. For any new county-level
ingestor: check robots.txt first (CNN and DDHQ both explicitly disallow
automated access - respected, not worked around); government county-clerk
sites so far have had no such restriction. Add any new Python dependency to
requirements.txt in the SAME commit as the code that needs it -
beautifulsoup4 was missed once (2026-08-04) and crashed the entire poller
process on Render, since it's a top-level import. API runs without --reload:
restart uvicorn + click Reset in the UI after any api/ingestor code change.

Longer-term / not urgent: WI and NV live feeds (general2028 prep only);
precinct-level drill-down for GA/NC (optional precision upgrade);
general2028 needs 2022 Senate data loaded (file already on disk).
