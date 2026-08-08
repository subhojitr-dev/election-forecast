# Next-session prompt — Election Forecast (NOV 3 READINESS)

Paste the block below to start the next session.

---

We're continuing the **Election Forecast Dashboard** (`C:\Users\subho\election-forecast`),
prepping for the real Nov 3, 2026 general election. Read `CONTEXT.md` first (its
"🗓️ SCHEDULE" table and the MI runbook section have the current state), then
`FEED_AUDIT.md`'s "Round 2 — LIVE CADENCE" section (the state-by-state readiness
evidence this whole plan is built on), then this prompt. Full story of the Aug 4
MI primary night is in `PROGRESS.md`'s 2026-08-04 and 2026-08-05 entries.

## Where we are (as of 2026-08-05)

**The core finding from Aug 4:** a state's live feed *mechanism* working and
matching certified historical results (what all 5 tracked states had before
Aug 4) is a **different, weaker claim** than "delivers usable data during a real
live count." MI had a "strong (mechanism)" rating right up until election night
proved its actual state system (`mvic.sos.state.mi.us/votehistory`) doesn't
publish live data at all — confirmed twice: nothing 3 hours post-close, still
nothing (0-byte results file) 11 hours post-close the next morning. **This is
the central risk for Nov 3: any of GA/NC/TX/SC could have the same gap, and we
won't know until tested against a real count.**

**What was done about it Aug 4, live, under pressure:** found and wired up 4
individual Michigan county results systems (Wayne/TotalVote, Kent/EnhancedVoting,
Washtenaw/custom HTML, Livingston/PDF) as a real-time fallback — genuinely
working, genuinely deployed, but explicitly flagged by the user as **not a
sustainable pattern** — one-off scraper per county doesn't scale to covering
enough of MI, let alone repeating for another state if TX turns out to have the
same problem.

**Retrospective research done the morning after** (not live-tested, but real
evidence from each state's own most recent actual primary): NC (Mar 3, 2026)
and GA (May 19, 2026) both have good evidence of same-night, real-time
reporting. TX (Mar 3, 2026) had a real, documented mess — hand-count delays
past midnight in some counties, big counties (Harris/Dallas/Tarrant)
acknowledged as slow — moderate, bounded risk, not MI-bad, but real. SC and AZ
remain the only states with **firsthand** proof (both directly tested live).

## The Nov 3 readiness plan, in order

**① DONE 2026-08-05 — `mielections.us` ruled out.** Checked twice, 13+ hours
apart, from two independent network vantage points: DNS resolves, nothing
responds on HTTP or HTTPS either time. Not election-night overload — persistently
unreachable. Not worth pursuing further.

**②-④ DONE — MI county-level picture is much better than Aug 4 night
suggested, and the build work is complete.** Went back the next morning and
found last night's "Oakland/Macomb/Genesee Clarity not activated" conclusion
was **wrong** — caused by stale electionIds from a generic web search, not an
actual limitation. Generic MI Clarity ingestor built (accepts base domain as a
parameter — Ottawa's instance is white-labeled on `miottawavotes.gov`, same
platform, different domain), `mi_enhancedvoting_feed.py`'s contest-name
matching is fuzzy (not exact), and the county survey continued well past the
original 11: **18 MI counties now wired with real data, ~77-80% of the
statewide vote** (Wayne, Oakland, Macomb, Kent, Washtenaw, Genesee, Ingham,
Kalamazoo, Ottawa, Livingston, Saginaw, Bay, Eaton, Muskegon, Berrien, Monroe,
Midland, Calhoun). See `FEED_AUDIT.md`'s MI county table and `PROGRESS.md`'s
2026-08-05 entries for the full list, vendors, and numbers. **Still open:**
continue the survey toward ~90% if useful — remaining candidates are mostly
smaller/rural counties, explicitly deprioritized by the user as unlikely to
move a general-election outcome much; Jackson County checked and ruled out
(PDF is precinct-level detail, not the cumulative format the parser expects);
St. Clair checked and ruled out (no live system found).

**⑤ Contact county clerks directly** for any county that blocks automated
access (Oakland's main `oakgov.com` site returned 403 — a separate
`elections.oaklandcountymi.gov` domain wasn't blocked and is worth using
instead) or has no findable online system at all — same respectful,
direct-outreach approach already used with DDHQ.

**⑥ Follow up on the DDHQ pricing conversation** (contacted 2026-08-04, no
public pricing — quote-only, likely a multi-day response). Confirmed via
research: DDHQ's API is one unified **nationwide** system, not per-state
products — but whether they offer *scoped* (fewer-states) pricing is unknown;
ask directly when they respond. If workable, this could replace the whole
county-by-county approach for MI, and possibly serve as a prepared fallback
for TX too.

**⑦ Give TX the same advance attention MI needed reactively.** TX's own March
2026 primary showed real, documented delays for specific counties (hand-counts,
big-county backlogs). Before Nov 3, identify TX's biggest counties' own
results systems now — the same discovery process as MI, done calmly, not
live under time pressure on election night.

**⑧ Mid-late Oct, 2026 (already on the calendar):** states publish the real
Nov 3 general at 0% reporting. Discover real electionIds for GA/MI/NC/TX/SC
and fill into `production_poller.py`'s `build_production_tasks()`. Also:
replace MI's "TBD AUG 4" candidate placeholders in `api/elections.py` with
the real primary winners — Aug 4's county data strongly suggested Abdul
El-Sayed (60%+ across Wayne/Kent/Washtenaw/Livingston), but **confirm against
an actual certified/official source before writing it into the manifest**,
don't assume from partial county data alone.

**⑨ ~2 weeks before Nov 3 (already on the calendar, scope now sharpened):**
full dry run, all 5 tracked states × Senate, against each state's live
(empty) Nov feed. **This must specifically test TIMELINESS, not just final
accuracy** — that's the exact gap that let MI's problem go undetected until
election night itself. If any of GA/NC/TX/SC shows the same "mechanism works
but nothing flows live" pattern, apply the same county-level-fallback
playbook developed for MI, with enough lead time to do it calmly.

**⑩ Election week → Nov 3:** final rehearsal, `ENABLE_POLLER=1` /
`POLLER_MODE=prod`, go live.

## Reminders / gotchas (still true, carried forward)

- `baseline.db` is gitignored — production only picks up local DB changes via
  a new GitHub Release + updated `DB_URL` (current tag: `db-v3`).
- **Never run `python ingestor/etl_baseline.py`** to add a state/year — destructive,
  rebuilds the whole DB from scratch.
- Always use a **scratch race_type** for any test/mechanics run, never a real
  tracked one — this is exactly the class of bug already found and fixed once
  (MI/TX/NC's 2020 baseline, 2026-07-18) and structurally avoided since (every
  ingest() function scopes its `DELETE` to its own precinct_id/race_type).
- For any new county-level ingestor: check `robots.txt` first (CNN and DDHQ
  both explicitly disallow automated access — respected, not worked around).
  Government county-clerk sites so far have had no such restriction.
- Add any new Python dependency to `requirements.txt` in the **same commit**
  as the code that needs it — `beautifulsoup4` was missed once (2026-08-04)
  and crashed the *entire* poller process on Render (not just the one new
  task), since it's a top-level import.
- API runs without `--reload`: restart uvicorn + click Reset in the UI after
  any api/ingestor code change.

## Longer-term / not urgent

- WI and NV live feeds — `general2028` prep only, not gating Nov 3.
- Precinct-level drill-down (GA/NC) — optional precision upgrade.
- `general2028` needs 2022 Senate data loaded (file already on disk).
