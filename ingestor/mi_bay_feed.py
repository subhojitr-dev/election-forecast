"""mi_bay_feed.py — Bay County, MI live results via its own periodically-
regenerated PDF report ("Summary Results Report"). A genuine one-off: Bay's
report template is NOT the same as mi_pdf_feed.py's (Livingston/Muskegon)
template — no percentage columns, and TOTAL is the FIRST number on each
candidate's line, not the last:

    DEM United States Senator
    Abdul El-Sayed 6,163 3,268 2,626 269
    Mallory McMorrow 961 324 626 11
    Haley Stevens 8,165 3,339 4,692 134
    Write-In Totals 15 8 7 0

(the 3 trailing numbers are Election Day / Absentee / Early Voting and sum
to the TOTAL — confirmed: 3,268+2,626+269 = 6,163).

Discovered 2026-08-05. No robots.txt restriction found. County's own official
public results PDF, same category as everywhere else.

Usage:
    python ingestor/mi_bay_feed.py
"""
from __future__ import annotations

import io
import os
import re
import sqlite3

import httpx
from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "data", "db", "baseline.db")
URL = ("https://www.baycountymi.gov/Documents/Departments/Clerk/Elections/"
       "Election%20Results/August%204,%202026%20Primary%20Election%20"
       "Summary%20Unofficial.pdf")

CONTEST_HEADER = "DEM United States Senator"
_CAND_RE = re.compile(
    r"([A-Z][A-Za-z.\'\- ]+?) ([\d,]+) [\d,]+ [\d,]+ [\d,]+"
)


def fetch_senate_dem():
    """Returns [(candidate, total_votes), ...] for the DEM US Senate primary."""
    r = httpx.get(URL, timeout=25, headers={"User-Agent": "Mozilla/5.0"},
                  follow_redirects=True)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() for p in reader.pages)

    start = text.find(CONTEST_HEADER)
    if start == -1:
        return []
    end = text.find("Vote For 1", start)
    section = text[start:end if end != -1 else start + 1000]

    candidates = []
    for m in _CAND_RE.finditer(section):
        name = m.group(1).strip()
        if name.lower().startswith("write-in") or not name:
            continue
        candidates.append((name, int(m.group(2).replace(",", ""))))
    return candidates


def ingest(db_path: str = DB, db_race_type: str = "mi_primary_2026",
           county_fips: str = "26017", mi_total_counties: int = 83):
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
    return {"county": "BAY", "rows": len(payload), "candidates": candidates}


if __name__ == "__main__":
    s = ingest()
    print(f"BAY: {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
