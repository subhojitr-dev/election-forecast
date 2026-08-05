"""mi_pdf_feed.py — generic MI county live results via a periodically-updated
PDF report (a common county-clerk software template, not one county's one-off).

Discovered 2026-08-04 with Livingston, generalized 2026-08-05 after finding
Muskegon uses the same report style but with a DIFFERENT number of
voting-method columns (Election Day / Absentee / Early-County / Early-Local /
Total = 5 pairs, vs Livingston's Early/Absentee/Precinct/Total = 4 pairs).
The parser below handles any number of (count, pct%) column-pairs per
candidate, always taking the LAST pair as the "Total" column — so it should
generalize to other counties on this same report template without further
changes, as long as the contest-header text still contains
"United States Senator - Democratic" as a substring (confirmed true for both
Livingston's "...Democratic" and Muskegon's "...Democratic Party - Vote for
not more than 1") and "Total" remains the rightmost column.

No robots.txt restriction found on any county site checked so far. County's
own official public results PDF, same category as everywhere else.

Usage:
    python ingestor/mi_pdf_feed.py <pdf_url> <county_fips> <county_name>
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

CONTEST_HEADER = "United States Senator - Democratic"

# Name line, then N >= 1 (count, pct%) column-pairs -- take the LAST pair as
# the Total column, whatever N happens to be for this county's report.
_CAND_RE = re.compile(
    r"([A-Z][A-Za-z.\'\- ]+?)\n"
    r"((?:[\d,]+\n[\d.]+%\n){1,8})"
)


def _last_count(blob: str) -> int:
    lines = [l for l in blob.strip().split("\n") if l]
    counts = lines[0::2]   # count, pct, count, pct, ... -> counts at even indices
    return int(counts[-1].replace(",", ""))


def fetch_senate_dem(pdf_url: str):
    """Returns [(candidate, total_votes), ...] for the DEM US Senate primary."""
    r = httpx.get(pdf_url, timeout=25, headers={"User-Agent": "Mozilla/5.0"},
                  follow_redirects=True)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() for p in reader.pages)

    start = text.find(CONTEST_HEADER)
    if start == -1:
        return []
    end = text.find("Cast Votes:", start)
    section = text[start:end if end != -1 else start + 2500]

    candidates = []
    for m in _CAND_RE.finditer(section):
        name = m.group(1).strip()
        if name.lower() in ("choice", "party") or not name:
            continue
        candidates.append((name, _last_count(m.group(2))))
    return candidates


def ingest(pdf_url: str, county_fips: str, county_name: str,
           db_path: str = DB, db_race_type: str = "mi_primary_2026",
           mi_total_counties: int = 83):
    candidates = fetch_senate_dem(pdf_url)
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
    return {"county": county_name, "rows": len(payload), "candidates": candidates}


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else (
        "https://milivcounty.gov/wp-content/uploads/All-Candidate-and-Proposal-Report-8-4-2026.pdf")
    fips = sys.argv[2] if len(sys.argv) > 2 else "26093"
    name = sys.argv[3] if len(sys.argv) > 3 else "LIVINGSTON"
    s = ingest(url, fips, name)
    print(f"{name}: {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
