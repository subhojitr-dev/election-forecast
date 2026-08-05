"""mi_enhancedvoting_feed.py — Michigan county-level live results via EnhancedVoting.

Discovered 2026-08-04, alongside mi_totalvote_feed.py: Michigan's central state
system doesn't show live partial results (see mi_live_feed.py), so this pulls
individual counties from whichever live vendor system they actually run.
EnhancedVoting is a second such vendor (confirmed: Kent County, MI, and
separately Lake County, MI use it — GA's OWN state system, results.enr.
clarityelections.com, is a DIFFERENT company/product, not related despite
both having "voting" in searches for them; don't confuse the two).

Much better data quality than TotalVote's Wayne page: EnhancedVoting exposes
a clean JSON API (no HTML scraping needed), and Kent reports far more
granularly and completely (77/202 precincts vs Wayne's 1/720 at the same
point in the night).

No robots.txt restriction found. Same category as every other state ENR
system this project uses -- the county's own official public results page.

API pattern (confirmed working for Kent):
    https://app.enhancedvoting.com/results/public/api/elections/{slug}/{election_id}/data
    slug example: "kent-county-mi"   election_id example: "08042026"
Guessed slugs for Oakland/Macomb/Genesee/Washtenaw/Ingham/Ottawa all 204'd
(endpoint exists, no data) — those counties are NOT on EnhancedVoting, this
isn't a slug-guessing problem. Add more (slug, name) tuples below only once
confirmed working, the same way Kent was.

Usage:
    python ingestor/mi_enhancedvoting_feed.py kent-county-mi 08042026 26081 KENT
"""
from __future__ import annotations

import os
import sqlite3

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "data", "db", "baseline.db")
BASE = "https://app.enhancedvoting.com/results/public/api/elections"

CONTEST_NAME = "United States Senator (DEM)"


def fetch_senate_dem(slug: str, election_id: str):
    """Returns (candidates, reporting_units, total_units) for the DEM US
    Senate primary in this county. candidates is [(name, votes), ...]."""
    url = f"{BASE}/{slug}/{election_id}/data"
    r = httpx.get(url, timeout=20, follow_redirects=True,
                  headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()

    for item in data.get("ballotItems", []):
        name = item["name"][0]["text"] if item.get("name") else ""
        if name != CONTEST_NAME:
            continue
        rs = item.get("reportingStatus") or {}
        reporting = rs.get("reportingUnits", 0)
        total = rs.get("totalUnits", 0)
        candidates = []
        for opt in item.get("summaryResults", {}).get("ballotOptions", []):
            cand_name = opt["name"][0]["text"] if opt.get("name") else ""
            if opt.get("isWriteIn"):
                continue
            candidates.append((cand_name, opt.get("voteCount", 0)))
        return candidates, reporting, total

    return [], 0, 0


def ingest(slug: str, election_id: str, county_fips: str, county_name: str,
           db_path: str = DB, db_race_type: str = "mi_primary_2026",
           mi_total_counties: int = 83):
    candidates, reporting, total = fetch_senate_dem(slug, election_id)
    pid = f"MI-{county_fips}-CTY"

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id=?",
                 (db_race_type, pid))
    payload = []
    tot_votes = sum(v for _, v in candidates) or 1
    for cand, votes in candidates:
        payload.append((pid, db_race_type, cand, "DEM", votes, votes / tot_votes,
                        # precincts_reporting/total_precincts track COUNTIES
                        # in/out of 83 (county-pseudo-precinct convention),
                        # matching mi_live_feed.py / mi_totalvote_feed.py.
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
    slug = sys.argv[1] if len(sys.argv) > 1 else "kent-county-mi"
    eid = sys.argv[2] if len(sys.argv) > 2 else "08042026"
    fips = sys.argv[3] if len(sys.argv) > 3 else "26081"
    name = sys.argv[4] if len(sys.argv) > 4 else "KENT"
    s = ingest(slug, eid, fips, name)
    print(f"{name}: {s['county_precincts_reporting']}/{s['county_precincts_total']} "
          f"county precincts in, {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
