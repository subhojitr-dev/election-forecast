We're continuing the Election Forecast Dashboard (C:\Users\subho\election-forecast).
Read CONTEXT.md first — the "🔴 NEXT SESSION — START HERE → LIVE-READINESS" section
has the full current state — then NEXT_SESSION_PROMPT.md.

Where we are: dashboard is deployed & public (Vercel + Render, CORS locked). We're in
LIVE-READINESS — wiring each state's live results feed into results_live using the
county-pseudo-precinct pattern ({ST}-{fips}-CTY), so the analytics run unchanged on
election night. 7 states are DONE and validated:
  - NC, GA, PA, AZ, MI, TX — the original 6 (of 8) target states, all validated to the
    exact certified 2024 general result (nc_live_feed.py/nc_ingestor.py, ga_live_feed.py,
    pa_live_feed.py, az_live_feed.py, mi_live_feed.py, tx_live_feed.py + matching
    etl_*_county_baseline.py each). AZ/MI are PRIMARY-NIGHT READY for Jul 21 / Aug 4 — see
    CONTEXT.md's runbook. MI needs a HEADED browser at runtime; TX only needs headless;
    the rest are plain httpx.
  - SC — a NEW 9th state, not one of the original 8 (had zero data loaded before this).
    Added because SC's Senate seat (Graham, Class 2) IS up in 2026, same class as
    GA/MI/NC/TX. Baseline loaded from scratch via etl_sc_baseline.py (do NOT use the
    original etl_baseline.py to add a state — it drops+rebuilds the whole DB from its 5
    hardcoded sources, destroying every other state's live-feed work). Live feed:
    sc_live_feed.py — SC's Clarity ENR (enr-scvotes.org) is the ONE place the classic
    Clarity mechanism (current_ver.txt) is still fully alive, plain httpx, no
    Cloudflare/WAF/Playwright at all — the simplest state wired this project. Validated
    against SC's real June 2026 primary (exact statewide + per-candidate match, 46/46
    counties). Real 2026 nominees are in the manifest: Lindsey Graham (R, incumbent) vs
    Annie Andrews (D) — pulled directly from the June primary results. Added SC to
    api/main.py's EV (9) + STATE_NAMES dicts (REQUIRED — the states endpoint sums EV
    unconditionally and crashes without it). Did NOT add SC to ALL8/the demo election —
    scoped to general2026 only.

Production DB is a static release snapshot (GitHub Release db-v1) — SC (and all the
county-pseudo baselines from this session) are LOCAL ONLY until someone re-gzips and
re-uploads baseline.db.gz. Nothing pushed to the release yet.

NV and WI remain DEPRIORITIZED — neither has a Senate or President race on the Nov 3, 2026
ballot (both Class 3, next up 2028; confirmed against api/elections.py). WI is additionally
the hardest case (no statewide feed, 72 county clerk sites); AP Elections API re-priced
WI-specific, still quote-only, no shortcut found. Revisit both ahead of general2028
whenever there's runway — not urgent.

Clarity is DEAD everywhere checked EXCEPT SC (genuinely still alive there — don't assume
"Clarity = dead" as a blanket rule, verify per state). Playwright is a hard runtime
dependency for MI (headed) and TX (headless); everything else (NC/GA/PA/AZ/SC) is plain
httpx.

The plan, in order — do these:
  1. WI — only if there's spare runway; see CONTEXT.md's scoping note first (survey a
     handful of real county sites, don't commit blind). Not gating Nov 2026 — treat as
     2028 prep. Aug 11 primary is a free test window if picked up.
  2. NV — same low urgency as WI; revisit whenever convenient for 2028 prep.
  3. Before Jul 21 / Aug 4: nothing left to BUILD for AZ/MI — just run the runbook
     commands in CONTEXT.md on the actual nights and report the live validation results.
  4. Whenever convenient: re-gzip + re-upload baseline.db to the GitHub Release so SC (and
     the rest of this session's work) actually reaches production — see DEPLOY.md. Also
     get SC's Nov 2026 electionId once enr-scvotes.org/SC/elections.json populates it
     (currently empty).

Gotchas: every *_live_feed.py must DELETE ... WHERE precinct_id LIKE '{ST}-%' first (not
just -CTY) or leftover precinct-level rows double-count. Party may be embedded in the
candidate NAME suffix OR the CONTEST name suffix (check both). SC's contest names have
literal DOUBLE SPACES ("U.S.  Senate  - REP") — substring-match, don't rely on exact
string equality. Each state needs a county-pseudo baseline too unless one already exists.
Adding a state NOT in the original 8 (like SC) is a bigger job than wiring a live feed for
an existing one: write a dedicated additive baseline loader (never touch the original
etl_baseline.py — it's destructive), then add EV/STATE_NAMES entries in api/main.py
(required, not cosmetic). baseline.db is gitignored, so local DB changes don't touch
production (see the note above about re-publishing). API runs without --reload → restart
uvicorn + click Reset in the UI after api/ingestor changes. MI needs a HEADED browser at
runtime; TX only needs headless. Before committing to a state, check whether it actually
has a race on the CURRENT election's manifest (api/elections.py) — NV/WI didn't.

Nothing is queued to build right now beyond WI/NV (both low-urgency). Report findings at
each step before moving on if picking either up (my working rule).
