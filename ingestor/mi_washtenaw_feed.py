"""mi_washtenaw_feed.py — Washtenaw County, MI live results (its own custom
system, distinct from both TotalVote (Wayne) and EnhancedVoting (Kent)).

Discovered 2026-08-04: Michigan's central state system shows nothing live
(see mi_live_feed.py's docstring), so this is a third county-level source,
found via washtenaw.org's own "Unofficial Election Results" link. Genuinely
comprehensive real-time reporting: statewide report timestamp, per-precinct
completion counts, every race on the ballot -- a static-ish HTML table
report, regenerated periodically (no JSON API found).

No robots.txt restriction found on electionresults.ewashtenaw.org. County's
own official public results page, same category as everywhere else.

Usage:
    python ingestor/mi_washtenaw_feed.py
"""
from __future__ import annotations

import os
import sqlite3

import httpx
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "data", "db", "baseline.db")
URL = "https://electionresults.ewashtenaw.org/electionreporting/aug2026/index.jsp"

CONTEST_TITLE = "US Senator DEM"


def fetch_senate_dem():
    """Returns [(candidate, votes), ...] for the DEM US Senate primary."""
    r = httpx.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    candidates = []
    in_section = False
    for tr in soup.find_all("tr"):
        header = tr.find("td", class_="headertr")
        if header:
            in_section = header.get_text(strip=True) == CONTEST_TITLE
            continue
        if not in_section:
            continue
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        name = tds[0].get_text(strip=True)
        if name.lower() in ("rejected write-ins", "unassigned write-ins"):
            continue
        votes = int(tds[4].get_text(strip=True).replace(",", "") or 0)
        candidates.append((name, votes))
    return candidates


def ingest(db_path: str = DB, db_race_type: str = "mi_primary_2026",
           county_fips: str = "26161", mi_total_counties: int = 83):
    candidates = fetch_senate_dem()
    pid = f"MI-{county_fips}-CTY"

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id=?",
                 (db_race_type, pid))
    payload = []
    tot_votes = sum(v for _, v in candidates) or 1
    for cand, votes in candidates:
        payload.append((pid, db_race_type, cand, "DEM", votes, votes / tot_votes,
                        1, mi_total_counties, "all"))
    conn.executemany(
        """INSERT INTO results_live
           (precinct_id, race_type, candidate, party, votes, vote_share,
            precincts_reporting, total_precincts, mode)
           VALUES (?,?,?,?,?,?,?,?,?)""", payload)
    conn.commit()
    conn.close()
    return {"county": "WASHTENAW", "rows": len(payload), "candidates": candidates}


if __name__ == "__main__":
    s = ingest()
    print(f"WASHTENAW: {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
