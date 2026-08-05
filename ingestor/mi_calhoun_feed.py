"""mi_calhoun_feed.py — Calhoun County, MI live results (its own custom-built
page at elections.calhouncountymi.gov, distinct from every other system found
so far). Server-side rendered HTML with real semantic markup: each contest is
a `<div class="contest" data-search="...">` containing a clean result table —
easy to parse reliably.

Discovered 2026-08-05. No robots.txt restriction found. County's own official
public results page, same category as everywhere else.

Usage:
    python ingestor/mi_calhoun_feed.py
"""
from __future__ import annotations

import os
import sqlite3

import httpx
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "data", "db", "baseline.db")
URL = "https://elections.calhouncountymi.gov/August2026/"


def fetch_senate_dem():
    """Returns [(candidate, votes), ...] for the DEM US Senate primary."""
    r = httpx.get(URL, timeout=25, headers={"User-Agent": "Mozilla/5.0"},
                  follow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    for div in soup.select("div.contest"):
        search = (div.get("data-search") or "").lower()
        if "senator" not in search or "dem" not in search:
            continue
        candidates = []
        for row in div.select("table.result-table tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            name = cells[0].get_text(strip=True)
            if name.lower() == "write-in":
                continue
            votes = int(cells[3].get_text(strip=True).replace(",", "") or 0)
            candidates.append((name, votes))
        return candidates
    return []


def ingest(db_path: str = DB, db_race_type: str = "mi_primary_2026",
           county_fips: str = "26025", mi_total_counties: int = 83):
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
    return {"county": "CALHOUN", "rows": len(payload), "candidates": candidates}


if __name__ == "__main__":
    s = ingest()
    print(f"CALHOUN: {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
