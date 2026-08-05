"""mi_clarity_feed.py — Michigan county-level live results via Clarity/SOE
Software (the same classic ENR platform sc_live_feed.py already uses for SC).

Discovered 2026-08-05: Oakland, Macomb, Genesee, and Ottawa's official results
pages all turned out to be Clarity, not "not activated" as first concluded on
Aug 4 night (that conclusion was wrong — caused by stale electionIds found via
generic web search; the correct, current URLs came from going straight to each
county's own official elections page). Unlike SC, where ONE Clarity instance
covers the whole state, MI's Clarity is scoped PER COUNTY — each county runs
its own separate instance at its own URL.

Mechanism (same classic Clarity discovery SC uses):
    {base}/{election_id}/current_ver.txt          -> plain-text version number
    {base}/{election_id}/{version}/json/en/summary.json
        -> a flat JSON array, ALL contests for this one county in one call:
           [{"C": "<contest name>", "CH": [candidate names...],
             "P": [party per candidate...], "V": [votes per candidate...],
             "PR": precincts_reporting, "TP": total_precincts}, ...]

**Requires a real browser User-Agent** — CloudFront (fronting this endpoint)
403s a bare/default User-Agent, even though there's no other bot-mitigation
(confirmed: no robots.txt restriction, and once a normal UA is set, plain
httpx works fine, no Cloudflare/WAF challenge of any kind).

**base_url varies by county — some are white-labeled**, not all on
results.enr.clarityelections.com:
    Oakland: https://results.enr.clarityelections.com/MI/OaklandMI  (electionId 127075)
             — note "OaklandMI", not "Oakland" (that's a different, stale
             jurisdiction pointing at an old May 2026 local election)
    Macomb:  https://results.enr.clarityelections.com/MI/Macomb     (electionId 126774)
    Genesee: https://results.enr.clarityelections.com/MI/Genesee    (electionId 126773)
    Ottawa:  https://www.miottawavotes.gov/MI/Ottawa                (electionId 126772)
             — white-labeled on the county's own domain, same platform underneath

**Contest name format varies, same lesson as mi_enhancedvoting_feed.py** — seen
both "DEM United States Senator" (Macomb) and "United States Senator - Dem"
(Oakland's HTML rendering). Matched via substring ("senator" + "dem",
case-insensitive), not an exact string.

Usage:
    python ingestor/mi_clarity_feed.py https://results.enr.clarityelections.com/MI/Macomb 126774 26099 MACOMB
"""
from __future__ import annotations

import os
import sqlite3

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "data", "db", "baseline.db")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def _get(url, timeout=25):
    r = httpx.get(url, timeout=timeout, headers={"User-Agent": UA}, follow_redirects=True)
    r.raise_for_status()
    return r


def current_version(base_url: str, election_id: str) -> str:
    return _get(f"{base_url}/{election_id}/current_ver.txt").text.strip()


def _is_senate_dem_contest(item: dict) -> bool:
    """Party marker location varies by county (found 2026-08-05): Macomb
    prefixes it into the contest name ("DEM United States Senator"); Oakland's
    HTML shows a "- Dem" suffix; Ottawa doesn't put it in the name at all —
    it's only in the separate "CAT" field ("Democratic"/"Republican"). Check
    both, and also fall back to the candidates' own "P" (party) array being
    all-DEM, so this doesn't silently miss a county with yet another format."""
    name = (item.get("C") or "").lower()
    cat = (item.get("CAT") or "").lower()
    if "senator" not in name:
        return False
    if "dem" in name or "dem" in cat:
        return True
    parties = item.get("P") or []
    return bool(parties) and all(p == "DEM" for p in parties)


def fetch_senate_dem(base_url: str, election_id: str):
    """Returns (candidates, reporting, total) for this county's DEM US Senate
    primary. candidates is [(name, votes), ...]."""
    version = current_version(base_url, election_id)
    data = _get(f"{base_url}/{election_id}/{version}/json/en/summary.json").json()
    for item in data:
        if not _is_senate_dem_contest(item):
            continue
        candidates = []
        for cand, votes in zip(item.get("CH", []), item.get("V", [])):
            if "write-in" in cand.lower():
                continue
            candidates.append((cand, votes))
        return candidates, item.get("PR", 0), item.get("TP", 0)
    return [], 0, 0


def ingest(base_url: str, election_id: str, county_fips: str, county_name: str,
           db_path: str = DB, db_race_type: str = "mi_primary_2026",
           mi_total_counties: int = 83):
    candidates, reporting, total = fetch_senate_dem(base_url, election_id)
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
    return {"county": county_name, "county_precincts_reporting": reporting,
            "county_precincts_total": total, "rows": len(payload),
            "candidates": candidates}


if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else "https://results.enr.clarityelections.com/MI/Macomb"
    eid = sys.argv[2] if len(sys.argv) > 2 else "126774"
    fips = sys.argv[3] if len(sys.argv) > 3 else "26099"
    name = sys.argv[4] if len(sys.argv) > 4 else "MACOMB"
    s = ingest(base, eid, fips, name)
    print(f"{name}: {s['county_precincts_reporting']}/{s['county_precincts_total']} "
          f"county precincts in, {s['rows']} candidate rows written")
    for cand, votes in s["candidates"]:
        print(f"  {cand}: {votes:,}")
