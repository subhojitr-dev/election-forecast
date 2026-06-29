"""
clarity_poller.py  —  Phase 2 live ingestor (core)
Election Forecast Dashboard

This is the engine that, given a *feed*, keeps the `results_live` table in the
SQLite DB continuously up to date. A "feed" is any source that can hand us the
current snapshot of an election:

    - LiveClarityFeed  : real Clarity ENR XML over HTTP (used on election night)
    - ClarityFileFeed  : a saved Clarity XML file (validates the parse path)
    - ReplayFeed       : replays a real past election from baseline.db   (replay_harness.py)
    - MockFeed         : synthetic generated results                     (mock_feed.py)

All feeds implement the same tiny interface (`FeedSource.next_snapshot()`), so
the poller does not care where the data comes from. That is what lets us build
and test today — months before any 2026 data exists — against archived/mock
data, then swap in the live feed in November with zero changes to the poller.

IMPORTANT REALITY (June 2026): Clarity's CDN currently returns HTTP 403 to
direct programmatic requests, and the `clarify` library's URL parser predates
Clarity's newer version strings. So LiveClarityFeed is written and ready, but
the *validated, working* end-to-end paths today are ReplayFeed and MockFeed.
Live fetching gets a final shakeout closer to the election (see HANDOVER_BRIEF).
"""

from __future__ import annotations

import io
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "data", "db", "baseline.db")

UA_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# A single point-in-time snapshot of a race, normalized into rows we can store.
# ---------------------------------------------------------------------------
@dataclass
class LiveRow:
    precinct_id: str          # must match precincts.id  ('{ST}-{fips}-{name}')
    candidate: str
    party: str                # DEM | REP | LIB | GRE | OTH
    votes: int
    mode: str = "all"         # ballot type: election_day | early | mail | military | all


@dataclass
class Snapshot:
    version: str                      # changes when results change; lets us skip no-ops
    rows: list[LiveRow]
    precincts_reporting: int
    total_precincts: int
    label: str = ""                   # human description for logging
    extra: dict = field(default_factory=dict)

    @property
    def pct_reporting(self) -> float:
        return (100.0 * self.precincts_reporting / self.total_precincts
                if self.total_precincts else 0.0)


# ---------------------------------------------------------------------------
# Feed interface — every data source implements this.
# ---------------------------------------------------------------------------
class FeedSource(ABC):
    race_type: str            # 'president' | 'senate'
    state_abbr: str           # 'GA', 'PA', ...

    @abstractmethod
    def next_snapshot(self) -> Optional[Snapshot]:
        """Return the next Snapshot, or None when the feed is exhausted
        (replay/mock finished). A live feed never returns None; it just keeps
        returning the latest snapshot (possibly with an unchanged version)."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Clarity XML -> normalized rows  (shared by live + file feeds)
# ---------------------------------------------------------------------------
PARTY_MAP = {"DEMOCRAT": "DEM", "DEM": "DEM", "REPUBLICAN": "REP", "REP": "REP",
             "LIBERTARIAN": "LIB", "LIB": "LIB", "GREEN": "GRE", "GRE": "GRE"}


def _map_party(p) -> str:
    if not isinstance(p, str):
        return "OTH"
    return PARTY_MAP.get(p.strip().upper(), "OTH")


def parse_clarity_xml(xml_bytes: bytes, race_type: str, state_abbr: str,
                      contest_filter: str, county_fips: str = "XXXXX"):
    """
    Parse a Clarity detail XML payload into (rows, precincts_reported, total).

    - contest_filter: substring to pick the race we care about from the many
      contests in a real feed (e.g. 'President', 'United States Senator').
    - Votes are SUMMED across vote_type/mode per precinct+candidate, matching
      how the historical ETL collapses modes. (Mode-level storage for the
      red-mirage feature is a future enhancement; results_live has no mode col.)
    - Statistical choices (Undervotes/Overvotes -> choice is None) are skipped.

    NOTE on precinct_id mapping: matching Clarity precinct *names* to our
    baseline precinct_ids is the genuinely hard part of going live (name spelling
    differs between sources). Here we build '{ST}-{county_fips}-{name}'. For the
    saved-file validation path county_fips is unknown, so it's a placeholder —
    that path proves parsing, not joinability. ReplayFeed sidesteps this entirely
    by using baseline precinct_ids directly.
    """
    import clarify

    # clarify.Parser.parse wants a filename or file-like; give it a BytesIO.
    p = clarify.Parser()
    try:
        p.parse(io.BytesIO(xml_bytes))
    except Exception:
        # fallback: some lxml paths prefer a real file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tf:
            tf.write(xml_bytes)
            tmp = tf.name
        p.parse(tmp)
        os.unlink(tmp)

    # pick the contest matching our race
    contests = [c for c in p.contests if contest_filter.lower() in (c.text or "").lower()]
    if not contests:
        raise ValueError(f"No contest matching {contest_filter!r}; "
                         f"available: {[c.text for c in p.contests]}")
    contest = contests[0]

    reported = contest.precincts_reported or 0
    total = (contest.precincts_participating or contest.precincts_reported or 0)

    # sum modes per (precinct, candidate)
    agg: dict[tuple, int] = {}
    party_of: dict[str, str] = {}
    for r in p.results:
        if r.contest.text != contest.text:
            continue
        if r.choice is None:          # Undervotes/Overvotes etc.
            continue
        if r.jurisdiction is None:    # county/state total — we keep precinct grain
            continue
        cand = r.choice.text
        party_of[cand] = _map_party(getattr(r.choice, "party", None))
        key = (r.jurisdiction.name, cand)
        agg[key] = agg.get(key, 0) + int(r.votes or 0)

    rows = [LiveRow(precinct_id=f"{state_abbr}-{county_fips}-{pname}",
                    candidate=cand, party=party_of[cand], votes=v)
            for (pname, cand), v in agg.items()]
    return rows, reported, total


# ---------------------------------------------------------------------------
# Writing a snapshot into results_live
# ---------------------------------------------------------------------------
def write_snapshot(conn: sqlite3.Connection, race_type: str, state_abbr: str,
                   snap: Snapshot, commit: bool = True):
    """
    Replace the live rows for this race+state with the current snapshot.
    results_live always reflects the *latest* picture (one row per
    precinct+candidate). vote_share is recomputed per precinct.
    """
    cur = conn.cursor()
    # clear prior live rows for this race + state (precinct_id is '{ST}-...')
    cur.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE ?",
                (race_type, f"{state_abbr}-%"))

    # per-precinct totals for vote_share
    ptot: dict[str, int] = {}
    for r in snap.rows:
        ptot[r.precinct_id] = ptot.get(r.precinct_id, 0) + r.votes

    payload = [
        (r.precinct_id, race_type, r.candidate, r.party, r.votes,
         (r.votes / ptot[r.precinct_id]) if ptot[r.precinct_id] else 0.0,
         snap.precincts_reporting, snap.total_precincts, getattr(r, "mode", "all"))
        for r in snap.rows
    ]
    cur.executemany(
        """INSERT INTO results_live
           (precinct_id, race_type, candidate, party, votes, vote_share,
            precincts_reporting, total_precincts, mode)
           VALUES (?,?,?,?,?,?,?,?,?)""", payload)
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# The polling loop — feed-agnostic
# ---------------------------------------------------------------------------
def run_poller(feed: FeedSource, *, interval: float = 0.0,
               max_polls: Optional[int] = None, db_path: str = DB_PATH,
               verbose: bool = True, on_write=None) -> int:
    """
    Drive a feed: repeatedly pull the next snapshot, and if its version changed
    since last poll, write it to results_live. Returns number of snapshots written.

    - interval: seconds between polls (60 on election night; 0 for fast replay).
    - max_polls: safety cap (None = until the feed is exhausted / Ctrl-C).
    - Skips writes when the feed version is unchanged (brief's requirement:
      "skip if version unchanged since last poll").
    - on_write(conn, snap): optional hook called after each NEW snapshot is
      written (Phase 3 uses it to compute + record analytics).
    """
    conn = sqlite3.connect(db_path)
    last_version = None
    polls = written = 0
    if verbose:
        log(f"[poller] start: {feed.state_abbr} {feed.race_type} "
            f"(interval={interval}s, db={os.path.basename(db_path)})")
    try:
        while True:
            snap = feed.next_snapshot()
            if snap is None:
                if verbose:
                    log("[poller] feed exhausted — stopping.")
                break
            polls += 1
            if snap.version == last_version:
                if verbose:
                    log(f"[poll {polls:>3}] version unchanged ({snap.version}) — skip")
            else:
                write_snapshot(conn, feed.race_type, feed.state_abbr, snap)
                last_version = snap.version
                written += 1
                if verbose:
                    lead = _leader_line(conn, feed.race_type, feed.state_abbr)
                    log(f"[poll {polls:>3}] v={snap.version:<10} "
                        f"{snap.precincts_reporting:>5}/{snap.total_precincts:<5} "
                        f"({snap.pct_reporting:5.1f}%) {snap.label}  {lead}")
                if on_write:
                    on_write(conn, snap)
            if max_polls and polls >= max_polls:
                if verbose:
                    log(f"[poller] hit max_polls={max_polls} — stopping.")
                break
            if interval:
                time.sleep(interval)
    except KeyboardInterrupt:
        log("\n[poller] interrupted by user — stopping cleanly.")
    finally:
        conn.close()
    if verbose:
        log(f"[poller] done: {polls} polls, {written} snapshots written.")
    return written


def _leader_line(conn, race_type, state_abbr) -> str:
    """Quick D vs R total from current live rows, for progress logging."""
    row = conn.execute(
        """SELECT
             SUM(CASE WHEN party='DEM' THEN votes ELSE 0 END),
             SUM(CASE WHEN party='REP' THEN votes ELSE 0 END)
           FROM results_live WHERE race_type=? AND precinct_id LIKE ?""",
        (race_type, f"{state_abbr}-%")).fetchone()
    d, r = (row[0] or 0), (row[1] or 0)
    if d == r == 0:
        return ""
    who = "D" if d > r else "R"
    return f"| D {d:,} / R {r:,}  ({who}+{abs(d-r):,})"


# ---------------------------------------------------------------------------
# Live feed (ready for November; 403-blocked today — see module docstring)
# ---------------------------------------------------------------------------
class LiveClarityFeed(FeedSource):
    """
    Fetches real Clarity ENR results over HTTP. Built and ready; needs a final
    shakeout near the election because (a) Clarity's CDN currently 403s scrapers
    and (b) the election_id + version discovery for Nov-2026 is not knowable yet.
    """
    def __init__(self, state_abbr: str, race_type: str, election_id: str,
                 contest_filter: str, base="https://results.enr.clarityelections.com",
                 session=None):
        import requests
        self.state_abbr = state_abbr
        self.race_type = race_type
        self.election_id = election_id
        self.contest_filter = contest_filter
        self.base = base
        self.session = session or requests.Session()
        self.session.headers.update(UA_HEADER)

    def _current_version(self) -> str:
        url = f"{self.base}/{self.state_abbr}/{self.election_id}/current_ver.txt"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        return r.text.strip()

    def _detail_zip_url(self, version: str) -> str:
        return (f"{self.base}/{self.state_abbr}/{self.election_id}/{version}"
                f"/reports/detailxml.zip")

    def next_snapshot(self) -> Optional[Snapshot]:
        import zipfile
        version = self._current_version()
        r = self.session.get(self._detail_zip_url(version), timeout=60)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            xml_bytes = z.read(z.namelist()[0])
        rows, reported, total = parse_clarity_xml(
            xml_bytes, self.race_type, self.state_abbr, self.contest_filter)
        return Snapshot(version=version, rows=rows,
                        precincts_reporting=reported, total_precincts=total,
                        label="(live)")


# ---------------------------------------------------------------------------
# One-shot feed from a saved Clarity XML file (validates the parse path)
# ---------------------------------------------------------------------------
class ClarityFileFeed(FeedSource):
    """Serves a single saved Clarity XML once (then exhausts). Proves that the
    real-format parsing + write path works end to end, without any network."""
    def __init__(self, path: str, race_type: str, state_abbr: str,
                 contest_filter: str, county_fips: str = "XXXXX"):
        self.path = path
        self.race_type = race_type
        self.state_abbr = state_abbr
        self.contest_filter = contest_filter
        self.county_fips = county_fips
        self._served = False

    def next_snapshot(self) -> Optional[Snapshot]:
        if self._served:
            return None
        self._served = True
        with open(self.path, "rb") as f:
            xml_bytes = f.read()
        rows, reported, total = parse_clarity_xml(
            xml_bytes, self.race_type, self.state_abbr, self.contest_filter,
            county_fips=self.county_fips)
        return Snapshot(version="file-1", rows=rows,
                        precincts_reporting=reported, total_precincts=total,
                        label=f"(file:{os.path.basename(self.path)})")


if __name__ == "__main__":
    # Smoke test: parse the bundled KY 2014 sample and write it to results_live.
    sample = os.path.join(ROOT, "data", "raw", "clarity_samples", "precinct.xml")
    log("Smoke test — parsing real Clarity sample (KY 2014 US Senate - REP):")
    feed = ClarityFileFeed(sample, race_type="senate", state_abbr="KY",
                           contest_filter="US Senator", county_fips="21089")
    run_poller(feed, interval=0, db_path=DB_PATH)
    # show what landed, then clean it up (KY sample is not part of our baseline)
    conn = sqlite3.connect(DB_PATH)
    n = conn.execute("SELECT COUNT(*) FROM results_live WHERE precinct_id LIKE 'KY-%'").fetchone()[0]
    log(f"\nresults_live KY rows written: {n}")
    for r in conn.execute("""SELECT candidate, SUM(votes) v FROM results_live
                             WHERE precinct_id LIKE 'KY-%' GROUP BY candidate
                             ORDER BY v DESC"""):
        log(f"   {r[0]:30} {r[1]:>6,}")
    conn.execute("DELETE FROM results_live WHERE precinct_id LIKE 'KY-%'")
    conn.commit(); conn.close()
    log("\n(cleaned up KY smoke-test rows from results_live)")
