"""production_poller.py — the real election-night scheduler.

Wraps every state's `*_live_feed.py` `ingest()` call in a loop, polling each
on its own interval. This REPLACES the manual "run the script by hand" steps
used everywhere else in this project — same `results_live` writes, same
analytics, nothing else in the app changes (that's the whole point of the
county-pseudo-precinct design: the poller is just a scheduler around calls
that already work).

⚠️ THE REAL PER-STATE ARGUMENTS BELOW ARE MOSTLY "TBD" — this is deliberate,
not an oversight. States don't publish their real Nov 3, 2026 election IDs
until ~2 weeks before (see PREP.md's timeline) — there is nothing real to
poll yet. `PRODUCTION_TASKS` is the config to fill in once each state
publishes its 0%-reporting general-election page (mid–late October):
  - AZ: id is already known & stable (68 is the 2026 PRIMARY; the general's
    id will be a NEW number — check `az_election_ids()`'s pattern once it's
    live) — but AZ isn't even in `general2026`, so it's not listed below.
  - MI/TX: auto-discover already (the script finds the id itself each poll —
    just needs the right target DATE/year plugged in once known).
  - GA/SC: need a fresh manual id lookup each cycle (see FEED_AUDIT.md).
  - NC: date-based like MI/TX once the 2026 general date is confirmed.
Only GA/MI/NC/TX/SC matter for Nov 2026 (the `general2026` senate list) —
PA/AZ aren't tracked until `general2028`.

WHAT'S TESTABLE TODAY: the scheduler mechanism itself — interval handling,
per-task error isolation (one state failing doesn't take down the others),
logging, and (on Linux only) MI's Xvfb-backed headed-browser launch. Use
`--mode test` to run the SAME loop against the archived 2024 general /
2021 runoff / June 2026 primary data already used in TESTING.md — proves
the poller works end-to-end without touching anything real. `--once` does
a single pass through every task instead of looping forever (for a quick
smoke test rather than watching it run).

Run:
    python ingestor/production_poller.py --mode test --once   # one full pass, test data
    python ingestor/production_poller.py --mode test          # loops forever, test data
    python ingestor/production_poller.py --mode prod          # the real thing (once TASKS below are filled in)
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import az_live_feed
import ga_live_feed
import mi_live_feed
import nc_live_feed
import pa_live_feed
import sc_live_feed
import tx_live_feed


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Task definition — each is a zero-arg callable (state/race/args already
# bound) plus how often to poll it. Kept as plain functions, not lambdas
# with captured loop variables, to avoid the classic late-binding bug.
# ---------------------------------------------------------------------------
@dataclass
class PollTask:
    name: str                      # "GA senate" — just for logging
    interval_s: int                # how often to poll this one
    fn: Callable[[], dict]         # zero-arg -> the ingest() summary dict
    enabled: bool = True           # False for "TBD" tasks — logged once, skipped
    last_run: float = field(default=0.0, init=False)

    def due(self, now: float) -> bool:
        return self.enabled and (now - self.last_run) >= self.interval_s


def _tbd(name):
    """Placeholder for a real-production task whose election id isn't known
    yet. Keeps the schedule fully defined (so filling in the real id later
    is a one-line change) without the poller trying to hit a nonexistent
    election."""
    def _run():
        log(f"  {name}: SKIPPED — real electionId not configured yet (see PREP.md)")
        return None
    return _run


# ---------------------------------------------------------------------------
# TEST config — archived elections, exactly the ones validated in
# TESTING.md §8. Proves the scheduler mechanism against real (if old) data.
# ---------------------------------------------------------------------------
def build_test_tasks() -> list[PollTask]:
    return [
        PollTask("GA president (2024NovGen)", 90,
                  lambda: ga_live_feed.ingest("2024NovGen", "President of the US", "president")),
        PollTask("GA senate (2021JanFedRun)", 90,
                  lambda: ga_live_feed.ingest("2021JanFedRun", "US Senate (Perdue)", "senate")),
        PollTask("NC senate (2020-11-03)", 60,
                  lambda: nc_live_feed.ingest("2020-11-03", "US SENATE", "senate")),
        PollTask("PA senate (105/G)", 75,
                  lambda: pa_live_feed.ingest("105", "G", "2", "senate")),
        PollTask("TX senate (2024/G)", 120,
                  lambda: tx_live_feed.ingest(
                      tx_live_feed.discover_election_id("2024", "G"), "7958", "senate")),
        PollTask("SC senate-REP (126294)", 60,
                  lambda: sc_live_feed.ingest("126294", "26001", "sc_poller_test_rep")),
        PollTask("MI senate (11/5/2024)", 180,
                  lambda: mi_live_feed.ingest(
                      mi_live_feed.discover_election_id("11/5/2024"), "senate"),
                  enabled=_mi_available()),
    ]


# ---------------------------------------------------------------------------
# PRODUCTION config — fill in real electionIds here as they're published
# (mid–late Oct 2026). Only the 5 states general2026 actually tracks.
# ---------------------------------------------------------------------------
def build_production_tasks() -> list[PollTask]:
    return [
        # GA: id is a human-readable string per election (e.g. "2026NovGen")
        # — check FEED_AUDIT.md / results.sos.ga.gov once GA configures it.
        PollTask("GA senate", 60, _tbd("GA senate"), enabled=False),
        # MI: auto-discovers from a date string — just needs the real date
        # (should be "11/3/2026") once MI's #ElectionDateId lists it.
        PollTask("MI senate", 90,
                  lambda: mi_live_feed.ingest(
                      mi_live_feed.discover_election_id("11/3/2026"), "senate"),
                  enabled=_mi_available()),
        # NC: same shape as the test task, just needs the real Nov 2026 date.
        PollTask("NC senate", 60, _tbd("NC senate"), enabled=False),
        # TX: auto-discovers via year+type — "2026"/"G" should just work once
        # results.texas-election.com configures the general.
        PollTask("TX senate", 60,
                  lambda: tx_live_feed.ingest(
                      tx_live_feed.discover_election_id("2026", "G"), "7958", "senate")),
        # SC: elections.json is empty between elections — needs a manual
        # electionId + contest-code lookup once it's live (see FEED_AUDIT.md).
        PollTask("SC senate", 60, _tbd("SC senate"), enabled=False),
    ]


# ---------------------------------------------------------------------------
# MI needs a real (virtual) display for its headed-browser requirement.
# Xvfb only exists on Linux — start it once at poller startup, before any
# MI task runs. On non-Linux (local dev), MI's task is simply disabled
# rather than crashing the whole poller — the other 6 states still get
# fully exercised locally.
# ---------------------------------------------------------------------------
_xvfb_started = False


def _mi_available() -> bool:
    return platform.system() == "Linux" and shutil.which("Xvfb") is not None


def start_xvfb_if_needed(tasks: list[PollTask]):
    global _xvfb_started
    if _xvfb_started or not any(t.name.startswith("MI") and t.enabled for t in tasks):
        return
    if not _mi_available():
        log("MI task present but Xvfb unavailable on this host (need Linux) — MI stays disabled.")
        return
    log("Starting Xvfb :99 for MI's headed-browser requirement ...")
    subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1024x768x24"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.environ["DISPLAY"] = ":99"
    time.sleep(2)   # give the X server a moment to come up before Chromium tries to attach
    _xvfb_started = True
    log("Xvfb ready (DISPLAY=:99).")


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------
def run(tasks: list[PollTask], once: bool):
    start_xvfb_if_needed(tasks)
    log(f"Poller starting — {len(tasks)} tasks "
        f"({sum(t.enabled for t in tasks)} enabled, {sum(not t.enabled for t in tasks)} TBD/disabled).")
    while True:
        now = time.time()
        ran_any = False
        for t in tasks:
            if not t.due(now):
                continue
            ran_any = True
            t.last_run = now
            try:
                summary = t.fn()
                if summary is not None:
                    log(f"  {t.name}: OK — {summary}")
            except Exception as e:
                log(f"  {t.name}: FAILED — {type(e).__name__}: {e}")
                log("    " + traceback.format_exc().replace("\n", "\n    "))
        if once:
            log("--once: single pass complete, exiting.")
            return
        if not ran_any:
            time.sleep(5)   # nothing due yet — check again shortly


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["test", "prod"], default="test")
    parser.add_argument("--once", action="store_true",
                        help="single pass through all tasks, then exit (for smoke-testing)")
    args = parser.parse_args()

    task_list = build_test_tasks() if args.mode == "test" else build_production_tasks()
    run(task_list, once=args.once)
