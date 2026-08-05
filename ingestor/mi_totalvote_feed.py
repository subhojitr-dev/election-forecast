"""mi_totalvote_feed.py — Michigan county-level live results via TotalVote.

Discovered 2026-08-04, live on Aug 4 primary night: Michigan's own centralized
state system (mvic.sos.state.mi.us/votehistory, see mi_live_feed.py) only shows
a county once it's 100% fully reported — no partial signal, ever. But at least
some individual counties (confirmed: Wayne) run their own live, continuously-
updating results system at michigan.totalvote.com/{County}/ResultsSW.aspx,
which DOES show partial, precinct-by-precinct progress in real time. This
ingestor pulls one county at a time from that system, scoped to the DEM
US Senate primary only (see mi_live_feed.py's `parties` param for why —
same reasoning applies here: the GOP primary isn't a real contest tonight).

No robots.txt restriction found on michigan.totalvote.com, and this is the
county's own official government results page (linked directly from
waynecountymi.gov) — same category as the state ENR/Clarity systems this
project already scrapes for every other state, not a licensed commercial
product like AP or Decision Desk HQ (which this project deliberately does
NOT scrape — see production_poller.py and PROGRESS.md's 2026-08-04 entries).

Confirmed county slugs + county IDs (cid) — add more as they're found:
    Wayne: slug="Wayne", cid="05"

Each ingest() call only touches ITS OWN county's precinct_id row (not a
blanket `LIKE 'MI-%'` delete like mi_live_feed.py uses) — deliberately, so
polling multiple counties via separate calls doesn't wipe each other out,
and so mi_live_feed.py's own broader delete+insert (if MI's state system
ever gets going) can cleanly supersede these partial per-county rows with
the authoritative statewide picture once it's actually available.

Usage:
    python ingestor/mi_totalvote_feed.py Wayne 05 26163 WAYNE
"""
from __future__ import annotations

import os
import re
import sqlite3

import httpx
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "data", "db", "baseline.db")
BASE = "https://michigan.totalvote.com"

CONTEST_TITLE = "United States Senator (DEM)"


def fetch_senate_dem(county_slug: str, cid: str):
    """Returns (candidates, reporting, total) where candidates is a list of
    (name, votes) tuples for the DEM US Senate primary in this county."""
    url = f"{BASE}/{county_slug}/ResultsSW.aspx?type=FED&cid={cid}&map="
    r = httpx.get(url, timeout=20, follow_redirects=True,
                  headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    for wrapper in soup.select("div.wrapper-inside.wrapper-border"):
        title_el = wrapper.select_one("div.display-results-box-a h1")
        if not title_el or not title_el.get_text(" ", strip=True).startswith(CONTEST_TITLE):
            continue
        reporting_el = wrapper.select_one("div.precinct-fully")
        m = re.search(r"(\d+)\s*/\s*(\d+)", reporting_el.get_text() if reporting_el else "")
        reporting, total = (int(m.group(1)), int(m.group(2))) if m else (0, 0)

        candidates = []
        for box_d in wrapper.select("div.display-results-box-d"):
            name_el = box_d.find("h1")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if name == "Write-In":
                continue
            section = box_d.find_parent("div", class_="section")
            votes_el = section.select_one("div.display-results-box-f h1") if section else None
            votes = int(votes_el.get_text(strip=True).replace(",", "")) if votes_el else 0
            candidates.append((name, votes))
        return candidates, reporting, total

    return [], 0, 0


def ingest(county_slug: str, cid: str, county_fips: str, county_name: str,
           db_path: str = DB, db_race_type: str = "mi_primary_2026",
           mi_total_counties: int = 83):
    candidates, reporting, total = fetch_senate_dem(county_slug, cid)
    pid = f"MI-{county_fips}-CTY"

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id=?",
                 (db_race_type, pid))
    payload = []
    for cand, votes in candidates:
        payload.append((pid, db_race_type, cand, "DEM", votes,
                        votes / max(sum(v for _, v in candidates), 1),
                        # precincts_reporting/total_precincts track COUNTIES
                        # in/out of 83 for MI (county-pseudo-precinct pattern),
                        # matching mi_live_feed.py's convention — NOT this
                        # county's own internal precinct count (that's a
                        # separate, more granular number TotalVote tracks
                        # for itself, not what our schema stores here).
                        1, mi_total_counties, "all"))
    conn.executemany(
        """INSERT INTO results_live
           (precinct_id, race_type, candidate, party, votes, vote_share,
            precincts_reporting, total_precincts, mode)
           VALUES (?,?,?,?,?,?,?,?,?)""", payload)
    conn.commit()
    conn.close()
    return {"county": county_name, "county_precincts_reporting": reporting,
            "county_precincts_total": total, "rows": len(payload),
            "candidates": candidates}


if __name__ == "__main__":
    import sys
    slug = sys.argv[1] if len(sys.argv) > 1 else "Wayne"
    cid = sys.argv[2] if len(sys.argv) > 2 else "05"
    fips = sys.argv[3] if len(sys.argv) > 3 else "26163"
    name = sys.argv[4] if len(sys.argv) > 4 else "WAYNE"
    s = ingest(slug, cid, fips, name)
    print(f"{name}: {s['county_precincts_reporting']}/{s['county_precincts_total']} "
          f"county precincts in, {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
