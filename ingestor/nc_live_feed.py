"""nc_live_feed.py — NC live ingestion into results_live (county level).

Reads NCSBE (via nc_ingestor) for a contest and writes county-pseudo-precinct
rows (NC-{fips}-CTY) into results_live, split by ballot mode. Joins 1:1 to the
county-pseudo NC baseline (etl_nc_county_baseline.py), so the existing analytics
compute NC's shift / win-prob / county table unchanged.

On election night this is called on a schedule (the NCSBE file updates as
counties report) — it replaces the "Next Batch" simulator for NC. No 403 issues.

CLI (test against a past NC election):
  python ingestor/nc_live_feed.py 2020-11-03 "US SENATE" senate
"""
from __future__ import annotations

import os
import sqlite3

from nc_ingestor import fetch_results_pct, parse_county

DB = os.path.join("data", "db", "baseline.db")


def county_fips_map(conn):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT county, county_fips FROM precincts WHERE id LIKE 'NC-%-CTY'")}


def ingest(date_iso, contest_filter, race_type="senate", db_path=DB):
    """Fetch NCSBE + write NC county results into results_live. Returns a summary."""
    rows = parse_county(fetch_results_pct(date_iso), contest_filter)
    conn = sqlite3.connect(db_path)
    cf = county_fips_map(conn)
    rows = [r for r in rows if r["county"] in cf]      # keep matchable counties
    present = {r["county"] for r in rows}
    ctot: dict = {}
    for r in rows:
        ctot[r["county"]] = ctot.get(r["county"], 0) + r["votes"]

    # clear ALL NC live rows for this race (incl. any leftover precinct-level rows
    # from prior sim/test runs) so only this feed's county totals remain
    conn.execute("DELETE FROM results_live WHERE race_type=? AND precinct_id LIKE 'NC-%'",
                 (race_type,))
    payload = []
    for r in rows:
        pid = f"NC-{cf[r['county']]}-CTY"
        ct = ctot.get(r["county"], 0)
        for mode, v in r["modes"].items():
            if v:
                payload.append((pid, race_type, r["candidate"], r["party"], v,
                                (v / ct) if ct else 0.0, len(present), len(cf), mode))
    conn.executemany(
        """INSERT INTO results_live
           (precinct_id, race_type, candidate, party, votes, vote_share,
            precincts_reporting, total_precincts, mode)
           VALUES (?,?,?,?,?,?,?,?,?)""", payload)
    conn.commit()
    d = sum(r["votes"] for r in rows if r["party"] == "DEM")
    rr = sum(r["votes"] for r in rows if r["party"] == "REP")
    conn.close()
    return {"counties_in": len(present), "counties_total": len(cf),
            "rows": len(payload), "dem": d, "rep": rr}


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2020-11-03"
    contest = sys.argv[2] if len(sys.argv) > 2 else "US SENATE"
    race = sys.argv[3] if len(sys.argv) > 3 else "senate"
    print(f"NC live ingest — {date} · {contest!r} -> results_live (race={race})")
    s = ingest(date, contest, race)
    tot = s["dem"] + s["rep"] or 1
    print(f"  counties reporting: {s['counties_in']}/{s['counties_total']}   "
          f"rows written: {s['rows']}")
    print(f"  live two-party: D {s['dem']:,} ({100*s['dem']/tot:.1f}%)   "
          f"R {s['rep']:,} ({100*s['rep']/tot:.1f}%)   "
          f"winner: {'D' if s['dem'] > s['rep'] else 'R'}")
