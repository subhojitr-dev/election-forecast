"""mi_livingston_feed.py — Livingston County, MI live results (a PDF report,
regenerated periodically on election night, distinct from every other county
system found so far — Wayne/TotalVote, Kent/EnhancedVoting, Washtenaw/custom
HTML).

Discovered 2026-08-04: found via milivcounty.gov's "Election Results" page,
which links a dated "All Candidate and Proposal Report" PDF
(All-Candidate-and-Proposal-Report-8-4-2026.pdf) that Livingston's clerk
re-uploads as counting progresses (confirmed: "Run Time"/"Run Date" stamped
inside the PDF itself, e.g. 10:26 PM 08/04/2026 -- genuinely fresh, not a
static file).

No robots.txt restriction found. County's own official public results PDF,
same category as everywhere else.

Usage:
    python ingestor/mi_livingston_feed.py
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
URL = "https://milivcounty.gov/wp-content/uploads/All-Candidate-and-Proposal-Report-8-4-2026.pdf"

CONTEST_HEADER = "United States Senator - Democratic"

# Name line, then 4x (count, pct%) pairs -- early/absentee/precinct/total.
_CAND_RE = re.compile(
    r"([A-Z][A-Za-z.\'\- ]+?)\n"
    r"[\d,]+\n[\d.]+%\n"
    r"[\d,]+\n[\d.]+%\n"
    r"[\d,]+\n[\d.]+%\n"
    r"([\d,]+)\n[\d.]+%"
)


def fetch_senate_dem():
    """Returns [(candidate, total_votes), ...] for the DEM US Senate primary."""
    r = httpx.get(URL, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() for p in reader.pages)

    start = text.find(CONTEST_HEADER)
    if start == -1:
        return []
    end = text.find("Cast Votes:", start)
    section = text[start:end if end != -1 else start + 2000]

    candidates = []
    for m in _CAND_RE.finditer(section):
        name = m.group(1).strip()
        if name.lower() in ("choice", "party") or not name:
            continue
        candidates.append((name, int(m.group(2).replace(",", ""))))
    return candidates


def ingest(db_path: str = DB, db_race_type: str = "mi_primary_2026",
           county_fips: str = "26093", mi_total_counties: int = 83):
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
    return {"county": "LIVINGSTON", "rows": len(payload), "candidates": candidates}


if __name__ == "__main__":
    s = ingest()
    print(f"LIVINGSTON: {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
